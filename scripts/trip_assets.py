#!/usr/bin/env python3
"""Bildmaterial für den Waldtresen / die psychedelische Reise (Taste 2 im Thema Power of the Green).

    .venv/bin/python scripts/trip_assets.py beings WESEN.png        -> assets/trip/beings.png  (Raster 5x4 -> 20 Zellen à 256 px, RGBA)
    .venv/bin/python scripts/trip_assets.py symbols BOGEN.png       -> assets/trip/symbols.png (Atlas 8x5 à 128 px, RGBA)
    .venv/bin/python scripts/trip_assets.py texture NAME BILD.png   -> assets/trip/tex_NAME.png (1024 breit)
    .venv/bin/python scripts/trip_assets.py bar BILD.png            -> assets/trip/bar.png (max. 1920 breit)
    .venv/bin/python scripts/trip_assets.py atlas AUS.png BOGEN.png SPALTEN REIHEN ZELLE [SPLIT]   (beliebiger Bogen, z. B. Moorsee)
    .venv/bin/python scripts/trip_assets.py plate AUS.png BILD.png  (Vollbild, max. 1920 breit)
    .venv/bin/python scripts/trip_assets.py grid AUS.png BOGEN.png SPALTEN REIHEN ZELLE [SPLIT]    (Bogen mit Raster, Reihenfolge bleibt; Auge des Waldes)
    .venv/bin/python scripts/trip_assets.py slice AUS.png BOGEN.png SPALTEN REIHEN ZELLE          (gleich große Zellen schneiden, Fußpunkt unten; Animationen)
Wesen-Bogen: 5 Spalten x 4 Reihen auf Schwarz, jede Zelle wird einzeln freigestellt (gefüllte Fläche).
Symbol-Bogen: viele kleine Objekte auf Schwarz, Zusammenhangskomponenten, größte zuerst.
Braucht numpy, pygame, scipy (nur zum Erzeugen).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pygame
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taxi_sprites import derive_alpha, save_rgba  # noqa: E402

OUT = "assets/trip"


def fit_cell(rgb: np.ndarray, alpha: np.ndarray, cell: int, pad: int = 6) -> tuple[np.ndarray, np.ndarray]:
    img = np.dstack([rgb, alpha]).astype(np.uint8)
    surf = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (img.shape[1], img.shape[0]), "RGBA")
    sc = (cell - pad) / max(img.shape[0], img.shape[1])
    surf = pygame.transform.smoothscale(surf, (max(1, int(img.shape[1] * sc)), max(1, int(img.shape[0] * sc))))
    return pygame.surfarray.pixels3d(surf).transpose(1, 0, 2).copy(), pygame.surfarray.pixels_alpha(surf).transpose(1, 0).copy()


def place(atlas: np.ndarray, arr: np.ndarray, al: np.ndarray, r: int, c: int, cell: int) -> None:
    oy, ox = r * cell + (cell - arr.shape[0]) // 2, c * cell + (cell - arr.shape[1]) // 2
    atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], :3] = arr
    atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], 3] = al


def _components(alpha: np.ndarray, split: int):
    fg = ndimage.binary_closing(alpha > 40, iterations=2)
    if split > 0:
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
        mask = lab[sl] == i + 1
        area = int(mask.sum())
        hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if max(hh, ww) < 28:
            continue
        cy, cx = (sl[0].start + sl[0].stop) / 2.0, (sl[1].start + sl[1].stop) / 2.0
        items.append({"area": area, "side": max(hh, ww), "cy": cy, "cx": cx, "idx": i + 1, "sl": sl})
    return lab, items


def beings(path: str, cols: int = 5, rows: int = 4, cell: int = 256, split: int = 6) -> None:
    """Die 20 größten Objekte, nach Rasterposition (Reihe, Spalte) ihres Schwerpunkts sortiert."""
    rgb, alpha = derive_alpha(pygame.image.load(path).convert_alpha())
    H, W = alpha.shape
    lab, items = _components(alpha, split)
    items.sort(key=lambda it: -it["area"])
    items = items[:cols * rows]
    for it in items:
        it["r"] = min(rows - 1, int(it["cy"] * rows / H))
        it["c"] = min(cols - 1, int(it["cx"] * cols / W))
    items.sort(key=lambda it: (it["r"], it["c"]))
    atlas = np.zeros((rows * cell, cols * cell, 4), dtype=np.uint8)
    used = set()
    for it in items:
        r, c = it["r"], it["c"]
        if (r, c) in used:                                      # Rasterplatz doppelt: nächsten freien nehmen
            free = [(rr, cc) for rr in range(rows) for cc in range(cols) if (rr, cc) not in used]
            if not free:
                break
            r, c = free[0]
        used.add((r, c))
        sl = it["sl"]
        mask = lab[sl] == it["idx"]
        arr, al = fit_cell(rgb[sl], (alpha[sl] * mask).astype(np.uint8), cell)
        place(atlas, arr, al, r, c, cell)
    out = pygame.image.frombuffer(atlas.tobytes(), (cols * cell, rows * cell), "RGBA")
    pygame.image.save(out, f"{OUT}/beings.png")
    print(f"Wesen: {len(items)} Objekte in {cols}x{rows} Zellen à {cell} px")


def grid(out_path: str, path: str, cols: int, rows: int, cell: int, split: int = 5) -> None:
    """Bogen mit Rasteranordnung (z. B. 8x3 Augen, 8x4 Frösche/Figuren) -> Atlas in derselben Reihenfolge:
    jedes Objekt landet in der Zelle, in der sein Schwerpunkt im Quellbild liegt (für andere Modi)."""
    rgb, alpha = derive_alpha(pygame.image.load(path).convert_alpha())
    H, W = alpha.shape
    lab, items = _components(alpha, split)
    items.sort(key=lambda it: -it["area"])
    items = items[:cols * rows]
    for it in items:
        it["r"] = min(rows - 1, int(it["cy"] * rows / H))
        it["c"] = min(cols - 1, int(it["cx"] * cols / W))
    items.sort(key=lambda it: (it["r"], it["c"]))
    atlas = np.zeros((rows * cell, cols * cell, 4), dtype=np.uint8)
    used = set()
    for it in items:
        r, c = it["r"], it["c"]
        if (r, c) in used:
            free = [(rr, cc) for rr in range(rows) for cc in range(cols) if (rr, cc) not in used]
            if not free:
                break
            r, c = free[0]
            print(f"  Hinweis: Objekt bei ({it['cx']:.0f},{it['cy']:.0f}) doppelt in Zelle, nach ({r},{c}) verschoben")
        used.add((r, c))
        sl = it["sl"]
        mask = lab[sl] == it["idx"]
        arr, al = fit_cell(rgb[sl], (alpha[sl] * mask).astype(np.uint8), cell)
        place(atlas, arr, al, r, c, cell)
    out = pygame.image.frombuffer(atlas.tobytes(), (cols * cell, rows * cell), "RGBA")
    pygame.image.save(out, out_path)
    print(f"Raster {out_path}: {len(items)} Objekte in {cols}x{rows} Zellen à {cell} px")


def slice_sheet(out_path: str, path: str, cols: int, rows: int, cell: int, pad: int = 4) -> None:
    """Bogen in gleich große Zellen schneiden (ohne Objektsuche): jede Zelle einzeln freistellen (weißer oder
    schwarzer Hintergrund, Alpha) und in die Zielzelle einpassen. Für Animationsbögen, bei denen Spritzer oder
    Sockel sonst als eigene Objekte zählen würden (Froschsprung, Zwerge)."""
    surf = pygame.image.load(path).convert_alpha()
    W, H = surf.get_size()
    cw, ch = W / cols, H / rows
    atlas = np.zeros((rows * cell, cols * cell, 4), dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            sub = surf.subsurface((int(c * cw), int(r * ch), int(cw), int(ch))).copy()
            rgb, alpha = derive_alpha(sub, connected=True)
            ys, xs = np.where(alpha > 16)
            if len(ys) == 0:
                continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            arr, al = fit_cell(rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1], cell, pad)
            # unten bündig (Fußpunkt), horizontal zentriert
            oy, ox = r * cell + (cell - arr.shape[0]) - pad // 2, c * cell + (cell - arr.shape[1]) // 2
            atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], :3] = arr
            atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], 3] = al
    out = pygame.image.frombuffer(atlas.tobytes(), (cols * cell, rows * cell), "RGBA")
    pygame.image.save(out, out_path)
    print(f"Schnitt {out_path}: {cols}x{rows} Zellen à {cell} px")


def fill_alpha(rgb: np.ndarray, thr: int = 3, close: int = 6) -> np.ndarray:
    """Alpha als gefüllte Silhouette auf reinem Schwarz: alles > thr ist Objekt, Lücken (schwarzes Haar, dunkle Lippen)
    werden geschlossen und gefüllt, damit dunkle Teile innerhalb der Figur nicht durchsichtig werden."""
    lum = rgb.astype(int).max(axis=2)
    m = lum > thr
    m = ndimage.binary_closing(m, iterations=close)
    m = ndimage.binary_fill_holes(m)
    m = ndimage.binary_opening(m, iterations=1)
    al = ndimage.gaussian_filter(m.astype(np.float32), 0.8)
    return (np.clip(al, 0.0, 1.0) * 255).astype(np.uint8)


def cut_sheet(out_path: str, path: str, cols: int, rows: int, cw: int, ch: int, trim: int = 0, mode: str = "fill",
              pad: int = 4) -> None:
    """Bogen in gleich große Zellen schneiden, Zielzelle cw x ch (auch rechteckig). trim=0: der ganze Zellenausschnitt
    wird nur skaliert (gleiche Lage/Größe in allen Zellen, z. B. ein Kopf in vielen Gesten); trim=1: Inhalt freistellen
    und zentriert einpassen (Masken, Teile). mode "fill" = gefüllte Silhouette (Köpfe, Masken), "glow" = Alpha aus der
    Helligkeit (Neonteile mit Lücken)."""
    surf = pygame.image.load(path).convert_alpha()
    W, H = surf.get_size()
    sw, sh = W / cols, H / rows
    atlas = np.zeros((rows * ch, cols * cw, 4), dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            sub = surf.subsurface((int(c * sw), int(r * sh), int(sw), int(sh))).copy()
            if mode == "fill":
                rgb = pygame.surfarray.array3d(sub).transpose(1, 0, 2).copy()
                alpha = fill_alpha(rgb)
            else:
                rgb, alpha = derive_alpha(sub, connected=False)
            if trim:
                ys, xs = np.where(alpha > 16)
                if len(ys) == 0:
                    continue
                y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
                rgb, alpha = rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
                sc = min((cw - pad) / rgb.shape[1], (ch - pad) / rgb.shape[0])
            else:
                sc = min(cw / rgb.shape[1], ch / rgb.shape[0])
            img = np.dstack([rgb, alpha]).astype(np.uint8)
            s2 = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (img.shape[1], img.shape[0]), "RGBA")
            s2 = pygame.transform.smoothscale(s2, (max(1, int(img.shape[1] * sc)), max(1, int(img.shape[0] * sc))))
            arr = pygame.surfarray.pixels3d(s2).transpose(1, 0, 2).copy()
            al = pygame.surfarray.pixels_alpha(s2).transpose(1, 0).copy()
            oy, ox = r * ch + (ch - arr.shape[0]) // 2, c * cw + (cw - arr.shape[1]) // 2
            atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], :3] = arr
            atlas[oy:oy + arr.shape[0], ox:ox + arr.shape[1], 3] = al
    out = pygame.image.frombuffer(atlas.tobytes(), (cols * cw, rows * ch), "RGBA")
    pygame.image.save(out, out_path)
    print(f"Zellen {out_path}: {cols}x{rows} à {cw}x{ch} px ({'freigestellt' if trim else 'ganzer Ausschnitt'})")


def symbols(path: str, cols: int = 8, rows: int = 5, cell: int = 128, split: int = 5) -> None:
    rgb, alpha = derive_alpha(pygame.image.load(path).convert_alpha())
    lab, items = _components(alpha, split)
    items = [it for it in items if it["side"] <= 260]
    items.sort(key=lambda it: -it["area"])
    atlas = np.zeros((rows * cell, cols * cell, 4), dtype=np.uint8)
    for k, it in enumerate(items[:cols * rows]):
        sl = it["sl"]
        mask = lab[sl] == it["idx"]
        arr, al = fit_cell(rgb[sl], (alpha[sl] * mask).astype(np.uint8), cell)
        place(atlas, arr, al, k // cols, k % cols, cell)
    out = pygame.image.frombuffer(atlas.tobytes(), (cols * cell, rows * cell), "RGBA")
    pygame.image.save(out, f"{OUT}/symbols.png")
    print(f"Symbole: {min(len(items), cols * rows)} von {len(items)} in {cols}x{rows} Zellen à {cell} px")


def atlas(out_path: str, path: str, cols: int, rows: int, cell: int, split: int = 5, max_side: int = 100000) -> None:
    """Beliebiger Bogen auf Schwarz -> Atlas cols x rows à cell px, größte Objekte zuerst (auch für andere Modi)."""
    rgb, alpha = derive_alpha(pygame.image.load(path).convert_alpha())
    lab, items = _components(alpha, split)
    items = [it for it in items if it["side"] <= max_side]
    items.sort(key=lambda it: -it["area"])
    out = np.zeros((rows * cell, cols * cell, 4), dtype=np.uint8)
    for k, it in enumerate(items[:cols * rows]):
        sl = it["sl"]
        mask = lab[sl] == it["idx"]
        arr, al = fit_cell(rgb[sl], (alpha[sl] * mask).astype(np.uint8), cell)
        place(out, arr, al, k // cols, k % cols, cell)
    surf = pygame.image.frombuffer(out.tobytes(), (cols * cell, rows * cell), "RGBA")
    pygame.image.save(surf, out_path)
    print(f"Atlas {out_path}: {min(len(items), cols * rows)} von {len(items)} in {cols}x{rows} à {cell} px")


def plate(out_path: str, path: str, width: int = 1920) -> None:
    surf = pygame.image.load(path)
    w, h = surf.get_size()
    if w > width:
        surf = pygame.transform.smoothscale(surf, (width, int(h * width / w)))
    pygame.image.save(surf, out_path)
    print("Bild", out_path, surf.get_size())


def texture(name: str, path: str, width: int = 1024) -> None:
    surf = pygame.image.load(path)
    w, h = surf.get_size()
    surf = pygame.transform.smoothscale(surf, (width, int(h * width / w)))
    pygame.image.save(surf, f"{OUT}/tex_{name}.png")
    print("Textur", name, surf.get_size())


def bar(path: str, width: int = 1920) -> None:
    surf = pygame.image.load(path)
    w, h = surf.get_size()
    if w > width:
        surf = pygame.transform.smoothscale(surf, (width, int(h * width / w)))
    pygame.image.save(surf, f"{OUT}/bar.png")
    print("Tresen", surf.get_size())


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    cmd = sys.argv[1]
    if cmd == "beings":
        beings(sys.argv[2])
    elif cmd == "symbols":
        symbols(sys.argv[2])
    elif cmd == "slice":        # slice AUSGABE.png BOGEN.png SPALTEN REIHEN ZELLE  (gleich große Zellen, unten bündig)
        slice_sheet(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
    elif cmd == "cut":
        cut_sheet(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7]),
                  int(sys.argv[8]) if len(sys.argv) > 8 else 0, sys.argv[9] if len(sys.argv) > 9 else "fill")
    elif cmd == "grid":
        grid(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7]) if len(sys.argv) > 7 else 5)
    elif cmd == "texture":
        texture(sys.argv[2], sys.argv[3])
    elif cmd == "bar":
        bar(sys.argv[2])
    elif cmd == "atlas":        # atlas AUSGABE.png BOGEN.png SPALTEN REIHEN ZELLE [SPLIT]
        atlas(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7]) if len(sys.argv) > 7 else 5)
    elif cmd == "plate":        # plate AUSGABE.png BILD.png
        plate(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
