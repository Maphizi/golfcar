"""Startbildschirm (Modus "boot"): das Titelbild "Marcs Taxi to Madness" bildfüllend, lebendig zur Musik, daneben ein
leuchtender Knopf "READY TO LIFT OFF". Bleibt stehen, bis der erste Knopf gedrückt wird: jede Taste (Startknopf, Knüppel,
Kippschalter) beendet die Szene, der Launcher startet danach den Taxistand; die Board-Tasten wechseln direkt den Modus.
Bild: assets/splash/scene.png (3:2, wird auf 16:9 beschnitten). Musik: Bass = Sonne und Knopf glühen, Beat = Zoom-Stoß und
Knopf hüpft, Höhen = Staub und Funken, Energie = Lichtstrahlen, Stille = ruhiges Atmen.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import images

log = logging.getLogger("splash")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "splash"
BUTTON_TEXT = "READY TO LIFT OFF"
HINT_TEXT = "STARTKNOPF DRÜCKEN"


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.plate = _load_rgba(ASSETS / str(scene_cfg.get("plate", "scene.png")))
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.sun = tuple(float(v) for v in scene_cfg.get("sun", [0.215, 0.47]))          # Sonne im Bild (Anteile, y von unten)
        self.button = tuple(float(v) for v in scene_cfg.get("button", [0.19, 0.86, 0.30, 0.10]))   # x, y Mitte, Breite, Höhe
        self.crop = tuple(float(v) for v in scene_cfg.get("crop", [0.118, 0.038]))        # Beschnitt oben, unten (Anteil des Bildes)
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.t0 = self.last
        self.bass_s = self.high_s = self.mid_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.flash = 0.0
        self.quiet_since = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.done = False
        log.info("Startbildschirm: Bild %s", "ok" if self.plate is not None else "fehlt")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN or self.done:
            return
        if ev.key == pygame.K_ESCAPE or ev.key in (0x4000006B, 0x4000006C):
            return                                            # ESC behandelt der Engine-Loop selbst; F16/F17 = Autopilot-Schalter
        self.done = True
        log.info("Erster Tastendruck: Startbildschirm endet")
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def images(self) -> dict:
        return {"uPlate": (self.plate if self.plate is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uPlate", "uPlateSize", "uPlateOK", "uSeed", "uSun", "uButton", "uCrop", "uBassS", "uMidS", "uHighS",
                "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uFlash", "uAge")

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
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.3)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.1)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
        # Drop: kurz leise, dann Schlag
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 8.0:
            self.drop_armed = False
            self.last_drop = now
            self.flash = 1.0
        self.flash = max(0.0, self.flash - dt / 1.2)
        size = (float(self.plate.shape[1]), float(self.plate.shape[0])) if self.plate is not None else (1.0, 1.0)
        return {
            "uPlateSize": size, "uPlateOK": 1.0 if self.plate is not None else 0.0, "uSeed": self.seed,
            "uSun": self.sun, "uButton": self.button, "uCrop": self.crop,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s,
            "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash,
            "uAge": now - self.t0,
        }

    def overlays(self, t: float):
        now = time.monotonic()
        bx, by, bw, bh = self.button
        # Knopf hüpft auf den Beat, Text wandert mit; Schrift glüht mit dem Bass
        bump = 0.012 * self.beat_pulse
        glow = 0.75 + 0.25 * self.bass_s + 0.1 * self.beat_pulse
        col = (255, int(235 * glow + 20), int(140 * glow + 40))
        out = [(BUTTON_TEXT, bh * 0.42, bx, by + bump, col, 0.95)]
        a = 0.35 + 0.25 * (0.5 + 0.5 * np.sin(now * 2.2))
        out.append((HINT_TEXT, 0.016, bx, by - bh * 0.78, (255, 220, 170), a))
        return out
