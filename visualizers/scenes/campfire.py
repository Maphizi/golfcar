"""Lagerfeuer (Taste 6): Beduinen-Abend in der Wüste. Szenen-Controller der GL-Engine.

Liefert dem Shader den Lauf des Abends (uDay: 0 Abenddämmerung -> Nacht -> Morgendämmerung, ein
Durchlauf dauert cycle_minutes), geglättete Musikhüllkurven (das Feuer atmet ruhig mit: Bass lässt
die Glut pulsieren, Anschläge schicken Funken hoch, leise Stellen lassen das Feuer kleiner werden),
Windböen (Flammen legen sich, Sand weht über die Dünenkämme, das Zelttuch flattert) und alle paar
Minuten eine Kamelkarawane, die über eine ferne Düne zieht.
Demo (--demo): Abend läuft 40x schneller, Karawane kommt schnell.
"""
from __future__ import annotations

import logging
import random
import time

log = logging.getLogger("campfire")


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.cycle = float(scene_cfg.get("cycle_minutes", 22.0)) * 60.0
        if demo:
            self.cycle /= 40.0
        self.t0 = time.monotonic()
        self.day_offset = float(scene_cfg.get("start_phase", 0.0))     # 0 = Abenddämmerung beim Start
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = self.t0
        self.bass_s = 0.0
        self.energy = 0.0
        self.spark = 0.0
        self.last_beat = 0.0
        self.wind = 0.0
        self.wind_target = 0.0
        self.next_gust_at = self.t0 + self.rng.uniform(15.0, 40.0)
        self.gust_until = 0.0
        self.caravan_t0: float | None = None
        self.caravan_len = 90.0
        self.caravan_dir = 1.0
        self.next_caravan_at = self.t0 + (self.rng.uniform(60.0, 150.0) if not demo else 4.0)
        self.fire_t = 0.0                                  # Feuerzeit: läuft mit der Energie schneller
        log.info("Lagerfeuer: Abend dauert %.0f min, Seed %.1f", self.cycle / 60.0, self.seed)

    def handle_event(self, ev) -> None:
        return

    def uniform_names(self):
        return ("uSeed", "uDay", "uBassS", "uEnergy", "uSpark", "uWind", "uCaravan", "uCaravanDir", "uFireT")

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        silent = bool(getattr(f, "silent", True))
        live = 0.0 if silent else 1.0
        bass = float(getattr(f, "bass", 0.0)) * live
        rms = float(getattr(f, "rms", 0.0)) * live
        beat = float(getattr(f, "beat", 0.0)) * live
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.25)
        self.energy += (rms - self.energy) * min(1.0, dt / 3.0)
        if beat > 0.5 and now - self.last_beat > 0.3:
            self.last_beat = now
            self.spark = min(1.0, self.spark + 0.6 + 0.4 * beat)
        self.spark = max(0.0, self.spark - dt / 0.8)
        # Windböen
        if now >= self.next_gust_at and self.gust_until <= now:
            self.wind_target = self.rng.uniform(0.4, 1.0)
            self.gust_until = now + self.rng.uniform(5.0, 12.0)
            self.next_gust_at = self.gust_until + self.rng.uniform(15.0, 45.0)
        elif now >= self.gust_until:
            self.wind_target = 0.08
        self.wind += (self.wind_target - self.wind) * min(1.0, dt / 2.5)
        # Karawane
        if self.caravan_t0 is not None and now - self.caravan_t0 > self.caravan_len:
            self.caravan_t0 = None
            self.next_caravan_at = now + (self.rng.uniform(120.0, 300.0) if not self.demo else 8.0)
        if self.caravan_t0 is None and now >= self.next_caravan_at:
            self.caravan_t0 = now
            self.caravan_len = self.rng.uniform(70.0, 110.0) if not self.demo else 6.0
            self.caravan_dir = self.rng.choice((-1.0, 1.0))
            log.info("Karawane zieht vorbei (%.0f s)", self.caravan_len)
        self.fire_t += dt * (0.7 + 0.6 * self.energy + 0.3 * self.bass_s)
        day = ((now - self.t0) / self.cycle + self.day_offset) % 1.0
        return {
            "uSeed": self.seed, "uDay": day, "uBassS": self.bass_s, "uEnergy": self.energy, "uSpark": self.spark,
            "uWind": self.wind, "uFireT": self.fire_t % 1000.0,
            "uCaravan": ((now - self.caravan_t0) / self.caravan_len) if self.caravan_t0 is not None else 0.0,
            "uCaravanDir": self.caravan_dir,
        }

    def overlays(self, t: float):
        return []
