"""Das Orakel (Taste 4 im Thema CYBERPUNK, Gegenstück zu HAL 3000 / Auge des Waldes).

Serverhalle (assets/cyber/oracle_scene.png) mit holografischer Geisha-KI-Maske im Projektionsrahmen
(assets/cyber/oracle_mask.png, 8x3 à 192: Reihe 0 Ausdrücke 0-7, Reihe 1 Farben 8-15, Reihe 2 Glitch 16-23).
Jedes Musikmerkmal hat sein Element:
  Bass      Maske atmet, Hologramm flackert, Serverlichter glühen
  Beat      Lauflicht durch die Serverschränke 1-2-3-4 (Muster wechseln), Maske zuckt
  Spektrum  acht Neontafeln unter der Maske (assets/cyber/oracle_figures.png Reihe 2, Zellen 16-23) = acht Bänder
  Mitten    Datenregen im Hintergrund, Höhen = Funken an den Kabeln
  Drop      Maske glitcht, wechselt Ausdruck und Farbe, Datenexplosion
  Stille    Maske erlischt zum Drahtgitter
Knüppel LINKS = Samurai-Android tanzt (Reihe 0, Pose je Beat), RECHTS = Cyberkatze streift herum (Reihe 1), OBEN = beide,
UNTEN = Glitch-Modus (Bild zerfällt in Blöcke, Farbkanäle laufen auseinander). Startknopf = die Maske spricht
(Mund-Zellen 6/7, Orakelsprüche laufen durch). Kippschalter = Nahaufnahme.
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

log = logging.getLogger("oracle")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
M_NEUTRAL, M_SMILE, M_SERIOUS, M_SURPRISE, M_ANGRY, M_SLEEP, M_SPEAK, M_WIDE = range(8)
M_COLORS = list(range(8, 16))
M_GLITCH = list(range(16, 24))
M_WIRE = 18
FIG_NONE, FIG_SAMURAI, FIG_CAT, FIG_BOTH = 0, 1, 2, 3
SPEAK_SECONDS = 6.0
ORACLE_LINES = [
    "DEINE DATEN SIND SCHON VERKAUFT.", "DER REGEN HÖRT NIE AUF. DU GEWÖHNST DICH.", "ICH SEHE 4.096 VERSIONEN VON DIR.",
    "DAS TAXI FÄHRT. DAS TAXAMETER AUCH.", "FRAG NICHT NACH DEM PREIS. FRAG NACH DER WÄHRUNG.", "DU BIST OFFLINE. ICH NICHT.",
    "DIE STADT TRÄUMT IN NEON. DU BIST EIN PIXEL.", "DEIN HANDICAP IST DEM KONZERN BEKANNT.", "NOCH EIN UPDATE. DANN BIST DU FREI.",
    "DIE KATZE WEISS MEHR ALS DU.", "VERTRAU KEINEM HOLOGRAMM. AUCH MIR NICHT.", "LOCH 19 LIEGT IM SEKTOR 7.",
]


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
        self.scene = _load_rgba(ASSETS / "oracle_scene.png")
        self.masks = _load_rgba(ASSETS / "oracle_mask.png")
        self.figs = _load_rgba(ASSETS / "oracle_figures.png")
        self.frame = tuple(float(v) for v in scene_cfg.get("frame", [0.505, 0.73, 0.27]))      # x, y, Breite
        self.panels = tuple(float(v) for v in scene_cfg.get("panels", [0.264, 0.757, 0.385, 0.052]))   # x0, x7, y, Breite
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.bands = [0.0] * 8
        self.band_peak = [0.0] * 8
        self.step = 0
        self.step_t0 = 0.0
        self.step_dir = 1
        self.pattern = 0
        self.pattern_next = time.monotonic() + self.rng.uniform(25.0, 45.0)
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.burst_t0 = -100.0
        # Maske
        self.expr = M_NEUTRAL
        self.expr_prev = M_NEUTRAL
        self.expr_t0 = 0.0
        self.expr_next = time.monotonic() + self.rng.uniform(6.0, 14.0)
        self.color_cell = M_COLORS[0]
        self.color_until = -1.0
        self.glitch_cell = M_GLITCH[0]
        self.glitch_until = -1.0
        self.awake = 0.0
        self.speak_t0 = -100.0
        self.line = ""
        self.line_t0 = -10.0
        # Figuren
        self.fig = FIG_NONE
        self.sam_pose = 0
        self.sam_prev = 0
        self.sam_t0 = 0.0
        self.cat_pose = 0
        self.cat_prev = 0
        self.cat_t0 = 0.0
        self.cat_x = 0.5
        self.cat_dir = 1.0
        self.cat_next = 0.0
        self.glitch_mode = False
        self.glitch_k = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 4.0
        log.info("Das Orakel: Szene %s, Masken %s, Figuren %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.masks is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def set_fig(self, which: int) -> None:
        self.fig = FIG_NONE if self.fig == which else which
        now = time.monotonic()
        if self.fig == FIG_NONE:
            wled.apply_mode_async("oracle")
            self.led_back_at = None
            return
        self._led_event({FIG_SAMURAI: "oracle_samurai", FIG_CAT: "oracle_cat", FIG_BOTH: "oracle_both"}[self.fig], now + 6.0)
        log.info("Figur: %s", {FIG_SAMURAI: "Samurai", FIG_CAT: "Katze", FIG_BOTH: "Samurai und Katze"}[self.fig])

    def toggle_glitch(self) -> None:
        self.glitch_mode = not self.glitch_mode
        log.info("Glitch-Modus %s", "an" if self.glitch_mode else "aus")

    def speak(self) -> None:
        now = time.monotonic()
        if now - self.speak_t0 < SPEAK_SECONDS:
            return
        self.speak_t0 = now
        self.line = self.rng.choice(ORACLE_LINES)
        self.line_t0 = now + 0.4
        self._led_event("oracle_speak", now + SPEAK_SECONDS)
        log.info("Orakel: %s", self.line)

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _set_expr(self, cell: int) -> None:
        if cell == self.expr:
            return
        self.expr_prev = self.expr
        self.expr = cell
        self.expr_t0 = time.monotonic()

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.burst_t0 = now
        self.step_dir = -self.step_dir
        self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
        self.glitch_cell = self.rng.choice([c for c in M_GLITCH if c != M_WIRE])
        self.glitch_until = now + 0.9
        self.color_cell = self.rng.choice([c for c in M_COLORS if c != self.color_cell])
        self.color_until = now + 8.0
        log.info("Drop: Maske glitcht, neue Farbe")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.set_fig(FIG_SAMURAI)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.set_fig(FIG_CAT)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.set_fig(FIG_BOTH)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_glitch()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.speak()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uMaskTex": (self.masks if self.masks is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uSceneTex", "uMaskTex", "uFigTex", "uSceneSize", "uMaskSize", "uFigSize", "uSeed", "uFrame", "uPanels",
                "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uStep", "uStepPhase", "uPattern",
                "uFlash", "uBurstT", "uAwake", "uMaskA", "uMaskB", "uMaskMix", "uSpeakT", "uFig", "uSam", "uCat", "uGlitch",
                "uZoom", "uBands0", "uBands1", "uPeaks0", "uPeaks1")

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
        spec = getattr(f, "spectrum", None)
        if spec is not None and len(spec) >= 8 and live:
            n = len(spec) // 8
            for i in range(8):
                v = min(1.0, float(np.mean(spec[i * n:(i + 1) * n])) * (1.15 + 0.1 * i))
                rate = 0.04 if v > self.bands[i] else 0.25
                self.bands[i] += (v - self.bands[i]) * min(1.0, dt / rate)
                self.band_peak[i] = max(self.band_peak[i] - dt * 0.6, v if v > self.band_peak[i] else self.band_peak[i])
        else:
            for i in range(8):
                self.bands[i] += (0.0 - self.bands[i]) * min(1.0, dt / 0.6)
                self.band_peak[i] = max(0.0, self.band_peak[i] - dt * 0.6)
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            self.last_beat = now
            self.step = (self.step + self.step_dir) % 4
            self.step_t0 = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            if self.fig in (FIG_SAMURAI, FIG_BOTH):
                self.sam_prev, self.sam_pose, self.sam_t0 = self.sam_pose, (self.sam_pose + self.rng.randint(1, 3)) % 8, now
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        if now >= self.pattern_next:
            self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
            self.pattern_next = now + self.rng.uniform(25.0, 45.0)
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
        # Maske: wach mit Musik, Ausdruck wechselt gelegentlich, spricht, glitcht, Farbe nach Drop
        self.awake += ((1.0 if self.live_s > 0.3 else 0.0) - self.awake) * min(1.0, dt / (0.8 if self.live_s > 0.3 else 3.0))
        speaking = now - self.speak_t0 < SPEAK_SECONDS
        if now < self.glitch_until:
            self._set_expr(self.glitch_cell)
        elif self.awake < 0.3:
            self._set_expr(M_WIRE if self.live_s < 0.1 else M_SLEEP)
        elif speaking:
            ph = (now - self.speak_t0) * 7.0
            self._set_expr(M_SPEAK if int(ph) % 3 != 1 else M_WIDE)
        elif now < self.color_until:
            self._set_expr(self.color_cell)
        else:
            if now >= self.expr_next:
                self.expr_next = now + self.rng.uniform(6.0, 14.0)
                loud = max(self.bands)
                pick = M_ANGRY if loud > 0.85 else self.rng.choice((M_NEUTRAL, M_SMILE, M_SERIOUS, M_SURPRISE, M_NEUTRAL))
                self._set_expr(pick)
            elif self.bass_s > 0.9 and self.expr != M_SURPRISE and self.rng.random() < 0.02:
                self._set_expr(M_SURPRISE)
                self.expr_next = now + 1.5
        # Katze streift herum
        self.cat_x += dt * self.cat_dir * (0.04 + 0.06 * self.energy)
        if self.cat_x > 0.85 or self.cat_x < 0.15:
            self.cat_dir = -self.cat_dir
        if now >= self.cat_next:
            self.cat_next = now + self.rng.uniform(1.0, 3.0)
            self.cat_prev, self.cat_pose, self.cat_t0 = self.cat_pose, self.rng.randrange(8), now
            if self.cat_pose == 2 or self.cat_pose == 4:
                self.cat_dir = -self.cat_dir
        self.glitch_k += ((1.0 if self.glitch_mode else 0.0) - self.glitch_k) * min(1.0, dt / 0.6)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("oracle")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("sam", "cat", "both", "glitch", "speak", "drop"))
            {"sam": lambda: self.set_fig(FIG_SAMURAI), "cat": lambda: self.set_fig(FIG_CAT), "both": lambda: self.set_fig(FIG_BOTH),
             "glitch": self.toggle_glitch, "speak": self.speak, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 8.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        return {
            "uSceneSize": size(self.scene), "uMaskSize": size(self.masks), "uFigSize": size(self.figs), "uSeed": self.seed,
            "uFrame": self.frame, "uPanels": self.panels, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern),
            "uFlash": self.flash, "uBurstT": (now - self.burst_t0) if now - self.burst_t0 < 3.0 else -1.0, "uAwake": self.awake,
            "uMaskA": float(self.expr_prev), "uMaskB": float(self.expr), "uMaskMix": min(1.0, (now - self.expr_t0) / 0.3),
            "uSpeakT": (now - self.speak_t0) if speaking else -1.0,
            "uFig": (float(self.fig), 0.0, 0.0, 0.0),
            "uSam": (float(self.sam_prev), float(self.sam_pose), min(1.0, (now - self.sam_t0) / 0.12), 0.0),
            "uCat": (self.cat_x, float(8 + self.cat_prev), float(8 + self.cat_pose), self.cat_dir),
            "uGlitch": self.glitch_k, "uZoom": self.zoom,
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]),
            "uPeaks0": tuple(self.band_peak[0:4]), "uPeaks1": tuple(self.band_peak[4:8]),
        }

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if now - self.speak_t0 < SPEAK_SECONDS and now >= self.line_t0 and self.line:
            k = now - self.line_t0
            n = min(len(self.line), int(k * 28))
            a = min(1.0, (SPEAK_SECONDS - (now - self.speak_t0)) / 1.0)
            out.append((self.line[:n], 0.026, 0.5, 0.25, (120, 230, 255), 0.9 * a))
        if now - self.burst_t0 < 2.0:
            out.append(("D A T E N E X P L O S I O N", 0.028, 0.5, 0.06, (255, 80, 220), 0.7 * (1.0 - (now - self.burst_t0) / 2.0)))
        if self.fig != FIG_NONE:
            label = {FIG_SAMURAI: "DER SAMURAI TANZT", FIG_CAT: "DIE KATZE PATROUILLIERT", FIG_BOTH: "SAMURAI UND KATZE"}[self.fig]
            out.append((label, 0.018, 0.5, 0.04, (160, 200, 255), 0.55))
        if self.glitch_mode:
            out.append(("G L I T C H", 0.02, 0.9, 0.95, (255, 80, 220), 0.5 + 0.4 * math.sin(t * 15.0)))
        return out
