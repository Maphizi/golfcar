"""Black Ice (Taste 7 im Thema CYBERPUNK, Gegenstück zum Systemfehler / zur Überdosis).

Ein Hack geht schief. Hacker-Kammer (assets/cyber/blackice_scene.png) in Wellen, die sich wiederholen:
  EINBRUCH (10 s)   "INTRUSION DETECTED", Scanlines, der Trace-Balken steigt
  TRACE (30 s)      Bildschirme kippen, Kanaltrennung, ICE-Daemonen (assets/cyber/blackice_daemons.png, 4x3 à 256)
                    lauern an den Rändern und greifen auf jeden Beat an, Datenrauschen
  BLACK ICE (20 s)  ein Daemon-Gesicht (assets/cyber/oracle_mask.png, Glitch-Reihe) füllt das Bild, Negativ-Blitze,
                    Bildsprünge, dein Gesicht als Fahndungsbild mit Barcode (assets/trip/face.png), Flüstertexte
  FLATLINE (8 s)    Schwarz, EKG-Linie, dann Reboot
Bass = Herzschlag/Tunnel, Beat = Glitch und Bildsprung, Höhen = Rauschen, Mitten verbiegen die Ränder, Drop = Schrei-Blitz.
Knüppel links/rechts = Gegenmaßnahme (Firewall, Proxy, Scrambler, Kill-Switch, Hard-Reset): kurz besser, dann schlimmer.
Oben = Neustart-Versuch (Bild rollt, Bootzeilen). Unten = Stecker ziehen (Schwarz mit Nachbildern, nochmal = rein).
Startknopf = Hilferuf an den Fixer (Cyberkatze aus assets/cyber/oracle_figures.png bringt kurz Ruhe).
Kippschalter AN = Jack out (kurz klar), AUS = Rückfall.
"""
from __future__ import annotations

import logging
import math
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("blackice")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
TRIP_ASSETS = ASSETS.parent / "trip"
PH_WARN, PH_POISON, PH_HORROR, PH_BLACKOUT = 0, 1, 2, 3
PHASE_LEN = {PH_WARN: 10.0, PH_POISON: 30.0, PH_HORROR: 20.0, PH_BLACKOUT: 8.0}
PHASE_NAMES = {PH_WARN: "EINBRUCH", PH_POISON: "TRACE", PH_HORROR: "BLACK ICE", PH_BLACKOUT: "FLATLINE"}
N_CRE = 5
N_CELLS = 12
WHISPERS = [
    "TRACE COMPLETE.", "WIR WISSEN, WO DU BIST.", "DEIN DECK GEHÖRT JETZT UNS.", "SEKTOR 7 IST GESPERRT. FÜR DICH.",
    "DAS ICE SCHMILZT NICHT. DU SCHON.", "JACK OUT. ODER BLEIB.", "DEIN PULS IST IN UNSERER DATENBANK.", "WER HAT DICH GESCHICKT?",
    "DIE FIREWALL WAR EINE EINLADUNG.", "NOCH EIN PAKET?", "ES IST NICHT VORBEI.", "DU WARST NIE ONLINE.",
]
ANTIDOTES = ["FIREWALL", "PROXY", "SCRAMBLER", "KILL-SWITCH", "HARD-RESET"]
CAT_CELLS = (8, 9, 10, 11)


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


