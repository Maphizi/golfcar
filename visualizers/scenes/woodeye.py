"""Das Auge des Waldes (Taste 4 im Thema THE POWER OF THE GREEN, Gegenstück zu HAL 3000).

Ein uralter Baum bei Nacht (assets/woodeye/scene.png), in der Rinde ein riesiges Auge (assets/woodeye/eyes.png,
8x3: Reihe 0 öffnet sich in 8 Schritten, Reihe 1 Irisfarben, Reihe 2 Blickrichtungen, Feuer, Spirale).
Jedes Musikmerkmal hat ein eigenes Element:
  Bass      Pupille weitet sich (Linse), die Rinde pumpt, die Kamera atmet
  Beat      Myzel in den Wurzeln als Lauflicht 1-2-3-4 (Muster wechseln), der Mond pulst
  Spektrum  acht Frösche (assets/woodeye/figures.png Reihen 0-2: sitzend, Kehlsack, Sprung) = acht Frequenzbänder,
            der dicke Ochsenfrosch links ist der Bass, die kleinen rechts die Höhen; laute Bänder springen
  Mitten    Kronendach wiegt sich, Pollen steigen
  Höhen     Glühwürmchen und Tautropfen funkeln
  Drop      Auge blinzelt und brennt, Iris wechselt die Farbe, Sporenwolke, alle Frösche springen,
            Lauflicht wechselt Richtung, Farbwelle im Myzel
  Stille    Auge schließt sich langsam, Myzel glimmt nur, Frösche schlafen
Knüppel: LINKS Fuchs tanzt (Reihe 3, Zellen 24-27), RECHTS Eule fliegt (28-31), OBEN beide, UNTEN Kaleidoskop
(Spiral-Iris, Farben kreisen). Startknopf = Froschchor (Welle durch alle Frösche). Kippschalter = Nahaufnahme ins Auge.
"""
from __future__ import annotations

import logging
import math
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("woodeye")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "woodeye"
# Frösche: (x, y, Größe) im Bild (Anteile, y von unten); Band 0 = Bass (links, groß) .. Band 7 = Höhen (rechts, klein)
FROGS = [(0.095, 0.335, 0.135), (0.157, 0.150, 0.105), (0.287, 0.150, 0.100), (0.428, 0.150, 0.095),
         (0.571, 0.150, 0.090), (0.712, 0.150, 0.085), (0.849, 0.150, 0.080), (0.935, 0.270, 0.075)]
