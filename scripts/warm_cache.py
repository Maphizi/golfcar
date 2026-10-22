#!/usr/bin/env python3
"""Bild-Cache vorwärmen: alle PNGs unter assets/ (ohne raw/) einmal durch visualizers.engine.images laden, damit der
erste Start jedes Modus nach einem Update nicht mehr dekodieren muss. Läuft ohne Display (scripts/update.sh)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from visualizers.engine import images  # noqa: E402


def main() -> int:
    t0 = time.monotonic()
    n = 0
    for p in sorted(ROOT.glob("assets/**/*.png")):
        if "raw" in p.parts or "themes" in p.parts:
            continue
        if images.load_rgba(p) is not None:
            n += 1
    # alte Cache-Dateien (Bilder, die es so nicht mehr gibt) aufräumen
    keep = set()
    for p in sorted(ROOT.glob("assets/**/*.png")):
        st = p.stat()
        import hashlib
        try:
            rel = str(p.resolve().relative_to(ROOT))
        except ValueError:
            rel = str(p.resolve())
        keep.add(f"{p.stem}_{hashlib.sha1(f'{rel}|{st.st_mtime_ns}|{st.st_size}'.encode()).hexdigest()[:20]}.npy")
    removed = 0
    if images.CACHE.exists():
        for f in images.CACHE.glob("*.npy"):
            if f.name not in keep:
                f.unlink(missing_ok=True)
                removed += 1
    print(f"Bild-Cache: {n} Bilder bereit, {removed} alte entfernt, {time.monotonic() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
