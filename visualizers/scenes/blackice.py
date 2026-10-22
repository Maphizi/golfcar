"""Black Ice (Taste 7 im Thema CYBERPUNK, Gegenstück zum Systemfehler / zur Überdosis).

Ein Hack geht schief. Hacker-Kammer (assets/cyber/blackice_scene.png, alle Bildschirme reines Schwarz) in Wellen:
  EINBRUCH          "INTRUSION DETECTED", Scanlines, Warnungen und Countdowns auf den Schirmen, der Trace-Balken steigt
  TRACE             Bildschirme kippen, Kanaltrennung, gemischte Inhalte (Glyphenregen, Karten, Radar, Augen, Daemonen)
  BLACK ICE         digitale Augen auf mehreren Schirmen schauen zum Betrachter, die Glitch-Maske (assets/cyber/oracle_mask.png)
                    auf dem größten Schirm, Fahndungsbild mit Barcode, Negativ-Blitze, Flüstertexte
  FLATLINE          Schwarz, EKG über alle Schirme, dann Reboot
Phasenlängen werden je Welle zufällig gestreckt (0.7 bis 1.5).

Die Bildschirme werden beim Start im Szenenbild gefunden (zusammenhängende reinschwarze Flächen, `_find_screens`), bis zu
N_SCREENS Rechtecke `uScr0..11` (x0, y0, x1, y1 in Anteilen, y von unten) und als Alpha-Maske im Szenenbild (0 = Schirm).
Jeder Schirm hat einen Inhalt `uScrC0..11` = (Typ, Variante/Atlaszelle, Startzeit, Seed):
  0 Atlaskachel (assets/cyber/blackice_screens.png, 8x4, Zelle = Spalte + 8*Reihe: Reihe 0 Auge geradeaus/links/rechts/halb/
  zu/rot/Glitch/zerfällt, Reihe 1 Schädel, Warndreieck, Radar, Fadenkreuz, Fingerabdruck, Schloss, Virus, Drahtgesicht, Reihe 2
  Wellenform, Herzlinie, Weltkarte, Barcode, Countdown 88, Glyphenregen, Platine, Spirale, Reihe 3 Rauschen, Testbild, Binär,
  DNA, Gehirnscan, Stadtkarte, Chromhand, rotes Auge), 1 digitales Auge (prozedural), 2 Countdown, 3 Warnung, 4 Rauschen,
  5 Fadenkreuz, 6 Barcode, 7 Fahndungsfoto (uFaceTex), 8 EKG, 9 aus, 10 Daemon (blackice_daemons.png 4x3 à 256),
  11 Glitch-Maske (uGodTex), 12 Fixer-Katze (uFigTex), 13 Bootzeilen, 14 Standby (Cursor blinkt), 15 Atlas-Auge (Reihe 0:
  blinzelt 0 -> 3 -> 4 -> 3 -> 0, schaut 1/2, Black ICE 5/6/7).
Auf jeden Beat wechseln 1 bis 3 Schirme ihren Inhalt (mehr bei hoher Energie, beim Drop alle), mit 80 ms Schwarz dazwischen.
Atlaskacheln laufen mit dem Bass (Glyphenregen, Radar, Herzlinie), Spektren zeigen die echten Bänder (uBands0/1).
Augen (uEyeLook, uEyeBlink) schauen umher und blinzeln, bei Black ICE rot, weit und zum Betrachter. Stille = Standby.
Alle 15 bis 30 s ein Ereignis von selbst: Augen-Salve, Countdown überall, Rauschsturm, kurzer Reboot.
Knüppel links/rechts = Gegenmaßnahme (Schirme kurz grün "OK" = Netzknoten), dann Rückfall. Oben = Neustart (alle Schirme
rollen Bootzeilen). Unten = Stecker ziehen (alle Schirme aus, nur Augen öffnen sich langsam im Dunkeln; nochmal = rein).
Startknopf = Hilferuf an den Fixer (Cyberkatze auf allen Schirmen). Kippschalter AN = Jack out (kurz klar), AUS = Rückfall.
"""
from __future__ import annotations

import logging
import math
import os
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import images

from launcher import wled

