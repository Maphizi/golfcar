#!/usr/bin/env python3
"""Bildmaterial für den neuen Uhrturm (Taste 4 im Thema ZURÜCK IN DIE ZUKUNFT) aus assets/future/raw/clocktower_*.png
(Prompts docs/future_plan.md, Runde 3) schneiden. Braucht numpy, pygame, scipy (nur zum Erzeugen, nicht auf dem Pi).

    .venv/bin/python scripts/clocktower_assets.py

Ergebnis unter assets/future/:
  clocktower_tower.png     Szene (1920 breit)
  clocktower_winmask.png   Fensterkarte gleicher Größe: R = Fenster-Nr. x 16 (0 = Fassade), G = weiche Scheibe,
                           B = Nr. des nächsten Fensters x 16 im Umkreis (Lichtschein), A = Lichtschein (weich)
  clocktower_layout.json   Fenster (x0, y0, x1, y1, Mitte, Fläche; y von unten) und Zifferblatt (x, y, Radius)
  clocktower_sil.png       Silhouetten 8x3 à 128x192: weiß, Alpha = Schatten
  clocktower_climber.png   Professor 8x2 à 160x360 (Reihe 0 Kletterzyklus, Reihe 1 Posen), Alpha freigestellt
  clocktower_hands.png     Zeiger 3x1 à 128x512, Drehpunkt genau in der Zellmitte, gleicher Maßstab
  clocktower_clockwork.png Uhrwerk 512x512, außerhalb des Kreises durchsichtig
  clocktower_car.png       Zeitmaschine 3x1 à 512x200 (Licht an, Blitzbögen, glühend), Räder auf der Unterkante,
                           vormultipliziert: Shader rechnet col * (1 - a) + rgb
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pygame
from scipy import ndimage

RAW = "assets/future/raw"
OUT = "assets/future"
MAX_WIN = 15


def load(name: str) -> np.ndarray:
    return pygame.surfarray.array3d(pygame.image.load(f"{RAW}/{name}.png")).transpose(1, 0, 2).copy()


def save(arr: np.ndarray, path: str) -> None:
    arr = np.ascontiguousarray(arr.astype(np.uint8))
    h, w = arr.shape[:2]
    mode = "RGBA" if arr.shape[2] == 4 else "RGB"
    pygame.image.save(pygame.image.frombuffer(arr.tobytes(), (w, h), mode), path)
    print("  ", path, f"{w}x{h}")


def scale(arr: np.ndarray, w: int, h: int) -> np.ndarray:
    mode = "RGBA" if arr.shape[2] == 4 else "RGB"
    s = pygame.image.frombuffer(np.ascontiguousarray(arr.astype(np.uint8)).tobytes(), (arr.shape[1], arr.shape[0]), mode)
    s = pygame.transform.smoothscale(s, (w, h))
    rgb = pygame.surfarray.array3d(s).transpose(1, 0, 2)
    if mode == "RGBA":
        return np.dstack([rgb, pygame.surfarray.array_alpha(s).transpose(1, 0)])
    return rgb


def tower() -> None:
    img = load("clocktower_tower")
    H0, W0 = img.shape[:2]
    W, H = 1920, int(round(H0 * 1920 / W0))
    img = scale(img, W, H)
    save(img, f"{OUT}/clocktower_tower.png")
    lum = img.max(axis=2).astype(int)
    # Fenster: fast reinschwarze Flächen, dünne Verbindungen getrennt, nur fensterartige Größen und Formen
    black = lum < 9
    core = ndimage.binary_erosion(black, iterations=3)
    lab, n = ndimage.label(core)
    wins = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        part = lab[sl] == k
        area = part.sum()
        h, w = part.shape
        if area < 0.0005 * W * H or area > 0.03 * W * H:
            continue
        fill = area / float(h * w)
        if fill < 0.55 or h > 0.4 * H or w > 0.25 * W:
            continue
        # Kern wieder auf die schwarze Fläche wachsen lassen (nur innerhalb des Rahmens)
        y0, y1 = max(0, sl[0].start - 4), min(H, sl[0].stop + 4)
        x0, x1 = max(0, sl[1].start - 4), min(W, sl[1].stop + 4)
        m = np.zeros((H, W), bool)
        m[sl][part] = True
        m = ndimage.binary_dilation(m, iterations=4) & black
        m = ndimage.binary_fill_holes(m)
        ys, xs = np.nonzero(m)
        wins.append({"mask": m, "area": int(m.sum()), "x0": xs.min(), "x1": xs.max() + 1, "y0": ys.min(), "y1": ys.max() + 1})
    wins.sort(key=lambda d: -d["area"])
    wins = wins[:MAX_WIN]
    wins.sort(key=lambda d: (d["x0"] + d["x1"]) / 2)                      # von links nach rechts nummeriert
    idmap = np.zeros((H, W), np.uint8)
    for i, d in enumerate(wins, start=1):
        idmap[d["mask"]] = i
    soft = ndimage.gaussian_filter((idmap > 0).astype(np.float32), 1.2)
    # Lichtschein: nächstes Fenster im Umkreis, Stärke fällt mit dem Abstand
    dist, (iy, ix) = ndimage.distance_transform_edt(idmap == 0, return_indices=True)
    near = idmap[iy, ix]
    halo = np.exp(-dist / 18.0) * (dist > 0)
    out = np.zeros((H, W, 4), np.uint8)
    out[..., 0] = idmap * 16
    out[..., 1] = np.clip(soft * 255, 0, 255)
    out[..., 2] = near * 16
    out[..., 3] = np.clip(halo * 255, 0, 255)
    save(out, f"{OUT}/clocktower_winmask.png")
    # Zifferblatt: größte helle, runde Fläche in der oberen Hälfte
    bright = (lum > 150) & (img.min(axis=2) > 90)
    bright[H // 2:] = False
    bl, bn = ndimage.label(ndimage.binary_opening(bright, iterations=2))
    sz = ndimage.sum(bright, bl, range(1, bn + 1))
    k = int(np.argmax(sz)) + 1
    ys, xs = np.nonzero(ndimage.binary_fill_holes(bl == k))
    cx, cy = xs.mean(), ys.mean()
    r = 0.5 * max(xs.max() - xs.min(), ys.max() - ys.min())
    layout = {
        "size": [W, H],
        "clock": [round(cx / W, 4), round(1.0 - cy / H, 4), round(r / W, 4)],
        "windows": [{"x0": round(d["x0"] / W, 4), "x1": round(d["x1"] / W, 4),
                     "y0": round(1.0 - d["y1"] / H, 4), "y1": round(1.0 - d["y0"] / H, 4),
                     "area": round(d["area"] / (W * H), 5)} for d in wins],
    }
    with open(f"{OUT}/clocktower_layout.json", "w") as fh:
        json.dump(layout, fh, indent=1)
    print(f"   {len(wins)} Fenster, Zifferblatt {layout['clock']}")


def silhouettes() -> None:
    img = load("clocktower_silhouettes").astype(float)
    H, W = img.shape[:2]
    cw, ch = 128, 192
    atlas = np.zeros((3 * ch, 8 * cw, 4), np.uint8)
    for r in range(3):
        for c in range(8):
            sub = img[r * H // 3:(r + 1) * H // 3, c * W // 8:(c + 1) * W // 8]
            al = np.clip((235.0 - sub.mean(axis=2)) / 200.0, 0.0, 1.0) * 255.0
            cell = np.dstack([np.full(sub.shape[:2] + (3,), 255.0), al])
            atlas[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = scale(cell, cw, ch)
    save(atlas, f"{OUT}/clocktower_sil.png")


def climber() -> None:
    img = load("clocktower_climber")
    H, W = img.shape[:2]
    cw, ch = 160, 360
    atlas = np.zeros((2 * ch, 8 * cw, 4), np.uint8)
    for r in range(2):
        for c in range(8):
            sub = img[r * H // 2:(r + 1) * H // 2, c * W // 8:(c + 1) * W // 8]
            lum = sub.max(axis=2).astype(float)
            if r == 0:                                                    # vor Stein: Mantel, Haar, Hände sind heller als die Wand
                strong = ndimage.binary_opening(lum > 58, iterations=2)  # (die dunkle Hose lässt sich nicht sauber trennen,
                lab, n = ndimage.label(strong)                            # sie verschwindet im Schatten der Fassade)
                if n:
                    sz = ndimage.sum(strong, lab, range(1, n + 1))
                    strong = np.isin(lab, 1 + np.flatnonzero(sz >= 0.15 * sz.max()))
                m = ndimage.binary_fill_holes(ndimage.binary_closing(strong, iterations=8))
                al = ndimage.gaussian_filter(m.astype(np.float32), 1.5)
                ys = np.nonzero(m.any(axis=1))[0]
                if len(ys):                                               # Mantelsaum läuft weich in den Schatten aus
                    y1 = ys.max()
                    fade = np.clip((y1 - np.arange(m.shape[0])) / (0.12 * m.shape[0]), 0.0, 1.0)
                    al *= (0.35 + 0.65 * fade)[:, None]
            else:                                                     # auf Schwarz
                m = ndimage.binary_fill_holes(ndimage.binary_closing(lum > 14, iterations=4))
                al = ndimage.gaussian_filter(m.astype(np.float32), 1.0)
                if c == 7:                                                # Hocke: der Steinsockel unter ihm fällt weg
                    al[int(al.shape[0] * 0.6):] = 0.0
            cell = np.dstack([sub, np.clip(al, 0, 1) * 255.0])
            atlas[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = scale(cell, cw, ch)
    save(atlas, f"{OUT}/clocktower_climber.png")


def hands() -> None:
    img = load("clocktower_hands").astype(float)
    H, W = img.shape[:2]
    cw = W // 3
    lum = img.max(axis=2)
    out_w, out_h = 128, 512
    k = 250.0 / 690.0                                                     # Minutenzeiger (~690 px) reicht 250 px nach oben
    atlas = np.zeros((out_h, 3 * out_w, 4), np.uint8)
    for i in range(3):
        sub = img[:, i * cw:(i + 1) * cw]
        sl = lum[:, i * cw:(i + 1) * cw] > 30
        ys, xs = np.nonzero(sl)
        filled = ndimage.binary_fill_holes(sl)
        hole = filled & ~sl
        hole[: int(ys.max() * 0.55)] = False                              # Drehpunkt im Ring unten (nicht die Zierbögen)
        lab, n = ndimage.label(hole)
        if n:
            szs = ndimage.sum(hole, lab, range(1, n + 1))
            cy, cx = ndimage.center_of_mass(lab == int(np.argmax(szs)) + 1)
        else:
            cy, cx = 718.0, cw / 2.0
        al = np.clip((sub.max(axis=2) - 12.0) / 30.0, 0, 1)
        al = np.maximum(al, ndimage.binary_fill_holes(sl) * 1.0) * (1.0 - hole)  # Loch im Ring bleibt durchsichtig
        cell = np.dstack([sub, al * 255.0])
        sw, sh = int(round(cw * k)), int(round(H * k))
        sc = scale(cell, sw, sh)
        ox, oy = int(round(out_w / 2 - cx * k)), int(round(out_h / 2 - cy * k))
        dst = np.zeros((out_h, out_w, 4), np.uint8)
        y0, x0 = max(0, oy), max(0, ox)
        y1, x1 = min(out_h, oy + sh), min(out_w, ox + sw)
        dst[y0:y1, x0:x1] = sc[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        atlas[:, i * out_w:(i + 1) * out_w] = dst
    save(atlas, f"{OUT}/clocktower_hands.png")


def clockwork() -> None:
    img = load("clocktower_clockwork").astype(float)
    H, W = img.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    lum = img.max(axis=2)
    m = ndimage.binary_fill_holes(ndimage.binary_closing(lum > 25, iterations=6))
    lab, n = ndimage.label(m)
    if n:
        szs = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == int(np.argmax(szs)) + 1
    al = ndimage.gaussian_filter(m.astype(np.float32), 2.0)
    save(scale(np.dstack([img, al * 255.0]), 512, 512), f"{OUT}/clocktower_clockwork.png")


def car() -> None:
    img = load("clocktower_car").astype(float)
    H, W = img.shape[:2]
    cw = W // 4
    y0, y1 = 472, 680                                                     # Wagen ohne Spiegelung, Räder auf der Unterkante
    atlas = np.zeros((200, 3 * 512, 4), np.uint8)
    for i in range(3):
        sub = img[y0:y1, i * cw:(i + 1) * cw]
        lum = sub.max(axis=2)
        # vormultipliziert: rgb wird addiert, Alpha deckt nur die Karosserie ab (Blitzbögen und Glühen leuchten frei)
        body = sub[..., :3].min(axis=2)
        if i < 2:
            m = ndimage.binary_fill_holes(ndimage.binary_closing((lum > 18) & (body > 8), iterations=6))
            m = ndimage.binary_opening(m, iterations=3)
            al = ndimage.gaussian_filter(m.astype(np.float32), 1.0)
        else:                                                             # glühend: halb durchsichtig
            al = np.clip(lum / 160.0, 0, 1) * 0.7
        atlas[:, i * 512:(i + 1) * 512] = scale(np.dstack([sub, al * 255.0]), 512, 200)
    save(atlas, f"{OUT}/clocktower_car.png")


def main() -> int:
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    pygame.init()
    for name, fn in (("clocktower_tower", tower), ("clocktower_silhouettes", silhouettes), ("clocktower_climber", climber),
                     ("clocktower_hands", hands), ("clocktower_clockwork", clockwork), ("clocktower_car", car)):
        if os.path.exists(f"{RAW}/{name}.png"):
            fn()
        else:
            print("  fehlt:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
