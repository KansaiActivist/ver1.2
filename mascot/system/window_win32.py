# -*- coding: utf-8 -*-
"""
Windows 用のウィンドウ取得口(追加ライブラリ不要。ctypes で user32 / dwmapi を呼ぶ)。
依存: system.window_api のみ。

  _Win32Api      … ctypes の薄いラッパー(判断を持たない)
  Win32Provider  … どのウィンドウを足場にするかの判断(api を差し替えてテストできる)

ウィンドウの見た目の枠は DWMWA_EXTENDED_FRAME_BOUNDS で取る
(GetWindowRect は Windows 10/11 で左右下に見えない余白を含むため、足場が浮いて見える)。
"""
import os
import sys

from mascot.system.window_api import WindowInfo, WindowProvider

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
GWL_EXSTYLE = -20
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

# デスクトップ・タスクバー・スタートメニュー等(足場にしない)
SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "ApplicationFrameInputSinkWindow",
    "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland",
}
MIN_W, MIN_H = 60, 30


class _Win32Api:
    """ctypes の薄いラッパー。ここには判断を書かない(判断は Win32Provider)。"""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct, self.wt = ctypes, wintypes
        u, d = ctypes.windll.user32, ctypes.windll.dwmapi
        self.u, self.d = u, d
        H = wintypes.HWND
        self._proc_t = ctypes.WINFUNCTYPE(wintypes.BOOL, H, wintypes.LPARAM)
        u.EnumWindows.argtypes = [self._proc_t, wintypes.LPARAM]
        u.EnumWindows.restype = wintypes.BOOL
        for fn in (u.IsWindowVisible, u.IsIconic, u.IsWindow):
            fn.argtypes = [H]
            fn.restype = wintypes.BOOL
        u.GetWindowTextLengthW.argtypes = [H]
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetClassNameW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int
        u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.GetWindowLongW.argtypes = [H, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowRect.restype = wintypes.BOOL
        d.DwmGetWindowAttribute.argtypes = [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        d.DwmGetWindowAttribute.restype = ctypes.c_long

    def enum_windows(self):
        """トップレベルウィンドウを手前(Zオーダー上位)から順に返す。"""
        found = []

        def cb(hwnd, _):
            found.append(int(hwnd) if hwnd else 0)
            return True
        proc = self._proc_t(cb)          # 呼び出し中は参照を保持する
        self.u.EnumWindows(proc, 0)
        return [h for h in found if h]

    def is_window(self, h):
        return bool(self.u.IsWindow(h))

    def is_visible(self, h):
        return bool(self.u.IsWindowVisible(h))

    def is_iconic(self, h):
        return bool(self.u.IsIconic(h))

    def exstyle(self, h):
        return int(self.u.GetWindowLongW(h, GWL_EXSTYLE)) & 0xFFFFFFFF

    def class_name(self, h):
        buf = self.ct.create_unicode_buffer(256)
        self.u.GetClassNameW(h, buf, 256)
        return buf.value

    def title_len(self, h):
        return int(self.u.GetWindowTextLengthW(h))

    def pid(self, h):
        p = self.wt.DWORD(0)
        self.u.GetWindowThreadProcessId(h, self.ct.byref(p))
        return int(p.value)

    def cloaked(self, h):
        v = self.wt.DWORD(0)
        hr = self.d.DwmGetWindowAttribute(h, DWMWA_CLOAKED, self.ct.byref(v), 4)
        return hr == 0 and v.value != 0

    def frame_rect(self, h):
        """見た目の枠 (left, top, right, bottom)。取れなければ GetWindowRect。"""
        r = self.wt.RECT()
        hr = self.d.DwmGetWindowAttribute(h, DWMWA_EXTENDED_FRAME_BOUNDS, self.ct.byref(r),
                                          self.ct.sizeof(r))
        if hr != 0 and not self.u.GetWindowRect(h, self.ct.byref(r)):
            return None
        return r.left, r.top, r.right, r.bottom


class Win32Provider(WindowProvider):
    name = "win32"
    native_pixels = True

    def __init__(self, api=None, pid=None):
        self._api = api
        self._pid = os.getpid() if pid is None else pid

    def open(self):
        if self._api is None:
            if sys.platform != "win32":
                self.reason = "Windows 以外では使えません。"
                return False
            try:
                self._api = _Win32Api()
            except Exception as e:
                self.reason = f"Windows のウィンドウ API を初期化できませんでした({e})。"
                return False
        return True

    def _rect(self, h):
        fr = self._api.frame_rect(h)
        if not fr:
            return None
        l, t, r, b = fr
        if r - l < MIN_W or b - t < MIN_H:
            return None
        return WindowInfo(int(h), l, t, r - l, b - t)

    def _alive(self, h):
        a = self._api
        return a.is_window(h) and a.is_visible(h) and not a.is_iconic(h) and not a.cloaked(h)

    def _accept(self, h):
        a = self._api
        if not self._alive(h):
            return None                          # 非表示・最小化・別の仮想デスクトップ
        ex = a.exstyle(h)
        if ex & WS_EX_TOOLWINDOW and not ex & WS_EX_APPWINDOW:
            return None                          # ツールウィンドウ(フローティングパレット等)
        if ex & WS_EX_NOACTIVATE:
            return None                          # フォーカスを取らないオーバーレイ類
        if ex & WS_EX_LAYERED and ex & WS_EX_TRANSPARENT:
            return None                          # クリックが素通りする透過ウィンドウ
        if a.pid(h) == self._pid:
            return None                          # 自分自身(マスコット・設定・読み込み画面)
        if a.class_name(h) in SKIP_CLASSES or a.title_len(h) == 0:
            return None
        return self._rect(h)

    def list_windows(self):
        out = []
        for h in self._api.enum_windows():
            try:
                w = self._accept(h)
            except Exception:
                continue                         # 1つのウィンドウで失敗しても全体は続ける
            if w is not None:
                out.append(w)
        return out

    def get_rect(self, wid):
        try:
            if not self._alive(wid):
                return None
            return self._rect(wid)
        except Exception:
            return None
