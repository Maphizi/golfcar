"""Pachinko (Taste 5 im Thema CYBERPUNK, Gegenstück zur Space-Slotmaschine).

Neon-Automat in einer Pachinko-Halle (assets/cyber/cyberslots_scene.png), die drei Fenster sind die Walzen, Symbole
aus assets/cyber/cyberslots_symbols.png (3x3, letztes = KI-Kern = Jackpot). Spiellogik der Slotmaschine
(slots.Controller), Knüppel links/rechts = Einsatz (Chip 10, Deck 50, Implant 200 Eddies), Startknopf = drehen.
Musik: Neonröhren und Bildschirme pulsen mit dem Bass, Lauflicht durch die drei Säulen auf den Beat, Höhen = Funken,
Drop = der Automat glitcht und die nächste Drehung läuft schneller. Gewinne: klein = Credits regnen, groß =
Hologramm-Feuerwerk und der Samurai tanzt (assets/cyber/oracle_figures.png), Jackpot = die Halle explodiert in Neon,
Drohnen bringen Geldkoffer (assets/cyber/core_objects.png Zellen 0 und 20).
"""
from __future__ import annotations

import logging
import math
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import config as lcfg, wled
from visualizers.scenes import slots

log = logging.getLogger("cyberslots")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
TW, TH = 384, 256
N_SYM = 9
ATLAS_W = N_SYM * TW
ATLAS_H = TH + 4
STAKES = [("CHIP", 10, 1), ("DECK", 50, 5), ("IMPLANT", 200, 20)]
CYBER = {
    "name": "PACHINKO", "sheet": "cyberslots_symbols.png",
    "title": "PACHINKO SEKTOR 7", "subtitle": "DIE BANK IST EIN KONZERN. DER KONZERN GEWINNT.",
    "colors": ((0.95, 0.20, 0.80), (0.20, 0.85, 1.00)),
    "symbols": ["NEUROCHIP", "DROHNE", "RAMEN", "KATANA", "CYBERDECK", "NEONKATZE", "CREDITCHIP", "CHROMSCHÄDEL", "KI-KERN"],
    "lose": ["Verloren. Die Drohne hat deine Eddies schon abgeholt.", "Nichts. Der Konzern dankt.",
             "Verlust. Der Chromschädel grinst. Er grinst immer.", "Kein Gewinn. Dein Implant meldet: erwartbar.",
             "Nichts. Die Neonkatze hat nicht mal hingesehen."],
    "near": ["Fast. Das Katana hat die Walze gestreift.", "Zwei Treffer. Der dritte hängt im Lag.",
             "Knapp. Der Ramen war noch heiß."],
    "small": ["Kleiner Gewinn. Ein paar Eddies, steuerfrei. Angeblich.", "Gewonnen. Die Katze blinzelt anerkennend."],
    "big": ["Drei gleiche. Die Halle rauscht Beifall.", "Gewinn. Das Hologramm tanzt für dich."],
    "jackpot": ["KI-KERN dreifach. Der Konzern schickt Drohnen. Mit Koffern.", "Jackpot. Sektor 7 gehört heute Nacht dir."],
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
        self.themes = [CYBER]
        self.led = ("cyberslots", "cyberslots_win", "cyberslots_jackpot")
        self.theme = 0
        self.next_theme = 0
        self.strip_row = TH
        self.strips = [slots.build_strip(11 + r, r, [CYBER] * 14) for r in range(slots.N_REELS)]
        self.atlas = np.zeros((ATLAS_H, ATLAS_W, 4), dtype=np.uint8)
        row = _sheet_tiles(ASSETS / "cyberslots_symbols.png")
        if row is not None:
            self.atlas[:TH] = row
        self.atlas_version = 1
        self._write_strips()
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "cyberslots_scene.png")
        self.figs = _load_rgba(ASSETS / "oracle_figures.png")
        self.objs = _load_rgba(ASSETS / "core_objects.png")
        self.windows = [tuple(float(v) for v in w) for w in scene_cfg.get("windows", [[0.344, 0.427], [0.450, 0.546], [0.570, 0.654]])]
        self.win_y = tuple(float(v) for v in scene_cfg.get("window_y", [0.42, 0.645]))
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
        self.glitch_t0 = -100.0
        self.sam_pose = 0
        self.sam_prev = 0
        self.sam_t0 = 0.0
        self.stake_t0 = -10.0
        self.stop_t0 = [-10.0] * 3
        self.was_spinning = [False] * 3
        self.result_logged = False
        log.info("Pachinko: Szene %s, Symbole %s, Figuren %s", "ok" if self.scene is not None else "fehlt",
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
        log.info("Einsatz: %s (%d Eddies, x%d)", *STAKES[self.stake])

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
                "uFigTex": (self.figs if self.figs is not None else self.blank, 1),
                "uObjTex": (self.objs if self.objs is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uSpriteTex", "uSceneTex", "uFigTex", "uObjTex", "uAtlasSize", "uSceneSize", "uFigSize", "uObjSize", "uTheme",
                "uColA", "uColB", "uReel", "uSpeed", "uState", "uStateT", "uWin", "uWinMask", "uWinLine", "uBlur", "uFade",
                "uStripRow", "uTile", "uWin0", "uWin1", "uWin2", "uWinY", "uSeed", "uBassS", "uMidS", "uHighS", "uEnergy",
                "uLive", "uBeatPulse", "uFlash", "uGlitchT", "uStake", "uStakeT", "uSam", "uStep", "uStepPhase", "uStopT")

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
            self.sam_prev, self.sam_pose, self.sam_t0 = self.sam_pose, (self.sam_pose + self.rng.randint(1, 3)) % 8, now
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
            self.glitch_t0 = now
            self.drop_boost = 1.0
            log.info("Drop: Automat glitcht, nächste Drehung schneller")
        self.flash = max(0.0, self.flash - dt / 2.0)
        for i, r in enumerate(self.reels):
            if self.was_spinning[i] and not r.spinning:
                self.stop_t0[i] = now
            self.was_spinning[i] = r.spinning
        if self.state == slots.ST_RESULT and not self.result_logged and self.message:
            self.result_logged = True
            log.info("%s: %s", {0: "Niete", 1: "kleiner Gewinn", 2: "Gewinn", 3: "JACKPOT", 4: "MEGA"}[self.win], self.message)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out.update({
            "uAtlasSize": (float(ATLAS_W), float(ATLAS_H)), "uTile": (float(TW), float(TH)),
            "uSceneSize": size(self.scene), "uFigSize": size(self.figs), "uObjSize": size(self.objs),
            "uWin0": self.windows[0], "uWin1": self.windows[1], "uWin2": self.windows[2], "uWinY": self.win_y,
            "uSeed": self.seed, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uFlash": self.flash,
            "uGlitchT": (now - self.glitch_t0) if now - self.glitch_t0 < 1.5 else -1.0,
            "uStake": float(self.stake), "uStakeT": now - self.stake_t0,
            "uSam": (float(self.sam_prev), float(self.sam_pose), min(1.0, (now - self.sam_t0) / 0.12), 0.0),
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
            (th["title"], 0.026, 0.5, 0.962, (255, 80, 220), 0.85 * dim),
            (th["subtitle"], 0.016, 0.5, 0.93, (120, 220, 255), 0.6 * dim),
            (f"GUTHABEN  {self.credits} €$      EINSATZ  {name}  {bet} €$  (x{mult})", 0.017, 0.5, 0.028, (180, 200, 230), 0.7 * dim),
        ]
        if now - self.stake_t0 < 1.6:
            a = min(1.0, (1.6 - (now - self.stake_t0)) / 0.6)
            out.append((f"EINSATZ: {name}", 0.03, 0.5, 0.5, (255, 200, 255), a))
        if self.state == slots.ST_RESULT and self.message:
            pulse = 1.0 if self.win == slots.WIN_NONE else 0.8 + 0.2 * math.sin(t * 3.0)
            out.append((self.message, 0.024, 0.5, 0.07, self.message_color, min(1.0, st_t * 2.0) * pulse))
            if self.win in (slots.WIN_JACKPOT, slots.WIN_MEGA):
                out.append(("K I - K E R N", 0.06, 0.5, 0.82, (120, 240, 255), 0.5 + 0.3 * math.sin(t * 4.0)))
            elif self.win == slots.WIN_BIG:
                out.append(("S E K T O R   7   Z A H L T", 0.045, 0.5, 0.82, (255, 120, 240), 0.5 + 0.3 * math.sin(t * 3.0)))
        return out
