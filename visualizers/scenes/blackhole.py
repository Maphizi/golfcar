"""Schwarzes Loch (Taste 3): Szenen-Controller. Glättet die Musik zu Hüllkurven, die der Shader
nicht selbst halten kann (Jet-Ausbruch nach dem Beat, Flare, Kamerawackeln), würfelt pro Start
Blickwinkel, Scheibenfarbe und Orbitrichtung und lässt die Kamera langsam kreisen.

Tasten: LINKS/RECHTS = Kamera schneller/andersherum, OBEN/UNTEN = Neigung, Start (ENTER) = Jet zünden,
Kippschalter AN (SPACE) = Nahaufnahme, AUS (BACKSPACE) = zurück.
"""
from __future__ import annotations

import logging
import math
import random
import time

import pygame

log = logging.getLogger("blackhole")


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.seed = self.rng.uniform(1.0, 500.0)
        self.tilt = self.rng.uniform(0.12, 0.32)           # Neigung der Scheibe zur Blickrichtung (rad)
        self.tilt_target = self.tilt
        self.orbit_speed = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(0.025, 0.045)
        self.angle = self.rng.uniform(0.0, 6.28)
        self.palette = self.rng.randrange(3)                # 0 orange/weiß, 1 blau/violett, 2 gold/rot
        self.jet = 0.0
        self.flare = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.last = time.monotonic()
        self.last_beat_at = 0.0
        self.bass_s = 0.0
        self.demo_next = time.monotonic() + 6.0
        log.info("Schwarzes Loch: Palette %d, Neigung %.2f, Orbit %.3f", self.palette, self.tilt, self.orbit_speed)

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.orbit_speed = max(-0.25, min(0.25, self.orbit_speed + 0.02))
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self.orbit_speed = max(-0.25, min(0.25, self.orbit_speed - 0.02))
        elif ev.key == pygame.K_UP:
            self.tilt_target = min(0.6, self.tilt_target + 0.06)
        elif ev.key == pygame.K_DOWN:
            self.tilt_target = max(0.03, self.tilt_target - 0.06)
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.jet = 1.0
            self.flare = 1.0
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    def uniform_names(self):
        return ("uSeed", "uTilt", "uAngle", "uPalette", "uJet", "uFlare", "uZoom", "uBassS")

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        beat = float(getattr(f, "beat", 0.0))
        bass = float(getattr(f, "bass", 0.0))
        silent = bool(getattr(f, "silent", True))
        # Jet: starker Beat zündet ihn, dann klingt er über ~3 s ab; Flare kürzer
        if beat > 0.6 and now - self.last_beat_at > 0.35 and not silent:
            self.jet = min(1.0, self.jet + 0.5 + 0.5 * beat)
            self.flare = 1.0
            self.last_beat_at = now
        self.jet = max(0.0, self.jet - dt / 3.0)
        self.flare = max(0.0, self.flare - dt / 0.5)
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.15)
        self.angle += dt * self.orbit_speed * (1.0 + 0.6 * self.bass_s)
        self.tilt += (self.tilt_target - self.tilt) * min(1.0, dt / 1.5)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 2.0)
        if self.demo and now >= self.demo_next:
            self.jet, self.flare = 1.0, 1.0
            self.zoom_target = 1.0 - self.zoom_target
            self.demo_next = now + 8.0
        return {"uSeed": self.seed, "uTilt": self.tilt, "uAngle": self.angle, "uPalette": float(self.palette),
                "uJet": self.jet, "uFlare": self.flare, "uZoom": self.zoom, "uBassS": self.bass_s}

    def overlays(self, t: float):
        return []
