"""Platzhalter-Modus: Vollbild mit Modusnamen, bis der echte Modus gebaut ist.

    python -m launcher.placeholder "F2  PSYCHEDELIC"
"""
from __future__ import annotations

import math
import sys
import time

from . import config, display

import pygame


def main(argv) -> int:
    name = " ".join(argv) or "PLATZHALTER"
    settings = config.load_settings()
    screen = display.init_fullscreen(name, settings)
    w, h = screen.get_size()
    clock = pygame.time.Clock()
    f_big = display.font(int(h * 0.08), bold=True)
    f_small = display.font(int(h * 0.03))
    t0 = time.monotonic()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return 0
        t = time.monotonic() - t0
        screen.fill((0, 0, 0))
        pulse = int(120 + 100 * (0.5 + 0.5 * math.sin(t * 2)))
        txt = f_big.render(name, True, (pulse, pulse // 3, pulse // 3))
        screen.blit(txt, ((w - txt.get_width()) // 2, (h - txt.get_height()) // 2))
        sub = f_small.render("Platzhalter – echter Modus folgt.  F6 = Home", True, (110, 110, 110))
        screen.blit(sub, ((w - sub.get_width()) // 2, int(h * 0.65)))
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
