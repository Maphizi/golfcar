#!/usr/bin/env python3
"""Rahmen der Slotmaschinen nachbearbeiten: Objekte, die ins Walzenfeld ragen, entfernen (future_frame: das Hoverboard).
Aufruf: scripts/frame_clean.py assets/slots/future_frame.png  (nach scripts/slots_assets.sh)."""
from __future__ import annotations

import sys

import numpy as np
import pygame

# je Rahmen: "inside" = Rechtecke (x0, y0, x1, y1 in 1920x1080) rein im Walzenfeld -> alles schwarz; "edge" = Streifen auf
# dem Rahmenrand daneben, in denen nur die Farben des Objekts (pink/grün) ersetzt werden, Quelle = (dx, dy) versetzt
CLEAN = {
    "future_frame.png": {"inside": [(305, 470, 600, 1016)],
                         "edge": [(286, 470, 305, 1016, 0, -420), (286, 1016, 600, 1068, 330, 0)]},
}


def object_mask(a: np.ndarray) -> np.ndarray:
    r, g, b = (a[..., i].astype(int) for i in range(3))
    pink = (r > 80) & (r > g + 25) & (b > g - 10)                     # auch der dunkle Rand/Schatten des Boards
    green = (g > r + 15) & (g > b + 15) & (g > 90)
    return pink | green


def main() -> int:
    for path in sys.argv[1:]:
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        rule = CLEAN.get(name)
        if not rule:
            continue
        surf = pygame.image.load(path)
        a = pygame.surfarray.array3d(surf).transpose(1, 0, 2).copy()
        for x0, y0, x1, y1 in rule.get("inside", []):
            a[y0:y1, x0:x1] = 0
        for x0, y0, x1, y1, dx, dy in rule.get("edge", []):
            sub = a[y0:y1, x0:x1]
            m = object_mask(sub)
            src = a[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            sub[m] = src[m]
            a[y0:y1, x0:x1] = sub
        out = pygame.image.frombuffer(np.ascontiguousarray(a).tobytes(), (a.shape[1], a.shape[0]), "RGB")
        pygame.image.save(out, path)
        print(f"Rahmen bereinigt: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
