"""Almanach (Taste 5 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zur Space-Slotmaschine).

Ein protziger Casino-Automat aus dem falschen 1985 (assets/future/almanac_scene.png), die drei Fenster sind die
Walzen, Symbole aus assets/future/almanac_symbols.png (3x3, letztes = Uhr 22:04 = Jackpot). Spiellogik der
Slotmaschine (slots.Controller), Knüppel links/rechts = Einsatz (Cent 1955 = 10, Dollar 1985 = 50, Karte 2015 = 200 $),
Startknopf = Hebel ziehen.
Musik: Gold, Spiegel und Neon im Foto pulsen mit dem Bass, Lauflicht durch die drei Säulen auf den Beat, Höhen =
Funken und Glitzer, Drop = Blitz von oben und die nächste Drehung läuft schneller. Gewinne: klein = Dollarscheine
regnen, groß = Feuerspuren laufen durch das Bild und der Professor tanzt (assets/future/clocktower_figures.png
Reihe 0), Jackpot (22:04 dreifach) = Blitz, die Zeitmaschine fährt durch den Automaten (Reihe 1), alles kippt kurz
nach Schwarzweiß wie 1955 und kommt mit Farbe zurück.
"""
from __future__ import annotations

import logging
import math
import os
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import config as lcfg, wled
from visualizers.scenes import slots

log = logging.getLogger("almanacslots")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
FIGURES = ASSETS / "clocktower_figures.png"        # 8x3 à 192: Reihe 0 Professor 0-7, Reihe 1 Zeitmaschine 8-15
TW, TH = 384, 256
N_SYM = 9
ATLAS_W = N_SYM * TW
ATLAS_H = TH + 4
STAKES = [("CENT 1955", 10, 1), ("DOLLAR 1985", 50, 5), ("KARTE 2015", 200, 20)]   # Name, Einsatz, Gewinnfaktor
FUTURE = {
    "name": "ALMANACH", "sheet": "almanac_symbols.png",
    "title": "ALMANACH CASINO 1985", "subtitle": "DAS FALSCHE 1985. DAS HAUS KENNT DAS ERGEBNIS SCHON.",
    "colors": ((1.00, 0.80, 0.25), (0.95, 0.15, 0.15)),
    "symbols": ["HOVERBOARD", "ALMANACH", "PLUTONIUM", "SKATEBOARD", "KASSETTE", "EINSTEIN", "TURNSCHUH", "FLUX", "22:04"],
    "lose": ["Verloren. Der Almanach hätte es gewusst. Du hast ihn nicht.", "Nichts. Das Haus kennt die Zukunft, du nicht.",
             "Verlust. Das Plutonium ist alle, dein Geld auch.", "Kein Gewinn. Einstein schaut weg.",
             "Nichts. Die Kassette spielt nur noch Rauschen."],
    "near": ["Fast. Das Hoverboard ist über der Linie hängen geblieben.", "Zwei Treffer. Der dritte steckt noch in 1955.",
             "Knapp. Der Fluxkompensator hat gezuckt."],
    "small": ["Kleiner Gewinn. Ein paar Dollar aus dem falschen Jahr.", "Gewonnen. Einstein wedelt mit dem Schwanz."],
    "big": ["Drei gleiche. 1,21 Gigawatt! Der Professor tanzt.", "Gewinn. Feuerspuren auf dem Casinoteppich."],
    "jackpot": ["GROSSER GOTT! 22:04 dreifach. Der Blitz zahlt aus.", "GROSSER GOTT! Die Zeitmaschine kommt. Mit Koffern."],
}


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


def _figures_path() -> Path:
    """Figurenbogen: KITT_ALMANAC_FIGURES (Test, z. B. assets/cyber/oracle_figures.png) oder der Uhrturm-Bogen."""
    env = os.environ.get("KITT_ALMANAC_FIGURES", "").strip()
    if env:
        p = Path(env)
        return p if p.is_absolute() else lcfg.ROOT / p
    return FIGURES


