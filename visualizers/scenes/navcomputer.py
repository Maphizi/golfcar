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

TYPES = ["desert", "ice", "forest", "ocean", "city", "volcanic", "gas", "swamp", "grass", "rock", "crystal"]
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
        self.armed = False  # Kippschalter-Zustand

    # -- Eingabe ---------------------------------------------------------
    def handle_event(self, ev) -> None:
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_F13:  # Kippschalter
                if self.phase in (PHASE_LAUNCH, PHASE_CRUISE, PHASE_ARRIVE):
                    self._set_phase(PHASE_BROWSE)  # Cruise abbrechen
                    self.armed = False
                else:
                    self.armed = not self.armed
                return
            if ev.key == pygame.K_F14:  # Startknopf
                if self.armed:
                    self.fly()
                return
            if ev.key in (pygame.K_LEFT, pygame.K_a):
                self.select(-1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                self.select(+1)
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.fly()
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

    def _set_phase(self, ph: int) -> None:
        self.phase = ph
        self.phase_t0 = time.monotonic()

    # -- Zustand ---------------------------------------------------------
    def _advance(self) -> None:
        now = time.monotonic()
        pt = now - self.phase_t0
        if self.phase == PHASE_LAUNCH and pt >= self.launch_s:
            self._set_phase(PHASE_CRUISE)
        elif self.phase == PHASE_CRUISE and pt >= self.cruise_s:
            self._set_phase(PHASE_ARRIVE)
        elif self.phase == PHASE_ARRIVE and pt >= self.arrive_s:
            self._set_phase(PHASE_BROWSE)
        if self.demo and self.phase == PHASE_BROWSE and now >= self.demo_next:
            if self.rng.random() < 0.6:
                self.select(self.rng.choice((-1, 1)))
                self.demo_next = now + 1.5
            else:
                self.fly()
                self.demo_next = now + self.launch_s + self.cruise_s + self.arrive_s + 3.0

    def uniform_names(self):
        return ("uPhase", "uPhaseT", "uSlide", "uPlanetType", "uColA", "uColB", "uPlanetSize", "uRings", "uMoons", "uLaunchS", "uCruiseS", "uArriveS")

    def uniforms(self, t: float, f) -> dict:
        self._advance()
        now = time.monotonic()
        p = self.planets[self.idx]
        slide = self.slide * max(0.0, 1.0 - (now - self.slide_t0) / 0.6)
        return {
            "uPhase": float(self.phase),
            "uPhaseT": now - self.phase_t0,
            "uSlide": slide,
            "uPlanetType": float(TYPES.index(p.get("type", "rock")) if p.get("type", "rock") in TYPES else 9),
            "uColA": tuple(p.get("color_a", [0.5, 0.5, 0.5])),
            "uColB": tuple(p.get("color_b", [0.3, 0.3, 0.3])),
            "uPlanetSize": float(p.get("size", 1.0)),
            "uRings": 1.0 if p.get("rings", False) else 0.0,
            "uMoons": float(p.get("moons", 0)),
            "uLaunchS": self.launch_s, "uCruiseS": self.cruise_s, "uArriveS": self.arrive_s,
        }

    def overlays(self, t: float):
        p = self.planets[self.idx]
        now = time.monotonic()
        pt = now - self.phase_t0
        n = len(self.planets)
        if self.phase == PHASE_BROWSE:
            fade = min(1.0, pt / 0.8) if pt < 1.0 else 1.0
            kind = {"desert": "WÜSTENWELT", "ice": "EISWELT", "forest": "WALDWELT", "ocean": "OZEANWELT", "city": "STADTWELT",
                    "volcanic": "VULKANWELT", "gas": "GASRIESE", "swamp": "SUMPFWELT", "grass": "GRASWELT", "rock": "FELSWELT",
                    "crystal": "KRISTALLWELT"}.get(p.get("type", ""), "UNBEKANNT")
            extra = []
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
                (p.get("subtitle", ""), 0.026, 0.28, 0.485, (200, 185, 110), 0.85 * fade),
                ("<  WÄHLEN  >     KIPPSCHALTER + START  KURS SETZEN", 0.024, 0.5, 0.05, DIM, 0.7 + 0.3 * math.sin(t * 2.0)),
                ("[ ARMED  —  START DRÜCKEN ]" if self.armed else "[ GESICHERT ]",
                 0.026, 0.72, 0.13,
                 (255, 60, 60) if self.armed else (70, 70, 70), 0.9),
            ]
        if self.phase == PHASE_LAUNCH:
            return [(f"KURS: {p['name'].upper()}", 0.05, 0.5, 0.88, YEL, 0.9), ("HYPERANTRIEB LÄDT", 0.028, 0.5, 0.83, (255, 236, 120), 0.5 + 0.5 * math.sin(t * 8.0))]
        if self.phase == PHASE_CRUISE:
            eta = max(0.0, self.cruise_s - pt)
            return [(f"HYPERRAUM   ZIEL {p['name'].upper()}   ANKUNFT IN {eta:04.1f}", 0.028, 0.5, 0.05, DIM, 0.8)]
        return [(f"ANKUNFT   {p['name'].upper()}", 0.05, 0.5, 0.88, YEL, min(1.0, pt / 1.5))]
