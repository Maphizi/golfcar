"""Der Kern (Taste 3 im Thema CYBERPUNK, Gegenstück zum Schwarzen Loch).

Reaktorkern in einer Serverkathedrale (assets/cyber/core_scene.png). Knüppel links/rechts wirft ein Objekt
(assets/cyber/core_objects.png, 6x4 à 192: Drohne, Schwebeauto, Android, Automat, Logo-Würfel, Katze, Ramen-Stand,
Cyberdeck ...) von dieser Seite hinein: es fliegt ein, wird in Spiralen angesogen, zerfällt dabei in Pixelblöcke und
einen Datenstrom, der im Takt in den Kern läuft (Hue-Verschiebung, Glitch), über etwa 40-60 s.
OBEN = Drohnenschwarm (Perlenkette aus Drohnen), UNTEN = Überlast: der Kern spuckt alles als Trümmer und Lichtbögen
aus (Blitz, Druckwelle, 8 s, laufende Objekte fliegen rückwärts). Startknopf = EMP-Puls (Ring, kurz Schwarzweiß).
Kippschalter = Nahaufnahme. Bass = Kern pulst und Lichtbögen springen, Beat = Ring, Höhen = Funken, Drop = Kern
wechselt Farbe und dreht rückwärts.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("core")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
SLOTS = 3
THROW_SECONDS = (40.0, 60.0)
EJECT_SECONDS = 8.0
EJECT_BURST_AT = 1.2
SWARM_SECONDS = 30.0
EMP_SECONDS = 2.5
NAMES = ["LIEFERDROHNE", "SCHWEBEAUTO", "ANDROID", "AUTOMAT", "KONZERNWÜRFEL", "VISOR-KATZE", "RAMEN-STAND", "CYBERDECK",
         "NEONSCHILD", "MOTORRAD", "WACHROBOTER", "HOLO-KOI", "MÜLLTONNE", "SCHIRM", "ARCADE", "SERVER", "CHROMSCHÄDEL",
         "PILLENDOSE", "SYNTHESIZER", "LATERNE", "KOFFER VOLL EDDIES", "HOVERBIKE", "KAMERA", "NUDELSCHALE"]
CELL_DRONE = 0


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


class Throw:
    def __init__(self, rng: random.Random, cell: int, side: float, now: float):
        self.cell = cell
        self.side = side
        self.t0 = now
        self.dur = rng.uniform(*THROW_SECONDS)
        self.swirl = rng.choice((-1.0, 1.0))
        self.seed = rng.uniform(1.0, 200.0)
        self.y0 = rng.uniform(-0.2, 0.25)
        self.name = NAMES[cell % len(NAMES)]
        self.reverse_t0: float | None = None
        self.reverse_p = 0.0

    def progress(self, now: float) -> float:
        if self.reverse_t0 is not None:
            return self.reverse_p - (now - self.reverse_t0) / self.dur * 4.0
        return (now - self.t0) / self.dur

    def reverse(self, now: float) -> None:
        if self.reverse_t0 is None:
            self.reverse_p = self.progress(now)
            self.reverse_t0 = now

    def done(self, now: float) -> bool:
        p = self.progress(now)
        return p >= 1.0 or p < -0.05


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "core_scene.png")
        self.objects = _load_rgba(ASSETS / "core_objects.png")
        self.center = tuple(float(v) for v in scene_cfg.get("center", [0.5, 0.56]))
        self.radius = float(scene_cfg.get("radius", 0.13))
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.hue = 0.0
        self.hue_target = 0.0
        self.spin_t = 0.0
        self.spin_dir = 1.0
        self.rings: list[float] = []
        self.throws: list[Throw | None] = [None] * SLOTS
        self.last_cells: list[int] = []
        self.swarm_t0: float | None = None
        self.eject_t0: float | None = None
        self.eject_burst_done = False
        self.emp_t0 = -10.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 3.0
        log.info("Der Kern: Szene %s, Objekte %s", "ok" if self.scene is not None else "fehlt", "ok" if self.objects is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def throw(self, side: str) -> None:
        now = time.monotonic()
        slot = next((i for i, th in enumerate(self.throws) if th is None), None)
        if slot is None:
            slot = max(range(SLOTS), key=lambda i: self.throws[i].progress(now))
            if self.throws[slot].progress(now) < 0.6:
                return
        pool = [c for c in range(24) if c not in self.last_cells[-6:]]
        cell = self.rng.choice(pool)
        self.last_cells.append(cell)
        self.throws[slot] = Throw(self.rng, cell, -1.0 if side == "left" else 1.0, now)
        self._led_event("core_throw", now + 3.0)
        log.info("Geworfen: %s von %s", self.throws[slot].name, side)

    def swarm(self) -> None:
        now = time.monotonic()
        if self.swarm_t0 is not None and now - self.swarm_t0 < 5.0:
            return
        self.swarm_t0 = now
        self._led_event("core_throw", now + 3.0)
        log.info("Drohnenschwarm")

    def eject(self) -> None:
        now = time.monotonic()
        if self.eject_t0 is not None and now - self.eject_t0 < EJECT_SECONDS:
            return
        self.eject_t0 = now
        self.eject_burst_done = False
        self._led_event("core_eject", now + EJECT_SECONDS)
        log.info("Überlast: der Kern spuckt aus")

    def emp(self) -> None:
        now = time.monotonic()
        if now - self.emp_t0 < EMP_SECONDS:
            return
        self.emp_t0 = now
        self.rings.append(now)
        self._led_event("core_emp", now + EMP_SECONDS)
        log.info("EMP")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.spin_dir = -self.spin_dir
        self.hue_target = self.rng.choice([-1.5, -0.8, 0.8, 1.5, 2.2])
        self.rings += [now, now + 0.25, now + 0.5]
        log.info("Drop: Kern wechselt Farbe, Richtung")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.throw("left")
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.throw("right")
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.swarm()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.eject()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.emp()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uObjTex": (self.objects if self.objects is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uObjTex", "uSceneSize", "uObjSize", "uSeed", "uCenter", "uRadius", "uBassS", "uMidS", "uHighS",
                 "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uFlash", "uHue", "uSpinT", "uZoom", "uSwarmT", "uEjectT",
                 "uEmpT"]
        names += [f"uRing{i}" for i in range(6)]
        for i in range(SLOTS):
            names += [f"uThrow{i}", f"uThrowPar{i}"]
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
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            self.rings.append(now)
            self.spin_t += 0.3 * self.spin_dir
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
        self.spin_t += dt * self.spin_dir * (0.3 + 2.0 * self.bass_s + 0.5 * self.energy)
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
        if now - self.last_drop > 12.0:
            self.hue_target = 0.0
        self.rings = [r for r in self.rings if now - r < 3.0][-6:]
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        eject_t = -1.0
        if self.eject_t0 is not None:
            eject_t = now - self.eject_t0
            if eject_t >= EJECT_SECONDS:
                self.eject_t0 = None
                eject_t = -1.0
            elif eject_t >= EJECT_BURST_AT and not self.eject_burst_done:
                self.eject_burst_done = True
                for th in self.throws:
                    if th is not None:
                        th.reverse(now)
                self.swarm_t0 = None
                self.rings += [now, now + 0.2, now + 0.4, now + 0.6]
        if self.swarm_t0 is not None and now - self.swarm_t0 > SWARM_SECONDS:
            self.swarm_t0 = None
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("core")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "swarm", "eject", "emp", "drop"))
            {"left": lambda: self.throw("left"), "right": lambda: self.throw("right"), "swarm": self.swarm,
             "eject": self.eject, "emp": self.emp, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 9.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out = {
            "uSceneSize": size(self.scene), "uObjSize": size(self.objects), "uSeed": self.seed, "uCenter": self.center,
            "uRadius": self.radius, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash,
            "uHue": self.hue, "uSpinT": self.spin_t % 1000.0, "uZoom": self.zoom,
            "uSwarmT": (now - self.swarm_t0) if self.swarm_t0 is not None else -1.0, "uEjectT": eject_t,
            "uEmpT": (now - self.emp_t0) if now - self.emp_t0 < EMP_SECONDS else -1.0,
        }
        for i in range(6):
            out[f"uRing{i}"] = max(0.0, now - self.rings[i]) if i < len(self.rings) else 99.0
        for i, th in enumerate(self.throws):
            if th is not None and th.done(now):
                log.info("%s %s", th.name, "ausgespuckt" if th.reverse_t0 else "vom Kern verschluckt")
                self.throws[i] = th = None
            if th is None:
                out[f"uThrow{i}"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uThrowPar{i}"] = (0.0, 0.0, 0.0, 0.0)
            else:
                out[f"uThrow{i}"] = (max(0.0, min(1.0, th.progress(now))), float(th.cell), th.side, th.seed)
                out[f"uThrowPar{i}"] = (th.swirl, 1.0 if th.reverse_t0 else 0.0, th.y0, 0.0)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        y = 0.05
        for th in self.throws:
            if th is None:
                continue
            p = th.progress(now)
            a = 0.75 * min(1.0, max(0.0, p) * 8.0) * min(1.0, (1.0 - p) * 6.0)
            if th.reverse_t0 is not None:
                label = f"{th.name}  -  WIRD AUSGESPUCKT"
            else:
                label = f"{th.name}  -  {int(p * 100):02d} % DEKOMPILIERT" if p > 0.2 else f"{th.name}  -  WIRD ERFASST"
            out.append((label, 0.018, 0.5, y, (120, 230, 255), a))
            y += 0.035
        if self.eject_t0 is not None:
            et = now - self.eject_t0
            a = min(1.0, et / 0.6) * min(1.0, (EJECT_SECONDS - et) / 1.5)
            out.append(("Ü B E R L A S T", 0.05, 0.5, 0.5, (255, 80, 220), 0.85 * a))
        if now - self.emp_t0 < 1.2:
            out.append(("E M P", 0.04, 0.5, 0.5, (220, 240, 255), 1.0 - (now - self.emp_t0) / 1.2))
        return out
