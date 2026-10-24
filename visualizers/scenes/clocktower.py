"""Der Uhrturm (Taste 4 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zu HAL 3000 / Orakel / Auge des Waldes).

Nah am Turm in einer Gewitternacht (assets/future/clocktower_tower.png, Bilder und Schnitt: docs/future_plan.md Runde 3,
scripts/clocktower_assets.py): oben das große leere Zifferblatt, darunter eine verwinkelte Fassade mit 13 schief und
durcheinander gesetzten Fenstern, unten ein Streifen nasser Straße. Die Fenster findet der Asset-Schnitt an ihren
reinschwarzen Scheiben (clocktower_winmask.png = Fenster-Nr. je Pixel, clocktower_layout.json = Rechtecke + Zifferblatt).

Jedes Fenster hat sein eigenes Licht (Farbe, Stufe aus einem Spektrumband) und eine Silhouette aus clocktower_sil.png
(8x3: tanzende Paare, Gitarrist, Hund, Professor, Hand und Gesicht an der Scheibe …), die sich langsam bewegt und alle
paar Sekunden wechselt; auf den Beat wechseln einzelne Fenster die Farbe, alle 8 Beats läuft eine Farbwelle durch.
Messingzeiger aus clocktower_hands.png kriechen mit der Energie von 21:00 auf 22:04, der Sekundenzeiger tickt je Beat.

Die Nacht spielt sich selbst ab (`act`, ~3 min je Runde):
  0 ruhige Nacht 21:00-21:50, der Professor (clocktower_climber.png, fotorealistisch) klettert irgendwann die Fassade hoch
  1 Gewitter ab 21:50: Regen, ferne Blitze, Uhr rückt näher, der Professor hängt unter dem Zifferblatt
  2 Countdown ab 22:02 (FINAL_SECONDS): Fenster pulsen mit den Sekunden, Silhouetten schauen hoch, Kabel knistert,
    die Zeitmaschine (clocktower_car.png) wartet mit Blitzbögen am Straßenrand
  3 22:04 – die Uhr spielt verrückt (CRAZY_SECONDS): Zeiger rasen vor und zurück, das Zifferblatt wird durchsichtig und
    das Uhrwerk (clocktower_clockwork.png) dreht sich dahinter, Funken, der Turm bebt, die Fenster flackern wild
  4 Blitz: Einschlag in den Turm, alle Fenster gleißen auf und gehen aus, die Zeitmaschine rast mit Feuerspuren los,
    die Uhr steht (STOP_SECONDS, Zifferblatt gesprungen), dann laufen die Zeiger zurück und es geht von vorn los
Knüppel LINKS = Professor (klettern bzw. nächste Pose), RECHTS = Zeitmaschine fährt durch, OBEN = alle Fenster wechseln,
UNTEN = Tanzabend (überall tanzende Paare in Pastell), Startknopf = 22:04 sofort, Kippschalter = Nahaufnahme aufs Zifferblatt.
"""
from __future__ import annotations

import colorsys
import json
import logging
import math
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled
from visualizers.engine import images

log = logging.getLogger("clocktower")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
N_WIN = 15                                     # Plätze im Shader (uWinA..D[0..14])
START_MINUTES = 21 * 60                        # die Uhr beginnt um 21:00 ...
STRIKE_MINUTES = 22 * 60 + 4                   # ... und um 22:04 spielt sie verrückt
ACT_STORM = 50.0 / 64.0                        # 21:50 das Gewitter zieht auf
ACT_FINAL = 62.0 / 64.0                        # 22:02 Countdown
FINAL_SECONDS = 20.0                           # 22:02 -> 22:04 dauert immer so lange
CRAZY_SECONDS = 5.5                            # so lange spielt die Uhr verrückt, dann schlägt der Blitz ein
STOP_SECONDS = 10.0                            # so lange steht die Uhr nach dem Blitz
REWIND_SECONDS = 2.5                           # dann drehen die Zeiger zurück
DROP_STRIKE_MIN = 0.6                          # Drop löst 22:04 erst ab ~21:38 aus, davor Gewitterstoß
CLIMB_SECONDS = 28.0                           # so lange klettert der Professor von der Straße bis unters Zifferblatt
CLIMB_START = (0.25, 0.42)                     # im Fortschritt der Nacht beginnt er irgendwo hier
CLIMB_PATH = ((0.535, 0.06), (0.528, 0.60))    # Route zwischen den Fenstern (Fußpunkt unten -> oben)
STORM_ZOOM = 0.12
SIL_CELLS = 24
SIL_EMPTY = 0.2                                # Anteil der Fenster ohne Silhouette (nur Licht)
SIL_LOOK = (4, 21, 22, 10, 13)                 # Countdown: zeigt hoch, Hand, Gesicht an der Scheibe, Fernglas, Laufen
SIL_DANCE = (0, 1, 12, 18)                     # Tanzabend: Paare
SIL_STILL = (5, 6, 21, 22, 19, 17)             # stehen still (Hund, Katze, Hand, Gesicht, Band, Kopfstand)
CAR_Y = 0.012                                  # Straße: Räder auf dieser Höhe
CAR_W = 0.27                                   # Breite der Zeitmaschine (Bildbreite)
CAR_WAIT_X = 0.07
CAR_SPEED = 0.5                                # Bildbreiten je Sekunde (beschleunigt)
TRAIL_SECONDS = 4.0
PASTEL = (0.92, 0.48, 0.14, 0.78, 0.36, 0.06, 0.58, 0.02)
ACT_NAMES = ("RUHIGE NACHT", "GEWITTER", "COUNTDOWN", "DIE UHR SPIELT VERRÜCKT", "BLITZ")
DEFAULT_CLOCK = (0.494, 0.833, 0.093)
POSE_HANG2, POSE_HANG1, POSE_PULL, POSE_FEAR, POSE_POINT, POSE_PLUG, POSE_SLIP, POSE_CROUCH = range(8, 16)


