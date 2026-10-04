"""Boot-Sequenz: kurze Startanimation vor dem Home-Screen (Modus "boot", beendet sich selbst)."""
from __future__ import annotations

import math
import sys
import time

from . import config, display
from .home_screen import draw_scanner, RED, AMBER, GREY, BLACK

import pygame

LINES = ["SYSTEMCHECK", "SENSOREN  . . . . OK", "STIMME  . . . . . OK", "FAHRER  . . . . . UNGEPRÜFT", "KITT-CART ONLINE"]


def main() -> int:
    settings = config.load_settings()
    dur = float(settings.get("launcher", {}).get("boot_seconds", 4.0))
    screen = display.init_fullscreen("KITT-CART BOOT", settings)
    w, h = screen.get_size()
    clock = pygame.time.Clock()
    f_title = display.font(int(h * 0.09), bold=True)
    f_line = display.font(int(h * 0.035))
    t0 = time.monotonic()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return 0
        t = time.monotonic() - t0
        if t >= dur:
            return 0
        screen.fill(BLACK)
        # Titel blendet ein
        a = min(1.0, t / 0.8)
        title = f_title.render("KITT-CART", True, (int(220 * a), int(30 * a), int(30 * a)))
        screen.blit(title, ((w - title.get_width()) // 2, int(h * 0.18)))
        draw_scanner(screen, (int(w * 0.15), int(h * 0.32), int(w * 0.7), int(h * 0.035)), t * 1.6)
        # Zeilen erscheinen nacheinander
        y = int(h * 0.45)
        per = (dur - 1.0) / len(LINES)
        for i, line in enumerate(LINES):
            if t > 0.6 + i * per:
                col = AMBER if i == len(LINES) - 1 else GREY
                cursor = "_" if (i == len(LINES) - 1 and int(t * 3) % 2 == 0) else ""
                s = f_line.render(line + cursor, True, col)
                screen.blit(s, (int(w * 0.3), y))
            y += int(h * 0.06)
        for yy in range(0, h, 3):
            pygame.draw.line(screen, BLACK, (0, yy), (w, yy))
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    sys.exit(main())
