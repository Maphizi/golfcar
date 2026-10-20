#!/usr/bin/env python3
"""Figuren für HAL 3000 freistellen: aus einem Bild mit zwei Figuren vor weißem Hintergrund (links
Astronaut, rechts Alien) einen Sprite-Atlas 1024x512 RGBA bauen (zwei Zellen 512x512, Figur mittig
eingepasst). Hat die Quelle einen Alphakanal, wird er direkt genommen; sonst gilt alles Nahezu-Weiße, das mit dem
Bildrand zusammenhängt, als Hintergrund (weiße Teile des Raumanzugs bleiben erhalten). Zuordnung der Teile zu den Figuren über die Bildhälfte ihres Schwerpunkts.

    .venv/bin/python scripts/hal_figures.py QUELLE.png assets/hal/figures.png [VORSCHAU.png]
Braucht numpy, pygame und scipy (nur zum Erzeugen; zur Laufzeit wird nur das PNG geladen).
"""
from __future__ import annotations

import sys

import numpy as np
import pygame
from scipy import ndimage

CELL = 512


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    src = pygame.image.load(sys.argv[1]).convert_alpha()
    w, h = src.get_size()
    rgb = pygame.surfarray.array3d(src).transpose(1, 0, 2).astype(np.float32)
    src_alpha = pygame.surfarray.array_alpha(src).transpose(1, 0).astype(np.float32) / 255.0
    has_alpha = src_alpha.min() < 0.5
    if has_alpha:
        # Quelle ist schon freigestellt (Alphakanal): direkt übernehmen
        fg = src_alpha > 0.5
    else:
        # nahezu weiß = Hintergrundkandidat; davon nur die Flächen, die den Rand berühren
        white = rgb.min(axis=2) > 232.0
        lab, n = ndimage.label(white)
        border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
        border.discard(0)
        fg = ~np.isin(lab, list(border))
        fg = ndimage.binary_opening(fg, iterations=1)
    # Figuren über Zusammenhangskomponenten; kleine Splitter nach Schwerpunkt zuordnen
    flab, fn = ndimage.label(fg)
    sizes = ndimage.sum(fg, flab, range(1, fn + 1))
    cents = ndimage.center_of_mass(fg, flab, range(1, fn + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s > 150]
    left = np.isin(flab, [i for i in keep if cents[i - 1][1] < w / 2])
    right = np.isin(flab, [i for i in keep if cents[i - 1][1] >= w / 2])
    # weiche Kante: Maske leicht glätten
    alpha_all = src_alpha if has_alpha else ndimage.gaussian_filter(fg.astype(np.float32), 1.0)
    atlas = np.zeros((CELL, 2 * CELL, 4), dtype=np.uint8)
    for k, mask in enumerate((left, right)):
        ys, xs = np.nonzero(mask)
        if len(ys) == 0:
            print("Figur", k, "nicht gefunden")
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = rgb[y0:y1, x0:x1]
        a = (alpha_all[y0:y1, x0:x1] * mask[y0:y1, x0:x1]).clip(0.0, 1.0)
        a3 = a[..., None]
        if has_alpha:
            col = crop
        else:   # Rand entfärben: Weißsaum vom Hintergrund wegnehmen (Un-Premultiply gegen Weiß)
            col = np.where(a3 > 0.05, (crop - 255.0 * (1.0 - a3)) / np.maximum(a3, 0.05), crop).clip(0, 255)
        img = np.dstack([col, a * 255.0]).astype(np.uint8)
        surf = pygame.image.frombuffer(img.tobytes(), (x1 - x0, y1 - y0), "RGBA")
        cw, ch = x1 - x0, y1 - y0
        scale = min((CELL - 24) / cw, (CELL - 24) / ch)
        surf = pygame.transform.smoothscale(surf, (int(cw * scale), int(ch * scale)))
        arr = pygame.surfarray.pixels3d(surf).transpose(1, 0, 2).copy()
        al = pygame.surfarray.pixels_alpha(surf).transpose(1, 0).copy()
        ox = k * CELL + (CELL - arr.shape[1]) // 2
        oy = (CELL - arr.shape[0]) // 2
        atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], :3] = arr
        atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], 3] = al
        print("Figur", k, "Quelle", (x0, y0, x1, y1), "->", arr.shape[1], "x", arr.shape[0])
    out = pygame.image.frombuffer(atlas.tobytes(), (2 * CELL, CELL), "RGBA")
    pygame.image.save(out, sys.argv[2])
    if len(sys.argv) > 3:
        prev = pygame.Surface((2 * CELL, CELL))
        prev.fill((20, 60, 120))
        prev.blit(out, (0, 0))
        pygame.image.save(prev, sys.argv[3])
    print("geschrieben:", sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
