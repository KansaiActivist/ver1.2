# -*- coding: utf-8 -*-
"""
Linux(X11)用のウィンドウ取得口(任意の追加ライブラリ python-xlib を使う)。
依存: system.window_api のみ。

  _XlibAdapter … python-xlib の呼び出し(判断を持たない)
  X11Provider  … どのウィンドウを足場にするかの判断(adapter を差し替えてテストできる)

Wayland では使えない(window_api.create_provider が事前に弾く)。
"""
import os

from mascot.system.window_api import REASON_NO_XLIB, WindowInfo, WindowProvider

MIN_W, MIN_H = 60, 30
ALL_DESKTOPS = 0xFFFFFFFF


class _XlibAdapter:
    def __init__(self):
        from Xlib import X, display
        self.X = X
        self.d = display.Display()
        self.root = self.d.screen().root
        self._atoms = {}

    def atom(self, name):
        if name not in self._atoms:
            self._atoms[name] = self.d.intern_atom(name)
        return self._atoms[name]

    def _prop(self, win, name):
        p = win.get_full_property(self.atom(name), self.X.AnyPropertyType)
        return None if p is None else list(p.value)

    def current_desktop(self):
        v = self._prop(self.root, "_NET_CURRENT_DESKTOP")
        return v[0] if v else None

    def stacking(self):
        """下から上の順(EWMH)。"""
        return self._prop(self.root, "_NET_CLIENT_LIST_STACKING") or []

    def props(self, wid):
        """判断に必要な情報をまとめて返す。ウィンドウが無ければ None。"""
        try:
            win = self.d.create_resource_object("window", wid)
            geo = win.get_geometry()
            pos = self.root.translate_coords(win, 0, 0)
            names = {self.atom(n): n for n in (
                "_NET_WM_STATE_HIDDEN", "_NET_WM_STATE_SKIP_TASKBAR",
                "_NET_WM_WINDOW_TYPE_NORMAL", "_NET_WM_WINDOW_TYPE_DIALOG")}
            state = self._prop(win, "_NET_WM_STATE") or []
            wtype = self._prop(win, "_NET_WM_WINDOW_TYPE") or []
            pid = self._prop(win, "_NET_WM_PID")
            desk = self._prop(win, "_NET_WM_DESKTOP")
            fe = self._prop(win, "_NET_FRAME_EXTENTS") or [0, 0, 0, 0]   # left,right,top,bottom
            return {
                "states": {names[a] for a in state if a in names},
                "types": {names[a] for a in wtype if a in names},
                "pid": pid[0] if pid else None,
                "desktop": desk[0] if desk else None,
                "rect": (pos.x, pos.y, geo.width, geo.height),
                "frame": tuple(fe),
            }
        except Exception:
            return None

    def close(self):
        try:
            self.d.close()
        except Exception:
            pass


class X11Provider(WindowProvider):
    name = "x11"
    native_pixels = True

    def __init__(self, adapter=None, pid=None):
        self._x = adapter
        self._pid = os.getpid() if pid is None else pid

    def open(self):
        if self._x is None:
            try:
                self._x = _XlibAdapter()
            except ImportError:
                self.reason = REASON_NO_XLIB
                return False
            except Exception as e:
                self.reason = f"X11 に接続できませんでした({e})。"
                return False
        return True

    def close(self):
        if self._x is not None and hasattr(self._x, "close"):
            self._x.close()

    def _accept(self, wid, cur_desktop):
        p = self._x.props(wid)
        if p is None:
            return None
        if "_NET_WM_STATE_HIDDEN" in p["states"] or "_NET_WM_STATE_SKIP_TASKBAR" in p["states"]:
            return None                          # 最小化・パネル類
        if p["types"] and not p["types"] & {"_NET_WM_WINDOW_TYPE_NORMAL",
                                            "_NET_WM_WINDOW_TYPE_DIALOG"}:
            return None
        if p["pid"] is not None and p["pid"] == self._pid:
            return None
        if (cur_desktop is not None and p["desktop"] not in (None, ALL_DESKTOPS)
                and p["desktop"] != cur_desktop):
            return None                          # 別のワークスペース
        x, y, w, h = p["rect"]
        left, right, top, bottom = p["frame"]    # 枠(タイトルバー)を含めた見た目の大きさにする
        x, y, w, h = x - left, y - top, w + left + right, h + top + bottom
        if w < MIN_W or h < MIN_H:
            return None
        return WindowInfo(int(wid), x, y, w, h)

    def list_windows(self):
        cur = self._x.current_desktop()
        out = []
        for wid in reversed(self._x.stacking()):         # 上から下の順にする
            try:
                w = self._accept(wid, cur)
            except Exception:
                continue
            if w is not None:
                out.append(w)
        return out

    def get_rect(self, wid):
        try:
            return self._accept(wid, self._x.current_desktop())
        except Exception:
            return None