log = logging.getLogger("blackice")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
TRIP_ASSETS = ASSETS.parent / "trip"
PH_WARN, PH_POISON, PH_HORROR, PH_BLACKOUT = 0, 1, 2, 3
PHASE_LEN = {PH_WARN: 10.0, PH_POISON: 30.0, PH_HORROR: 20.0, PH_BLACKOUT: 8.0}
PHASE_NAMES = {PH_WARN: "EINBRUCH", PH_POISON: "TRACE", PH_HORROR: "BLACK ICE", PH_BLACKOUT: "FLATLINE"}
PHASE_STRETCH = (0.7, 1.5)
N_SCREENS = 12
N_CELLS = 12                                   # Daemonen-Zellen
ATLAS_CELLS = 32                               # Bildschirm-Atlas 8x4 (Zelle = Spalte + 8*Reihe)
# Inhaltstypen
C_ATLAS, C_EYE, C_COUNT, C_WARN, C_NOISE, C_CROSS, C_BARCODE, C_FACE, C_EKG, C_OFF = range(10)
C_DAEMON, C_GOD, C_CAT, C_BOOT, C_STANDBY, C_ATLAS_EYE = 10, 11, 12, 13, 14, 15
A_SKULL, A_WARN, A_RADAR, A_CROSS, A_FINGER, A_LOCK, A_VIRUS, A_WIRE = range(8, 16)
A_WAVE, A_HEART, A_WORLD, A_BARCODE, A_COUNT, A_RAIN, A_CIRCUIT, A_SPIRAL = range(16, 24)
A_NOISE, A_TEST, A_BINARY, A_DNA, A_BRAIN, A_CITY, A_HAND, A_REDEYE = range(24, 32)
ATLAS_WARN = (A_WARN, A_RADAR, A_CROSS, A_LOCK, A_BARCODE, A_NOISE, A_TEST, A_BINARY, A_CIRCUIT, A_FINGER, A_WORLD, A_CITY)
ATLAS_TRACE = tuple(c for c in range(8, 32) if c != A_COUNT)
ATLAS_HORROR = (A_SKULL, A_VIRUS, A_WIRE, A_SPIRAL, A_REDEYE, A_BRAIN, A_HAND, A_WARN, A_NOISE)
ATLAS_OK = A_LOCK                              # Schloss = "OK"-Muster der Gegenmaßnahme
WHISPERS = [
    "TRACE COMPLETE.", "WIR WISSEN, WO DU BIST.", "DEIN DECK GEHÖRT JETZT UNS.", "SEKTOR 7 IST GESPERRT. FÜR DICH.",
    "DAS ICE SCHMILZT NICHT. DU SCHON.", "JACK OUT. ODER BLEIB.", "DEIN PULS IST IN UNSERER DATENBANK.", "WER HAT DICH GESCHICKT?",
    "DIE FIREWALL WAR EINE EINLADUNG.", "NOCH EIN PAKET?", "ES IST NICHT VORBEI.", "DU WARST NIE ONLINE.",
]
ANTIDOTES = ["FIREWALL", "PROXY", "SCRAMBLER", "KILL-SWITCH", "HARD-RESET"]
CAT_CELLS = (8, 9, 10, 11)
EVENTS = ("eyes", "countdown", "noise", "reboot")
EVENT_NAMES = {"eyes": "SIE SEHEN DICH.", "countdown": "COUNTDOWN LÄUFT.", "noise": "SIGNAL VERLOREN.", "reboot": "REBOOT ..."}
EVENT_LEN = {"eyes": 6.0, "countdown": 7.0, "noise": 2.5, "reboot": 3.0}


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