class Creature:
    def __init__(self, rng: random.Random, now: float, horror: bool, cell: int | None = None):
        self.cell = rng.randrange(N_CELLS) if cell is None else cell
        side = rng.choice((-1.0, 1.0))
        self.x = 0.5 + side * rng.uniform(0.28, 0.46)
        self.y = rng.uniform(0.18, 0.72)
        self.t0 = now
        self.life = rng.uniform(6.0, 12.0) if not horror else rng.uniform(3.0, 6.0)
        self.size = rng.uniform(0.12, 0.22) * (1.4 if horror else 1.0)
        self.approach = rng.uniform(0.3, 0.8) * (2.0 if horror else 1.0)
        self.hue = rng.uniform(0.0, 6.28)
        self.lunge_t0 = -10.0
        self.mirror = rng.random() < 0.5
        self.seed = rng.random()

    def age(self, now: float) -> float:
        return now - self.t0

    def done(self, now: float) -> bool:
        return now - self.t0 > self.life


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "blackice_scene.png")
        self.creatures_tex = _load_rgba(ASSETS / "blackice_daemons.png")
        self.face = _load_rgba(TRIP_ASSETS / "face.png") if (TRIP_ASSETS / "face.png").exists() else None
        self.gods = _load_rgba(ASSETS / "oracle_mask.png")
        self.figs = _load_rgba(ASSETS / "oracle_figures.png")
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.phase = PH_WARN
        self.phase_t0 = self.last
        self.wave = 0
        self.poison = 0.0
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.cut = (0.0, 0.0)
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.relief = 0.0
        self.relief_label = ""
        self.relief_t0 = -10.0
        self.relapse_at: float | None = None
        self.vomit_t0 = -10.0
        self.eyes_closed = False
        self.eyes = 0.0
        self.help_t0 = -10.0
        self.shock = 0.0
        self.shock_on = False
        self.shock_t0 = -10.0
        self.creatures: list[Creature] = []
        self.next_spawn = self.last + 3.0
        self.whisper = ""
        self.whisper_t0 = -10.0
        self.next_whisper = 0.0
        self.god_cell = 16 + self.rng.randrange(8)
        self.flap_t = 0.0
        self.led_back_at: float | None = None
        self.demo_next = self.last + 5.0
        log.info("Black Ice: Szene %s, Daemonen %s, Gesicht %s, Maske %s, Katze %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.creatures_tex is not None else "fehlt", "ok" if self.face is not None else "fehlt",
                 "ok" if self.gods is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def antidote(self) -> None:
        now = time.monotonic()
        if now - self.relief_t0 < 1.5:
            return
        self.relief_t0 = now
        self.relief = 1.0
        self.relief_label = self.rng.choice(ANTIDOTES)
        self.relapse_at = now + 4.0
        log.info("Gegenmaßnahme: %s (hilft kurz)", self.relief_label)

    def vomit(self) -> None:
        now = time.monotonic()
        if now - self.vomit_t0 < 3.5:
            return
        self.vomit_t0 = now
        self.poison = max(0.0, self.poison - 0.15)
        log.info("Neustart-Versuch")

    def toggle_eyes(self) -> None:
        self.eyes_closed = not self.eyes_closed
        log.info("Stecker %s", "gezogen" if self.eyes_closed else "wieder drin")

    def call_help(self) -> None:
        now = time.monotonic()
        if now - self.help_t0 < 6.0:
            return
        self.help_t0 = now
        self._led_event("blackice_help", now + 5.0)
        log.info("Hilferuf: der Fixer schickt die Katze")

    def set_shock(self, on: bool) -> None:
        if on == self.shock_on:
            return
        self.shock_on = on
        self.shock_t0 = time.monotonic()
        if not on:
            self.poison = min(1.0, self.poison + 0.2)                      # Rückfall
        log.info("Jack out %s", "an" if on else "aus, Rückfall")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.creatures = [Creature(self.rng, now, True, cell=c) for c in self.rng.sample(range(N_CELLS), N_CRE)]
        for c in self.creatures:
            c.size *= 1.4
            c.lunge_t0 = now
        self.poison = min(1.0, self.poison + 0.1)
        self._led_event("blackice_drop", now + 2.0)
        log.info("Drop: Schrei-Blitz, alle Daemonen greifen an")

    def _set_phase(self, ph: int, now: float) -> None:
        self.phase = ph
        self.phase_t0 = now
        if ph == PH_WARN:
            self.wave += 1
            self.seed = self.rng.uniform(1.0, 100.0)
            self.creatures = []
            wled.apply_mode_async("blackice")
        elif ph == PH_HORROR:
            self.god_cell = 16 + self.rng.randrange(8)
            self.next_whisper = now + 1.0
            wled.apply_mode_async("blackice_horror")
        elif ph == PH_BLACKOUT:
            self.creatures = []
            wled.apply_mode_async("blackice_blackout")
        elif ph == PH_POISON:
            wled.apply_mode_async("blackice")
        log.info("Phase: %s (Welle %d)", PHASE_NAMES[ph], self.wave)

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            self.antidote()
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.vomit()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_eyes()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.call_help()
        elif ev.key == pygame.K_SPACE:
            self.set_shock(True)
        elif ev.key == pygame.K_BACKSPACE:
            self.set_shock(False)

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uCreatureTex": (self.creatures_tex if self.creatures_tex is not None else self.blank, 1),
                "uFaceTex": (self.face if self.face is not None else self.blank, 1),
                "uGodTex": (self.gods if self.gods is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uCreatureTex", "uFaceTex", "uGodTex", "uFigTex", "uSceneSize", "uCreatureSize", "uFaceSize",
                 "uGodSize", "uFigSize", "uFaceOK", "uGodOK", "uFigOK", "uSeed", "uPhase", "uPhaseT", "uPhaseLen", "uWave",
                 "uPoison", "uRelief", "uVomitT", "uEyes", "uHelpT", "uShock", "uBassS", "uMidS", "uHighS", "uEnergy",
                 "uLive", "uBeatPulse", "uBeatStep", "uFlash", "uCut", "uGodCell", "uOwl"]
        for i in range(N_CRE):
            names += [f"uCre{i}", f"uCreP{i}"]
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
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            self.flap_t += 1.0
            if self.phase == PH_HORROR or self.poison > 0.75:
                self.cut = (self.rng.uniform(-0.03, 0.03), self.rng.uniform(-0.02, 0.02))
            for c in self.creatures:                                      # Wesen springen auf den Beat näher
                if self.phase == PH_HORROR or self.rng.random() < 0.35:
                    c.lunge_t0 = now
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
        self.flap_t += dt * (1.5 + 4.0 * self.bass_s)
        # Drop
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 10.0:
            self.drop_armed = False
            self.last_drop = now
            self._drop(now)
        self.flash = max(0.0, self.flash - dt / 1.5)
        # Phasen in Wellen
        pt = now - self.phase_t0
        if pt >= PHASE_LEN[self.phase]:
            self._set_phase((self.phase + 1) % 4, now)
            pt = 0.0
        target = {PH_WARN: 0.35, PH_POISON: 0.75, PH_HORROR: 1.0, PH_BLACKOUT: 0.2}[self.phase]
        self.poison += (target - self.poison) * min(1.0, dt / 6.0)
        self.poison = min(1.0, self.poison + 0.02 * dt * self.energy)         # laute Musik vergiftet schneller
        # Gegengift: Erleichterung klingt ab, dann Rückfall
        self.relief = max(0.0, self.relief - dt / 4.0)
        if self.relapse_at is not None and now >= self.relapse_at:
            self.relapse_at = None
            self.poison = min(1.0, self.poison + 0.15)
            log.info("Rückfall nach %s", self.relief_label)
        self.eyes += ((1.0 if self.eyes_closed else 0.0) - self.eyes) * min(1.0, dt / 0.6)
        self.shock += ((1.0 if self.shock_on else 0.0) - self.shock) * min(1.0, dt / 1.0)
        # Wesen: lauern, rücken näher, verschwinden; in der Horrorphase mehr und größer
        self.creatures = [c for c in self.creatures if not c.done(now)]
        if self.phase in (PH_POISON, PH_HORROR) and now >= self.next_spawn and len(self.creatures) < N_CRE:
            self.creatures.append(Creature(self.rng, now, self.phase == PH_HORROR))
            self.next_spawn = now + self.rng.uniform(1.5, 4.0) * (0.5 if self.phase == PH_HORROR else 1.0)
        # Flüstern
        if self.phase == PH_HORROR and now >= self.next_whisper:
            self.whisper = self.rng.choice(WHISPERS)
            self.whisper_t0 = now
            self.next_whisper = now + self.rng.uniform(3.0, 5.5)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("blackice_horror" if self.phase == PH_HORROR else "blackice")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("antidote", "vomit", "eyes", "help", "shock", "drop"))
            if pick == "eyes" and self.eyes_closed:
                pick = "antidote"
            {"antidote": self.antidote, "vomit": self.vomit, "eyes": self.toggle_eyes, "help": self.call_help,
             "shock": lambda: self.set_shock(not self.shock_on), "drop": lambda: self._drop(now)}[pick]()
            if self.eyes_closed:
                self.demo_next = now + 3.0
            else:
                self.demo_next = now + 7.0
            if pick == "eyes" and not self.eyes_closed:
                pass
        if self.eyes_closed and self.demo and now - self.demo_next > -0.5 and self.rng.random() < 0.02:
            self.toggle_eyes()
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        flap = self.flap_t % 4.0
        out = {
            "uSceneSize": size(self.scene), "uCreatureSize": size(self.creatures_tex), "uFaceSize": size(self.face),
            "uGodSize": size(self.gods), "uFigSize": size(self.figs), "uFaceOK": 1.0 if self.face is not None else 0.0,
            "uGodOK": 1.0 if self.gods is not None else 0.0, "uFigOK": 1.0 if self.figs is not None else 0.0,
            "uSeed": self.seed, "uPhase": float(self.phase), "uPhaseT": pt, "uPhaseLen": PHASE_LEN[self.phase],
            "uWave": float(self.wave), "uPoison": self.poison, "uRelief": self.relief,
            "uVomitT": (now - self.vomit_t0) if now - self.vomit_t0 < 3.0 else -1.0, "uEyes": self.eyes,
            "uHelpT": (now - self.help_t0) if now - self.help_t0 < 5.0 else -1.0, "uShock": self.shock,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s,
            "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash, "uCut": self.cut,
            "uGodCell": float(self.god_cell),
            "uOwl": (float(CAT_CELLS[int(flap) % 4]), float(CAT_CELLS[(int(flap) + 1) % 4]), flap - int(flap), 0.0),
        }
        for i in range(N_CRE):
            if i < len(self.creatures):
                c = self.creatures[i]
                age = c.age(now)
                lunge = max(0.0, 1.0 - (now - c.lunge_t0) / 0.5)
                out[f"uCre{i}"] = (c.x, c.y, c.size * (1.0 + 0.5 * c.approach * min(1.0, age / c.life)), float(c.cell))
                out[f"uCreP{i}"] = (age, lunge, c.hue, (1.0 if c.mirror else 0.0) + 2.0 * c.seed + 10.0 * c.life)
            else:
                out[f"uCre{i}"] = (0.0, 0.0, 0.0, -1.0)
                out[f"uCreP{i}"] = (0.0, 0.0, 0.0, 0.0)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        pt = now - self.phase_t0
        out = []
        pulse = int(68 + 70 * self.poison + 30 * self.bass_s + (25 if self.phase == PH_HORROR else 0) - 30 * self.relief - 20 * self.shock)
        if self.phase == PH_BLACKOUT:
            pulse = int(40 + 20 * math.sin(t * 2.0))
        col = (120, 230, 110) if pulse < 100 else ((255, 200, 80) if pulse < 140 else (255, 60, 60))
        flick = 0.75 + 0.25 * math.sin(t * (6.0 + 10.0 * self.poison))
        trace = int(min(100.0, 100.0 * (self.poison * 0.7 + 0.3 * (self.phase >= PH_HORROR))))
        out.append((f"PULS  {pulse}    TRACE  {trace} %", 0.026, 0.16, 0.95, col, 0.9 * flick))
        out.append((f"WELLE {self.wave + 1}   {PHASE_NAMES[self.phase]}", 0.016, 0.88, 0.95, (180, 160, 200), 0.6))
        if self.phase == PH_WARN:
            a = (0.5 + 0.5 * math.sin(t * 7.0)) * min(1.0, pt / 1.0)
            out.append(("I N T R U S I O N   D E T E C T E D", 0.045, 0.5, 0.5, (255, 60, 60), 0.9 * a))
        elif self.phase == PH_HORROR and self.whisper and now - self.whisper_t0 < 2.8:
            k = now - self.whisper_t0
            a = min(1.0, k * 4.0) * min(1.0, (2.8 - k) * 2.0) * (0.6 + 0.4 * math.sin(t * 23.0))
            x = 0.5 + 0.15 * math.sin(self.whisper_t0 * 3.1)
            out.append((self.whisper, 0.03, x, 0.3 + 0.3 * abs(math.sin(self.whisper_t0 * 1.7)), (255, 80, 110), 0.85 * a))
        elif self.phase == PH_BLACKOUT:
            a = 0.3 + 0.3 * math.sin(t * 1.5)
            out.append(("F L A T L I N E", 0.05, 0.5, 0.62, (120, 40, 60), a))
            if pt > PHASE_LEN[PH_BLACKOUT] - 2.5:
                out.append(("REBOOT ... VERBINDUNG STEHT. NOCH EINMAL.", 0.03, 0.5, 0.42, (120, 220, 255), min(1.0, (pt - 5.5) / 1.0) * 0.8))
        if now - self.relief_t0 < 3.5:
            k = now - self.relief_t0
            txt = f"{self.relief_label} ... BESSER?" if k < 2.0 else f"{self.relief_label} ... SCHLIMMER."
            out.append((txt, 0.03, 0.5, 0.12, (150, 230, 220) if k < 2.0 else (255, 90, 90), min(1.0, (3.5 - k) * 2.0) * 0.9))
        if now - self.vomit_t0 < 2.5:
            out.append(("REBOOT ...", 0.035, 0.5, 0.2, (120, 255, 120), min(1.0, (2.5 - (now - self.vomit_t0)) / 0.8)))
        if now - self.help_t0 < 5.0:
            out.append(("DER FIXER SCHICKT DIE KATZE. KURZ.", 0.028, 0.5, 0.1, (200, 160, 255), 0.8 * min(1.0, (5.0 - (now - self.help_t0)) / 1.0)))
        if self.shock_on:
            out.append(("JACK OUT. KLAR. FÜR EINEN MOMENT.", 0.024, 0.5, 0.08, (180, 220, 255), 0.7))
        if self.eyes_closed:
            out.append(("STECKER GEZOGEN. DAS NETZ BLEIBT.", 0.024, 0.5, 0.5, (140, 90, 120), 0.5 + 0.3 * math.sin(t * 2.0)))
        return out