EYE_OPEN, EYE_LEFT, EYE_RIGHT, EYE_UP, EYE_DOWN, EYE_FIRE, EYE_SPIRAL = 7, 16, 18, 19, 20, 22, 23
EYE_COLORS = list(range(8, 16))
FOX_CELLS, OWL_CELLS = (24, 25, 26, 27), (28, 29, 30, 31)
FIG_NONE, FIG_FOX, FIG_OWL, FIG_BOTH = 0, 1, 2, 3
CHORUS_SECONDS = 4.0
SPORE_SECONDS = 4.0


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
        self.eyes = _load_rgba(ASSETS / "eyes.png")
        self.figs = _load_rgba(ASSETS / "figures.png")
        self.eye = tuple(float(v) for v in scene_cfg.get("eye", [0.511, 0.722, 0.175]))     # x, y, Breite
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.bands = [0.0] * 8
        self.jump_t0 = [-10.0] * 8
        self.jump_arm = [True] * 8
        # Beat-Zähler / Lauflicht
        self.step = 0
        self.step_t0 = 0.0
        self.step_dir = 1
        self.pattern = 0
        self.pattern_next = time.monotonic() + self.rng.uniform(25.0, 45.0)
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        # Drop
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.spore_t0 = -100.0
        # Auge
        self.open = 0.0
        self.blink_t0 = -10.0
        self.blink_next = time.monotonic() + self.rng.uniform(5.0, 12.0)
        self.look = EYE_OPEN
        self.look_prev = EYE_OPEN
        self.look_t0 = 0.0
        self.gaze_until = 0.0
        self.gaze_next = time.monotonic() + self.rng.uniform(4.0, 9.0)
        self.color_until = -1.0
        self.color_cell = EYE_COLORS[0]
        self.fire_until = -1.0
        # Figuren
        self.fig = FIG_NONE
        self.fox_pose = 0
        self.fox_prev = 0
        self.fox_t0 = 0.0
        self.owl_t = 0.0
        self.flap_t = 0.0
        self.kaleido = 0.0
        self.kaleido_on = False
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.chorus_t0 = -100.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 4.0
        log.info("Auge des Waldes: Szene %s, Augen %s, Figuren %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.eyes is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def set_fig(self, which: int) -> None:
        self.fig = FIG_NONE if self.fig == which else which
        now = time.monotonic()
        if self.fig == FIG_NONE:
            wled.apply_mode_async("woodeye")
            self.led_back_at = None
            return
        profile = {FIG_FOX: "woodeye_fox", FIG_OWL: "woodeye_owl", FIG_BOTH: "woodeye_both"}[self.fig]
        self._led_event(profile, now + 6.0)
        log.info("Figur: %s", {FIG_FOX: "Fuchs", FIG_OWL: "Eule", FIG_BOTH: "Fuchs und Eule"}[self.fig])

    def toggle_kaleido(self) -> None:
        self.kaleido_on = not self.kaleido_on
        self._set_look(EYE_SPIRAL if self.kaleido_on else EYE_OPEN)
        log.info("Kaleidoskop %s", "an" if self.kaleido_on else "aus")

    def chorus(self) -> None:
        now = time.monotonic()
        if now - self.chorus_t0 < CHORUS_SECONDS:
            return
        self.chorus_t0 = now
        for i in range(8):
            self.jump_t0[i] = now + 0.6 + i * 0.18
        self._led_event("woodeye_chorus", now + CHORUS_SECONDS)
        log.info("Froschchor")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _set_look(self, cell: int) -> None:
        if cell == self.look:
            return
        self.look_prev = self.look
        self.look = cell
        self.look_t0 = time.monotonic()

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.spore_t0 = now
        self.blink_t0 = now
        self.step_dir = -self.step_dir
        self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
        self.pattern_next = now + self.rng.uniform(25.0, 45.0)
        self.fire_until = now + 1.4
        self.color_cell = self.rng.choice([c for c in EYE_COLORS if c != self.color_cell])
        self.color_until = now + 7.0
        for i in range(8):
            self.jump_t0[i] = now + 0.05 * i
        log.info("Drop: Auge brennt, Sporen, Frösche springen")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.set_fig(FIG_FOX)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.set_fig(FIG_OWL)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.set_fig(FIG_BOTH)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_kaleido()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.chorus()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uEyeTex": (self.eyes if self.eyes is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uEyeTex", "uFigTex", "uSceneSize", "uEyeSize", "uFigSize", "uSeed", "uEyePos",
                 "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uStep", "uStepPhase", "uPattern",
                 "uFlash", "uSporeT", "uZoom", "uKaleido", "uChorusT", "uBlink", "uEyeA", "uEyeB", "uEyeMix",
                 "uFig", "uOwl", "uBands0", "uBands1", "uHueT"]
        names += [f"uFrog{i}" for i in range(8)]
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
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.15)
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.35)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.12)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        # Spektrum -> acht Bänder (Frösche), schneller Anstieg, langsames Abklingen
        spec = getattr(f, "spectrum", None)
        if spec is not None and len(spec) >= 8 and live:
            n = len(spec) // 8
            for i in range(8):
                v = float(np.mean(spec[i * n:(i + 1) * n]))
                v = min(1.0, v * (1.15 + 0.1 * i))
                rate = 0.05 if v > self.bands[i] else 0.3
                self.bands[i] += (v - self.bands[i]) * min(1.0, dt / rate)
                if v > 0.78 and self.jump_arm[i] and now - self.jump_t0[i] > 0.7:
                    self.jump_t0[i] = now
                    self.jump_arm[i] = False
                if v < 0.5:
                    self.jump_arm[i] = True
        else:
            for i in range(8):
                self.bands[i] += (0.0 - self.bands[i]) * min(1.0, dt / 0.6)
        # Beat: Lauflicht einen Schritt weiter, Puls
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.step = (self.step + self.step_dir) % 4
            self.step_t0 = now
            self.beat_pulse = 1.0
            self.flap_t += 1.0
            if self.fig in (FIG_FOX, FIG_BOTH):
                self.fox_prev, self.fox_pose, self.fox_t0 = self.fox_pose, self.step, now
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        if now >= self.pattern_next:
            self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
            self.pattern_next = now + self.rng.uniform(25.0, 45.0)
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
        # Auge: öffnet sich mit Musik, schließt sich in der Stille; Blinzeln; Blick folgt dem lautesten Frosch
        target = 1.0 if self.live_s > 0.3 else 0.0
        self.open += (target - self.open) * min(1.0, dt / (0.6 if target > self.open else 2.5))
        if now >= self.blink_next:
            self.blink_t0 = now
            self.blink_next = now + self.rng.uniform(5.0, 12.0)
        bl = (now - self.blink_t0) / 0.32
        blink = 1.0 - math.sin(min(1.0, bl) * math.pi) if 0.0 <= bl < 1.0 else 1.0
        openness = max(0.0, min(1.0, self.open * blink))
        if self.kaleido_on:
            self._set_look(EYE_SPIRAL)
        elif now < self.fire_until:
            self._set_look(EYE_FIRE)
        else:
            loud = max(range(8), key=lambda i: self.bands[i])
            if self.bands[loud] > 0.72 and now > self.gaze_until - 0.6:
                self._set_look(EYE_LEFT if loud <= 2 else (EYE_RIGHT if loud >= 5 else EYE_DOWN))
                self.gaze_until = now + 1.2
            elif now >= self.gaze_next:
                self._set_look(self.rng.choice((EYE_LEFT, EYE_RIGHT, EYE_UP, EYE_DOWN)))
                self.gaze_until = now + self.rng.uniform(1.0, 2.0)
                self.gaze_next = now + self.rng.uniform(4.0, 9.0)
            elif now >= self.gaze_until:
                self._set_look(self.color_cell if now < self.color_until else EYE_OPEN)
        look_mix = min(1.0, (now - self.look_t0) / 0.25)
        # Figuren, Kaleidoskop, Zoom, Eule
        self.owl_t += dt * (0.12 + 0.25 * self.energy + 0.1 * self.bass_s)
        self.flap_t += dt * (1.5 + 5.0 * self.bass_s)
        self.kaleido += ((1.0 if self.kaleido_on else 0.0) - self.kaleido) * min(1.0, dt / 1.2)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("woodeye")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("fox", "owl", "both", "kaleido", "chorus", "drop"))
            {"fox": lambda: self.set_fig(FIG_FOX), "owl": lambda: self.set_fig(FIG_OWL), "both": lambda: self.set_fig(FIG_BOTH),
             "kaleido": self.toggle_kaleido, "chorus": self.chorus, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 9.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        fox_mix = min(1.0, (now - self.fox_t0) / 0.12)
        flap = self.flap_t % 4.0
        out = {
            "uSceneSize": size(self.scene), "uEyeSize": size(self.eyes), "uFigSize": size(self.figs), "uSeed": self.seed,
            "uEyePos": self.eye, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uStep": float(self.step),
            "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern), "uFlash": self.flash,
            "uSporeT": (now - self.spore_t0) if now - self.spore_t0 < SPORE_SECONDS else -1.0, "uZoom": self.zoom,
            "uKaleido": self.kaleido, "uChorusT": (now - self.chorus_t0) if now - self.chorus_t0 < CHORUS_SECONDS else -1.0,
            "uBlink": openness, "uEyeA": float(self.look_prev), "uEyeB": float(self.look), "uEyeMix": look_mix,
            "uFig": (float(self.fig), float(FOX_CELLS[self.fox_prev]), float(FOX_CELLS[self.fox_pose]), fox_mix),
            "uOwl": (self.owl_t % 1000.0, float(OWL_CELLS[int(flap) % 4]), float(OWL_CELLS[(int(flap) + 1) % 4]), flap - int(flap)),
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]), "uHueT": (t * 0.15) % 1000.0,
        }
        for i, (x, y, s) in enumerate(FROGS):
            jt = now - self.jump_t0[i]
            hop = jt / 0.55 if 0.0 <= jt < 0.55 else -1.0
            out[f"uFrog{i}"] = (x, y, s, hop)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if now - self.chorus_t0 < CHORUS_SECONDS:
            a = min(1.0, (now - self.chorus_t0) / 0.4) * min(1.0, (CHORUS_SECONDS - (now - self.chorus_t0)) / 0.8)
            out.append(("F R O S C H C H O R", 0.035, 0.5, 0.5, (200, 255, 210), 0.8 * a))
        if now - self.spore_t0 < 2.5:
            a = min(1.0, (2.5 - (now - self.spore_t0)) / 0.8)
            out.append(("D E R   W A L D   E R W A C H T", 0.03, 0.5, 0.08, (180, 255, 220), 0.7 * a))
        if self.fig != FIG_NONE:
            label = {FIG_FOX: "DER FUCHS TANZT", FIG_OWL: "DIE EULE KREIST", FIG_BOTH: "FUCHS UND EULE"}[self.fig]
            out.append((label, 0.018, 0.5, 0.05, (190, 220, 200), 0.55))
        return out
