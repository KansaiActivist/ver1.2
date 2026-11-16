# -*- coding: utf-8 -*-
"""Qt の画面情報を、足場の計算用の ScreenInfo に変換する。依存: surfaces.geometry のみ。"""
from PySide6.QtGui import QGuiApplication

from mascot.surfaces.geometry import Rect, ScreenInfo


def snapshot_screens():
    out = []
    for s in QGuiApplication.screens():
        g, a = s.geometry(), s.availableGeometry()
        out.append(ScreenInfo(g.x(), g.y(), g.width(), g.height(), float(s.devicePixelRatio()),
                              Rect(a.x(), a.y(), a.width(), a.height())))
    return out
