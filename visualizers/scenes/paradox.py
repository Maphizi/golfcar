"""Paradoxon (Taste 7 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zum Systemfehler / zur Überdosis / zu Black Ice).

Die Zeitlinie bricht. Erfinderwerkstatt bei Nacht (assets/future/paradox_scene.png) in Wellen, die sich wiederholen:
  STÖRUNG (10 s)        "ZEITKREISE DEFEKT", die Anzeigen rattern (Datumsziffern in Rot/Grün/Gelb), der Puls steigt
  PARADOXON (30 s)      Doppelbilder, Farben kippen in Sepia und Blitzblau, Anachronismen (assets/future/paradox_intruders.png,
                        4x3 à 256) lauern an den Rändern und springen auf jeden Beat, Filmkorn, die eigene Hand unten im
                        Bild wird durchsichtig
  1,21 GIGAWATT (20 s)  Blitze überall, Negativ-Blitze und Bildsprünge auf den Beat, das Fahrerfoto auf dem Polaroid
                        (assets/taxi/future/driver.png) verblasst Stück für Stück, Flüstertexte
  AUSLÖSCHUNG (8 s)     Schwarz mit Filmriss und Brandloch, Sepia-Nachbilder, dann "ZEITLINIE WIEDERHERGESTELLT. NOCH EINMAL."
Bass = Herzschlag (Bild pumpt), Beat = Bildsprung und Negativflackern, Höhen = Filmkorn und Staubfäden, Mitten verbiegen die
Ränder, Drop = Blitz und alle Anachronismen springen. Stille = schweres Atmen, Sepia kriecht.
Knüppel links/rechts = Gegenmaßnahme (Zeitkreise reset, Almanach verbrennen, Brief an den Professor, Blitzableiter, 88 mph):
kurz besser (das Foto kehrt zurück), Rückfall nach 4 s. Oben = Zeitkreise neu starten (Bild rollt, Ziffern rattern).
Unten = Foto ansehen (Dunkel, nur das Foto groß in der Mitte, atmet und verblasst; nochmal = zurück).
Startknopf = der Professor kommt mit der Zeitmaschine (assets/future/clocktower_figures.png, 8x3 à 192: Reihe 0 Professor,
Reihe 1 Zeitmaschine; fehlt der Bogen, nur Feuerspuren und klares Bild; Test: KITT_PARADOX_FIGURES=<png>).
Kippschalter AN = zurück in 1985 (klar, kalt, Sepia weg), AUS = Rückfall.
"""
from __future__ import annotations

import logging
import math
import os
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import images

from launcher import wled

log = logging.getLogger("paradox")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
TAXI_ASSETS = ASSETS.parent / "taxi" / "future"
PH_WARN, PH_POISON, PH_HORROR, PH_BLACKOUT = 0, 1, 2, 3
PHASE_LEN = {PH_WARN: 10.0, PH_POISON: 30.0, PH_HORROR: 20.0, PH_BLACKOUT: 8.0}
PHASE_NAMES = {PH_WARN: "STÖRUNG", PH_POISON: "PARADOXON", PH_HORROR: "1,21 GIGAWATT", PH_BLACKOUT: "AUSLÖSCHUNG"}
N_CRE = 5
N_CELLS = 12
WHISPERS = [
    "DU LÖSCHST DICH AUS.", "DEINE ELTERN HABEN SICH NIE GETROFFEN.", "DER ALMANACH IST BEI BIFF.", "ZWEIUNDZWANZIG UHR VIER.",
    "ACHTUNDACHTZIG MEILEN REICHEN NICHT.", "DAS FOTO WIRD LEER.", "DU WARST NIE HIER.", "WER FÄHRT DEN WAGEN, WENN ES DICH NICHT GIBT?",
    "DIE UHR STEHT SEIT 1955.", "1,21 GIGAWATT. UND KEIN BLITZ.", "DER BRIEF KAM NIE AN.", "ES GIBT KEIN ZURÜCK, NUR VORBEI.",
]
ANTIDOTES = ["ZEITKREISE RESET", "ALMANACH VERBRENNEN", "BRIEF AN DEN PROFESSOR", "BLITZABLEITER", "88 MPH"]
MONTHS = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"]
DATE_LABELS = ("ZIELZEIT", "GEGENWART", "LETZTE ZEIT")
DATE_COLORS = ((255, 70, 50), (70, 255, 90), (255, 215, 60))
PROF_WAVE, PROF_CHEER, PROF_POINT = 6, 3, 2                                   # Reihe 0: Professor-Posen
CAR_CELLS = (8, 9, 10, 11, 12, 13)                                             # Reihe 1: Zeitmaschine fährt
CAR_FIRE = (14, 15)                                                            # ... mit Feuerspuren
PHOTO_DEFAULT = (0.364, 0.204, 0.12)                                            # Polaroid: Mitte x, y (von unten), Breite
HAND_DEFAULT = (0.80, 0.07, 0.11)                                               # durchsichtige Hand: x, y, Größe


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


