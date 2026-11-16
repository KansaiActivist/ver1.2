# -*- coding: utf-8 -*-
"""
macOS 用のウィンドウ取得口(任意の追加ライブラリ pyobjc-framework-Quartz を使う)。
依存: system.window_api のみ。

  ・CGWindowListCopyWindowInfo の「位置・大きさ・レイヤー・所有プロセス」だけを使う。
    ウィンドウのタイトル(画面収録の許可が必要な項目)は読まないので、許可ダイアログは出ない想定。
  ・座標は論理座標(ポイント)なので native_pixels = False。
  ・Quartz が無ければ使えない旨を reason に入れて無効になる。
"""
import os

from mascot.system.window_api import REASON_NO_QUARTZ, WindowInfo, WindowProvider

MIN_W, MIN_H = 60, 30


def _quartz_source():
    """Quartz から生のウィンドウ辞書のリストを返す関数を作る。"""
    from Quartz import (CGWindowListCopyWindowInfo, kCGNullWindowID,
                        kCGWindowListExcludeDesktopElements, kCGWindowListOptionIncludingWindow,
                        kCGWindowListOptionOnScreenOnly)
    all_opts = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements

    def source(wid=None):
        if wid is None:
            return list(CGWindowListCopyWindowInfo(all_opts, kCGNullWindowID) or [])
        return list(CGWindowListCopyWindowInfo(kCGWindowListOptionIncludingWindow, wid) or [])
    return source


class MacProvider(WindowProvider):
    name = "macos"
    native_pixels = False

    def __init__(self, source=None, pid=None):
        self._source = source
        self._pid = os.getpid() if pid is None else pid

    def open(self):
        if self._source is None:
            try:
                self._source = _quartz_source()
            except Exception:
                self.reason = REASON_NO_QUARTZ
                return False
        return True

    def _parse(self, d):
        if d.get("kCGWindowLayer", 0) != 0:
            return None                          # メニューバー・Dock・通知などは別レイヤー
        if d.get("kCGWindowOwnerPID") == self._pid:
            return None
        if float(d.get("kCGWindowAlpha", 1.0)) <= 0.0:
            return None
        if "kCGWindowIsOnscreen" in d and not d["kCGWindowIsOnscreen"]:
            return None
        b = d.get("kCGWindowBounds")
        if not b:
            return None
        w, h = int(b["Width"]), int(b["Height"])
        if w < MIN_W or h < MIN_H:
            return None
        return WindowInfo(int(d["kCGWindowNumber"]), int(b["X"]), int(b["Y"]), w, h)

    def list_windows(self):
        out = []
        for d in self._source():                 # 手前から奥の順
            try:
                w = self._parse(d)
            except Exception:
                continue
            if w is not None:
                out.append(w)
        return out

    def get_rect(self, wid):
        try:
            for d in self._source(wid):
                if int(d.get("kCGWindowNumber", -1)) == wid:
                    return self._parse(d)
        except Exception:
            pass
        return None
