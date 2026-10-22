"""Das Orakel (Taste 4 im Thema CYBERPUNK, Gegenstück zu HAL 3000 / Auge des Waldes).

Serverhalle (assets/cyber/oracle_scene.png) mit einem schwebenden Hologramm-Kopf im Projektionsrahmen
(assets/cyber/oracle_heads.png, 8x3 à 192: 24 verschiedene Köpfe, HEAD_NAMES; der Glitch-Übergang ist rein prozedural).
Jedes Musikmerkmal hat sein Element:
  Beat      die acht Neontafeln gehen hart an/aus nach Mustern (uPanelOn, uPattern), Serverlichter in Zonen blinken mit,
            jeder 4. Beat ein neuer Kopf (bei hoher Energie jeder 2., Automatik schnell: jeder Beat)
  Bass      Kopf atmet/pulst, Hologramm flackert, Serverlichter glühen
  Mitten    Kopf dreht sich leicht (Parallaxe), Datenregen im Hintergrund
  Höhen     Funkenregen im Rahmen, Funken an den Kabeln
  Spektrum  Bandenergie = Füllhöhe/Helligkeit innerhalb einer AN-Tafel (uBands/uPeaks)
  Drop      Datenexplosion, neuer Kopf mit Glitch-Übergang, neues Tafelmuster, neuer Farbton
  Stille    der Kopf erlischt zum Drahtgitter/Scanlinien-Schemen (uAwake)
Von selbst alle 20-40 s ein Ereignis: Datenexplosion, Kopf-Salve (4 Köpfe in 2 s), Scanner-Welle durch die Halle,
kurzer Glitch-Modus, Orakelspruch. Knüppel LINKS/RECHTS = voriger/nächster Kopf, OBEN = Automatik schnell (20 s),
UNTEN = Glitch-Modus (Bild zerfällt in Blöcke, Farbkanäle laufen auseinander). Startknopf = das Orakel spricht
(Spruch wird getippt, Kopf glitcht zum Text). Kippschalter = Nahaufnahme.
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

log = logging.getLogger("oracle")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
HEAD_CELL = 192
HEADS = 24
HEAD_NAMES = ["GEISHA", "ONI", "ANDROID", "NEONSCHÄDEL", "CYBERKATZE", "KITSUNE", "BUDDHA", "VR-HELM",
              "DRAHTGITTER", "TATTOO", "HALBROBOTER", "GASMASKE", "SAMURAI", "QUALLE", "PIXEL", "MANNEQUIN",
              "OKTOPUS", "PUPPE", "DATENBRILLE", "LÖWE", "KAPUZE", "GLASKOPF", "ROSENSCHÄDEL", "PORZELLAN"]
HEAD_MEMORY = 10        # so viele zuletzt gezeigte Köpfe werden beim Würfeln gemieden
N_PATTERNS = 8          # Lauflicht l->r, r->l, außen->innen, gerade/ungerade, zufällig, alle an jeden 4., Spiegel, Paare
PATTERN_NAMES = ["LAUFLICHT", "RÜCKLAUF", "AUSSEN-INNEN", "WECHSEL", "ZUFALL", "VOLLBILD", "SPIEGEL", "PAARE"]
SPEAK_SECONDS = 6.0
FAST_SECONDS = 20.0
SALVO_SECONDS = 2.0
SCAN_SECONDS = 2.4
AUTO_GLITCH_SECONDS = 4.0
AFTERGLOW = 0.1         # Nachglühen einer aus-Tafel (s)
AUTO_EVENT = (20.0, 40.0)
ORACLE_LINES = [
    "DEINE DATEN SIND SCHON VERKAUFT.", "DER REGEN HÖRT NIE AUF. DU GEWÖHNST DICH.", "ICH SEHE 4.096 VERSIONEN VON DIR.",
    "DAS TAXI FÄHRT. DAS TAXAMETER AUCH.", "FRAG NICHT NACH DEM PREIS. FRAG NACH DER WÄHRUNG.", "DU BIST OFFLINE. ICH NICHT.",
    "DIE STADT TRÄUMT IN NEON. DU BIST EIN PIXEL.", "DEIN HANDICAP IST DEM KONZERN BEKANNT.", "NOCH EIN UPDATE. DANN BIST DU FREI.",
    "DIE KATZE WEISS MEHR ALS DU.", "VERTRAU KEINEM HOLOGRAMM. AUCH MIR NICHT.", "LOCH 19 LIEGT IM SEKTOR 7.",
    "ICH HABE ACHT GESICHTER. KEINES IST MEINS.", "DER SAMURAI WARTET SEIT 1999 AUF EIN UPDATE.",
]


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


def _pattern_mask(pattern: int, step: int, rnd: random.Random) -> list[bool]:
    """Welche der acht Tafeln bei Beat-Schritt `step` (0..7) im Muster `pattern` an sind."""
    s = step % 8
    if pattern == 0:                                   # Lauflicht links -> rechts (zwei Läufer im Abstand 4)
        return [i == s or i == (s + 4) % 8 for i in range(8)]
    if pattern == 1:                                   # rechts -> links
        return [i == 7 - s or i == (11 - s) % 8 for i in range(8)]
    if pattern == 2:                                   # von außen nach innen und zurück (Paare 0/7, 1/6, 2/5, 3/4)
        k = s if s < 4 else 7 - s
        return [i == k or i == 7 - k for i in range(8)]
    if pattern == 3:                                   # gerade / ungerade im Wechsel
        return [(i % 2) == (s % 2) for i in range(8)]
    if pattern == 4:                                   # zufällig, drei bis vier Tafeln
        on = [False] * 8
        for i in rnd.sample(range(8), rnd.randint(3, 4)):
            on[i] = True
        return on
    if pattern == 5:                                   # alle an auf jedem 4. Beat, dazwischen eine wandert
        return [True] * 8 if s % 4 == 0 else [i == (s * 3) % 8 for i in range(8)]
    if pattern == 6:                                   # Spiegel: zwei Lichter laufen von der Mitte nach außen
        k = s % 4
        return [i == 3 - k or i == 4 + k for i in range(8)]
    pair = s % 4                                       # Paare: 0+1, 2+3, 4+5, 6+7 (reihum)
    return [i // 2 == pair for i in range(8)]


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "oracle_scene.png")
        self.heads = _load_rgba(ASSETS / "oracle_heads.png")
        self.figs = _load_rgba(ASSETS / "oracle_figures.png")
        self.frame = tuple(float(v) for v in scene_cfg.get("frame", [0.505, 0.73, 0.27]))      # x, y, Breite
        self.panels = tuple(float(v) for v in scene_cfg.get("panels", [0.264, 0.757, 0.385, 0.052]))   # x0, x7, y, Breite
        self.auto_event = tuple(float(v) for v in scene_cfg.get("auto_event", AUTO_EVENT))
        self.seed = self.rng.uniform(1.0, 100.0)
        now = time.monotonic()
        self.last = now
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.bands = [0.0] * 8
        self.band_peak = [0.0] * 8
        # Beat / Tafeln
        self.step = 0                                   # Beat-Schritt 0..7 (Tafelmuster), Zonen 0..3 = step % 4
        self.step_t0 = 0.0
        self.pattern = 0
        self.pattern_beats = 0
        self.pattern_len = self.rng.randint(8, 16)
        self.panel_on = [False] * 8
        self.panel_lvl = [0.0] * 8
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.beat_count = 0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.burst_t0 = -100.0
        # Kopf
        self.head = self.rng.randrange(HEADS)
        self.head_prev = self.head
        self.recent = [self.head]                      # zuletzt gezeigte Köpfe (nicht zu oft dieselben)
        self.head_t0 = -10.0
        self.head_len = 0.3                            # Dauer des Übergangs
        self.head_glitch = 0.3                         # Stärke des Glitch-Übergangs 0..1
        self.head_beats = 0                            # Beats seit dem letzten Wechsel
        self.hue = 0.0
        self.hue_target = 0.0
        self.awake = 0.0
        self.speak_t0 = -100.0
        self.line = ""
        self.line_t0 = -10.0
        # Automatik
        self.fast_until = -1.0
        self.salvo_until = -1.0
        self.salvo_next = 0.0
        self.scan_t0 = -100.0
        self.auto_glitch_until = -1.0
        self.auto_next = now + self.rng.uniform(*self.auto_event)
        self.last_key = -100.0
        self.last_head_led = -100.0
        self.head_led_toggle = False
        # Glitch-Modus / Zoom
        self.glitch_mode = False
        self.glitch_k = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = now + 4.0
        self.demo_drop_next = now + 9.0
        log.info("Das Orakel: Szene %s, Köpfe %s, Glyphen %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.heads is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def set_head(self, idx: int, glitch: float = 0.3, length: float = 0.3, manual: bool = False) -> None:
        """Neuen Kopf einblenden; glitch = Stärke der Glitch-Zwischenphase (Drop = 1.0)."""
        now = time.monotonic()
        idx %= HEADS
        if idx == self.head:
            return
        self.head_prev = self.head
        self.head = idx
        self.head_t0 = now
        self.head_len = length
        self.head_glitch = glitch
        self.head_beats = 0
        self.recent.append(idx)
        del self.recent[:-HEAD_MEMORY]
        if self.rng.random() < 0.35:
            self.hue_target = self.rng.choice((0.0, 0.0, 0.6, -0.6, 1.2, 2.4))
        if manual or now - self.last_head_led > 3.0:
            self.last_head_led = now
            self.head_led_toggle = not self.head_led_toggle
            if self.led_back_at is None or now >= self.led_back_at:
                self._led_event("oracle_samurai" if self.head_led_toggle else "oracle_cat", now + 1.0)

    def next_head(self, direction: int) -> None:
        self.last_key = time.monotonic()
        self.set_head(self.head + direction, glitch=0.5, length=0.25, manual=True)
        log.info("Kopf von Hand: %s", HEAD_NAMES[self.head])

    def random_head(self, glitch: float = 0.3, length: float = 0.3) -> None:
        """Zufälliger Kopf, nie derselbe und keiner der zuletzt gezeigten (HEAD_MEMORY)."""
        pool = [i for i in range(HEADS) if i != self.head and i not in self.recent]
        self.set_head(self.rng.choice(pool or [i for i in range(HEADS) if i != self.head]), glitch, length)

    def fast(self) -> None:
        now = time.monotonic()
        self.last_key = now
        if now < self.fast_until:
            self.fast_until = -1.0
            log.info("Automatik schnell aus")
            return
        self.fast_until = now + FAST_SECONDS
        self.random_head(0.5, 0.2)
        log.info("Automatik schnell: jeder Beat ein Kopf (%.0f s)", FAST_SECONDS)

    def salvo(self) -> None:
        now = time.monotonic()
        self.salvo_until = now + SALVO_SECONDS
        self.salvo_next = now
        log.info("Kopf-Salve")

    def scan(self) -> None:
        self.scan_t0 = time.monotonic()
        log.info("Scanner-Welle")

    def burst(self) -> None:
        now = time.monotonic()
        self.flash = max(self.flash, 0.7)
        self.burst_t0 = now
        self._led_event("oracle_both", now + 3.0)
        log.info("Datenexplosion")

    def toggle_glitch(self) -> None:
        self.last_key = time.monotonic()
        self.glitch_mode = not self.glitch_mode
        self.auto_glitch_until = -1.0
        log.info("Glitch-Modus %s", "an" if self.glitch_mode else "aus")

    def speak(self) -> None:
        now = time.monotonic()
        if now - self.speak_t0 < SPEAK_SECONDS:
            return
        self.speak_t0 = now
        self.line = self.rng.choice(ORACLE_LINES)
        self.line_t0 = now + 0.4
        self._led_event("oracle_speak", now + SPEAK_SECONDS)
        log.info("Orakel: %s", self.line)

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _new_pattern(self) -> None:
        self.pattern = (self.pattern + self.rng.randint(1, N_PATTERNS - 1)) % N_PATTERNS
        self.pattern_beats = 0
        self.pattern_len = self.rng.randint(8, 16)

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.burst_t0 = now
        self._new_pattern()
        self.random_head(1.0, 0.6)
        self.hue_target = self.rng.choice((0.6, -0.6, 1.2, -1.2, 2.4, 3.6))
        self._led_event("oracle_both", now + 3.0)
        log.info("Drop: Datenexplosion, Kopf %s, Muster %s", HEAD_NAMES[self.head], PATTERN_NAMES[self.pattern])

    def _beat(self, now: float) -> None:
        """Ein Beat: Tafelmuster weiterschalten, Kopf nach Zählung wechseln."""
        self.last_beat = now
        self.beat_pulse = 1.0
        self.beat_count += 1
        self.beat_step = (self.beat_step + 1) % 8
        self.step = (self.step + 1) % 8
        self.step_t0 = now
        self.pattern_beats += 1
        if self.pattern_beats >= self.pattern_len:
            self._new_pattern()
        self.panel_on = _pattern_mask(self.pattern, self.step, self.rng)
        self.head_beats += 1
        if now < self.salvo_until:
            return
        period = 1 if now < self.fast_until else (2 if self.energy > 0.45 else 4)
        if self.head_beats >= period and now - self.head_t0 > 0.35:
            self.random_head(0.5 if now < self.fast_until else 0.3, 0.2 if now < self.fast_until else 0.3)

    def _auto_event(self, now: float) -> None:
        pick = self.rng.choice(("burst", "salvo", "scan", "scan", "glitch", "speak", "salvo"))
        if pick == "burst":
            self.burst()
        elif pick == "salvo":
            self.salvo()
        elif pick == "scan":
            self.scan()
        elif pick == "glitch":
            if not self.glitch_mode:
                self.auto_glitch_until = now + AUTO_GLITCH_SECONDS
                log.info("Kurzer Glitch-Modus")
        else:
            self.speak()

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.next_head(-1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.next_head(1)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.fast()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.toggle_glitch()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.last_key = time.monotonic()
            self.speak()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uHeadTex": (self.heads if self.heads is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uSceneTex", "uHeadTex", "uFigTex", "uSceneSize", "uHeadSize", "uFigSize", "uSeed", "uFrame", "uPanels",
                "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uStep", "uStepPhase", "uPattern",
                "uPanelOn0", "uPanelOn1", "uZoneOn", "uFlash", "uBurstT", "uAwake", "uHeadA", "uHeadB", "uHeadMix", "uHeadGlitch",
                "uHue", "uSpeakT", "uScanT", "uFast", "uGlitch", "uZoom", "uBands0", "uBands1", "uPeaks0", "uPeaks1")

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
        spec = getattr(f, "spectrum", None)
        if spec is not None and len(spec) >= 8 and live:
            n = len(spec) // 8
            for i in range(8):
                v = min(1.0, float(np.mean(spec[i * n:(i + 1) * n])) * (1.15 + 0.1 * i))
                rate = 0.04 if v > self.bands[i] else 0.25
                self.bands[i] += (v - self.bands[i]) * min(1.0, dt / rate)
                self.band_peak[i] = max(self.band_peak[i] - dt * 0.6, v if v > self.band_peak[i] else self.band_peak[i])
        else:
            for i in range(8):
                self.bands[i] += (0.0 - self.bands[i]) * min(1.0, dt / 0.6)
                self.band_peak[i] = max(0.0, self.band_peak[i] - dt * 0.6)
        # Beat: echter Beat, sonst (Musik ohne erkannten Beat) ein weicher Takt alle 0.6 s, bei Stille nichts
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if not on_beat and live and self.energy > 0.08 and now - self.last_beat > 1.4:
            on_beat = True
        if on_beat:
            self._beat(now)
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        # Tafeln: an = 1, aus fällt in AFTERGLOW auf 0; bei Stille alles aus
        for i in range(8):
            target = 1.0 if (self.panel_on[i] and live) else 0.0
            if target > self.panel_lvl[i]:
                self.panel_lvl[i] = target
            else:
                self.panel_lvl[i] = max(target, self.panel_lvl[i] - dt / AFTERGLOW)
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
        # Kopf: wach mit Musik, Salve, Farbton gleitet
        self.awake += ((1.0 if self.live_s > 0.3 else 0.0) - self.awake) * min(1.0, dt / (0.8 if self.live_s > 0.3 else 3.0))
        if now < self.salvo_until and now >= self.salvo_next:
            self.salvo_next = now + SALVO_SECONDS / 4.0
            self.random_head(0.7, 0.18)
        self.hue += (self.hue_target - self.hue) * min(1.0, dt / 1.5)
        speaking = now - self.speak_t0 < SPEAK_SECONDS
        # Automatik: Ereignis von selbst, wenn 6 s keine Taste
        if now >= self.auto_next:
            self.auto_next = now + self.rng.uniform(*self.auto_event)
            if now - self.last_key > 6.0 and live:
                self._auto_event(now)
        glitch_on = self.glitch_mode or now < self.auto_glitch_until
        self.glitch_k += ((1.0 if glitch_on else 0.0) - self.glitch_k) * min(1.0, dt / 0.6)
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("oracle")
        if self.demo:
            if now >= self.demo_next:
                self.demo_next = now + 7.0
                self.rng.choice((self.burst, self.salvo, self.scan, self.speak, self.fast, self.toggle_glitch))()
                self.last_key = -100.0
            if now >= self.demo_drop_next:
                self.demo_drop_next = now + 14.0
                self._drop(now)
        # Übergang des Kopfes: Mischung 0..1, Glitch-Anteil als Buckel in der Mitte (+ Puls beim Sprechen)
        mix = min(1.0, (now - self.head_t0) / max(0.05, self.head_len))
        hg = self.head_glitch * math.sin(mix * math.pi)
        if speaking:
            hg = max(hg, 0.35 * abs(math.sin((now - self.speak_t0) * 14.0)))
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        zone_on = [1.0 if (self.panel_lvl[2 * z] > 0.5 or self.panel_lvl[2 * z + 1] > 0.5) else 0.0 for z in range(4)]
        return {
            "uSceneSize": size(self.scene), "uHeadSize": size(self.heads), "uFigSize": size(self.figs), "uSeed": self.seed,
            "uFrame": self.frame, "uPanels": self.panels, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern),
            "uPanelOn0": tuple(self.panel_lvl[0:4]), "uPanelOn1": tuple(self.panel_lvl[4:8]), "uZoneOn": tuple(zone_on),
            "uFlash": self.flash, "uBurstT": (now - self.burst_t0) if now - self.burst_t0 < 3.0 else -1.0, "uAwake": self.awake,
            "uHeadA": float(self.head_prev), "uHeadB": float(self.head), "uHeadMix": mix, "uHeadGlitch": hg, "uHue": self.hue,
            "uSpeakT": (now - self.speak_t0) if speaking else -1.0,
            "uScanT": (now - self.scan_t0) if now - self.scan_t0 < SCAN_SECONDS else -1.0,
            "uFast": 1.0 if (now < self.fast_until or now < self.salvo_until) else 0.0,
            "uGlitch": self.glitch_k, "uZoom": self.zoom,
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]),
            "uPeaks0": tuple(self.band_peak[0:4]), "uPeaks1": tuple(self.band_peak[4:8]),
        }

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        out.append(("O R A K E L", 0.02, 0.5, 0.95, (120, 200, 255), 0.35 + 0.25 * self.awake))
        if now - self.speak_t0 < SPEAK_SECONDS and now >= self.line_t0 and self.line:
            k = now - self.line_t0
            n = min(len(self.line), int(k * 28))
            a = min(1.0, (SPEAK_SECONDS - (now - self.speak_t0)) / 1.0)
            out.append((self.line[:n], 0.026, 0.5, 0.25, (120, 230, 255), 0.9 * a))
        if now - self.burst_t0 < 2.0:
            out.append(("D A T E N E X P L O S I O N", 0.028, 0.5, 0.88, (255, 80, 220), 0.7 * (1.0 - (now - self.burst_t0) / 2.0)))
        name = HEAD_NAMES[self.head] if self.awake > 0.3 else "OFFLINE"
        if now < self.salvo_until:
            name = "SALVE  " + name
        out.append((name, 0.022, 0.5, 0.03, (160, 220, 255), 0.4 + 0.5 * min(1.0, (now - self.head_t0) / 0.3) * self.awake + 0.2 * (1.0 - self.awake)))
        if now < self.fast_until:
            out.append(("AUTOMATIK SCHNELL  %d" % int(self.fast_until - now + 0.99), 0.018, 0.5, 0.84, (255, 200, 120), 0.6 + 0.3 * math.sin(t * 8.0)))
        if now - self.scan_t0 < SCAN_SECONDS:
            out.append(("S C A N", 0.018, 0.1, 0.05, (120, 255, 220), 0.6))
        if self.glitch_k > 0.3:
            out.append(("G L I T C H", 0.02, 0.9, 0.05, (255, 80, 220), 0.5 + 0.4 * math.sin(t * 15.0)))
        return out