def _load_photo(path, size: int = 512) -> np.ndarray | None:
    """Fahrerfoto verkleinert laden (auf dem Polaroid ist es klein, sonst flimmert es)."""
    try:
        surf = pygame.image.load(str(path))
        if max(surf.get_size()) > size:
            surf = pygame.transform.smoothscale(surf.convert(24) if surf.get_bitsize() < 24 else surf, (size, size))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
        return np.ascontiguousarray(np.dstack([rgb, alpha]).astype(np.uint8)[::-1])
    except Exception as exc:
        log.warning("Foto %s nicht ladbar: %s", path, exc)
        return None


def _triple(value, default) -> tuple[float, float, float]:
    try:
        vals = [float(v) for v in value]
        if len(vals) == 3:
            return vals[0], vals[1], vals[2]
    except (TypeError, ValueError):
        pass
    return default


class Creature:
    """Ein Anachronismus lauert am Rand, rückt näher, springt auf den Beat."""

    def __init__(self, rng: random.Random, now: float, horror: bool, cell: int | None = None):
        self.cell = rng.randrange(N_CELLS) if cell is None else cell
        side = rng.choice((-1.0, 1.0))
        self.x = 0.5 + side * rng.uniform(0.28, 0.46)
        self.y = rng.uniform(0.2, 0.7)
        self.t0 = now
        self.life = rng.uniform(6.0, 12.0) if not horror else rng.uniform(3.0, 6.0)
        self.size = rng.uniform(0.14, 0.24) * (1.4 if horror else 1.0)
        self.approach = rng.uniform(0.3, 0.8) * (2.0 if horror else 1.0)
        self.hue = rng.uniform(0.0, 6.28)
        self.lunge_t0 = -10.0
        self.mirror = rng.random() < 0.5
        self.seed = rng.random()

    def age(self, now: float) -> float:
        return now - self.t0

    def done(self, now: float) -> bool:
        return now - self.t0 > self.life


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "paradox_scene.png")
        self.creatures_tex = _load_rgba(ASSETS / "paradox_intruders.png")
        self.photo = _load_photo(TAXI_ASSETS / "driver.png") if (TAXI_ASSETS / "driver.png").exists() else None
        fig_path = Path(os.environ.get("KITT_PARADOX_FIGURES", "") or (ASSETS / "clocktower_figures.png"))
        if not fig_path.is_absolute():
            fig_path = ASSETS.parents[1] / fig_path
        self.figs = _load_rgba(fig_path) if fig_path.exists() else None
        self.photo_cfg = _triple(scene_cfg.get("photo"), PHOTO_DEFAULT)
        self.hand_cfg = _triple(scene_cfg.get("hand"), HAND_DEFAULT)
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.phase = PH_WARN
        self.phase_t0 = self.last
        self.wave = 0
        self.poison = 0.0
        self.fade = 0.0
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.cut = (0.0, 0.0)
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.bolt_t0 = -10.0
        self.bolt = (0.5, 0.0, 0.0)                                            # x, Seed, Stärke
        self.relief = 0.0
        self.relief_label = ""
        self.relief_t0 = -10.0
        self.relapse_at: float | None = None
        self.reboot_t0 = -10.0
        self.photo_view_on = False
        self.photo_view = 0.0
        self.help_t0 = -10.0
        self.shock = 0.0
        self.shock_on = False
        self.shock_t0 = -10.0
        self.creatures: list[Creature] = []
        self.next_spawn = self.last + 3.0
        self.whisper = ""
        self.whisper_t0 = -10.0
        self.next_whisper = 0.0
        self.rattle_t = 0.0
        self.rattle_lines = [self._rattle_line(i) for i in range(3)]
        self.car_t = 0.0
        self.led_back_at: float | None = None
        self.demo_next = self.last + 5.0
        log.info("Paradoxon: Szene %s, Anachronismen %s, Foto %s, Figuren %s (%s)", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.creatures_tex is not None else "fehlt", "ok" if self.photo is not None else "fehlt",
                 "ok" if self.figs is not None else "fehlt", fig_path)

    # -- Aktionen ----------------------------------------------------------
    def antidote(self) -> None:
        now = time.monotonic()
        if now - self.relief_t0 < 1.5:
            return
        self.relief_t0 = now
        self.relief = 1.0
        self.relief_label = self.rng.choice(ANTIDOTES)
        self.relapse_at = now + 4.0
        self.fade = max(0.0, self.fade - 0.35)                                 # das Foto kehrt zurück
        log.info("Gegenmaßnahme: %s (hilft kurz)", self.relief_label)

    def reboot(self) -> None:
        now = time.monotonic()
        if now - self.reboot_t0 < 3.5:
            return
        self.reboot_t0 = now
        self.poison = max(0.0, self.poison - 0.15)
        log.info("Zeitkreise neu starten")

    def toggle_photo_view(self) -> None:
        self.photo_view_on = not self.photo_view_on
        log.info("Foto %s", "ansehen" if self.photo_view_on else "weglegen")

    def call_help(self) -> None:
        now = time.monotonic()
        if now - self.help_t0 < 6.0:
            return
        self.help_t0 = now
        self.fade = max(0.0, self.fade - 0.3)
        self._led_event("paradox_help", now + 5.0)
        log.info("Hilfe: der Professor kommt mit der Zeitmaschine")

    def set_shock(self, on: bool) -> None:
        if on == self.shock_on:
            return
        self.shock_on = on
        self.shock_t0 = time.monotonic()
        if not on:
            self.poison = min(1.0, self.poison + 0.2)                      # Rückfall
            self.fade = min(1.0, self.fade + 0.2)
        log.info("Zurück in 1985 %s", "an" if on else "aus, Rückfall")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _bolt(self, now: float, strength: float) -> None:
        self.bolt_t0 = now
        self.bolt = (self.rng.uniform(0.1, 0.9), self.rng.uniform(0.0, 100.0), strength)

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self._bolt(now, 1.6)
        self.creatures = [Creature(self.rng, now, True, cell=c) for c in self.rng.sample(range(N_CELLS), N_CRE)]
        for c in self.creatures:
            c.size *= 1.3
            c.lunge_t0 = now
        self.poison = min(1.0, self.poison + 0.1)
        self.fade = min(1.0, self.fade + 0.08)
        self._led_event("paradox_drop", now + 2.0)
        log.info("Drop: Blitz, alle Anachronismen springen")

    def _set_phase(self, ph: int, now: float) -> None:
        self.phase = ph
        self.phase_t0 = now
        if ph == PH_WARN:
            self.wave += 1
            self.seed = self.rng.uniform(1.0, 100.0)
            self.creatures = []
            self.fade = 0.0                                                   # Zeitlinie wiederhergestellt
            wled.apply_mode_async("paradox")
        elif ph == PH_HORROR:
            self.next_whisper = now + 1.0
            wled.apply_mode_async("paradox_horror")
        elif ph == PH_BLACKOUT:
            self.creatures = []
            self.fade = 1.0
            wled.apply_mode_async("paradox_blackout")
        elif ph == PH_POISON:
            wled.apply_mode_async("paradox")
        log.info("Phase: %s (Welle %d)", PHASE_NAMES[ph], self.wave)

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            self.antidote()
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.reboot()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_photo_view()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.call_help()
        elif ev.key == pygame.K_SPACE:
            self.set_shock(True)
        elif ev.key == pygame.K_BACKSPACE:
            self.set_shock(False)

    # -- Anzeigen ----------------------------------------------------------
    def _rattle_line(self, i: int) -> str:
        r = self.rng
        month = r.choice(MONTHS)
        day = r.randrange(1, 32)
        year = r.choice((1885, 1955, 1985, 2015, r.randrange(1000, 2999)))
        return f"{DATE_LABELS[i]}   {month} {day:02d} {year}   {r.randrange(24):02d}:{r.randrange(60):02d}"

    def _rattle(self, now: float) -> None:
        if now - self.rattle_t > 0.08:
            self.rattle_t = now
            self.rattle_lines = [self._rattle_line(i) for i in range(3)]

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uCreatureTex": (self.creatures_tex if self.creatures_tex is not None else self.blank, 1),
                "uPhotoTex": (self.photo if self.photo is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uCreatureTex", "uPhotoTex", "uFigTex", "uSceneSize", "uCreatureSize", "uPhotoSize", "uFigSize",
                 "uPhotoOK", "uFigOK", "uPhoto", "uHand", "uSeed", "uPhase", "uPhaseT", "uPhaseLen", "uWave", "uPoison", "uFade",
                 "uRelief", "uRebootT", "uPhotoView", "uHelpT", "uShock", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive",
                 "uBeatPulse", "uBeatStep", "uFlash", "uCut", "uBolt", "uCar", "uProf"]
        for i in range(N_CRE):
            names += [f"uCre{i}", f"uCreP{i}"]
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
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.1)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            if self.phase == PH_HORROR or self.poison > 0.75:
                self.cut = (self.rng.uniform(-0.03, 0.03), self.rng.uniform(-0.02, 0.02))
            if self.phase == PH_HORROR:
                self._bolt(now, 1.0)
                self.fade = min(1.0, self.fade + 0.035)                      # das Foto verblasst Stück für Stück
            elif self.phase == PH_POISON and self.rng.random() < 0.25:
                self._bolt(now, 0.6)
            for c in self.creatures:                                      # Anachronismen springen auf den Beat näher
                if self.phase == PH_HORROR or self.rng.random() < 0.35:
                    c.lunge_t0 = now
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
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
        self.flash = max(0.0, self.flash - dt / 1.5)
        # Phasen in Wellen
        pt = now - self.phase_t0
        if pt >= PHASE_LEN[self.phase]:
            self._set_phase((self.phase + 1) % 4, now)
            pt = 0.0
        target = {PH_WARN: 0.35, PH_POISON: 0.75, PH_HORROR: 1.0, PH_BLACKOUT: 0.2}[self.phase]
        self.poison += (target - self.poison) * min(1.0, dt / 6.0)
        self.poison = min(1.0, self.poison + 0.02 * dt * self.energy)         # laute Musik beschleunigt den Bruch
        if self.phase == PH_HORROR:
            self.fade = min(1.0, self.fade + dt * 0.012)
        elif self.phase == PH_POISON:
            self.fade = min(0.35, self.fade + dt * 0.004) if self.fade < 0.35 else self.fade
        if self.shock_on:
            self.fade = max(0.0, self.fade - dt / 2.0)                        # 1985: das Foto kommt zurück
        # Gegenmaßnahme: Erleichterung klingt ab, dann Rückfall
        self.relief = max(0.0, self.relief - dt / 4.0)
        if self.relapse_at is not None and now >= self.relapse_at:
            self.relapse_at = None
            self.poison = min(1.0, self.poison + 0.15)
            self.fade = min(1.0, self.fade + 0.25)
            log.info("Rückfall nach %s", self.relief_label)
        self.photo_view += ((1.0 if self.photo_view_on else 0.0) - self.photo_view) * min(1.0, dt / 0.6)
        self.shock += ((1.0 if self.shock_on else 0.0) - self.shock) * min(1.0, dt / 1.0)
        # Anachronismen: lauern, rücken näher, verschwinden; in der Gigawatt-Phase mehr und größer
        self.creatures = [c for c in self.creatures if not c.done(now)]
        if self.phase in (PH_POISON, PH_HORROR) and now >= self.next_spawn and len(self.creatures) < N_CRE:
            self.creatures.append(Creature(self.rng, now, self.phase == PH_HORROR))
            self.next_spawn = now + self.rng.uniform(1.5, 4.0) * (0.5 if self.phase == PH_HORROR else 1.0)
        # Flüstern
        if self.phase == PH_HORROR and now >= self.next_whisper:
            self.whisper = self.rng.choice(WHISPERS)
            self.whisper_t0 = now
            self.next_whisper = now + self.rng.uniform(3.0, 5.5)
        if self.phase == PH_WARN or now - self.reboot_t0 < 3.0:
            self._rattle(now)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("paradox_horror" if self.phase == PH_HORROR else "paradox")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("antidote", "reboot", "photo", "help", "shock", "drop"))
            if pick == "photo" and self.photo_view_on:
                pick = "antidote"
            {"antidote": self.antidote, "reboot": self.reboot, "photo": self.toggle_photo_view, "help": self.call_help,
             "shock": lambda: self.set_shock(not self.shock_on), "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + (3.0 if self.photo_view_on else 7.0)
        if self.photo_view_on and self.demo and now - self.demo_next > -0.5 and self.rng.random() < 0.02:
            self.toggle_photo_view()
        # Hilfe: Zeitmaschine fährt (Räder-Zellen), Professor winkt
        help_t = now - self.help_t0
        if help_t < 5.0:
            self.car_t += dt * (12.0 if help_t < 3.0 else 0.0)
            fire = help_t < 1.2
            cells = CAR_FIRE if fire else CAR_CELLS
            ci = int(self.car_t) % len(cells)
            car = (float(cells[ci]), float(cells[(ci + 1) % len(cells)]), self.car_t - int(self.car_t), help_t)
            wave = 0.5 + 0.5 * math.sin(help_t * 6.0)
            prof = (float(PROF_WAVE), float(PROF_CHEER if help_t > 3.6 else PROF_POINT), wave, max(0.0, min(1.0, (help_t - 2.6) / 0.6)))
        else:
            car = (0.0, 0.0, 0.0, -1.0)
            prof = (0.0, 0.0, 0.0, 0.0)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        bolt_age = now - self.bolt_t0
        out = {
            "uSceneSize": size(self.scene), "uCreatureSize": size(self.creatures_tex), "uPhotoSize": size(self.photo),
            "uFigSize": size(self.figs), "uPhotoOK": 1.0 if self.photo is not None else 0.0,
            "uFigOK": 1.0 if self.figs is not None else 0.0, "uPhoto": self.photo_cfg, "uHand": self.hand_cfg,
            "uSeed": self.seed, "uPhase": float(self.phase), "uPhaseT": pt, "uPhaseLen": PHASE_LEN[self.phase],
            "uWave": float(self.wave), "uPoison": self.poison, "uFade": self.fade, "uRelief": self.relief,
            "uRebootT": (now - self.reboot_t0) if now - self.reboot_t0 < 3.0 else -1.0, "uPhotoView": self.photo_view,
            "uHelpT": help_t if help_t < 5.0 else -1.0, "uShock": self.shock,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s,
            "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash, "uCut": self.cut,
            "uBolt": (bolt_age if bolt_age < 1.0 else -1.0, self.bolt[0], self.bolt[1], self.bolt[2]),
            "uCar": car, "uProf": prof,
        }
        for i in range(N_CRE):
            if i < len(self.creatures):
                c = self.creatures[i]
                age = c.age(now)
                lunge = max(0.0, 1.0 - (now - c.lunge_t0) / 0.5)
                out[f"uCre{i}"] = (c.x, c.y, c.size * (1.0 + 0.5 * c.approach * min(1.0, age / c.life)), float(c.cell))
                out[f"uCreP{i}"] = (age, lunge, c.hue, (1.0 if c.mirror else 0.0) + 2.0 * c.seed + 10.0 * c.life)
            else:
                out[f"uCre{i}"] = (0.0, 0.0, 0.0, -1.0)
                out[f"uCreP{i}"] = (0.0, 0.0, 0.0, 0.0)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        pt = now - self.phase_t0
        out = []
        pulse = int(62 + 70 * self.poison + 30 * self.bass_s + (25 if self.phase == PH_HORROR else 0) - 30 * self.relief - 20 * self.shock)
        if self.phase == PH_BLACKOUT:
            pulse = int(40 + 20 * math.sin(t * 2.0))
        col = (120, 230, 110) if pulse < 100 else ((255, 200, 80) if pulse < 140 else (255, 60, 60))
        flick = 0.75 + 0.25 * math.sin(t * (6.0 + 10.0 * self.poison))
        timeline = int(max(0.0, min(100.0, 100.0 * (1.0 - 0.55 * self.poison - 0.45 * self.fade) * (1.0 - 0.2 * (self.phase >= PH_HORROR)))))
        if self.phase == PH_BLACKOUT:
            timeline = 0 if pt < PHASE_LEN[PH_BLACKOUT] - 2.5 else 100
        out.append((f"PULS  {pulse}    ZEITLINIE  {timeline} %", 0.026, 0.16, 0.95, col, 0.9 * flick))
        out.append((f"WELLE {self.wave + 1}   {PHASE_NAMES[self.phase]}", 0.016, 0.88, 0.95, (210, 180, 140), 0.6))
        rattling = self.phase == PH_WARN or now - self.reboot_t0 < 2.5
        if rattling:
            a = min(1.0, pt / 1.0) if self.phase == PH_WARN else min(1.0, (2.5 - (now - self.reboot_t0)) / 0.6)
            for i, line in enumerate(self.rattle_lines):
                out.append((line, 0.02, 0.5, 0.83 - 0.045 * i, DATE_COLORS[i], 0.85 * a * (0.8 + 0.2 * math.sin(t * 30.0 + i))))
        if self.phase == PH_WARN:
            a = (0.5 + 0.5 * math.sin(t * 7.0)) * min(1.0, pt / 1.0)
            out.append(("Z E I T K R E I S E   D E F E K T", 0.045, 0.5, 0.5, (255, 70, 50), 0.9 * a))
        elif self.phase == PH_HORROR and self.whisper and now - self.whisper_t0 < 2.8:
            k = now - self.whisper_t0
            a = min(1.0, k * 4.0) * min(1.0, (2.8 - k) * 2.0) * (0.6 + 0.4 * math.sin(t * 23.0))
            x = 0.5 + 0.15 * math.sin(self.whisper_t0 * 3.1)
            out.append((self.whisper, 0.03, x, 0.3 + 0.3 * abs(math.sin(self.whisper_t0 * 1.7)), (200, 220, 255), 0.85 * a))
        elif self.phase == PH_BLACKOUT:
            a = 0.3 + 0.3 * math.sin(t * 1.5)
            out.append(("A U S L Ö S C H U N G", 0.05, 0.5, 0.62, (150, 100, 50), a))
            if pt > PHASE_LEN[PH_BLACKOUT] - 2.5:
                out.append(("ZEITLINIE WIEDERHERGESTELLT. NOCH EINMAL.", 0.03, 0.5, 0.42, (170, 210, 255), min(1.0, (pt - 5.5) / 1.0) * 0.8))
        if now - self.relief_t0 < 3.5:
            k = now - self.relief_t0
            txt = f"{self.relief_label} ... BESSER?" if k < 2.0 else f"{self.relief_label} ... SCHLIMMER."
            out.append((txt, 0.03, 0.5, 0.12, (150, 230, 220) if k < 2.0 else (255, 90, 90), min(1.0, (3.5 - k) * 2.0) * 0.9))
        if now - self.reboot_t0 < 2.5:
            out.append(("ZEITKREISE NEU STARTEN ...", 0.035, 0.5, 0.2, (255, 220, 120), min(1.0, (2.5 - (now - self.reboot_t0)) / 0.8)))
        if now - self.help_t0 < 5.0:
            out.append(("DER PROFESSOR KOMMT. STEIG EIN. KURZ.", 0.028, 0.5, 0.1, (255, 225, 170), 0.8 * min(1.0, (5.0 - (now - self.help_t0)) / 1.0)))
        if self.shock_on:
            out.append(("ZURÜCK IN 1985. KLAR. FÜR EINEN MOMENT.", 0.024, 0.5, 0.08, (180, 220, 255), 0.7))
        if self.photo_view_on:
            out.append(("DAS FOTO. SIE VERBLASSEN.", 0.024, 0.5, 0.1, (200, 170, 120), 0.5 + 0.3 * math.sin(t * 2.0)))
        return out
