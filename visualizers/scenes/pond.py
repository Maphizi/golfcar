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

from visualizers.engine import images

from launcher import config as lcfg

log = logging.getLogger("pond")
ASSETS = lcfg.ROOT / "assets" / "pond"
TRIP_ASSETS = lcfg.ROOT / "assets" / "trip"
SLOTS = 2
THROW_SECONDS = (40.0, 60.0)
EJECT_SECONDS = 9.0
EJECT_BURST_AT = 1.5
LEAF_SECONDS = 45
# Uferleben: assets/pond/shore.png (4x6 à 192: Spalte = Stufe Keim/jung/voll/verwelkt, Reihe = Art: 0 Fliegenpilze, 1 Farn,
# 2 Leuchtpilze, 3 Lotus, 4 Schilf mit Libelle, 5 Fleischfresser). Plätze: (x, Fußlinie y, Größe, Seite -1/1, im Wasser)
SHORE = [(0.07, 0.30, 0.21, -1, 0), (0.13, 0.19, 0.19, -1, 0), (0.05, 0.42, 0.17, -1, 0), (0.19, 0.12, 0.20, -1, 0),
         (0.30, 0.17, 0.15, -1, 1), (0.87, 0.30, 0.21, 1, 0), (0.82, 0.19, 0.19, 1, 0), (0.91, 0.41, 0.17, 1, 0),
         (0.76, 0.12, 0.20, 1, 0), (0.72, 0.17, 0.15, 1, 1)]
