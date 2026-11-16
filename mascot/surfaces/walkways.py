# -*- coding: utf-8 -*-
"""
ウィンドウ上の歩行の窓口。Pet はこのクラスだけを知っていればよい(注入される)。
依存: system(取得口), surfaces 内, diagnostics。

  WalkSurfaces = 取得口 + 監視スレッド(WindowWatcher) + 足場の地図(SurfaceMap) + ジャンプ計画

使えない環境(Wayland・必要なライブラリが無い・取得に失敗し続けた等)では active が False になり、
Pet は従来どおり画面下端だけを歩く。理由は unavailable_reason() で取れる(設定画面で表示)。
"""
from mascot.diagnostics import LOG
from mascot.surfaces.geometry import window_to_logical
from mascot.surfaces.planner import plan_hop
from mascot.surfaces.surface_map import SurfaceMap
from mascot.surfaces.watcher import WindowWatcher
from mascot.system.window_api import NullProvider
from mascot.system.window_factory import create_provider


DROP_GRACE = 0.12      # 離したとき足元が上端よりこの割合(体の高さ比)まで下でも、上端に乗せる


class WalkSurfaces:
    def __init__(self, provider, watcher=None):
        self.provider = provider
        self.watcher = watcher or WindowWatcher(provider)
        self.map = SurfaceMap()
        self._enabled = True
        self._key = None               # 地図を作り直す必要があるかの判定用
        self._track_v = -1
        self._screens = []
        self._body_h = 100.0

    # ---- 状態 -------------------------------------------------------------
    @property
    def active(self):
        """いま足場を使ってよいか(設定が有効で、取得口が使える)。"""
        if not self._enabled or isinstance(self.provider, NullProvider):
            return False
        return self.watcher.status in ("idle", "starting", "running")

    def unavailable_reason(self):
        """使えない理由(使える場合は空文字)。設定画面での表示用。"""
        if isinstance(self.provider, NullProvider):
            return self.provider.reason
        if self.watcher.status in ("unavailable", "failed"):
            return self.provider.reason or "ウィンドウ情報を取得できませんでした。"
        return ""

    def set_enabled(self, flag):
        self._enabled = bool(flag)
        self.watcher.set_active(self._enabled)

    def start(self):
        if isinstance(self.provider, NullProvider):
            LOG.info("他のウィンドウの上を歩く機能は使えません: %s", self.provider.reason)
            return
        self.watcher.start()

    def stop(self):
        self.watcher.stop()

    # ---- GUIスレッドから毎フレーム呼ぶ(軽い) -------------------------------
    def update(self, screens, body_w, body_h):
        """最新の走査結果・追従中の位置を取り込む。作り直しは走査が更新されたときだけ。"""
        self._body_h = body_h
        snap = self.watcher.latest()
        key = (snap.scan_version, id(screens), round(body_w), round(body_h))
        if key != self._key:
            self._key = key
            self._screens = screens
            self.map.rebuild(snap.windows, screens, body_w, body_h, self.provider.native_pixels)
            self._track_v = -1
        if snap.track_version != self._track_v:
            self._track_v = snap.track_version
            rect = (window_to_logical(snap.tracked, screens, self.provider.native_pixels)
                    if snap.tracked is not None else None)
            self.map.set_tracked(snap.tracked_wid, rect, snap.tracked_ready)

    def track(self, wid):
        self.watcher.track(wid)

    def rect_now(self, wid):
        return self.map.rect_now(wid)

    def forget(self, wid):
        """ウィンドウが消えていた: 足場から外し、すぐ走査し直す。"""
        self.map.forget(wid)
        self.watcher.request_scan()

    def interval(self, wid, foot_x):
        return self.map.interval(wid, foot_x)

    def landing(self, foot_x, prev_feet, new_feet):
        r = self.map.landing(foot_x, prev_feet, new_feet, DROP_GRACE * self._body_h)
        if r is None:
            return None
        return {"wid": r[0], "y": r[1], "lo": r[2], "hi": r[3]}

    def plan_hop(self, foot_x, feet_y, body_w, body_h, gravity, top_limit, exclude_wid=None):
        return plan_hop(self.map.ledges_now(), foot_x, feet_y, body_w, body_h, gravity,
                        top_limit, exclude_wid)


def create_walk_surfaces(cfg, provider=None):
    """設定に従って WalkSurfaces を作る(開始は呼び出し側が start())。"""
    ws = WalkSurfaces(provider if provider is not None else create_provider())
    ws.set_enabled(cfg.get("walk_on_windows", True))
    return ws
