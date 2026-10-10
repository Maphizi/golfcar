"""Space-Slotmaschine (Taste 5): Szenen-Controller der GL-Engine.

Spielt von selbst: Walzen drehen, bleiben einzeln, paarweise oder alle zugleich stehen, manchmal
dreht eine noch einmal nach. Meist verliert man, ab und zu gewinnt man, selten den Jackpot.
Alle paar Runden wechselt zufällig das übergeordnete Thema (Symbole, Farben, Sprüche).

Eingabe: ENTER / Leertaste (Startknopf) = sofort drehen, Pfeil links/rechts = Thema wechseln.
Die Walzeninhalte, Ziele und Sprüche kommen aus diesem Controller; der Shader zeichnet nur.
"""
from __future__ import annotations

import math
import random
import time

import numpy as np
import pygame

from visualizers.scenes import slots_art as art

STRIP_LEN = 32          # Symbole pro Walze
N_REELS = 3
SYM = 16                # Sprite-Kantenlänge in Pixeln
ATLAS_W = 7 * SYM       # 7 Symbole pro Thema nebeneinander
ATLAS_H = len(art.THEMES) * SYM + 4   # Themenzeilen + Streifenzeilen (eine je Walze)

ST_IDLE, ST_SPIN, ST_RESULT, ST_THEME = 0, 1, 2, 3
WIN_NONE, WIN_SMALL, WIN_BIG, WIN_JACKPOT = 0, 1, 2, 3
BET = 10
PAYOUT = {WIN_SMALL: 25, WIN_BIG: 150, WIN_JACKPOT: 1000}

WHITE = (245, 245, 250)
GOLD = (255, 220, 80)


def build_atlas() -> np.ndarray:
    """RGBA-Atlas: Zeile ti = Thema ti (16 px hoch), darunter die Walzenstreifen als Rotwert."""
    img = np.zeros((ATLAS_H, ATLAS_W, 4), dtype=np.uint8)
    for ti, th in enumerate(art.THEMES):
        for si, (_, ascii_art) in enumerate(th["symbols"]):
            rows = ascii_art.strip("\n").split("\n")
            for ry, row in enumerate(rows):
                for rx, ch in enumerate(row):
                    if ch == ".":
                        continue
                    r, g, b = art.PALETTE[ch]
                    img[ti * SYM + (SYM - 1 - ry), si * SYM + rx] = (r, g, b, 255)
    return img


def build_strip(theme: int, reel: int) -> list[int]:
    """Feste Symbolfolge je Thema und Walze: Jackpot-Symbol selten, der Rest gleichmäßig gemischt."""
    rng = random.Random(1000 + theme * 10 + reel)
    n_sym = len(art.THEMES[theme]["symbols"])
    pool = []
    for s in range(n_sym - 1):
        pool += [s] * 5
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


