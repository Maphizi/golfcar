"""Das Orakel (Taste 4 im Thema CYBERPUNK, Gegenstück zu HAL 3000 / Auge des Waldes).

Serverhalle (assets/cyber/oracle_scene.png) mit EINEM Hologramm-Kopf im Projektionsrahmen, der 32 Gesten kann
(assets/cyber/oracle_main.png, 8x4 à 256x288, immer dieselbe Figur, gleiche Lage in jeder Zelle; GESTURE_NAMES).
Jedes Musikmerkmal hat sein Element:
  Beat      Tafeln hart an/aus nach Mustern (uPanelOn, uPattern), Serverlichter in Zonen, der Kopf nickt (uWobble.yz)
            und wechselt die Geste (ruhig jeder 4. Beat, mittel jeder 2., wild jeder Beat), Blinzeln alle 3-6 s
  Bass      Kopf atmet/pulst, Hologramm flackert, Serverlichter glühen
  Mitten    Kopf dreht sich leicht (Parallaxe), Datenregen im Hintergrund
  Höhen     Funkenregen im Rahmen, Funken an den Kabeln
  Spektrum  Bandenergie = Füllhöhe/Helligkeit innerhalb einer AN-Tafel (uBands/uPeaks)
  Drop      Datenexplosion, MASKE AUF (assets/cyber/oracle_masks.png 8x2 à 256, MASK_NAMES) für MASK_BEATS Beats, dabei
            wackelt der Kopf heftig im Takt (uWobble.x), Gesten wild; neues Tafelmuster, neuer Farbton
  Stille    der Kopf schläft (Geste SCHLAF) und erlischt zum Drahtgitter-Schemen (uAwake)
Knüppel LINKS/RECHTS/OBEN/UNTEN = der Kopf schaut/dreht/neigt sich dorthin (je Richtung ein Satz Gesten, G_LEFT ...),
Startknopf = das Orakel spricht (Sprechmünder, Spruch wird getippt), Kippschalter AN = ÜBERGEBEN: Würgen -> Mund auf ->
Schwall aus Datenmüll (assets/cyber/oracle_garbage.png 8x2 à 128, Teilchen uGarb0..15 fallen über die Tafeln) -> Wischen;
Kippschalter AUS = Nahaufnahme aus. Von selbst alle 20-40 s ein Ereignis: Datenexplosion, Gesten-Salve, Scanner-Welle,
kurzer Glitch-Modus, Spruch, selten Übergeben; Maske auch ohne Drop, wenn lange keiner kam.
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
HEAD_CW, HEAD_CH = 256, 288
N_GESTURES = 32
GESTURE_NAMES = ["NEUTRAL", "BLICK RECHTS", "BLICK LINKS", "BLICK OBEN", "BLICK UNTEN", "NEIGUNG RECHTS", "NEIGUNG LINKS",
                 "PROFIL LINKS", "PROFIL RECHTS", "KINN HOCH", "LAUERN", "SCHLAF", "ZWINKERN", "BRAUE", "SCHRECK", "LÄCHELN",
                 "GRINSEN", "LACHEN", "ZORN", "SCHREI", "SPRECHEN", "SPRECHEN O", "ZUNGE", "BACKEN",
                 "SCHWINDEL", "GLITCH", "NICKEN", "WÜRGEN", "ÜBERGEBEN", "SCHWALL", "WISCHEN", "BRÜLLEN"]
G_SLEEP, G_WINK, G_NEUTRAL = 11, 12, 0
G_LEFT = (2, 7, 6)                      # Gesichter, die nach links im Bild zeigen
G_RIGHT = (1, 8, 5)
G_UP = (3, 9, 31, 17)
G_DOWN = (4, 10, 26)
IDLE_CALM = (0, 0, 11, 12, 15, 1, 2, 3, 4, 5, 6, 13)
IDLE_MID = IDLE_CALM + (7, 8, 9, 10, 14, 16, 20, 21, 23)
IDLE_WILD = IDLE_MID + (17, 18, 19, 22, 24, 31, 25)
MASK_GESTURES = (24, 19, 25, 31, 18, 14, 17)
SPEAK_CYCLE = (20, 21, 0, 20, 21, 15, 20, 21)
VOMIT_SEQ = ((27, 0.7), (28, 0.5), (29, 2.6), (30, 1.3))     # Geste, Dauer: Würgen, Mund auf, Schwall, Wischen
VOMIT_STREAM = (1.2, 3.8)               # Sekunden ab Start, in denen der Schwall fließt
MANUAL_HOLD = 2.2                       # s, die eine Knüppel-Geste gehalten wird
N_MASKS = 16
MASK_NAMES = ["ONI", "KITSUNE", "GASMASKE", "VR-VISIER", "PORZELLAN", "CHROMSCHÄDEL", "MEMPO", "HOCKEY",
              "PESTDOKTOR", "NEONKATZE", "CLOWN", "GLITCHMASKE", "GOLDENE TOTENMASKE", "GEISHA", "DRAHTGITTER", "SCHWEISSER"]
MASK_BEATS = (8, 16)
MASK_MEMORY = 6
MASK_AUTO_AFTER = 120.0                 # s ohne Drop: Maske kommt auch über die Ereignis-Automatik (bei Energie > 0.4)
MASK_EVERY = (45.0, 90.0)               # eigener Takt: so oft setzt sie sich bei Musik (Energie > 0.2) von selbst eine Maske auf
N_GARB = 16
GARB_GRAVITY = 3.2                      # in Kopf-Einheiten je s²
GARB_FLOOR = -2.9                       # unterhalb (Kopf-Einheiten) verschwinden die Teile
N_PATTERNS = 8          # Lauflicht l->r, r->l, außen->innen, gerade/ungerade, zufällig, alle an jeden 4., Spiegel, Paare
PATTERN_NAMES = ["LAUFLICHT", "RÜCKLAUF", "AUSSEN-INNEN", "WECHSEL", "ZUFALL", "VOLLBILD", "SPIEGEL", "PAARE"]
SPEAK_SECONDS = 6.0
SALVO_SECONDS = 2.0
SCAN_SECONDS = 2.4
AUTO_GLITCH_SECONDS = 4.0
AFTERGLOW = 0.1         # Nachglühen einer aus-Tafel (s)
AUTO_EVENT = (20.0, 40.0)
AUTO_VOMIT_GAP = 90.0   # Übergeben von selbst frühestens alle 90 s
ORACLE_LINES = [
    "DEINE DATEN SIND SCHON VERKAUFT.", "DER REGEN HÖRT NIE AUF. DU GEWÖHNST DICH.", "ICH SEHE 4.096 VERSIONEN VON DIR.",
    "DAS TAXI FÄHRT. DAS TAXAMETER AUCH.", "FRAG NICHT NACH DEM PREIS. FRAG NACH DER WÄHRUNG.", "DU BIST OFFLINE. ICH NICHT.",
    "DIE STADT TRÄUMT IN NEON. DU BIST EIN PIXEL.", "DEIN HANDICAP IST DEM KONZERN BEKANNT.", "NOCH EIN UPDATE. DANN BIST DU FREI.",
    "DIE KATZE WEISS MEHR ALS DU.", "VERTRAU KEINEM HOLOGRAMM. AUCH MIR NICHT.", "LOCH 19 LIEGT IM SEKTOR 7.",
    "ICH HABE 32 GESICHTER. KEINES IST MEINS.", "DER SAMURAI WARTET SEIT 1999 AUF EIN UPDATE.", "MIR IST SCHLECHT. ZU VIELE PAKETE.",
]


def _panel_colors(figs) -> list:
    """Leuchtfarbe der acht Tafel-Glyphen (Atlas-Reihe 2, Zellen 16-23; im geladenen Bild unten wie im Shader): Mittel der
    hellsten Pixel, satt und voll ausgesteuert. Ohne Bild ein Regenbogen."""
    fallback = [[255, 30, 20], [255, 120, 0], [255, 220, 0], [40, 255, 30], [0, 230, 255], [20, 60, 255], [150, 30, 255], [255, 20, 160]]
    if figs is None:
        return fallback
    try:
        h, w = figs.shape[:2]
        cw = w // 8
        out = []
        for i in range(8):
            cell = figs[0:cw, i * cw:(i + 1) * cw].astype(float)
            al = cell[..., 3] / 255.0
            lum = cell[..., :3].max(axis=2) * al
            sel = lum >= np.quantile(lum[al > 0.3], 0.8) if (al > 0.3).any() else al > 0
            rgb = cell[..., :3][sel].mean(axis=0)
            mx, mn = rgb.max(), rgb.min()
            rgb = np.clip((rgb - mn) / max(1.0, mx - mn), 0, 1) * 255.0       # satt: Grauanteil ganz raus (LEDs mischen sonst Weiß)
            out.append([int(v) for v in rgb])
        return out
    except Exception:
        return fallback


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


class Garbage:
    """Ein Datenmüll-Teil aus dem Mund: Lage/Geschwindigkeit in Kopf-Einheiten (d-Raum des Shaders, y nach oben)."""
    __slots__ = ("x", "y", "vx", "vy", "cell", "rot", "spin", "age", "alive")

    def __init__(self, rng: random.Random, mouth: tuple[float, float]):
        self.x, self.y = mouth[0] + rng.uniform(-0.04, 0.04), mouth[1] + rng.uniform(-0.03, 0.03)
        self.vx = rng.uniform(-0.9, 0.9) + rng.choice((-0.3, 0.3))
        self.vy = rng.uniform(-1.4, -0.2)
        self.cell = rng.randrange(16)
        self.rot = rng.uniform(0.0, 6.28)
        self.spin = rng.uniform(-6.0, 6.0)
        self.age = 0.0
        self.alive = True


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "oracle_scene.png")
        self.heads = _load_rgba(ASSETS / "oracle_main.png")
        self.masks = _load_rgba(ASSETS / "oracle_masks.png")
        self.garb_tex = _load_rgba(ASSETS / "oracle_garbage.png")
        self.figs = _load_rgba(ASSETS / "oracle_figures.png")
        self.panel_cols = _panel_colors(self.figs)                 # Farbe der acht Tafeln (Glyphen 16-23) für das LED-Board
        self.frame = tuple(float(v) for v in scene_cfg.get("frame", [0.505, 0.73, 0.27]))      # x, y, Breite
        self.panels = tuple(float(v) for v in scene_cfg.get("panels", [0.264, 0.757, 0.385, 0.052]))   # x0, x7, y, Breite
        self.mask_fit = tuple(float(v) for v in scene_cfg.get("mask_fit", [0.0, 0.08, 0.62]))  # dx, dy, Größe (Kopf-Einheiten)
        self.mouth = tuple(float(v) for v in scene_cfg.get("mouth", [-0.05, -0.36]))           # Mund (Kopf-Einheiten)
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
        # Kopf / Gesten
        self.pose = G_NEUTRAL
        self.pose_prev = G_NEUTRAL
        self.pose_t0 = -10.0
        self.pose_len = 0.15                           # Dauer der Überblendung
        self.pose_glitch = 0.1                         # Stärke des Glitch-Übergangs 0..1
        self.pose_beats = 0                            # Beats seit dem letzten Wechsel
        self.manual_until = -1.0                       # bis hierhin hält die Knüppel-Geste
        self.manual_set: tuple[int, ...] = ()
        self.manual_i = 0
        self.next_blink = now + 3.0
        self.blink_back_at = -1.0
        self.blink_from = G_NEUTRAL
        self.hue = 0.0
        self.hue_target = 0.0
        self.awake = 0.0
        self.bob = 0.0
        self.speak_t0 = -100.0
        self.line = ""
        self.line_t0 = -10.0
        # Maske
        self.mask = -1
        self.mask_k = 0.0
        self.mask_t0 = -100.0
        self.mask_off_beat = -1
        self.mask_recent: list[int] = []
        self.mask_next = now + self.rng.uniform(*MASK_EVERY) * (0.3 if demo else 1.0)
        self.wobble = 0.0
        # Übergeben
        self.vomit_t0 = -100.0
        self.last_vomit = -100.0
        self.garbage: list[Garbage] = []
        self.garb_acc = 0.0
        # Automatik
        self.salvo_until = -1.0
        self.salvo_next = 0.0
        self.scan_t0 = -100.0
        self.auto_glitch_until = -1.0
        self.auto_next = now + self.rng.uniform(*self.auto_event)
        self.last_key = -100.0
        # Glitch-Modus / Zoom
        self.glitch_mode = False
        self.glitch_k = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = now + 4.0
        self.demo_drop_next = now + 9.0
        log.info("Das Orakel: Szene %s, Gesten %s, Masken %s, Datenmüll %s, Glyphen %s",
                 *("ok" if a is not None else "fehlt" for a in (self.scene, self.heads, self.masks, self.garb_tex, self.figs)))

    # -- Gesten ------------------------------------------------------------
    def set_pose(self, idx: int, glitch: float = 0.1, length: float = 0.15) -> None:
        """Neue Geste einblenden; glitch = Stärke der Glitch-Zwischenphase (Drop/Maske = 1.0)."""
        idx %= N_GESTURES
        if idx == self.pose:
            return
        now = time.monotonic()
        self.pose_prev = self.pose
        self.pose = idx
        self.pose_t0 = now
        self.pose_len = length
        self.pose_glitch = glitch
        self.pose_beats = 0

    def _busy(self, now: float) -> bool:
        """Übergeben oder Sprechen laufen: die Automatik lässt die Geste in Ruhe."""
        return now - self.vomit_t0 < sum(d for _, d in VOMIT_SEQ) or now - self.speak_t0 < SPEAK_SECONDS

    def gesture_dir(self, gset: tuple[int, ...], name: str) -> None:
        """Knüppel: Geste aus dem Richtungssatz, bei wiederholtem Druck die nächste; hält MANUAL_HOLD Sekunden."""
        now = time.monotonic()
        self.last_key = now
        if now - self.vomit_t0 < sum(d for _, d in VOMIT_SEQ):
            return
        if self.manual_set == gset and now < self.manual_until:
            self.manual_i = (self.manual_i + 1) % len(gset)
        else:
            self.manual_set = gset
            self.manual_i = 0
        self.manual_until = now + MANUAL_HOLD
        self.set_pose(gset[self.manual_i], glitch=0.25, length=0.14)
        self.bob = 1.0
        log.info("Geste %s: %s", name, GESTURE_NAMES[self.pose])

    def _idle_pool(self) -> tuple[int, ...]:
        if self.mask >= 0:
            return MASK_GESTURES
        if self.energy > 0.45:
            return IDLE_WILD
        if self.energy > 0.2:
            return IDLE_MID
        return IDLE_CALM

    def random_pose(self, glitch: float = 0.1, length: float = 0.15) -> None:
        pool = [g for g in self._idle_pool() if g != self.pose]
        self.set_pose(self.rng.choice(pool), glitch, length)

    def salvo(self) -> None:
        now = time.monotonic()
        self.salvo_until = now + SALVO_SECONDS
        self.salvo_next = now
        log.info("Gesten-Salve")

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
        self.glitch_mode = not self.glitch_mode
        self.auto_glitch_until = -1.0
        log.info("Glitch-Modus %s", "an" if self.glitch_mode else "aus")

    def speak(self) -> None:
        now = time.monotonic()
        if now - self.speak_t0 < SPEAK_SECONDS or now - self.vomit_t0 < sum(d for _, d in VOMIT_SEQ):
            return
        self.speak_t0 = now
        self.line = self.rng.choice(ORACLE_LINES)
        self.line_t0 = now + 0.4
        self._led_event("oracle_speak", now + SPEAK_SECONDS)
        log.info("Orakel: %s", self.line)

    # -- Maske / Übergeben -------------------------------------------------
    def mask_on(self, now: float, reason: str) -> None:
        if self.masks is None:
            return
        pool = [i for i in range(N_MASKS) if i not in self.mask_recent]
        self.mask = self.rng.choice(pool or list(range(N_MASKS)))
        self.mask_recent.append(self.mask)
        del self.mask_recent[:-MASK_MEMORY]
        self.mask_t0 = now
        self.mask_off_beat = self.beat_count + self.rng.randint(*MASK_BEATS)
        self.wobble = 1.0
        self.set_pose(self.rng.choice(MASK_GESTURES), glitch=1.0, length=0.5)
        self._led_event("oracle_mask", now + 4.0)
        log.info("Maske auf (%s): %s für %d Beats", reason, MASK_NAMES[self.mask], self.mask_off_beat - self.beat_count)

    def mask_off(self) -> None:
        if self.mask < 0:
            return
        log.info("Maske ab: %s", MASK_NAMES[self.mask])
        self.mask = -1
        self.mask_off_beat = -1
        self.set_pose(self.rng.choice((0, 30, 24, 15)), glitch=0.6, length=0.3)

    def vomit(self) -> None:
        now = time.monotonic()
        if now - self.vomit_t0 < sum(d for _, d in VOMIT_SEQ) + 1.0:
            return
        self.vomit_t0 = now
        self.last_vomit = now
        self.garbage = []
        self.garb_acc = 0.0
        if self.mask >= 0:
            self.mask_off()
        self.set_pose(VOMIT_SEQ[0][0], glitch=0.2, length=0.2)
        self._led_event("oracle_vomit", now + sum(d for _, d in VOMIT_SEQ))
        log.info("Übergeben: Datenmüll")

    def _vomit_tick(self, now: float, dt: float) -> None:
        k = now - self.vomit_t0
        total = sum(d for _, d in VOMIT_SEQ)
        if k < total:
            acc = 0.0
            for g, d in VOMIT_SEQ:
                acc += d
                if k < acc:
                    if self.pose != g and now - self.pose_t0 > 0.1:
                        self.set_pose(g, glitch=0.15, length=0.18)
                    break
            if VOMIT_STREAM[0] <= k < VOMIT_STREAM[1]:
                self.garb_acc += dt * (10.0 + 10.0 * self.energy)
                while self.garb_acc >= 1.0 and len(self.garbage) < N_GARB:
                    self.garb_acc -= 1.0
                    self.garbage.append(Garbage(self.rng, self.mouth))
                self.garb_acc = min(self.garb_acc, 1.0)
        for p in self.garbage:
            p.age += dt
            p.vy -= GARB_GRAVITY * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.spin * dt
            if p.y < GARB_FLOOR:
                p.alive = False
        self.garbage = [p for p in self.garbage if p.alive]

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
        self.hue_target = self.rng.choice((0.6, -0.6, 1.2, -1.2, 2.4, 3.6))
        if now - self.vomit_t0 >= sum(d for _, d in VOMIT_SEQ):
            self.mask_on(now, "Drop")
            self.mask_next = now + self.rng.uniform(*MASK_EVERY)
        else:
            self.set_pose(19, glitch=1.0, length=0.5)
        log.info("Drop: Datenexplosion, Muster %s", PATTERN_NAMES[self.pattern])

    def _beat(self, now: float) -> None:
        """Ein Beat: Tafelmuster weiterschalten, Kopf nickt, Geste nach Zählung wechseln, Maske wackelt / fällt ab."""
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
        self.pose_beats += 1
        self.bob = max(self.bob, 0.6 + 0.4 * self.bass_s)
        if self.mask >= 0:
            self.wobble = 1.0
            if self.beat_count >= self.mask_off_beat:
                self.mask_off()
                return
        if now < self.salvo_until or now < self.manual_until or self._busy(now):
            return
        if self.mask >= 0:
            period = 1 if self.energy > 0.3 else 2
        else:
            period = 1 if self.energy > 0.55 else (2 if self.energy > 0.3 else 4)
        if self.pose_beats >= period and now - self.pose_t0 > 0.25:
            self.random_pose(0.1 if self.mask < 0 else 0.4, 0.15)

    def _auto_event(self, now: float) -> None:
        pick = self.rng.choice(("burst", "salvo", "scan", "scan", "glitch", "speak", "salvo", "vomit", "mask"))
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
        elif pick == "vomit":
            if self.energy > 0.3 and now - self.last_vomit > AUTO_VOMIT_GAP:
                self.vomit()
            else:
                self.salvo()
        elif pick == "mask":
            if self.mask < 0 and self.energy > 0.4 and now - self.last_drop > MASK_AUTO_AFTER:
                self.mask_on(now, "von selbst")
            else:
                self.scan()
        else:
            self.speak()

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.gesture_dir(G_LEFT, "links")
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.gesture_dir(G_RIGHT, "rechts")
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.gesture_dir(G_UP, "oben")
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.gesture_dir(G_DOWN, "unten")
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.last_key = time.monotonic()
            self.speak()
        elif ev.key == pygame.K_SPACE:
            self.last_key = time.monotonic()
            self.vomit()
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0
        elif ev.key == pygame.K_g:
            self.toggle_glitch()

    # -- Engine ------------------------------------------------------------
    def led_state(self) -> dict:
        """LED-Board: Programm "panels", je LED eine Tafelfarbe im Wechsel, hell, solange die Tafel an ist."""
        return {"program": "panels", "cols": self.panel_cols, "lvl": list(self.panel_lvl)}

    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uHeadTex": (self.heads if self.heads is not None else self.blank, 1),
                "uMaskTex": (self.masks if self.masks is not None else self.blank, 1),
                "uGarbTex": (self.garb_tex if self.garb_tex is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uHeadTex", "uMaskTex", "uGarbTex", "uFigTex", "uSceneSize", "uHeadSize", "uMaskSize", "uGarbSize",
                 "uFigSize", "uSeed", "uFrame", "uPanels", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse",
                 "uBeatStep", "uStep", "uStepPhase", "uPattern", "uPanelOn0", "uPanelOn1", "uZoneOn", "uFlash", "uBurstT",
                 "uAwake", "uHeadA", "uHeadB", "uHeadMix", "uHeadGlitch", "uHue", "uSpeakT", "uScanT", "uFast", "uGlitch",
                 "uZoom", "uBands0", "uBands1", "uPeaks0", "uPeaks1", "uMaskP", "uMaskFit", "uWobble", "uMouth", "uVomitT",
                 "uNGarb"]
        names += [f"uGarb{i}" for i in range(N_GARB)]
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
        # Beat: echter Beat, sonst (Musik ohne erkannten Beat) ein weicher Takt alle 1.4 s, bei Stille nichts
        on_beat = beat > 0.5 and now - self.last_beat > 0.25
        if not on_beat and live and self.energy > 0.08 and now - self.last_beat > 1.4:
            on_beat = True
        if on_beat:
            self._beat(now)
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        self.bob = max(0.0, self.bob - dt / 0.35)
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
        # Kopf: wach mit Musik (Stille = Schlaf), Salve, Blinzeln, Sprechmünder, Farbton gleitet
        awake_target = 1.0 if self.live_s > 0.3 else 0.0
        self.awake += (awake_target - self.awake) * min(1.0, dt / (0.8 if awake_target else 3.0))
        busy = self._busy(now)
        if awake_target == 0.0 and self.pose != G_SLEEP and not busy:
            self.set_pose(G_SLEEP, glitch=0.2, length=0.6)
        if now < self.salvo_until and now >= self.salvo_next and not busy:
            self.salvo_next = now + SALVO_SECONDS / 6.0
            self.random_pose(0.5, 0.12)
        speaking = now - self.speak_t0 < SPEAK_SECONDS
        if speaking:
            k = now - self.speak_t0
            want = SPEAK_CYCLE[int(k * 7.0) % len(SPEAK_CYCLE)] if k < SPEAK_SECONDS - 0.8 else 15
            if want != self.pose and now - self.pose_t0 > 0.08:
                self.set_pose(want, glitch=0.05, length=0.08)
        elif awake_target and not busy and now >= self.next_blink and now >= self.manual_until and self.mask < 0:
            self.next_blink = now + self.rng.uniform(3.0, 6.0)
            if self.pose not in (G_SLEEP, G_WINK, 24, 25):
                self.blink_from = self.pose
                self.blink_back_at = now + 0.14
                self.set_pose(G_SLEEP if self.rng.random() < 0.7 else G_WINK, glitch=0.0, length=0.06)
        if self.blink_back_at > 0 and now >= self.blink_back_at:
            self.blink_back_at = -1.0
            if self.pose in (G_SLEEP, G_WINK) and awake_target:
                self.set_pose(self.blink_from, glitch=0.0, length=0.06)
        if now - self.vomit_t0 < sum(d for _, d in VOMIT_SEQ) + 6.0:
            self._vomit_tick(now, dt)
        if self.mask >= 0 and not live and now - self.mask_t0 > 4.0:
            self.mask_off()
        if now >= self.mask_next:                                         # Maske im eigenen Takt, nicht nur beim Drop
            self.mask_next = now + self.rng.uniform(*MASK_EVERY) * (0.3 if self.demo else 1.0)
            if self.mask < 0 and live and self.energy > 0.2 and not self._busy(now):
                self.mask_on(now, "Takt")
        self.mask_k += ((1.0 if self.mask >= 0 else 0.0) - self.mask_k) * min(1.0, dt / 0.22)
        self.wobble = max(0.0, self.wobble - dt / 0.5) if self.mask >= 0 else max(0.0, self.wobble - dt / 0.25)
        self.hue += (self.hue_target - self.hue) * min(1.0, dt / 1.5)
        # Automatik: Ereignis von selbst, wenn 6 s keine Taste
        if now >= self.auto_next:
            self.auto_next = now + self.rng.uniform(*self.auto_event)
            if now - self.last_key > 6.0 and live:
                self._auto_event(now)
        glitch_on = self.glitch_mode or now < self.auto_glitch_until
        self.glitch_k += ((1.0 if glitch_on else 0.0) - self.glitch_k) * min(1.0, dt / 0.6)
        zoom_target = max(self.zoom_target, 0.35 * self.mask_k)
        self.zoom += (zoom_target - self.zoom) * min(1.0, dt / 1.8)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("oracle")
        if self.demo:
            if now >= self.demo_next:
                self.demo_next = now + 7.0
                self.rng.choice((self.burst, self.salvo, self.scan, self.speak, self.vomit, lambda: self.gesture_dir(G_LEFT, "links"),
                                 lambda: self.gesture_dir(G_UP, "oben")))()
                self.last_key = -100.0
            if now >= self.demo_drop_next:
                self.demo_drop_next = now + 14.0
                self._drop(now)
        # Übergang der Geste: Mischung 0..1, Glitch-Anteil als Buckel in der Mitte (+ Puls beim Sprechen)
        mix = min(1.0, (now - self.pose_t0) / max(0.05, self.pose_len))
        hg = self.pose_glitch * math.sin(mix * math.pi)
        if speaking:
            hg = max(hg, 0.15 * abs(math.sin((now - self.speak_t0) * 14.0)))
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        zone_on = [1.0 if (self.panel_lvl[2 * z] > 0.5 or self.panel_lvl[2 * z + 1] > 0.5) else 0.0 for z in range(4)]
        vk = now - self.vomit_t0
        out = {
            "uSceneSize": size(self.scene), "uHeadSize": size(self.heads), "uMaskSize": size(self.masks), "uGarbSize": size(self.garb_tex),
            "uFigSize": size(self.figs), "uSeed": self.seed,
            "uFrame": self.frame, "uPanels": self.panels, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.6), "uPattern": float(self.pattern),
            "uPanelOn0": tuple(self.panel_lvl[0:4]), "uPanelOn1": tuple(self.panel_lvl[4:8]), "uZoneOn": tuple(zone_on),
            "uFlash": self.flash, "uBurstT": (now - self.burst_t0) if now - self.burst_t0 < 3.0 else -1.0, "uAwake": self.awake,
            "uHeadA": float(self.pose_prev), "uHeadB": float(self.pose), "uHeadMix": mix, "uHeadGlitch": hg, "uHue": self.hue,
            "uSpeakT": (now - self.speak_t0) if speaking else -1.0,
            "uScanT": (now - self.scan_t0) if now - self.scan_t0 < SCAN_SECONDS else -1.0,
            "uFast": 1.0 if now < self.salvo_until else 0.0,
            "uGlitch": self.glitch_k, "uZoom": self.zoom,
            "uBands0": tuple(self.bands[0:4]), "uBands1": tuple(self.bands[4:8]),
            "uPeaks0": tuple(self.band_peak[0:4]), "uPeaks1": tuple(self.band_peak[4:8]),
            "uMaskP": (float(self.mask if self.mask >= 0 else self.mask_recent[-1] if self.mask_recent else 0), self.mask_k,
                       min(9.0, now - self.mask_t0), 0.0),
            "uMaskFit": self.mask_fit, "uWobble": (self.wobble, self.bob, self.beat_pulse), "uMouth": self.mouth,
            "uVomitT": (vk - VOMIT_STREAM[0]) if VOMIT_STREAM[0] <= vk < VOMIT_STREAM[1] + 0.6 else -1.0,
            "uNGarb": float(len(self.garbage)),
        }
        for i in range(N_GARB):
            if i < len(self.garbage):
                p = self.garbage[i]
                out[f"uGarb{i}"] = (p.x, p.y, float(p.cell), p.rot)
            else:
                out[f"uGarb{i}"] = (0.0, -99.0, 0.0, 0.0)
        return out

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
        if self.mask >= 0:
            out.append(("MASKE: " + MASK_NAMES[self.mask], 0.022, 0.14, 0.9, (255, 120, 200), 0.6 + 0.3 * self.beat_pulse))
        vk = now - self.vomit_t0
        if vk < sum(d for _, d in VOMIT_SEQ):
            out.append(("D A T E N M Ü L L", 0.026, 0.5, 0.84, (120, 255, 160), 0.5 + 0.4 * abs(math.sin(t * 9.0))))
        name = GESTURE_NAMES[self.pose] if self.awake > 0.3 else "OFFLINE"
        if now < self.salvo_until:
            name = "SALVE  " + name
        elif now < self.manual_until:
            name = "MANUELL  " + name
        out.append((name, 0.022, 0.5, 0.03, (160, 220, 255), 0.4 + 0.5 * min(1.0, (now - self.pose_t0) / 0.3) * self.awake + 0.2 * (1.0 - self.awake)))
        if now - self.scan_t0 < SCAN_SECONDS:
            out.append(("S C A N", 0.018, 0.1, 0.05, (120, 255, 220), 0.6))
        if self.glitch_k > 0.3:
            out.append(("G L I T C H", 0.02, 0.9, 0.05, (255, 80, 220), 0.5 + 0.4 * math.sin(t * 15.0)))
        return out
