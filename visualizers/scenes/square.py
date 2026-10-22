"""Marktplatz (Taste 6 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zum Lagerfeuer / Dachterrasse).

Derselbe Marktplatz mit Rathaus und Uhrturm in vier Epochen (assets/future/square_1885|1955|1985|2015.png, je 1920x1080).
Die Stadt lebt mit der Musik: Fenster und Schilder leuchten mit dem Bass (Boden bebt leicht), jeder Beat schickt eine
Lichtwelle vom Uhrturm aus horizontal durch die Häuserzeile, Mitten = Verkehrs- und Passantenlichter am Boden, Höhen je
Epoche: Staub (1885), Regen (1955), Neon-Flackern (1985), Hologramm-Funken (2015). Drop = Blitz in den Uhrturm und
Zeitsprung in eine zufällige andere Epoche. Stille = Lichter dimmen, nur die Laternen bleiben.
Zeitsprung (Knüppel links = früher, rechts = später, sonst alle cycle_minutes von selbst): zwei Feuerspuren laufen von
links nach rechts über den Platz, Weißblitz, in der Mitte des Blitzes springt die Epoche. Teilchen je Epoche aus
assets/future/square_particles.png (8x3 à 160, echte Alpha: Reihe 0 Wilder Westen, 1 Fünfziger/Achtziger, 2 Zukunft).
OBEN = Feuerwerk (1885 Kanonenblitze, 2015 Drohnenshow, sonst bunt), UNTEN = Stromausfall (Platz geht blockweise aus und
kommt mit den Beats zurück), Startknopf = Blitz in den Turm, Kippschalter = Nahaufnahme auf das Zifferblatt.
Fehlende Epochenbilder fallen auf das nächste vorhandene zurück (Log-Hinweis).
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import images

from launcher import wled

log = logging.getLogger("square")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
YEARS = ["1885", "1955", "1985", "2015"]
ERA_LED = ["square_1885", "square_1955", "square_1985", "square_2015"]
JUMP_SECONDS = 3.0        # Dauer des Zeitsprungs (Feuerspuren, Blitz, Nachglühen)
JUMP_SWITCH = 1.1         # Sekunde im Sprung, in der die Epoche wechselt (Mitte des Weißblitzes)
JUMP_BLEND = 0.25         # Überblendung der Epochen rund um den Wechsel (Sekunden)
FIREWORK_SECONDS = 8.0
BLACKOUT_SECONDS = 14.0
LIGHTNING_SECONDS = 2.0
N_PULSES = 6


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        loaded = [_load_rgba(ASSETS / f"square_{y}.png") if (ASSETS / f"square_{y}.png").exists() else None for y in YEARS]
        have = [i for i, img in enumerate(loaded) if img is not None]
        self.eras: list[np.ndarray | None] = []
        for i, img in enumerate(loaded):
            if img is None and have:
                j = min(have, key=lambda k: (abs(k - i), -k))          # nächste vorhandene Epoche, bei Gleichstand die spätere
                log.info("Epoche %s fehlt, nehme %s", YEARS[i], YEARS[j])
                img = loaded[j]
            self.eras.append(img)
        self.particles = _load_rgba(ASSETS / "square_particles.png")
        self.cycle = max(10.0, float(scene_cfg.get("cycle_minutes", 4.0)) * 60.0)
        self.clock = tuple(float(v) for v in scene_cfg.get("clock", [0.53, 0.82]))[:2]   # Uhrturm x, y (von unten), Standard
        self.ground = float(scene_cfg.get("ground", 0.36))                              # y, bis zu der der Platz (Boden) reicht
        # je Epoche eigene Uhr-/Bodenlage (die vier Fotos sind nicht pixelgleich); fehlt der Eintrag, gilt der Standard
        clocks = scene_cfg.get("clocks", [])
        grounds = scene_cfg.get("grounds", [])
        self.clocks = [tuple(float(v) for v in clocks[i])[:2] if i < len(clocks) else self.clock for i in range(4)]
        self.grounds = [float(grounds[i]) if i < len(grounds) else self.ground for i in range(4)]
        self.era = int(scene_cfg.get("start_era", self.rng.randrange(4))) % 4
        self.era_from = self.era
        self.era_to = self.era
        self.era_t0 = -10.0
        self.next_cycle = time.monotonic() + self.cycle
        self.jump_t0 = -100.0
        self.jump_dir = 1.0
        self.jump_switched = True
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.pulses: list[float] = []
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.hue = 0.0
        self.hue_target = 0.0
        self.firework_t0 = -100.0
        self.firework_seed = 0.0
        self.blackout_t0 = -100.0
        self.blackout_beats = 0
        self.lightning_t0 = -100.0
        self.lightning_seed = 0.0
        self.traffic_t = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 4.0
        wled.apply_mode_async(ERA_LED[self.era])
        log.info("Marktplatz: Epochen %s, Teilchen %s, Start %s", " ".join(f"{y}:{'ok' if loaded[i] is not None else 'fehlt'}" for i, y in enumerate(YEARS)),
                 "ok" if self.particles is not None else "fehlt", YEARS[self.era])

    # -- Aktionen ----------------------------------------------------------
    def jump(self, target: int, direction: float = 1.0) -> None:
        """Zeitsprung in die Epoche target (0..3): Feuerspuren, Weißblitz, Wechsel in der Mitte des Blitzes."""
        now = time.monotonic()
        if now - self.jump_t0 < JUMP_SWITCH + 0.5:
            return
        target %= 4
        if target == self.era and self.jump_switched:
            return
        self.jump_t0 = now
        self.jump_dir = direction
        self.jump_switched = False
        self.era_from = self.era
        self.era_to = target
        self.next_cycle = now + self.cycle
        self._led_event("square_jump", now + 3.0)
        log.info("Zeitsprung: %s -> %s", YEARS[self.era], YEARS[target])

    def change_era(self, d: int) -> None:
        base = self.era_to if not self.jump_switched else self.era
        self.jump((base + d) % 4, float(d))

    def fireworks(self) -> None:
        now = time.monotonic()
        if now - self.firework_t0 < 2.0:
            return
        self.firework_t0 = now
        self.firework_seed = self.rng.uniform(1.0, 100.0)
        self._led_event("square_fireworks", now + FIREWORK_SECONDS)
        log.info("Feuerwerk (%s)", YEARS[self.era])

    def blackout(self) -> None:
        now = time.monotonic()
        if now - self.blackout_t0 < 3.0:
            return
        self.blackout_t0 = now
        self.blackout_beats = 0
        self._led_event("square_blackout", now + BLACKOUT_SECONDS)
        log.info("Stromausfall")

    def lightning(self) -> None:
        now = time.monotonic()
        if now - self.lightning_t0 < 0.8:
            return
        self.lightning_t0 = now
        self.lightning_seed = self.rng.uniform(1.0, 100.0)
        self._led_event("square_lightning", now + LIGHTNING_SECONDS)
        log.info("Blitz in den Uhrturm")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.lightning()
        self.hue_target = self.rng.choice([-1.2, -0.6, 0.6, 1.2])
        others = [i for i in range(4) if i != self.era]
        target = self.rng.choice(others)
        self.jump(target, 1.0 if (target - self.era) % 4 <= 2 else -1.0)
        log.info("Drop: Blitz in den Turm, Sprung nach %s", YEARS[target])

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.change_era(-1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.change_era(+1)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.fireworks()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.blackout()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.lightning()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        out = {f"uEra{i}Tex": (img if img is not None else self.blank, 1) for i, img in enumerate(self.eras)}
        out["uPartTex"] = (self.particles if self.particles is not None else self.blank, 1)
        return out

    def uniform_names(self):
        return ("uEra0Tex", "uEra1Tex", "uEra2Tex", "uEra3Tex", "uPartTex", "uEra0Size", "uEra1Size", "uEra2Size", "uEra3Size",
                "uPartSize", "uSeed", "uClock", "uGround", "uEra", "uEraA", "uEraB", "uEraMix", "uJumpT", "uJumpDir", "uBassS",
                "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uFlash", "uHue", "uFireT", "uFireSeed",
                "uBlackT", "uBlackBeats", "uLightT", "uLightSeed", "uTrafficT", "uZoom", "uPulseA", "uPulseB")

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
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.1)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            self.pulses = (self.pulses + [now])[-N_PULSES:]
            if now - self.blackout_t0 < BLACKOUT_SECONDS:
                self.blackout_beats += 1
        if not live and now - self.last_beat > 2.5:       # Stille: ab und zu eine leise Welle, damit der Platz atmet
            self.last_beat = now
            self.pulses = (self.pulses + [now])[-N_PULSES:]
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
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
        if now - self.last_drop > 14.0:
            self.hue_target = 0.0
        self.traffic_t += dt * (0.15 + 1.2 * self.mid_s + 0.4 * self.energy)
        # Zeitsprung: Wechsel der Epoche in der Mitte des Weißblitzes, Überblendung nur kurz
        jt = now - self.jump_t0
        mix = 0.0
        if jt < JUMP_SECONDS:
            mix = min(1.0, max(0.0, (jt - (JUMP_SWITCH - JUMP_BLEND * 0.5)) / JUMP_BLEND))
            if not self.jump_switched and jt >= JUMP_SWITCH:
                self.jump_switched = True
                self.era = self.era_to
                self.era_t0 = now
                wled.apply_mode_async(ERA_LED[self.era])
                self.led_back_at = None
        elif not self.jump_switched:
            self.jump_switched = True
            self.era = self.era_to
        if self.jump_switched:
            self.era_from = self.era
            mix = 0.0
        if self.jump_switched and now >= self.next_cycle and jt >= JUMP_SECONDS:
            self.jump((self.era + 1) % 4, 1.0)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async(ERA_LED[self.era])
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "fire", "black", "light", "drop", "zoom", "back"))
            {"left": lambda: self.change_era(-1), "right": lambda: self.change_era(+1), "fire": self.fireworks,
             "black": self.blackout, "light": self.lightning, "drop": lambda: self._drop(now),
             "zoom": lambda: setattr(self, "zoom_target", 1.0), "back": lambda: setattr(self, "zoom_target", 0.0)}[pick]()
            self.demo_next = now + 8.0
        self.pulses = [p for p in self.pulses if now - p < 3.0]
        ages = [max(0.0, now - p) for p in self.pulses[-N_PULSES:]]
        while len(ages) < N_PULSES:
            ages.append(99.0)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        era_f = (self.era_from + ((self.era_to - self.era_from + 2) % 4 - 2) * mix) % 4.0
        ca, cb = self.clocks[self.era_from], self.clocks[self.era_to]
        clock = (ca[0] + (cb[0] - ca[0]) * mix, ca[1] + (cb[1] - ca[1]) * mix)
        ground = self.grounds[self.era_from] + (self.grounds[self.era_to] - self.grounds[self.era_from]) * mix
        out = {
            "uPartSize": size(self.particles), "uSeed": self.seed, "uClock": clock, "uGround": ground,
            "uEra": era_f, "uEraA": float(self.era_from), "uEraB": float(self.era_to), "uEraMix": mix,
            "uJumpT": jt if jt < JUMP_SECONDS else -1.0, "uJumpDir": self.jump_dir,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash,
            "uHue": self.hue, "uFireT": (now - self.firework_t0) if now - self.firework_t0 < FIREWORK_SECONDS else -1.0,
            "uFireSeed": self.firework_seed,
            "uBlackT": (now - self.blackout_t0) if now - self.blackout_t0 < BLACKOUT_SECONDS else -1.0,
            "uBlackBeats": float(self.blackout_beats),
            "uLightT": (now - self.lightning_t0) if now - self.lightning_t0 < LIGHTNING_SECONDS else -1.0,
            "uLightSeed": self.lightning_seed, "uTrafficT": self.traffic_t % 1000.0, "uZoom": self.zoom,
            "uPulseA": tuple(ages[0:3]), "uPulseB": tuple(ages[3:6]),
        }
        for i, img in enumerate(self.eras):
            out[f"uEra{i}Size"] = size(img)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        jt = now - self.jump_t0
        big = 0.0
        if 0.0 <= jt < JUMP_SECONDS and jt >= JUMP_SWITCH:
            k = jt - JUMP_SWITCH
            big = min(1.0, k / 0.15) * min(1.0, (JUMP_SECONDS - JUMP_SWITCH - k) / 0.6)
            out.append((YEARS[self.era_to], 0.2, 0.5, 0.5, (255, 240, 200), 0.9 * big))
        if now - self.era_t0 > 2.0 or big <= 0.0:
            out.append((f"MARKTPLATZ   {YEARS[self.era]}", 0.028, 0.5, 0.93, (230, 220, 200), 0.6 * (1.0 - big)))
        lt = now - self.lightning_t0
        if 0.0 <= lt < LIGHTNING_SECONDS:
            a = min(1.0, lt / 0.1) * min(1.0, (LIGHTNING_SECONDS - lt) / 0.6)
            cx, cy = self.clocks[self.era]
            out.append(("22:04", 0.07, cx, min(0.9, cy + 0.12), (255, 255, 255), 0.95 * a))
        if now - self.blackout_t0 < BLACKOUT_SECONDS:
            k = now - self.blackout_t0
            out.append(("S T R O M A U S F A L L", 0.03, 0.5, 0.86, (255, 90, 70),
                        0.7 * min(1.0, k * 2.0) * min(1.0, (BLACKOUT_SECONDS - k) / 1.0)))
        return out
