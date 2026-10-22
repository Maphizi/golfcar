"""Das Auge des Waldes (Taste 4 im Thema THE POWER OF THE GREEN, Gegenstück zu HAL 3000).

Ein uralter Baum bei Nacht (assets/woodeye/scene.png), in der Rinde ein riesiges Auge (assets/woodeye/eyes.png,
8x3: Reihe 0 öffnet sich in 8 Schritten, Reihe 1 Irisfarben, Reihe 2 Blickrichtungen, Feuer, Spirale).
Jedes Musikmerkmal hat ein eigenes Element:
  Bass      Pupille weitet sich (Linse), die Rinde pumpt, die Kamera atmet
  Beat      Myzel in den Wurzeln als Lauflicht 1-2-3-4 (Muster wechseln), der Mond pulst
  Spektrum  acht Frösche (assets/woodeye/figures.png Reihen 0-2: sitzend, Kehlsack, Sprung) = acht Frequenzbänder,
            der dicke Ochsenfrosch links ist der Bass, die kleinen rechts die Höhen; laute Bänder springen
  Mitten    Kronendach wiegt sich, Pollen steigen
  Höhen     Glühwürmchen und Tautropfen funkeln
  Drop      Auge blinzelt und brennt, Iris wechselt die Farbe, Sporenwolke, alle Frösche springen,
            Lauflicht wechselt Richtung, Farbwelle im Myzel
  Stille    Auge schließt sich langsam, Myzel glimmt nur, Frösche schlafen
Knüppel: LINKS Fuchs tanzt (Reihe 3, Zellen 24-27), RECHTS Eule fliegt (28-31), OBEN beide, UNTEN Kaleidoskop
(Spiral-Iris, Farben kreisen). Startknopf = Froschchor (Welle durch alle Frösche). Kippschalter = Nahaufnahme ins Auge.
"""
from __future__ import annotations

import logging
import math
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import images

from launcher import wled

log = logging.getLogger("woodeye")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "woodeye"
# Seerosenblätter: (x, y, Größe) im Bild (Anteile, y von unten); Band 0 = Bass (links) .. Band 7 = Höhen (rechts)
FROG_DY = -0.022          # Frösche sitzen AUF dem Blatt (Zellenrand unten)
FROGS = [(0.072, 0.118 + FROG_DY, 0.085), (0.157, 0.150 + FROG_DY, 0.085), (0.287, 0.150 + FROG_DY, 0.082), (0.428, 0.150 + FROG_DY, 0.080),
         (0.571, 0.150 + FROG_DY, 0.078), (0.712, 0.150 + FROG_DY, 0.076), (0.849, 0.150 + FROG_DY, 0.074), (0.930, 0.118 + FROG_DY, 0.074)]
MAX_FROGS = 4             # höchstens so viele gleichzeitig (ruhiger)
# Frosch je Blatt: assets/woodeye/frogs.png (8x4 à 160: Reihe = Art, Spalte = Sprungbild 0 sitzt .. 7 Kehlsack),
# assets/woodeye/dive.png (8x2 à 192: Reihe 0 springt ins Wasser, Reihe 1 taucht auf). Phasen:
PH_EMPTY, PH_EMERGE, PH_SIT, PH_HOP, PH_DIVE, PH_UNDER = 0, 1, 2, 3, 4, 5
HOP_SECONDS, DIVE_SECONDS, EMERGE_SECONDS, UNDER_MIN = 0.6, 0.7, 0.8, 1.2
N_SPECIES = 4
EYE_OPEN, EYE_LEFT, EYE_RIGHT, EYE_UP, EYE_DOWN, EYE_FIRE, EYE_SPIRAL = 7, 16, 18, 19, 20, 22, 23
EYE_COLORS = list(range(8, 16))
OWL_CELLS = (28, 29, 30, 31)
FIG_NONE, FIG_OWL, FIG_GNOMES, FIG_BOTH = 0, 1, 2, 3
# Zwerge (assets/woodeye/gnomes.png 8x3 à 160: Reihe 0 gucken, 1 ducken, 2 winken): (x, y Fußlinie, Größe, Zelle) über den Wurzeln
GNOMES = [(0.06, 0.40, 0.075, 0), (0.14, 0.36, 0.08, 1), (0.22, 0.42, 0.07, 2), (0.30, 0.33, 0.085, 3),
          (0.38, 0.38, 0.07, 4), (0.46, 0.30, 0.08, 5), (0.56, 0.31, 0.078, 6), (0.64, 0.37, 0.072, 7),
          (0.72, 0.33, 0.082, 1), (0.80, 0.41, 0.07, 3), (0.88, 0.36, 0.08, 5), (0.95, 0.42, 0.072, 7)]
