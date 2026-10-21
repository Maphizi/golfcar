"""Moorsee (Taste 3 im Thema THE POWER OF THE GREEN, Gegenstück zum Schwarzen Loch).

Ein Waldsee bei Nacht (assets/pond/lake.png) mit Strudel in der Mitte. Steuerknüppel LINKS/RECHTS wirft ein
Wesen der Speisekarte (assets/trip/beings.png) in den See: Platscher, kurzes Treiben, dann zieht der
Strudel es in Spiralen nach innen, dabei wird es zu einem immer längeren Band gestreckt, das schlangenförmig
zur Musik wogt, bis es im Trichter verschwindet (Luftblasen steigen auf). OBEN = Blätterregen (Blätter
fallen, drehen sich im Strudel zur Spirale). UNTEN = Umkehrung: der See bäumt sich auf, eine Fontäne
schleudert alles zurück, Wellen laufen zum Ufer, der Nebel reißt auf und kurz liegt der leuchtende
Seegrund frei (assets/pond/bottom.png). Startknopf = Stein hüpft über das Wasser (Ringe). Kippschalter =
Nahaufnahme in den Strudel.
Musik: Bass dreht den Strudel und lässt Nebel und Mondspiegelung atmen, jeder Beat wirft einen Ring aufs
Wasser, Drops lassen das ganze Wasser aufleuchten, Höhen funkeln als Glühwürmchen und Tautropfen.
"""
from __future__ import annotations

import logging
import math
import random
import time

import numpy as np
import pygame

from launcher import config as lcfg

