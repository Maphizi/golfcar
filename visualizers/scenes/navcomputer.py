"""Navigationscomputer (F2): Planeten durchblättern und anfliegen.

Bedienung:  Maus links / Pfeil links = vorheriger Planet, Maus rechts / Pfeil rechts = nächster,
            Maus Mitte, Enter oder Leertaste = Kurs setzen und anfliegen.
Phasen:     0 browse (Planet steht, Sterne ruhen) -> 1 launch (Sterne ziehen sich zu Streifen)
            -> 2 cruise (psychedelischer Schweif, langsam) -> 3 arrive (Ziel wächst aus der Mitte) -> browse
"""
from __future__ import annotations

import math
import random
import time

import pygame

from launcher import config as lcfg

import logging

log = logging.getLogger("navcomputer")

TYPES = ["desert", "ice", "forest", "ocean", "city", "volcanic", "gas", "swamp", "grass", "rock", "crystal", "star", "comet", "station"]
KINDS = {"desert": "WÜSTENWELT", "ice": "EISWELT", "forest": "WALDWELT", "ocean": "OZEANWELT", "city": "STADTWELT",
         "volcanic": "VULKANWELT", "gas": "GASRIESE", "swamp": "SUMPFWELT", "grass": "GRASWELT", "rock": "FELSWELT",
         "crystal": "KRISTALLWELT", "star": "STERN", "comet": "KOMET", "station": "KAMPFSTATION"}
