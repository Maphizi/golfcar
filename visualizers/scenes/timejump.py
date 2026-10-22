"""Zeitsprung (Taste 2 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zum Navigationscomputer).

Fahrt aus der Windschutzscheibe der Zeitmaschine (assets/future/timejump_cockpit.png, Scheibe = reines Schwarz,
dahinter eine von vier Epochenstraßen timejump_1885/1955/1985/2015.png). Startknopf = Gas geben, der Tacho steigt mit
der Energie der Musik Richtung 88 MPH (laute Musik hält den Schub, Stille lässt ausrollen); die Fahrt endet NUR per
Kippschalter (SPACE/BACKSPACE). Bei 88 zündet der Zeitsprung: Blaulicht um die Scheibe, Weißblitz, Feuerspuren,
und die Straße liegt in einer anderen Epoche (zufällig, nie dieselbe). Drop = sofortiger Sprung.
Bass = Motor/Scheibenwackeln, Beat = Laternen und Schilder blitzen, Höhen = Staub/Funken/Regen/Hologrammfunken je
Epoche, Mitten = Verkehrsdichte, Energie = Tempo. Knüppel links/rechts = Spur, oben = Hupe (Verkehr weicht, in 2015
fliegt alles hoch), unten = Zeitkreise umschalten (nächste Epoche vorwählen, Anzeige rattert).
Ereignisse alle 30-60 s je Epoche (EVENTS) und immer das Gewitter. Verkehr timejump_traffic.png (8x4 à 192, Reihe =
Epoche). Zeitkreis-Overlay: ZIELZEIT rot, JETZTZEIT grün, ZULETZT gelb in den drei Anzeigen des Cockpits.
"""
from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import blobs, images

from launcher import wled

log = logging.getLogger("timejump")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
N_MOV = 10
JUMP_LEN = 3.0            # Dauer des Zeitsprungs (s); Epochenwechsel in der Mitte
JUMP_SWAP = 1.5
CIRCUIT_LEN = 1.2         # Anzeige rattert (s)
HONK_LEN = 1.5
MPH_JUMP = 88.0
COCKPIT_DROP = 0.08
CIRCUIT_X = 0.735         # Zeitkreis-Anzeigen im Cockpitbild: Mitte x und die drei Zeilen (y von unten)
CIRCUIT_Y = (0.356, 0.247, 0.142)
MPH_X, MPH_Y = 0.5, 0.035       # Tacho-Text unter dem Lenkrad       # Cockpitbild um diesen Anteil nach unten schieben (Armaturen kleiner, Scheibe größer)
SHIELD_Y0 = 0.45          # Unterkante der Scheibe im Cockpitbild (Anteil von unten): darunter liegt das Armaturenbrett
EVENT_EVERY = (30.0, 60.0)
ERA_NAMES = ("1885", "1955", "1985", "2015")
ERA_LABELS = ("WILDER WESTEN", "KLEINSTADT", "VORSTADT", "ZUKUNFT")
ERA_DATES = ("SEP 02 1885 08:00", "NOV 05 1955 06:00", "OKT 26 1985 01:21", "OKT 21 2015 04:29")
# (Name, Dauer, Zeile, Epoche oder -1 = immer)
EVENTS = [
    ("PFERDEKUTSCHE", 12.0, "DIE POST KOMMT DURCH", 0),
    ("DAMPFLOK", 14.0, "VOLLDAMPF NEBEN DER STRASSE", 0),
    ("MISTWAGEN", 12.0, "ICH HASSE MIST", 1),
    ("TANZBALL", 16.0, "VERZAUBERUNG UNTER DEM MEER", 1),
    ("SKATEBOARDER", 14.0, "HALT DICH AM WAGEN FEST", 2),
    ("EINKAUFSZENTRUM", 14.0, "NEON BIS MITTERNACHT", 2),
    ("HOVERBOARDS", 14.0, "DIE DINGER FAHREN NICHT AUF WASSER", 3),
    ("HOLOGRAMM-HAI", 14.0, "DER HAI SIEHT NOCH IMMER FALSCH AUS", 3),
    ("GEWITTER", 14.0, "22:04 - DER BLITZ SCHLÄGT EIN", -1),
]
EV_COACH, EV_TRAIN, EV_MANURE, EV_DANCE, EV_SKATE, EV_MALL, EV_HOVER, EV_SHARK, EV_STORM = range(9)
# Zellen im Verkehrsbogen (Reihe = Epoche, Zelle = Reihe*8 + Spalte)
ROAD_CELLS = {0: (0, 1, 3, 7), 1: (8, 9, 10, 11, 12, 13, 14, 15), 2: (16, 17, 18, 19, 20, 21, 22, 23),
              3: (24, 25, 26, 27, 28, 29, 30)}
