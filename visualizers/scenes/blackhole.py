"""Schwarzes Loch (Taste 3): Szenen-Controller. Glättet die Musik zu Hüllkurven, die der Shader
nicht selbst halten kann (Jet-Ausbruch nach dem Beat, Flare, Kamerawackeln), würfelt pro Start
Blickwinkel, Scheibenfarbe und Orbitdrehung und lässt die Kamera langsam kreisen.

Steuerknüppel LINKS/RECHTS/OBEN/UNTEN = einen Planeten aus dem Katalog (config/planets.toml) von
dieser Bildseite ins Loch werfen. Er wird über rund eine Minute eingezogen, dabei zu einem immer
längeren Band gestreckt (Spaghettisierung), das sich schlangenförmig zur Musik windet, und verglüht
am Horizont. Zwei Planeten können gleichzeitig unterwegs sein.
Start (ENTER) = Jet zünden, Kippschalter AN (SPACE) = Nahaufnahme, AUS (BACKSPACE) = zurück.
"""
from __future__ import annotations

import logging
import math
import random
import time

import pygame

from launcher import config as lcfg

log = logging.getLogger("blackhole")

TYPES = ["desert", "ice", "forest", "ocean", "city", "volcanic", "gas", "swamp", "grass", "rock", "crystal", "star", "comet", "station"]
SLOTS = 2
THROW_SECONDS = (50.0, 70.0)        # Dauer vom Bildrand bis zum Verschwinden: sehr langsam