def _hue_lerp(a: float, b: float, k: float) -> float:
    d = ((b - a + 0.5) % 1.0) - 0.5
    return (a + d * k) % 1.0


class Window:
    """Ein Fenster: Licht (Farbton, Sättigung, Stufe) und Silhouette (Zelle A -> B mit Überblendung, Lage, Bewegung)."""

    def __init__(self, idx: int, box: tuple[float, float, float, float], rng: random.Random, now: float):
        self.idx = idx
        self.box = box
        self.rng = rng
        self.band = idx % 8
        self.hue = rng.random()
        self.hue_from = self.hue
        self.hue_to = self.hue
        self.hue_t0 = -10.0
        self.sat = 0.8
        self.on = 1.0
        self.on_target = 1.0
        self.sil_a = self.sil_b = self._pick()
        self.sil_t0 = -10.0
        self.sil_next = now + rng.uniform(2.0, 12.0)
        self.mirror = rng.random() < 0.5
        self.walk = 0.0
        self.walk_v = 0.0
        self.dx = rng.uniform(-0.15, 0.15)
        self.flash = 0.0
        self._motion()

    def _pick(self, pool=None) -> int:
        if pool is None and self.rng.random() < SIL_EMPTY:
            return -1
        return self.rng.choice(pool) if pool else self.rng.randrange(SIL_CELLS)

    def _motion(self) -> None:
        cell = self.sil_b
        self.walk_v = 0.0 if cell in SIL_STILL or cell < 0 else self.rng.choice((0.0, 0.0, 0.05, -0.05, 0.09, -0.09))

    def set_hue(self, hue: float, now: float, sat: float | None = None) -> None:
        self.hue_from, self.hue_to, self.hue_t0 = self.hue, hue % 1.0, now
        if sat is not None:
            self.sat = sat

    def set_sil(self, cell: int, now: float) -> None:
        if cell == self.sil_b:
            return
        self.sil_a, self.sil_b, self.sil_t0 = self.sil_b, cell, now
        self.mirror = self.rng.random() < 0.5
        self.dx = self.rng.uniform(-0.18, 0.18)
        self._motion()

    def tick(self, now: float, dt: float, fade: float = 0.45) -> None:
        k = min(1.0, max(0.0, (now - self.hue_t0) / fade))           # Welle: Start liegt je Fenster etwas später
        self.hue = _hue_lerp(self.hue_from, self.hue_to, k * k * (3.0 - 2.0 * k))
        self.on += (self.on_target - self.on) * min(1.0, dt / 0.25)
        self.flash = max(0.0, self.flash - dt / 0.6)
        if self.walk_v:                                                    # läuft durchs Zimmer, kehrt am Rand um
            self.dx += self.walk_v * dt
            if abs(self.dx) > 0.3:
                self.dx = math.copysign(0.3, self.dx)
                self.walk_v = -self.walk_v
                self.mirror = not self.mirror


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        load = lambda n: images.load_rgba(ASSETS / n) if (ASSETS / n).exists() else None
        self.scene = load("clocktower_tower.png")
        self.winmask = load("clocktower_winmask.png")
        self.sil = load("clocktower_sil.png")
        self.climber = load("clocktower_climber.png")
        self.hands_tex = load("clocktower_hands.png")
        self.clockwork = load("clocktower_clockwork.png")
        self.car_tex = load("clocktower_car.png")
        layout = {}
        try:
            layout = json.loads((ASSETS / "clocktower_layout.json").read_text())
        except (OSError, ValueError) as exc:
            log.warning("Uhrturm: clocktower_layout.json fehlt (%s), keine Fenster", exc)
        self.clock = tuple(float(v) for v in scene_cfg.get("clock", layout.get("clock", DEFAULT_CLOCK)))
        boxes = [(w["x0"], w["y0"], w["x1"], w["y1"]) for w in layout.get("windows", [])][:N_WIN]
        self.cable = tuple(float(v) for v in scene_cfg.get("cable", (0.646, 0.676, 0.69, 0.33, 0.87, 0.26)))
        now = time.monotonic()
        self.wins = [Window(i, b, self.rng, now) for i, b in enumerate(boxes)]
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = now
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.bands = [0.0] * 8
        self.beat_pulse = 0.0
        self.beat_n = 0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        # Uhr
        self.progress = self.rng.uniform(0.0, 0.3)       # 0 = 21:00, 1 = 22:04
        self.sec = self.rng.randrange(60)
        self.sec_t0 = -10.0
        self.sec_wall = now
        self.crazy_t0 = -100.0                            # 22:04 erreicht: die Uhr spielt verrückt
        self.bolt_t0 = -100.0                             # Blitz
        self.bolt_seed = 1.0
        self.crazy_off = [0.0, 0.0, 0.0]                  # Zeigerversatz (Umdrehungen) beim Verrücktspielen
        self.crazy_vel = [0.0, 0.0, 0.0]
        self.crazy_next = 0.0
        self.cw_rot = 0.0                                 # Drehung des Uhrwerks
        self.act = 0
        self.act_t0 = now
        self.storm = 0.0
        self.final_k = 0.0
        self.crazy_k = 0.0
        self.auto_zoom = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        # Wetter
        self.sheet_t0, self.sheet_x, self.sheet_k = -10.0, 0.5, 0.0
        self.sheet_next = now + 3.0
        self.far_t0, self.far_x, self.far_seed, self.far_k = -100.0, 0.2, 1.0, 0.0
        self.far_next = now + 8.0
        self.spark_t0 = -100.0
        self.spark_next = now + self.rng.uniform(20.0, 40.0)
        # Professor
        self.climb_at = self.rng.uniform(*CLIMB_START)    # Fortschritt der Nacht, bei dem er losklettert
        self.climb_t0: float | None = None
        self.doc_pose = POSE_HANG2
        self.doc_pose_next = 0.0
        self.doc_vis = 0.0
        self.doc_pos = (CLIMB_PATH[0][0], CLIMB_PATH[0][1])
        self.doc_fall_t0 = -100.0
        # Zeitmaschine
        self.car_x = -1.0
        self.car_driving = False
        self.car_t0 = -100.0
        self.car_start_at: float | None = None
        # Fenster
        self.dance = False
        self.wave_t0 = -10.0
        self.shuffle_t0 = -10.0
        self.crazy_win_next = 0.0
        self.demo_next = now + 4.0
        log.info("Der Uhrturm: Szene %s, %d Fenster, Silhouetten %s, Kletterer %s, Zeiger %s, Uhrwerk %s, Zeitmaschine %s",
                 "ok" if self.scene is not None else "fehlt", len(self.wins), *("ok" if a is not None else "fehlt" for a in
                 (self.sil, self.climber, self.hands_tex, self.clockwork, self.car_tex)))

    # -- Aktionen ----------------------------------------------------------
    def strike(self, now: float | None = None, by: str = "hand") -> None:
        """22:04: die Uhr spielt verrückt, CRAZY_SECONDS später schlägt der Blitz ein."""
        now = time.monotonic() if now is None else now
        if self.act >= 3:
            return
        self.progress = 1.0
        self.crazy_t0 = now
        self.crazy_next = now
        wled.apply_mode_async("clocktower_strike")
        log.info("22:04 – die Uhr spielt verrückt (%s)", by)

    def _bolt(self, now: float) -> None:
        self.bolt_t0 = now
        self.bolt_seed = self.rng.uniform(1.0, 100.0)
        self.flash = 1.0
        self.sheet_t0, self.sheet_x, self.sheet_k = now, self.clock[0], 1.0
        for w in self.wins:
            w.flash = 1.0
            w.on_target = 0.0                                          # nach dem Gleißen gehen alle Lichter aus
        if not self.car_driving:
            self.car_start_at = now + 0.4
        if self.doc_vis > 0.5:
            self.doc_fall_t0 = now + 0.8
        log.info("Blitz schlägt in den Turm")

    def drive(self, now: float, x0: float = -CAR_W) -> None:
        if self.car_driving:
            return
        self.car_driving, self.car_t0, self.car_x = True, now, x0
        log.info("Die Zeitmaschine rast los")

    def doc_action(self, now: float) -> None:
        if self.climb_t0 is None:
            self.climb_t0 = now
            self.doc_fall_t0 = -100.0
            log.info("Der Professor klettert auf den Turm")
        else:
            self.doc_pose = POSE_HANG2 + (self.doc_pose - POSE_HANG2 + 1) % 7
            self.doc_pose_next = now + 4.0

    def shuffle(self, now: float) -> None:
        for w in self.wins:
            w.set_sil(w._pick(SIL_DANCE if self.dance else None), now)
            w.set_hue(self.rng.random(), now)
        self.shuffle_t0 = now

    def toggle_dance(self) -> None:
        self.dance = not self.dance
        now = time.monotonic()
        for i, w in enumerate(self.wins):
            if self.dance:
                w.set_sil(self.rng.choice(SIL_DANCE), now)
                w.set_hue(PASTEL[i % len(PASTEL)], now, sat=0.45)
            else:
                w.set_hue(self.rng.random(), now, sat=0.8)
        log.info("Tanzabend %s", "an" if self.dance else "aus")

    def _drop(self, now: float) -> None:
        for w in self.wins:
            w.set_hue(self.rng.random(), now)
            w.flash = max(w.flash, 0.6)
        if self.progress >= DROP_STRIKE_MIN and self.act < 3:
            self.strike(now, by="Drop")
            return
        if self.act < 3:
            self.progress = min(ACT_FINAL - 0.01, self.progress + 10.0 / 64.0)
            self._far(now, 1.0)
            self.sheet_t0, self.sheet_x, self.sheet_k = now, self.far_x, 1.0
            self.spark_t0 = now
            log.info("Drop: Gewitterstoß, die Uhr springt auf %s", self.clock_text(now)[:5])

    def _far(self, now: float, k: float) -> None:
        self.far_t0, self.far_seed, self.far_k = now, self.rng.uniform(1.0, 100.0), k
        self.far_x = self.rng.choice((self.rng.uniform(0.03, 0.25), self.rng.uniform(0.78, 0.97)))

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        now = time.monotonic()
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.doc_action(now)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.drive(now)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.shuffle(now)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_dance()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.strike(now)
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Uhr ---------------------------------------------------------------
    def _rate(self) -> float:
        r = (1.0 - ACT_FINAL) / FINAL_SECONDS if self.progress >= ACT_FINAL else 0.0025 + 0.012 * self.energy
        return r * (4.0 if self.demo else 1.0)

    def _minutes(self, now: float) -> float:
        age = now - self.bolt_t0
        if self.act == 3 or (self.act == 4 and age < STOP_SECONDS):
            return float(STRIKE_MINUTES)
        if self.act == 4 and age < STOP_SECONDS + REWIND_SECONDS:
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
        tremble = 0.0
        if self.act == 4 and now - self.bolt_t0 < STOP_SECONDS:            # nach dem Einschlag zittern die Zeiger
            tremble = 0.004 * math.sin(now * 37.0) * math.exp(-(now - self.bolt_t0) * 0.4)
        return ((h + self.crazy_off[0] + tremble) % 1.0, (m + self.crazy_off[1] - tremble) % 1.0,
                (s + self.crazy_off[2]) % 1.0)

    def clock_text(self, now: float) -> str:
        minutes = self._minutes(now)
        return f"{int(minutes // 60) % 24:02d}:{int(minutes % 60):02d}:{self.sec % 60:02d}"

    def _tick(self, now: float) -> None:
        self.sec = (self.sec + 1) % 60
        self.sec_t0 = now

    def led_state(self) -> dict:
        """Für das LED-Programm `clockwork` (launcher/ledstream.py)."""
        now = time.monotonic()
        wins = []
        for w in self.wins:
            r, g, b = colorsys.hsv_to_rgb(w.hue, w.sat, 1.0)
            lvl = w.on * (0.35 + 0.65 * self.bands[w.band]) + w.flash
            wins.append((0.5 * (w.box[0] + w.box[2]), (r * 255.0, g * 255.0, b * 255.0), min(1.5, lvl)))
        car = (self.car_x + 0.5 * CAR_W, self._car_speed()) if self.car_driving else None
        return {
            "clock_k": (self._minutes(now) - START_MINUTES) / (STRIKE_MINUTES - START_MINUTES),
            "act": self.act, "storm": self.storm, "final": self.final_k, "crazy": self.crazy_k,
            "rewind": self.act == 4 and now - self.bolt_t0 >= STOP_SECONDS,
            "stopped": self.act == 4 and now - self.bolt_t0 < STOP_SECONDS,
            "strike_age": now - self.bolt_t0, "sec": self._hands(now)[2],
            "sheet": (now - self.sheet_t0, self.sheet_x, self.sheet_k),
            "far": (now - self.far_t0, self.far_x, self.far_k),
            "spark_age": now - self.spark_t0, "car": car, "car_wait": self._car_wait(), "car_t0": self.car_t0,
            "doc": self.doc_vis, "dance": 1.0 if self.dance else 0.0, "beat_step": self.beat_n, "wins": wins,
        }

    def _car_wait(self) -> bool:
        return not self.car_driving and (self.act == 2 or self.act == 3 or self.car_start_at is not None)

    def _car_speed(self) -> float:
        return CAR_SPEED * (0.5 + 1.5 * min(1.0, (time.monotonic() - self.car_t0) / 1.2))

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        b = self.blank
        return {"uSceneTex": (self.scene if self.scene is not None else b, 1),
                "uWinTex": (self.winmask if self.winmask is not None else b, 2),
                "uSilTex": (self.sil if self.sil is not None else b, 3),
                "uDocTex": (self.climber if self.climber is not None else b, 4),
                "uHandTex": (self.hands_tex if self.hands_tex is not None else b, 5),
                "uGearTex": (self.clockwork if self.clockwork is not None else b, 6),
                "uCarTex": (self.car_tex if self.car_tex is not None else b, 7)}

    def uniform_names(self):
        names = ["uSceneTex", "uWinTex", "uSilTex", "uDocTex", "uHandTex", "uGearTex", "uCarTex",
                 "uSceneSize", "uSilSize", "uDocSize", "uHandSize", "uGearSize", "uCarSize", "uSeed", "uClock", "uCable",
                 "uCable2", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uFlash", "uHands", "uClockT",
                 "uBoltT", "uBoltSeed", "uCrazy", "uGearRot", "uStorm", "uFinal", "uSheet", "uFarBolt", "uSparkT",
                 "uDoc", "uDocPos", "uCar", "uCarT", "uZoom", "uNWin"]
        for i in range(N_WIN):
            names += [f"uWinA[{i}]", f"uWinB[{i}]", f"uWinC[{i}]"]
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
        spec = getattr(f, "spectrum", None)
        for i in range(8):
            v = 0.0
            if spec is not None and len(spec) >= 8 and live:
                n = len(spec) // 8
                v = min(1.0, float(np.mean(spec[i * n:(i + 1) * n])) * (1.15 + 0.1 * i))
            self.bands[i] += (v - self.bands[i]) * min(1.0, dt / (0.06 if v > self.bands[i] else 0.35))
        # Ablauf der Nacht
        crazy_age = now - self.crazy_t0
        bolt_age = now - self.bolt_t0
        if self.act == 3 and crazy_age >= CRAZY_SECONDS:
            self._bolt(now)
            bolt_age = 0.0
        if crazy_age < CRAZY_SECONDS:
            act = 3
        elif bolt_age < STOP_SECONDS + REWIND_SECONDS:
            act = 4
        else:
            if self.act == 4:                                              # neue Nacht
                self.progress = 0.0
                self.climb_at = self.rng.uniform(*CLIMB_START)
                self.climb_t0 = None
                for w in self.wins:
                    w.on_target = 1.0
            self.progress = min(1.0, self.progress + dt * self._rate() * live)
            if self.progress >= 1.0:
                self.strike(now, by="Uhr")
                act = 3
            else:
                act = 2 if self.progress >= ACT_FINAL else (1 if self.progress >= ACT_STORM else 0)
        if act != self.act:
            self.act, self.act_t0 = act, now
            log.info("Uhrturm: %s (%s)", ACT_NAMES[act], self.clock_text(now)[:5])
        storm_t = {3: 1.0, 4: 0.6 if bolt_age < STOP_SECONDS else 0.2}.get(act)
        if storm_t is None:
            k = min(1.0, max(0.0, (self.progress - 0.62) / 0.3))
            storm_t = k * k * (3.0 - 2.0 * k)
        self.storm += (storm_t - self.storm) * min(1.0, dt / 2.5)
        self.final_k += ((1.0 if act == 2 else 0.0) - self.final_k) * min(1.0, dt / 0.8)
        self.crazy_k += ((1.0 if act == 3 else 0.0) - self.crazy_k) * min(1.0, dt / (0.6 if act == 3 else 1.5))
        az = STORM_ZOOM * self.storm if act in (1, 2) else 0.0
        self.auto_zoom += (az - self.auto_zoom) * min(1.0, dt / (2.5 if az > self.auto_zoom else 0.8))
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        # Zeiger spielen verrückt: Geschwindigkeiten springen, rasen vor und zurück; danach zurück auf 22:04
        if act == 3:
            if now >= self.crazy_next:
                self.crazy_next = now + self.rng.uniform(0.25, 0.7)
                self.crazy_vel = [self.rng.uniform(-1.2, 1.2), self.rng.uniform(-5.0, 5.0), self.rng.uniform(-9.0, 9.0)]
            ramp = min(1.0, crazy_age / 1.5)
            for i in range(3):
                self.crazy_off[i] += self.crazy_vel[i] * ramp * dt
            self.cw_rot += dt * (2.0 + 6.0 * math.sin(now * 1.3)) * ramp
        else:
            for i in range(3):
                self.crazy_off[i] = (((self.crazy_off[i] + 0.5) % 1.0) - 0.5) * math.exp(-dt / 0.15)
            self.cw_rot += dt * 0.3 * self.crazy_k
        # Beat und Sekunden
        stopped = act in (3, 4)
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            self.last_beat = now
            self.beat_n += 1
            self.beat_pulse = 1.0
            if not stopped:
                self._tick(now)
            self._windows_beat(now)
        elif not live and not stopped and now - self.sec_wall >= 1.0:
            self.sec_wall = now
            self._tick(now)
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
        self.flash = max(0.0, self.flash - dt / 1.6)
        self._weather(now, live)
        self._windows_tick(now, dt, live)
        self._doc_tick(now, dt, live)
        self._car_tick(now, dt)
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("doc", "car", "shuffle", "dance", "strike", "drop"))
            {"doc": lambda: self.doc_action(now), "car": lambda: self.drive(now), "shuffle": lambda: self.shuffle(now),
             "dance": self.toggle_dance, "strike": lambda: self.strike(now), "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 8.0
        return self._pack(now)

    # -- Teile -------------------------------------------------------------
    def _weather(self, now: float, live: float) -> None:
        if now >= self.sheet_next:                                         # Wetterleuchten (Mitten), im Gewitter öfter
            self.sheet_t0, self.sheet_x = now, self.rng.uniform(0.02, 0.98)
            self.sheet_k = self.rng.uniform(0.4, 1.0) * (0.5 + 0.5 * self.mid_s) if live else self.rng.uniform(0.25, 0.5)
            gap = self.rng.uniform(1.5, 7.0) / (0.3 + 2.5 * self.mid_s) if live else self.rng.uniform(5.0, 12.0)
            self.sheet_next = now + gap / (1.0 + 2.5 * self.storm)
        if now >= self.far_next:                                           # ferne Blitze
            if self.act in (1, 2, 3) or (live and self.rng.random() < 0.5):
                self._far(now, self.rng.uniform(0.5, 1.0) * (0.6 + 0.4 * self.storm))
                for w in self.wins:                                        # die Lichter zucken kurz
                    if self.rng.random() < 0.25:
                        w.flash = max(w.flash, 0.25)
            self.far_next = now + (self.rng.uniform(2.0, 5.0) / (0.5 + self.storm) if self.act in (1, 2, 3)
                                   else self.rng.uniform(10.0, 20.0))
        if self.act == 2 and now - self.spark_t0 > 1.5 and self.rng.random() < 0.02:
            self.spark_t0 = now                                            # Countdown: das Kabel knistert
        elif self.act < 2 and now >= self.spark_next:
            self.spark_t0 = now
            self.spark_next = now + self.rng.uniform(25.0, 50.0)

    def _windows_beat(self, now: float) -> None:
        if not self.wins or self.act == 4:
            return
        if self.act == 3:
            return
        if self.dance:                                                     # Tanzabend: Farben bleiben pastell, rücken weiter
            if self.beat_n % 4 == 0:
                for w in self.wins:
                    w.set_hue(PASTEL[(PASTEL.index(min(PASTEL, key=lambda p: abs(p - w.hue))) + 1) % len(PASTEL)], now, sat=0.45)
            return
        if self.act == 2:                                                  # Countdown: alle pulsen im Sekundentakt
            for w in self.wins:
                w.flash = max(w.flash, 0.35)
            return
        if self.beat_n % 8 == 0:                                           # Farbwelle von links nach rechts
            self.wave_t0 = now
            step = self.rng.choice((0.13, 0.21, 0.33, 0.5))
            for w in self.wins:
                w.set_hue(w.hue_to + step, now + 0.07 * w.idx)
        else:
            for w in self.rng.sample(self.wins, min(len(self.wins), self.rng.choice((1, 1, 2)))):
                w.set_hue(self.rng.random(), now)

    def _windows_tick(self, now: float, dt: float, live: float) -> None:
        crazy = self.act == 3
        if crazy and now >= self.crazy_win_next:                           # wildes Flackern: Farben und Figuren springen
            self.crazy_win_next = now + self.rng.uniform(0.08, 0.18)
            for w in self.rng.sample(self.wins, min(len(self.wins), 4)):
                w.set_hue(self.rng.random(), now, sat=1.0)
                w.on_target = 1.0 if self.rng.random() < 0.75 else 0.0
                if self.rng.random() < 0.3:
                    w.set_sil(w._pick(), now)
        bolt_age = now - self.bolt_t0
        for w in self.wins:
            if self.act == 4 and bolt_age > 3.0 + 0.45 * w.idx:            # nach dem Einschlag kommen sie einzeln zurück
                if w.on_target == 0.0:
                    w.on_target = 1.0
                    w.set_hue(self.rng.random(), now, sat=0.8)
            if not crazy and self.act != 4 and now >= w.sil_next:          # Silhouetten wechseln
                pool = SIL_DANCE if self.dance else (SIL_LOOK if self.act == 2 else None)
                w.set_sil(w._pick(pool), now)
                w.sil_next = now + (self.rng.uniform(3.0, 6.0) if self.act == 2 else self.rng.uniform(6.0, 14.0))
            w.tick(now, dt, 0.12 if crazy else 0.45)
            if not crazy and self.act != 4 and w.sat < 0.79 and not self.dance:
                w.sat += (0.8 - w.sat) * min(1.0, dt / 1.0)

    def _doc_tick(self, now: float, dt: float, live: float) -> None:
        cx, cy, cr = self.clock
        ledge = (cx + 0.01, cy - cr * 1.778 * 0.98)                     # Kante unter dem Zifferblatt (Seitenverhältnis 16:9)
        if self.climb_t0 is None and self.act < 3 and self.progress >= self.climb_at:
            self.climb_t0 = now
            log.info("Der Professor klettert auf den Turm")
        vis_t = 0.0
        if self.climb_t0 is not None:
            k = (now - self.climb_t0) / (CLIMB_SECONDS / (4.0 if self.demo else 1.0))
            if k < 1.0:
                (x0, y0), (x1, y1) = CLIMB_PATH
                kk = k + 0.012 * math.sin(k * 60.0)                       # ruckweise: Griff für Griff
                self.doc_pos = (x0 + (x1 - x0) * kk + 0.01 * math.sin(k * 7.0), y0 + (y1 - y0) * kk)
                self.doc_pose = int(k * 40.0) % 8                          # Kletterzyklus (Reihe 0)
            else:
                self.doc_pos = ledge
                if not (self.act == 4 and now >= self.doc_fall_t0) and now >= self.doc_pose_next:
                    pools = {0: (POSE_HANG2, POSE_HANG1, POSE_POINT), 1: (POSE_HANG2, POSE_HANG1, POSE_PULL),
                             2: (POSE_PULL, POSE_PLUG, POSE_POINT, POSE_PULL), 3: (POSE_FEAR, POSE_HANG1, POSE_SLIP),
                             4: (POSE_FEAR, POSE_SLIP)}
                    self.doc_pose = self.rng.choice(pools[self.act])
                    self.doc_pose_next = now + (self.rng.uniform(0.5, 1.0) if self.act == 3 else self.rng.uniform(2.5, 5.0))
            vis_t = 1.0
            if self.act == 4 and now >= self.doc_fall_t0:                  # nach dem Einschlag rutscht er ab und ist weg
                self.doc_pose = POSE_SLIP
                vis_t = 0.0
        self.doc_vis += (vis_t - self.doc_vis) * min(1.0, dt / (0.8 if vis_t > self.doc_vis else 1.2))

    def _car_tick(self, now: float, dt: float) -> None:
        if self.car_start_at is not None and now >= self.car_start_at:
            self.car_start_at = None
            self.drive(now, CAR_WAIT_X - 0.5 * CAR_W)
        if self.car_driving:
            self.car_x += dt * self._car_speed()
            if self.car_x > 1.0 + self._car_speed() * TRAIL_SECONDS:
                self.car_driving = False

    def _pack(self, now: float) -> dict:
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        bolt_age = now - self.bolt_t0
        out = {
            "uSceneSize": size(self.scene), "uSilSize": size(self.sil), "uDocSize": size(self.climber),
            "uHandSize": size(self.hands_tex), "uGearSize": size(self.clockwork), "uCarSize": size(self.car_tex),
            "uSeed": self.seed, "uClock": self.clock, "uCable": self.cable[:4], "uCable2": self.cable[4:6],
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s,
            "uBeatPulse": self.beat_pulse, "uFlash": self.flash, "uHands": self._hands(now), "uClockT": self.progress,
            "uBoltT": bolt_age if bolt_age < STOP_SECONDS + REWIND_SECONDS else -1.0, "uBoltSeed": self.bolt_seed,
            "uCrazy": self.crazy_k, "uGearRot": self.cw_rot, "uStorm": self.storm, "uFinal": self.final_k,
            "uSheet": (now - self.sheet_t0, self.sheet_x, self.sheet_k, 0.0),
            "uFarBolt": (now - self.far_t0, self.far_x, self.far_seed, self.far_k),
            "uSparkT": now - self.spark_t0,
            "uDoc": (float(self.doc_pose), self.doc_vis, 1.0 if self.climb_t0 is not None and
                     (now - self.climb_t0) * (4.0 if self.demo else 1.0) < CLIMB_SECONDS else 0.0, 0.0),
            "uDocPos": (self.doc_pos[0], self.doc_pos[1], 0.0, 0.0),
            "uCar": (self.car_x if self.car_driving else (CAR_WAIT_X - 0.5 * CAR_W if self._car_wait() else -5.0),
                     CAR_Y, CAR_W, 2.0 if self.car_driving and now - self.car_t0 > 0.5 else (0.0 if self.car_driving else 1.0)),
            "uCarT": (now - self.car_t0, self._car_speed(), 1.0 if self.car_driving else 0.0, 0.0),
            "uZoom": max(self.zoom, self.auto_zoom), "uNWin": float(len(self.wins)),
        }
        for i in range(N_WIN):
            if i < len(self.wins):
                w = self.wins[i]
                lvl = w.on * (0.35 + 0.65 * self.bands[w.band]) * (0.6 + 0.4 * self.live_s) + w.flash
                mix = min(1.0, (now - w.sil_t0) / 0.8)
                bob = 0.02 * self.beat_pulse if w.sil_b in SIL_DANCE or w.sil_b in (2, 7, 12, 19) else 0.0
                out[f"uWinA[{i}]"] = w.box
                # .w = gespiegelt (ganzzahlig) + Wippen auf den Beat (Nachkommastelle)
                out[f"uWinB[{i}]"] = (w.hue, w.sat * (1.0 - min(1.0, w.flash)), lvl, (1.0 if w.mirror else 0.0) + min(0.9, bob * 40.0))
                out[f"uWinC[{i}]"] = (float(w.sil_a), float(w.sil_b), mix, w.dx)
            else:
                out[f"uWinA[{i}]"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uWinB[{i}]"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uWinC[{i}]"] = (-1.0, -1.0, 1.0, 0.0)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = [(self.clock_text(now), 0.02, 0.07, 0.04, (255, 225, 170), 0.55)]
        if self.act == 2:
            left = max(0.0, (1.0 - self.progress) / max(1e-6, self._rate()))
            pulse = 0.7 + 0.3 * math.cos(2.0 * math.pi * (left % 1.0))
            out.append((f"22:04 IN 0:{int(math.ceil(left)):02d}", 0.032, 0.5, 0.07, (255, 170, 90), pulse))
        elif self.act == 4 and now - self.bolt_t0 < 3.0:
            a = min(1.0, (3.0 - (now - self.bolt_t0)) / 1.0) * (0.8 + 0.2 * math.sin(t * 40.0))
            out.append(("1,21 GIGAWATT", 0.045, 0.5, 0.5, (235, 240, 255), a))
        return out