class Controller(slots.Controller):
    def __init__(self, scene_cfg: dict, demo: bool = False):
        super().__init__(scene_cfg, demo)
        self.themes = [FUTURE]
        self.led = ("almanacslots", "almanacslots_win", "almanacslots_jackpot")
        self.theme = 0
        self.next_theme = 0
        self.strip_row = TH
        self.strips = [slots.build_strip(11 + r, r, [FUTURE] * 14) for r in range(slots.N_REELS)]
        self.atlas = np.zeros((ATLAS_H, ATLAS_W, 4), dtype=np.uint8)
        row = _sheet_tiles(ASSETS / FUTURE["sheet"])
        if row is not None:
            self.atlas[:TH] = row
        self.atlas_version = 1
        self._write_strips()
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "almanac_scene.png")
        fig_path = _figures_path()
        self.figs = _load_rgba(fig_path) if fig_path.exists() else None
        if self.figs is None:
            log.info("Figurenbogen %s fehlt: Professor und Zeitmaschine bleiben leer", fig_path)
        self.windows = [tuple(float(v) for v in w) for w in scene_cfg.get("windows", [[0.316, 0.412], [0.447, 0.546], [0.581, 0.678]])]
        self.win_y = tuple(float(v) for v in scene_cfg.get("window_y", [0.414, 0.666]))
        self.stake = 0
        self._apply_stake()
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last_f = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.last_beat = 0.0
        self.step = 0
        self.step_t0 = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.drop_boost = 0.0
        self.bolt_t0 = -100.0          # Blitz von oben (Drop), Alter in uBoltT
        self.bolt_seed = 0.0
        self.sepia = 0.0               # 1 = Schwarzweiß wie 1955 (Jackpot)
        self.prof_pose = 0
        self.prof_prev = 0
        self.prof_t0 = 0.0
        self.stake_t0 = -10.0
        self.stop_t0 = [-10.0] * 3
        self.was_spinning = [False] * 3
        self.result_logged = False
        log.info("Almanach: Szene %s, Symbole %s, Figuren %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if row is not None else "fehlt", "ok" if self.figs is not None else "fehlt")

    def _pick_theme(self) -> int:
        return 0

    def _apply_stake(self) -> None:
        name, bet, mult = STAKES[self.stake]
        self.bet = bet
        self.payout_mult = mult

    def _change_theme(self, d: int) -> None:
        self.stake = (self.stake + d) % len(STAKES)
        self._apply_stake()
        self.stake_t0 = time.monotonic()
        log.info("Einsatz: %s (%d $, x%d)", *STAKES[self.stake])

    def _spin(self, only_reel: int = -1) -> None:
        super()._spin(only_reel)
        if only_reel < 0 and self.drop_boost > 0.0:
            for r in self.reels:
                r.max_speed *= 1.0 + 0.7 * self.drop_boost
            self.drop_boost = 0.0
        self.result_logged = False

    def images(self) -> dict:
        return {"uSpriteTex": (self.atlas, self.atlas_version),
                "uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uSpriteTex", "uSceneTex", "uFigTex", "uAtlasSize", "uSceneSize", "uFigSize", "uTheme",
                "uColA", "uColB", "uReel", "uSpeed", "uState", "uStateT", "uWin", "uWinMask", "uWinLine", "uBlur", "uFade",
                "uStripRow", "uTile", "uWin0", "uWin1", "uWin2", "uWinY", "uSeed", "uBassS", "uMidS", "uHighS", "uEnergy",
                "uLive", "uBeatPulse", "uFlash", "uBoltT", "uBoltSeed", "uSepia", "uStake", "uStakeT", "uFig", "uStep",
                "uStepPhase", "uStopT")

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
            self.step = (self.step + 1) % 3
            self.step_t0 = now
            # Professor: neue Pose auf jeden Beat (Reihe 0, Zellen 0-7)
            self.prof_prev, self.prof_pose, self.prof_t0 = self.prof_pose, (self.prof_pose + self.rng.randint(1, 3)) % 8, now
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
            self.bolt_t0 = now
            self.bolt_seed = self.rng.uniform(1.0, 100.0)
            self.drop_boost = 1.0
            log.info("Drop: Blitz in den Automaten, nächste Drehung schneller")
        self.flash = max(0.0, self.flash - dt / 2.0)
        for i, r in enumerate(self.reels):
            if self.was_spinning[i] and not r.spinning:
                self.stop_t0[i] = now
            self.was_spinning[i] = r.spinning
        # Jackpot: nach dem Blitz kippt das Bild für ein paar Sekunden nach Schwarzweiß (1955) und kommt zurück
        sepia_goal = 0.0
        if self.state == slots.ST_RESULT and self.win >= slots.WIN_JACKPOT:
            st_t = now - self.state_t0
            if 0.7 <= st_t < 4.2:
                sepia_goal = 1.0
        self.sepia += (sepia_goal - self.sepia) * min(1.0, dt / (0.12 if sepia_goal > self.sepia else 1.2))
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
            "uBoltT": (now - self.bolt_t0) if now - self.bolt_t0 < 1.5 else -1.0, "uBoltSeed": self.bolt_seed,
            "uSepia": self.sepia,
            "uStake": float(self.stake), "uStakeT": now - self.stake_t0,
            "uFig": (float(self.prof_prev), float(self.prof_pose), min(1.0, (now - self.prof_t0) / 0.12),
                     1.0 if self.figs is not None else 0.0),
            "uStep": float(self.step), "uStepPhase": min(1.0, (now - self.step_t0) / 0.5),
            "uStopT": tuple(min(9.0, now - st) for st in self.stop_t0),
        })
        return out

    def overlays(self, t: float):
        th = self.themes[0]
        now = time.monotonic()
        st_t = now - self.state_t0
        dim = 1.0 - 0.4 * max(self.blur)
        name, bet, mult = STAKES[self.stake]
        out = [
            (th["title"], 0.026, 0.5, 0.962, (255, 215, 80), 0.85 * dim),
            (th["subtitle"], 0.016, 0.5, 0.93, (255, 120, 90), 0.6 * dim),
            (f"GUTHABEN  {self.credits} $      EINSATZ  {name}  {bet} $  (x{mult})", 0.017, 0.5, 0.028, (230, 210, 170), 0.7 * dim),
        ]
        if now - self.stake_t0 < 1.6:
            a = min(1.0, (1.6 - (now - self.stake_t0)) / 0.6)
            out.append((f"EINSATZ: {name}", 0.03, 0.5, 0.5, (255, 230, 150), a))
        if self.state == slots.ST_RESULT and self.message:
            pulse = 1.0 if self.win == slots.WIN_NONE else 0.8 + 0.2 * math.sin(t * 3.0)
            out.append((self.message, 0.024, 0.5, 0.07, self.message_color, min(1.0, st_t * 2.0) * pulse))
            if self.win in (slots.WIN_JACKPOT, slots.WIN_MEGA):
                out.append(("G R O S S E R   G O T T !", 0.06, 0.5, 0.82, (255, 240, 200), 0.5 + 0.3 * math.sin(t * 4.0)))
            elif self.win == slots.WIN_BIG:
                out.append(("1 , 2 1   G I G A W A T T", 0.045, 0.5, 0.82, (255, 200, 80), 0.5 + 0.3 * math.sin(t * 3.0)))
        return out
