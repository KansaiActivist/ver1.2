# -*- coding: utf-8 -*-
"""
別のウィンドウへのジャンプの計画。Qt にも OS にも依存しない純粋な計算。依存: なし。

ジャンプは「初速 (vx, vy) を計算して、既存の落下(重力による放物運動)に入る」だけ。
落下中の着地判定は通常の落下と同じなので、新しい物理は増えない。

  上の足場へ(up > 0): 頂点が足場より margin だけ高くなる初速で跳ぶ
  下・横の足場へ     : 小さく跳ねて、水平の初速で隣へ渡る
"""
import math
import random

HOP_MARGIN = 0.3        # 足場より、頂点をどれだけ高くするか(体の高さに対する割合)
MAX_UP = 1.5            # 跳べる高さの上限(体の高さに対する割合)
MAX_DOWN = 3.0          # 跳び降りてよい深さの上限(体の高さに対する割合)
MAX_REACH = 2.2         # 横に届く距離の上限(体の幅に対する割合)
MAX_VX = 900.0          # 水平の初速の上限(px/s)


def plan_hop(ledges, foot_x, feet_y, body_w, body_h, gravity, top_limit,
             exclude_wid=None, rng=random):
    """
    ledges    : [(wid, 上端のy, 足元中心の下限, 上限)]
    foot_x    : 足元中心のx / feet_y: 足元のy
    top_limit : 体の上端がこれより上に出てはいけない y(画面上端)
    戻り値    : {"vx", "vy", "wid", "tx"}  または None
    """
    cands = []
    for wid, y, lo, hi in ledges:
        if wid == exclude_wid:
            continue
        up = feet_y - y                                   # 正: 足場の方が高い
        if up > MAX_UP * body_h or up < -MAX_DOWN * body_h:
            continue
        m = min(0.2 * (hi - lo), 0.15 * body_w)           # 端ぎりぎりを狙わない
        tx = min(max(foot_x, lo + m), hi - m)
        dx = tx - foot_x
        if abs(dx) > MAX_REACH * body_w:
            continue
        if up <= 0 and abs(dx) < 0.3 * body_w:
            continue                                      # ほぼ真下の足場は、跳ばずに飛び降りれば済む
        rise = up + HOP_MARGIN * body_h if up > 0 else 0.3 * body_h
        vy0 = -math.sqrt(2 * gravity * rise)
        disc = vy0 * vy0 + 2 * gravity * (y - feet_y)
        if disc < 0:
            continue
        t = (-vy0 + math.sqrt(disc)) / gravity            # 足場の高さまで降りてくる時刻
        if t <= 0:
            continue
        vx = dx / t
        if abs(vx) > MAX_VX:
            continue
        apex_top = feet_y - vy0 * vy0 / (2 * gravity) - body_h
        if apex_top < top_limit:
            continue                                      # 頭が画面の上に出てしまう
        cands.append(({"vx": vx, "vy": vy0, "wid": wid, "tx": tx}, 1.0 / (1.0 + abs(dx))))
    if not cands:
        return None
    total = sum(w for _, w in cands)
    r = rng.random() * total
    for c, w in cands:
        r -= w
        if r <= 0:
            return c
    return cands[-1][0]
