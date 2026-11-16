# -*- coding: utf-8 -*-
"""
足場の地図。走査結果(生の座標)から、キャラクターが立てる「ウィンドウ上端の区間」を作り、
着地判定・追従・現在位置の問い合わせに答える。Qt にも OS にも依存しない純粋なロジック。依存: surfaces.geometry のみ。

  ・足場は走査(約0.3秒ごと)の時点の位置で作る。追従中のウィンドウだけは、
    最新の矩形(高頻度で更新)との差を足して、いまの位置に補正して答える。
  ・「足元の中心」が動いてよい範囲は、区間の両端から body_w の1/4だけ内側
    (端では体の一部がはみ出して見えるのが自然なため)。
"""
from mascot.surfaces.geometry import Rect, compute_ledges, window_to_logical

EDGE_INSET = 0.25      # 足場の端から、足元中心までの余白(体の幅に対する割合)
SNAP_TOL = 0.5         # 足場の端から体の幅のこれだけ外までは、足場に乗っているとみなす
MIN_LEN = 0.6          # 足場として使う最小の長さ(体の幅に対する割合)


class SurfaceMap:
    def __init__(self):
        self._scan = {}            # wid -> (走査時の Rect, [(x0, x1), ...])
        self._rects = {}           # wid -> 走査時の Rect(足場にならないウィンドウも含む)
        self._order = []
        self._tracked = None       # (wid, Rect | None, ready)
        self.body_w = 100.0

    # ---- 更新 -------------------------------------------------------------
    def rebuild(self, windows, screens, body_w, body_h, native_pixels=True):
        self.body_w = float(body_w)
        rects = [(w.wid, window_to_logical(w, screens, native_pixels)) for w in windows]
        areas = [s.area for s in screens]
        ivs = compute_ledges(rects, areas, body_h, max(40.0, MIN_LEN * body_w)) if areas else {}
        self._scan = {wid: (r, ivs[wid]) for wid, r in rects if wid in ivs}
        self._rects = dict(rects)
        self._order = [wid for wid, _ in rects]

    def forget(self, wid):
        """消えたと分かったウィンドウを、次の走査まで足場から外す(古い足場への再着地を防ぐ)。"""
        self._scan.pop(wid, None)
        self._rects.pop(wid, None)

    def set_tracked(self, wid, rect, ready):
        self._tracked = (wid, rect, ready)

    # ---- 問い合わせ -------------------------------------------------------
    def rect_now(self, wid):
        """いまのウィンドウ位置(論理座標)。無ければ None(= 閉じた・最小化・非表示)。"""
        t = self._tracked
        if t is not None and t[0] == wid and t[2]:
            return t[1]
        return self._rects.get(wid)

    def _shift(self, wid):
        """走査時の位置から、いまの位置までのずれ (dx, dy)。"""
        e = self._scan.get(wid)
        now = self.rect_now(wid)
        if e is None or now is None:
            return None
        return now.x - e[0].x, now.y - e[0].y

    def _foot_range(self, x0, x1):
        inset = EDGE_INSET * self.body_w
        lo, hi = x0 + inset, x1 - inset
        if hi < lo:
            lo = hi = (x0 + x1) / 2
        return lo, hi

    def ledges_now(self):
        """[(wid, 上端のy, 足元中心の下限, 上限)] いまの位置に補正済み。"""
        out = []
        for wid, (r0, ivs) in self._scan.items():
            sh = self._shift(wid)
            if sh is None:
                continue
            dx, dy = sh
            for x0, x1 in ivs:
                lo, hi = self._foot_range(x0 + dx, x1 + dx)
                out.append((wid, r0.y + dy, lo, hi))
        return out

    def landing(self, foot_x, prev_feet, new_feet, grace=0.0):
        """落下中に足元が [prev_feet, new_feet] を通過したとき、最初に着く足場。なければ None。
        grace: 足元が上端より少し下(この距離まで)から始まっても乗せる(ドラッグで離したときの許容)。"""
        best = None
        for wid, y, lo, hi in self.ledges_now():
            if prev_feet - 1.0 - grace <= y <= new_feet and lo <= foot_x <= hi:
                if best is None or y < best[1]:
                    best = (wid, y, lo, hi)
        return best

    def interval(self, wid, foot_x):
        """wid の足場のうち、足元中心 foot_x が乗っている区間の (下限, 上限)。乗っていなければ None。"""
        e = self._scan.get(wid)
        sh = self._shift(wid)
        if e is None or sh is None:
            return None
        tol = SNAP_TOL * self.body_w
        for x0, x1 in e[1]:
            lo, hi = self._foot_range(x0 + sh[0], x1 + sh[0])
            if lo - tol <= foot_x <= hi + tol:
                return lo, hi
        return None
