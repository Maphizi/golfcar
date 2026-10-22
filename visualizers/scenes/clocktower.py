"""Der Uhrturm (Taste 4 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zu HAL 3000 / Orakel / Auge des Waldes).

Rathaus mit Uhrturm in einer Gewitternacht (assets/future/clocktower_scene.png, 1920x1080: leeres beleuchtetes
Zifferblatt OHNE Zeiger, Kabel vom Turm zur Laterne, unten acht gleich große dunkle Schaufenster), Figuren aus
assets/future/clocktower_figures.png (8x3 à 192: Reihe 0 Professor 0-7, Reihe 1 Zeitmaschine 8-15, Reihe 2 Tanzpaar 16-23).
Das Zifferblatt ist das Gesicht: die Zeiger zeichnet der Shader (uHands = Stunde, Minute, Sekunde in Umdrehungen).
Jedes Musikmerkmal hat sein Element:
  Beat      Sekundenzeiger tickt einen Schritt weiter (mit Überschwinger), Lauflicht durch die Schaufenster
  Energie   die großen Zeiger kriechen Richtung 22:04 (uClockT), bei 22:04 schlägt der Blitz ein
  Spektrum  acht Schaufenster = acht Bänder (uBands/uPeaks)
  Bass      Wolken leuchten von innen, der Turm bebt
  Mitten    Wetterleuchten hinter den Wolken (uSheet)
  Höhen     Regen und Funken am Kabel
  Drop      Blitz in den Turm, Kabel glüht, Weißblitz, Zeiger springen auf 22:04 (uStrikeT, uBolt)
  Stille    Wolken ziehen, nur Wetterleuchten, Fenster aus
Knüppel LINKS = der Professor hängt am Zifferblatt (Posen auf den Beat), RECHTS = die Zeitmaschine rast über den Platz
(Feuerspuren bleiben 4 s liegen), OBEN = beide, UNTEN = Tanzball (Girlanden über dem Platz, ein Paar tanzt zum Beat).
Startknopf = 22:04 von Hand (Blitz, Uhr bleibt 10 s stehen, läuft dann neu an). Kippschalter = Nahaufnahme aufs Zifferblatt.
Der Figurenbogen ist ungleichmäßig geschnitten (Zeitmaschine mal groß, mal klein, Reste der Nachbarzellen): `_fit_cells`
misst je Zelle den Hauptkörper, löscht Streuteile und liefert Passmaße (uCarFit, uDocFit*, uDancerFit*), mit denen der
Shader jede Zelle gleich breit und am Fußpunkt (bzw. der Professor am Griff oben) verankert zeichnet.
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

log = logging.getLogger("clocktower")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
FIG_NONE, FIG_DOC, FIG_CAR, FIG_BOTH = 0, 1, 2, 3
DOC_HANG, DOC_CLIMB, DOC_POINT, DOC_CHEER, DOC_SCARE, DOC_PULL, DOC_WAVE, DOC_SLIP = range(8)
CAR_CELLS = list(range(8, 16))                 # Fahrt von links nach rechts, die letzten zwei mit Feuerspuren
DANCE_CELLS = list(range(16, 24))
START_MINUTES = 21 * 60                        # die Uhr beginnt um 21:00 ...
STRIKE_MINUTES = 22 * 60 + 4                   # ... und der Blitz schlägt um 22:04 ein
STOP_SECONDS = 10.0                            # so lange steht die Uhr nach dem Blitz
REWIND_SECONDS = 2.0                           # dann drehen die Zeiger zurück
STRIKE_GAP = 12.0                              # Mindestabstand zweier Blitze
CAR_SPEED = 0.36                               # Platzbreite pro Sekunde
CAR_X0, CAR_X1 = -0.18, 1.2
CAR_FIRE_X = 0.3                               # ab hier zieht die Zeitmaschine Feuerspuren
TRAIL_SECONDS = 4.0
DEFAULT_CLOCK = (0.667, 0.824, 0.045)         # Zifferblatt x, y, Radius (am Foto gemessen)
DEFAULT_WINDOWS = (0.186, 0.613, 0.268, 0.044) # acht Schaufenster: x erste, x letzte, y Mitte, Breite (das neunte unter dem Turm)
DEFAULT_CABLE = (0.714, 0.764, 0.922, 0.463)   # Kabel Turm -> Laterne (x0, y0, x1, y1), Durchhang im Shader
CELL = 192
NO_FIT = (0.0, -1.0, 0.5, 0.5)                 # Passmaß ohne Messung: ganze Zelle, Fußpunkt unten
DOC_LABELS = {FIG_DOC: "DER PROFESSOR HÄNGT AM ZEIGER", FIG_CAR: "DIE ZEITMASCHINE RAST", FIG_BOTH: "DER GROSSE MOMENT"}
LED_FIG = {FIG_DOC: "clocktower_doc", FIG_CAR: "clocktower_car", FIG_BOTH: "clocktower_both"}


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 = unten). Ohne Alphakanal wird Schwarz freigestellt (Bögen vom Bot)."""
    try:
        surf = pygame.image.load(str(path))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
        try:
            alpha = pygame.surfarray.array_alpha(surf).transpose(1, 0)
        except ValueError:
            alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
        if int(alpha.min()) >= 250 and "scene" not in Path(path).name:
            peak = rgb.max(axis=2).astype(np.int16)
            alpha = np.clip((peak - 14) * 8, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(np.dstack([rgb, alpha]).astype(np.uint8)[::-1])
    except Exception as exc:
        log.warning("Bild %s nicht ladbar: %s", path, exc)
        return None


def _fit_cells(img: np.ndarray) -> list[tuple[float, float, float, float]]:
    """Je Zelle (8x3 à 192) den Hauptkörper messen: (Mitte x, Fuß y, halbe Breite, halbe Höhe) in Zellkoordinaten -1..1.
    Streuteile außerhalb des dichtesten Zeilen-/Spaltenblocks werden im Alphakanal gelöscht (Bogen ist Zeile 0 = unten)."""
    fits = []
    h, w = img.shape[:2]
    if h < 3 * CELL or w < 8 * CELL:
        return [NO_FIT] * 24
    for idx in range(24):
        ci, ri = idx % 8, idx // 8
        y0 = (2 - ri) * CELL                                   # GL-Zeile 0 = Bildunterkante
        cell = img[y0:y0 + CELL, ci * CELL:(ci + 1) * CELL]
        solid = (cell[:, :, 3] > 200) & (cell[:, :, :3].max(axis=2) > 70)
        rows = solid.sum(axis=1)
        cols = solid.sum(axis=0)

        def best_run(counts, minimum, gap_tol):
            # dichtester zusammenhängender Block; Lücken bis gap_tol Pixel (z. B. zwischen den Tänzern) zählen noch dazu
            runs, cur, mass, last = [], None, 0, -1
            for i, c in enumerate(list(counts) + [0]):
                if c >= minimum:
                    if cur is None:
                        cur, mass = i, 0
                    mass += int(c)
                    last = i
                elif cur is not None and i - last > gap_tol:
                    runs.append((cur, last, mass))
                    cur = None
            if cur is not None:
                runs.append((cur, last, mass))
            if not runs:
                return None
            a, b, _ = max(runs, key=lambda r: r[2])
            return a, b

        ry = best_run(rows, 10, 8)
        if ry is None:
            fits.append(NO_FIT)
            continue
        cols = solid[ry[0]:ry[1] + 1].sum(axis=0)
        rx = best_run(cols, 4, 28) or (0, CELL - 1)
        lo_y, hi_y = max(0, ry[0] - 3), min(CELL - 1, ry[1] + 3)
        lo_x, hi_x = max(0, rx[0] - 3), min(CELL - 1, rx[1] + 3)
        keep = np.zeros((CELL, CELL), dtype=bool)
        keep[lo_y:hi_y + 1, lo_x:hi_x + 1] = True
        cell[:, :, 3] = np.where(keep, cell[:, :, 3], 0)
        cx = ((lo_x + hi_x + 1) / CELL) - 1.0
        bottom = (2.0 * lo_y / CELL) - 1.0
        fits.append((cx, bottom, (hi_x - lo_x + 1) / CELL, (hi_y - lo_y + 1) / CELL))
    return fits


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        scene_path = ASSETS / "clocktower_scene.png"
        fig_path = ASSETS / "clocktower_figures.png"
        self.scene = _load_rgba(scene_path) if scene_path.exists() else None
        self.figs = _load_rgba(fig_path) if fig_path.exists() else None
        if self.scene is None:
            log.warning("Uhrturm: Szene %s fehlt, es bleibt dunkel (Zeiger, Fenster, Blitze laufen trotzdem)", scene_path)
        if self.figs is None:
            log.warning("Uhrturm: Figurenbogen %s fehlt, Professor/Zeitmaschine/Tanzpaar bleiben unsichtbar", fig_path)
        self.fits = _fit_cells(self.figs) if self.figs is not None else [NO_FIT] * 24
        self.clock = tuple(float(v) for v in scene_cfg.get("clock", DEFAULT_CLOCK))                # x, y, Radius
        self.windows = tuple(float(v) for v in scene_cfg.get("windows", DEFAULT_WINDOWS))          # x0, x7, y, Breite
        self.cable = tuple(float(v) for v in scene_cfg.get("cable", DEFAULT_CABLE))                # x0, y0, x1, y1
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
        # Uhr
        self.progress = self.rng.uniform(0.0, 0.35)      # 0 = 21:00, 1 = 22:04
        self.sec = self.rng.randrange(60)                 # Sekundenzeiger-Schritt
        self.sec_t0 = -10.0
        self.sec_wall = time.monotonic()
        self.strike_t0 = -100.0
        self.strike_by = ""
        self.rewind_from = 1.0
        self.cable_glow = 0.0
        self.bolt_seed = 1.0
        # Wetter
        self.sheet_t0 = -10.0
        self.sheet_x = 0.5
        self.sheet_k = 0.0
        self.sheet_next = time.monotonic() + 2.0
        # Figuren
        self.fig = FIG_NONE
        self.doc_pose = DOC_HANG
        self.doc_prev = DOC_HANG
        self.doc_t0 = 0.0
        self.doc_next = 0.0
        self.car_x = CAR_X0
        self.car_driving = False
        self.car_t0 = -100.0
        self.car_next = 0.0
        self.car_scale = 0.17
        self.dance = False
        self.dance_k = 0.0
        self.dance_pose = DANCE_CELLS[0]
        self.dance_prev = DANCE_CELLS[0]
        self.dance_t0 = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 4.0
        log.info("Der Uhrturm: Szene %s (%s), Figuren %s (%s)", "ok" if self.scene is not None else "fehlt", scene_path.name,
                 "ok" if self.figs is not None else "fehlt", fig_path.name)

    # -- Aktionen ----------------------------------------------------------
    def _base_profile(self) -> str:
        return "clocktower_dance" if self.dance else "clocktower"

    def _led_event(self, profile: str, back_at: float | None) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def set_fig(self, which: int) -> None:
        now = time.monotonic()
        self.fig = FIG_NONE if self.fig == which else which
        if self.fig == FIG_NONE:
            self._led_event(self._base_profile(), None)
            log.info("Figuren aus")
            return
        if self.fig in (FIG_CAR, FIG_BOTH):
            self._start_car(now)
        if self.fig in (FIG_DOC, FIG_BOTH):
            self.doc_prev, self.doc_pose, self.doc_t0 = self.doc_pose, DOC_HANG, now
        self._led_event(LED_FIG[self.fig], now + 6.0)
        log.info("Figur: %s", {FIG_DOC: "Professor", FIG_CAR: "Zeitmaschine", FIG_BOTH: "Professor und Zeitmaschine"}[self.fig])

    def toggle_dance(self) -> None:
        self.dance = not self.dance
        self._led_event(self._base_profile(), None)
        log.info("Tanzball %s", "an" if self.dance else "aus")

    def strike(self, now: float | None = None, by: str = "hand") -> None:
        """22:04 – der Blitz schlägt ein, die Uhr bleibt stehen."""
        now = time.monotonic() if now is None else now
        if now - self.strike_t0 < STRIKE_GAP:
            return
        self.strike_t0 = now
        self.strike_by = by
        self.progress = 1.0
        self.flash = 1.0
        self.cable_glow = 1.0
        self.bolt_seed = self.rng.uniform(1.0, 100.0)
        self.sheet_t0, self.sheet_x, self.sheet_k = now, self.clock[0], 1.0
        if self.fig in (FIG_DOC, FIG_BOTH):
            self.doc_prev, self.doc_pose, self.doc_t0 = self.doc_pose, DOC_SCARE, now
        self._led_event("clocktower_strike", now + 4.0)
        log.info("22:04 – Blitz schlägt in den Turm (%s)", by)

    def _start_car(self, now: float) -> None:
        if self.car_driving:
            return
        self.car_driving = True
        self.car_t0 = now
        self.car_x = CAR_X0
        self.car_scale = self.rng.uniform(0.15, 0.19)

    def _drop(self, now: float) -> None:
        self.step_dir = -self.step_dir
        self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
        self.strike(now, by="Drop")
        if self.fig in (FIG_DOC, FIG_BOTH):
            self.doc_prev, self.doc_pose, self.doc_t0 = self.doc_pose, DOC_SCARE, now
        log.info("Drop: Blitz, Lauflicht wechselt die Richtung")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.set_fig(FIG_DOC)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.set_fig(FIG_CAR)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.set_fig(FIG_BOTH)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_dance()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.strike()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Uhr ---------------------------------------------------------------
    def _minutes(self, now: float) -> float:
        """Angezeigte Tageszeit in Minuten (21:00 .. 22:04), nach dem Blitz steht sie, dann dreht sie zurück."""
        age = now - self.strike_t0
        if age < STOP_SECONDS:
            return float(STRIKE_MINUTES)
        if age < STOP_SECONDS + REWIND_SECONDS:
            k = (age - STOP_SECONDS) / REWIND_SECONDS
            k = k * k * (3.0 - 2.0 * k)
            return STRIKE_MINUTES - k * (STRIKE_MINUTES - START_MINUTES)
        return START_MINUTES + self.progress * (STRIKE_MINUTES - START_MINUTES)

    def _hands(self, now: float) -> tuple[float, float, float]:
        minutes = self._minutes(now)
        h = ((minutes / 60.0) % 12.0) / 12.0
        m = (minutes % 60.0) / 60.0
        age = now - self.sec_t0
        move = 1.0 - math.exp(-age * 22.0)
        over = 0.32 * math.sin(age * 26.0) * math.exp(-age * 7.0)
        s = ((self.sec - 1) + move + over) / 60.0
        return h, m, s % 1.0

    def clock_text(self, now: float) -> str:
        minutes = self._minutes(now)
        hh = int(minutes // 60) % 24
        mm = int(minutes % 60)
        return f"{hh:02d}:{mm:02d}:{self.sec % 60:02d}"

    def _tick(self, now: float) -> None:
        self.sec = (self.sec + 1) % 60
        self.sec_t0 = now

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uSceneTex", "uFigTex", "uSceneSize", "uFigSize", "uSeed", "uClock", "uWindows", "uCable",
                "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uStep", "uStepPhase", "uPattern",
                "uFlash", "uHands", "uClockT", "uStrikeT", "uBoltSeed", "uCableGlow", "uSheet", "uFig", "uDoc", "uDocFitA",
                "uDocFitB", "uCar", "uCarPar", "uCarFit", "uDance", "uDancer", "uDancerFitA", "uDancerFitB", "uZoom",
                "uBands0", "uBands1", "uPeaks0", "uPeaks1")

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
        stopped = now - self.strike_t0 < STOP_SECONDS
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            self.last_beat = now
            self.step = (self.step + self.step_dir) % 4
            self.step_t0 = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            if not stopped:
                self._tick(now)
            if self.fig in (FIG_DOC, FIG_BOTH) and now >= self.doc_next:
                pick = DOC_PULL if self.cable_glow > 0.3 else self.rng.choice((DOC_CLIMB, DOC_POINT, DOC_CHEER, DOC_PULL, DOC_WAVE, DOC_SLIP, DOC_HANG))
                self.doc_prev, self.doc_pose, self.doc_t0 = self.doc_pose, pick, now
                self.doc_next = now + self.rng.uniform(0.3, 1.2)
            if self.dance:
                self.dance_prev, self.dance_pose, self.dance_t0 = self.dance_pose, DANCE_CELLS[(DANCE_CELLS.index(self.dance_pose) + self.rng.randint(1, 2)) % 8], now
        elif not live and not stopped and now - self.sec_wall >= 1.0:
            self.sec_wall = now                                          # Stille: die Uhr tickt wie eine echte, 1 Hz
            self._tick(now)
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
        self.flash = max(0.0, self.flash - dt / 1.6)
        self.cable_glow = max(0.0, self.cable_glow - dt / 6.0)
        # Uhr: die großen Zeiger kriechen mit der Energie Richtung 22:04; nach Stillstand und Rücklauf geht es von vorn los
        age = now - self.strike_t0
        if age >= STOP_SECONDS + REWIND_SECONDS:
            if self.progress >= 1.0:
                self.progress = 0.0
            self.progress = min(1.0, self.progress + dt * (0.0025 + 0.012 * self.energy) * live)
            if self.progress >= 1.0:
                self.strike(now, by="Uhr")
        # Wetterleuchten (Mitten): weiche Blitze hinter den Wolken, in Stille selten
        if now >= self.sheet_next:
            self.sheet_t0, self.sheet_x = now, self.rng.uniform(0.05, 0.95)
            self.sheet_k = self.rng.uniform(0.4, 1.0) * (0.5 + 0.5 * self.mid_s) if live else self.rng.uniform(0.25, 0.5)
            gap = self.rng.uniform(1.0, 6.0) / (0.3 + 2.5 * self.mid_s) if live else self.rng.uniform(4.0, 10.0)
            self.sheet_next = now + gap
        # Professor: ohne Beat gelegentlich eine neue Pose
        if self.fig in (FIG_DOC, FIG_BOTH) and not live and now >= self.doc_next:
            self.doc_prev, self.doc_pose, self.doc_t0 = self.doc_pose, self.rng.choice((DOC_HANG, DOC_CLIMB, DOC_WAVE, DOC_SLIP)), now
            self.doc_next = now + self.rng.uniform(2.0, 5.0)
        # Zeitmaschine: fährt über den Platz, Feuerspuren bleiben liegen, im Figurmodus immer wieder
        if self.car_driving:
            self.car_x += dt * CAR_SPEED * (0.8 + 0.5 * self.energy)
            if self.car_x > CAR_X1 + CAR_SPEED * TRAIL_SECONDS * 1.3:
                self.car_driving = False
                self.car_next = now + self.rng.uniform(6.0, 12.0)
        elif self.fig in (FIG_CAR, FIG_BOTH) and now >= self.car_next:
            self._start_car(now)
        self.dance_k += ((1.0 if self.dance else 0.0) - self.dance_k) * min(1.0, dt / 0.8)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async(self._base_profile())
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("doc", "car", "both", "dance", "strike", "drop"))
            {"doc": lambda: self.set_fig(FIG_DOC), "car": lambda: self.set_fig(FIG_CAR), "both": lambda: self.set_fig(FIG_BOTH),
             "dance": self.toggle_dance, "strike": self.strike, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 8.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        car_prog = (self.car_x - CAR_X0) / (CAR_X1 - CAR_X0)
        car_cell = CAR_CELLS[min(7, max(0, int(car_prog * 8.0)))]
        return {
            "uSceneSize": size(self.scene), "uFigSize": size(self.figs), "uSeed": self.seed,
            "uClock": self.clock, "uWindows": self.windows, "uCable": self.cable,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s,
            "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern),
            "uFlash": self.flash, "uHands": self._hands(now), "uClockT": self.progress,
            "uStrikeT": age if age < STOP_SECONDS + REWIND_SECONDS else -1.0, "uBoltSeed": self.bolt_seed,
            "uCableGlow": self.cable_glow,
            "uSheet": (now - self.sheet_t0, self.sheet_x, self.sheet_k, 0.0),
            "uFig": (float(self.fig), 0.0, 0.0, 0.0),
            "uDoc": (float(self.doc_prev), float(self.doc_pose), min(1.0, (now - self.doc_t0) / 0.15),
                     0.25 * math.sin(now * 0.9) + 0.1 * self.bass_s * math.sin(now * 9.0)),
            "uDocFitA": self.fits[self.doc_prev], "uDocFitB": self.fits[self.doc_pose],
            "uCar": (self.car_x if self.car_driving else -2.0, float(car_cell), self.car_scale,
                     1.0 if self.car_driving else 0.0),
            "uCarPar": (0.1, CAR_SPEED * (0.8 + 0.5 * self.energy), CAR_FIRE_X, TRAIL_SECONDS),
            "uCarFit": self.fits[car_cell],
            "uDance": self.dance_k,
            "uDancer": (float(self.dance_prev), float(self.dance_pose), min(1.0, (now - self.dance_t0) / 0.15), 0.0),
            "uDancerFitA": self.fits[self.dance_prev], "uDancerFitB": self.fits[self.dance_pose],
            "uZoom": self.zoom,
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]),
            "uPeaks0": tuple(self.band_peak[0:4]), "uPeaks1": tuple(self.band_peak[4:8]),
        }

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        age = now - self.strike_t0
        struck = age < STOP_SECONDS
        title_col = (255, 255, 255) if struck and age < 1.5 else (255, 215, 140)
        out.append(("UHRTURM  22:04", 0.03, 0.5, 0.95, title_col, 0.8))
        out.append((self.clock_text(now), 0.022, 0.5, 0.905, (255, 235, 190) if not struck else (255, 255, 255), 0.7))
        if age < 4.0:
            a = 1.0 if age < 2.5 else (4.0 - age) / 1.5
            flick = 0.75 + 0.25 * math.sin(t * 40.0)
            out.append(("1,21 GIGAWATT", 0.05, 0.5, 0.5, (255, 255, 255), min(1.0, a) * flick))
        elif struck:
            out.append(("DIE UHR STEHT", 0.02, 0.5, 0.5, (200, 220, 255), 0.5 + 0.3 * math.sin(t * 3.0)))
        elif age < STOP_SECONDS + REWIND_SECONDS:
            out.append(("ZEITKREISE ZURÜCK", 0.02, 0.5, 0.5, (120, 255, 160), 0.7))
        if self.dance:
            out.append(("VERZAUBERUNG UNTER DEM MEER", 0.022, 0.5, 0.1, (255, 170, 210), 0.65 + 0.3 * math.sin(t * 2.5)))
        if self.fig != FIG_NONE:
            out.append((DOC_LABELS[self.fig], 0.018, 0.5, 0.045, (200, 220, 255), 0.55))
        return out