def _find_screens(img: np.ndarray, min_area: float = 0.003, thr: int = 3, erode: int = 8):
    """Bildschirme im Szenenbild: zusammenhängende reinschwarze Flächen mit Mindestgröße und rechteckiger Füllung.

    `img` ist das geladene RGBA-Bild (Zeile 0 = unten). Dünne schwarze Verbindungen (Kabel, Bezel-Schatten) werden mit
    einer Erosion um `erode` Pixel getrennt, dann je Kern die schwarzen Pixel im Umfeld wieder dazugenommen.
    Liefert (Rechtecke, Alpha): Rechtecke (x0, y0, x1, y1) in Anteilen, y von unten, nach Fläche absteigend; Alpha
    255 = Raum, 0 = Schirm (weicher Rand über 3 px)."""
    h, w = img.shape[:2]
    luma = img[..., :3].max(axis=2)
    black = luma < thr
    rects: list[tuple[float, float, float, float]] = []
    mask = np.zeros((h, w), dtype=bool)
    try:
        from scipy import ndimage
        core = ndimage.binary_erosion(black, structure=np.ones((erode, erode)))
        lab, n = ndimage.label(core)
        if n > 0:
            sizes = ndimage.sum(core, lab, index=np.arange(1, n + 1))
            objs = ndimage.find_objects(lab)
            found = []
            for k in np.flatnonzero(sizes >= min_area * h * w):
                sl = objs[k]
                y0, y1 = max(0, sl[0].start - erode), min(h, sl[0].stop + erode)
                x0, x1 = max(0, sl[1].start - erode), min(w, sl[1].stop + erode)
                sub = black[y0:y1, x0:x1]
                slab, sn = ndimage.label(sub)
                if sn == 0:
                    continue
                ssz = ndimage.sum(sub, slab, index=np.arange(1, sn + 1))
                best = int(np.argmax(ssz)) + 1
                part = slab == best
                ys, xs = np.nonzero(part)
                by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
                fill = ssz[best - 1] / float((by1 - by0) * (bx1 - bx0))
                if fill < 0.8:                                                # Schirme sind (fast) volle Rechtecke
                    continue
                area = ssz[best - 1] / float(h * w)
                found.append((area, (x0 + bx0) / w, (y0 + by0) / h, (x0 + bx1) / w, (y0 + by1) / h))
                mask[y0:y1, x0:x1] |= part
            found.sort(reverse=True)
            rects = [r[1:] for r in found[:N_SCREENS]]
        alpha = ndimage.uniform_filter((~mask).astype(np.float32), size=3)
    except Exception as exc:
        log.info("Bildschirm-Suche ohne scipy (%s)", exc)
        alpha = (~mask).astype(np.float32)
    return rects, np.clip(alpha * 255.0, 0, 255).astype(np.uint8)


