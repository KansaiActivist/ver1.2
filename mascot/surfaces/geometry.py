# -*- coding: utf-8 -*-
"""
足場の計算に使う幾何(長方形・画面情報・区間演算)。Qt にも OS にも依存しない純粋なロジック。

座標系: 「論理座標」= Qt のグローバル座標(キャラクターのウィンドウを動かすのと同じ座標)。
OSが返す生の座標(デバイスピクセル)から論理座標への変換は native_to_logical() で行う。
  論理座標 = 画面の左上(生) + (生の座標 - 画面の左上(生)) / 画面の拡大率
(Qt は画面の左上位置を生の座標のまま持ち、画面内の距離だけを拡大率で割るため)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h


@dataclass(frozen=True)
class ScreenInfo:
    nx: float        # 画面の左上(生の座標)
    ny: float
    lw: float        # 画面の大きさ(論理)
    lh: float
    dpr: float       # 拡大率
    area: Rect       # タスクバー等を除いた使える範囲(論理座標)


def _screen_for_native(nx, ny, screens):
    best, best_d = None, None
    for s in screens:
        x1, y1 = s.nx + s.lw * s.dpr, s.ny + s.lh * s.dpr
        if s.nx <= nx < x1 and s.ny <= ny < y1:
            return s
        dx = max(s.nx - nx, 0, nx - x1)
        dy = max(s.ny - ny, 0, ny - y1)
        d = dx * dx + dy * dy
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best


def native_to_logical(nx, ny, screens):
    s = _screen_for_native(nx, ny, screens) if screens else None
    if s is None:
        return float(nx), float(ny)
    return s.nx + (nx - s.nx) / s.dpr, s.ny + (ny - s.ny) / s.dpr


def window_to_logical(win, screens, native_pixels=True):
    """WindowInfo(生の座標) → Rect(論理座標)。"""
    if not native_pixels or not screens:
        return Rect(win.x, win.y, win.w, win.h)
    x0, y0 = native_to_logical(win.x, win.y, screens)
    x1, y1 = native_to_logical(win.x + win.w, win.y + win.h, screens)
    return Rect(x0, y0, x1 - x0, y1 - y0)


# ---- 区間(x 方向の線分)の演算 ------------------------------------------
def subtract_interval(segs, cut):
    """区間のリストから cut=(a, b) の部分を取り除く。"""
    a, b = cut
    out = []
    for s0, s1 in segs:
        if b <= s0 or a >= s1:
            out.append((s0, s1))
            continue
        if a > s0:
            out.append((s0, a))
        if b < s1:
            out.append((b, s1))
    return out


def merge_intervals(segs, gap=0.5):
    out = []
    for s0, s1 in sorted(segs):
        if out and s0 <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], s1))
        else:
            out.append((s0, s1))
    return out


def compute_ledges(rects, areas, body_h, min_len):
    """
    ウィンドウの上端のうち「キャラクターが立てる部分」を求める。

    rects : [(wid, Rect)] 手前のウィンドウが先(論理座標)
    areas : 画面ごとの使える範囲 [Rect]
    戻り値: {wid: [(x0, x1), ...]}  上端の高さは Rect.y

    立てない部分:
      ・手前の別ウィンドウの内側に隠れている部分(足元が他のウィンドウの中になる)
      ・キャラクターの全身が画面内に収まらない高さ(最大化ウィンドウ等で上端が画面上端に近い)
      ・使える範囲(タスクバー等を除く)より下
      ・短すぎる部分
    """
    out = {}
    for i, (wid, r) in enumerate(rects):
        y = r.y
        segs = [(r.x, r.right)]
        for _, h in rects[:i]:
            if h.y < y - 1 and y < h.bottom:
                segs = subtract_interval(segs, (h.x, h.right))
        clipped = []
        for a in areas:
            if a.y + body_h <= y <= a.bottom - 1:
                for s0, s1 in segs:
                    lo, hi = max(s0, a.x), min(s1, a.right)
                    if hi > lo:
                        clipped.append((lo, hi))
        merged = [s for s in merge_intervals(clipped) if s[1] - s[0] >= min_len]
        if merged:
            out[wid] = merged
    return out