N_SHORE = len(SHORE)
AUTO_PER_SIDE = 2                              # von selbst höchstens so viele Pflanzen je Ufer, der Rest kommt per Knüppel
AUTO_PLANT = (8.0, 20.0)                       # Abstand der Keime von selbst (s, durch die Energie geteilt)
SPROUT_RATE = 0.7                              # Wachstum je s nach Knüppel (Stufe 0 -> 2 in ~3 s), sonst mit der Energie
WATER_SPECIES, BANK_SPECIES = (3, 4), (0, 1, 2, 5)
AUTO_THROW = (50.0, 100.0)            # Wesen fallen nur noch selten von selbst in den Strudel.0
# Zellen im Atlas assets/pond/creatures.png (6 x 4, Index = Reihe*6 + Spalte)
LEAVES = [13, 3, 2, 13]
STONE = 6
FOUNTAIN = [5, 7, 8, 9, 12, 16, 18, 10, 11, 20, 22, 23, 1, 4, 15, 19]
BUBBLES = [20, 22, 23]


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


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
        self.beat_pulse = 0.0                # klingt nach jedem Beat ab: Beben, Schaumsprung, Glühen
        self.beat_step = 0                   # Beat-Zähler: Schaumspiralen springen im Takt weiter
        self.quake_t0 = -10.0
        self.rings: list[tuple[float, float, float]] = []     # (x, y, t0)
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = 0.0
        self.throws: list[Throw | None] = [None] * SLOTS
        self.last_names: list[str] = []
        self.shore_tex = _load_rgba(ASSETS / "shore.png")
        self.plant_species = [0] * N_SHORE
        self.plant_stage = [0.0] * N_SHORE         # 0 Keim .. 2 voll .. 3 verwelkt; -1 = leer
        self.plant_alive = [False] * N_SHORE
        self.plant_seed = [self.rng.random() for _ in range(N_SHORE)]
        self.plant_rate = [1.0] * N_SHORE
        self.plant_t0 = [-10.0] * N_SHORE          # Startzeit (Sprießfunken im Shader)
        self.plant_fast = [False] * N_SHORE        # per Knüppel: wächst schnell, unabhängig von der Musik
        self.plant_next = time.monotonic() + 2.0
        self.spore_t0 = -10.0
        self.auto_throw_at = time.monotonic() + self.rng.uniform(*AUTO_THROW)
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

    def sprout(self, side: int) -> None:
        """Knüppel: auf dieser Seite sprießt sofort etwas Neues (leerer Platz, sonst der älteste wird ersetzt) und wächst
        in ~3 s mit Funken hoch; die anderen Pflanzen der Seite bekommen einen Schub."""
        now = time.monotonic()
        mine = [i for i in range(N_SHORE) if SHORE[i][3] == side]
        cands = [i for i in mine if not self.plant_alive[i]]
        if cands:
            i = self.rng.choice(cands)
        else:                                                           # alles belegt: die am weitesten entwickelte neu
            i = max(mine, key=lambda k: (self.plant_stage[k], -self.plant_t0[k]))
        self._plant_start(i, now, fast=True)
        for k in mine:
            if k != i and self.plant_alive[k] and self.plant_stage[k] < 2.0:
                self.plant_stage[k] = min(2.0, self.plant_stage[k] + 0.5)
        self.spore_t0 = now
        log.info("Es sprießt: %s %s", ("Fliegenpilze", "Farn", "Leuchtpilze", "Lotus", "Schilf", "Fleischfresser")[self.plant_species[i]],
                 "links" if side < 0 else "rechts")

    def _plant_start(self, i: int, now: float, fast: bool = False) -> None:
        pool = WATER_SPECIES if SHORE[i][4] else BANK_SPECIES
        self.plant_species[i] = self.rng.choice(pool)
        self.plant_stage[i] = 0.0
        self.plant_alive[i] = True
        self.plant_seed[i] = self.rng.random()
        self.plant_rate[i] = self.rng.uniform(0.7, 1.4)
        self.plant_t0[i] = now
        self.plant_fast[i] = fast

    def _plants_tick(self, now: float, dt: float, live: float, on_beat: bool) -> None:
        """Pflanzen wachsen mit der Energie der Musik, stehen voll da, verwelken; in der Stille welkt alles langsam."""
        alive = [i for i in range(N_SHORE) if self.plant_alive[i]]
        grow = 0.03 + 0.22 * self.energy + 0.08 * self.bass_s
        for i in alive:
            st = self.plant_stage[i]
            r = self.plant_rate[i]
            if self.plant_fast[i] and st < 2.0:                        # per Knüppel: schnell hoch, auch ohne Musik
                self.plant_stage[i] = min(2.0, st + dt * SPROUT_RATE)
            elif live < 0.3:
                self.plant_stage[i] = min(3.0, st + dt * 0.08 * r) if st >= 2.0 else st + dt * 0.03 * r
            elif st < 2.0:
                self.plant_stage[i] = min(2.0, st + dt * grow * r)
            else:                                                     # voll: hält, welkt dann langsam
                hold = 12.0 + 20.0 * self.energy
                self.plant_stage[i] = min(3.0, st + dt * r / hold)
            if self.plant_stage[i] >= 3.0:
                self.plant_alive[i] = False
        # neue Keime von selbst: selten und je Ufer höchstens AUTO_PER_SIDE, damit der Knüppel Platz hat
        if live > 0.3 and now >= self.plant_next:
            self.plant_next = now + self.rng.uniform(*AUTO_PLANT) / (0.5 + 1.0 * self.energy)
            empty = [i for i in range(N_SHORE) if not self.plant_alive[i]
                     and sum(1 for k in alive if SHORE[k][3] == SHORE[i][3]) < AUTO_PER_SIDE]
            if empty and self.rng.random() < 0.3 + 0.7 * self.energy:
                self._plant_start(self.rng.choice(empty), now)
        if on_beat and self.rng.random() < 0.2 + 0.4 * self.bass_s:
            self.spore_t0 = now

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
            self.sprout(-1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.sprout(1)
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
                "uBeingsTex": (self.beings_tex if self.beings_tex is not None else self.blank, 1),
                "uShoreTex": (self.shore_tex if self.shore_tex is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uLakeTex", "uBottomTex", "uCreatureTex", "uBeingsTex", "uLakeSize", "uCreatureSize", "uBeingsSize",
                 "uSeed", "uVortex", "uWater", "uBassS", "uMidS", "uHighS", "uEnergy", "uSwirlT", "uSnakeT", "uZoom",
                 "uFlash", "uLeaf", "uLeafSeed", "uEjectT", "uStone", "uStoneSide", "uLeafCells", "uBubbleCells",
                 "uBeatPulse", "uBeatStep", "uQuakeT", "uShoreTex", "uShoreSize", "uSporeT"]
        names += [f"uPlant{i}" for i in range(N_SHORE)]
        names += [f"uPlantS{i}" for i in range(N_SHORE)]
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
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            if self.beat_step % 4 == 0 or bass > 0.75:                  # Druckwelle nur bei jedem 4. oder kräftigen Beat
                self.quake_t0 = now
            self.swirl_t += 0.2 * beat                                   # Drehstoß
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
            for i in range(N_SHORE):                                  # Drop: das ganze Ufer blüht
                if not self.plant_alive[i]:
                    self._plant_start(i, now)
                    self.plant_stage[i] = 1.2
                elif self.plant_stage[i] < 2.0:
                    self.plant_stage[i] = 1.8
            self.spore_t0 = now
        self.flash = max(0.0, self.flash - dt / 2.5)
        self.rings = [r for r in self.rings if now - r[2] < 4.0][-6:]
        # Strudel und Schlangenwellen
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        self._plants_tick(now, dt, live, beat > 0.5 and now - self.last_beat < 0.05)
        if now >= self.auto_throw_at:                                  # selten fällt ein Wesen von selbst hinein
            self.auto_throw_at = now + self.rng.uniform(*AUTO_THROW)
            if live and self.energy > 0.3:
                self.throw(self.rng.choice(("left", "right")))
        self.swirl_t += dt * (0.4 + 2.6 * self.bass_s + 0.6 * self.energy + 1.5 * self.beat_pulse)
        self.snake_t += dt * (0.3 + 1.6 * self.bass_s + 0.8 * self.beat_pulse)
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
            pick = self.rng.choice(("left", "right", "leaf", "eject", "stone", "throw"))
            {"left": lambda: self.sprout(-1), "right": lambda: self.sprout(1), "leaf": self.leaf_rain, "throw": lambda: self.throw("left"),
             "eject": self.eject, "stone": self.skip_stone}[pick]()
            self.demo_next = now + 10.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out = {
            "uLakeSize": size(self.lake), "uCreatureSize": size(self.creatures), "uBeingsSize": size(self.beings_tex),
            "uSeed": self.seed, "uVortex": self.vortex, "uWater": self.water,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uSwirlT": self.swirl_t % 1000.0, "uSnakeT": self.snake_t % 1000.0, "uZoom": self.zoom, "uFlash": self.flash,
            "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uQuakeT": min(9.0, now - self.quake_t0),
            "uLeaf": ((now - self.leaf_t0) / LEAF_SECONDS) if self.leaf_t0 is not None else 0.0, "uLeafSeed": self.leaf_seed,
            "uEjectT": eject_t, "uStone": st if 0.0 <= st < 2.4 else -1.0, "uStoneSide": self.stone_side,
            "uLeafCells": tuple(float(v) for v in LEAVES), "uBubbleCells": (float(BUBBLES[0]), float(BUBBLES[1]), float(BUBBLES[2]), float(STONE)),
            "uShoreSize": size(self.shore_tex), "uSporeT": min(5.0, now - self.spore_t0),
        }
        for i, (x, y, sz, side, water) in enumerate(SHORE):
            out[f"uPlant{i}"] = (x, y, sz, float(self.plant_species[i]))
            out[f"uPlantS{i}"] = (self.plant_stage[i] if self.plant_alive[i] else -1.0, float(side * (1 + water)), self.plant_seed[i],
                                  min(9.0, now - self.plant_t0[i]))
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
