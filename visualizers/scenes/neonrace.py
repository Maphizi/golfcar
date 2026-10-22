"""Neonfahrt (Taste 2 im Thema CYBERPUNK, Gegenstück zum Navigationscomputer).

Fahrt durch die Regenstadt aus der Windschutzscheibe (assets/cyber/neonrace_scene.png). Startknopf = losfahren, sonst
fährt der Wagen nach 5 s von selbst los (AUTOPILOT); die Fahrt endet per Kippschalter (SPACE/BACKSPACE = anhalten) und
nimmt nach einer Pause wieder Fahrt auf. Tempo folgt der Energie der Musik (laut = schnell, Stille = langsam rollen),
Beat = kurzer Schub (Streifen heller/schneller), Drop = Nitro (gedämpft). Der Autopilot wählt die Spur fließend (-1..1):
Hindernisse und Verkehr in der eigenen Spur lösen einen Spurwechsel aus (AUSWEICHEN), knapp vorbeiziehende Objekte
rucken (Streiflicht), bei hohem Tempo reagiert er gelegentlich zu spät (BEINAHE: Blitz am Rand, Hupe des anderen).
Knüppel links/rechts überstimmt den Autopiloten für 4 s (MANUELL), oben = Lichthupe (querende Gefahren verschwinden
schneller), unten = Rückspiegel. Schilder: Hologramme und Neonstellen des Fotos wechseln die Farbe auf jeden Beat
(je Schild eigener Versatz), bei Drops alle gleichzeitig; Bass = Helligkeit, Höhen = Flackern/Glitch; Lauflicht durch
die Fassaden auf den Beat (uStep/uStepPhase/uPattern wie beim Orakel).
Ereignisse alle 30-60 s (EVENTS): Polizeidrohnen, Werbeblimp, Regensturm, Tunnel, Konzernturm, Straßenmarkt,
Kirschblütenallee. Hologramme assets/cyber/neonrace_holo.png (8x3 à 160), Verkehr neonrace_traffic.png (8x2 à 192:
Reihe 0 Fahrzeuge, Reihe 1 Flieger), Hindernisse neonrace_obstacles.png (8x2 à 192: Reihe 0 steht auf der Straße,
Reihe 1 quert die Straße; fehlt der Bogen, bleibt die Textur leer; KITT_NEONRACE_OBSTACLES=Pfad zum Testen).
"""
from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("neonrace")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
N_HOLO, N_CARS, N_FLY, N_OBS = 10, 6, 6, 6
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
OBS_CELLS, CROSS_CELLS = tuple(range(8)), tuple(range(8, 16))      # Reihe 0 steht auf der Straße, Reihe 1 quert sie
OBS_NAMES = ["BARRIERE", "KISTE", "DROHNE", "HÜTCHEN", "HOLO-SCHILD", "MÜLL", "FASS", "PANNENWAGEN",
             "FUSSGÄNGER", "KATZE", "HÄNDLERKARREN", "POLIZEIDROHNE", "PFÜTZE", "WERBESÄULE", "ROLLER", "LASTROBOTER"]
