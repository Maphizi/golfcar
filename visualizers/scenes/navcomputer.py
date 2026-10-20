"""Navigationscomputer (F2): Planeten durchblättern und anfliegen.

Bedienung:  Maus links / Pfeil links = vorheriger Planet, Maus rechts / Pfeil rechts = nächster,
            Maus Mitte oder Startknopf (Enter) = Kurs setzen und anfliegen. Kein Schießen mehr.
Phasen:     0 browse (Planet steht, Sterne ruhen) -> 1 launch (Sterne ziehen sich zu Streifen)
            -> 2 cruise (psychedelischer Schweif, langsam) -> 3 arrive (Ziel wächst aus der Mitte) -> browse
Der Flug endet nur, wenn der Pilot den Kippschalter umlegt (nie von selbst; im --demo nach cruise_seconds).
Unterwegs passiert alle 30 bis 60 s zufällig ein Ereignis (EVENTS): Asteroidenfeld mit Einschlägen und
Schildanzeige, Farbnebel mit Blitzen, Vorbeiflug an einer Sonne, Wurmloch, Raumstation, Kometenschauer.
Drei Sekunden vorher blinkt die Warnung im HUD.
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
# Verkehr im Hyperraum: Kometen zwischen den Planeten (selten, klein), nur zum Anschauen. Der Shader kennt auch Schiffe
# (Arten 0 Jäger, 1 Satellit, 2 Kreuzer, 3 Ringstation, 5 Stationsmodule), sie sind hier abgeschaltet;
# TRAFFIC_KINDS erweitern, um sie wieder einzuschalten.
TRAFFIC_MAX = 1
TRAFFIC_EVERY = (15.0, 30.0)
TRAFFIC_KINDS = [4]
COMET_SCALE = 0.45
TRAFFIC_NAMES = ["JÄGER", "SATELLIT", "KREUZER", "RINGSTATION", "KOMET", "STATION"]
PHASE_BROWSE, PHASE_LAUNCH, PHASE_CRUISE, PHASE_ARRIVE = 0, 1, 2, 3
# Ereignisse unterwegs: (Name, Dauer in s, HUD-Zeile während des Ereignisses); Index + 1 = uEvent im Shader
EVENTS = [
    ("ASTEROIDENFELD", 17.0, "AUSWEICHEN   SCHILDE {shield:3.0f} %"),
    ("FARBNEBEL", 18.0, "SENSOREN GESTÖRT   SICHT NULL"),
    ("SONNE", 16.0, "HITZESCHILD AKTIV   ABSTAND HALTEN"),
    ("WURMLOCH", 12.0, "RAUMZEIT INSTABIL   FESTHALTEN"),
    ("RAUMSTATION", 10.0, "ANDOCKEN VERWEIGERT   WEITERFLUG"),
    ("KOMETENSCHAUER", 12.0, "TRÜMMER VORAUS   KURS HALTEN"),
]
EVENT_EVERY = (30.0, 60.0)
EVENT_WARN = 3.0
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
        self.last_f = None
        self.armed = False          # Kippschalter-Zustand
        self.end_after_launch = False
        # Ereignisse unterwegs
        self.event: dict | None = None
        self.next_event_at = 0.0
        self.shield = 100.0
        self.impact = (0.0, 0.0, -10.0)    # x, y, Zeitpunkt
        self.next_impact_at = 0.0
        self.flash = (0.0, -10.0)          # Winkel, Zeitpunkt
        self.next_flash_at = 0.0
        self.next_comet_at = 0.0
        self.event_seed = 0.5

    # -- Eingabe ---------------------------------------------------------
    def handle_event(self, ev) -> None:
        # Kippschalter (PXN-CB1, Code 267): dpad_remap.py schickt SPACE für AN und BACKSPACE für AUS,
        # Startknopf (266) kommt als ENTER. F13/F14 der älteren joystick.py werden bewusst ignoriert,
        # sonst würde ein Druck doppelt gezählt. Ablauf: AN = scharf, Start = los, Flug bis AUS.
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_SPACE, pygame.K_BACKSPACE):
                # Kippschalter umgelegt: im Flug = Ankunft einleiten (egal in welche Richtung),
                # sonst scharf (AN) / gesichert (AUS)
                if self.phase in (PHASE_CRUISE, PHASE_LAUNCH):
                    self.end_flight()
                else:
                    self.set_armed(ev.key == pygame.K_SPACE)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.fly()   # Startknopf fliegt direkt, kein armed nötig (im Flug ohne Funktion)
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                self.select(-1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                self.select(+1)
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
        """Kippschalter außerhalb des Flugs: nur Anzeige scharf / gesichert."""
        self.armed = on

    def end_flight(self) -> None:
        """Ankunft einleiten: im Hyperraum sofort, während des Starts nach dem Start."""
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
            self.event = None
            self.next_event_at = self.phase_t0 + self.rng.uniform(*EVENT_EVERY) * 0.6   # erstes Ereignis etwas früher
            self.shield = 100.0
        elif ph != PHASE_CRUISE:
            self.fly_idx = -1
            self.event = None

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
        elif self.phase == PHASE_CRUISE and self.demo and pt >= self.cruise_s:
            self._set_phase(PHASE_ARRIVE)      # nur im Demo: feste Flugdauer. Sonst endet der Flug allein per Kippschalter
        elif self.phase == PHASE_ARRIVE and pt >= self.arrive_s:
            self._set_phase(PHASE_BROWSE)
        self._advance_flyby(now)
        self._advance_traffic(now)
        self._advance_event(now)
        if self.demo and self.phase == PHASE_BROWSE and now >= self.demo_next:
            if self.rng.random() < 0.6:
                self.select(self.rng.choice((-1, 1)))
                self.demo_next = now + 1.5
            else:
                self.fly()
                self.demo_next = now + self.launch_s + self.cruise_s + self.arrive_s + 3.0

    def _spawn_traffic(self, kind: int, now: float, scale: float, length: float, cross: bool = False) -> None:
        self.traffic.append({
            "kind": kind, "t0": now, "len": length, "ang": self.rng.uniform(0.0, 6.283), "dir": self.rng.choice((-1.0, 1.0)),
            "spin": self.rng.uniform(-0.3, 0.3), "cross": cross, "y": self.rng.uniform(-0.4, 0.5), "scale": scale,
        })

    def _advance_event(self, now: float) -> None:
        """Ereignisse im Hyperraum: Warnung, dann 10 bis 18 s Ereignis, dann 30 bis 60 s Ruhe."""
        if self.phase != PHASE_CRUISE:
            self.shield = min(100.0, self.shield + 0.05)
            return
        ev = self.event
        if ev is None:
            if now >= self.next_event_at:
                kind = self.rng.randrange(len(EVENTS))
                self.event = {"kind": kind, "warn_t0": now, "t0": now + EVENT_WARN, "len": EVENTS[kind][1], "started": False}
                self.event_seed = self.rng.random()
                log.info("Ereignis voraus: %s", EVENTS[kind][0])
            else:
                self.shield = min(100.0, self.shield + 0.03)
            return
        kind = ev["kind"]
        if not ev["started"] and now >= ev["t0"]:
            ev["started"] = True
            if kind == 4:                                   # Raumstation zieht groß vorbei
                self._spawn_traffic(3, now, 2.6, ev["len"], cross=True)
            elif kind == 5:
                self.next_comet_at = now
            elif kind == 0:
                self.next_impact_at = now + self.rng.uniform(1.0, 2.5)
            elif kind == 1:
                self.next_flash_at = now + self.rng.uniform(1.0, 3.0)
        if ev["started"]:
            if kind == 0 and now >= self.next_impact_at:   # Einschlag: Schild nimmt Schaden
                self.impact = (self.rng.uniform(-1.2, 1.2), self.rng.uniform(-0.7, 0.7), now)
                self.shield = max(5.0, self.shield - self.rng.uniform(4.0, 11.0))
                self.next_impact_at = now + self.rng.uniform(1.5, 3.5)
            elif kind == 1 and now >= self.next_flash_at:   # Blitz im Nebel
                self.flash = (self.rng.uniform(0.0, 6.283), now)
                self.next_flash_at = now + self.rng.uniform(1.5, 4.0)
            elif kind == 5 and now >= self.next_comet_at and len(self.traffic) < 4:
                self._spawn_traffic(4, now, self.rng.uniform(0.5, 0.9), self.rng.uniform(2.5, 4.0), cross=self.rng.random() < 0.5)
                self.next_comet_at = now + self.rng.uniform(0.9, 1.6)
            if now >= ev["t0"] + ev["len"]:
                self.event = None
                self.next_event_at = now + self.rng.uniform(*EVENT_EVERY)
                log.info("Ereignis vorbei: %s", EVENTS[kind][0])

    def uniform_names(self):
        return ("uPhase", "uPhaseT", "uSlide", "uPlanetType", "uColA", "uColB", "uPlanetSize", "uRings", "uMoons", "uLaunchS", "uCruiseS", "uArriveS",
                "uFly", "uFlyType", "uFlySize", "uFlyRings", "uFlySide", "uFlyColA", "uFlyColB", "uSponsorTex", "uSponsorOK",
                "uShip0", "uShip1", "uShip2", "uShipP0", "uShipP1", "uShipP2", "uCross", "uLaser", "uLaserTo", "uBoom", "uBoomKind", "uShoot",
                "uEvent", "uEventT", "uEventLen", "uEventWarn", "uEventSeed", "uShield", "uImpact", "uFlash")

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
        # Abschießen gibt es nicht mehr: Fadenkreuz, Laser und Explosion bleiben aus
        ships.update({"uCross": (0.0, 0.0), "uLaser": 0.0, "uLaserTo": (0.0, 0.0),
                      "uBoom": (0.0, 0.0, 9.0, 0.0), "uBoomKind": 0.0, "uShoot": 0.0})
        ev = self.event
        started = bool(ev and ev["started"])
        ships.update({
            "uEvent": float(ev["kind"] + 1) if started else 0.0,
            "uEventT": (now - ev["t0"]) if started else 0.0,
            "uEventLen": ev["len"] if ev else 0.0,
            "uEventWarn": min(1.0, (now - ev["warn_t0"]) / EVENT_WARN) if ev and not started else 0.0,
            "uEventSeed": self.event_seed,
            "uShield": self.shield / 100.0,
            "uImpact": (self.impact[0], self.impact[1], now - self.impact[2], 0.0),
            "uFlash": (self.flash[0], now - self.flash[1], 0.0, 0.0),
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
            if self.fly_idx >= 0:
                k = (now - self.fly_t0) / self.fly_len
                fp = self.planets[self.fly_idx]
                out.append((f"PASSIERE  {fp['name'].upper()}", 0.03, 0.5, 0.9, (255, 236, 120), min(1.0, k * 4.0) * min(1.0, (1.0 - k) * 4.0) * 0.9))
            out.append((f"HYPERRAUM   ZIEL {p['name'].upper()}   FLUGZEIT {pt:05.1f}   KIPPSCHALTER = ANKUNFT", 0.028, 0.5, 0.06, DIM, 0.8))
            ev = self.event
            if ev is not None:
                name, _, line = EVENTS[ev["kind"]]
                if not ev["started"]:
                    out.append((f"ACHTUNG   {name} VORAUS", 0.036, 0.5, 0.8, (255, 70, 50), 0.4 + 0.6 * abs(math.sin(t * 6.0))))
                else:
                    k = (now - ev["t0"]) / ev["len"]
                    a = min(1.0, k * 6.0) * min(1.0, (1.0 - k) * 6.0)
                    out.append((name, 0.034, 0.5, 0.8, (255, 200, 90), 0.9 * a))
                    out.append((line.format(shield=self.shield), 0.024, 0.5, 0.755, (255, 150, 90) if ev["kind"] == 0 and self.shield < 50 else (230, 200, 140), 0.85 * a))
            return out
        return [(f"ANKUNFT   {p['name'].upper()}", 0.05, 0.5, 0.88, YEL, min(1.0, pt / 1.5))]
