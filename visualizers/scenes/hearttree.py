"""Der Herzbaum (Taste 6 im Thema THE POWER OF THE GREEN, Gegenstück zum Lagerfeuer).

Ein uralter Baum bei Nacht (assets/hearttree/scene.png), durch Wurzeln, Stamm und Äste laufen Adern aus leuchtendem
Saft. Der Shader erkennt die Adern im Foto (bernstein/türkis) und lässt sie pulsieren:
  Bass      Herzschlag: ein Lichtimpuls läuft von den Wurzeln durch den Stamm in die Krone, der Stamm weitet sich
  Beat      Leuchtwelle wandert durch die Adern (Tempo folgt der Musik, Richtung wechselt beim Drop)
  Mitten    das Blätterdach wiegt sich, Pollen steigen
  Höhen     Tautropfen und Glühwürmchen funkeln
  Energie   Grundglühen der Adern; Stille = langsamer Ruhepuls wie ein schlafendes Herz
  Drop      der Baum blüht auf: Blüten-/Blättersturm aus der Krone, Adernfarbe wechselt, Lichtblitz aus den Wurzeln
Jahreszeiten (Knüppel links/rechts, wandern auch von selbst über cycle_minutes): Frühling (Blüten), Sommer
(Glühwürmchen), Herbst (Laub fällt, Krone rot-gold), Winter (Schnee, Adern eisblau). Fallende Teile aus
assets/hearttree/seasons.png (8x3 à 192: Reihe 0 Frühling, 1 Herbst, 2 Winter).
OBEN = Sturm von Hand, UNTEN = Wurzeln leuchten / Myzel breitet sich aus, Startknopf = großer Herzschlag,
Kippschalter = Nahaufnahme an die Rinde.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("hearttree")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "hearttree"
SEASONS = ["FRÜHLING", "SOMMER", "HERBST", "WINTER"]
SEASON_LED = ["hearttree_spring", "hearttree_summer", "hearttree_autumn", "hearttree_winter"]
STORM_SECONDS = 7.0
ROOTS_SECONDS = 9.0
N_PULSES = 6


def _load_rgba(path) -> np.ndarray | None:
    try:
        surf = pygame.image.load(str(path))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
        try:
            alpha = pygame.surfarray.array_alpha(surf).transpose(1, 0)
        except ValueError:
            alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
        return np.ascontiguousarray(np.dstack([rgb, alpha]).astype(np.uint8)[::-1])
    except Exception as exc:
        log.warning("Bild %s nicht ladbar: %s", path, exc)
        return None


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "scene.png")
        self.sheet = _load_rgba(ASSETS / "seasons.png")
        self.trunk = tuple(float(v) for v in scene_cfg.get("trunk", [0.52, 0.42]))      # Stammmitte (Nahaufnahme, Atmen)
        self.cycle = float(scene_cfg.get("cycle_minutes", 6.0)) * 60.0                 # Minuten je Jahreszeit
        self.season = float(scene_cfg.get("start_season", self.rng.randrange(4)))
        self.season_target: float | None = None
        self.season_shown = int(self.season) % 4
        self.season_t0 = -10.0
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        self.wave_t = 0.0
        self.wave_dir = 1.0
        self.pulses: list[float] = []            # Startzeiten der Herzschläge
        self.bass_prev = 0.0
        self.last_pulse = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.hue = 0.0
        self.hue_target = 0.0
        self.storm_t0 = -100.0
        self.storm_seed = 0.0
        self.roots_t0 = -100.0
        self.bigbeat_t0 = -100.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 4.0
        wled.apply_mode_async(SEASON_LED[self.season_shown])
        log.info("Herzbaum: Szene %s, Jahreszeiten-Bogen %s, Start %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.sheet is not None else "fehlt", SEASONS[self.season_shown])

    # -- Aktionen ----------------------------------------------------------
    def change_season(self, d: int) -> None:
        cur = int(round(self.season_target if self.season_target is not None else self.season)) % 4
        self.season_target = float((cur + d) % 4)
        # kürzester Weg um den Kreis
        while self.season_target - self.season > 2.0:
            self.season_target -= 4.0
        while self.season_target - self.season < -2.0:
            self.season_target += 4.0
        log.info("Jahreszeit: %s", SEASONS[int(self.season_target) % 4])

    def storm(self, seed: float | None = None) -> None:
        now = time.monotonic()
        if now - self.storm_t0 < 2.0:
            return
        self.storm_t0 = now
        self.storm_seed = seed if seed is not None else self.rng.uniform(1.0, 100.0)
        log.info("Sturm: %s", {0: "Blüten", 1: "Pollen und Blätter", 2: "Laub", 3: "Schnee"}[int(round(self.season)) % 4])

    def roots(self) -> None:
        now = time.monotonic()
        if now - self.roots_t0 < 3.0:
            return
        self.roots_t0 = now
        self._led_event("hearttree_roots", now + ROOTS_SECONDS)
        log.info("Wurzeln leuchten, Myzel breitet sich aus")

    def big_beat(self) -> None:
        now = time.monotonic()
        if now - self.bigbeat_t0 < 1.5:
            return
        self.bigbeat_t0 = now
        self.pulses = [now - 0.0, now + 0.25, now + 0.5][-N_PULSES:]
        self._led_event("hearttree_beat", now + 2.5)
        log.info("Großer Herzschlag")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.wave_dir = -self.wave_dir
        self.hue_target = self.rng.choice([-1.2, -0.6, 0.6, 1.2, 2.0])
        self.storm_t0 = now
        self.storm_seed = self.rng.uniform(1.0, 100.0)
        self.pulses = (self.pulses + [now])[-N_PULSES:]
        log.info("Drop: der Baum blüht auf")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.change_season(-1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.change_season(+1)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.storm()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.roots()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.big_beat()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uSheetTex": (self.sheet if self.sheet is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uSheetTex", "uSceneSize", "uSheetSize", "uSeed", "uTrunk", "uSeason", "uBassS", "uMidS",
                 "uHighS", "uEnergy", "uLive", "uBeatPulse", "uWaveT", "uFlash", "uHue", "uStormT", "uStormSeed",
                 "uRootsT", "uBigBeat", "uZoom", "uPulseA", "uPulseB"]
        return tuple(names)

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        silent = bool(getattr(f, "silent", True))
        live = 0.0 if silent else 1.0
        bass = float(getattr(f, "bass", 0.0)) * live
        mid = float(getattr(f, "mid", 0.0)) * live
        high = float(getattr(f, "high", 0.0)) * live
        beat = float(getattr(f, "beat", 0.0)) * live
        rms = float(getattr(f, "rms", 0.0)) * live
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.12)
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.35)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.12)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        # Herzschlag: Bass-Anstieg oder Beat -> Lichtimpuls von den Wurzeln aufwärts
        rising = bass > 0.45 and bass > self.bass_prev + 0.12
        self.bass_prev = bass
        if (rising or beat > 0.5) and now - self.last_pulse > 0.28:
            self.last_pulse = now
            self.pulses = (self.pulses + [now])[-N_PULSES:]
        if not live and now - self.last_pulse > 2.4:          # Ruhepuls in der Stille
            self.last_pulse = now
            self.pulses = (self.pulses + [now])[-N_PULSES:]
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        self.wave_t += dt * self.wave_dir * (0.25 + 1.5 * self.bass_s + 0.5 * self.energy)
        # Drop
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 10.0:
            self.drop_armed = False
            self.last_drop = now
            self._drop(now)
        self.flash = max(0.0, self.flash - dt / 2.0)
        self.hue += (self.hue_target - self.hue) * min(1.0, dt / 1.5)
        if now - self.last_drop > 14.0 and abs(self.hue_target) > 0.0:
            self.hue_target = 0.0                                # Adern finden zu ihrer Farbe zurück
        # Jahreszeit: von selbst langsam weiter, per Knüppel schnell zum Ziel
        if self.season_target is not None:
            self.season += (self.season_target - self.season) * min(1.0, dt / 1.2)
            if abs(self.season_target - self.season) < 0.01:
                self.season = self.season_target
                self.season_target = None
        else:
            self.season += dt / self.cycle
        self.season %= 4.0
        shown = int(round(self.season)) % 4
        if shown != self.season_shown:
            self.season_shown = shown
            self.season_t0 = now
            wled.apply_mode_async(SEASON_LED[shown])
            self.led_back_at = None
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async(SEASON_LED[self.season_shown])
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "storm", "roots", "beat", "drop"))
            {"left": lambda: self.change_season(-1), "right": lambda: self.change_season(+1), "storm": self.storm,
             "roots": self.roots, "beat": self.big_beat, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 8.0
        self.pulses = [p for p in self.pulses if now - p < 3.0]
        ages = [max(0.0, now - p) for p in self.pulses[-N_PULSES:]]
        while len(ages) < N_PULSES:
            ages.append(99.0)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        return {
            "uSceneSize": size(self.scene), "uSheetSize": size(self.sheet), "uSeed": self.seed, "uTrunk": self.trunk,
            "uSeason": self.season, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uWaveT": self.wave_t % 1000.0,
            "uFlash": self.flash, "uHue": self.hue,
            "uStormT": (now - self.storm_t0) if now - self.storm_t0 < STORM_SECONDS else -1.0, "uStormSeed": self.storm_seed,
            "uRootsT": (now - self.roots_t0) if now - self.roots_t0 < ROOTS_SECONDS else -1.0,
            "uBigBeat": (now - self.bigbeat_t0) if now - self.bigbeat_t0 < 2.5 else -1.0, "uZoom": self.zoom,
            "uPulseA": tuple(ages[0:3]), "uPulseB": tuple(ages[3:6]),
        }

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if now - self.season_t0 < 2.5:
            a = min(1.0, (now - self.season_t0) / 0.4) * min(1.0, (2.5 - (now - self.season_t0)) / 0.8)
            out.append((SEASONS[self.season_shown], 0.04, 0.5, 0.5, (230, 245, 220), 0.8 * a))
        if now - self.bigbeat_t0 < 1.5:
            a = min(1.0, (1.5 - (now - self.bigbeat_t0)) / 0.6)
            out.append(("H E R Z S C H L A G", 0.03, 0.5, 0.08, (255, 210, 120), 0.7 * a))
        return out