KIND_HOLO, KIND_CAR, KIND_FLY, KIND_OBS, KIND_CROSS = range(5)
LANE_SLOTS = (-1.0, -0.5, 0.0, 0.5, 1.0)                             # Kandidaten des Autopiloten
LANE_HALF = 0.42                                                     # halbe Wagenbreite in Spureinheiten
AUTO_START = 5.0                                                     # s bis der Autopilot von selbst losfährt
RESTART_AFTER = 20.0                                                 # s Pause nach manuellem Anhalten
MANUAL_SECONDS = 4.0
NEAR_MIN_GAP = 25.0                                                  # s Abstand zwischen Beinahe-Treffern


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
    """Etwas, das von weit hinten (z=0) auf die Kamera zukommt (z=1): Hologramm am Straßenrand, Auto, Flieger,
    Hindernis auf der Straße (kind 3, feste Spur) oder Querung (kind 4, x wandert über die Straße)."""

    def __init__(self, rng: random.Random, cell: int, side: float, lane: float, speed: float, kind: int, now: float):
        self.cell, self.side, self.lane, self.kind = cell, side, lane, kind
        self.z = 0.0
        self.speed = speed
        self.seed = rng.random()
        self.born = now
        self.hue = rng.random()
        self.vx = 0.0                     # Querung: Spureinheiten je Sekunde
        self.react_z = 0.6                # ab dieser Tiefe weicht der Autopilot aus
        self.evaded = False
        self.evade_t = -10.0
        self.passed = False

    def x(self) -> float:
        """Querposition in Spureinheiten (Hologramme/Flieger: Seite)."""
        return self.lane if self.kind in (KIND_CAR, KIND_OBS, KIND_CROSS) else self.side


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "neonrace_scene.png")
        self.holo = _load_rgba(ASSETS / "neonrace_holo.png")
        self.traffic = _load_rgba(ASSETS / "neonrace_traffic.png")
        obs_path = Path(os.environ.get("KITT_NEONRACE_OBSTACLES") or (ASSETS / "neonrace_obstacles.png"))
        self.obs_tex = _load_rgba(obs_path) if obs_path.exists() else None
        if self.obs_tex is None:
            log.warning("Hindernis-Bogen %s fehlt: Hindernisse bleiben unsichtbar (Autopilot weicht trotzdem aus)", obs_path)
        self.vanish = tuple(float(v) for v in scene_cfg.get("vanish", [0.5, 0.5]))
        self.auto_start = float(scene_cfg.get("auto_start", AUTO_START))
        self.restart_after = float(scene_cfg.get("restart_after", RESTART_AFTER))
        self.seed = self.rng.uniform(1.0, 100.0)
        now = time.monotonic()
        self.last = now
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
        self.boost = 0.0                   # Beat-Schub
        self.hue_all = 0.0                 # gemeinsamer Farbversatz aller Schilder (springt beim Drop)
        self.hue_all_target = 0.0
        self.step = 0                      # Lauflicht durch die Fassaden
        self.step_t0 = 0.0
        self.step_dir = 1
        self.pattern = 0
        self.pattern_next = now + self.rng.uniform(25.0, 45.0)
        self.driving = False
        self.auto_started = False
        self.speed = 0.0
        self.dist = 0.0
        self.lane = 0.0
        self.lane_target = 0.0
        self.lane_vel = 0.0
        self.manual_until = -1.0
        self.wander_at = now + self.rng.uniform(8.0, 15.0)
        self.evade_t0 = -10.0
        self.evade_name = ""
        self.graze_t0, self.graze_side = -10.0, 1.0
        self.near_t0, self.near_side = -10.0, 1.0
        self.honk_t0 = -10.0
        self.mirror = False
        self.mirror_k = 0.0
        self.wiper_t = 0.0
        self.event: dict | None = None
        self.next_event_at = 0.0
        self.holos: list[Mover | None] = [None] * N_HOLO
        self.cars: list[Mover | None] = [None] * N_CARS
        self.flyers: list[Mover | None] = [None] * N_FLY
        self.obstacles: list[Mover | None] = [None] * N_OBS
        self.started_at = 0.0
        self.auto_start_at = now + self.auto_start
        self.led_back_at: float | None = None
        self.demo_next = now + 8.0
        log.info("Neonfahrt: Szene %s, Hologramme %s, Verkehr %s, Hindernisse %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.holo is not None else "fehlt", "ok" if self.traffic is not None else "fehlt",
                 "ok" if self.obs_tex is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def start(self, auto: bool = False) -> None:
        if self.driving:
            return
        self.driving = True
        self.auto_started = auto
        now = time.monotonic()
        self.started_at = now
        self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.3 if self.demo else 0.7)
        self._led_event("neonrace_start", now + 3.0)
        log.info("Losgefahren (%s)", "Autopilot" if auto else "Startknopf")

    def stop(self) -> None:
        if not self.driving:
            return
        self.driving = False
        self.event = None
        self.auto_start_at = time.monotonic() + self.restart_after
        secs = int(time.monotonic() - self.started_at)
        log.info("Angehalten nach %d:%02d", secs // 60, secs % 60)
        wled.apply_mode_async("neonrace")

    def change_lane(self, d: float) -> None:
        """Knüppel: halbe Spur je Druck, Autopilot für 4 s aus."""
        self.lane_target = max(-1.0, min(1.0, round((self.lane_target + d * 0.5) * 2.0) / 2.0))
        self.manual_until = time.monotonic() + MANUAL_SECONDS

    def honk(self) -> None:
        self.honk_t0 = time.monotonic()
        self._led_event("neonrace_honk", self.honk_t0 + 1.5)

    def toggle_mirror(self) -> None:
        self.mirror = not self.mirror

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.nitro = 0.8
        self.hue_all_target += self.rng.uniform(1.2, 2.8)          # alle Schilder springen gemeinsam
        self.step_dir = -self.step_dir
        self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
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
        if self.rng.random() < rate * 0.04 * (2.5 if ev == EV_MARKET else 1.0):
            i = next((k for k, m in enumerate(self.holos) if m is None), None)
            if i is not None:
                self.holos[i] = Mover(self.rng, self.rng.randrange(24), self.rng.choice((-1.0, 1.0)), 0.0, self.rng.uniform(0.8, 1.2), KIND_HOLO, now)
        if self.rng.random() < rate * 0.012:
            i = next((k for k, m in enumerate(self.cars) if m is None), None)
            if i is not None:
                cell = CELL_POLICE if ev == EV_DRONES and self.rng.random() < 0.5 else self.rng.choice(CAR_CELLS)
                m = Mover(self.rng, cell, 0.0, self.rng.choice((-1.0, 0.0, 1.0)), self.rng.uniform(0.3, 0.7), KIND_CAR, now)
                self._arm_reaction(m)
                self.cars[i] = m
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
                self.flyers[i] = Mover(self.rng, cell, self.rng.uniform(-1.0, 1.0), self.rng.uniform(0.2, 1.0), self.rng.uniform(0.5, 1.0), KIND_FLY, now)
        # Hindernisse: Rate steigt mit Mitten und Energie, Markt = mehr Querungen
        obs_rate = (0.3 + 1.6 * self.energy + 1.2 * self.mid_s) * 0.008 * (0.5 + 0.5 * self.speed)
        if self.rng.random() < obs_rate:
            i = next((k for k, m in enumerate(self.obstacles) if m is None), None)
            if i is not None:
                crossing = self.rng.random() < (0.6 if ev == EV_MARKET else 0.35)
                if crossing:
                    side = self.rng.choice((-1.0, 1.0))
                    m = Mover(self.rng, self.rng.choice(CROSS_CELLS), side, 1.9 * side, 1.0, KIND_CROSS, now)
                    m.vx = -side * self.rng.uniform(0.35, 0.7)
                    m.z = self.rng.uniform(0.15, 0.4)
                else:
                    lane = self.rng.choice(LANE_SLOTS) + self.rng.uniform(-0.15, 0.15)
                    m = Mover(self.rng, self.rng.choice(OBS_CELLS), 0.0, lane, 1.0, KIND_OBS, now)
                self._arm_reaction(m)
                self.obstacles[i] = m

    def _arm_reaction(self, m: Mover) -> None:
        """Wann der Autopilot auf dieses Objekt reagiert; bei hohem Tempo gelegentlich zu spät (Beinahe-Treffer)."""
        late = (self.speed > 0.7 and time.monotonic() - self.near_t0 > NEAR_MIN_GAP
                and self.rng.random() < 0.12 * self.speed)
        m.react_z = self.rng.uniform(0.86, 0.9) if late else self.rng.uniform(0.5, 0.64)

    def _advance_movers(self, dt: float, now: float) -> None:
        honk = now - self.honk_t0 < 1.5
        for lst in (self.holos, self.cars, self.flyers, self.obstacles):
            for k, m in enumerate(lst):
                if m is None:
                    continue
                if m.kind == KIND_CAR:
                    rel = max(0.05, self.speed - 0.3 * m.speed) * 0.8
                elif m.kind == KIND_CROSS:
                    rel = self.speed * 0.9
                    m.lane += dt * m.vx * (3.0 if honk else 1.0) * (1.0 + 0.5 * self.energy)
                else:
                    rel = self.speed * m.speed
                m.z += dt * rel * 0.5
                if m.z >= 1.0 or (m.kind == KIND_CROSS and abs(m.lane) > 2.2):
                    lst[k] = None

    # -- Autopilot ---------------------------------------------------------
    def _threats(self):
        for lst in (self.cars, self.obstacles):
            for m in lst:
                if m is not None:
                    yield m

    def _autopilot(self, now: float) -> None:
        manual = now < self.manual_until
        for m in self._threats():
            dl = m.x() - self.lane
            # Vorbeiziehen: knapp = Streiflicht/Ruck, in der Spur = Beinahe-Treffer
            if not m.passed and m.z >= 0.9:
                m.passed = True
                if abs(dl) < 0.3:
                    self.near_t0, self.near_side = now, (1.0 if dl >= 0.0 else -1.0)
                    self._led_event("neonrace_honk", now + 1.0)
                    log.info("Beinahe-Treffer: %s (x %.2f, Spur %.2f -> %.2f, Reaktion ab %.2f, %s)",
                             OBS_NAMES[m.cell] if m.kind in (KIND_OBS, KIND_CROSS) else "VERKEHR", m.x(), self.lane,
                             self.lane_target, m.react_z, "manuell" if manual else ("ausgewichen" if m.evaded else "ignoriert"))
                elif abs(dl) < LANE_HALF + 0.35:
                    self.graze_t0, self.graze_side = now, (1.0 if dl >= 0.0 else -1.0)
            if manual or m.z < m.react_z or m.z >= 0.9:
                continue
            if m.evaded and now - m.evade_t < 0.8:       # nach 0,8 s nochmal prüfen (Querung läuft nach, Knüppel lenkte hinein)
                continue
            if abs(m.x() - self.lane_target) >= LANE_HALF and abs(dl) >= LANE_HALF:
                continue
            m.evaded, m.evade_t = True, now
            self._evade(now, m)
        if manual:
            return
        if now >= self.wander_at and now - self.evade_t0 > 3.0:          # freie Fahrt: Spur wandert gemächlich (frei bleibt frei)
            self.wander_at = now + self.rng.uniform(8.0, 15.0)
            wish = max(-1.0, min(1.0, self.lane_target + self.rng.uniform(-0.6, 0.6)))
            self.lane_target = self._best_lane(wish, 0.6)

    def _best_lane(self, wish: float, pull: float) -> float:
        """Freieste Spur: Abstand zu allen nahen Objekten groß, Nähe zum Wunsch (pull) belohnt."""
        near = [(o.x() + (o.vx * 0.8 if o.kind == KIND_CROSS else 0.0), o.z) for o in self._threats() if o.z > 0.3 and not o.passed]
        best, best_score = wish, -9.0
        for c in LANE_SLOTS:
            gap = min((abs(c - x) * (0.6 + z) for x, z in near), default=2.0)
            score = min(gap, 1.2) - pull * abs(c - wish)
            if score > best_score:
                best, best_score = c, score
        return best

    def _evade(self, now: float, m: Mover) -> None:
        self.lane_target = self._best_lane(self.lane, 0.25)
        self.evade_t0 = now
        self.evade_name = OBS_NAMES[m.cell] if m.kind in (KIND_OBS, KIND_CROSS) else "VERKEHR"

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uHoloTex": (self.holo if self.holo is not None else self.blank, 1),
                "uTrafficTex": (self.traffic if self.traffic is not None else self.blank, 1),
                "uObsTex": (self.obs_tex if self.obs_tex is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uHoloTex", "uTrafficTex", "uObsTex", "uSceneSize", "uHoloSize", "uTrafficSize", "uObsSize",
                 "uSeed", "uVanish", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uBoost",
                 "uHueAll", "uStep", "uStepPhase", "uPattern", "uSpeed", "uDist", "uLane", "uLaneVel", "uAuto", "uEvadeT",
                 "uGraze", "uNear", "uHonkT", "uMirror", "uWiperT", "uNitro", "uEvent", "uEventT", "uEventLen", "uDriving"]
        names += [f"uHolo{i}" for i in range(N_HOLO)]
        names += [f"uCar{i}" for i in range(N_CARS)]
        names += [f"uFly{i}" for i in range(N_FLY)]
        names += [f"uObs{i}" for i in range(N_OBS)]
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
            self.boost = 1.0
            self.step = (self.step + self.step_dir) % 4
            self.step_t0 = now
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
        self.boost = max(0.0, self.boost - dt / 0.5)
        if now >= self.pattern_next:
            self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
            self.pattern_next = now + self.rng.uniform(25.0, 45.0)
        self.hue_all += (self.hue_all_target - self.hue_all) * min(1.0, dt / 0.25)
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
        # Autostart: nach 5 s ohne Tastendruck (bzw. Pause nach dem Anhalten) fährt der Autopilot los
        if not self.driving and now >= self.auto_start_at:
            self.start(auto=True)
        # Tempo: Energie der Musik, Beat-Schub, Nitro; Stille = langsam rollen, nie ganz stehen
        if self.driving:
            target = 0.18 + 0.72 * self.energy + 0.12 * self.boost + 0.45 * self.nitro
            if live < 0.5:
                target = 0.12
        else:
            target = 0.0
        self.speed += (target - self.speed) * min(1.0, dt / (1.2 if target > self.speed else 2.5))
        self.dist += dt * self.speed * (1.0 + 0.5 * self.boost)
        if self.driving:
            self._autopilot(now)
        lane_prev = self.lane
        self.lane += (self.lane_target - self.lane) * min(1.0, dt / 0.55)
        vel = (self.lane - lane_prev) / max(dt, 1e-3)
        self.lane_vel += (vel - self.lane_vel) * min(1.0, dt / 0.15)
        storm = self.event is not None and self.event["kind"] == EV_STORM
        self.wiper_t += dt * (0.5 + 2.5 * self.mid_s + (2.0 if storm else 0.0)) * (1.0 if self.driving else 0.3)
        self.mirror_k += ((1.0 if self.mirror else 0.0) - self.mirror_k) * min(1.0, dt / 0.4)
        if self.driving:
            self._spawn(now)
            self._advance_movers(dt, now)
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
        if self.demo and self.driving and now >= self.demo_next:
            pick = self.rng.choice(("honk", "mirror", "drop", "left", "right", "none"))
            {"left": lambda: self.change_lane(-1.0), "right": lambda: self.change_lane(1.0), "honk": self.honk,
             "mirror": self.toggle_mirror, "drop": lambda: self._drop(now), "none": lambda: None}[pick]()
            self.demo_next = now + 8.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        ev = self.event
        manual = now < self.manual_until
        out = {
            "uSceneSize": size(self.scene), "uHoloSize": size(self.holo), "uTrafficSize": size(self.traffic),
            "uObsSize": size(self.obs_tex),
            "uSeed": self.seed, "uVanish": self.vanish, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uBoost": self.boost, "uHueAll": self.hue_all,
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern),
            "uSpeed": self.speed, "uDist": self.dist % 1000.0, "uLane": self.lane, "uLaneVel": self.lane_vel,
            "uAuto": 0.0 if manual else 1.0,
            "uEvadeT": (now - self.evade_t0) if now - self.evade_t0 < 2.0 else -1.0,
            "uGraze": ((now - self.graze_t0) if now - self.graze_t0 < 1.0 else -1.0, self.graze_side),
            "uNear": ((now - self.near_t0) if now - self.near_t0 < 1.5 else -1.0, self.near_side),
            "uHonkT": (now - self.honk_t0) if now - self.honk_t0 < 1.5 else -1.0, "uMirror": self.mirror_k,
            "uWiperT": self.wiper_t % 1000.0, "uNitro": self.nitro, "uDriving": 1.0 if self.driving else 0.0,
            "uEvent": float(ev["kind"] + 1) if ev else 0.0, "uEventT": (now - ev["t0"]) if ev else 0.0,
            "uEventLen": ev["len"] if ev else 1.0,
        }
        for name, lst in (("uHolo", self.holos), ("uCar", self.cars), ("uFly", self.flyers), ("uObs", self.obstacles)):
            for i, m in enumerate(lst):
                if m is None:
                    out[f"{name}{i}"] = (0.0, 0.0, -1.0, 0.0)
                else:
                    out[f"{name}{i}"] = (float(m.cell), m.x(), m.z, m.seed)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if not self.driving:
            out.append(("N E O N F A H R T", 0.05, 0.5, 0.62, (255, 60, 200), 0.7 + 0.3 * np.sin(t * 2.0)))
            out.append(("STARTKNOPF = LOSFAHREN      KIPPSCHALTER = ANHALTEN", 0.02, 0.5, 0.55, (120, 220, 255), 0.7))
            wait = self.auto_start_at - now
            if 0.0 < wait < 6.0:
                out.append((f"AUTOPILOT IN {int(wait) + 1} S", 0.022, 0.5, 0.48, (255, 255, 160), 0.6 + 0.3 * np.sin(t * 6.0)))
        else:
            secs = int(now - self.started_at)
            kmh = int(40 + 260 * self.speed)
            out.append((f"{kmh} KM/H     {secs // 60}:{secs % 60:02d}", 0.02, 0.5, 0.04, (120, 220, 255), 0.6))
            rest = self.manual_until - now
            if rest > 0.0:
                out.append((f"MANUELL ({int(rest) + 1} S)", 0.018, 0.5, 0.08, (255, 220, 120), 0.75))
            else:
                out.append(("AUTOPILOT", 0.018, 0.5, 0.08, (120, 255, 200), 0.45 + 0.15 * np.sin(t * 3.0)))
            if self.event:
                name, length, line = EVENTS[self.event["kind"]]
                k = (now - self.event["t0"]) / length
                a = min(1.0, k * 6.0) * min(1.0, (1.0 - k) * 6.0)
                out.append((name, 0.03, 0.5, 0.92, (255, 60, 200), 0.9 * a))
                out.append((line, 0.018, 0.5, 0.88, (200, 240, 255), 0.8 * a))
            ev_t = now - self.evade_t0
            if ev_t < 1.6:
                out.append((f"AUSWEICHEN: {self.evade_name}", 0.028, 0.5, 0.3, (255, 200, 80), min(1.0, (1.6 - ev_t) * 2.0)))
            near_t = now - self.near_t0
            if near_t < 1.4:
                out.append(("B E I N A H E !", 0.045, 0.5, 0.42, (255, 80, 80), (1.0 - near_t / 1.4) * (0.6 + 0.4 * np.sin(t * 25.0))))
            if self.nitro > 0.3:
                out.append(("N I T R O", 0.06, 0.5, 0.5, (255, 255, 120), self.nitro * (0.5 + 0.5 * np.sin(t * 20.0))))
            if now - self.honk_t0 < 1.2:
                out.append(("LICHTHUPE", 0.025, 0.5, 0.12, (255, 255, 200), 1.0 - (now - self.honk_t0) / 1.2))
        return out
