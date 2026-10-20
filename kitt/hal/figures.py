"""Schwebende Figuren bei HAL 3000: Astronaut und Alien (assets/hal/figures.png, zwei Zellen 512x512).

Steuerknüppel LINKS = Astronaut statt HAL-Konsole, RECHTS = Alien, OBEN = beide, UNTEN = wieder HAL.
Die Figuren treiben leicht durch den Raum (langsame Lissajous-Bahnen), drehen sich träge und
"tanzen" zur Musik: Bass lässt sie federn (Größe pulst, kleiner Hüpfer), jeder Beat gibt einen
Schwung in die Drehung, Mitten lassen den Körper wellig schwingen (Verzerrung im Shader), Höhen ein
feines Zittern. Alles geglättet, damit es nach Schweben aussieht und nicht nach Zappeln.
"""
from __future__ import annotations

import logging
import math
import random
import time

import numpy as np

from launcher import config as lcfg, wled

log = logging.getLogger("hal.figures")

ATLAS = lcfg.ROOT / "assets" / "hal" / "figures.png"
MODE_HAL, MODE_ASTRO, MODE_ALIEN, MODE_BOTH = 0, 1, 2, 3
NAMES = {MODE_HAL: "HAL", MODE_ASTRO: "ASTRONAUT", MODE_ALIEN: "ALIEN", MODE_BOTH: "ASTRONAUT UND ALIEN"}


def load_atlas() -> np.ndarray | None:
    try:
        import pygame
        surf = pygame.image.load(str(ATLAS))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
        alpha = pygame.surfarray.array_alpha(surf).transpose(1, 0)
        img = np.dstack([rgb, alpha]).astype(np.uint8)
        return img[::-1].copy()            # GL: Zeile 0 unten
    except Exception as exc:
        log.warning("Figuren-Atlas %s nicht ladbar: %s", ATLAS, exc)
        return None


class Figure:
    def __init__(self, rng: random.Random, cell: int, home_x: float):
        self.cell = cell                   # 0 Astronaut, 1 Alien (Zelle im Atlas)
        self.home_x = home_x
        self.phase = rng.uniform(0.0, 6.28)
        self.f1, self.f2 = rng.uniform(0.05, 0.09), rng.uniform(0.04, 0.07)
        self.spin = rng.choice((-1.0, 1.0)) * rng.uniform(0.04, 0.08)
        self.angle = rng.uniform(-0.3, 0.3)
        self.ang_vel = 0.0
        self.x, self.y = home_x, 0.0
        self.scale = 0.0
        self.bounce = 0.0

    def update(self, t: float, dt: float, bass: float, beat_kick: float, energy: float, rng: random.Random, target_scale: float, home_x: float) -> None:
        self.home_x += (home_x - self.home_x) * min(1.0, dt / 1.5)
        # Schweben: zwei langsame Sinusbahnen übereinander
        tx = self.home_x + 0.16 * math.sin(t * self.f1 * 6.28 + self.phase) + 0.05 * math.sin(t * self.f2 * 9.0)
        ty = 0.02 + 0.11 * math.sin(t * self.f2 * 6.28 + self.phase * 1.7) + 0.04 * math.cos(t * self.f1 * 11.0)
        self.x += (tx - self.x) * min(1.0, dt / 1.2)
        self.y += (ty - self.y) * min(1.0, dt / 1.2)
        # Drehung: träge, Beat gibt Schwung in die aktuelle Richtung
        if beat_kick > 0.0:
            self.ang_vel += beat_kick * rng.choice((-1.0, 1.0)) * 0.9
        self.ang_vel += (self.spin * (0.5 + energy) - self.ang_vel) * min(1.0, dt / 2.5)
        self.angle += self.ang_vel * dt
        if abs(self.angle) > 0.9:                      # nicht auf den Kopf: sanft zurückdrehen
            self.ang_vel -= self.angle * dt * 1.5
        # Federn mit dem Bass
        self.bounce += (bass - self.bounce) * min(1.0, dt / 0.12)
        self.scale += (target_scale * (1.0 + 0.1 * self.bounce) - self.scale) * min(1.0, dt / 0.4)


class Figures:
    uniform_names = ("uFigMode", "uFigMix", "uFigA", "uFigB", "uFigWave", "uFigTex")

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.mode = MODE_HAL
        self.mix = 0.0
        self.atlas = load_atlas()
        self.atlas_version = 1
        self.astro = Figure(self.rng, 0, -0.1)
        self.alien = Figure(self.rng, 1, 0.1)
        self.last = time.monotonic()
        self.last_beat = 0.0
        self.wave_phase = 0.0
        self.wave_amp = 0.0
        self.mid_s = 0.0
        self.high_s = 0.0

    def set_mode(self, mode: int) -> None:
        if self.atlas is None and mode != MODE_HAL:
            log.warning("Figuren nicht verfügbar (assets/hal/figures.png fehlt)")
            return
        if mode != self.mode:
            self.mode = mode
            log.info("Figur: %s", NAMES.get(mode, mode))
            wled.apply_mode_async({MODE_HAL: "hal", MODE_ASTRO: "hal_astronaut", MODE_ALIEN: "hal_alien", MODE_BOTH: "hal_both"}[mode])

    def images(self) -> dict:
        if self.atlas is None:
            return {}
        return {"uFigTex": (self.atlas, self.atlas_version)}

    def update(self, now: float, f) -> dict:
        dt = min(0.1, max(0.0, now - self.last))
        self.last = now
        t = now % 10000.0
        live = 0.0 if (f is None or getattr(f, "silent", True)) else 1.0
        bass = float(getattr(f, "bass", 0.0)) * live if f is not None else 0.0
        mid = float(getattr(f, "mid", 0.0)) * live if f is not None else 0.0
        high = float(getattr(f, "high", 0.0)) * live if f is not None else 0.0
        beat = float(getattr(f, "beat", 0.0)) * live if f is not None else 0.0
        energy = float(getattr(f, "rms", 0.0)) * live if f is not None else 0.0
        kick = 0.0
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            kick = beat
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.3)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.15)
        # Körperwelle: Phase läuft mit der Musik, Stärke aus den Mitten (sanft)
        self.wave_phase = (self.wave_phase + dt * (1.2 + 3.0 * self.mid_s)) % 1000.0
        self.wave_amp += ((0.012 + 0.05 * self.mid_s + 0.02 * self.high_s) * (0.4 + 0.6 * live) - self.wave_amp) * min(1.0, dt / 0.5)
        target = 1.0 if self.mode != MODE_HAL else 0.0
        self.mix += (target - self.mix) * min(1.0, dt / 0.7)
        both = self.mode == MODE_BOTH
        show_a = self.mode in (MODE_ASTRO, MODE_BOTH)
        show_b = self.mode in (MODE_ALIEN, MODE_BOTH)
        size = 0.62 if both else 0.78
        self.astro.update(t, dt, bass, kick, energy, self.rng, size if show_a else 0.0, -0.34 if both else 0.0)
        self.alien.update(t, dt, bass, kick, energy, self.rng, size if show_b else 0.0, 0.34 if both else 0.0)
        return {"uFigMode": float(self.mode), "uFigMix": self.mix,
                "uFigA": (self.astro.x, self.astro.y, self.astro.angle, self.astro.scale),
                "uFigB": (self.alien.x, self.alien.y, self.alien.angle, self.alien.scale),
                "uFigWave": (self.wave_phase, self.wave_amp)}
