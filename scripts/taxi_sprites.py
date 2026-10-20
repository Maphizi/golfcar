#!/usr/bin/env python3
"""Mission-Logo und schwebende Figuren für den Taxistand vorbereiten.

    .venv/bin/python scripts/taxi_sprites.py LOGO.png FIGURENBOGEN.png [--max 24] [--side 130]
Schreibt assets/taxi/mission.png (Logo, auf 1024 Breite) und assets/taxi/sprites.png (Atlas 8 x 3
Zellen à 96 px, RGBA). Der Figurenbogen braucht einen Alphakanal (freigestellt); daraus werden die
Zusammenhangskomponenten genommen, die kleinen (längste Seite <= --side Pixel) bevorzugt, bis --max
Stück, von unten nach oben. Braucht numpy, pygame, scipy (nur zum Erzeugen).
"""
from __future__ import annotations

import sys

import numpy as np
import pygame
from scipy import ndimage

OUT = "assets/taxi"
COLS, ROWS, CELL = 8, 3, 96


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    max_n = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else COLS * ROWS
    side = int(sys.argv[sys.argv.index("--side") + 1]) if "--side" in sys.argv else 130
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    logo = pygame.image.load(sys.argv[1])
    w, h = logo.get_size()
    logo = pygame.transform.smoothscale(logo, (1024, int(h * 1024 / w)))
    pygame.image.save(logo, f"{OUT}/mission.png")
    print("Logo:", logo.get_size())

    sheet = pygame.image.load(sys.argv[2]).convert_alpha()
    rgb = pygame.surfarray.array3d(sheet).transpose(1, 0, 2)
    alpha = pygame.surfarray.array_alpha(sheet).transpose(1, 0)
    fg = alpha > 40
    fg = ndimage.binary_closing(fg, iterations=2)
    lab, n = ndimage.label(fg)
    objs = ndimage.find_objects(lab)
    items = []
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        ys, xs = sl
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        if max(hh, ww) < 30:
            continue
        items.append((max(hh, ww), ys.start, i + 1, sl))
    small = [it for it in items if it[0] <= side]
    small.sort(key=lambda it: (-it[1], it[0]))                      # unten zuerst
    chosen = small[:max_n]
    if len(chosen) < max_n:                                           # mit den nächstgrößeren auffüllen
        rest = sorted([it for it in items if it[0] > side], key=lambda it: it[0])
        chosen += rest[:max_n - len(chosen)]
    atlas = np.zeros((ROWS * CELL, COLS * CELL, 4), dtype=np.uint8)
    for k, (_, _, idx, sl) in enumerate(chosen[:COLS * ROWS]):
        ys, xs = sl
        mask = (lab[sl] == idx)
        crop = np.dstack([rgb[sl], (alpha[sl] * mask).astype(np.uint8)])
        surf = pygame.image.frombuffer(np.ascontiguousarray(crop).tobytes(), (crop.shape[1], crop.shape[0]), "RGBA")
        sc = (CELL - 6) / max(crop.shape[0], crop.shape[1])
        surf = pygame.transform.smoothscale(surf, (max(1, int(crop.shape[1] * sc)), max(1, int(crop.shape[0] * sc))))
        arr = pygame.surfarray.pixels3d(surf).transpose(1, 0, 2).copy()
        al = pygame.surfarray.pixels_alpha(surf).transpose(1, 0).copy()
        r, c = divmod(k, COLS)
        oy, ox = r * CELL + (CELL - arr.shape[0]) // 2, c * CELL + (CELL - arr.shape[1]) // 2
        atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], :3] = arr
        atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], 3] = al
    out = pygame.image.frombuffer(atlas.tobytes(), (COLS * CELL, ROWS * CELL), "RGBA")
    pygame.image.save(out, f"{OUT}/sprites.png")
    print(f"Figuren: {len(chosen[:COLS * ROWS])} von {len(items)} Komponenten in {COLS}x{ROWS} Zellen à {CELL} px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
