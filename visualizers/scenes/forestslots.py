"""Der Pilzautomat (Taste 5 im Thema THE POWER OF THE GREEN, Gegenstück zur Space-Slotmaschine).

Ein Baumstumpf im Nachtwald als Automat (assets/forestslots/scene.png): drei ausgehöhlte Fenster sind die Walzen,
die Symbole kommen aus assets/forestslots/symbols.png (3x3, letztes = Lichthirsch = Jackpot). Spiellogik (Walzen,
Gewinnplanung, Fast-Gewinn, Nachdrehen, Jackpot, Mega) ist die der Space-Slotmaschine (slots.Controller).
Statt dreier Automaten wechselt der Knüppel links/rechts den Einsatz (Eichel, Pilz, Hirsch) mit steigender
Gewinnhöhe und stärkeren Effekten. Startknopf = Hebel ziehen.
Musik: Bass lässt die leuchtenden Pilze pulsieren und die Walzen wippen, Beats glimmen im Moos und zucken auf der
Gewinnlinie, Höhen funkeln als Glühwürmchen, Drops schicken eine Sporenwolke und eine Farbwelle über die Pilze
(und die nächste Drehung läuft schneller an). Gewinne: klein = Glühwürmchen aus den Fenstern, groß = Blätter- und
Pollenregen, Pilze leuchten in Wellen, der Fuchs tanzt (assets/woodeye/figures.png); Jackpot = der ganze Wald
leuchtet auf, der Lichthirsch galoppiert durchs Bild, Sporenfeuerwerk.
"""
from __future__ import annotations

import logging
import math
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import config as lcfg, wled
from visualizers.scenes import slots, slots_themes as art

log = logging.getLogger("forestslots")

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "forestslots"
WOODEYE_ASSETS = ASSETS.parent / "woodeye"
TW, TH = 384, 256                     # Kacheln des Waldbogens (3:2)
N_SYM = 9
ATLAS_W = N_SYM * TW
ATLAS_H = TH + 4
STAKES = [("EICHEL", 10, 1), ("PILZ", 50, 5), ("HIRSCH", 200, 20)]   # Name, Einsatz, Gewinnfaktor
FOX_CELLS = (24, 25, 26, 27)


def _sheet_tiles(path) -> np.ndarray | None:
    try:
        surf = pygame.image.load(str(path))
        if surf.get_size() != (TW * 3, TH * 3):
            surf = pygame.transform.smoothscale(surf, (TW * 3, TH * 3))
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
    except Exception as exc:
        log.warning("Bildbogen %s nicht ladbar: %s", path, exc)
        return None
    row = np.zeros((TH, N_SYM * TW, 4), dtype=np.uint8)
    for ry in range(3):
        for rx in range(3):
            k = ry * 3 + rx
            tile = rgb[ry * TH:(ry + 1) * TH, rx * TW:(rx + 1) * TW]
            row[:, k * TW:(k + 1) * TW, :3] = tile[::-1]
            # Schwarzer Hintergrund -> Alpha aus der Helligkeit (Symbole liegen frei im Fenster)
            lum = tile[::-1].max(axis=2).astype(np.float32)
            row[:, k * TW:(k + 1) * TW, 3] = np.clip((lum - 14.0) / 40.0, 0.0, 1.0) * 255
    return row


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


