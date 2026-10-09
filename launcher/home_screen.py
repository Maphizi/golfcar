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

# Space-Thema: gelbes Monochrom-Display
RED = (255, 214, 10)        # Hauptfarbe (Name aus dem Klassik-Thema beibehalten)
DIM = (70, 58, 5)
AMBER = (255, 160, 30)
GREY = (120, 110, 60)
WHITE = (255, 236, 120)
BLACK = (0, 0, 0)


def draw_glyphs(surf, x, y, n, cell, seed, color):
    """Dekorative fremde Schrift: 3x5-Pixelmuster je Zeichen aus einem Hash."""
    import random
    rng = random.Random(seed)
    for i in range(n):
        head = rng.random() > 0.3
        for cy in range(5):
            for cx in range(3):
                if rng.random() > 0.55 or (cy == 0 and head):
                    pygame.draw.rect(surf, color, (x + i * cell * 4 + cx * cell, y + cy * cell, cell - 1, cell - 1))


def draw_scanner(surf, rect, t):
    """KITT-Scanner: ein Lichtpunkt pendelt mit Nachleuchten."""
    x0, y, w, h = rect
    n = 24
    seg_w = w / n
    pos = (math.sin(t * 2.2) + 1) / 2 * (n - 1)
    for i in range(n):
        d = abs(i - pos)
        bright = max(0.0, 1.0 - d / 4.0) ** 2
        col = tuple(int(DIM[k] + (RED[k] - DIM[k]) * bright) for k in range(3))
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
        screen.blit(title, ((w - title.get_width()) // 2, int(h * 0.06)))
        draw_glyphs(screen, int(w * 0.36), int(h * 0.17), 12, max(2, int(h * 0.006)), 7, AMBER)
        draw_scanner(screen, (int(w * 0.15), int(h * 0.23), int(w * 0.7), int(h * 0.035)), t)
        pygame.draw.rect(screen, DIM, (int(w * 0.06), int(h * 0.04), int(w * 0.88), int(h * 0.92)), 2)
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
        foot = f_small.render("F6 HAUPTMENÜ     ESC EXIT (DEV)", True, GREY)
        screen.blit(foot, ((w - foot.get_width()) // 2, int(h * 0.80)))
        s = f_small.render(sys_line, True, GREY)
        screen.blit(s, ((w - s.get_width()) // 2, int(h * 0.88)))
        draw_glyphs(screen, int(w * 0.62), int(h * 0.88), 8, max(2, int(h * 0.005)), 23, DIM)
        # Scanlines für CRT-Anmutung (günstig: jede 3. Zeile abdunkeln)
        for yy in range(0, h, 3):
            pygame.draw.line(screen, (0, 0, 0), (0, yy), (w, yy))
        pygame.display.flip()
        clock.tick(int(settings.get("display", {}).get("home_fps", 30)))


if __name__ == "__main__":
    sys.exit(main())