class Throw:
    def __init__(self, rng: random.Random, planet: dict, side: str, now: float, aspect: float):
        self.planet = planet
        self.t0 = now
        self.dur = rng.uniform(*THROW_SECONDS)
        off = rng.uniform(-0.28, 0.28)
        # Startpunkt in Bildkoordinaten (Mitte 0/0, Breite ±aspect/2, Höhe ±0.5), knapp innerhalb des Rands,
        # damit der Planet erst als Kugel zu sehen ist, bevor er gestreckt wird
        if side == "left":
            self.pos = (-aspect * 0.5 + 0.14, off)
        elif side == "right":
            self.pos = (aspect * 0.5 - 0.14, off)
        elif side == "up":
            self.pos = (off * aspect, 0.38)
        else:
            self.pos = (off * aspect, -0.38)
        self.swirl = rng.choice((-1.0, 1.0)) * rng.uniform(1.6, 2.8)     # Spiralrichtung und -stärke
        self.seed = rng.uniform(1.0, 200.0)
        self.size = float(planet.get("size", 1.0)) * 0.075
        self.rings = 1.0 if planet.get("rings") else 0.0
        self.type = float(TYPES.index(planet.get("type", "rock")) if planet.get("type", "rock") in TYPES else 9)
        self.col_a = tuple(planet.get("color_a", [0.5, 0.5, 0.5]))
        self.col_b = tuple(planet.get("color_b", [0.3, 0.3, 0.3]))
        self.name = str(planet.get("name", "?")).upper()

    def progress(self, now: float) -> float:
        return (now - self.t0) / self.dur

    def done(self, now: float) -> bool:
        return self.progress(now) >= 1.0


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.seed = self.rng.uniform(1.0, 500.0)
        self.tilt = self.rng.uniform(0.12, 0.32)           # Neigung der Scheibe zur Blickrichtung (rad)
        self.orbit_speed = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(0.02, 0.035)
        self.angle = self.rng.uniform(0.0, 6.28)
        self.palette = self.rng.randrange(3)                # 0 orange/weiß, 1 blau/violett, 2 gold/rot
        self.jet = 0.0
        self.flare = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.last = time.monotonic()
        self.last_beat_at = 0.0
        self.bass_s = 0.0
        self.mid_s = 0.0
        self.snake_t = 0.0                                  # langsame Zeit für die Schlangenwellen
        self.aspect = 16.0 / 9.0
        self.throws: list[Throw | None] = [None] * SLOTS
        self.last_names: list[str] = []
        self.demo_next = time.monotonic() + 4.0
        try:
            self.planets = [p for p in lcfg._load("planets.toml").get("planets", []) if p.get("name")]
        except Exception as exc:                            # pragma: no cover
            log.warning("planets.toml: %s", exc)
            self.planets = []
        if not self.planets:
            self.planets = [{"name": "UNBEKANNT", "type": "rock", "color_a": [0.5] * 3, "color_b": [0.3] * 3}]
        log.info("Schwarzes Loch: Palette %d, Neigung %.2f, Orbit %.3f, %d Planeten im Katalog",
                 self.palette, self.tilt, self.orbit_speed, len(self.planets))

    # ---- Werfen
    def throw(self, side: str) -> None:
        now = time.monotonic()
        slot = next((i for i, th in enumerate(self.throws) if th is None), None)
        if slot is None:
            # beide Bahnen belegt: den weiter fortgeschrittenen ersetzen (er ist ohnehin fast weg)
            slot = max(range(SLOTS), key=lambda i: self.throws[i].progress(now))
            if self.throws[slot].progress(now) < 0.6:
                return
        active = {th.name for th in self.throws if th}
        pool = [p for p in self.planets if str(p.get("name", "")).upper() not in active and p.get("name") not in self.last_names[-6:]]
        planet = self.rng.choice(pool or self.planets)
        self.last_names.append(planet.get("name"))
        self.throws[slot] = Throw(self.rng, planet, side, now, self.aspect)
        log.info("Planet geworfen: %s von %s (%.0f s)", self.throws[slot].name, side, self.throws[slot].dur)

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.throw("left")
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.throw("right")
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.throw("up")
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.throw("down")
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.jet = 1.0
            self.flare = 1.0
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    def uniform_names(self):
        names = ["uSeed", "uTilt", "uAngle", "uPalette", "uJet", "uFlare", "uZoom", "uBassS", "uMidS", "uSnakeT"]
        for i in range(SLOTS):
            names += [f"uThrow{i}", f"uThrowPos{i}", f"uThrowColA{i}", f"uThrowColB{i}", f"uThrowPar{i}", f"uThrowPar2{i}"]
        return tuple(names)

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        beat = float(getattr(f, "beat", 0.0))
        bass = float(getattr(f, "bass", 0.0))
        mid = float(getattr(f, "mid", 0.0))
        silent = bool(getattr(f, "silent", True))
        # Jet: starker Beat zündet ihn, dann klingt er über ~3 s ab; Flare kürzer
        if beat > 0.6 and now - self.last_beat_at > 0.35 and not silent:
            self.jet = min(1.0, self.jet + 0.5 + 0.5 * beat)
            self.flare = 1.0
            self.last_beat_at = now
        self.jet = max(0.0, self.jet - dt / 3.0)
        self.flare = max(0.0, self.flare - dt / 0.5)
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.15)
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.4)
        # Schlangenzeit: läuft langsam, mit Bass etwas schneller (bei Stille ganz langsam weiter)
        self.snake_t += dt * (0.25 + 0.9 * self.bass_s * (0.0 if silent else 1.0))
        self.angle += dt * self.orbit_speed * (1.0 + 0.6 * self.bass_s)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 2.0)
        if self.demo and now >= self.demo_next:
            self.jet, self.flare = 1.0, 1.0
            self.throw(self.rng.choice(("left", "right", "up", "down")))
            self.demo_next = now + 12.0
        out = {"uSeed": self.seed, "uTilt": self.tilt, "uAngle": self.angle, "uPalette": float(self.palette),
               "uJet": self.jet, "uFlare": self.flare, "uZoom": self.zoom, "uBassS": self.bass_s,
               "uMidS": self.mid_s, "uSnakeT": self.snake_t % 1000.0}
        for i, th in enumerate(self.throws):
            if th is not None and th.done(now):
                log.info("%s ist im Loch verschwunden", th.name)
                self.throws[i] = th = None
            if th is None:
                out[f"uThrow{i}"] = 0.0
                out[f"uThrowPos{i}"] = (0.0, 0.0)
                out[f"uThrowColA{i}"] = (0.0, 0.0, 0.0)
                out[f"uThrowColB{i}"] = (0.0, 0.0, 0.0)
                out[f"uThrowPar{i}"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uThrowPar2{i}"] = (0.0, 0.0, 0.0, 0.0)
            else:
                out[f"uThrow{i}"] = max(0.0, min(1.0, th.progress(now)))
                out[f"uThrowPos{i}"] = th.pos
                out[f"uThrowColA{i}"] = th.col_a
                out[f"uThrowColB{i}"] = th.col_b
                out[f"uThrowPar{i}"] = (th.size, th.type, th.seed, th.swirl)
                out[f"uThrowPar2{i}"] = (th.rings, 0.0, 0.0, 0.0)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        y = 0.05
        for th in self.throws:
            if th is None:
                continue
            p = th.progress(now)
            a = 0.75 * min(1.0, p * 8.0) * min(1.0, (1.0 - p) * 6.0)
            label = f"{th.name}  -  WIRD ZERRISSEN" if p > 0.55 else f"{th.name}  -  FÄLLT"
            out.append((label, 0.018, 0.5, y, (255, 170, 120), a))
            y += 0.035
        return out
