"""Slotmaschinen (Taste 5): Szenen-Controller der GL-Engine, Basis für alle Themen.

Vollbild-Walzen (Nahaufnahme, Traum-Unschärfe beim Drehen), die sich die Bildbreite teilen; je Automat 3, 4 oder 5
Walzen ("reels" im Automaten-Dict, slots_themes.py). Drei Automaten je Thema, Knüppel links/rechts wechselt
(ST_THEME-Überblendung), oben/unten = Einsatz (STAKES), ENTER / Leertaste = drehen. Spielt sonst von selbst: Walzen
drehen, bleiben einzeln, paarweise oder alle zugleich stehen, manchmal dreht eine noch einmal nach.
Gewinne: 3 Walzen = zwei gleiche klein, drei gleiche groß, Jackpot-Symbol dreifach = Jackpot, alle 9 = Mega;
5 Walzen = drei gleiche nebeneinander klein, vier gleiche groß; 4 Walzen = drei gleiche mit Lücke klein, drei nebeneinander groß;
4/5 Walzen alle gleich = Jackpot, Jackpot-Symbol auf allen = Mega (_evaluate).
Themenrahmen (assets/slots/<thema>_frame.png, Mitte Schwarz = Walzen sichtbar, Luma-Key; KITT_SLOTS_FRAME=<pfad> zum
Testen) liegt über den Walzen: seine hellen gesättigten Stellen pulsen zum Bass, Lauflicht über Stege und Rahmen auf
den Beat (uStep/uStepPhase/uPattern), Höhen funkeln, Drop = uFlash + nächste Drehung schneller, Stille dimmt alles.
Themen-Controller (forestslots, cyberslots, almanacslots) sind dünne Unterklassen: THEMES, LED, STAKES, FRAME, FIGURES,
STYLE (Shader-Variante uStyle 0 Space, 1 Natur, 2 Cyber, 3 Zukunft). Der Shader visualizers/shaders/slots zeichnet nur.
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
import pygame.image

from launcher import config as lcfg, wled
from visualizers.scenes import slots_themes as art

log = logging.getLogger("slots")

STRIP_LEN = 32          # Symbole pro Walze
MAX_REELS = art.MAX_REELS
TW, TH = art.TILE_W, art.TILE_H         # Kachelgröße der Bildbögen
N_SYM = art.SHEET_COLS * art.SHEET_ROWS
ATLAS_W = N_SYM * TW                    # 9 Symbole eines Automaten nebeneinander
FRAME_SIZE = (1280, 720)                # Rahmenbild wird auf diese Größe gebracht (ein Sampler, Pi 5)

ST_IDLE, ST_SPIN, ST_RESULT, ST_THEME = 0, 1, 2, 3
WIN_NONE, WIN_SMALL, WIN_BIG, WIN_JACKPOT, WIN_MEGA = 0, 1, 2, 3, 4
WIN_NAMES = {WIN_NONE: "Niete", WIN_SMALL: "kleiner Gewinn", WIN_BIG: "Gewinn", WIN_JACKPOT: "JACKPOT", WIN_MEGA: "MEGA"}
LINE_CENTER, LINE_UP, LINE_DOWN, LINE_MEGA = 0, 1, 2, 3     # Gewinnlinie: Mitte, steigend, fallend, alles
PAYOUT = {WIN_SMALL: 25, WIN_BIG: 150, WIN_JACKPOT: 1000, WIN_MEGA: 10000}
HOLD = {WIN_NONE: 1.1, WIN_SMALL: 3.0, WIN_BIG: 5.0, WIN_JACKPOT: 8.0, WIN_MEGA: 9.0}
MEGA_MSGS = ["MEGA JACKPOT!!!", "ALLES GLEICH!", "UNMÖGLICH!", "DAS UNIVERSUM BEBT!", "WAHNSINN!!!"]
N_PATTERNS = 4

WHITE = (245, 245, 250)
GOLD = (255, 220, 80)


def _sheet_tiles(path, keyed: bool) -> np.ndarray | None:
    """Bildbogen (3x3) als Zeile von 9 Kacheln (TH x 9*TW x 4), aus dem Bild-Cache (npz, Schlüssel Bogen + keyed);
    None bei Fehler. keyed: Schwarz im Bogen wird durchsichtig (Alpha aus der Helligkeit), sonst volles Etikett."""
    out = images.derived("slots_tiles", path, f"{TW}x{TH}|{int(keyed)}", lambda: {"row": _sheet_tiles_decode(path, keyed)})
    row = out.get("row")
    return None if row is None or row.ndim != 3 else row


def _sheet_tiles_decode(path, keyed: bool) -> np.ndarray:
    try:
        surf = pygame.image.load(str(path))
        if surf.get_size() != (TW * art.SHEET_COLS, TH * art.SHEET_ROWS):
            surf = pygame.transform.smoothscale(surf, (TW * art.SHEET_COLS, TH * art.SHEET_ROWS))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)        # (H, W, 3)
    except Exception as exc:
        log.warning("Bildbogen %s nicht ladbar: %s", path, exc)
        return np.zeros(0, dtype=np.uint8)
    row = np.zeros((TH, N_SYM * TW, 4), dtype=np.uint8)
    for ry in range(art.SHEET_ROWS):
        for rx in range(art.SHEET_COLS):
            k = ry * art.SHEET_COLS + rx
            tile = rgb[ry * TH:(ry + 1) * TH, rx * TW:(rx + 1) * TW][::-1]    # GL: Zeile 0 unten
            row[:, k * TW:(k + 1) * TW, :3] = tile
            if keyed:
                lum = tile.max(axis=2).astype(np.float32)
                row[:, k * TW:(k + 1) * TW, 3] = np.clip((lum - 14.0) / 40.0, 0.0, 1.0) * 255
            else:
                row[:, k * TW:(k + 1) * TW, 3] = 255
    return row


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


def load_frame(path) -> np.ndarray | None:
    """Themenrahmen (RGBA, aus dem Bild-Cache): auf FRAME_SIZE skaliert, Alpha per Luma-Key (reines Schwarz = Walzen
    sichtbar, weicher Rand). PNG-Dekodierung und Luma-Key von 1920x1080 kosten auf dem Pi sonst je Start ~2 s."""
    out = images.derived("slots_frame", path, f"{FRAME_SIZE[0]}x{FRAME_SIZE[1]}", lambda: {"rgba": _load_frame_decode(path)})
    rgba = out.get("rgba")
    return None if rgba is None or rgba.ndim != 3 else rgba


def _load_frame_decode(path) -> np.ndarray:
    try:
        surf = pygame.image.load(str(path))
        if surf.get_size() != FRAME_SIZE:
            surf = pygame.transform.smoothscale(surf, FRAME_SIZE)
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)[::-1]
    except Exception as exc:
        log.warning("Rahmen %s nicht ladbar: %s", path, exc)
        return np.zeros(0, dtype=np.uint8)
    lum = rgb.max(axis=2).astype(np.float32)
    alpha = np.clip((lum - 10.0) / 26.0, 0.0, 1.0)
    # weicher Rand: Alpha leicht glätten (3x3), damit die Kante nicht pixelig über den Walzen liegt
    pad = np.pad(alpha, 1, mode="edge")
    alpha = sum(pad[dy:dy + alpha.shape[0], dx:dx + alpha.shape[1]] for dy in range(3) for dx in range(3)) / 9.0
    out = np.zeros((rgb.shape[0], rgb.shape[1], 4), dtype=np.uint8)
    out[:, :, :3] = rgb
    out[:, :, 3] = (alpha * 255).astype(np.uint8)
    return np.ascontiguousarray(out)


def build_strip(theme: int, reel: int, themes=art.THEMES, seed_base: int = 1000) -> list[int]:
    """Feste Symbolfolge je Thema und Walze: Jackpot-Symbol selten, der Rest gleichmäßig gemischt."""
    rng = random.Random(seed_base + theme * 10 + reel)
    n_sym = len(themes[theme]["symbols"])
    pool = []
    for s in range(n_sym - 1):
        pool += [s] * 3
    pool += [n_sym - 1] * 2
    pool = pool[:STRIP_LEN]
    while len(pool) < STRIP_LEN:
        pool.append(rng.randrange(n_sym - 1))
    rng.shuffle(pool)
    # keine zwei gleichen direkt hintereinander (sieht beim Stehenbleiben besser aus)
    for i in range(1, STRIP_LEN):
        if pool[i] == pool[i - 1]:
            for j in range(i + 1, STRIP_LEN):
                if pool[j] != pool[i] and pool[j] != pool[(i + 1) % STRIP_LEN]:
                    pool[i], pool[j] = pool[j], pool[i]
                    break
    return pool


def ease_back(u: float, s: float = 0.9) -> float:
    """Ease-out mit Überschwingen (die Walze rastet mit kleinem Rückprall ein)."""
    u = min(max(u, 0.0), 1.0) - 1.0
    return 1.0 + u * u * ((s + 1.0) * u + s)


class Reel:
    def __init__(self) -> None:
        self.pos = 0.0          # Position in Symbolen (ganzzahlig = Symbol auf der Gewinnlinie)
        self.speed = 0.0        # Symbole pro Sekunde
        self.spinning = False
        self.stop_at = 0.0      # Zeitpunkt, an dem das Einrasten beginnt
        self.target = 0
        self.decel = 1.2
        self.start_pos = 0.0
        self.dist = 0.0
        self.stopping_since = -1.0
        self.max_speed = 10.0
        self.start_t = 0.0

    def start(self, now: float, stop_at: float, target: int, max_speed: float) -> None:
        self.spinning = True
        self.stop_at = stop_at
        self.target = target
        self.max_speed = max_speed
        self.stopping_since = -1.0
        self.start_t = now

    def update(self, now: float, dt: float) -> None:
        if not self.spinning:
            self.speed = 0.0
            return
        if self.stopping_since < 0.0:
            ramp = min(1.0, (now - self.start_t) / 0.45)
            ramp = ramp * ramp * (3.0 - 2.0 * ramp)
            self.speed = self.max_speed * ramp
            self.pos += self.speed * dt
            if now >= self.stop_at:
                self.stopping_since = now
                self.start_pos = self.pos
                # Restweg bis zum Ziel plus ein bis zwei ganze Umdrehungen
                frac = (self.target - self.pos) % STRIP_LEN
                self.dist = frac + STRIP_LEN * random.choice((0, 1))
                self.decel = max(0.9, self.dist / self.max_speed * 1.5)
        else:
            u = (now - self.stopping_since) / self.decel
            self.pos = self.start_pos + self.dist * ease_back(u)
            self.speed = self.max_speed * max(0.0, 1.0 - u) ** 2
            if u >= 1.0:
                self.pos = float(self.target)
                self.speed = 0.0
                self.spinning = False


class Controller:
    # Unterklassen (Themen) überschreiben nur diese Klassenwerte
    THEMES = art.THEMES
    LED = ("slots", "slots_win", "slots_jackpot")      # WLED-Profile: Modus, großer Gewinn, Jackpot
    STAKES = [("KADETT", 10, 1), ("PILOT", 50, 5), ("ADMIRAL", 200, 20)]   # Name, Einsatz, Gewinnfaktor
    CURRENCY = "CR"
    FRAME = "space_frame.png"                          # assets/slots/, optional
    FIGURES: Path | None = None                        # Figuren-Atlas (Zellen 192 px) für Gewinn-Overlays
    FIG_CELLS = (0, 1)                                 # erste Zelle, Anzahl Posen (wechseln auf den Beat)
    STYLE = 0                                          # Shader-Variante uStyle: 0 Space, 1 Natur, 2 Cyber, 3 Zukunft
    COUNTER = "slots_theme.txt"                        # logs/: jedes Einschalten der nächste Automat
    SEED_BASE = 1000
    TITLE_COLOR, SUBTITLE_COLOR, INFO_COLOR = GOLD, (255, 240, 200), (190, 190, 200)
    SEPIA_ON_JACKPOT = False
    LOG = "slots"

    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.cfg = scene_cfg
        self.themes = self.THEMES
        self.led = self.LED
        self.stakes = self.STAKES
        self.stake = 0
        self.stake_t0 = -10.0
        self.bet, self.payout_mult = self.stakes[0][1], self.stakes[0][2]
        self.strip_row = len(self.themes) * TH            # erste Streifenzeile im Atlas
        self.atlas_h = self.strip_row + MAX_REELS
        self.theme = self._pick_theme()
        self.n_reels = self._reels_of(self.theme)
        self.reels = [Reel() for _ in range(MAX_REELS)]
        self.strips = [[0] * STRIP_LEN for _ in range(MAX_REELS)]
        self._build_strips()
        for r in self.reels:
            r.pos = float(self.rng.randrange(STRIP_LEN))
            r.target = int(r.pos)
        self.atlas = self._build_atlas()
        self.atlas_version = 0
        self._write_strips()
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.frame = self._load_frame()
        self.figs = _load_rgba(self.FIGURES) if self.FIGURES and Path(self.FIGURES).exists() else None
        if self.FIGURES and self.figs is None:
            log.info("Figurenbogen %s fehlt: Gewinn-Figuren bleiben leer", self.FIGURES)
        self.area = self._area()
        self.state = ST_IDLE
        self.state_t0 = time.monotonic()
        self.last = self.state_t0
        self.idle_len = 1.5
        self.win = WIN_NONE
        self.win_mask = 0
        self.win_line = LINE_CENTER
        self.message = ""
        self.message_color = WHITE
        self.credits = 1337
        self.spins = 0
        self.next_theme = self.theme
        self.blur = [0.0] * MAX_REELS   # je Walze: 0 scharf, 1 verschwommen; folgt der Drehzahl
        self.respin_pending = False
        self.respin_reel = -1
        self.result_logged = False
        # Musik
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last_f = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        self.step = 0                       # Beat-Zähler: Lauflicht über Stege und Rahmen
        self.step_t0 = 0.0
        self.pattern = self.rng.randrange(N_PATTERNS)
        self.pattern_t0 = time.monotonic()
        self.pattern_len = self.rng.uniform(25.0, 45.0)
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.drop_t0 = -100.0
        self.flash = 0.0
        self.drop_boost = 0.0
        self.stop_t0 = [-10.0] * MAX_REELS  # wann jede Walze zuletzt stehen blieb
        self.was_spinning = [False] * MAX_REELS
        self.fig_pose = 0
        self.fig_prev = 0
        self.fig_t0 = 0.0
        self.sepia = 0.0
        log.info("%s: Automat %s (%d Walzen), Rahmen %s, Figuren %s", self.LOG, self.themes[self.theme]["name"],
                 self.n_reels, "ok" if self.frame is not None else "fehlt (Blende)", "ok" if self.figs is not None else "keine")

    # -- Aufbau ----------------------------------------------------------
    def _pick_theme(self) -> int:
        """Automat für diesen Start: liest den Zähler in logs/ und schreibt den nächsten."""
        path = lcfg.ROOT / "logs" / self.COUNTER
        n = 0
        try:
            n = int(path.read_text().strip() or "0")
        except (OSError, ValueError):
            n = 0
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str((n + 1) % len(self.themes)))
        except OSError:
            pass
        return n % len(self.themes)

    def _reels_of(self, theme: int) -> int:
        return int(min(MAX_REELS, max(art.MIN_REELS, self.themes[theme].get("reels", 3))))

    def _sheet_path(self, ti: int) -> Path | None:
        """Bogen des Automaten ti; fehlt er (Bilder vom Bot noch nicht da), Ersatz = erster vorhandener Bogen des Themas."""
        p = art.SHEET_DIR / self.themes[ti]["sheet"]
        if p.exists():
            return p
        for th in self.themes:
            q = art.SHEET_DIR / th["sheet"]
            if q.exists():
                log.warning("Bogen %s fehlt, Automat %s läuft mit Ersatzbogen %s", p.name, self.themes[ti]["name"], q.name)
                return q
        log.warning("Bogen %s fehlt und kein Ersatz vorhanden: Themenfarbe", p.name)
        return None

    def _build_atlas(self) -> np.ndarray:
        """RGBA-Atlas: Zeilenblock ti = Automat ti (TH Pixel hoch, 9 Kacheln), darunter die Walzenstreifen."""
        img = np.zeros((self.atlas_h, ATLAS_W, 4), dtype=np.uint8)
        for ti, th in enumerate(self.themes):
            p = self._sheet_path(ti)
            row = _sheet_tiles(p, bool(th.get("keyed", False))) if p else None
            if row is None:                                              # Platzhalter: Themenfarbe
                ca = tuple(int(c * 255) for c in th["colors"][0])
                img[ti * TH:(ti + 1) * TH, :, :3] = ca
                img[ti * TH:(ti + 1) * TH, :, 3] = 255
            else:
                img[ti * TH:(ti + 1) * TH] = row
        return img

    def _load_frame(self) -> np.ndarray | None:
        env = os.environ.get("KITT_SLOTS_FRAME", "").strip()
        if env:
            p = Path(env)
            p = p if p.is_absolute() else lcfg.ROOT / p
        else:
            p = art.SHEET_DIR / self.FRAME
        if not p.exists():
            log.info("Rahmen %s fehlt: Blende statt Themenrahmen", p)
            return None
        return load_frame(p)

    def _area(self) -> tuple[float, float, float, float]:
        """Walzenfläche x0, y0, x1, y1 (Bildanteile, von unten): mit Rahmen die Schwarzfläche in der Mitte."""
        if "area" in self.cfg:
            return tuple(float(v) for v in self.cfg["area"])
        return (0.10, 0.075, 0.90, 0.925) if self.frame is not None else (0.05, 0.02, 0.95, 0.98)

    def _build_strips(self) -> None:
        for r in range(MAX_REELS):
            self.strips[r] = build_strip(self.theme, r, self.themes, self.SEED_BASE)

    def _write_strips(self) -> None:
        """Walzenstreifen als Rotwert in die Streifenzeilen des Atlas schreiben (Zeile uStripRow + Walze)."""
        base = self.strip_row
        for r in range(MAX_REELS):
            self.atlas[base + r, :, :] = 0
            for k, sym in enumerate(self.strips[r]):
                self.atlas[base + r, k] = (sym, 0, 0, 255)
        self.atlas_version += 1

    # -- Eingabe ---------------------------------------------------------
    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            if self.state in (ST_IDLE, ST_RESULT):
                self._spin()
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self._change_theme(+1)
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self._change_theme(-1)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self._change_stake(+1)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self._change_stake(-1)
        # BACKSPACE (Kippschalter aus): nichts

    # -- Spielablauf -----------------------------------------------------
    def _set_state(self, st: int) -> None:
        self.state = st
        self.state_t0 = time.monotonic()

    def _change_theme(self, d: int) -> None:
        if self.state == ST_THEME:
            return
        self.next_theme = (self.theme + d) % len(self.themes)
        self._set_state(ST_THEME)

    def _change_stake(self, d: int) -> None:
        self.stake = (self.stake + d) % len(self.stakes)
        name, self.bet, self.payout_mult = self.stakes[self.stake]
        self.stake_t0 = time.monotonic()
        log.info("Einsatz: %s (%d %s, x%d)", name, self.bet, self.CURRENCY, self.payout_mult)

    def _positions_of(self, reel: int, sym: int) -> list[int]:
        return [k for k, s in enumerate(self.strips[reel]) if s == sym]

    def _pos_not(self, reel: int, sym: int) -> int:
        while True:
            k = self.rng.randrange(STRIP_LEN)
            if self.strips[reel][k] != sym:
                return k

    def _sym(self, reel: int, k: int, off: int = 0) -> int:
        return self.strips[reel][(k + off) % STRIP_LEN]

    def _evaluate(self, targets: list[int]) -> tuple[int, int, int]:
        """Gewinn aus den Zielpositionen: (Gewinnart, Maske der Gewinnwalzen, Gewinnlinie)."""
        n = self.n_reels
        jackpot = len(self.themes[self.theme]["symbols"]) - 1
        center = [self._sym(r, targets[r]) for r in range(n)]
        full = (1 << n) - 1
        if n == 3:
            all9 = [self._sym(r, targets[r], d) for r in range(n) for d in (-1, 0, 1)]
            if len(set(all9)) == 1:
                return WIN_MEGA, full, LINE_MEGA
            lines = [(center, LINE_CENTER),
                     ([self._sym(0, targets[0], -1), center[1], self._sym(2, targets[2], 1)], LINE_UP),
                     ([self._sym(0, targets[0], 1), center[1], self._sym(2, targets[2], -1)], LINE_DOWN)]
            for vals, line in lines:
                if vals[0] == vals[1] == vals[2]:
                    return (WIN_JACKPOT if vals[0] == jackpot else WIN_BIG), full, line
            if center[0] == center[1]:
                return WIN_SMALL, 0b011, LINE_CENTER
            if center[1] == center[2]:
                return WIN_SMALL, 0b110, LINE_CENTER
            if center[0] == center[2]:
                return WIN_SMALL, 0b101, LINE_CENTER
            return WIN_NONE, 0, LINE_CENTER
        # 4 oder 5 Walzen: alle gleich = Jackpot (Jackpot-Symbol = Mega); 5 Walzen: vier gleiche = groß, drei
        # nebeneinander = klein; 4 Walzen: drei nebeneinander = groß, drei gleiche mit Lücke = klein; Diagonalen über
        # drei benachbarte Walzen = klein
        if len(set(center)) == 1:
            return (WIN_MEGA if center[0] == jackpot else WIN_JACKPOT), full, LINE_CENTER
        best = max(set(center), key=center.count)
        best_mask = sum(1 << r for r in range(n) if center[r] == best)
        if n == 5 and center.count(best) == 4:
            return WIN_BIG, best_mask, LINE_CENTER
        for r0 in range(n - 2):
            run = center[r0:r0 + 3]
            if run[0] == run[1] == run[2]:
                return (WIN_BIG if n == 4 else WIN_SMALL), 0b111 << r0, LINE_CENTER
        if n == 4 and center.count(best) == 3:
            return WIN_SMALL, best_mask, LINE_CENTER
        for r0 in range(n - 2):                          # Diagonalen über drei benachbarte Walzen
            up = [self._sym(r0, targets[r0], -1), center[r0 + 1], self._sym(r0 + 2, targets[r0 + 2], 1)]
            dn = [self._sym(r0, targets[r0], 1), center[r0 + 1], self._sym(r0 + 2, targets[r0 + 2], -1)]
            if up[0] == up[1] == up[2]:
                return WIN_SMALL, 0b111 << r0, LINE_UP
            if dn[0] == dn[1] == dn[2]:
                return WIN_SMALL, 0b111 << r0, LINE_DOWN
        return WIN_NONE, 0, LINE_CENTER

    def _candidate(self, kind: int, near: bool) -> list[int]:
        """Zielpositionen für die gewünschte Gewinnart würfeln (wird danach mit _evaluate geprüft)."""
        n = self.n_reels
        n_sym = len(self.themes[self.theme]["symbols"])
        jackpot = n_sym - 1
        rng = self.rng
        t = [rng.randrange(STRIP_LEN) for _ in range(n)]
        if kind == WIN_NONE:
            if near:                                      # knapp daneben: zwei gleiche, das dritte direkt über/unter der Linie
                s = rng.randrange(n_sym - 1)
                r0 = rng.randrange(n - 2)
                for r in range(n):
                    t[r] = self._pos_not(r, s)
                t[r0] = rng.choice(self._positions_of(r0, s))
                t[r0 + 1] = rng.choice(self._positions_of(r0 + 1, s))
                t[r0 + 2] = (rng.choice(self._positions_of(r0 + 2, s)) + rng.choice((-1, 1))) % STRIP_LEN
            return t
        if kind == WIN_SMALL:
            s = rng.randrange(n_sym - 1)
            for r in range(n):
                t[r] = self._pos_not(r, s)
            if n == 3:
                group = rng.choice(((0, 1), (1, 2), (0, 2)))
            elif n == 4:
                group = rng.choice(((0, 1, 3), (0, 2, 3)))              # drei gleiche mit Lücke
            else:
                r0 = rng.randrange(n - 2)
                group = (r0, r0 + 1, r0 + 2)                            # drei nebeneinander
            for r in group:
                t[r] = rng.choice(self._positions_of(r, s))
            return t
        if kind == WIN_BIG:
            s = rng.randrange(n_sym - 1)
            t = [rng.choice(self._positions_of(r, s)) for r in range(n)]
            if n == 4:
                odd = rng.choice((0, 3))                                 # drei nebeneinander, die vierte anders
                t[odd] = self._pos_not(odd, s)
            elif n == 5:
                odd = rng.randrange(n)                                   # vier gleiche
                t[odd] = self._pos_not(odd, s)
            return t
        # Jackpot: 3 Walzen = Jackpot-Symbol, 4/5 Walzen = alle gleich (selten das Jackpot-Symbol = Mega)
        s = jackpot if n == 3 or rng.random() < 0.15 else rng.randrange(n_sym - 1)
        return [rng.choice(self._positions_of(r, s)) for r in range(n)]

    def _plan(self) -> list[int]:
        """Ergebnis vorab würfeln: meist verloren (oft knapp), ab und zu gewinnen, selten Jackpot."""
        roll = self.rng.random()
        if roll < 0.62:
            kind, near = WIN_NONE, self.rng.random() < 0.45
        elif roll < 0.84:
            kind, near = WIN_SMALL, False
        elif roll < 0.96:
            kind, near = WIN_BIG, False
        else:
            kind, near = WIN_JACKPOT, False
        for _ in range(40):
            t = self._candidate(kind, near)
            got = self._evaluate(t)[0]
            if got == kind or (kind == WIN_JACKPOT and got == WIN_MEGA):
                return t
        while True:                                       # Rückfall: irgendeine Niete
            t = [self.rng.randrange(STRIP_LEN) for _ in range(self.n_reels)]
            if self._evaluate(t)[0] == WIN_NONE:
                return t

    def _stop_pattern(self) -> list[float]:
        n = self.n_reels
        j = lambda: self.rng.uniform(-0.2, 0.2)
        mid = (n - 1) / 2.0
        patterns = [
            [2.0 + 1.1 * i + j() for i in range(n)],                                # nacheinander
            [2.4 + 1.2 * (i // 2) + (j() if i % 2 == 0 else 0.0) for i in range(n)],  # paarweise
            [3.0 + j()] * n,                                                          # alle zugleich
            [1.6 + j()] + [4.6 + 0.5 * i + j() for i in range(1, n)],                 # eine früh, die anderen lange
            [2.2 + 0.9 * i + j() for i in range(n - 1)] + [6.5 + 0.4 * n + j()],      # die letzte zögert
            [1.8 + 1.0 * abs(i - mid) + j() for i in range(n)],                       # Mitte zuerst
        ]
        return self.rng.choice(patterns)

    def _spin(self, only_reel: int = -1) -> None:
        now = time.monotonic()
        n = self.n_reels
        if only_reel < 0:
            targets = self._plan()
            times = self._stop_pattern()
            self.credits -= self.bet
            self.spins += 1
            boost = 1.0 + 0.6 * self.drop_boost
            self.drop_boost = 0.0
            for r in range(n):
                self.reels[r].start(now, now + times[r], targets[r], self.rng.uniform(5.5, 8.0) * boost)
        else:
            # Nachdrehen einer Walze: mit halber Chance übernimmt sie das Symbol der Nachbarwalze
            r = only_reel
            nb = r - 1 if r > 0 else r + 1
            if self.rng.random() < 0.5:
                target = self.rng.choice(self._positions_of(r, self._sym(nb, self.reels[nb].target)))
            else:
                target = self.rng.randrange(STRIP_LEN)
            self.reels[r].start(now, now + self.rng.uniform(0.8, 1.7), target, 9.0)
        self.message = ""
        self.win = WIN_NONE
        self.win_mask = 0
        self.win_line = LINE_CENTER
        self.result_logged = False
        self._set_state(ST_SPIN)

    def _finish(self) -> None:
        th = self.themes[self.theme]
        n = self.n_reels
        targets = [self.reels[r].target for r in range(n)]
        self.win, self.win_mask, self.win_line = self._evaluate(targets)
        if self.win == WIN_NONE and not self.respin_pending and self.rng.random() < 0.18:
            # Traumlogik: eine Walze dreht noch einmal nach
            self.respin_pending = True
            self.respin_reel = self.rng.randrange(n)
            self.message = "MOMENT ..."
            self.message_color = WHITE
            self._set_state(ST_RESULT)
            return
        self.respin_pending = False
        if self.win == WIN_NONE:
            center = [self._sym(r, targets[r]) for r in range(n)]
            near = False
            for r0 in range(n - 2):
                if center[r0] == center[r0 + 1] and any(self._sym(r0 + 2, targets[r0 + 2], d) == center[r0] for d in (-1, 1)):
                    near = True
            pool = th["near"] if near else th["lose"]
            self.message_color = (200, 200, 210)
        else:
            self.credits += PAYOUT[self.win] * self.payout_mult
            if self.win in (WIN_JACKPOT, WIN_MEGA):
                wled.apply_mode_async(self.led[2])
            elif self.win == WIN_BIG:
                wled.apply_mode_async(self.led[1])
            pool = {WIN_SMALL: th["small"], WIN_BIG: th["big"], WIN_JACKPOT: th["jackpot"], WIN_MEGA: MEGA_MSGS}[self.win]
            self.message_color = GOLD
        self.message = self.rng.choice(pool)
        self._set_state(ST_RESULT)

    def _advance(self) -> None:
        now = time.monotonic()
        dt = min(0.05, now - self.last)
        self.last = now
        for reel in self.reels:
            reel.update(now, dt)
        # Unschärfe je Walze folgt ihrer Drehzahl: beim Anlaufen weich hinein, beim Stillstand schnell scharf
        for i, reel in enumerate(self.reels):
            target = min(1.0, reel.speed / 6.0)
            tau = 1.2 if target > self.blur[i] else 0.35
            self.blur[i] += (target - self.blur[i]) * min(1.0, dt / tau)
            if self.was_spinning[i] and not reel.spinning:
                self.stop_t0[i] = now
            self.was_spinning[i] = reel.spinning
        st_t = now - self.state_t0
        if self.state == ST_IDLE:
            if st_t >= self.idle_len:
                self._spin()
        elif self.state == ST_SPIN:
            if not any(r.spinning for r in self.reels):
                self._finish()
        elif self.state == ST_RESULT:
            if not self.result_logged and self.message:
                self.result_logged = True
                log.info("%s: %s", WIN_NAMES[self.win], self.message)
            if self.respin_pending:
                if st_t >= 0.7:
                    self._spin(self.respin_reel)
            else:
                # Nieten kurz, Gewinne dürfen wirken
                if st_t >= HOLD[self.win]:
                    if self.win >= WIN_BIG:
                        wled.apply_mode_async(self.led[0])      # Board zurück auf das Modusprofil
                    self.idle_len = self.rng.uniform(0.3, 1.0) if self.win == WIN_NONE else self.rng.uniform(0.8, 1.6)
                    self._set_state(ST_IDLE)
        elif self.state == ST_THEME:
            if st_t >= 0.9 and self.theme != self.next_theme:
                self.theme = self.next_theme
                self.n_reels = self._reels_of(self.theme)
                self._build_strips()
                self._write_strips()
                for r in self.reels:
                    r.spinning = False
                    r.pos = float(self.rng.randrange(STRIP_LEN))
                    r.target = int(r.pos)
                self.message = ""
                self.win = WIN_NONE
                self.win_mask = 0
                log.info("Automat: %s (%d Walzen)", self.themes[self.theme]["name"], self.n_reels)
            if st_t >= 1.8:
                self.idle_len = 1.0
                self._set_state(ST_IDLE)

    # -- Musik -------------------------------------------------------------
    def _music(self, f) -> None:
        now = time.monotonic()
        dt = min(0.1, now - self.last_f)
        self.last_f = now
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
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.step = (self.step + 1) % 60
            self.step_t0 = now
            first, count = self.FIG_CELLS
            self.fig_prev, self.fig_t0 = self.fig_pose, now
            self.fig_pose = first + (self.fig_pose - first + self.rng.randint(1, max(1, count - 1))) % max(1, count)
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        if now - self.pattern_t0 > self.pattern_len:
            self._next_pattern(now)
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 10.0:
            self.drop_armed = False
            self.last_drop = now
            self.drop_t0 = now
            self.flash = 1.0
            self.drop_boost = 1.0
            self._next_pattern(now)
            log.info("Drop: Blitz, nächste Drehung schneller")
        self.flash = max(0.0, self.flash - dt / 2.0)
        # Jackpot (Zukunft): Bild kippt nach Schwarzweiß wie 1955 und kommt zurück
        goal = 0.0
        if self.SEPIA_ON_JACKPOT and self.state == ST_RESULT and self.win >= WIN_JACKPOT and 0.7 <= now - self.state_t0 < 4.2:
            goal = 1.0
        self.sepia += (goal - self.sepia) * min(1.0, dt / (0.12 if goal > self.sepia else 1.2))

    def _next_pattern(self, now: float) -> None:
        self.pattern = (self.pattern + self.rng.randint(1, N_PATTERNS - 1)) % N_PATTERNS
        self.pattern_t0 = now
        self.pattern_len = self.rng.uniform(25.0, 45.0)

    # -- Schnittstelle zur Engine ------------------------------------------
    def images(self) -> dict:
        return {"uSpriteTex": (self.atlas, self.atlas_version),
                "uFrameTex": (self.frame if self.frame is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    UNIFORMS = ("uSpriteTex", "uFrameTex", "uFigTex", "uAtlasSize", "uTile", "uFrameSize", "uFigSize", "uArea", "uTheme",
                "uNReels", "uStyle", "uKeyed", "uFrameOK", "uColA", "uColB", "uReel0", "uReel1", "uReel2", "uReel3", "uReel4",
                "uState", "uStateT", "uWin", "uWinMask", "uWinLine", "uFade", "uStripRow", "uFig", "uSeed", "uBassS", "uMidS",
                "uHighS", "uEnergy", "uLive", "uBeatPulse", "uFlash", "uDropT", "uStep", "uStepPhase", "uPattern", "uStake",
                "uStakeT", "uSepia")

    def led_state(self) -> dict:
        """Für launcher/ledstream.py: Casino-Markise; Gewinnstufe nur in der Ergebnisphase."""
        now = time.monotonic()
        res = self.state == ST_RESULT
        return {"program": "slots", "spinning": self.state == ST_SPIN, "win": int(self.win) if res else 0,
                "win_age": (now - self.state_t0) if res else 0.0}

    def uniform_names(self):
        return self.UNIFORMS

    def uniforms(self, t: float, f) -> dict:
        self._advance()
        self._music(f)
        now = time.monotonic()
        th = self.themes[self.theme]
        st_t = now - self.state_t0
        fade = 0.0
        if self.state == ST_THEME:
            fade = math.sin(min(1.0, st_t / 1.8) * math.pi)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out = {
            "uAtlasSize": (float(ATLAS_W), float(self.atlas_h)),
            "uTile": (float(TW), float(TH)),
            "uFrameSize": size(self.frame), "uFigSize": size(self.figs),
            "uArea": self.area,
            "uTheme": float(self.theme),
            "uNReels": float(self.n_reels),
            "uStyle": float(self.STYLE),
            "uKeyed": 1.0 if th.get("keyed") else 0.0,
            "uFrameOK": 1.0 if self.frame is not None else 0.0,
            "uColA": th["colors"][0],
            "uColB": th["colors"][1],
            "uState": float(self.state),
            "uStateT": st_t,
            "uWin": float(self.win),
            "uWinMask": float(self.win_mask),
            "uWinLine": float(self.win_line),
            "uFade": fade,
            "uStripRow": float(self.strip_row),
            "uFig": (float(self.fig_prev), float(self.fig_pose), min(1.0, (now - self.fig_t0) / 0.12),
                     1.0 if self.figs is not None else 0.0),
            "uSeed": self.seed, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uFlash": self.flash,
            "uDropT": (now - self.drop_t0) if now - self.drop_t0 < 4.0 else -1.0,
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.5), "uPattern": float(self.pattern),
            "uStake": float(self.stake), "uStakeT": now - self.stake_t0,
            "uSepia": self.sepia,
        }
        for i in range(MAX_REELS):
            r = self.reels[i]
            out[f"uReel{i}"] = (r.pos, r.speed, self.blur[i], min(9.0, now - self.stop_t0[i]))
        return out

    def overlays(self, t: float):
        th = self.themes[self.theme]
        now = time.monotonic()
        st_t = now - self.state_t0
        dim = 1.0 - 0.4 * max(self.blur[:self.n_reels])
        name, bet, mult = self.stakes[self.stake]
        cur = self.CURRENCY
        out = [
            (th["title"], 0.026, 0.5, 0.962, self.TITLE_COLOR, 0.85 * dim),
            (th["subtitle"], 0.016, 0.5, 0.93, self.SUBTITLE_COLOR, 0.6 * dim),
            (f"GUTHABEN  {self.credits} {cur}      EINSATZ  {name}  {bet} {cur}  (x{mult})", 0.017, 0.5, 0.028, self.INFO_COLOR, 0.7 * dim),
        ]
        if now - self.stake_t0 < 1.6:
            a = min(1.0, (1.6 - (now - self.stake_t0)) / 0.6)
            out.append((f"EINSATZ: {name}  {bet} {cur}", 0.03, 0.5, 0.5, (255, 240, 180), a))
        if self.state == ST_RESULT and self.message:
            pulse = 1.0 if self.win == WIN_NONE else 0.8 + 0.2 * math.sin(t * 3.0)
            out.append((self.message, 0.024, 0.5, 0.07, self.message_color, min(1.0, st_t * 2.0) * pulse))
            if self.win >= WIN_JACKPOT:
                out.append((th.get("jackpot_text", "J A C K P O T"), 0.07, 0.5, 0.5, GOLD, 0.5 + 0.3 * math.sin(t * 4.0)))
            elif self.win == WIN_BIG:
                out.append((th.get("big_text", "G E W I N N"), 0.055, 0.5, 0.5, GOLD, 0.5 + 0.3 * math.sin(t * 3.0)))
        if self.state == ST_THEME and st_t >= 0.9:
            out.append(("NEUER AUTOMAT", 0.03, 0.5, 0.5, WHITE, 1.0 - (st_t - 0.9) / 0.9))
        return out
