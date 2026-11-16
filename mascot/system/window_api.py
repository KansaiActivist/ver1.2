# -*- coding: utf-8 -*-
"""
他アプリのウィンドウ位置を調べる「取得口」の契約(型と共通の理由文)。依存: 標準ライブラリのみ。

OSごとの実装は別ファイル(window_win32 / window_x11 / window_macos)に分け、
どれを使うかの選択は window_factory.py が行う(契約と選択を分けて循環を防ぐ)。
使えない環境では NullProvider になり、その理由(reason)を利用者に見せられる
(無理な回避策は使わない)。

取得口の約束:
  ・list_windows(): 画面に見えている通常ウィンドウを、手前から奥の順に返す
                    (最小化・非表示・自分のプロセスのウィンドウ・ツールチップ類は含めない)
  ・get_rect(wid) : 1つのウィンドウの現在位置。閉じた/最小化/非表示なら None
  ・座標はOSの生の座標(Windows/X11 はデバイスピクセル、macOS は論理座標=native_pixels False)
  ・1つのスレッドからだけ呼ぶ(open → list_windows/get_rect → close)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    wid: int
    x: int
    y: int
    w: int
    h: int


class WindowProvider:
    name = "base"
    native_pixels = True      # 座標がデバイスピクセルか(macOS は論理座標なので False)
    reason = ""               # 使えない理由(利用者向けの説明)

    def open(self):
        """使える状態にする。使えなければ False(理由を self.reason に入れる)。"""
        return False

    def list_windows(self):
        return []

    def get_rect(self, wid):
        return None

    def close(self):
        pass


class NullProvider(WindowProvider):
    """ウィンドウ情報を取得できない環境用。画面下端の歩行だけになる。"""
    name = "none"

    def __init__(self, reason):
        self.reason = reason


REASON_WAYLAND = ("Wayland ではOSの仕様により他のアプリのウィンドウ位置を取得できません。"
                  "画面下端のみ歩きます(X11 のセッションなら利用できます)。")
REASON_NO_XLIB = "python-xlib が必要です(pip install python-xlib)。"
REASON_NO_QUARTZ = "pyobjc-framework-Quartz が必要です(pip install pyobjc-framework-Quartz)。"
