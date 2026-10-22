"""Zusammenhängende Flächen in Masken ohne scipy (der Pi hat kein scipy): Erosion, Markierung, Kästen, 3x3-Weichzeichner.

`label(mask)` arbeitet wie `scipy.ndimage.label` (4er-Nachbarschaft) über Zeilenläufe mit Union-Find; schnell, solange die
Maske aus wenigen Flächen besteht (vorher `erode()` nimmt Einzelpixel und dünne Brücken weg)."""
from __future__ import annotations

import numpy as np


def erode(mask: np.ndarray, k: int) -> np.ndarray:
    """Binäre Erosion mit einem k x k Quadrat (wie `ndimage.binary_erosion(mask, np.ones((k, k)))`, Rand = False)."""
    h, w = mask.shape
    if k <= 1:
        return mask.copy()
    if h < k or w < k:
        return np.zeros_like(mask, dtype=bool)
    s = np.zeros((h + 1, w + 1), dtype=np.int32)
    s[1:, 1:] = mask.astype(np.int32).cumsum(0).cumsum(1)
    win = s[k:, k:] - s[:-k, k:] - s[k:, :-k] + s[:-k, :-k]                    # Summe je k x k Fenster
    out = np.zeros_like(mask, dtype=bool)
    o = k // 2
    out[o:o + h - k + 1, o:o + w - k + 1] = win == k * k
    return out


def blur3(a: np.ndarray) -> np.ndarray:
    """3x3-Mittelwert (wie `ndimage.uniform_filter(a, 3)`), Rand gespiegelt."""
    p = np.pad(a.astype(np.float32), 1, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            out += p[dy:dy + a.shape[0], dx:dx + a.shape[1]]
    return out / 9.0


def label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """(Markierungen int32 0 = Hintergrund, 1..n, Anzahl n) für die 4er-zusammenhängenden True-Flächen."""
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    parent = [0]
    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    prev: list[tuple[int, int, int]] = []
    m = mask.astype(np.uint8)
    for y in range(h):
        row = m[y]
        if not row.any():
            prev = []
            continue
        d = np.diff(np.concatenate(([0], row, [0])).astype(np.int8))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        runs: list[tuple[int, int, int]] = []
        for x0, x1 in zip(starts.tolist(), ends.tolist()):
            rid = -1
            for px0, px1, pid in prev:
                if px0 < x1 and px1 > x0:
                    r = find(pid)
                    if rid < 0:
                        rid = r
                    elif r != rid:
                        parent[r] = rid
            if rid < 0:
                rid = len(parent)
                parent.append(rid)
            runs.append((x0, x1, rid))
            lab[y, x0:x1] = rid
        prev = runs
    roots = np.array([find(i) for i in range(len(parent))], dtype=np.int32)
    uniq = np.unique(roots[1:]) if len(parent) > 1 else np.zeros(0, dtype=np.int32)
    lut = np.zeros(len(parent), dtype=np.int32)
    lut[uniq] = np.arange(1, len(uniq) + 1, dtype=np.int32)
    return lut[roots][lab], int(len(uniq))


def sizes(lab: np.ndarray, n: int) -> np.ndarray:
    """Pixelzahl je Markierung 1..n (Index 0 = Markierung 1)."""
    return np.bincount(lab.ravel(), minlength=n + 1)[1:].astype(np.int64)


def boxes(lab: np.ndarray, n: int) -> list[tuple[int, int, int, int] | None]:
    """Je Markierung 1..n (y0, y1, x0, x1) mit exklusivem Ende, wie `ndimage.find_objects`."""
    out: list[tuple[int, int, int, int] | None] = [None] * n
    ys, xs = np.nonzero(lab)
    if len(ys) == 0:
        return out
    ids = lab[ys, xs]
    order = np.argsort(ids, kind="stable")
    ids, ys, xs = ids[order], ys[order], xs[order]
    first = np.flatnonzero(np.diff(np.concatenate(([0], ids))))                # Beginn jeder Markierung
    y0, y1 = np.minimum.reduceat(ys, first), np.maximum.reduceat(ys, first)
    x0, x1 = np.minimum.reduceat(xs, first), np.maximum.reduceat(xs, first)
    for k, i in enumerate(ids[first].tolist()):
        out[i - 1] = (int(y0[k]), int(y1[k]) + 1, int(x0[k]), int(x1[k]) + 1)
    return out