class Controller(slots.Controller):
    def __init__(self, scene_cfg: dict, demo: bool = False):
        super().__init__(scene_cfg, demo)
        self.themes = [art.FOREST]
        self.led = ("forestslots", "forestslots_win", "forestslots_jackpot")
        self.theme = 0
        self.next_theme = 0
        self.strip_row = TH
        self.strips = [slots.build_strip(7 + r, r, [art.FOREST] * 10) for r in range(slots.N_REELS)]
        self.atlas = np.zeros((ATLAS_H, ATLAS_W, 4), dtype=np.uint8)
        row = _sheet_tiles(ASSETS / "symbols.png")
        if row is not None:
            self.atlas[:TH] = row
        self.atlas_version = 1
        self._write_strips()
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "scene.png")
        self.figs = _load_rgba(WOODEYE_ASSETS / "figures.png")
        self.windows = [tuple(float(v) for v in w) for w in scene_cfg.get("windows", [[0.335, 0.418], [0.439, 0.528], [0.550, 0.636]])]
        self.win_y = tuple(float(v) for v in scene_cfg.get("window_y", [0.447, 0.681]))
        self.stake = 0
        self._apply_stake()
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last_f = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.spore_t0 = -100.0
        self.drop_boost = 0.0
        self.fox_t0 = 0.0
        self.fox_pose = 0
        self.fox_prev = 0
        self.stake_t0 = -10.0
        self.result_logged = False
        log.info("Pilzautomat: Szene %s, Symbole %s, Figuren %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if row is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    def _pick_theme(self) -> int:
        return 0                                          # Themenzähler der Space-Automaten nicht weiterzählen

    # -- Einsatz statt Automatenwechsel --------------------------------------
    def _apply_stake(self) -> None:
        name, bet, mult = STAKES[self.stake]
        self.bet = bet
        self.payout_mult = mult

    def _change_theme(self, d: int) -> None:
        self.stake = (self.stake + d) % len(STAKES)
        self._apply_stake()
        self.stake_t0 = time.monotonic()
        log.info("Einsatz: %s (%d CR, x%d)", *STAKES[self.stake])

    def _spin(self, only_reel: int = -1) -> None:
        super()._spin(only_reel)
        if only_reel < 0 and self.drop_boost > 0.0:
            for r in self.reels:
                r.max_speed *= 1.0 + 0.6 * self.drop_boost
            self.drop_boost = 0.0
        self.result_logged = False

    # -- Engine --------------------------------------------------------------
    def images(self) -> dict:
        return {"uSpriteTex": (self.atlas, self.atlas_version),
                "uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uSpriteTex", "uSceneTex", "uFigTex", "uAtlasSize", "uSceneSize", "uFigSize", "uTheme", "uColA", "uColB",
                "uReel", "uSpeed", "uState", "uStateT", "uWin", "uWinMask", "uWinLine", "uBlur", "uFade", "uStripRow",
                "uTile", "uWin0", "uWin1", "uWin2", "uWinY", "uSeed", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive",
                "uBeatPulse", "uFlash", "uSporeT", "uStake", "uStakeT", "uFox")

    def uniforms(self, t: float, f) -> dict:
        out = super().uniforms(t, f)
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
            self.fox_prev, self.fox_pose, self.fox_t0 = self.fox_pose, (self.fox_pose + 1) % 4, now
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.45)
        if live and self.energy > 0.03 and e_fast < 0.5 * self.energy:
            self.quiet_since = self.quiet_since or now
            if now - self.quiet_since > 0.4:
                self.drop_armed = True
        else:
            self.quiet_since = None
        if self.drop_armed and beat > 0.5 and e_fast > 1.05 * self.energy and now - self.last_drop > 10.0:
            self.drop_armed = False
            self.last_drop = now
            self.flash = 1.0
            self.spore_t0 = now
            self.drop_boost = 1.0
            log.info("Drop: Sporen, nächste Drehung schneller")
        self.flash = max(0.0, self.flash - dt / 2.0)
        if self.state == slots.ST_RESULT and not self.result_logged and self.message:
            self.result_logged = True
            log.info("%s: %s", {0: "Niete", 1: "kleiner Gewinn", 2: "Gewinn", 3: "JACKPOT", 4: "MEGA"}[self.win], self.message)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out.update({
            "uAtlasSize": (float(ATLAS_W), float(ATLAS_H)), "uTile": (float(TW), float(TH)),
            "uSceneSize": size(self.scene), "uFigSize": size(self.figs),
            "uWin0": self.windows[0], "uWin1": self.windows[1], "uWin2": self.windows[2], "uWinY": self.win_y,
            "uSeed": self.seed, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uFlash": self.flash,
            "uSporeT": (now - self.spore_t0) if now - self.spore_t0 < 4.0 else -1.0,
            "uStake": float(self.stake), "uStakeT": now - self.stake_t0,
            "uFox": (float(FOX_CELLS[self.fox_prev]), float(FOX_CELLS[self.fox_pose]), min(1.0, (now - self.fox_t0) / 0.12), 0.0),
        })
        return out

    def overlays(self, t: float):
        th = self.themes[0]
        now = time.monotonic()
        st_t = now - self.state_t0
        dim = 1.0 - 0.4 * max(self.blur)
        name, bet, mult = STAKES[self.stake]
        out = [
            (th["title"], 0.026, 0.5, 0.962, (200, 255, 210), 0.85 * dim),
            (th["subtitle"], 0.016, 0.5, 0.93, (190, 230, 200), 0.6 * dim),
            (f"GUTHABEN  {self.credits} CR      EINSATZ  {name}  {bet} CR  (x{mult})", 0.017, 0.5, 0.028, (190, 210, 200), 0.7 * dim),
        ]
        if now - self.stake_t0 < 1.6:
            a = min(1.0, (1.6 - (now - self.stake_t0)) / 0.6)
            out.append((f"EINSATZ: {name}", 0.03, 0.5, 0.5, (255, 240, 180), a))
        if self.state == slots.ST_RESULT and self.message:
            pulse = 1.0 if self.win == slots.WIN_NONE else 0.8 + 0.2 * math.sin(t * 3.0)
            out.append((self.message, 0.024, 0.5, 0.07, self.message_color, min(1.0, st_t * 2.0) * pulse))
            if self.win in (slots.WIN_JACKPOT, slots.WIN_MEGA):
                out.append(("L I C H T H I R S C H", 0.06, 0.5, 0.82, (255, 230, 120), 0.5 + 0.3 * math.sin(t * 4.0)))
            elif self.win == slots.WIN_BIG:
                out.append(("D E R   W A L D   G I B T", 0.045, 0.5, 0.82, (200, 255, 190), 0.5 + 0.3 * math.sin(t * 3.0)))
        return out