log = logging.getLogger("pond")
ASSETS = lcfg.ROOT / "assets" / "pond"
TRIP_ASSETS = lcfg.ROOT / "assets" / "trip"
SLOTS = 2
THROW_SECONDS = (40.0, 60.0)
EJECT_SECONDS = 9.0
EJECT_BURST_AT = 1.5
LEAF_SECONDS = 45.0
# Zellen im Atlas assets/pond/creatures.png (6 x 4, Index = Reihe*6 + Spalte)
LEAVES = [13, 3, 2, 13]
STONE = 6
FOUNTAIN = [5, 7, 8, 9, 12, 16, 18, 10, 11, 20, 22, 23, 1, 4, 15, 19]
BUBBLES = [20, 22, 23]


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
    def __init__(self, rng: random.Random, being: dict, side: str, now: float):
        self.being = being
        self.name = str(being.get("name", "?")).upper()
        self.cell = float(being.get("cell", 0))
        self.t0 = now
        self.dur = rng.uniform(*THROW_SECONDS)
        self.side = -1.0 if side == "left" else 1.0
        self.seed = rng.uniform(1.0, 100.0)
        self.swirl = rng.choice((-1.0, 1.0))
        self.reverse_t0: float | None = None
        self.reverse_p = 0.0

    def progress(self, now: float) -> float:
        if self.reverse_t0 is not None:
            return self.reverse_p - (now - self.reverse_t0) / self.dur * 3.0
        return (now - self.t0) / self.dur

    def reverse(self, now: float) -> None:
        if self.reverse_t0 is None:
            self.reverse_p = min(1.0, self.progress(now))
            self.reverse_t0 = now

    def done(self, now: float) -> bool:
        p = self.progress(now)
        return p >= 1.0 or (self.reverse_t0 is not None and p <= 0.0)


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.lake = _load_rgba(ASSETS / "lake.png")
        self.bottom = _load_rgba(ASSETS / "bottom.png")
        self.creatures = _load_rgba(ASSETS / "creatures.png")
        self.beings_tex = _load_rgba(TRIP_ASSETS / "beings.png")
        try:
            self.beings = [b for b in lcfg._load("trip.toml").get("beings", []) if b.get("name")]
        except Exception:
            self.beings = []
        if not self.beings:
            self.beings = [{"name": "FROSCH", "cell": 7}]
        self.vortex = tuple(float(v) for v in scene_cfg.get("vortex", [0.56, 0.30]))
        self.water = tuple(float(v) for v in scene_cfg.get("water", [0.14, 0.52, 0.18, 0.9]))   # y unten, y oben, x links, x rechts
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = 0.0
        self.mid_s = 0.0
        self.high_s = 0.0
        self.energy = 0.0
        self.swirl_t = 0.0
        self.snake_t = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.flash = 0.0
        self.last_beat = 0.0
        self.rings: list[tuple[float, float, float]] = []     # (x, y, t0)
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = 0.0
        self.throws: list[Throw | None] = [None] * SLOTS
        self.last_names: list[str] = []
        self.leaf_t0: float | None = None
        self.leaf_seed = 0.0
        self.eject_t0: float | None = None
        self.eject_burst_done = False
        self.stone_t0 = -10.0
        self.stone_side = 1.0
        self.stone_rings_done = 0
        self.demo_next = time.monotonic() + 4.0
        log.info("Moorsee: See %s, Grund %s, Wesen %d", "ok" if self.lake is not None else "fehlt",
                 "ok" if self.bottom is not None else "fehlt", len(self.beings))

    # -- Aktionen ----------------------------------------------------------
    def throw(self, side: str) -> None:
        now = time.monotonic()
        slot = next((i for i, th in enumerate(self.throws) if th is None), None)
        if slot is None:
            slot = max(range(SLOTS), key=lambda i: self.throws[i].progress(now))
            if self.throws[slot].progress(now) < 0.6:
                return
        active = {th.name for th in self.throws if th}
        pool = [b for b in self.beings if str(b.get("name", "")).upper() not in active and b.get("name") not in self.last_names[-5:]]
        being = self.rng.choice(pool or self.beings)
        self.last_names.append(being.get("name"))
        self.throws[slot] = Throw(self.rng, being, side, now)
        self.rings.append((self.vortex[0] + self.throws[slot].side * 0.22, self.vortex[1] + 0.05, now + 0.7))
        log.info("Geworfen: %s von %s", self.throws[slot].name, side)

    def leaf_rain(self) -> None:
        now = time.monotonic()
        if self.leaf_t0 is not None and now - self.leaf_t0 < LEAF_SECONDS * 0.7:
            return
        self.leaf_t0 = now
        self.leaf_seed = self.rng.random()
        log.info("Blätterregen")

    def eject(self) -> None:
        now = time.monotonic()
        if self.eject_t0 is not None and now - self.eject_t0 < EJECT_SECONDS:
            return
        self.eject_t0 = now
        self.eject_burst_done = False
        log.info("Umkehrung: der See spuckt aus")

    def skip_stone(self) -> None:
        now = time.monotonic()
        if now - self.stone_t0 < 3.0:
            return
        self.stone_t0 = now
        self.stone_side = self.rng.choice((-1.0, 1.0))
        self.stone_rings_done = 0

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.throw("left")
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.throw("right")
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.leaf_rain()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.eject()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.skip_stone()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uLakeTex": (self.lake if self.lake is not None else self.blank, 1),
                "uBottomTex": (self.bottom if self.bottom is not None else self.blank, 1),
                "uCreatureTex": (self.creatures if self.creatures is not None else self.blank, 1),
                "uBeingsTex": (self.beings_tex if self.beings_tex is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uLakeTex", "uBottomTex", "uCreatureTex", "uBeingsTex", "uLakeSize", "uCreatureSize", "uBeingsSize",
                 "uSeed", "uVortex", "uWater", "uBassS", "uMidS", "uHighS", "uEnergy", "uSwirlT", "uSnakeT", "uZoom",
                 "uFlash", "uLeaf", "uLeafSeed", "uEjectT", "uStone", "uStoneSide", "uLeafCells", "uBubbleCells"]
        names += [f"uRing{i}" for i in range(6)]
        for i in range(SLOTS):
            names += [f"uThrow{i}", f"uThrowPar{i}"]
        names += [f"uFountain{i}" for i in range(4)]
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
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.2)
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.4)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.15)
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        # Beat: Ring am Strudel
        if beat > 0.5 and now - self.last_beat > 0.3:
            self.last_beat = now
            self.rings.append((self.vortex[0], self.vortex[1], now))
        # Drop: Wasser leuchtet auf
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 10.0:
            self.drop_armed = False
            self.last_drop = now
            self.flash = 1.0
        self.flash = max(0.0, self.flash - dt / 2.5)
        self.rings = [r for r in self.rings if now - r[2] < 4.0][-6:]
        # Strudel und Schlangenwellen
        self.swirl_t += dt * (0.35 + 1.2 * self.bass_s + 0.3 * self.energy)
        self.snake_t += dt * (0.3 + 1.0 * self.bass_s)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 2.0)
        # Stein: Ringe bei jedem Aufsetzen
        st = now - self.stone_t0
        if 0.0 <= st < 2.4:
            hops = int(st / 0.6)
            while self.stone_rings_done <= hops and self.stone_rings_done < 4:
                k = self.stone_rings_done
                x = self.vortex[0] + self.stone_side * (0.34 - k * 0.11)
                self.rings.append((x, self.vortex[1] + 0.06 - k * 0.015, now))
                self.stone_rings_done += 1
        # Umkehrung
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
                self.leaf_t0 = None
                for k in range(5):
                    self.rings.append((self.vortex[0], self.vortex[1], now + k * 0.35))
        if self.leaf_t0 is not None and now - self.leaf_t0 > LEAF_SECONDS:
            self.leaf_t0 = None
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "leaf", "eject", "stone"))
            {"left": lambda: self.throw("left"), "right": lambda: self.throw("right"), "leaf": self.leaf_rain,
             "eject": self.eject, "stone": self.skip_stone}[pick]()
            self.demo_next = now + 10.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out = {
            "uLakeSize": size(self.lake), "uCreatureSize": size(self.creatures), "uBeingsSize": size(self.beings_tex),
            "uSeed": self.seed, "uVortex": self.vortex, "uWater": self.water,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uSwirlT": self.swirl_t % 1000.0, "uSnakeT": self.snake_t % 1000.0, "uZoom": self.zoom, "uFlash": self.flash,
            "uLeaf": ((now - self.leaf_t0) / LEAF_SECONDS) if self.leaf_t0 is not None else 0.0, "uLeafSeed": self.leaf_seed,
            "uEjectT": eject_t, "uStone": st if 0.0 <= st < 2.4 else -1.0, "uStoneSide": self.stone_side,
            "uLeafCells": tuple(float(v) for v in LEAVES), "uBubbleCells": (float(BUBBLES[0]), float(BUBBLES[1]), float(BUBBLES[2]), float(STONE)),
        }
        for i in range(6):
            if i < len(self.rings):
                x, y, t0 = self.rings[i]
                out[f"uRing{i}"] = (x, y, max(0.0, now - t0), 1.0)
            else:
                out[f"uRing{i}"] = (0.0, 0.0, 99.0, 0.0)
        for i, th in enumerate(self.throws):
            if th is not None and th.done(now):
                log.info("%s %s", th.name, "wieder ausgespuckt" if th.reverse_t0 else "vom Strudel verschluckt")
                self.throws[i] = th = None
            if th is None:
                out[f"uThrow{i}"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uThrowPar{i}"] = (0.0, 0.0, 0.0, 0.0)
            else:
                out[f"uThrow{i}"] = (max(0.0, min(1.0, th.progress(now))), th.cell, th.side, th.seed)
                out[f"uThrowPar{i}"] = (th.swirl, 1.0 if th.reverse_t0 else 0.0, 0.0, 0.0)
        for i in range(4):
            out[f"uFountain{i}"] = tuple(float(FOUNTAIN[i * 4 + k]) for k in range(4))
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
                label = f"{th.name}  -  WIRD ZERRISSEN" if p > 0.5 else (f"{th.name}  -  TREIBT" if p > 0.08 else f"{th.name}  -  PLATSCH")
            out.append((label, 0.018, 0.5, y, (170, 230, 190), a))
            y += 0.035
        if self.eject_t0 is not None:
            et = now - self.eject_t0
            a = min(1.0, et / 0.6) * min(1.0, (EJECT_SECONDS - et) / 1.5)
            out.append(("D E R   S E E   S P U C K T   A U S", 0.04, 0.5, 0.5, (220, 245, 230), 0.85 * a))
        return out