SIDE_CELLS = {0: (4, 6), 1: (), 2: (), 3: ()}
SLOW_CELLS = {0, 3, 7, 11, 18, 27}            # Reiter, Planwagen, Longhorn, Fahrrad, Skateboarder, Hoverboarder: langsam
CELL_COACH, CELL_TRAIN, CELL_TUMBLE, CELL_MANURE, CELL_SKATE, CELL_HOVER, CELL_SHARK = 1, 2, 5, 12, 18, 27, 31
KIND_ROAD, KIND_SIDE, KIND_FLY = 0, 1, 2


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


def _windshield_mask(img: np.ndarray, rect) -> np.ndarray:
    """Alpha des Cockpits: 255 = Armatur/Rahmen (vorn), 0 = Scheibe (Epoche dahinter).

    Scheibe = zusammenhängende, (fast) schwarze Fläche, die im Scheibenbereich `rect` (x0, x1, y0, y1, y von unten)
    liegt; dunkle Stellen des Armaturenbretts bleiben dadurch vorn. Weicher Rand über 3 px."""
    h, w = img.shape[:2]
    luma = img[..., :3].max(axis=2)
    black = luma < 10
    x0, x1, y0, y1 = rect
    inside = np.zeros((h, w), dtype=bool)
    inside[max(0, int(y0 * h) - 8):int(y1 * h) + 1, int(x0 * w):int(x1 * w) + 1] = True     # Zeilen von unten
    shield = black & inside
    lab, n = blobs.label(shield)
    if n > 0:
        keep = np.flatnonzero(blobs.sizes(lab, n) >= 0.002 * h * w) + 1                     # nur große Flächen
        shield = np.isin(lab, keep)
    alpha = blobs.blur3((~shield).astype(np.float32))
    return np.clip(alpha * 255.0, 0, 255).astype(np.uint8)


