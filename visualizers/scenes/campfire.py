"""Lagerfeuer "Rast am Rand der Galaxis" (Space-Taxi, Taste 6). Szenen-Controller der GL-Engine.

Ein Lagerfeuer auf einem fremden Hochplateau unter Milchstraße, Ringplanet und zwei Monden, das Space-Taxi parkt
hinten (assets/campfire/scene.png, Szene OHNE Flammen, nur Glut). Das Feuer ist der ruhige Herzschlag:
  Stufe      `level` 0..3 (Glut, klein, normal, groß) folgt der Energie der Musik mit Trägheit (LEVEL_TAU), nie ein
             Sprung: drei Flammenbögen (flames_small/mid/big.png, 8x4 à 128x256, Schleife) werden weich gemischt
             (uFlame = Bogen A, Bogen B, Mischung, Größe), Bass = leichtes Pulsen, Beat = ein Funke mehr
  Holz       alle LOG_EVERY 2-4 min (oder Knüppel OBEN) fliegt ein Scheit ins Feuer: Funkenwolke, `boost` hebt die Stufe
             und klingt über ~90 s ab; selten (CRYSTAL_EVERY, oder Drop bei lauter Musik) ein Kristall: Flammen werden
             BLUE_SECONDS lang blau-violett (flames_blue.png, uFlameK.y)
  Funken     steigen auf, driften im Wind und werden am Himmel kurz zu Sternen (Vier-Strahl-Funke); UNTEN = stochern
  Himmel     Sterne funkeln mit den Höhen, Sternschnuppen SHOOT_EVERY, Polarlicht pulst mit dem Bass, der Himmel steigt
             über `cycle_minutes` unmerklich (Planet geht auf), das Taxi blinkt alle TAXI_EVERY mit den Positionslichtern
  Leben      Kessel dampft, Raummotten kreisen (Anzahl mit den Höhen), ein Alien lugt selten hinter dem Stein hervor,
             ENTER = Marshmallow am Stock (röstet je nach Feuer: roh -> golden -> verkohlt)
Knüppel LINKS/RECHTS = Windstoß (Flammen und Rauch legen sich), OBEN = Holz, UNTEN = stochern, ENTER = Marshmallow,
Kippschalter AN = Nahaufnahme, AUS = zurück. Lage im Bild: config/visualizer.toml [scenes.campfire].
Demo (--demo): alles 8x schneller. Test: python -m visualizers.engine campfire --test-signal --demo.
"""
from __future__ import annotations

import logging
import math
import os
import random
import time

import numpy as np
import pygame

from launcher import config as lcfg
from launcher import wled
from visualizers.engine import images

log = logging.getLogger("campfire")
ASSETS = lcfg.ROOT / "assets" / "campfire"
N_FRAMES = 32
SHEETS = ("flames_small.png", "flames_mid.png", "flames_big.png", "flames_blue.png")
N_SPARKS = 24
N_MOTHS = 3
N_ITEMS = 4
# Zellen in items.png (8x2 à 192)
ITEM_LOG, ITEM_BRANCH, ITEM_CONE, ITEM_CRYSTAL = 0, 1, 2, 3
ITEM_MALLOW = (4, 5, 6)                         # roh, golden, verkohlt
ITEM_MOTH = (9, 10, 11)
ITEM_ALIEN_EYES, ITEM_ALIEN_HEAD = 12, 13
FUEL_NAMES = {ITEM_LOG: "SCHEIT", ITEM_BRANCH: "AST", ITEM_CONE: "ZAPFEN", ITEM_CRYSTAL: "KRISTALL"}
# Zellen in sparks.png (8x2 à 128): 0-2 Funken, 3-5/8-10/13 Glutstücke, 7/15 Sternfunken, 11/12 Asche
SPARK_CELLS = (0, 1, 2, 4, 6, 9, 14)
STAR_CELLS = (7, 15)
ASH_CELLS = (11, 12)
LEVEL_TAU = 4.0                                 # s Trägheit der Feuerstufe
LOG_EVERY = (120.0, 240.0)
CRYSTAL_EVERY = (150.0, 210.0)
BLUE_SECONDS = (30.0, 60.0)
BOOST_DECAY = 90.0                              # s, bis ein Scheit "abgebrannt" ist
ALIEN_EVERY = (90.0, 200.0)
TAXI_EVERY = (120.0, 300.0)
SHOOT_EVERY = (20.0, 60.0)
GUST_EVERY = (20.0, 40.0)
MALLOW_SECONDS = 9.0
FLIGHT_SECONDS = 1.2