class Screen:
    """Inhalt eines Bildschirms: Typ, Variante (Atlaszelle / Daemon-Zelle / Startzahl), Startzeit, Seed."""

    def __init__(self):
        self.kind = C_STANDBY
        self.var = 0.0
        self.t0 = -10.0
        self.seed = 0.0
        self.locked = False                   # z. B. Glitch-Maske auf dem größten Schirm bei Black ICE


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "blackice_scene.png")
        self.screens_tex = _load_rgba(ASSETS / "blackice_screens.png")
        self.creatures_tex = _load_rgba(ASSETS / "blackice_daemons.png")
        self.face = _load_rgba(TRIP_ASSETS / "face.png") if (TRIP_ASSETS / "face.png").exists() else None
        self.gods = _load_rgba(ASSETS / "oracle_mask.png")
        self.figs = _load_rgba(ASSETS / "oracle_figures.png")
        self.rects: list[tuple[float, float, float, float]] = []
        if self.scene is not None:
            self.rects, self.scene[..., 3] = _find_screens(
                self.scene, float(scene_cfg.get("screen_min_area", 0.003)), int(scene_cfg.get("screen_black", 3)))
            for i, r in enumerate(self.rects):
                log.info("Bildschirm %d: x %.3f-%.3f, y %.3f-%.3f (von unten)", i, r[0], r[2], r[1], r[3])
        self.screens = [Screen() for _ in range(N_SCREENS)]
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.t = 0.0
        self.phase = PH_WARN
        self.phase_t0 = self.last
        self.phase_len = PHASE_LEN[PH_WARN]
        self.wave = 0
        self.poison = 0.0
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.bands = [0.0] * 8
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
        self.eyes_t0 = -10.0
        self.help_t0 = -10.0
        self.shock = 0.0
        self.shock_on = False
        self.shock_t0 = -10.0
        self.whisper = ""
        self.whisper_t0 = -10.0
        self.next_whisper = 0.0
        self.god_cell = 16 + self.rng.randrange(8)
        self.flap_t = 0.0
        self.led_back_at: float | None = None
        # Augen
        self.eye_look = [0.0, 0.0]
        self.eye_target = [0.0, 0.0]
        self.next_look = 0.0
        self.eye_blink = 0.0
        self.blink_t0 = -10.0
        self.next_blink = self.last + 2.0
        # Schirmwechsel und Ereignisse
        self.next_idle_switch = self.last + 2.0
        self.event = ""
        self.event_t0 = -10.0
        self.event_len = 0.0
        self.next_event = self.last + self.rng.uniform(15.0, 30.0)
        self.demo_next = self.last + 5.0
        self._reshuffle(all_screens=True)
        if os.environ.get("KITT_BLACKICE_PHASE", "").isdigit():          # Test: Startphase vorgeben
            self._set_phase(int(os.environ["KITT_BLACKICE_PHASE"]) % 4, self.last)
            self.wave = 0
        log.info("Black Ice: Szene %s (%d Schirme), Atlas %s, Daemonen %s, Gesicht %s, Maske %s, Katze %s",
                 "ok" if self.scene is not None else "fehlt", len(self.rects), "ok" if self.screens_tex is not None else "fehlt",
                 "ok" if self.creatures_tex is not None else "fehlt", "ok" if self.face is not None else "fehlt",
                 "ok" if self.gods is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    # -- Bildschirme -------------------------------------------------------
    def _pick_content(self, i: int) -> tuple[int, float]:
        """Zufälliger Inhalt je Phase: (Typ, Variante)."""
        r = self.rng
        if self.phase == PH_WARN:
            kinds = [(C_ATLAS, 4), (C_WARN, 2), (C_COUNT, 2), (C_CROSS, 1), (C_BARCODE, 1), (C_NOISE, 1), (C_ATLAS_EYE, 1),
                     (C_EYE, 1), (C_EKG, 1)]
            atlas = ATLAS_WARN
        elif self.phase == PH_POISON:
            kinds = [(C_ATLAS, 7), (C_ATLAS_EYE, 2), (C_EYE, 1), (C_COUNT, 1), (C_WARN, 1), (C_NOISE, 1), (C_CROSS, 1),
                     (C_BARCODE, 1), (C_FACE, 1), (C_EKG, 1), (C_DAEMON, 2), (C_OFF, 1)]
            atlas = ATLAS_TRACE
        elif self.phase == PH_HORROR:
            kinds = [(C_ATLAS, 2), (C_ATLAS_EYE, 4), (C_EYE, 3), (C_WARN, 1), (C_NOISE, 1), (C_FACE, 2), (C_DAEMON, 2),
                     (C_COUNT, 1), (C_EKG, 1)]
            atlas = ATLAS_HORROR
        else:
            kinds = [(C_EKG, 3), (C_OFF, 2), (C_NOISE, 1)]
            atlas = ATLAS_WARN
        kind = r.choices([k for k, _ in kinds], weights=[w for _, w in kinds])[0]
        if kind == C_ATLAS:
            var = float(r.choice(atlas))
        elif kind == C_DAEMON:
            var = float(r.randrange(N_CELLS))
        elif kind == C_COUNT:
            var = float(r.choice((10, 30, 60, 99)))
        elif kind in (C_EYE, C_ATLAS_EYE):
            var = r.random()                                              # Irisfarbe
        else:
            var = float(r.randrange(4))
        if kind == C_FACE and self.face is None:
            kind, var = C_CROSS, 0.0
        return kind, var

    def _switch(self, i: int, kind: int | None = None, var: float | None = None) -> None:
        s = self.screens[i]
        if kind is None:
            kind, var = self._pick_content(i)
        s.kind, s.var = kind, (var if var is not None else 0.0)
        s.t0 = self.t
        s.seed = self.rng.random()

    def _reshuffle(self, all_screens: bool = False, count: int = 1) -> None:
        idx = [i for i in range(len(self.rects) or 1) if not self.screens[i].locked]
        if not idx:
            return
        if not all_screens:
            idx = self.rng.sample(idx, min(count, len(idx)))
        for i in idx:
            self._switch(i)

    def _start_event(self, name: str) -> None:
        self.event = name
        self.event_t0 = self.t
        self.event_len = EVENT_LEN[name]
        n = len(self.rects) or 1
        if name == "eyes":
            for i in range(n):
                self._switch(i, self.rng.choice((C_EYE, C_ATLAS_EYE, C_ATLAS_EYE)), self.rng.random())
        elif name == "countdown":
            start = float(self.rng.choice((10, 20, 30)))
            for i in range(n):
                self._switch(i, C_COUNT, start)
        elif name == "noise":
            for i in range(n):
                self._switch(i, C_NOISE, float(self.rng.randrange(4)))
        elif name == "reboot":
            self.vomit()
        log.info("Ereignis: %s", name)

    # -- Aktionen ----------------------------------------------------------
    def antidote(self) -> None:
        now = time.monotonic()
        if now - self.relief_t0 < 1.5:
            return
        self.relief_t0 = now
        self.relief = 1.0
        self.relief_label = self.rng.choice(ANTIDOTES)
        self.relapse_at = now + 4.0
        for i in range(len(self.rects) or 1):                                # alle Schirme kurz grün "OK"
            if not self.screens[i].locked:
                self._switch(i, C_ATLAS, float(ATLAS_OK))
        log.info("Gegenmaßnahme: %s (hilft kurz)", self.relief_label)

    def vomit(self) -> None:
        now = time.monotonic()
        if now - self.vomit_t0 < 3.5:
            return
        self.vomit_t0 = now
        self.poison = max(0.0, self.poison - 0.15)
        log.info("Neustart-Versuch: alle Schirme booten")

    def toggle_eyes(self) -> None:
        self.eyes_closed = not self.eyes_closed
        self.eyes_t0 = time.monotonic()
        if not self.eyes_closed:
            self._reshuffle(all_screens=True)
        log.info("Stecker %s", "gezogen" if self.eyes_closed else "wieder drin")

    def call_help(self) -> None:
        now = time.monotonic()
        if now - self.help_t0 < 6.0:
            return
        self.help_t0 = now
        self._led_event("blackice_help", now + 5.0)
        log.info("Hilferuf: der Fixer schickt die Katze auf alle Schirme")

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
        self._reshuffle(all_screens=True)
        self.poison = min(1.0, self.poison + 0.1)
        self._led_event("blackice_drop", now + 2.0)
        log.info("Drop: Schrei-Blitz, alle Schirme wechseln")

    def _set_phase(self, ph: int, now: float) -> None:
        self.phase = ph
        self.phase_t0 = now
        self.phase_len = PHASE_LEN[ph] * self.rng.uniform(*PHASE_STRETCH)
        for s in self.screens:
            s.locked = False
        if ph == PH_WARN:
            self.wave += 1
            self.seed = self.rng.uniform(1.0, 100.0)
            wled.apply_mode_async("blackice")
        elif ph == PH_HORROR:
            self.god_cell = 16 + self.rng.randrange(8)
            self.next_whisper = now + 1.0
            if self.rects and self.gods is not None:                        # Glitch-Maske auf dem größten Schirm
                self._switch(0, C_GOD, float(self.god_cell))
                self.screens[0].locked = True
            wled.apply_mode_async("blackice_horror")
        elif ph == PH_BLACKOUT:
            wled.apply_mode_async("blackice_blackout")
        elif ph == PH_POISON:
            wled.apply_mode_async("blackice")
        self._reshuffle(all_screens=True)
        log.info("Phase: %s (Welle %d, %.0f s)", PHASE_NAMES[ph], self.wave, self.phase_len)

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
                "uScreenTex": (self.screens_tex if self.screens_tex is not None else self.blank, 1),
                "uCreatureTex": (self.creatures_tex if self.creatures_tex is not None else self.blank, 1),
                "uFaceTex": (self.face if self.face is not None else self.blank, 1),
                "uGodTex": (self.gods if self.gods is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uScreenTex", "uCreatureTex", "uFaceTex", "uGodTex", "uFigTex", "uSceneSize", "uScreenSize",
                 "uCreatureSize", "uFaceSize", "uGodSize", "uFigSize", "uScreenOK", "uFaceOK", "uGodOK", "uFigOK", "uSeed",
                 "uPhase", "uPhaseT", "uPhaseLen", "uWave", "uPoison", "uRelief", "uReliefT", "uVomitT", "uEyes", "uEyesT",
                 "uHelpT", "uShock", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uFlash",
                 "uCut", "uOwl", "uBands0", "uBands1", "uEyeLook", "uEyeBlink", "uNScr", "uEvent"]
        for i in range(N_SCREENS):
            names += [f"uScr{i}", f"uScrC{i}"]
        return tuple(names)

    def _eyes_tick(self, now: float, dt: float) -> None:
        """Augen: Blick wandert (bei Black ICE zum Betrachter), Blinzeln alle 2 bis 6 s, auf Drops weit auf."""
        if now >= self.next_look:
            self.next_look = now + self.rng.uniform(0.8, 2.5)
            if self.phase == PH_HORROR and self.rng.random() < 0.7:
                self.eye_target = [0.0, 0.0]
            else:
                self.eye_target = [self.rng.uniform(-1.0, 1.0), self.rng.uniform(-0.6, 0.6)]
        rate = 0.12 if self.phase == PH_HORROR else 0.3
        for k in range(2):
            self.eye_look[k] += (self.eye_target[k] - self.eye_look[k]) * min(1.0, dt / rate)
        if now >= self.next_blink:
            self.blink_t0 = now
            self.next_blink = now + self.rng.uniform(2.0, 6.0) * (0.6 if self.phase == PH_HORROR else 1.0)
        b = (now - self.blink_t0) / 0.28
        self.eye_blink = math.sin(b * math.pi) if 0.0 <= b <= 1.0 else 0.0

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        self.t = t
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
        spec = getattr(f, "spectrum", None)
        if spec is not None and len(spec) >= 8 and live:
            n = len(spec) // 8
            for i in range(8):
                v = min(1.0, float(np.mean(spec[i * n:(i + 1) * n])) * (1.15 + 0.1 * i))
                self.bands[i] += (v - self.bands[i]) * min(1.0, dt / (0.04 if v > self.bands[i] else 0.25))
        else:
            for i in range(8):
                self.bands[i] += (0.0 - self.bands[i]) * min(1.0, dt / 0.6)
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            self.flap_t += 1.0
            if self.phase == PH_HORROR or self.poison > 0.75:
                self.cut = (self.rng.uniform(-0.03, 0.03), self.rng.uniform(-0.02, 0.02))
            if not self.event and self.phase != PH_BLACKOUT and not self.eyes_closed:
                n = 1 + min(2, int(self.energy * 3.0 + (1 if self.phase == PH_HORROR else 0)))
                self._reshuffle(count=n)                                      # Schirme wechseln zum Beat
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
        # Phasen in Wellen (Längen zufällig gestreckt)
        pt = now - self.phase_t0
        if pt >= self.phase_len:
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
            self._reshuffle(count=3)
            log.info("Rückfall nach %s", self.relief_label)
        self.eyes += ((1.0 if self.eyes_closed else 0.0) - self.eyes) * min(1.0, dt / 0.6)
        self.shock += ((1.0 if self.shock_on else 0.0) - self.shock) * min(1.0, dt / 1.0)
        self._eyes_tick(now, dt)
        # Schirme auch ohne Beat langsam wechseln, Ereignisse von selbst
        if self.event and t - self.event_t0 >= self.event_len:
            self.event = ""
            self._reshuffle(all_screens=True)
        if live and not self.event and self.phase != PH_BLACKOUT and not self.eyes_closed and now >= self.next_idle_switch:
            self.next_idle_switch = now + self.rng.uniform(3.0, 6.0)
            self._reshuffle(count=1)
        if live and not self.event and self.phase in (PH_WARN, PH_POISON, PH_HORROR) and now >= self.next_event \
                and not self.eyes_closed and now - self.help_t0 > 6.0:
            self.next_event = now + self.rng.uniform(15.0, 30.0)
            self._start_event(self.rng.choice(EVENTS))
        # Flüstern
        if self.phase == PH_HORROR and now >= self.next_whisper:
            self.whisper = self.rng.choice(WHISPERS)
            self.whisper_t0 = now
            self.next_whisper = now + self.rng.uniform(3.0, 5.5)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("blackice_horror" if self.phase == PH_HORROR else "blackice")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("antidote", "vomit", "eyes", "help", "shock", "drop", "event"))
            if pick == "eyes" and self.eyes_closed:
                pick = "antidote"
            {"antidote": self.antidote, "vomit": self.vomit, "eyes": self.toggle_eyes, "help": self.call_help,
             "shock": lambda: self.set_shock(not self.shock_on), "drop": lambda: self._drop(now),
             "event": lambda: self._start_event(self.rng.choice(EVENTS))}[pick]()
            self.demo_next = now + (3.0 if self.eyes_closed else 7.0)
        if self.eyes_closed and self.demo and now - self.demo_next > -0.5 and self.rng.random() < 0.02:
            self.toggle_eyes()
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        flap = self.flap_t % 4.0
        out = {
            "uSceneSize": size(self.scene), "uScreenSize": size(self.screens_tex), "uCreatureSize": size(self.creatures_tex),
            "uFaceSize": size(self.face), "uGodSize": size(self.gods), "uFigSize": size(self.figs),
            "uScreenOK": 1.0 if self.screens_tex is not None else 0.0, "uFaceOK": 1.0 if self.face is not None else 0.0,
            "uGodOK": 1.0 if self.gods is not None else 0.0, "uFigOK": 1.0 if self.figs is not None else 0.0,
            "uSeed": self.seed, "uPhase": float(self.phase), "uPhaseT": pt, "uPhaseLen": self.phase_len,
            "uWave": float(self.wave), "uPoison": self.poison, "uRelief": self.relief,
            "uReliefT": (now - self.relief_t0) if now - self.relief_t0 < 4.0 else -1.0,
            "uVomitT": (now - self.vomit_t0) if now - self.vomit_t0 < 3.0 else -1.0, "uEyes": self.eyes,
            "uEyesT": (now - self.eyes_t0) if self.eyes_closed else -1.0,
            "uHelpT": (now - self.help_t0) if now - self.help_t0 < 5.0 else -1.0, "uShock": self.shock,
            "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy, "uLive": self.live_s,
            "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash, "uCut": self.cut,
            "uOwl": (float(CAT_CELLS[int(flap) % 4]), float(CAT_CELLS[(int(flap) + 1) % 4]), flap - int(flap), 0.0),
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]),
            "uEyeLook": (self.eye_look[0], self.eye_look[1]), "uEyeBlink": self.eye_blink,
            "uNScr": float(len(self.rects)),
            "uEvent": (float(EVENTS.index(self.event) + 1) if self.event else 0.0, self.event_t0, self.event_len, 0.0),
        }
        for i in range(N_SCREENS):
            if i < len(self.rects):
                out[f"uScr{i}"] = tuple(self.rects[i])
                s = self.screens[i]
                out[f"uScrC{i}"] = (float(s.kind), s.var, s.t0, s.seed)
            else:
                out[f"uScr{i}"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uScrC{i}"] = (float(C_OFF), 0.0, 0.0, 0.0)
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
            if pt > self.phase_len - 2.5:
                out.append(("REBOOT ... VERBINDUNG STEHT. NOCH EINMAL.", 0.03, 0.5, 0.42, (120, 220, 255),
                            min(1.0, (pt - (self.phase_len - 2.5)) / 1.0) * 0.8))
        if self.event and self.event != "reboot" and t - self.event_t0 < 2.5:
            k = t - self.event_t0
            out.append((EVENT_NAMES[self.event], 0.028, 0.5, 0.85, (255, 120, 120), 0.8 * min(1.0, k * 3.0) * min(1.0, (2.5 - k) * 2.0)))
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
        if self.live_s < 0.3 and self.phase != PH_BLACKOUT:
            out.append(("STANDBY ... KEIN SIGNAL", 0.022, 0.5, 0.88, (90, 140, 120), 0.5 + 0.2 * math.sin(t * 1.3)))
        return out
