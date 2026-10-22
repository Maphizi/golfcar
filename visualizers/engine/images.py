"""Bilder für die Szenen laden: RGBA-Array (H x W x 4, Zeile 0 unten, für GL) mit npy-Cache unter .cache/img.
PNG-Dekodierung und Umwandlung kosten auf dem Pi je 1080p-Bild spürbar Zeit; der Cache liest das fertige Array direkt.
Schlüssel ist Pfad + Änderungszeit + Größe, neue Bilder (update.sh) werden also automatisch neu gelesen."""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger("images")
ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("KITT_IMG_CACHE") or (ROOT / ".cache" / "img"))


def _decode(path: Path) -> np.ndarray:
    import pygame
    surf = pygame.image.load(str(path))
    rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
    try:
        alpha = pygame.surfarray.array_alpha(surf).transpose(1, 0)
    except ValueError:
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    return np.ascontiguousarray(np.dstack([rgb, alpha]).astype(np.uint8)[::-1])


def load_rgba(path) -> np.ndarray | None:
    """RGBA-Array des Bilds (Zeile 0 unten) oder None, wenn es fehlt/nicht ladbar ist."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        log.warning("Bild %s fehlt", p)
        return None
    try:
        rel = str(p.resolve().relative_to(ROOT))
    except ValueError:
        rel = str(p.resolve())
    key = hashlib.sha1(f"{rel}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:20]
    cache = CACHE / f"{p.stem}_{key}.npy"
    if cache.exists():
        try:
            return np.load(cache)
        except Exception as exc:
            log.warning("Bild-Cache %s defekt (%s), lese neu", cache.name, exc)
    try:
        arr = _decode(p)
    except Exception as exc:
        log.warning("Bild %s nicht ladbar: %s", p, exc)
        return None
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".tmp.npy")
        np.save(tmp, arr)
        os.replace(tmp, cache)
    except OSError as exc:
        log.debug("Bild-Cache nicht schreibbar: %s", exc)
    return arr