def ease_back(u: float, s: float = 1.4) -> float:
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
            ramp = min(1.0, (now - self.start_t) / 0.35)
            self.speed = self.max_speed * ramp
            self.pos += self.speed * dt
            if now >= self.stop_at:
                self.stopping_since = now
                self.start_pos = self.pos
                # Restweg bis zum Ziel plus ein bis zwei ganze Umdrehungen
                frac = (self.target - self.pos) % STRIP_LEN
                self.dist = frac + STRIP_LEN * random.choice((0, 1))
                self.decel = max(0.9, self.dist / self.max_speed * 1.3)
        else:
            u = (now - self.stopping_since) / self.decel
            self.pos = self.start_pos + self.dist * ease_back(u)
            self.speed = self.max_speed * max(0.0, 1.0 - u) ** 2
            if u >= 1.0:
                self.pos = float(self.target)
                self.speed = 0.0
                self.spinning = False


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.theme = self.rng.randrange(len(art.THEMES))
        self.strips = [build_strip(self.theme, r) for r in range(N_REELS)]
        self.reels = [Reel() for _ in range(N_REELS)]
        for r in range(N_REELS):
            self.reels[r].pos = float(self.rng.randrange(STRIP_LEN))
        self.atlas = build_atlas()
        self.atlas_version = 0
        self._write_strips()
        self.state = ST_IDLE
        self.state_t0 = time.monotonic()
        self.last = self.state_t0
        self.idle_len = 2.5
        self.win = WIN_NONE
        self.win_mask = 0
        self.message = ""
        self.message_color = WHITE
        self.credits = 1337
        self.spins = 0
        self.spins_until_theme = self.rng.randint(4, 8)
        self.next_theme = self.theme
        self.lever_t0 = -10.0
        self.respin_pending = False
        self.respin_reel = -1
        self.planned_win = WIN_NONE
        self.cfg = scene_cfg

    def _write_strips(self) -> None:
        """Walzenstreifen als Rotwert in die Streifenzeilen des Atlas schreiben (Zeile uStripRow + Walze)."""
        base = len(art.THEMES) * SYM
        for r in range(N_REELS):
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

    # -- Spielablauf -----------------------------------------------------
    def _set_state(self, st: int) -> None:
        self.state = st
        self.state_t0 = time.monotonic()

    def _change_theme(self, d: int) -> None:
        if self.state == ST_THEME:
            return
        self.next_theme = (self.theme + d) % len(art.THEMES)
        self._set_state(ST_THEME)

    def _positions_of(self, reel: int, sym: int) -> list[int]:
        return [k for k, s in enumerate(self.strips[reel]) if s == sym]

    def _plan(self) -> tuple[int, list[int], int]:
        """Ergebnis vorab würfeln: (Gewinnart, Zielpositionen, Maske der Gewinnwalzen)."""
        n_sym = len(art.THEMES[self.theme]["symbols"])
        jackpot = n_sym - 1
        roll = self.rng.random()
        strips = self.strips
        if roll < 0.62:                                   # verloren, oft knapp
            if self.rng.random() < 0.45:
                s = self.rng.randrange(n_sym - 1)
                a = self.rng.choice(self._positions_of(0, s))
                b = self.rng.choice(self._positions_of(1, s))
                # dritte Walze: das Symbol liegt direkt über oder unter der Linie
                c = (self.rng.choice(self._positions_of(2, s)) + self.rng.choice((-1, 1))) % STRIP_LEN
                return WIN_NONE, [a, b, c], 0
            while True:
                t = [self.rng.randrange(STRIP_LEN) for _ in range(N_REELS)]
                vals = [strips[r][t[r]] for r in range(N_REELS)]
                if len(set(vals)) == 3:
                    return WIN_NONE, t, 0
        if roll < 0.84:                                   # zwei gleiche
            s = self.rng.randrange(n_sym - 1)
            pair = self.rng.choice(((0, 1), (1, 2), (0, 2)))
            t = [0, 0, 0]
            for r in pair:
                t[r] = self.rng.choice(self._positions_of(r, s))
            other = [r for r in range(N_REELS) if r not in pair][0]
            while True:
                k = self.rng.randrange(STRIP_LEN)
                if strips[other][k] != s:
                    t[other] = k
                    break
            return WIN_SMALL, t, (1 << pair[0]) | (1 << pair[1])
        if roll < 0.96:                                   # drei gleiche
            s = self.rng.randrange(n_sym - 1)
            return WIN_BIG, [self.rng.choice(self._positions_of(r, s)) for r in range(N_REELS)], 7
        return WIN_JACKPOT, [self.rng.choice(self._positions_of(r, jackpot)) for r in range(N_REELS)], 7

    def _stop_pattern(self) -> list[float]:
        j = lambda: self.rng.uniform(-0.2, 0.2)
        patterns = [
            [1.2 + j(), 2.2 + j(), 3.2 + j()],            # nacheinander
            [1.6 + j(), 1.6, 3.6 + j()],                  # zwei zugleich, dann eine
            [2.2 + j(), 2.2, 2.2],                        # alle zugleich
            [1.0 + j(), 3.8 + j(), 4.6 + j()],            # eine früh, die anderen drehen lange weiter
            [1.4 + j(), 2.4 + j(), 5.8 + j()],            # die letzte zögert
            [2.8 + j(), 1.2 + j(), 2.0 + j()],            # Mitte zuerst
        ]
        return self.rng.choice(patterns)

    def _spin(self, only_reel: int = -1) -> None:
        now = time.monotonic()
        if only_reel < 0:
            self.planned_win, targets, self.win_mask_planned = self._plan()
            times = self._stop_pattern()
            self.credits -= BET
            self.spins += 1
            self.lever_t0 = now
            for r in range(N_REELS):
                self.reels[r].start(now, now + times[r], targets[r], self.rng.uniform(9.0, 14.0))
        else:
            # Nachdrehen einer Walze: mit halber Chance wird daraus ein Gewinn
            r = only_reel
            others = [o for o in range(N_REELS) if o != r]
            s_other = [self.strips[o][self.reels[o].target] for o in others]
            if self.rng.random() < 0.5 and s_other[0] == s_other[1]:
                target = self.rng.choice(self._positions_of(r, s_other[0]))
                self.planned_win, self.win_mask_planned = WIN_BIG, 7
            elif self.rng.random() < 0.5:
                target = self.rng.choice(self._positions_of(r, s_other[0]))
                self.planned_win, self.win_mask_planned = WIN_SMALL, (1 << r) | (1 << others[0])
            else:
                target = self.rng.randrange(STRIP_LEN)
                self.planned_win, self.win_mask_planned = WIN_NONE, 0
            self.reels[r].start(now, now + self.rng.uniform(1.2, 2.2), target, 7.0)
        self.message = ""
        self.win = WIN_NONE
        self.win_mask = 0
        self._set_state(ST_SPIN)

    def _finish(self) -> None:
        th = art.THEMES[self.theme]
        vals = [self.strips[r][self.reels[r].target] for r in range(N_REELS)]
        jackpot = len(th["symbols"]) - 1
        # Gewinn aus den tatsächlichen Symbolen bestimmen (deckt auch das Nachdrehen ab)
        if vals[0] == vals[1] == vals[2]:
            self.win = WIN_JACKPOT if vals[0] == jackpot else WIN_BIG
            self.win_mask = 7
        elif vals[0] == vals[1] or vals[1] == vals[2] or vals[0] == vals[2]:
            self.win = WIN_SMALL
            self.win_mask = (3 if vals[0] == vals[1] else 6 if vals[1] == vals[2] else 5)
        else:
            self.win = WIN_NONE
            self.win_mask = 0
        if self.win == WIN_NONE and not self.respin_pending and self.rng.random() < 0.18:
            # Traumlogik: eine Walze dreht noch einmal nach
            self.respin_pending = True
            self.respin_reel = self.rng.randrange(N_REELS)
            self.message = "MOMENT ..."
            self.message_color = WHITE
            self._set_state(ST_RESULT)
            return
        self.respin_pending = False
        if self.win == WIN_NONE:
            near = any(
                self.strips[2][(self.reels[2].target + d) % STRIP_LEN] == vals[0] == vals[1] for d in (-1, 1)
            )
            pool = th["near"] if near else th["lose"]
            self.message_color = (200, 200, 210)
        else:
            self.credits += PAYOUT[self.win]
            pool = {WIN_SMALL: th["small"], WIN_BIG: th["big"], WIN_JACKPOT: th["jackpot"]}[self.win]
            self.message_color = GOLD
        self.message = self.rng.choice(pool)
        self._set_state(ST_RESULT)

    def _advance(self) -> None:
        now = time.monotonic()
        dt = min(0.05, now - self.last)
        self.last = now
        for reel in self.reels:
            reel.update(now, dt)
        st_t = now - self.state_t0
        if self.state == ST_IDLE:
            if st_t >= self.idle_len:
                if self.spins >= self.spins_until_theme:
                    self.spins = 0
                    self.spins_until_theme = self.rng.randint(4, 8)
                    choices = [i for i in range(len(art.THEMES)) if i != self.theme]
                    self.next_theme = self.rng.choice(choices)
                    self._set_state(ST_THEME)
                else:
                    self._spin()
        elif self.state == ST_SPIN:
            if not any(r.spinning for r in self.reels):
                self._finish()
        elif self.state == ST_RESULT:
            if self.respin_pending:
                if st_t >= 1.2:
                    self._spin(self.respin_reel)
            else:
                hold = {WIN_NONE: 2.8, WIN_SMALL: 3.2, WIN_BIG: 4.5, WIN_JACKPOT: 7.0}[self.win]
                if st_t >= hold:
                    self.idle_len = self.rng.uniform(0.6, 2.0)
                    self._set_state(ST_IDLE)
        elif self.state == ST_THEME:
            if st_t >= 0.9 and self.theme != self.next_theme:
                self.theme = self.next_theme
                self.strips = [build_strip(self.theme, r) for r in range(N_REELS)]
                self._write_strips()
                for r in range(N_REELS):
                    self.reels[r].pos = float(self.rng.randrange(STRIP_LEN))
                    self.reels[r].target = int(self.reels[r].pos)
                self.message = ""
            if st_t >= 1.8:
                self.idle_len = 1.0
                self._set_state(ST_IDLE)

    # -- Schnittstelle zur Engine ------------------------------------------
    def images(self) -> dict:
        return {"uSpriteTex": (self.atlas, self.atlas_version)}

    def uniform_names(self):
        return ("uSpriteTex", "uAtlasSize", "uTheme", "uColA", "uColB", "uReel", "uSpeed", "uState", "uStateT",
                "uWin", "uWinMask", "uLever", "uFade", "uStripRow")

    def uniforms(self, t: float, f) -> dict:
        self._advance()
        now = time.monotonic()
        th = art.THEMES[self.theme]
        st_t = now - self.state_t0
        fade = 0.0
        if self.state == ST_THEME:
            fade = math.sin(min(1.0, st_t / 1.8) * math.pi)
        lever = max(0.0, 1.0 - (now - self.lever_t0) / 0.7)
        return {
            "uAtlasSize": (float(ATLAS_W), float(ATLAS_H)),
            "uTheme": float(self.theme),
            "uColA": th["colors"][0],
            "uColB": th["colors"][1],
            "uReel": tuple(r.pos for r in self.reels),
            "uSpeed": tuple(r.speed for r in self.reels),
            "uState": float(self.state),
            "uStateT": st_t,
            "uWin": float(self.win),
            "uWinMask": float(self.win_mask),
            "uLever": math.sin(lever * math.pi),
            "uFade": fade,
            "uStripRow": float(len(art.THEMES) * SYM),
        }

    def overlays(self, t: float):
        th = art.THEMES[self.theme]
        now = time.monotonic()
        st_t = now - self.state_t0
        out = [
            (th["title"], 0.032, 0.5, 0.862, GOLD, 0.95),
            (th["subtitle"], 0.018, 0.5, 0.822, (255, 240, 200), 0.75),
            (f"GUTHABEN  {self.credits} CR      EINSATZ  {BET} CR", 0.019, 0.5, 0.148, (200, 200, 210), 0.8),
            ("START  DREHEN        <  >  THEMA", 0.017, 0.5, 0.035, (120, 120, 130), 0.55 + 0.25 * math.sin(t * 2.0)),
        ]
        if self.state == ST_RESULT and self.message:
            blink = 1.0 if self.win == WIN_NONE else 0.7 + 0.3 * math.sin(t * 9.0)
            out.append((self.message, 0.024, 0.5, 0.205, self.message_color, min(1.0, st_t * 3.0) * blink))
            if self.win == WIN_JACKPOT:
                out.append(("J A C K P O T", 0.08, 0.5, 0.74, GOLD, 0.6 + 0.4 * math.sin(t * 12.0)))
            elif self.win == WIN_BIG:
                out.append(("G E W I N N", 0.06, 0.5, 0.74, GOLD, 0.6 + 0.4 * math.sin(t * 8.0)))
        if self.state == ST_THEME and st_t >= 0.9:
            out.append(("NEUES THEMA", 0.03, 0.5, 0.74, WHITE, 1.0 - (st_t - 0.9) / 0.9))
        return out