N_GNOMES = len(GNOMES)
GNOMES_VISIBLE = 5        # gleichzeitig sichtbare Zwerge (ruhiger als alle zwölf)
G_PEEK, G_DUCK, G_WAVE = 0, 1, 2
CHORUS_SECONDS = 4.0
SPORE_SECONDS = 4.0


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "scene.png")
        self.eyes = _load_rgba(ASSETS / "eyes.png")
        self.figs = _load_rgba(ASSETS / "figures.png")
        self.frogs_tex = _load_rgba(ASSETS / "frogs.png")
        self.dive_tex = _load_rgba(ASSETS / "dive.png")
        self.gnomes_tex = _load_rgba(ASSETS / "gnomes.png")
        self.eye = tuple(float(v) for v in scene_cfg.get("eye", [0.511, 0.722, 0.175]))     # x, y, Breite
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.bands = [0.0] * 8
        self.jump_arm = [True] * 8
        self.phase = [PH_EMPTY] * 8           # je Blatt: leer -> taucht auf -> sitzt -> hüpft / springt ins Wasser -> unten
        self.phase_t0 = [0.0] * 8
        self.species = [self.rng.randrange(N_SPECIES) for _ in range(8)]
        self.under_beats = [0] * 8
        self.returning = [False] * 8          # unter Wasser: kommt wieder hoch (Tauchspiel) oder bleibt weg
        self.last_dive = -10.0
        self.last_pop_change = 0.0
        self.hue_burst = 0.0
        # Zwerge
        self.gnome_pose = [G_PEEK] * N_GNOMES
        self.gnome_prev = [G_PEEK] * N_GNOMES
        self.gnome_t0 = [0.0] * N_GNOMES
        self.gnome_rise = [0.0] * N_GNOMES
        self.hop_wish = [False] * 8
        self.gnome_on = [True] * N_GNOMES
        self.gnome_wave_next = time.monotonic() + 3.0
        # Beat-Zähler / Lauflicht
        self.step = 0
        self.step_t0 = 0.0
        self.step_dir = 1
        self.pattern = 0
        self.pattern_next = time.monotonic() + self.rng.uniform(25.0, 45.0)
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        # Drop
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.spore_t0 = -100.0
        # Auge
        self.open = 0.0
        self.blink_t0 = -10.0
        self.blink_next = time.monotonic() + self.rng.uniform(5.0, 12.0)
        self.look = EYE_OPEN
        self.look_prev = EYE_OPEN
        self.look_t0 = 0.0
        self.gaze_until = 0.0
        self.gaze_next = time.monotonic() + self.rng.uniform(4.0, 9.0)
        self.color_until = -1.0
        self.color_cell = EYE_COLORS[0]
        self.fire_until = -1.0
        # Figuren
        self.fig = FIG_NONE
        self.owl_t = 0.0
        self.flap_t = 0.0
        self.kaleido = 0.0
        self.kaleido_on = False
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.chorus_t0 = -100.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 4.0
        log.info("Auge des Waldes: Szene %s, Augen %s, Eule %s, Frösche %s, Tauchen %s, Zwerge %s",
                 "ok" if self.scene is not None else "fehlt", "ok" if self.eyes is not None else "fehlt",
                 "ok" if self.figs is not None else "fehlt", "ok" if self.frogs_tex is not None else "fehlt",
                 "ok" if self.dive_tex is not None else "fehlt", "ok" if self.gnomes_tex is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def set_fig(self, which: int) -> None:
        self.fig = FIG_NONE if self.fig == which else which
        if self.fig in (FIG_GNOMES, FIG_BOTH):
            self._gnome_pick()
        now = time.monotonic()
        if self.fig == FIG_NONE:
            wled.apply_mode_async("woodeye")
            self.led_back_at = None
            return
        profile = {FIG_OWL: "woodeye_owl", FIG_GNOMES: "woodeye_fox", FIG_BOTH: "woodeye_both"}[self.fig]
        self._led_event(profile, now + 6.0)
        log.info("Figur: %s", {FIG_OWL: "Eule", FIG_GNOMES: "Zwerge", FIG_BOTH: "Eule und Zwerge"}[self.fig])

    def toggle_kaleido(self) -> None:
        self.kaleido_on = not self.kaleido_on
        self._set_look(EYE_SPIRAL if self.kaleido_on else EYE_OPEN)
        log.info("Kaleidoskop %s", "an" if self.kaleido_on else "aus")

    def chorus(self) -> None:
        now = time.monotonic()
        if now - self.chorus_t0 < CHORUS_SECONDS:
            return
        self.chorus_t0 = now
        for i in range(8):                   # Welle: alle sitzenden hüpfen nacheinander, leere Blätter bekommen Besuch
            if self.phase[i] == PH_SIT:
                self._set_phase(i, PH_HOP, now + 0.3 + i * 0.14)
            elif self.phase[i] in (PH_EMPTY, PH_UNDER) and i % 2 == 0 and self.energy > 0.3 \
                    and sum(1 for p in self.phase if p in (PH_SIT, PH_HOP, PH_EMERGE)) < MAX_FROGS:
                self._set_phase(i, PH_EMERGE, now + 0.3 + i * 0.14)
                self.species[i] = self.rng.randrange(N_SPECIES)
        self._led_event("woodeye_chorus", now + CHORUS_SECONDS)
        log.info("Froschchor")

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _set_look(self, cell: int) -> None:
        if cell == self.look:
            return
        self.look_prev = self.look
        self.look = cell
        self.look_t0 = time.monotonic()

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.spore_t0 = now
        self.blink_t0 = now
        self.step_dir = -self.step_dir
        self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
        self.pattern_next = now + self.rng.uniform(25.0, 45.0)
        self.fire_until = now + 1.4
        self.color_cell = self.rng.choice([c for c in EYE_COLORS if c != self.color_cell])
        self.color_until = now + 7.0
        for i in range(8):
            if self.phase[i] == PH_SIT:
                self._set_phase(i, PH_HOP, now + 0.05 * i)
        self.hue_burst = 1.0
        log.info("Drop: Auge brennt, Sporen, Frösche springen")

    def _set_phase(self, i: int, ph: int, t0: float) -> None:
        self.phase[i] = ph
        self.phase_t0[i] = t0

    def _frogs_tick(self, now: float, on_beat: bool, live: float, dt: float) -> None:
        """Besetzung der Blätter folgt der Musik: Stille = keiner, leise = vereinzelt, laut = alle. Frösche kommen aus dem
        Wasser (tauchen auf) und gehen, indem sie hineinspringen. Dazu das Tauchspiel im Takt: auf Beats springt mal
        einer ab und kommt ein paar Beats später wieder hoch."""
        # Phasenübergänge
        for i in range(8):
            ph, t0 = self.phase[i], self.phase_t0[i]
            if now < t0:
                continue
            if ph == PH_HOP and now - t0 >= HOP_SECONDS:
                self._set_phase(i, PH_SIT, now)
            elif ph == PH_DIVE and now - t0 >= DIVE_SECONDS:
                self._set_phase(i, PH_UNDER, now)
            elif ph == PH_EMERGE and now - t0 >= EMERGE_SECONDS:
                self._set_phase(i, PH_SIT, now)
            elif ph == PH_UNDER and now - t0 >= UNDER_MIN:
                if self.returning[i]:
                    if on_beat:
                        self.under_beats[i] -= 1
                        if self.under_beats[i] <= 0:
                            self._set_phase(i, PH_EMERGE, now)
                    elif live < 0.3 and now - t0 > 3.0:
                        self._set_phase(i, PH_EMPTY, now)
                elif now - t0 > 2.5:
                    self._set_phase(i, PH_EMPTY, now)
        # Zielbesetzung aus der Musik
        if live < 0.3:
            target = 0
        else:
            e = max(0.0, min(1.0, (self.energy - 0.12) / 0.5))
            target = int(round(0.4 + (MAX_FROGS - 0.4) * e))
            target = max(0, min(MAX_FROGS, target))
        present = [i for i in range(8) if self.phase[i] in (PH_SIT, PH_HOP, PH_EMERGE)]
        if on_beat and now - self.last_pop_change > (1.2 if target > len(present) else 2.5):   # nur auf den Beat
            if target > len(present):
                cands = [i for i in range(8) if self.phase[i] == PH_EMPTY or (self.phase[i] == PH_UNDER and not self.returning[i] and now - self.phase_t0[i] > UNDER_MIN)]
                if cands:
                    i = self.rng.choice(cands)
                    self.species[i] = self.rng.randrange(N_SPECIES)
                    self._set_phase(i, PH_EMERGE, now)
                    self.last_pop_change = now
            elif target < len(present) - 1 or (target == 0 and present):
                cands = [i for i in present if self.phase[i] == PH_SIT and now - self.phase_t0[i] > 1.0]
                if cands:
                    i = self.rng.choice(cands)
                    self.returning[i] = False
                    self._set_phase(i, PH_DIVE, now)
                    self.last_pop_change = now
        # Tauchspiel im Takt
        under = sum(1 for p in self.phase if p in (PH_DIVE, PH_UNDER))
        if on_beat and live > 0.3 and under < 2 and now - self.last_dive > 4.0 and len(present) >= 2:
            if self.rng.random() < 0.04 + 0.12 * self.energy:
                cands = [i for i in present if self.phase[i] == PH_SIT and now - self.phase_t0[i] > 1.5]
                if cands:
                    i = self.rng.choice(cands)
                    self.returning[i] = True
                    self.under_beats[i] = self.rng.choice((2, 2, 3, 4, 6))
                    self._set_phase(i, PH_DIVE, now)
                    self.last_dive = now

    def _gnomes_tick(self, now: float, on_beat: bool, dt: float) -> None:
        show = self.fig in (FIG_GNOMES, FIG_BOTH)
        for i in range(N_GNOMES):
            target = 1.0 if (show and self.gnome_on[i]) else 0.0
            delay = 0.06 * i if show else 0.04 * (N_GNOMES - i)
            self.gnome_rise[i] += (target - self.gnome_rise[i]) * min(1.0, dt / 0.5) * (1.0 if now - self.gnome_t0[i] > delay else 0.3)
            if self.gnome_pose[i] == G_DUCK and now - self.gnome_t0[i] > 0.45:
                self._gnome_set(i, G_PEEK, now)
            elif self.gnome_pose[i] == G_WAVE and now - self.gnome_t0[i] > 1.3:
                self._gnome_set(i, G_PEEK, now)
        if not show:
            return
        if on_beat:
            for i in range(N_GNOMES):
                if self.gnome_on[i] and self.gnome_pose[i] == G_PEEK and self.rng.random() < 0.08 + 0.15 * self.bass_s:
                    self._gnome_set(i, G_DUCK, now)
        if now >= self.gnome_wave_next:
            self.gnome_wave_next = now + self.rng.uniform(5.0, 10.0)
            # alle paar Winker wechselt die Besetzung: einer verschwindet, ein anderer kommt
            if self.rng.random() < 0.4:
                on = [i for i in range(N_GNOMES) if self.gnome_on[i]]
                off = [i for i in range(N_GNOMES) if not self.gnome_on[i]]
                if on and off:
                    self.gnome_on[self.rng.choice(on)] = False
                    self.gnome_on[self.rng.choice(off)] = True
            i = self.rng.randrange(N_GNOMES)
            if self.gnome_pose[i] == G_PEEK:
                self._gnome_set(i, G_WAVE, now)

    def _gnome_pick(self) -> None:
        """Fünf zufällige Zwerge sichtbar, die anderen bleiben unten."""
        chosen = set(self.rng.sample(range(N_GNOMES), GNOMES_VISIBLE))
        self.gnome_on = [i in chosen for i in range(N_GNOMES)]

    def _gnome_set(self, i: int, pose: int, now: float) -> None:
        self.gnome_prev[i] = self.gnome_pose[i]
        self.gnome_pose[i] = pose
        self.gnome_t0[i] = now

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.set_fig(FIG_OWL)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.set_fig(FIG_GNOMES)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.set_fig(FIG_BOTH)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_kaleido()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.chorus()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uEyeTex": (self.eyes if self.eyes is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1),
                "uFrogTex": (self.frogs_tex if self.frogs_tex is not None else self.blank, 1),
                "uDiveTex": (self.dive_tex if self.dive_tex is not None else self.blank, 1),
                "uGnomeTex": (self.gnomes_tex if self.gnomes_tex is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uEyeTex", "uFigTex", "uSceneSize", "uEyeSize", "uFigSize", "uSeed", "uEyePos",
                 "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uStep", "uStepPhase", "uPattern",
                 "uFlash", "uSporeT", "uZoom", "uKaleido", "uChorusT", "uBlink", "uEyeA", "uEyeB", "uEyeMix",
                 "uFig", "uOwl", "uBands0", "uBands1", "uHueT"]
        names += [f"uFrog{i}" for i in range(8)]
        names += [f"uFrogPh{i}" for i in range(8)]
        names += ["uHueBurst", "uFrogTex", "uDiveTex", "uGnomeTex", "uFrogSize", "uDiveSize", "uGnomeSize"]
        names += [f"uGnome{i}" for i in range(N_GNOMES)]
        names += [f"uGnomeS{i}" for i in range(N_GNOMES)]
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
        self.bass_s += (bass - self.bass_s) * min(1.0, dt / 0.15)
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.35)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.12)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        # Spektrum -> acht Bänder (Frösche), schneller Anstieg, langsames Abklingen
        spec = getattr(f, "spectrum", None)
        if spec is not None and len(spec) >= 8 and live:
            n = len(spec) // 8
            for i in range(8):
                v = float(np.mean(spec[i * n:(i + 1) * n]))
                v = min(1.0, v * (1.15 + 0.1 * i))
                rate = 0.05 if v > self.bands[i] else 0.3
                self.bands[i] += (v - self.bands[i]) * min(1.0, dt / rate)
                if v > 0.78 and self.jump_arm[i] and self.phase[i] == PH_SIT and now - self.phase_t0[i] > 0.5:
                    self.hop_wish[i] = True                        # springt beim nächsten Beat
                    self.jump_arm[i] = False
                if v < 0.5:
                    self.jump_arm[i] = True
        else:
            for i in range(8):
                self.bands[i] += (0.0 - self.bands[i]) * min(1.0, dt / 0.6)
        # Beat: Lauflicht einen Schritt weiter, Puls, Frösche tauchen
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if on_beat:
            hoppers = [i for i in range(8) if self.hop_wish[i] and self.phase[i] == PH_SIT]
            for i in hoppers[:2]:                                   # höchstens zwei je Beat
                self._set_phase(i, PH_HOP, now)
            for i in range(8):
                self.hop_wish[i] = False
        self._frogs_tick(now, on_beat, self.live_s, dt)
        self._gnomes_tick(now, on_beat, dt)
        self.hue_burst = max(0.0, self.hue_burst - dt / 3.0)
        if on_beat:
            self.last_beat = now
            self.step = (self.step + self.step_dir) % 4
            self.step_t0 = now
            self.beat_pulse = 1.0
            self.flap_t += 1.0
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        if now >= self.pattern_next:
            self.pattern = (self.pattern + self.rng.randint(1, 3)) % 4
            self.pattern_next = now + self.rng.uniform(25.0, 45.0)
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
        self.flash = max(0.0, self.flash - dt / 2.0)
        # Auge: öffnet sich mit Musik, schließt sich in der Stille; Blinzeln; Blick folgt dem lautesten Frosch
        target = 1.0 if self.live_s > 0.3 else 0.0
        self.open += (target - self.open) * min(1.0, dt / (0.6 if target > self.open else 2.5))
        if now >= self.blink_next:
            self.blink_t0 = now
            self.blink_next = now + self.rng.uniform(5.0, 12.0)
        bl = (now - self.blink_t0) / 0.32
        blink = 1.0 - math.sin(min(1.0, bl) * math.pi) if 0.0 <= bl < 1.0 else 1.0
        openness = max(0.0, min(1.0, self.open * blink))
        if self.kaleido_on:
            self._set_look(EYE_SPIRAL)
        elif now < self.fire_until:
            self._set_look(EYE_FIRE)
        else:
            loud = max(range(8), key=lambda i: self.bands[i])
            if self.bands[loud] > 0.72 and now > self.gaze_until - 0.6:
                self._set_look(EYE_LEFT if loud <= 2 else (EYE_RIGHT if loud >= 5 else EYE_DOWN))
                self.gaze_until = now + 1.2
            elif now >= self.gaze_next:
                self._set_look(self.rng.choice((EYE_LEFT, EYE_RIGHT, EYE_UP, EYE_DOWN)))
                self.gaze_until = now + self.rng.uniform(1.0, 2.0)
                self.gaze_next = now + self.rng.uniform(4.0, 9.0)
            elif now >= self.gaze_until:
                self._set_look(self.color_cell if now < self.color_until else EYE_OPEN)
        look_mix = min(1.0, (now - self.look_t0) / 0.25)
        # Figuren, Kaleidoskop, Zoom, Eule
        self.owl_t += dt * (0.12 + 0.25 * self.energy + 0.1 * self.bass_s)
        self.flap_t += dt * (1.5 + 5.0 * self.bass_s)
        self.kaleido += ((1.0 if self.kaleido_on else 0.0) - self.kaleido) * min(1.0, dt / 1.2)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("woodeye")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("gnomes", "owl", "both", "kaleido", "chorus", "drop"))
            {"gnomes": lambda: self.set_fig(FIG_GNOMES), "owl": lambda: self.set_fig(FIG_OWL), "both": lambda: self.set_fig(FIG_BOTH),
             "kaleido": self.toggle_kaleido, "chorus": self.chorus, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 9.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        flap = self.flap_t % 4.0
        out = {
            "uSceneSize": size(self.scene), "uEyeSize": size(self.eyes), "uFigSize": size(self.figs), "uSeed": self.seed,
            "uEyePos": self.eye, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uStep": float(self.step),
            "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern), "uFlash": self.flash,
            "uSporeT": (now - self.spore_t0) if now - self.spore_t0 < SPORE_SECONDS else -1.0, "uZoom": self.zoom,
            "uKaleido": self.kaleido, "uChorusT": (now - self.chorus_t0) if now - self.chorus_t0 < CHORUS_SECONDS else -1.0,
            "uBlink": openness, "uEyeA": float(self.look_prev), "uEyeB": float(self.look), "uEyeMix": look_mix,
            "uFig": (float(self.fig), 0.0, 0.0, 0.0),
            "uFrogSize": size(self.frogs_tex), "uDiveSize": size(self.dive_tex), "uGnomeSize": size(self.gnomes_tex),
            "uOwl": (self.owl_t % 1000.0, float(OWL_CELLS[int(flap) % 4]), float(OWL_CELLS[(int(flap) + 1) % 4]), flap - int(flap)),
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]), "uHueT": (t * 0.15) % 1000.0,
        }
        out["uHueBurst"] = self.hue_burst
        for i, (x, y, s) in enumerate(FROGS):
            ph = self.phase[i]
            pt = now - self.phase_t0[i]
            if pt < 0.0:                                          # geplant, noch nicht dran: wie vorher weiter zeigen
                ph = PH_SIT if ph == PH_HOP else (PH_EMPTY if ph == PH_EMERGE else ph)
                pt = 0.0
            dur = {PH_HOP: HOP_SECONDS, PH_DIVE: DIVE_SECONDS, PH_EMERGE: EMERGE_SECONDS}.get(ph, 1.0)
            prog = min(1.0, pt / dur) if ph in (PH_HOP, PH_DIVE, PH_EMERGE) else pt
            out[f"uFrog{i}"] = (x, y, s, float(self.species[i]))
            out[f"uFrogPh{i}"] = (float(ph), prog, 1.0 if x > 0.5 else 0.0, 0.0)
        for i, (x, y, s, cell) in enumerate(GNOMES):
            out[f"uGnome{i}"] = (x, y, s, float(cell))
            out[f"uGnomeS{i}"] = (float(self.gnome_prev[i]), float(self.gnome_pose[i]), min(1.0, (now - self.gnome_t0[i]) / 0.12), self.gnome_rise[i])
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if now - self.chorus_t0 < CHORUS_SECONDS:
            a = min(1.0, (now - self.chorus_t0) / 0.4) * min(1.0, (CHORUS_SECONDS - (now - self.chorus_t0)) / 0.8)
            out.append(("F R O S C H C H O R", 0.035, 0.5, 0.5, (200, 255, 210), 0.8 * a))
        if now - self.spore_t0 < 2.5:
            a = min(1.0, (2.5 - (now - self.spore_t0)) / 0.8)
            out.append(("D E R   W A L D   E R W A C H T", 0.03, 0.5, 0.08, (180, 255, 220), 0.7 * a))
        if self.fig != FIG_NONE:
            label = {FIG_GNOMES: "DIE ZWERGE SCHAUEN", FIG_OWL: "DIE EULE KREIST", FIG_BOTH: "EULE UND ZWERGE"}[self.fig]
            out.append((label, 0.018, 0.5, 0.05, (190, 220, 200), 0.55))
        return out