class Mover:
    """Etwas, das von weit hinten (z=0) auf die Kamera zukommt (z=1): auf der Straße, am Straßenrand oder fliegend."""

    def __init__(self, rng: random.Random, cell: int, x: float, kind: int, own: float, height: float = 0.0,
                 big: float = 1.0, drift: float = 0.0):
        self.cell, self.x, self.kind, self.own, self.height, self.big, self.drift = cell, x, kind, own, height, big, drift
        self.z = 0.0
        self.seed = rng.random()


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.vanish = tuple(float(v) for v in scene_cfg.get("vanish", [0.5, 0.42]))
        sh = [float(v) for v in scene_cfg.get("windshield", [0.0, 1.0, 0.36, 1.0])]
        sh[2] = max(sh[2], SHIELD_Y0)          # die Config ist nur ein Hinweis: das Armaturenbrett im Bild ist ebenfalls schwarz
        self.shield = tuple(sh)
        # Cockpit um `cockpit_drop` nach unten schieben (mehr Scheibe); der Shader bekommt die Scheibenkante auf dem Schirm
        self.drop = float(scene_cfg.get("cockpit_drop", COCKPIT_DROP))
        self.shield_screen = (sh[0], sh[1], sh[2] - self.drop, self.drop)
        self.cockpit = _load_rgba(ASSETS / "timejump_cockpit.png")
        if self.cockpit is not None:
            self.cockpit = self.cockpit.copy()
            self.cockpit[..., 3] = _windshield_mask(self.cockpit, self.shield)
        self.eras = [_load_rgba(ASSETS / f"timejump_{name}.png") for name in ERA_NAMES]
        self.traffic = _load_rgba(ASSETS / "timejump_traffic.png")
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
        self.driving = False
        self.mph = 0.0
        self.boost = 0.0
        self.dist = 0.0
        self.lane = 0.0
        self.lane_target = 0.0
        self.honk_t0 = -10.0
        self.circuit_t0 = -10.0
        self.jump_t0 = -10.0
        self.jump_swapped = True
        self.era = self.rng.randrange(4)
        if os.environ.get("KITT_TIMEJUMP_ERA", "").isdigit():       # Test: Startepoche vorgeben
            self.era = int(os.environ["KITT_TIMEJUMP_ERA"]) % 4
        self.era_from = self.era
        self.era_prev = self.rng.choice([e for e in range(4) if e != self.era])
        self.era_next = self.rng.choice([e for e in range(4) if e not in (self.era, self.era_prev)])
        self.jumps = 0
        self.event: dict | None = None
        self.next_event_at = 0.0
        self.movers: list[Mover] = []
        self.started_at = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 3.0
        self.demo_jump_at = 0.0
        if demo:
            self.start()
        log.info("Zeitsprung: Cockpit %s, Epochen %s, Verkehr %s, Start in %s",
                 "ok" if self.cockpit is not None else "fehlt",
                 "/".join("ok" if e is not None else "fehlt" for e in self.eras),
                 "ok" if self.traffic is not None else "fehlt", ERA_NAMES[self.era])

    # -- Aktionen ----------------------------------------------------------
    def start(self) -> None:
        if self.driving:
            return
        self.driving = True
        now = time.monotonic()
        self.started_at = now
        self.boost = 0.0
        self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.25 if self.demo else 0.7)
        self.demo_jump_at = now + 12.0
        self._led_event("timejump_start", now + 3.0)
        log.info("Gas gegeben in %s", ERA_NAMES[self.era])

    def stop(self) -> None:
        if not self.driving:
            return
        self.driving = False
        self.event = None
        secs = int(time.monotonic() - self.started_at)
        log.info("Angehalten nach %d:%02d, %d Zeitsprünge", secs // 60, secs % 60, self.jumps)
        wled.apply_mode_async("timejump")

    def change_lane(self, d: float) -> None:
        self.lane_target = max(-1.0, min(1.0, self.lane_target + d))

    def honk(self) -> None:
        self.honk_t0 = time.monotonic()
        self._led_event("timejump_honk", self.honk_t0 + HONK_LEN)

    def toggle_circuits(self) -> None:
        """Nächste Epoche vorwählen (Reihenfolge der Zeitkreise), Anzeige rattert."""
        others = [e for e in range(4) if e != self.era]
        self.era_next = others[(others.index(self.era_next) + 1) % 3] if self.era_next in others else others[0]
        self.circuit_t0 = time.monotonic()
        log.info("Zeitkreise: Ziel %s", ERA_NAMES[self.era_next])

    def jump(self, now: float | None = None) -> None:
        """Zeitsprung zünden: Blitz, Feuerspuren, in der Mitte wechselt die Epoche."""
        now = time.monotonic() if now is None else now
        if now - self.jump_t0 < JUMP_LEN:
            return
        self.jump_t0 = now
        self.jump_swapped = False
        self.jumps += 1
        self._led_event("timejump_jump", now + JUMP_LEN)
        log.info("Zeitsprung bei %d MPH: %s -> %s", int(self.mph), ERA_NAMES[self.era], ERA_NAMES[self.era_next])

    def _swap_era(self) -> None:
        self.era_prev, self.era_from = self.era, self.era
        self.era = self.era_next
        self.era_next = self.rng.choice([e for e in range(4) if e not in (self.era, self.era_prev)])   # nie dieselbe, gern eine neue
        self.movers = []
        self.event = None
        self.mph = min(self.mph, 42.0)
        self.boost = 0.0
        self.demo_jump_at = time.monotonic() + self.rng.uniform(14.0, 20.0)

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        log.info("Drop: sofortiger Zeitsprung")
        self.mph = max(self.mph, MPH_JUMP)
        self.jump(now)

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
            self.toggle_circuits()

    # -- Verkehr -----------------------------------------------------------
    def _add(self, m: Mover) -> bool:
        if len(self.movers) >= N_MOV:
            return False
        self.movers.append(m)
        return True

    def _spawn(self, now: float, dt: float) -> None:
        ev = self.event["kind"] if self.event else -1
        era = self.era
        speed_n = self.mph / MPH_JUMP
        rate = (0.3 + 1.2 * speed_n) * (0.4 + 1.6 * self.mid_s) * dt      # Mitten = Verkehrsdichte
        rng = self.rng
        if era == 3:                                                       # Zukunft: alles fliegt
            if rng.random() < rate * 0.6:
                cell = CELL_HOVER if ev == EV_HOVER and rng.random() < 0.7 else rng.choice(ROAD_CELLS[3])
                low = cell == CELL_HOVER
                self._add(Mover(rng, cell, rng.uniform(-1.0, 1.0), KIND_FLY, rng.uniform(0.2, 0.6),
                                height=rng.uniform(0.05, 0.3) if low else rng.uniform(0.3, 1.0)))
        else:
            if rng.random() < rate * 0.5:
                cells = ROAD_CELLS[era]
                if era == 0 and rng.random() < 0.25:
                    self._add(Mover(rng, CELL_TUMBLE, -1.4, KIND_ROAD, 0.0, drift=rng.uniform(0.6, 1.2)))
                else:
                    cell = rng.choice(cells)
                    if ev == EV_SKATE and rng.random() < 0.6:
                        cell = CELL_SKATE
                    own = rng.uniform(0.15, 0.35) if cell in SLOW_CELLS else rng.uniform(0.4, 0.75)
                    self._add(Mover(rng, cell, rng.choice((-1.0, 0.0, 1.0)), KIND_ROAD, own))
            if SIDE_CELLS[era] and rng.random() < rate * 0.35:
                cell = rng.choice(SIDE_CELLS[era])
                self._add(Mover(rng, cell, rng.choice((-1.0, 1.0)), KIND_SIDE, 0.0, big=1.6 if cell == 6 else 1.0))
        # Ereignis-Gäste
        if ev == EV_COACH and rng.random() < dt * 0.25:
            self._add(Mover(rng, CELL_COACH, rng.choice((-1.0, 1.0)), KIND_ROAD, -0.6))         # kommt von hinten vorbei
        elif ev == EV_TRAIN and rng.random() < dt * 0.2:
            self._add(Mover(rng, CELL_TRAIN, rng.choice((-1.0, 1.0)), KIND_SIDE, -0.9, big=1.5))
        elif ev == EV_MANURE and rng.random() < dt * 0.2:
            self._add(Mover(rng, CELL_MANURE, 0.0, KIND_ROAD, 0.15, big=1.3))

    def _advance_movers(self, dt: float) -> None:
        speed_n = self.mph / MPH_JUMP
        honk = time.monotonic() - self.honk_t0 < HONK_LEN
        keep = []
        for m in self.movers:
            rel = speed_n - m.own * 0.6
            if m.kind == KIND_ROAD and m.own > 0.0:
                rel = max(0.03, rel)
            elif m.own < 0.0:
                rel = max(rel, 0.35 - m.own)                               # rast vorbei
            m.z += dt * rel * 0.45
            if m.drift:
                m.x += dt * m.drift * (0.5 + 0.5 * self.high_s)            # Steppenläufer rollt über die Straße
            if honk and m.kind == KIND_ROAD and abs(m.x - self.lane) < 0.6:
                m.x += dt * 1.5 * (1.0 if m.x >= self.lane else -1.0)
            if m.z < 1.0 and abs(m.x) < 2.2:
                keep.append(m)
        self.movers = keep

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        out = {"uCockpitTex": (self.cockpit if self.cockpit is not None else self.blank, 1)}
        for i, e in enumerate(self.eras):
            out[f"uEra{i}Tex"] = (e if e is not None else self.blank, 1)
        out["uTrafficTex"] = (self.traffic if self.traffic is not None else self.blank, 1)
        return out

    def uniform_names(self):
        names = ["uCockpitTex", "uEra0Tex", "uEra1Tex", "uEra2Tex", "uEra3Tex", "uTrafficTex", "uCockpitSize",
                 "uEraSize", "uTrafficSize", "uSeed", "uVanish", "uShield", "uBassS", "uMidS", "uHighS", "uEnergy",
                 "uLive", "uBeatPulse", "uBeatStep", "uSpeed", "uMph", "uDist", "uLane", "uDriving", "uHonkT",
                 "uCircuitT", "uJumpT", "uEraA", "uEraB", "uEraMix", "uEvent", "uEventT", "uEventLen"]
        names += [f"uMov{i}" for i in range(N_MOV)]
        names += [f"uMovP{i}" for i in range(N_MOV)]
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
        jt = now - self.jump_t0
        jumping = jt < JUMP_LEN
        if jumping and not self.jump_swapped and jt >= JUMP_SWAP:
            self.jump_swapped = True
            self._swap_era()
        # Tempo: Energie der Musik plus Schub bei anhaltend lauter Musik; Stille = ausrollen; nach dem Sprung ~40
        if self.driving:
            if live:
                self.boost = max(0.0, min(30.0, self.boost + dt * 6.0 * (self.energy - 0.45)))
            else:
                self.boost = max(0.0, self.boost - dt * 4.0)
            target = (35.0 + 50.0 * self.energy + self.boost) * live + (1.0 - live) * 8.0
            if jumping:
                target = MPH_JUMP + 6.0 if jt < JUMP_SWAP else 40.0
        else:
            target = 0.0
            self.boost = 0.0
        self.mph += (target - self.mph) * min(1.0, dt / (1.8 if target > self.mph else 3.0))
        if self.driving and not jumping and jt > JUMP_LEN + 2.0:
            if self.mph >= MPH_JUMP - 0.5 or (self.demo and now >= self.demo_jump_at and live):
                self.mph = max(self.mph, MPH_JUMP)
                self.jump(now)
        speed_n = self.mph / MPH_JUMP
        self.dist += dt * speed_n
        self.lane += (self.lane_target - self.lane) * min(1.0, dt / 0.8)
        if self.driving:
            self._spawn(now, dt)
            self._advance_movers(dt)
            ev = self.event
            if ev is None and now >= self.next_event_at and not jumping:
                choices = [k for k, e in enumerate(EVENTS) if e[3] in (-1, self.era)]
                kind = self.rng.choice(choices)
                self.event = {"kind": kind, "t0": now, "len": EVENTS[kind][1]}
                log.info("Ereignis: %s", EVENTS[kind][0])
                if kind == EV_STORM:
                    self._led_event("timejump_storm", now + EVENTS[kind][1])
            elif ev is not None and now - ev["t0"] >= ev["len"]:
                self.event = None
                self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.3 if self.demo else 1.0)
        else:
            self._advance_movers(dt)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("timejump")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "honk", "circuits", "circuits"))
            {"left": lambda: self.change_lane(-1.0), "right": lambda: self.change_lane(1.0), "honk": self.honk,
             "circuits": self.toggle_circuits}[pick]()
            self.demo_next = now + 6.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        ev = self.event
        era_img = next((e for e in self.eras if e is not None), None)
        if jumping:
            era_a, era_b = self.era_from, (self.era if self.jump_swapped else self.era_next)
            k = (jt - (JUMP_SWAP - 0.35)) / 0.7
            era_mix = max(0.0, min(1.0, k * k * (3.0 - 2.0 * k)))
        else:
            era_a, era_b, era_mix = self.era, self.era_next, 0.0
        out = {
            "uCockpitSize": size(self.cockpit), "uEraSize": size(era_img), "uTrafficSize": size(self.traffic),
            "uSeed": self.seed, "uVanish": self.vanish, "uShield": self.shield_screen, "uBassS": self.bass_s, "uMidS": self.mid_s,
            "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse,
            "uBeatStep": float(self.beat_step), "uSpeed": speed_n, "uMph": self.mph, "uDist": self.dist % 1000.0,
            "uLane": self.lane, "uDriving": 1.0 if self.driving else 0.0,
            "uHonkT": (now - self.honk_t0) if now - self.honk_t0 < HONK_LEN else -1.0,
            "uCircuitT": (now - self.circuit_t0) if now - self.circuit_t0 < CIRCUIT_LEN else -1.0,
            "uJumpT": jt if jumping else -1.0,
            "uEraA": float(era_a), "uEraB": float(era_b), "uEraMix": era_mix,
            "uEvent": float(ev["kind"] + 1) if ev else 0.0, "uEventT": (now - ev["t0"]) if ev else 0.0,
            "uEventLen": ev["len"] if ev else 1.0,
        }
        movers = sorted(self.movers, key=lambda m: m.z)                      # fern zuerst, nah zuletzt gezeichnet
        for i in range(N_MOV):
            if i < len(movers):
                m = movers[i]
                out[f"uMov{i}"] = (float(m.cell), m.x, m.z, m.seed)
                out[f"uMovP{i}"] = (float(m.kind), m.height, m.big, m.own)
            else:
                out[f"uMov{i}"] = (0.0, 0.0, -1.0, 0.0)
                out[f"uMovP{i}"] = (0.0, 0.0, 1.0, 0.0)
        return out

    # -- Overlays ----------------------------------------------------------
    def _date(self, era: int, rattle: bool) -> str:
        s = ERA_DATES[era]
        if not rattle:
            return s
        return "".join(str(self.rng.randrange(10)) if c.isdigit() else c for c in s)

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        rattle = now - self.circuit_t0 < CIRCUIT_LEN
        jt = now - self.jump_t0
        dim = 1.0 if self.driving else 0.45
        if jt < JUMP_LEN and not self.jump_swapped:
            rattle = True
        # Zeitkreise in den drei Anzeigen des Cockpits (rechts): Ziel rot, Jetzt grün, Zuletzt gelb
        flick = 0.85 + 0.15 * np.sin(t * 37.0)
        d = self.drop
        rows = ((self.era_next, CIRCUIT_Y[0] - d, (255, 70, 50)), (self.era, CIRCUIT_Y[1] - d, (70, 255, 110)), (self.era_prev, CIRCUIT_Y[2] - d, (255, 215, 60)))
        for era, y, color in rows:
            out.append((self._date(era, rattle), 0.025, CIRCUIT_X, y, color, dim * flick))
        if not self.driving:
            out.append(("Z E I T S P R U N G", 0.05, 0.5, 0.74, (255, 170, 60), 0.7 + 0.3 * np.sin(t * 2.0)))
            out.append(("STARTKNOPF = GAS GEBEN      KIPPSCHALTER = ANHALTEN      KNÜPPEL UNTEN = ZEITKREISE", 0.018, 0.5, 0.67, (160, 220, 255), 0.7))
            out.append((f"{ERA_NAMES[self.era]}  {ERA_LABELS[self.era]}", 0.022, 0.5, 0.60, (255, 220, 160), 0.6))
            out.append(("0 MPH", 0.05, MPH_X, MPH_Y, (255, 170, 60), 0.45))
        else:
            mph = int(self.mph)
            hot = self.mph >= MPH_JUMP - 0.5
            col = (200, 230, 255) if hot else (255, 170, 60)
            out.append((f"{mph} MPH", 0.05, MPH_X, MPH_Y, col, 0.9 if not hot else 0.6 + 0.4 * np.sin(t * 25.0)))
            secs = int(now - self.started_at)
            out.append((f"{ERA_NAMES[self.era]}  {ERA_LABELS[self.era]}     {secs // 60}:{secs % 60:02d}     SPUR {int(round(self.lane)) + 2}",
                        0.018, 0.5, 0.925, (160, 220, 255), 0.55))
            if self.event:
                name, length, line, _ = EVENTS[self.event["kind"]]
                k = (now - self.event["t0"]) / length
                a = min(1.0, k * 6.0) * min(1.0, (1.0 - k) * 6.0)
                out.append((name, 0.03, 0.5, 0.90, (255, 170, 60), 0.9 * a))
                out.append((line, 0.017, 0.5, 0.86, (200, 240, 255), 0.8 * a))
            if jt < JUMP_LEN:
                a = min(1.0, jt * 4.0) * min(1.0, (JUMP_LEN - jt) * 2.0)
                out.append(("Z E I T S P R U N G", 0.07, 0.5, 0.52, (220, 240, 255), a * (0.5 + 0.5 * np.sin(t * 30.0))))
                if self.jump_swapped:
                    out.append((f"{ERA_NAMES[self.era]} - {ERA_LABELS[self.era]}", 0.03, 0.5, 0.45, (255, 220, 160), a))
            if now - self.honk_t0 < 1.2:
                out.append(("HUPE", 0.025, 0.5, 0.80, (255, 255, 200), 1.0 - (now - self.honk_t0) / 1.2))
            if rattle and jt >= JUMP_LEN:
                out.append((f"ZIEL: {ERA_NAMES[self.era_next]} {ERA_LABELS[self.era_next]}", 0.022, 0.5, 0.80, (255, 70, 50), 0.9))
        return out