ORIGINS = {"real": "ECHTER HIMMEL", "saga": "FERNE GALAXIS", "fiction": "ERDACHTE WELT"}
SPONSOR = lcfg.ROOT / "assets" / "sponsor.png"
FLYBY_EVERY = 25.0
# Verkehr im Hyperraum: Kometen zwischen den Planeten (selten, klein). Der Shader kennt auch Schiffe
# (Arten 0 Jäger, 1 Satellit, 2 Kreuzer, 3 Ringstation, 5 Stationsmodule), sie sind hier abgeschaltet;
# TRAFFIC_KINDS erweitern, um sie wieder einzuschalten.
TRAFFIC_MAX = 1
TRAFFIC_EVERY = (15.0, 30.0)
TRAFFIC_KINDS = [4]
COMET_SCALE = 0.45
TRAFFIC_NAMES = ["JÄGER", "SATELLIT", "KREUZER", "RINGSTATION", "KOMET", "STATION"]
CROSS_STEP = 0.14
PHASE_BROWSE, PHASE_LAUNCH, PHASE_CRUISE, PHASE_ARRIVE = 0, 1, 2, 3
YEL = (255, 214, 10)
DIM = (150, 130, 40)


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.planets = lcfg._load("planets.toml").get("planets", [])
        if not self.planets:
            self.planets = [{"name": "UNBEKANNT", "type": "rock", "subtitle": "", "color_a": [0.5] * 3, "color_b": [0.3] * 3}]
        self.launch_s = float(scene_cfg.get("launch_seconds", 3.5))
        self.cruise_s = float(scene_cfg.get("cruise_seconds", 14.0))
        self.arrive_s = float(scene_cfg.get("arrive_seconds", 4.0))
        self.idx = random.randrange(len(self.planets))
        self.target = self.idx
        self.phase = PHASE_BROWSE
        self.phase_t0 = time.monotonic()
        self.slide = 0.0            # -1..1 Richtung des letzten Wechsels, klingt ab
        self.slide_t0 = 0.0
        self.demo = demo
        self.demo_next = time.monotonic() + 3.0
        self.rng = random.Random()
        self.fly_idx = -1           # Vorbeiflug im Hyperraum: Index des Objekts, -1 = keiner
        self.fly_t0 = 0.0
        self.fly_len = 7.0
        self.next_fly_at = 0.0
        self.sponsor = None
        self.sponsor_version = 1
        if SPONSOR.exists():
            try:
                import numpy as np
                surf = pygame.image.load(str(SPONSOR))
                w, h = surf.get_size()
                rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
                try:
                    alpha = pygame.surfarray.array_alpha(surf).T
                except ValueError:
                    alpha = np.full((h, w), 255, dtype=np.uint8)
                self.sponsor = np.ascontiguousarray(np.dstack((rgb, alpha)).astype(np.uint8)[::-1])
            except Exception as exc:
                log.warning("Sponsor-Logo nicht ladbar: %s", exc)
        self.traffic: list[dict] = []      # {kind, t0, len, ang, dir, spin, cross}
        self.next_traffic_at = 0.0
        self.cross = [0.0, 0.1]            # Fadenkreuz (Bildkoordinaten, x in ±aspect, y in ±1)
        self.laser_t0 = -10.0
        self.laser_target = (0.0, 0.0)
        self.boom = None                   # (x, y, t0, kind)
        self.kills = 0
        self.shots = 0
        self.last_f = None
        self.armed = False          # Kippschalter-Zustand
        self.end_after_launch = False

    # -- Eingabe ---------------------------------------------------------
    def handle_event(self, ev) -> None:
        # Kippschalter (PXN-CB1, Code 267): dpad_remap.py schickt SPACE für AN und BACKSPACE für AUS,
        # Startknopf (266) kommt als ENTER. F13/F14 der älteren joystick.py werden bewusst ignoriert,
        # sonst würde ein Druck doppelt gezählt. Ablauf: AN = scharf, Start = los, Flug bis AUS.
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_SPACE, pygame.K_BACKSPACE):
                # Kippschalter (AN oder AUS): beide Zustände fliegen los
                if self.phase == PHASE_CRUISE:
                    pass  # im Hyperraum nichts tun
                else:
                    self.set_armed(True)
                    self.fly()
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.phase == PHASE_CRUISE:
                    self.shoot()
                elif self.armed:
                    self.fly()
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                if self.phase == PHASE_CRUISE:
                    self.cross[0] = max(-1.6, self.cross[0] - CROSS_STEP)
                else:
                    self.select(-1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                if self.phase == PHASE_CRUISE:
                    self.cross[0] = min(1.6, self.cross[0] + CROSS_STEP)
                else:
                    self.select(+1)
            elif ev.key == pygame.K_UP and self.phase == PHASE_CRUISE:
                self.cross[1] = min(0.9, self.cross[1] + CROSS_STEP)
            elif ev.key == pygame.K_DOWN and self.phase == PHASE_CRUISE:
                self.cross[1] = max(-0.9, self.cross[1] - CROSS_STEP)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                self.select(-1)
            elif ev.button == 3:
                self.select(+1)
            elif ev.button == 2:
                self.fly()
        elif ev.type == pygame.MOUSEWHEEL:
            self.select(-1 if ev.y > 0 else +1)

    def select(self, d: int) -> None:
        if self.phase != PHASE_BROWSE:
            return
        self.idx = (self.idx + d) % len(self.planets)
        self.slide = float(d)
        self.slide_t0 = time.monotonic()

    def fly(self) -> None:
        if self.phase != PHASE_BROWSE:
            return
        self.target = self.idx
        self._set_phase(PHASE_LAUNCH)

    def set_armed(self, on: bool) -> None:
        """Kippschalter. AUS während des Flugs leitet die Ankunft ein (im Hyperraum sofort, beim Start
        nach dem Start). Die Maus-Mitteltaste fliegt weiter ohne Kippschalter, mit fester Flugdauer."""
        if on == self.armed:
            return
        self.armed = on
        if not on:
            if self.phase == PHASE_CRUISE:
                self._set_phase(PHASE_ARRIVE)
            elif self.phase == PHASE_LAUNCH:
                self.end_after_launch = True

    def _set_phase(self, ph: int) -> None:
        self.phase = ph
        self.phase_t0 = time.monotonic()
        if ph == PHASE_CRUISE:
            self.fly_idx = -1
            self.next_fly_at = self.phase_t0 + self.rng.uniform(8.0, 14.0)
        elif ph != PHASE_CRUISE:
            self.fly_idx = -1

    # -- Verkehr und Schießen --------------------------------------------------
    def _traffic_pos(self, s: dict, now: float) -> tuple[float, float, float, float]:
        """(x, y, Größe, Fortschritt) eines Verkehrsobjekts."""
        k = min(1.0, (now - s["t0"]) / s["len"])
        if s["cross"]:
            # quert das Bild in mittlerer Entfernung
            x = (-1.9 + 3.8 * k) * s["dir"]
            y = s["y"] + 0.15 * math.sin(k * 3.0 + s["ang"])
            size = 0.13 + 0.06 * s["scale"]
        else:
            # kommt aus der Tiefe und fliegt an uns vorbei
            dist = 0.03 + k * k * 1.9
            x = math.cos(s["ang"]) * dist
            y = math.sin(s["ang"]) * dist * 0.7
            size = (0.02 + k ** 1.5 * 0.7) * s["scale"]
        return x, y, size, k

    def _advance_traffic(self, now: float) -> None:
        if self.phase != PHASE_CRUISE:
            self.traffic = []
            return
        self.traffic = [s for s in self.traffic if now - s["t0"] < s["len"]]
        if len(self.traffic) < TRAFFIC_MAX and now >= self.next_traffic_at:
            kind = self.rng.choice(TRAFFIC_KINDS)
            self.traffic.append({
                "kind": kind, "t0": now, "len": self.rng.uniform(2.5, 4.0) if kind == 4 else self.rng.uniform(5.0, 9.0),
                "ang": self.rng.uniform(0.0, 6.283), "dir": self.rng.choice((-1.0, 1.0)),
                "spin": self.rng.uniform(-0.6, 0.6), "cross": self.rng.random() < 0.35,
                "y": self.rng.uniform(-0.5, 0.6), "scale": self.rng.uniform(0.7, 1.3) * (COMET_SCALE if kind == 4 else 1.0),
            })
            self.next_traffic_at = now + self.rng.uniform(*TRAFFIC_EVERY)

    def shoot(self) -> None:
        now = time.monotonic()
        self.shots += 1
        self.laser_t0 = now
        self.laser_target = (self.cross[0], self.cross[1])
        best, best_d = None, 1e9
        for s in self.traffic:
            x, y, size, k = self._traffic_pos(s, now)
            d = math.hypot(x - self.cross[0], y - self.cross[1])
            if d < size * 1.3 + 0.08 and d < best_d:
                best, best_d = s, d
        if best is not None:
            x, y, size, _ = self._traffic_pos(best, now)
            self.boom = (x, y, now, best["kind"], size)
            self.traffic.remove(best)
            self.kills += 1
            log.info("Abschuss: %s (%d/%d)", TRAFFIC_NAMES[best["kind"]], self.kills, self.shots)

    def _advance_flyby(self, now: float) -> None:
        """Alle ~25 s im Hyperraum zieht eines der anderen Objekte vorbei."""
        if self.phase != PHASE_CRUISE or len(self.planets) < 2:
            return
        if self.fly_idx >= 0 and now - self.fly_t0 >= self.fly_len:
            self.fly_idx = -1
            self.next_fly_at = now + FLYBY_EVERY + self.rng.uniform(-5.0, 5.0)
        if self.fly_idx < 0 and now >= self.next_fly_at:
            choices = [i for i in range(len(self.planets)) if i != self.idx]
            self.fly_idx = self.rng.choice(choices)
            self.fly_t0 = now
            self.fly_len = self.rng.uniform(6.0, 9.0)
            self.fly_side = self.rng.choice((-1.0, 1.0))
            log.info("Vorbeiflug: %s", self.planets[self.fly_idx].get("name"))

    # -- Zustand ---------------------------------------------------------
    def _advance(self) -> None:
        now = time.monotonic()
        pt = now - self.phase_t0
        if self.phase == PHASE_LAUNCH and pt >= self.launch_s:
            self._set_phase(PHASE_CRUISE)
            if self.end_after_launch:
                self.end_after_launch = False
                self._set_phase(PHASE_ARRIVE)
        elif self.phase == PHASE_CRUISE and not self.armed and pt >= self.cruise_s:
            self._set_phase(PHASE_ARRIVE)      # ohne Kippschalter (Maus/Demo): feste Flugdauer
        elif self.phase == PHASE_ARRIVE and pt >= self.arrive_s:
            self._set_phase(PHASE_BROWSE)
        self._advance_flyby(now)
        self._advance_traffic(now)
        if self.demo and self.phase == PHASE_BROWSE and now >= self.demo_next:
            if self.rng.random() < 0.6:
                self.select(self.rng.choice((-1, 1)))
                self.demo_next = now + 1.5
            else:
                self.fly()
                self.demo_next = now + self.launch_s + self.cruise_s + self.arrive_s + 3.0

    def uniform_names(self):
        return ("uPhase", "uPhaseT", "uSlide", "uPlanetType", "uColA", "uColB", "uPlanetSize", "uRings", "uMoons", "uLaunchS", "uCruiseS", "uArriveS",
                "uFly", "uFlyType", "uFlySize", "uFlyRings", "uFlySide", "uFlyColA", "uFlyColB", "uSponsorTex", "uSponsorOK",
                "uShip0", "uShip1", "uShip2", "uShipP0", "uShipP1", "uShipP2", "uCross", "uLaser", "uLaserTo", "uBoom", "uBoomKind", "uShoot")

    def images(self) -> dict:
        if self.sponsor is None:
            return {}
        return {"uSponsorTex": (self.sponsor, self.sponsor_version)}

    def _type_index(self, p: dict) -> float:
        return float(TYPES.index(p.get("type", "rock")) if p.get("type", "rock") in TYPES else 9)

    def uniforms(self, t: float, f) -> dict:
        self._advance()
        now = time.monotonic()
        self.last_f = f
        p = self.planets[self.idx]
        ships = {}
        for i in range(3):
            if i < len(self.traffic):
                s = self.traffic[i]
                x, y, size, k = self._traffic_pos(s, now)
                alpha = min(1.0, k * 6.0) * min(1.0, (1.0 - k) * 4.0 + 0.2)
                ships[f"uShip{i}"] = (x, y, size, float(s["kind"]))
                # Winkel klein halten: große Werte (Sekunden seit Boot mal Drehung) machen sin/cos auf der GPU ungenau
                ships[f"uShipP{i}"] = (alpha, (s["ang"] + (now - s["t0"]) * s["spin"]) % 6.2832, k, s["dir"])
            else:
                ships[f"uShip{i}"] = (0.0, 0.0, 0.0, 0.0)
                ships[f"uShipP{i}"] = (0.0, 0.0, 0.0, 1.0)
        boom = self.boom if self.boom and now - self.boom[2] < 1.4 else None
        ships.update({
            "uCross": (self.cross[0], self.cross[1]),
            "uLaser": max(0.0, 1.0 - (now - self.laser_t0) / 0.35),
            "uLaserTo": self.laser_target,
            "uBoom": (boom[0], boom[1], now - boom[2], boom[4]) if boom else (0.0, 0.0, 9.0, 0.0),
            "uBoomKind": float(boom[3]) if boom else 0.0,
            "uShoot": 1.0 if self.phase == PHASE_CRUISE else 0.0,
        })
        slide = self.slide * max(0.0, 1.0 - (now - self.slide_t0) / 0.6)
        return {
            "uPhase": float(self.phase),
            "uPhaseT": now - self.phase_t0,
            "uSlide": slide,
            "uPlanetType": self._type_index(p),
            "uColA": tuple(p.get("color_a", [0.5, 0.5, 0.5])),
            "uColB": tuple(p.get("color_b", [0.3, 0.3, 0.3])),
            "uPlanetSize": float(p.get("size", 1.0)),
            "uRings": 1.0 if p.get("rings", False) else 0.0,
            "uMoons": float(p.get("moons", 0)),
            "uLaunchS": self.launch_s, "uCruiseS": self.cruise_s, "uArriveS": self.arrive_s,
            "uFly": (min(1.0, (now - self.fly_t0) / self.fly_len) if self.fly_idx >= 0 else 0.0),
            "uFlyType": self._type_index(self.planets[self.fly_idx]) if self.fly_idx >= 0 else 9.0,
            "uFlySize": float(self.planets[self.fly_idx].get("size", 1.0)) if self.fly_idx >= 0 else 1.0,
            "uFlyRings": 1.0 if self.fly_idx >= 0 and self.planets[self.fly_idx].get("rings") else 0.0,
            "uFlySide": getattr(self, "fly_side", 1.0),
            "uFlyColA": tuple(self.planets[self.fly_idx].get("color_a", [0.5] * 3)) if self.fly_idx >= 0 else (0.5, 0.5, 0.5),
            "uFlyColB": tuple(self.planets[self.fly_idx].get("color_b", [0.3] * 3)) if self.fly_idx >= 0 else (0.3, 0.3, 0.3),
            "uSponsorOK": 1.0 if self.sponsor is not None else 0.0,
            **ships,
        }

    def overlays(self, t: float):
        base = self._overlays(t)
        # Text verwackelt zur Musik: Bass schüttelt, Beat stößt an, Höhen zittern fein
        f = self.last_f
        if f is not None and not getattr(f, "silent", True):
            bass, beat, high = float(getattr(f, "bass", 0.0)), float(getattr(f, "beat", 0.0)), float(getattr(f, "high", 0.0))
            # ganz dezent: höchstens wenige Pixel, keine Größenänderung
            amp = 0.0025 * bass + 0.004 * beat
            jx = amp * math.sin(t * 37.0) + 0.001 * high * math.sin(t * 91.0)
            jy = amp * math.cos(t * 29.0) + 0.001 * high * math.cos(t * 83.0)
            base = [(text, size, x + jx, y + jy, col, a) for text, size, x, y, col, a in base]
        # Sponsorzeile klein unten rechts; das Logo (assets/sponsor.png) zeichnet der Shader daneben
        base.append(("SPONSORED BY", 0.015, 0.76 if self.sponsor is not None else 0.845, 0.03, (120, 130, 150), 0.7))
        if self.sponsor is None:
            base.append(("SPACEX", 0.024, 0.925, 0.03, (150, 165, 190), 0.8))
        return base

    def _overlays(self, t: float):
        p = self.planets[self.idx]
        now = time.monotonic()
        pt = now - self.phase_t0
        n = len(self.planets)
        if self.phase == PHASE_BROWSE:
            fade = min(1.0, pt / 0.8) if pt < 1.0 else 1.0
            kind = KINDS.get(p.get("type", ""), "UNBEKANNT")
            extra = [ORIGINS[p["origin"]]] if p.get("origin") in ORIGINS else []
            if p.get("moons"):
                extra.append(f"{p['moons']} MOND" + ("E" if p["moons"] > 1 else ""))
            if p.get("rings"):
                extra.append("RINGSYSTEM")
            if p.get("suns", 1) > 1:
                extra.append(f"{p['suns']} SONNEN")
            return [
                (f"NAVIGATION   {self.idx + 1:02d} / {n:02d}", 0.024, 0.28, 0.72, DIM, 0.8),
                (p["name"].upper(), 0.075, 0.28, 0.60, YEL, 0.95 * fade),
                (kind + ("   ·   " + "  ·  ".join(extra) if extra else ""), 0.026, 0.28, 0.535, (255, 236, 120), 0.85 * fade),
                (p.get("subtitle", ""), 0.026 if len(p.get("subtitle", "")) <= 44 else 0.02, 0.28, 0.485, (200, 185, 110), 0.85 * fade),
                ("<  WÄHLEN  >     KIPPSCHALTER + START  KURS SETZEN", 0.024, 0.42, 0.06, DIM, 0.7 + 0.3 * math.sin(t * 2.0)),
                ("[ SCHARF  —  START DRÜCKEN ]" if self.armed else "[ GESICHERT  —  KIPPSCHALTER ]",
                 0.026, 0.72, 0.13,
                 (255, 60, 60) if self.armed else (70, 70, 70), 0.9),
            ]
        if self.phase == PHASE_LAUNCH:
            return [(f"KURS: {p['name'].upper()}", 0.05, 0.5, 0.88, YEL, 0.9), ("HYPERANTRIEB LÄDT", 0.028, 0.5, 0.83, (255, 236, 120), 0.5 + 0.5 * math.sin(t * 8.0))]
        if self.phase == PHASE_CRUISE:
            eta = max(0.0, self.cruise_s - pt)
            out = []
            if self.kills or self.shots:
                out.append((f"ABSCHÜSSE {self.kills}   SCHÜSSE {self.shots}", 0.024, 0.86, 0.9, (255, 120, 80), 0.9))
            near = any(math.hypot(x - self.cross[0], y - self.cross[1]) < size * 1.3 + 0.08
                       for x, y, size, _ in (self._traffic_pos(s, now) for s in self.traffic))
            out.append(("ZIEL ERFASST" if near else "D-PAD ZIELEN   START FEUER", 0.02, 0.5, 0.13,
                        (255, 80, 60) if near else DIM, 0.9 if near else 0.6))
            if self.fly_idx >= 0:
                k = (now - self.fly_t0) / self.fly_len
                fp = self.planets[self.fly_idx]
                out.append((f"PASSIERE  {fp['name'].upper()}", 0.03, 0.5, 0.9, (255, 236, 120), min(1.0, k * 4.0) * min(1.0, (1.0 - k) * 4.0) * 0.9))
            if self.armed:
                out.append((f"HYPERRAUM   ZIEL {p['name'].upper()}   FLUGZEIT {pt:05.1f}   KIPPSCHALTER AUS = ANKUNFT", 0.028, 0.5, 0.06, DIM, 0.8))
            else:
                out.append((f"HYPERRAUM   ZIEL {p['name'].upper()}   ANKUNFT IN {eta:04.1f}", 0.028, 0.5, 0.06, DIM, 0.8))
            return out
        return [(f"ANKUNFT   {p['name'].upper()}", 0.05, 0.5, 0.88, YEL, min(1.0, pt / 1.5))]
