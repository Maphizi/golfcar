"""Neonfahrt (Taste 2 im Thema CYBERPUNK, Gegenstück zum Navigationscomputer).

Fahrt durch die Regenstadt aus der Windschutzscheibe (assets/cyber/neonrace_scene.png). Startknopf = losfahren, die
Fahrt endet NUR per Kippschalter (SPACE/BACKSPACE = anhalten). Tempo folgt der Energie der Musik (Lichtstreifen,
Regen schräger, Hologramme ziehen schneller vorbei), Bass = Motorvibration, Beat = Schilder und Hologramme blitzen,
Höhen = Regentropfen funkeln, Mitten = Scheibenwischer. Drop = Nitro (Lichttunnel, Farben kippen).
Knüppel links/rechts = Spurwechsel, oben = Lichthupe (alle Schilder blitzen), unten = Rückspiegel (Verfolger).
Ereignisse alle 30-60 s (EVENTS): Polizeidrohnen, Werbeblimp, Regensturm, Tunnel, Konzernturm, Straßenmarkt,
Kirschblütenallee. Hologramme assets/cyber/neonrace_holo.png (8x3 à 160), Verkehr neonrace_traffic.png (8x2 à 192:
Reihe 0 Fahrzeuge, Reihe 1 Flieger).
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("neonrace")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
N_HOLO, N_CARS, N_FLY = 10, 6, 6
EVENT_EVERY = (30.0, 60.0)
EVENTS = [
    ("POLIZEIDROHNEN", 14.0, "ROT UND BLAU IM RÜCKSPIEGEL"),
    ("WERBEBLIMP", 16.0, "ER VERKAUFT DIR DEIN EIGENES LEBEN"),
    ("REGENSTURM", 14.0, "WISCHER AUF ANSCHLAG"),
    ("TUNNEL", 12.0, "LICHT IN STREIFEN"),
    ("KONZERNTURM", 14.0, "DER TURM SIEHT ALLES"),
    ("STRASSENMARKT", 16.0, "RAMEN, PILLEN, KATZEN"),
    ("KIRSCHBLÜTENALLEE", 14.0, "ROSA IM REGEN"),
]
EV_DRONES, EV_BLIMP, EV_STORM, EV_TUNNEL, EV_TOWER, EV_MARKET, EV_BLOSSOM = range(7)
CAR_CELLS, FLY_CELLS = list(range(8)), list(range(8, 16))
CELL_POLICE, CELL_BLIMP, CELL_DRONE, CELL_BLOSSOM, CELL_GLIDER = 4, 9, 8, 12, 10


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


class Mover:
    """Etwas, das von weit hinten (z=0) auf die Kamera zukommt (z=1): Hologramm am Straßenrand, Auto, Flieger."""

    def __init__(self, rng: random.Random, cell: int, side: float, lane: float, speed: float, kind: int, now: float):
        self.cell, self.side, self.lane, self.kind = cell, side, lane, kind
        self.z = 0.0
        self.speed = speed
        self.seed = rng.random()
        self.born = now
        self.hue = rng.random()


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "neonrace_scene.png")
        self.holo = _load_rgba(ASSETS / "neonrace_holo.png")
        self.traffic = _load_rgba(ASSETS / "neonrace_traffic.png")
        self.vanish = tuple(float(v) for v in scene_cfg.get("vanish", [0.5, 0.5]))
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
        self.nitro = 0.0
        self.driving = False
        self.speed = 0.0
        self.dist = 0.0
        self.lane = 0.0
        self.lane_target = 0.0
        self.honk_t0 = -10.0
        self.mirror = False
        self.mirror_k = 0.0
        self.wiper_t = 0.0
        self.event: dict | None = None
        self.next_event_at = 0.0
        self.holos: list[Mover | None] = [None] * N_HOLO
        self.cars: list[Mover | None] = [None] * N_CARS
        self.flyers: list[Mover | None] = [None] * N_FLY
        self.started_at = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 3.0
        if demo:
            self.start()
        log.info("Neonfahrt: Szene %s, Hologramme %s, Verkehr %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.holo is not None else "fehlt", "ok" if self.traffic is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def start(self) -> None:
        if self.driving:
            return
        self.driving = True
        now = time.monotonic()
        self.started_at = now
        self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.3 if self.demo else 0.7)
        self._led_event("neonrace_start", now + 3.0)
        log.info("Losgefahren")

    def stop(self) -> None:
        if not self.driving:
            return
        self.driving = False
        self.event = None
        secs = int(time.monotonic() - self.started_at)
        log.info("Angehalten nach %d:%02d", secs // 60, secs % 60)
        wled.apply_mode_async("neonrace")

    def change_lane(self, d: float) -> None:
        self.lane_target = max(-1.0, min(1.0, self.lane_target + d))

    def honk(self) -> None:
        self.honk_t0 = time.monotonic()
        self._led_event("neonrace_honk", self.honk_t0 + 1.5)

    def toggle_mirror(self) -> None:
        self.mirror = not self.mirror

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.nitro = 1.0
        self._led_event("neonrace_nitro", now + 3.0)
        log.info("Drop: Nitro")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.start()
        elif ev.key in (pygame.K_SPACE, pygame.K_BACKSPACE):
            self.stop()
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self.change_lane(-1.0)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.change_lane(1.0)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.honk()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_mirror()

    # -- Verkehr -----------------------------------------------------------
    def _spawn(self, now: float) -> None:
        ev = self.event["kind"] if self.event else -1
        rate = 0.4 + 2.0 * self.speed
        if self.rng.random() < rate * 0.05 * (2.5 if ev == EV_MARKET else 1.0):
            i = next((k for k, m in enumerate(self.holos) if m is None), None)
            if i is not None:
                cell = CELL_BLOSSOM if ev == EV_BLOSSOM and self.rng.random() < 0.0 else self.rng.randrange(24)
                self.holos[i] = Mover(self.rng, cell, self.rng.choice((-1.0, 1.0)), 0.0, self.rng.uniform(0.8, 1.2), 0, now)
        if self.rng.random() < rate * 0.025:
            i = next((k for k, m in enumerate(self.cars) if m is None), None)
            if i is not None:
                cell = CELL_POLICE if ev == EV_DRONES and self.rng.random() < 0.5 else self.rng.choice(CAR_CELLS)
                self.cars[i] = Mover(self.rng, cell, 0.0, self.rng.choice((-1.0, 0.0, 1.0)), self.rng.uniform(0.3, 0.7), 1, now)
        fly_rate = rate * 0.02 * (3.0 if ev in (EV_DRONES, EV_BLOSSOM) else 1.0)
        if self.rng.random() < fly_rate:
            i = next((k for k, m in enumerate(self.flyers) if m is None), None)
            if i is not None:
                if ev == EV_DRONES:
                    cell = self.rng.choice((CELL_DRONE, CELL_GLIDER, 14))
                elif ev == EV_BLOSSOM:
                    cell = CELL_BLOSSOM
                elif ev == EV_BLIMP:
                    cell = self.rng.choice((CELL_BLIMP, 15))
                else:
                    cell = self.rng.choice(FLY_CELLS)
                self.flyers[i] = Mover(self.rng, cell, self.rng.uniform(-1.0, 1.0), self.rng.uniform(0.2, 1.0), self.rng.uniform(0.5, 1.0), 2, now)

    def _advance_movers(self, dt: float) -> None:
        for lst in (self.holos, self.cars, self.flyers):
            for k, m in enumerate(lst):
                if m is None:
                    continue
                rel = self.speed * m.speed if m.kind != 1 else max(0.05, self.speed - 0.3 * m.speed) * 0.8
                m.z += dt * rel * 0.5
                if m.z >= 1.0:
                    lst[k] = None

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uHoloTex": (self.holo if self.holo is not None else self.blank, 1),
                "uTrafficTex": (self.traffic if self.traffic is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uHoloTex", "uTrafficTex", "uSceneSize", "uHoloSize", "uTrafficSize", "uSeed", "uVanish",
                 "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uSpeed", "uDist", "uLane",
                 "uHonkT", "uMirror", "uWiperT", "uNitro", "uEvent", "uEventT", "uEventLen", "uDriving"]
        names += [f"uHolo{i}" for i in range(N_HOLO)]
        names += [f"uCar{i}" for i in range(N_CARS)]
        names += [f"uFly{i}" for i in range(N_FLY)]
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
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 10.0 and self.driving:
            self.drop_armed = False
            self.last_drop = now
            self._drop(now)
        self.nitro = max(0.0, self.nitro - dt / 3.0)
        # Tempo: Energie der Musik, Nitro, Stillstand ohne Fahrt
        target = (0.25 + 0.75 * self.energy + 0.5 * self.nitro) if self.driving else 0.0
        if self.driving and live < 0.5:
            target = 0.12
        self.speed += (target - self.speed) * min(1.0, dt / (1.5 if target > self.speed else 2.5))
        self.dist += dt * self.speed
        self.lane += (self.lane_target - self.lane) * min(1.0, dt / 0.8)
        storm = self.event is not None and self.event["kind"] == EV_STORM
        self.wiper_t += dt * (0.5 + 2.5 * self.mid_s + (2.0 if storm else 0.0)) * (1.0 if self.driving else 0.3)
        self.mirror_k += ((1.0 if self.mirror else 0.0) - self.mirror_k) * min(1.0, dt / 0.4)
        if self.driving:
            self._spawn(now)
            self._advance_movers(dt)
            ev = self.event
            if ev is None and now >= self.next_event_at:
                kind = self.rng.randrange(len(EVENTS))
                self.event = {"kind": kind, "t0": now, "len": EVENTS[kind][1]}
                log.info("Ereignis: %s", EVENTS[kind][0])
                if kind == EV_DRONES:
                    self._led_event("neonrace_police", now + EVENTS[kind][1])
            elif ev is not None and now - ev["t0"] >= ev["len"]:
                self.event = None
                self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.3 if self.demo else 1.0)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("neonrace")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "honk", "mirror", "drop"))
            {"left": lambda: self.change_lane(-1.0), "right": lambda: self.change_lane(1.0), "honk": self.honk,
             "mirror": self.toggle_mirror, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 6.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        ev = self.event
        out = {
            "uSceneSize": size(self.scene), "uHoloSize": size(self.holo), "uTrafficSize": size(self.traffic),
            "uSeed": self.seed, "uVanish": self.vanish, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uSpeed": self.speed, "uDist": self.dist % 1000.0, "uLane": self.lane,
            "uHonkT": (now - self.honk_t0) if now - self.honk_t0 < 1.5 else -1.0, "uMirror": self.mirror_k,
            "uWiperT": self.wiper_t % 1000.0, "uNitro": self.nitro, "uDriving": 1.0 if self.driving else 0.0,
            "uEvent": float(ev["kind"] + 1) if ev else 0.0, "uEventT": (now - ev["t0"]) if ev else 0.0,
            "uEventLen": ev["len"] if ev else 1.0,
        }
        for name, lst in (("uHolo", self.holos), ("uCar", self.cars), ("uFly", self.flyers)):
            for i, m in enumerate(lst):
                if m is None:
                    out[f"{name}{i}"] = (0.0, 0.0, -1.0, 0.0)
                else:
                    out[f"{name}{i}"] = (float(m.cell), m.side if m.kind != 1 else m.lane, m.z, m.seed)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if not self.driving:
            out.append(("N E O N F A H R T", 0.05, 0.5, 0.62, (255, 60, 200), 0.7 + 0.3 * np.sin(t * 2.0)))
            out.append(("STARTKNOPF = LOSFAHREN      KIPPSCHALTER = ANHALTEN", 0.02, 0.5, 0.55, (120, 220, 255), 0.7))
        else:
            secs = int(now - self.started_at)
            kmh = int(40 + 260 * self.speed)
            out.append((f"{kmh} KM/H     {secs // 60}:{secs % 60:02d}     SPUR {int(round(self.lane)) + 2}", 0.02, 0.5, 0.04, (120, 220, 255), 0.6))
            if self.event:
                name, length, line = EVENTS[self.event["kind"]]
                k = (now - self.event["t0"]) / length
                a = min(1.0, k * 6.0) * min(1.0, (1.0 - k) * 6.0)
                out.append((name, 0.03, 0.5, 0.92, (255, 60, 200), 0.9 * a))
                out.append((line, 0.018, 0.5, 0.88, (200, 240, 255), 0.8 * a))
            if self.nitro > 0.3:
                out.append(("N I T R O", 0.06, 0.5, 0.5, (255, 255, 120), self.nitro * (0.5 + 0.5 * np.sin(t * 20.0))))
            if now - self.honk_t0 < 1.2:
                out.append(("LICHTHUPE", 0.025, 0.5, 0.12, (255, 255, 200), 1.0 - (now - self.honk_t0) / 1.2))
        return out
