# -*- coding: utf-8 -*-
"""このOSで使えるウィンドウ取得口を選ぶ。依存: system 内(契約と各OSの実装)のみ。"""
import os
import sys

from mascot.system.window_api import REASON_WAYLAND, NullProvider


def create_provider(platform=None, env=None):
    """このOSで使える取得口を返す。platform / env はテスト用に差し替え可能。"""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    if platform == "win32":
        from mascot.system.window_win32 import Win32Provider
        return Win32Provider()
    if platform == "darwin":
        from mascot.system.window_macos import MacProvider
        return MacProvider()
    if platform.startswith("linux"):
        if env.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return NullProvider(REASON_WAYLAND)
        if not env.get("DISPLAY"):
            return NullProvider("X11 の DISPLAY が見つからないため、他のウィンドウの上は歩けません。")
        from mascot.system.window_x11 import X11Provider
        return X11Provider()
    return NullProvider("このOSでは、他のウィンドウの上を歩く機能は未対応です。")
