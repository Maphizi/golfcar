#!/usr/bin/env python3
"""Mission-Logo und schwebende Figuren für den Taxistand vorbereiten.

    .venv/bin/python scripts/taxi_sprites.py LOGO.png FIGURENBOGEN.png [--out assets/taxi/space] [--max 24] [--side 130] [--split 8]
Schreibt <out>/mission.png (Logo, auf 1024 Breite) und <out>/sprites.png (Atlas 8 x 3
Zellen à 96 px, RGBA). Logo und Bogen dürfen einen Alphakanal haben, einen schwarzen Hintergrund (Logo) oder ein eingebranntes
Transparenz-Schachbrett (wird herausgerechnet); aus dem Bogen werden die
Zusammenhangskomponenten genommen, die kleinen (längste Seite <= --side Pixel) bevorzugt, bis --max
Stück, von unten nach oben. --split N trennt sich berührende Objekte (Erosion um N Pixel). Braucht numpy, pygame, scipy (nur zum Erzeugen).
"""
from __future__ import annotations

import sys

import numpy as np
import pygame
from scipy import ndimage

OUT = "assets/taxi/space"
COLS, ROWS, CELL = 8, 3, 96


def derive_alpha(surf, connected: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """(rgb HxWx3, alpha HxW 0..255). Nimmt den Alphakanal, wenn er Transparenz hat; sonst: schwarzer
    Hintergrund -> Alpha aus der Helligkeit; eingebranntes Transparenz-Schachbrett (weiß/hellgrau,
    neutral) -> alles Neutrale und Helle, das mit dem Rand zusammenhängt, wird Hintergrund."""
    rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2).copy()
    try:
        alpha = pygame.surfarray.array_alpha(surf).transpose(1, 0).copy()
    except ValueError:
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    if alpha.min() < 128:
        return rgb, alpha
    a = rgb.astype(int)
    corner = np.concatenate([a[:8, :8].reshape(-1, 3), a[-8:, -8:].reshape(-1, 3)]).mean(axis=0)
    if corner.max() < 30:                                              # schwarzer Hintergrund (Logo)
        lum = a.max(axis=2)
        al = np.clip((lum - 12) / 50.0, 0.0, 1.0)
        return rgb, (al * 255).astype(np.uint8)
    neutral = (np.abs(a[:, :, 0] - a[:, :, 1]) < 12) & (np.abs(a[:, :, 1] - a[:, :, 2]) < 12) & (np.abs(a[:, :, 0] - a[:, :, 2]) < 12)
    bright = a.min(axis=2) > 192
    cand = neutral & bright
    if connected:                                                      # nur Hintergrund, der den Rand berührt
        lab, n = ndimage.label(cand)
        border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
        border.discard(0)
        bg = np.isin(lab, list(border))
    else:                                                              # Logo: Schachbrett auch in Lücken
        bg = cand
    bg = ndimage.binary_closing(bg, iterations=1)                        # Lücken im Schachbrett schließen
    fg = ~bg
    fg = ndimage.binary_opening(fg, iterations=1)
    fg = ndimage.binary_erosion(fg, iterations=1)                        # hellen Saum abschneiden
    al = ndimage.gaussian_filter(fg.astype(np.float32), 0.8)
    return rgb, (np.clip(al, 0.0, 1.0) * 255).astype(np.uint8)


def save_rgba(path: str, rgb: np.ndarray, alpha: np.ndarray, width: int | None = None) -> tuple[int, int]:
    img = np.dstack([rgb, alpha]).astype(np.uint8)
    surf = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (img.shape[1], img.shape[0]), "RGBA")
    if width and surf.get_width() != width:
        surf = pygame.transform.smoothscale(surf, (width, int(surf.get_height() * width / surf.get_width())))
    pygame.image.save(surf, path)
    return surf.get_size()


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    global OUT
    if "--out" in sys.argv:
        OUT = sys.argv[sys.argv.index("--out") + 1]
    max_n = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else COLS * ROWS
    side = int(sys.argv[sys.argv.index("--side") + 1]) if "--side" in sys.argv else 130
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    lrgb, lal = derive_alpha(pygame.image.load(sys.argv[1]).convert_alpha(), connected=False)
    print("Logo:", save_rgba(f"{OUT}/mission.png", lrgb, lal, 1024))

    rgb, alpha = derive_alpha(pygame.image.load(sys.argv[2]).convert_alpha())
    fg = alpha > 40
    fg = ndimage.binary_closing(fg, iterations=2)
    split = int(sys.argv[sys.argv.index("--split") + 1]) if "--split" in sys.argv else 0
    if split > 0:
        # Objekte, die sich berühren, trennen: Maske erodieren, Kerne beschriften, Pixel dem nächsten Kern zuordnen
        core = ndimage.binary_erosion(fg, iterations=split)
        lab, n = ndimage.label(core)
        _, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
        lab = np.where(fg, lab[iy, ix], 0)
    else:
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