class Spark:
    __slots__ = ("x", "y", "vx", "vy", "cell", "size", "age", "life", "star", "spin")

    def __init__(self, rng: random.Random, x: float, y: float, strength: float, ash: bool = False):
        self.x = x + rng.uniform(-0.03, 0.03)
        self.y = y + rng.uniform(0.0, 0.04)
        self.vx = rng.uniform(-0.03, 0.03) * (1.0 + strength)
        self.vy = rng.uniform(0.05, 0.14) * (0.8 + 0.8 * strength)
        self.cell = rng.choice(ASH_CELLS if ash else SPARK_CELLS)
        self.size = rng.uniform(0.012, 0.03) * (1.3 if ash else 1.0)
        self.age = 0.0
        self.life = rng.uniform(2.5, 5.0) * (0.7 if ash else 1.0)
        self.star = (not ash) and rng.random() < 0.3        # wird am Ende kurz zum Stern
        self.spin = rng.uniform(-3.0, 3.0)


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.speedup = 8.0 if demo else 1.0
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = images.load_rgba(ASSETS / "scene.png")
        self.sheets = [images.load_rgba(ASSETS / n) for n in SHEETS]
        self.sparks_tex = images.load_rgba(ASSETS / "sparks.png")
        self.items_tex = images.load_rgba(ASSETS / "items.png")
        self.fire = tuple(float(v) for v in scene_cfg.get("fire", [0.47, 0.27, 0.16]))           # x, Fuß y (von unten), Breite
        self.kettle = tuple(float(v) for v in scene_cfg.get("kettle", [0.44, 0.44]))             # Tülle des Kessels
        self.kettle_box = tuple(float(v) for v in scene_cfg.get("kettle_box", [0.44, 0.419, 0.034, 0.051]))  # Kesselbauch vor den Flammen
        self.cal = os.environ.get("KITT_CAMPFIRE_CAL", "") not in ("", "0")
        self.taxi = tuple(float(v) for v in scene_cfg.get("taxi", [0.02, 0.50, 0.30, 0.62]))     # Lichter des Taxis
        self.horizon = float(scene_cfg.get("horizon", 0.57))
        self.alien = tuple(float(v) for v in scene_cfg.get("alien", [0.72, 0.21, 0.09]))         # x, Fuß y, Größe
        self.mallow = tuple(float(v) for v in scene_cfg.get("mallow", [0.56, 0.46]))             # Spitze des Stocks
        self.cycle_minutes = float(scene_cfg.get("cycle_minutes", 60.0))
        self.planet = tuple(float(v) for v in scene_cfg.get("planet", [0.779, 0.755, 0.094]))   # Saturn: Mitte x, y, Radius (Breiten-Anteil)
        ring = [float(v) for v in scene_cfg.get("ring", [0.196, 0.034, 21.4, 0.71, -0.016, 0.0])]  # a, b, Neigung Grad (positiv = rechts tiefer), innen/a, Versatz x, y
        self.ring = (ring[0], ring[1], math.radians(ring[2]), ring[3])
        self.ring_off = (ring[4], ring[5]) if len(ring) >= 6 else (0.0, 0.0)
        self.ring_t = 0.0                                                                     # Ringzeit (läuft mit der Energie schneller)
        self.seed = self.rng.uniform(1.0, 100.0)
        now = time.monotonic()
        self.t0 = now
        self.last = now
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        # Feuer
        self.level = 1.2
        self.boost = 0.0
        self.blue_until = -1.0
        self.blue_k = 0.0
        self.frame_t = 0.0
        self.wind = 0.0
        self.wind_target = 0.0
        self.gust_next = now + self.rng.uniform(*GUST_EVERY)
        self.poke_t0 = -10.0
        self.ember = 0.0                                  # Glut glüht nach Stochern / Wind
        # Teilchen und Gegenstände
        self.sparks: list[Spark] = []
        self.spark_acc = 0.0
        self.flights: list[dict] = []                     # {cell, x0, y0, t0}
        self.mallow_t0 = -100.0
        self.mallow_grade = 0
        self.mallow_result = ""
        self.moths = [{"phase": self.rng.uniform(0.0, 6.28), "r": self.rng.uniform(0.08, 0.16), "speed": self.rng.uniform(0.6, 1.1),
                       "h": self.rng.uniform(0.05, 0.14), "wing": 0.0, "on": 0.0} for _ in range(N_MOTHS)]
        self.alien_t0 = -100.0
        self.taxi_t0 = -100.0
        self.shoot_t0 = -100.0
        self.shoot = (0.3, 0.9, 0.3, -0.12)
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.last_key = -100.0
        self.led_back_at: float | None = None
        self.led_state = "campfire"
        s = self.speedup
        self.log_next = now + self.rng.uniform(*LOG_EVERY) / s
        self.crystal_next = now + self.rng.uniform(*CRYSTAL_EVERY) / s
        self.alien_next = now + self.rng.uniform(*ALIEN_EVERY) / s
        self.taxi_next = now + self.rng.uniform(*TAXI_EVERY) / s
        self.shoot_next = now + self.rng.uniform(*SHOOT_EVERY) / s
        self.demo_next = now + 5.0
        log.info("Lagerfeuer: Szene %s, Flammen %s, Funken %s, Gegenstände %s", "ok" if self.scene is not None else "fehlt",
                 "/".join("ok" if sh is not None else "fehlt" for sh in self.sheets),
                 "ok" if self.sparks_tex is not None else "fehlt", "ok" if self.items_tex is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def _burst(self, n: int, strength: float, ash: bool = False) -> None:
        fx, fy = self.fire[0], self.fire[1]
        for _ in range(n):
            if len(self.sparks) >= N_SPARKS:
                self.sparks.pop(0)
            self.sparks.append(Spark(self.rng, fx, fy + 0.04, strength, ash))

    def throw(self, cell: int | None = None) -> None:
        """Holz (oder Kristall) fliegt von rechts unten ins Feuer."""
        now = time.monotonic()
        if cell is None:
            cell = self.rng.choice((ITEM_LOG, ITEM_LOG, ITEM_BRANCH, ITEM_CONE))
        if len(self.flights) >= 2:
            return
        self.flights.append({"cell": cell, "x0": 0.95, "y0": 0.05, "t0": now})
        log.info("Nachlegen: %s", FUEL_NAMES.get(cell, cell))

    def _land(self, cell: int, now: float) -> None:
        if cell == ITEM_CRYSTAL:
            self.blue_until = now + self.rng.uniform(*BLUE_SECONDS) / (self.speedup if self.demo else 1.0)
            self.boost = max(self.boost, 0.8)
            self._burst(14, 1.2)
            self._led("campfire_blue", now + 6.0)
            log.info("Fremder Brennstoff: blaue Flammen")
        else:
            self.boost = max(self.boost, 1.3 if cell == ITEM_LOG else 0.8)
            self._burst(10 if cell == ITEM_LOG else 6, 1.0)
            self._burst(3, 0.5, ash=True)
            self._led("campfire_log", now + 4.0)
        self.ember = 1.0

    def poke(self) -> None:
        now = time.monotonic()
        if now - self.poke_t0 < 1.0:
            return
        self.poke_t0 = now
        self.ember = 1.0
        self._burst(12, 1.4)
        self._burst(2, 0.6, ash=True)
        log.info("Stochern")

    def gust(self, direction: float) -> None:
        self.wind_target = max(-1.0, min(1.0, self.wind_target + 0.7 * direction))
        self.ember = max(self.ember, 0.6)
        self._burst(4, 0.8)

    def marshmallow(self) -> None:
        now = time.monotonic()
        if now - self.mallow_t0 < MALLOW_SECONDS + 1.0:
            return
        self.mallow_t0 = now
        self.mallow_grade = 0
        self.mallow_result = ""
        log.info("Marshmallow am Stock")

    def _led(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self._burst(16, 1.5)
        self.ember = 1.0
        if self.energy > 0.5 and now > self.blue_until and not self.flights:
            self.throw(ITEM_CRYSTAL)
        else:
            self.boost = max(self.boost, 0.6)
        log.info("Drop: Funkensturm")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        self.last_key = time.monotonic()
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.gust(-1.0)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.gust(1.0)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.throw()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.poke()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.marshmallow()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        out = {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
               "uSparkTex": (self.sparks_tex if self.sparks_tex is not None else self.blank, 1),
               "uItemTex": (self.items_tex if self.items_tex is not None else self.blank, 1)}
        for i, name in enumerate(("uFlameSTex", "uFlameMTex", "uFlameBTex", "uFlameXTex")):
            out[name] = (self.sheets[i] if self.sheets[i] is not None else self.blank, 1)
        return out

    def uniform_names(self):
        names = ["uSceneTex", "uFlameSTex", "uFlameMTex", "uFlameBTex", "uFlameXTex", "uSparkTex", "uItemTex",
                 "uSceneSize", "uFlameSize", "uSparkSize", "uItemSize", "uSeed", "uFire", "uKettle", "uTaxi", "uHorizon",
                 "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uLevel", "uFlame", "uFlameK", "uFrameMix",
                 "uWind", "uEmber", "uPokeT", "uSkyRise", "uShoot", "uTaxiT", "uZoom", "uMallow", "uCal", "uKettleBox",
                 "uPlanet", "uRing", "uRingT", "uRingOff"]
        names += [f"uSp{i}" for i in range(N_SPARKS)]
        names += [f"uItem{i}" for i in range(N_ITEMS)] + [f"uItemP{i}" for i in range(N_ITEMS)]
        names += [f"uMoth{i}" for i in range(N_MOTHS)]
        return tuple(names)

    def _flame_mix(self) -> tuple[float, float, float, float, float]:
        """(Bogen A, Bogen B, Mischung, Größe, Deckkraft) aus der Stufe 0..3: Glut = kleine Flammen klein und blass."""
        lv = max(0.0, min(3.0, self.level))
        if lv < 1.0:
            return 0.0, 0.0, 0.0, 0.55 + 0.45 * lv, 0.3 + 0.7 * lv
        if lv < 2.0:
            return 0.0, 1.0, lv - 1.0, 1.0, 1.0
        return 1.0, 2.0, lv - 2.0, 1.0 + 0.1 * (lv - 2.0), 1.0

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        sdt = dt * self.speedup
        silent = bool(getattr(f, "silent", True))
        live = 0.0 if silent else 1.0
        bass = float(getattr(f, "bass", 0.0)) * live
        mid = float(getattr(f, "mid", 0.0)) * live
        high = float(getattr(f, "high", 0.0)) * live
        beat = float(getattr(f, "beat", 0.0)) * live
        rms = float(getattr(f, "rms", 0.0)) * live
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.15)
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.4)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.12)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 3.0)
        self.ring_t += dt * (0.7 + 0.8 * self.energy) * self.speedup
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
            if self.rng.random() < 0.3 + 0.5 * self.bass_s:
                self._burst(1, 0.6)
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.5)
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 12.0:
            self.drop_armed = False
            self.last_drop = now
            self._drop(now)
        # Feuerstufe: ruhig aus der Energie, Holz hebt, nichts springt
        self.boost = max(0.0, self.boost - sdt / BOOST_DECAY * 1.3)
        target = (0.35 + 2.3 * min(1.0, self.energy * 1.6)) * live + (1.0 - live) * 0.25 + self.boost
        self.level += (min(3.0, target) - self.level) * min(1.0, dt / LEVEL_TAU)
        blue_on = now < self.blue_until
        self.blue_k += ((1.0 if blue_on else 0.0) - self.blue_k) * min(1.0, dt / 2.5)
        self.frame_t += dt * (9.0 + 5.0 * self.energy + 2.0 * self.boost)
        # Wind: Stöße klingen ab, kleine Böen von selbst
        if now >= self.gust_next:
            self.gust_next = now + self.rng.uniform(*GUST_EVERY) / self.speedup
            self.wind_target += self.rng.uniform(-0.4, 0.4)
        self.wind_target *= max(0.0, 1.0 - dt / 6.0)
        self.wind += (self.wind_target - self.wind) * min(1.0, dt / 1.5)
        self.ember = max(0.0, self.ember - dt / 3.0)
        # Funken: Grundrate mit der Stufe, steigen, driften im Wind, werden am Himmel zu Sternen
        self.spark_acc += dt * (0.4 + 1.6 * self.level / 3.0 + 2.0 * self.ember)
        while self.spark_acc >= 1.0:
            self.spark_acc -= 1.0
            if len(self.sparks) < N_SPARKS:
                self.sparks.append(Spark(self.rng, self.fire[0], self.fire[1] + 0.05, 0.3 + self.level / 3.0))
        for sp in self.sparks:
            sp.age += dt
            sp.vx += (0.05 * self.wind + 0.02 * math.sin(sp.age * 5.0 + sp.spin)) * dt
            sp.vy = max(0.02, sp.vy - 0.012 * dt)
            sp.x += sp.vx * dt
            sp.y += sp.vy * dt
        self.sparks = [sp for sp in self.sparks if sp.age < sp.life and sp.y < 1.05]
        # Holz und Kristall: von selbst, Flug, Landung
        if now >= self.log_next and live and not self.flights:
            self.log_next = now + self.rng.uniform(*LOG_EVERY) / self.speedup
            self.throw()
        if now >= self.crystal_next and live and not self.flights and not blue_on:
            self.crystal_next = now + self.rng.uniform(*CRYSTAL_EVERY) / self.speedup
            self.throw(ITEM_CRYSTAL)
        for fl in list(self.flights):
            if now - fl["t0"] >= FLIGHT_SECONDS:
                self.flights.remove(fl)
                self._land(fl["cell"], now)
        # Marshmallow: Röstgrad aus Feuerstufe und Zeit
        mk = now - self.mallow_t0
        if mk < MALLOW_SECONDS:
            roast = (mk - 1.5) * (0.1 + 0.085 * self.level + 0.5 * self.blue_k)      # normales Feuer = golden, groß = verkohlt
            self.mallow_grade = 0 if roast < 1.0 else (1 if roast < 2.6 else 2)
            if mk > MALLOW_SECONDS - 0.3 and not self.mallow_result:
                self.mallow_result = ("ROH. ZU UNGEDULDIG.", "PERFEKT GOLDEN.", "VERKOHLT. WIE DEINE ZUKUNFT.")[self.mallow_grade]
                log.info("Marshmallow: %s", self.mallow_result)
        # Motten: Anzahl mit den Höhen, kreisen um das Feuer
        want = 0 if not live else (1 if self.high_s < 0.2 else (2 if self.high_s < 0.45 else 3))
        for i, m in enumerate(self.moths):
            m["on"] += ((1.0 if i < want else 0.0) - m["on"]) * min(1.0, dt / 2.0)
            m["phase"] += dt * m["speed"] * (0.7 + 0.6 * self.high_s)
            m["wing"] += dt * (10.0 + 10.0 * self.high_s)
        # Alien, Taxi, Sternschnuppe, Himmel
        if now >= self.alien_next and live:
            self.alien_next = now + self.rng.uniform(*ALIEN_EVERY) / self.speedup
            self.alien_t0 = now
            log.info("Das Alien lugt hervor")
        if now >= self.taxi_next:
            self.taxi_next = now + self.rng.uniform(*TAXI_EVERY) / self.speedup
            self.taxi_t0 = now
        if now >= self.shoot_next:
            self.shoot_next = now + self.rng.uniform(*SHOOT_EVERY) / self.speedup
            self.shoot_t0 = now
            x0 = self.rng.uniform(0.1, 0.9)
            self.shoot = (x0, self.rng.uniform(0.75, 0.98), self.rng.choice((-1.0, 1.0)) * self.rng.uniform(0.08, 0.2), -self.rng.uniform(0.05, 0.12))
        sky_rise = ((now - self.t0) * self.speedup / (self.cycle_minutes * 60.0)) % 1.0
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 2.0)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("campfire")
        if self.led_back_at is None:                      # Dauerprofil folgt der Feuerstufe
            want_led = "campfire_big" if self.level > 2.4 else "campfire"
            if want_led != self.led_state:
                self.led_state = want_led
                wled.apply_mode_async(want_led)
        if self.demo and now >= self.demo_next:
            self.demo_next = now + 6.0
            self.rng.choice((self.poke, self.marshmallow, lambda: self.gust(1.0), lambda: self.gust(-1.0), self.throw,
                             lambda: self.throw(ITEM_CRYSTAL)))()
        # -- Uniforms
        a, b, mix, scale, alpha = self._flame_mix()
        fa = int(self.frame_t) % N_FRAMES
        size = lambda arr: (float(arr.shape[1]), float(arr.shape[0])) if arr is not None else (1.0, 1.0)
        out = {
            "uSceneSize": size(self.scene), "uFlameSize": size(self.sheets[0]), "uSparkSize": size(self.sparks_tex),
            "uItemSize": size(self.items_tex), "uSeed": self.seed,
            "uFire": (self.fire[0], self.fire[1], self.fire[2], 0.0), "uKettle": self.kettle, "uTaxi": self.taxi,
            "uHorizon": self.horizon, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uLevel": self.level,
            "uFlame": (a, b, mix, scale), "uFlameK": (alpha, self.blue_k, float(fa), float((fa + 1) % N_FRAMES)),
            "uFrameMix": self.frame_t - int(self.frame_t), "uWind": self.wind, "uEmber": self.ember,
            "uPokeT": (now - self.poke_t0) if now - self.poke_t0 < 3.0 else -1.0, "uSkyRise": sky_rise,
            "uShoot": ((now - self.shoot_t0) if now - self.shoot_t0 < 1.6 else -1.0, self.shoot[0], self.shoot[1], math.atan2(self.shoot[3], self.shoot[2])),
            "uTaxiT": (now - self.taxi_t0) if now - self.taxi_t0 < 3.0 else -1.0, "uZoom": self.zoom,
            "uMallow": (mk if mk < MALLOW_SECONDS else -1.0, float(self.mallow_grade), self.mallow[0], self.mallow[1]),
            "uCal": 1.0 if self.cal else 0.0, "uKettleBox": self.kettle_box,
            "uPlanet": (self.planet[0], self.planet[1], self.planet[2], 0.0), "uRing": self.ring, "uRingT": self.ring_t, "uRingOff": self.ring_off,
        }
        for i in range(N_SPARKS):
            if i < len(self.sparks):
                sp = self.sparks[i]
                k = sp.age / sp.life
                star = sp.star and k > 0.75
                cell = self.rng.choice(STAR_CELLS) if (star and int(sp.age * 10) % 2 == 0) else sp.cell
                fade = min(1.0, (1.0 - k) * 4.0) * min(1.0, sp.age * 6.0)
                out[f"uSp{i}"] = (sp.x, sp.y, float(STAR_CELLS[0] if star else sp.cell), sp.size * (1.8 if star else 1.0) * (0.5 + 0.5 * fade))
            else:
                out[f"uSp{i}"] = (0.0, -9.0, 0.0, 0.0)
        # Gegenstände: 0/1 Flug, 2 Marshmallow, 3 Alien
        items = [(0.0, -9.0, 0.0, 0.0, 0.0, 0.0)] * N_ITEMS
        for j, fl in enumerate(self.flights[:2]):
            k = min(1.0, (now - fl["t0"]) / FLIGHT_SECONDS)
            x = fl["x0"] + (self.fire[0] - fl["x0"]) * k
            y = fl["y0"] + (self.fire[1] + 0.03 - fl["y0"]) * k + 0.25 * math.sin(k * math.pi)
            items[j] = (x, y, float(fl["cell"]), 0.07 * (1.0 - 0.3 * k), 1.0, k * 8.0)
        if mk < MALLOW_SECONDS:
            ins = min(1.0, mk / 1.2) * min(1.0, (MALLOW_SECONDS - mk) / 1.0)
            tipx, tipy = self.mallow                                       # Stock kommt von rechts oben, Marshmallow über dem Feuer
            x = tipx + 0.075 + (1.0 - ins) * 0.5 + 0.004 * math.sin(now * 2.0)
            y = tipy + 0.035 + 0.01 * math.sin(now * 1.3)
            items[2] = (x, y, float(ITEM_MALLOW[self.mallow_grade]), 0.16, 1.0, 1.9)
        ak = now - self.alien_t0
        if ak < 7.0:
            up = min(1.0, ak / 1.5) * min(1.0, (7.0 - ak) / 1.0)
            cell = ITEM_ALIEN_HEAD if 2.5 < ak < 5.5 else ITEM_ALIEN_EYES
            items[3] = (self.alien[0], self.alien[1] - self.alien[2] * 0.5 * (1.0 - up), float(cell), self.alien[2], up, 0.0)
        for i, it in enumerate(items):
            out[f"uItem{i}"] = it[:4]
            out[f"uItemP{i}"] = (it[4], it[5], 0.0, 0.0)
        for i, m in enumerate(self.moths):
            x = self.fire[0] + math.cos(m["phase"]) * m["r"] * 0.55
            y = self.fire[1] + 0.22 + m["h"] + math.sin(m["phase"] * 1.3) * 0.05 + math.sin(m["phase"]) * m["r"] * 0.25
            wing = ITEM_MOTH[int(m["wing"]) % 3]
            out[f"uMoth{i}"] = (x, y, float(wing), m["on"])
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        k = now - self.t0
        if k < 6.0:
            out.append(("RAST AM RAND DER GALAXIS", 0.03, 0.5, 0.9, (255, 220, 170), 0.8 * min(1.0, k) * min(1.0, (6.0 - k) / 1.5)))
        mk = now - self.mallow_t0
        if mk < MALLOW_SECONDS + 3.0 and self.mallow_result and mk > MALLOW_SECONDS - 0.3:
            out.append((self.mallow_result, 0.026, 0.5, 0.82, (255, 230, 190), 0.9 * min(1.0, (MALLOW_SECONDS + 3.0 - mk) / 1.0)))
        if self.blue_k > 0.5:
            out.append(("FREMDER BRENNSTOFF", 0.02, 0.5, 0.86, (170, 190, 255), 0.5 * self.blue_k))
        if now - self.last_key < 2.0:
            names = {0: "GLUT", 1: "KLEINES FEUER", 2: "LAGERFEUER", 3: "GROSSES FEUER"}
            out.append((names[min(3, int(self.level + 0.5))], 0.018, 0.5, 0.05, (255, 200, 140), 0.6 * (1.0 - (now - self.last_key) / 2.0)))
        return out
