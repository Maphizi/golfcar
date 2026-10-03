"""Gemeinsame Vollbild-Hilfen für pygame-Fenster (Home, Platzhalter)."""
from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402


def init_fullscreen(title: str, settings: dict) -> pygame.Surface:
    disp = settings.get("display", {})
    driver = disp.get("sdl_videodriver", "")
    if driver and driver != "auto":
        os.environ["SDL_VIDEODRIVER"] = driver
    pygame.init()
    pygame.display.set_caption(title)
    pygame.mouse.set_visible(False)
    size = (int(disp.get("width", 0)), int(disp.get("height", 0)))
    flags = pygame.FULLSCREEN
    if disp.get("vsync", True):
        screen = pygame.display.set_mode(size, flags, vsync=1)
    else:
        screen = pygame.display.set_mode(size, flags)
    return screen


def font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in ("dejavusansmono", "liberationmono", "freemono"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.SysFont(None, size, bold=bold)
