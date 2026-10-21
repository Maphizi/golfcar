"""Waldtresen (Taste 2 im Thema THE POWER OF THE GREEN): psychedelische Wesen essen und auf die Reise gehen.

Phasen: 0 browse (Tresen aus assets/trip/bar.png, Wesen auf dem Teller, Steuerknüppel links/rechts blättert)
        -> 1 eat (Startknopf: das Wesen fliegt auf die Kamera zu, Biss, Augenlider schließen sich)
        -> 2 trip (Kaleidoskop aus Naturtexturen, Symbole schweben, Ereignisse alle 30-60 s; endet NUR per
           Kippschalter) -> 3 comedown (zurück an den Tresen) -> browse mit Bilanz.
Jedes Wesen hat ein Profil in config/trip.toml (Palette, Tempo, Spiegel, Verdrehung, Symbolsatz, Verzerrung).
Musik: Bass lässt alles atmen, Beats schalten den Puls, Drops wechseln Palette oder Spiegelzahl, Höhen funkeln.
Während der Reise: Knüppel links/rechts = Spiegel, oben/unten = Tempo.
"""
from __future__ import annotations

import logging
import math
import random
import time

import numpy as np
import pygame

from launcher import config as lcfg

log = logging.getLogger("trip")
ASSETS = lcfg.ROOT / "assets" / "trip"
PH_BROWSE, PH_EAT, PH_TRIP, PH_COMEDOWN = 0, 1, 2, 3
EAT_SECONDS, COMEDOWN_SECONDS = 2.6, 4.0
EVENT_EVERY = (20.0, 40.0)
GOD_MIN_GAP = 60.0                    # Waldgötter selten: frühestens nach 60 s, und nur wenn die Musik aufdreht
GOD_CHANCE_PER_S = 0.025              # ab dann je Sekunde bei lauter Musik (Energie > Schwelle), sonst gar nicht
VARIANT_EVERY = (25.0, 50.0)          # Kaleidoskop-Variante wechselt von selbst (und bei jedem zweiten Drop)
N_VARIANTS = 4
# Ereignisse: (Name, Dauer, HUD-Zeile); Index + 1 = uEvent
EVENTS = [
    ("FROSCHKONZERT", 14.0, "DIE FRÖSCHE SINGEN IM TAKT"),
    ("PILZREGEN", 14.0, "ES REGNET PILZE UND POLLEN"),
    ("DER WALD SCHAUT", 12.0, "AUGEN ÖFFNEN SICH IN DEN BLÜTEN"),
    ("SCHMETTERLINGSSCHWARM", 12.0, "FLÜGEL ÜBERALL"),
    ("POLLENSTURM", 10.0, "ALLES LEUCHTET VON INNEN"),
    ("LICHTHIRSCH", 12.0, "EIN GEWEIH AUS LICHT"),
    ("DEIN GESICHT", 10.0, "DU BIST AUCH HIER"),
    ("WURZELN", 12.0, "WURZELN WACHSEN DURCH DICH HINDURCH"),
    ("WALDGOTT", 11.0, ""),
]
GOD_NAMES = ["MOOSVATER", "DER GEWEIHTE", "PILZMUTTER", "WURZELFRAU", "EULENGEIST", "RINDENGESICHT"]
GOD_LINES = [
    "DU HAST DEN FARN NICHT GEGOSSEN.", "DEINE FAHRT IST EINE ILLUSION. DAS TAXAMETER NICHT.",
    "DER WALD HAT DICH SCHON VERGESSEN. ICH NOCH NICHT.", "ISS WENIGER PILZE. SAGT DER PILZ.",
    "DU BIST NUR EIN BLATT. EIN LAUTES.", "DIE SCHNECKE WAR VOR DIR HIER. SIE WARTET NOCH.",
    "DEIN HANDICAP IST DEM MOOS EGAL.", "ATME. DAS MACHT DER BAUM AUCH. SEIT 400 JAHREN.",
    "ICH SEHE DEINE WURZELN. SIE SIND KURZ.", "KEHR UM. ODER AUCH NICHT. DER WALD WÄCHST ÜBERALL.",
]
# Symbolzellen im Atlas assets/trip/symbols.png (8 x 5, Index = Reihe*8 + Spalte)
SYMBOL_SETS = {
    "eyes": [1, 2, 3, 4], "frogs": [26, 27, 29, 31], "butterflies": [6, 13, 28], "leaves": [11, 14, 16, 19, 24],
    "ferns": [7, 23, 33], "shells": [9, 12, 25, 34], "feathers": [0, 15, 17, 18], "mushrooms": [36, 35, 38],
    "orbs": [35, 38, 10], "mixed": [1, 6, 9, 14, 23, 26, 35, 0],
}
EVENT_SYMBOLS = {1: [26, 27, 29, 31], 2: [36, 35, 38, 22], 3: [1, 2, 3, 4], 4: [6, 13, 28, 32, 37], 5: [35, 38, 10], 6: [30], 7: [],
                 8: [11, 14, 16, 19], 9: [1, 2, 3, 4]}
