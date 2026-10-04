"""Home-Screen (F6): schwarzer 80er-Fahrzeugcomputer mit Scanner-Balken und Menü.

Läuft als eigener Prozess, gestartet vom Launcher-Kern. Zeigt die Modi
F1–F5 und Systemwerte. Reagiert selbst auf keine Hotkeys, das macht der Kern.
"""
from __future__ import annotations

import math
import sys
import time

from . import config, display, sysmon

try:
    import pygame
except ImportError:  # pragma: no cover
    print("pygame fehlt", file=sys.stderr)
    sys.exit(1)

RED = (220, 30, 30)
DIM = (90, 10, 10)
AMBER = (230, 160, 40)
GREY = (120, 120, 120)
WHITE = (235, 235, 235)
BLACK = (0, 0, 0)


def draw_scanner(surf, rect, t):
    """KITT-Scanner: ein Lichtpunkt pendelt mit Nachleuchten."""
    x0, y, w, h = rect
    n = 24
    seg_w = w / n
    pos = (math.sin(t * 2.2) + 1) / 2 * (n - 1)
    for i in range(n):
        d = abs(i - pos)
        bright = max(0.0, 1.0 - d / 4.0) ** 2
        col = (int(DIM[0] + (RED[0] - DIM[0]) * bright) , int(10 + 40 * bright), int(10 + 30 * bright))
        pygame.draw.rect(surf, col, (x0 + i * seg_w + 2, y, seg_w - 4, h))


def main() -> int:
    settings = config.load_settings()
    modes = config.load_modes().get("modes", {})
    screen = display.init_fullscreen("KITT-CART HOME", settings)
    w, h = screen.get_size()
    clock = pygame.time.Clock()
    f_title = display.font(int(h * 0.09), bold=True)
    f_item = display.font(int(h * 0.045))
    f_small = display.font(int(h * 0.028))
    menu = [
        ("F1", "gaming"), ("F2", "viz_psychedelic"), ("F3", "viz_crt"),
        ("F4", "viz_eye"), ("F5", "kitt"), ("F7", "campfire"),
    ]
    t0 = time.monotonic()
    last_sys = 0.0
    sys_line = ""
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return 0
        t = time.monotonic() - t0
        if t - last_sys >= 2.0:
            sys_line = sysmon.format_line()
            last_sys = t
        screen.fill(BLACK)
        title = f_title.render("KITT-CART", True, RED)
        screen.blit(title, ((w - title.get_width()) // 2, int(h * 0.08)))
        draw_scanner(screen, (int(w * 0.15), int(h * 0.22), int(w * 0.7), int(h * 0.035)), t)
        y = int(h * 0.33)
        for key, mode in menu:
            spec = modes.get(mode, {})
            label = spec.get("label", mode)
            enabled = spec.get("enabled", True)
            col = AMBER if enabled else GREY
            k = f_item.render(key, True, col)
            lab = f_item.render(label, True, WHITE if enabled else GREY)
            screen.blit(k, (int(w * 0.25), y))
            screen.blit(lab, (int(w * 0.34), y))
            y += int(h * 0.068)
        foot = f_small.render("F6 HOME     ESC EXIT (DEV)", True, GREY)
        screen.blit(foot, ((w - foot.get_width()) // 2, int(h * 0.80)))
        s = f_small.render(sys_line, True, GREY)
        screen.blit(s, ((w - s.get_width()) // 2, int(h * 0.88)))
        # Scanlines für CRT-Anmutung (günstig: jede 3. Zeile abdunkeln)
        for yy in range(0, h, 3):
            pygame.draw.line(screen, (0, 0, 0), (0, yy), (w, yy))
        pygame.display.flip()
        clock.tick(int(settings.get("display", {}).get("home_fps", 30)))


if __name__ == "__main__":
    sys.exit(main())
