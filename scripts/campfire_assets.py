#!/usr/bin/env python3
"""Bildmaterial für das Lagerfeuer vorbereiten.

    .venv/bin/python scripts/campfire_assets.py SZENE.png FLAMMEN_COLLAGE.png [--sheet-top Y]
Schreibt assets/campfire/scene.png (die Szene, unverändert bzw. auf max. 1920 Breite verkleinert)
und assets/campfire/flames.png (das Flammen-Spritesheet, 8 x 5 Einzelbilder, Hintergrund schwarz).
Die Collage darf oben weitere Bilder enthalten: --sheet-top gibt die Zeile an, ab der das Sheet
beginnt (Standard: automatisch, erste lange schwarze Zeilenfolge). Gitterlinien zwischen den
Einzelbildern werden erkannt und entfernt (Zellen gleichmäßig, Ränder schwarz).
"""
from __future__ import annotations

import sys

import numpy as np
import pygame

OUT_DIR = "assets/campfire"
COLS, ROWS = 8, 5


def load(path: str) -> np.ndarray:
    s = pygame.image.load(path)
    return pygame.surfarray.array3d(s).transpose(1, 0, 2).copy()


def save(path: str, arr: np.ndarray) -> None:
    surf = pygame.image.frombuffer(np.ascontiguousarray(arr).astype(np.uint8).tobytes(), (arr.shape[1], arr.shape[0]), "RGB")
    pygame.image.save(surf, path)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    scene = load(sys.argv[1])
    if scene.shape[1] > 1920:
        surf = pygame.image.load(sys.argv[1])
        h = int(scene.shape[0] * 1920 / scene.shape[1])
        scene = pygame.surfarray.array3d(pygame.transform.smoothscale(surf, (1920, h))).transpose(1, 0, 2).copy()
    save(f"{OUT_DIR}/scene.png", scene)
    print("Szene:", scene.shape[1], "x", scene.shape[0])

    col = load(sys.argv[2]).astype(int)
    H, W = col.shape[:2]
    top = None
    if "--sheet-top" in sys.argv:
        top = int(sys.argv[sys.argv.index("--sheet-top") + 1])
    else:
        rowmean = col.mean(axis=(1, 2))
        run = 0
        for y in range(H):
            run = run + 1 if rowmean[y] < 12 else 0
            if run >= 40:
                top = y - run + 1
                break
    if top is None:
        print("Sheet-Anfang nicht gefunden, --sheet-top angeben")
        return 1
    sheet = col[top:]
    sh, sw = sheet.shape[:2]
    # Gitterlinien: gleichmäßig graue Zeilen/Spalten (geringe Streuung, nicht schwarz) ausblenden
    rs = sheet.std(axis=(1, 2)); rm = sheet.mean(axis=(1, 2))
    cs = sheet.std(axis=(0, 2)); cm = sheet.mean(axis=(0, 2))
    grid_rows = (rs < 6) & (rm > 18)
    grid_cols = (cs < 6) & (cm > 18)
    sheet = sheet.copy()
    sheet[grid_rows] = 0
    sheet[:, grid_cols] = 0
    # auf ganze Zellen schneiden
    cw, ch = sw // COLS, sh // ROWS
    sheet = sheet[:ch * ROWS, :cw * COLS]
    # Zellenränder sauber schwarz (2 px), Bild schwarz halten, wo fast schwarz
    for r in range(ROWS):
        sheet[r * ch:r * ch + 2] = 0
        sheet[(r + 1) * ch - 2:(r + 1) * ch] = 0
    for c in range(COLS):
        sheet[:, c * cw:c * cw + 2] = 0
        sheet[:, (c + 1) * cw - 2:(c + 1) * cw] = 0
    # Schwarzwert: schwaches Grau (Gitterreste, Kompression) auf Schwarz ziehen, Flammen bleiben
    lum = sheet.max(axis=2)
    gate = np.clip((lum - 28) / 40.0, 0.0, 1.0)[..., None]
    sheet = (sheet * gate).astype(int)
    save(f"{OUT_DIR}/flames.png", sheet)
    print(f"Flammen: {COLS}x{ROWS} Zellen à {cw}x{ch} (Sheet ab Zeile {top}), Gitter entfernt: {int(grid_rows.sum())} Zeilen, {int(grid_cols.sum())} Spalten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