EV_ROOTS, EV_GOD = 7, 8               # Indizes in EVENTS
RETURN_LINES = [
    "DER FUCHS HAT DEIN TAXI BEWACHT.", "DIE SCHNECKE HAT NICHTS GEMERKT.", "DU HAST MIT EINEM FARN GEREDET. ER FAND DICH NETT.",
    "DEIN TAXAMETER LIEF WEITER. NATÜRLICH.", "DIE PILZE SAGEN: BIS BALD.", "DU WARST KURZ EIN FROSCH. STEHT DIR.",
]


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


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.beings = lcfg._load("trip.toml").get("beings", []) or [{"cell": 0, "name": "FLIEGENPILZ", "origin": "real", "effect": ""}]
        self.idx = self.rng.randrange(len(self.beings))
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.bar = _load_rgba(ASSETS / "bar.png")
        self.beings_tex = _load_rgba(ASSETS / "beings.png")
        self.symbols = _load_rgba(ASSETS / "symbols.png")
        self.textures = [t for t in (_load_rgba(ASSETS / f"tex_{n}.png") for n in ("canopy", "frog", "amanita")) if t is not None]
        self.face = _load_rgba(ASSETS / "face.png") if (ASSETS / "face.png").exists() else None
        self.gods = _load_rgba(ASSETS / "gods.png") if (ASSETS / "gods.png").exists() else None
        self.roots = _load_rgba(ASSETS / "roots.png") if (ASSETS / "roots.png").exists() else None
        self.variant = 0
        self.variant_prev = 0
        self.variant_t0 = 0.0
        self.variant_next = 0.0
        self.wander_next = 0.0
        self.tex_shift = 0.0
        self.god_next = 0.0
        self.twist = 0.5
        self.warp = 0.6
        self.symbols_key = "mixed"
        self.last_tick = 0.0
        self.spin_dir = 1.0
        self.phase = PH_BROWSE
        self.phase_t0 = time.monotonic()
        self.slide = 0.0
        self.slide_t0 = 0.0
        self.last = self.phase_t0
        self.bass_s = 0.0
        self.mid_s = 0.0
        self.high_s = 0.0
        self.energy = 0.0
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        self.drop_armed = False
        self.quiet_since: float | None = None
        self.last_drop = 0.0
        self.trip_t = 0.0                 # Reisezeit (läuft mit dem Tempo)
        self.spin = 0.0
        self.mirrors = 8.0
        self.mirrors_target = 8.0
        self.tempo = 1.0
        self.palette = 0.0
        self.palette_target = 0.0
        self.intensity = 0.0
        self.event: dict | None = None
        self.next_event_at = 0.0
        self.trip_started = 0.0
        self.return_line = ""
        self.return_until = 0.0
        self.demo_next = time.monotonic() + 3.0
        log.info("Waldtresen: %d Wesen, Tresen %s, Texturen %d, Gesicht %s, Waldgötter %s, Wurzeln %s", len(self.beings),
                 "ok" if self.bar is not None else "fehlt", len(self.textures), "ok" if self.face is not None else "fehlt",
                 "ok" if self.gods is not None else "fehlt (assets/trip/gods.png)", "ok" if self.roots is not None else "prozedural")

    # -- Eingabe -----------------------------------------------------------
    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_SPACE, pygame.K_BACKSPACE):
            if self.phase in (PH_TRIP, PH_EAT):
                self._set_phase(PH_COMEDOWN)
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.phase == PH_BROWSE:
                self._set_phase(PH_EAT)
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            if self.phase == PH_BROWSE:
                self.select(-1)
            elif self.phase == PH_TRIP:
                self.mirrors_target = max(4.0, self.mirrors_target - 2.0)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            if self.phase == PH_BROWSE:
                self.select(+1)
            elif self.phase == PH_TRIP:
                self.mirrors_target = min(16.0, self.mirrors_target + 2.0)
        elif ev.key in (pygame.K_UP, pygame.K_w) and self.phase == PH_TRIP:
            self.tempo = min(2.0, self.tempo * 1.25)
        elif ev.key in (pygame.K_DOWN, pygame.K_s) and self.phase == PH_TRIP:
            self.tempo = max(0.3, self.tempo / 1.25)

    def select(self, d: int) -> None:
        self.idx = (self.idx + d) % len(self.beings)
        self.slide = float(d)
        self.slide_t0 = time.monotonic()

    def _set_phase(self, ph: int) -> None:
        now = time.monotonic()
        if ph == PH_TRIP:
            # Ein Programm für alle Wesen, jede Reise anders: Profil wird gewürfelt (trip.toml-Profile nur noch Namen/Bild)
            self.mirrors = self.mirrors_target = float(self.rng.choice((4, 5, 6, 8, 8, 10, 12)))
            self.tempo = self.rng.uniform(0.55, 0.95)
            self.palette = self.palette_target = float(self.rng.randrange(6))
            self.twist = self.rng.uniform(0.2, 0.9)
            self.warp = self.rng.uniform(0.3, 0.9)
            self.symbols_key = self.rng.choice(list(SYMBOL_SETS))
            self.trip_t = 0.0
            self.intensity = 0.0
            self.event = None
            self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.3 if self.demo else 0.6)
            self.god_next = now + GOD_MIN_GAP * (0.25 if self.demo else 1.0)
            self.variant = self.rng.randrange(N_VARIANTS)
            self.variant_prev = self.variant
            self.variant_next = now + self.rng.uniform(*VARIANT_EVERY)
            self.wander_next = now + self.rng.uniform(12.0, 22.0)
            self.spin_dir = self.rng.choice((-1.0, 1.0))
            self.trip_started = now
            log.info("Reise beginnt: %s (Spiegel %d, Tempo %.2f, Palette %d, Symbole %s)", self.beings[self.idx].get("name"), int(self.mirrors), self.tempo, int(self.palette), self.symbols_key)
        elif ph == PH_COMEDOWN and self.phase == PH_TRIP:
            secs = int(now - self.trip_started)
            self.return_line = f"DU WARST {secs // 60} MIN {secs % 60:02d} S WEG.  " + self.rng.choice(RETURN_LINES)
            self.return_until = now + COMEDOWN_SECONDS + 10.0
            log.info("Reise endet nach %d s", secs)
        self.phase = ph
        self.phase_t0 = now

    # -- Zustand -----------------------------------------------------------
    def _advance(self, f) -> None:
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
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.3)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.15)
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = min(1.0, self.beat_pulse + 0.5 + 0.5 * beat)
            if self.phase == PH_TRIP:
                self.spin += 0.035 * self.spin_dir * (0.5 + beat)         # Drehstoß auf jeden Beat
                self.trip_t += 0.07 * beat
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.6)
        # Drop: nach leiser Stelle ein Beat -> Palette oder Spiegel wechseln
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 12.0 and self.phase == PH_TRIP:
            self.drop_armed = False
            self.last_drop = now
            roll = self.rng.random()
            if roll < 0.35:
                self.palette_target = float((int(self.palette_target) + self.rng.randrange(1, 6)) % 6)
            elif roll < 0.65:
                self.mirrors_target = float(self.rng.choice((4, 6, 8, 10, 12, 16)))
            else:
                self._next_variant(now)
            self.tex_shift = self.rng.random() * 10.0
            self.spin_dir = -self.spin_dir
            log.info("Drop: Palette %d, Spiegel %d, Variante %d", int(self.palette_target), int(self.mirrors_target), self.variant)
        pt = now - self.phase_t0
        if self.phase == PH_EAT and pt >= EAT_SECONDS:
            self._set_phase(PH_TRIP)
        elif self.phase == PH_COMEDOWN and pt >= COMEDOWN_SECONDS:
            self._set_phase(PH_BROWSE)
        if self.phase == PH_TRIP:
            self.intensity = min(1.0, self.intensity + dt / (16.0 if not self.demo else 4.0))
            self.trip_t += dt * self.tempo * (0.7 + 0.9 * self.energy + 0.6 * self.bass_s)
            self.spin += dt * self.tempo * 0.1 * (1.0 + 2.0 * self.bass_s) * self.spin_dir
            self.mirrors += (self.mirrors_target - self.mirrors) * min(1.0, dt / 2.0)
            self.palette += (self.palette_target - self.palette) * min(1.0, dt / 3.0)
            if now >= self.variant_next:
                self._next_variant(now)
            if now >= self.wander_next:                               # zufällige Wanderung: Spiegel, Palette, Texturen
                self.wander_next = now + self.rng.uniform(15.0, 30.0)
                pick = self.rng.random()
                if pick < 0.3:
                    self.mirrors_target = float(self.rng.choice((4, 5, 6, 8, 10, 12, 16)))
                elif pick < 0.55:
                    self.palette_target = float(self.rng.randrange(6))
                elif pick < 0.7:
                    self.tex_shift = self.rng.random() * 10.0
                elif pick < 0.85:
                    self.twist = self.rng.uniform(0.2, 0.9)
                    self.warp = self.rng.uniform(0.3, 0.9)
                else:
                    self.symbols_key = self.rng.choice(list(SYMBOL_SETS))
                log.info("Wanderung: Spiegel %d, Palette %d", int(self.mirrors_target), int(self.palette_target))
            self._advance_event(now)
        elif self.phase == PH_COMEDOWN:
            self.intensity = max(0.0, 1.0 - pt / COMEDOWN_SECONDS)
        if self.demo and now >= self.demo_next:
            if self.phase == PH_BROWSE:
                if self.rng.random() < 0.5:
                    self.select(1)
                    self.demo_next = now + 1.5
                else:
                    self._set_phase(PH_EAT)
                    self.demo_next = now + 40.0
            elif self.phase == PH_TRIP:
                self._set_phase(PH_COMEDOWN)
                self.demo_next = now + 8.0

    def _next_variant(self, now: float) -> None:
        self.variant_prev = self.variant
        self.variant = (self.variant + self.rng.randrange(1, N_VARIANTS)) % N_VARIANTS
        self.variant_t0 = now
        self.variant_next = now + self.rng.uniform(*VARIANT_EVERY)
        log.info("Kaleidoskop-Variante %d", self.variant)

    def _start_event(self, kind: int, now: float) -> None:
        self.event = {"kind": kind, "t0": now, "len": EVENTS[kind][1], "seed": self.rng.random(), "line": "", "name": EVENTS[kind][0]}
        if kind == EV_GOD:
            g = self.rng.randrange(6)
            self.event["seed"] = (g + 0.5) / 6.0
            self.event["name"] = f"WALDGOTT  {GOD_NAMES[g]}"
            self.event["line"] = self.rng.choice(GOD_LINES)
        log.info("Ereignis: %s %s", self.event["name"], self.event["line"])

    def _advance_event(self, now: float) -> None:
        ev = self.event
        # Waldgott: selten, und nur wenn die Musik aufdreht (hohe Energie); verdrängt ein laufendes Ereignis
        loud = self.energy > 0.45 or self.demo
        if self.gods is not None and now >= self.god_next and loud and self.intensity > 0.5 and (ev is None or ev["kind"] != EV_GOD):
            dt_tick = min(1.0, now - self.last_tick) if self.last_tick else 0.0
            if self.rng.random() < GOD_CHANCE_PER_S * (4.0 if self.demo else 1.0) * dt_tick * (0.5 + self.energy):
                self._start_event(EV_GOD, now)
                self.god_next = now + GOD_MIN_GAP * (0.25 if self.demo else 1.0)
                return
        self.last_tick = now
        if ev is None:
            if now >= self.next_event_at and self.intensity > 0.4:
                choices = [i for i in range(len(EVENTS)) if i != EV_GOD and (i != 6 or self.face is not None)]
                choices += [EV_ROOTS]                                     # Wurzeln etwas häufiger
                self._start_event(self.rng.choice(choices), now)
            return
        if now - ev["t0"] >= ev["len"]:
            self.event = None
            self.next_event_at = now + self.rng.uniform(*EVENT_EVERY) * (0.3 if self.demo else 1.0)

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        out = {
            "uBarTex": (self.bar if self.bar is not None else self.blank, 1),
            "uBeingsTex": (self.beings_tex if self.beings_tex is not None else self.blank, 1),
            "uSymbolTex": (self.symbols if self.symbols is not None else self.blank, 1),
            "uFaceTex": (self.face if self.face is not None else self.blank, 1),
            "uGodTex": (self.gods if self.gods is not None else self.blank, 1),
            "uRootTex": (self.roots if self.roots is not None else self.blank, 1),
        }
        for i in range(3):
            out[f"uTex{i}"] = (self.textures[i % max(1, len(self.textures))] if self.textures else self.blank, 1)
        return out

    def uniform_names(self):
        return ("uBarTex", "uBeingsTex", "uSymbolTex", "uFaceTex", "uTex0", "uTex1", "uTex2", "uBarSize", "uBeingsSize",
                "uSymbolSize", "uFaceSize", "uTexSize", "uNumTex", "uPhase", "uPhaseT", "uSlide", "uCell", "uProfile",
                "uProfile2", "uSymA", "uSymB", "uTripT", "uSpin", "uMirrors", "uPalette", "uIntensity", "uBassS", "uMidS",
                "uHighS", "uEnergy", "uPulse", "uEvent", "uEventT", "uEventLen", "uEventSeed", "uEvSym", "uFaceOK",
                "uGodTex", "uRootTex", "uGodSize", "uRootSize", "uGodOK", "uRootOK", "uVariant")

    def uniforms(self, t: float, f) -> dict:
        self._advance(f)
        now = time.monotonic()
        b = self.beings[self.idx]
        slide = self.slide * max(0.0, 1.0 - (now - self.slide_t0) / 0.5)
        syms = SYMBOL_SETS.get(self.symbols_key, SYMBOL_SETS["mixed"])
        syms = (syms * 3)[:8]
        ev = self.event
        evs = (EVENT_SYMBOLS.get(ev["kind"] + 1, []) * 4)[:4] if ev else [0, 0, 0, 0]
        evs = (evs + [0, 0, 0, 0])[:4]
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        return {
            "uBarSize": size(self.bar), "uBeingsSize": size(self.beings_tex), "uSymbolSize": size(self.symbols),
            "uFaceSize": size(self.face), "uTexSize": size(self.textures[0]) if self.textures else (1.0, 1.0),
            "uNumTex": float(len(self.textures)),
            "uPhase": float(self.phase), "uPhaseT": now - self.phase_t0, "uSlide": slide,
            "uCell": float(b.get("cell", 0)),
            "uProfile": (self.twist, self.warp, self.tempo, float(self.idx)),
            "uProfile2": (EAT_SECONDS, COMEDOWN_SECONDS, 0.0, 0.0),
            "uSymA": tuple(float(v) for v in syms[:4]), "uSymB": tuple(float(v) for v in syms[4:8]),
            "uTripT": self.trip_t % 1000.0, "uSpin": self.spin % 6.2832, "uMirrors": self.mirrors, "uPalette": self.palette,
            "uIntensity": self.intensity, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uPulse": self.beat_pulse,
            "uEvent": float(ev["kind"] + 1) if ev else 0.0, "uEventT": (now - ev["t0"]) if ev else 0.0,
            "uEventLen": ev["len"] if ev else 1.0, "uEventSeed": ev["seed"] if ev else 0.0,
            "uEvSym": tuple(float(v) for v in evs), "uFaceOK": 1.0 if self.face is not None else 0.0,
            "uGodSize": size(self.gods), "uRootSize": size(self.roots), "uGodOK": 1.0 if self.gods is not None else 0.0,
            "uRootOK": 1.0 if self.roots is not None else 0.0,
            "uVariant": (float(self.variant), float(self.variant_prev), min(1.0, (now - self.variant_t0) / 3.0), self.tex_shift),
        }

    def overlays(self, t: float):
        now = time.monotonic()
        b = self.beings[self.idx]
        pt = now - self.phase_t0
        GREEN, LIGHT, DIM = (120, 230, 110), (235, 245, 220), (120, 150, 110)
        out = []
        if self.phase == PH_BROWSE:
            fade = min(1.0, pt / 0.8)
            origin = "ECHT" if b.get("origin") == "real" else "ERDACHT"
            out += [
                (f"WALDTRESEN   {self.idx + 1:02d} / {len(self.beings):02d}", 0.02, 0.17, 0.80, DIM, 0.8),
                (str(b.get("name", "")).upper(), 0.05, 0.17, 0.72, GREEN, 0.95 * fade),
                (origin, 0.018, 0.17, 0.665, LIGHT, 0.85 * fade),
                (f"WIRKUNG: {str(b.get('effect', '')).upper()}", 0.016, 0.17, 0.63, LIGHT, 0.85 * fade),
                ("<  WÄHLEN  >      START  =  ESSEN", 0.022, 0.5, 0.06, DIM, 0.7 + 0.3 * math.sin(t * 2.0)),
            ]
            if now < self.return_until and self.return_line:
                out.append((self.return_line, 0.02, 0.5, 0.12, GREEN, min(1.0, (self.return_until - now) / 2.0)))
        elif self.phase == PH_EAT:
            out.append((f"{str(b.get('name', '')).upper()}  WIRD GEGESSEN", 0.03, 0.5, 0.88, GREEN, max(0.0, 1.0 - pt / 1.5)))
        elif self.phase == PH_TRIP:
            secs = int(now - self.trip_started)
            out.append((f"REISE   {str(b.get('name', '')).upper()}   {secs // 60}:{secs % 60:02d}   KIPPSCHALTER = ZURÜCK", 0.02, 0.5, 0.05, DIM, 0.55))
            out.append(("KNÜPPEL  LINKS/RECHTS SPIEGEL   OBEN/UNTEN TEMPO", 0.015, 0.5, 0.025, DIM, 0.35))
            if self.event:
                name, length, line = EVENTS[self.event["kind"]]
                name = self.event.get("name") or name
                line = self.event.get("line") or line
                k = (now - self.event["t0"]) / length
                a = min(1.0, k * 6.0) * min(1.0, (1.0 - k) * 6.0)
                out.append((name, 0.03, 0.5, 0.9, GREEN, 0.9 * a))
                out.append((line, 0.02, 0.5, 0.86, LIGHT, 0.8 * a))
        else:
            out.append(("ZURÜCK AM TRESEN", 0.04, 0.5, 0.5, LIGHT, min(1.0, pt / 1.0) * min(1.0, (COMEDOWN_SECONDS - pt) / 1.0)))
        return out
