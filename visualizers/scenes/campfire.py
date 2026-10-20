"""Lagerfeuer (Taste 6): Cinemagraph aus echtem Bildmaterial. Szenen-Controller der GL-Engine.

Die Szene ist ein Foto (assets/campfire/scene.png, vom Piloten erzeugt), das der Shader lebendig
macht: an der Feuerstelle brennen echte Flammen aus einem Spritesheet (assets/campfire/flames.png,
8x5 Einzelbilder, Schleife mit Überblendung), dazu Funken, Rauch, Hitzeflimmern und flackerndes
Feuerlicht auf dem ganzen Bild. Dazu ein langsamer Kameraschwenk, Sternschnuppen und der Lauf des
Abends als Farbstimmung (uDay: Abendrot -> Nacht -> Morgengrauen) über cycle_minutes.
Musik: Bass lässt das Feuer größer und heller werden, Anschläge schicken Funken hoch, leise Stellen
lassen es ruhiger brennen. Windböen legen Flammen und Rauch zur Seite.
Lage der Feuerstelle im Bild: config/visualizer.toml [scenes.campfire] fire = [x, y, Breite, Höhe]
(Anteile der Bildbreite/-höhe, y von unten). Demo (--demo): Abend läuft 40x schneller.
"""
from __future__ import annotations

import logging
import random
import time

import numpy as np

from launcher import config as lcfg

log = logging.getLogger("campfire")
ASSETS = lcfg.ROOT / "assets" / "campfire"


def _load_rgba(path) -> np.ndarray | None:
    try:
        import pygame
        surf = pygame.image.load(str(path))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
        h, w = rgb.shape[:2]
        alpha = np.full((h, w, 1), 255, dtype=np.uint8)
        return np.ascontiguousarray(np.dstack([rgb, alpha]).astype(np.uint8)[::-1])     # GL: Zeile 0 unten
    except Exception as exc:
        log.warning("Bild %s nicht ladbar: %s", path, exc)
        return None


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.cycle = float(scene_cfg.get("cycle_minutes", 22.0)) * 60.0
        if demo:
            self.cycle /= 40.0
        self.t0 = time.monotonic()
        self.day_offset = float(scene_cfg.get("start_phase", 0.0))
        self.fire = tuple(float(v) for v in scene_cfg.get("fire", [0.44, 0.27, 0.26, 0.30]))
        self.grid = tuple(int(v) for v in scene_cfg.get("flame_frames", [8, 5]))
        self.fps = float(scene_cfg.get("flame_fps", 12.0))
        self.plate = _load_rgba(ASSETS / str(scene_cfg.get("plate", "scene.png")))
        self.flames = _load_rgba(ASSETS / str(scene_cfg.get("flames", "flames.png")))
        if self.plate is None:
            log.warning("Keine Szene: assets/campfire/scene.png fehlt, Bild bleibt dunkel")
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = self.t0
        self.bass_s = 0.0
        self.energy = 0.0
        self.spark = 0.0
        self.last_beat = 0.0
        self.wind = 0.0
        self.wind_target = 0.08
        self.next_gust_at = self.t0 + self.rng.uniform(15.0, 40.0)
        self.gust_until = 0.0
        self.fire_t = 0.0
        self.frame_t = 0.0
        self.meteor = (0.0, 0.0, 0.0, -10.0)        # x, y, Richtung, Zeitpunkt
        self.next_meteor_at = self.t0 + (self.rng.uniform(30.0, 80.0) if not demo else 3.0)
        self.cam = [0.0, 0.0]
        log.info("Lagerfeuer: Szene %s, Flammen %s, Abend %.0f min", "ok" if self.plate is not None else "fehlt",
                 "ok" if self.flames is not None else "fehlen", self.cycle / 60.0)

    def handle_event(self, ev) -> None:
        return

    def images(self) -> dict:
        out = {}
        if self.plate is not None:
            out["uPlate"] = (self.plate, 1)
        if self.flames is not None:
            out["uFlames"] = (self.flames, 1)
        return out

    def uniform_names(self):
        return ("uPlate", "uFlames", "uSeed", "uDay", "uBassS", "uEnergy", "uSpark", "uWind", "uFireT", "uFrame", "uFire", "uGrid",
                "uPlateOK", "uFlamesOK", "uPlateSize", "uFlamesSize", "uMeteor", "uCam")

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        silent = bool(getattr(f, "silent", True))
        live = 0.0 if silent else 1.0
        bass = float(getattr(f, "bass", 0.0)) * live
        rms = float(getattr(f, "rms", 0.0)) * live
        beat = float(getattr(f, "beat", 0.0)) * live
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.2)
        self.energy += (rms - self.energy) * min(1.0, dt / 3.0)
        if beat > 0.5 and now - self.last_beat > 0.3:
            self.last_beat = now
            self.spark = min(1.0, self.spark + 0.6 + 0.4 * beat)
        self.spark = max(0.0, self.spark - dt / 0.8)
        if now >= self.next_gust_at and self.gust_until <= now:
            self.wind_target = self.rng.uniform(0.4, 1.0)
            self.gust_until = now + self.rng.uniform(5.0, 12.0)
            self.next_gust_at = self.gust_until + self.rng.uniform(15.0, 45.0)
        elif now >= self.gust_until:
            self.wind_target = 0.08
        self.wind += (self.wind_target - self.wind) * min(1.0, dt / 2.5)
        # Flammenbilder: Tempo folgt leicht der Musik
        self.frame_t += dt * self.fps * (0.9 + 0.3 * self.energy + 0.2 * self.bass_s)
        self.fire_t += dt * (0.8 + 0.5 * self.energy)
        if now >= self.next_meteor_at:
            self.meteor = (self.rng.uniform(0.2, 0.9), self.rng.uniform(0.7, 0.95), self.rng.choice((-1.0, 1.0)), now)
            self.next_meteor_at = now + (self.rng.uniform(40.0, 120.0) if not self.demo else 5.0)
        # Kamera: ganz langsamer Schwenk (Ken-Burns), nie still
        tt = now - self.t0
        self.cam[0] = 0.012 * np.sin(tt * 0.021 + self.seed) + 0.006 * np.sin(tt * 0.047)
        self.cam[1] = 0.008 * np.sin(tt * 0.017 + 1.0) + 0.004 * np.cos(tt * 0.039)
        day = ((now - self.t0) / self.cycle + self.day_offset) % 1.0
        n_frames = float(self.grid[0] * self.grid[1])
        return {
            "uSeed": self.seed, "uDay": day, "uBassS": self.bass_s, "uEnergy": self.energy, "uSpark": self.spark,
            "uWind": self.wind, "uFireT": self.fire_t % 1000.0, "uFrame": self.frame_t % n_frames,
            "uFire": self.fire, "uGrid": (float(self.grid[0]), float(self.grid[1])),
            "uPlateOK": 1.0 if self.plate is not None else 0.0, "uFlamesOK": 1.0 if self.flames is not None else 0.0,
            "uPlateSize": (float(self.plate.shape[1]), float(self.plate.shape[0])) if self.plate is not None else (1.0, 1.0),
            "uFlamesSize": (float(self.flames.shape[1]), float(self.flames.shape[0])) if self.flames is not None else (1.0, 1.0),
            "uMeteor": (self.meteor[0], self.meteor[1], self.meteor[2], now - self.meteor[3]),
            "uCam": (float(self.cam[0]), float(self.cam[1])),
        }

    def overlays(self, t: float):
        return []
