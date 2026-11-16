# -*- coding: utf-8 -*-
"""
ウィンドウの監視スレッド。依存: diagnostics のみ(Qt も OS も直接は使わない。取得口は外から渡される)。

毎フレームの全走査はしない。2段階で更新する:
  ・全ウィンドウの走査 … scan_interval(既定0.3秒)ごと。足場の候補の更新用
  ・乗っているウィンドウ(track)の位置だけ … track_interval(既定10ms)ごと。移動への追従用
    (1つのウィンドウの矩形取得は軽い。何も乗っていなければ行わない)

取得口はこのスレッドからだけ呼ぶ。結果は不変の Snapshot として丸ごと差し替えるので、
GUI側は latest() で受け取るだけでよい(ロック待ちはほぼ発生しない)。
取得に連続で失敗したら、無理に続けず status="failed" にして止まる(画面下端だけの歩行に戻る)。
"""
import threading
import time
from dataclasses import dataclass

from mascot.diagnostics import LOG


@dataclass(frozen=True)
class Snapshot:
    scan_version: int = 0
    windows: tuple = ()              # WindowInfo(手前→奥)。生の座標
    tracked_wid: object = None       # いま追従しているウィンドウ
    tracked_ready: bool = False      # tracked が取得済みか(False の間は走査結果で代用する)
    tracked: object = None           # WindowInfo / None(= 消えた・最小化)
    track_version: int = 0


class WindowWatcher:
    def __init__(self, provider, scan_interval=0.3, track_interval=0.01, max_failures=5,
                 clock=time.monotonic):
        self.provider = provider
        self.scan_interval = scan_interval
        self.track_interval = track_interval
        self.max_failures = max_failures
        self._clock = clock
        self.status = "idle"         # idle / running / unavailable / failed / stopped
        self.scan_count = 0          # 全走査した回数(テスト・診断用)
        self.track_count = 0
        self._lock = threading.Lock()
        self._snap = Snapshot()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._active = threading.Event()
        self._active.set()
        self._scan_req = False
        self._thread = None

    # ---- 外から使う操作(どのスレッドからでも可) ---------------------------
    def start(self):
        if self._thread is not None:
            return
        self.status = "starting"
        self._thread = threading.Thread(target=self._run, name="window-watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout=3.0):
        self._stop.set()
        self._wake.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout)
            if t.is_alive():
                LOG.warning("ウィンドウ監視スレッドが時間内に終了しませんでした")
        self.status = "stopped"

    def set_active(self, flag):
        """False の間は走査も追従もしない(設定でオフのとき)。"""
        if flag:
            self._active.set()
            self._scan_req = True
        else:
            self._active.clear()
        self._wake.set()

    def track(self, wid):
        """このウィンドウの位置を高頻度で追う(None で解除)。"""
        with self._lock:
            if self._snap.tracked_wid == wid:
                return
            s = self._snap
            self._snap = Snapshot(s.scan_version, s.windows, wid, False, None, s.track_version + 1)
        self._wake.set()

    def request_scan(self):
        self._scan_req = True
        self._wake.set()

    def latest(self):
        with self._lock:
            return self._snap

    # ---- スレッド本体 -----------------------------------------------------
    def _publish_scan(self, windows):
        with self._lock:
            s = self._snap
            self._snap = Snapshot(s.scan_version + 1, tuple(windows), s.tracked_wid,
                                  s.tracked_ready, s.tracked, s.track_version)

    def _publish_tracked(self, wid, rect):
        with self._lock:
            s = self._snap
            if s.tracked_wid != wid:
                return                       # 取得中に追従先が変わった → 古い結果は捨てる
            if s.tracked_ready and s.tracked == rect:
                return                       # 変化なし
            self._snap = Snapshot(s.scan_version, s.windows, wid, True, rect, s.track_version + 1)

    def _run(self):
        try:
            ok = self.provider.open()
        except Exception:
            LOG.exception("ウィンドウ取得口の初期化に失敗しました")
            ok = False
        if not ok:
            self.status = "unavailable"
            LOG.info("他のウィンドウの上を歩く機能は使えません: %s",
                     getattr(self.provider, "reason", "") or "(理由不明)")
            return
        self.status = "running"
        LOG.info("ウィンドウ監視を開始しました (%s)", self.provider.name)
        next_scan = 0.0
        failures = 0
        try:
            while not self._stop.is_set():
                if not self._active.is_set():
                    self._wake.wait(0.5)
                    self._wake.clear()
                    continue
                now = self._clock()
                try:
                    if self._scan_req or now >= next_scan:
                        self._scan_req = False
                        self._publish_scan(self.provider.list_windows())
                        self.scan_count += 1
                        next_scan = now + self.scan_interval
                    wid = self.latest().tracked_wid
                    if wid is not None:
                        self._publish_tracked(wid, self.provider.get_rect(wid))
                        self.track_count += 1
                    failures = 0
                except Exception:
                    failures += 1
                    if failures == 1:
                        LOG.exception("ウィンドウ情報の取得に失敗しました")
                    if failures >= self.max_failures:
                        self.status = "failed"
                        LOG.warning("取得が続けて失敗したため、ウィンドウ上の歩行を止めます")
                        return
                tracking = self.latest().tracked_wid is not None
                wait = self.track_interval if tracking else max(0.0, next_scan - self._clock())
                self._wake.wait(wait)
                self._wake.clear()
        finally:
            try:
                self.provider.close()
            except Exception:
                pass
