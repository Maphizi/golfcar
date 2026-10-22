"""Fluxkompensator (Taste 3 im Thema ZURÜCK IN DIE ZUKUNFT, Gegenstück zum Schwarzen Loch).

Erfinderwerkstatt bei Nacht (assets/future/flux_scene.png), in der Mitte der leuchtende Fluxkompensator: ein Y aus
drei weißblauen Lichtröhren. Die Röhren werden beim Start im Foto erkannt (helle weißblaue Stellen um `center`),
daraus Knotenpunkt und drei Arme (uCenter, uArm0..2) für Lichtstöße, Halo und Blitze.
Knüppel links/rechts wirft ein Objekt aus den Epochen (assets/future/flux_objects.png, 6x4 à 192: Hoverboard,
Almanach, Skateboard, E-Gitarre, Plutoniumkoffer ...) von dieser Seite hinein: es wird angezogen, zieht zwei
Feuerspuren hinter sich her, dehnt sich zur Zeitschleife um das Y und löst sich in Blitze auf, die in die drei Arme
laufen (40-60 s). OBEN = Gewitter (20 s: Blitze schlagen von oben in die Kabel ein, Y flackert, Regen am Fenster,
Schleifen tanzen). UNTEN = Paradoxon (8 s: alles kommt rückwärts wieder heraus, das Fahrerfoto erscheint als
Polaroid und verblasst, Beats holen es zurück). Startknopf = 1,21 Gigawatt (Weißblitz, Lichtbögen über alle Kabel,
Bild zittert, kurz Negativ). Kippschalter = Nahaufnahme auf das Y.
Bass = Arme pulsen + Bild bebt, Beat = Lichtstoß durch die Arme + Ringe, Höhen = Funken an den Kabeln, Mitten =
Oszilloskop-Wellen, Drop = Blitz + Farbwechsel des Y + Zeitschleifen laufen rückwärts. Stille = Y glimmt nur.
Fehlt der Objektbogen, kann zum Testen KITT_FLUX_OBJECTS auf einen anderen 6x4-Bogen zeigen.
"""
from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

import numpy as np
import pygame

from visualizers.engine import images

from launcher import wled

log = logging.getLogger("flux")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "future"
PHOTO = Path(__file__).resolve().parents[2] / "assets" / "taxi" / "future" / "driver.png"
SLOTS = 3
THROW_SECONDS = (40.0, 60.0)
EJECT_SECONDS = 8.0
EJECT_BURST_AT = 1.2
STORM_SECONDS = 20.0
OVER_SECONDS = 2.5
BOLTS = 3
OBJECT_NAMES = ["HOVERBOARD", "SPORTALMANACH", "SKATEBOARD", "E-GITARRE", "PLUTONIUMKOFFER", "WALKIE-TALKIE", "KASSETTE",
                "HUND", "COWBOYHUT", "MODELLZUG", "WECKER", "VIDEOKAMERA", "BRIEF VON 1885", "TURNSCHUH", "LIMOFLASCHE",
                "JUKEBOX", "FAHRRAD", "SONNENBRILLE", "BLITZABLEITER", "POLAROID", "PIZZA", "MIKROWELLE",
                "SATELLITENSCHÜSSEL", "RADIO"]


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL) aus dem npy-Cache (visualizers.engine.images)."""
    return images.load_rgba(path)


def _detect_y(img: np.ndarray, center: tuple, radius: float):
    """Sucht die weißblauen Röhren des Y um `center` und liefert (Knotenpunkt uv, [(dir_x, dir_y, Länge)] x3)
    in isotropen Koordinaten (x mit Bildseitenverhältnis gestreckt, y nach oben) oder None."""
    try:
        h, w = img.shape[:2]
        asp = w / h
        x0, x1 = max(0, int(w * (center[0] - 2.2 * radius))), min(w, int(w * (center[0] + 2.2 * radius)))
        y0, y1 = max(0, int(h * (center[1] - 2.2 * radius))), min(h, int(h * (center[1] + 2.2 * radius)))
        sub = img[y0:y1, x0:x1, :3].astype(np.float32) / 255.0
        mask = (sub.min(axis=2) > 0.8) & (sub[..., 2] >= sub[..., 0])
        ys, xs = np.nonzero(mask)
        if len(xs) < 200:
            return None
        px, py = (x0 + xs) / w, (y0 + ys) / h
        cx, cy = px.mean(), py.mean()
        qx, qy = (px - cx) * asp, py - cy
        keep = np.hypot(qx, qy) < 1.7 * radius          # Streulicht am Rahmen weglassen
        qx, qy = qx[keep], qy[keep]
        cx2, cy2 = cx + qx.mean() / asp, cy + qy.mean()
        qx, qy = qx - qx.mean(), qy - qy.mean()
        ang = np.degrees(np.arctan2(qy, qx)) % 360.0
        lines = []
        for lo, hi in ((95.0, 180.0), (0.0, 85.0), (200.0, 340.0)):   # oben links, oben rechts, unten
            m = (ang >= lo) & (ang < hi)
            if m.sum() < 60:
                return None
            pts = np.stack([qx[m], qy[m]], 1)
            mu = pts.mean(0)
            _, vec = np.linalg.eigh(np.cov((pts - mu).T))
            d = vec[:, 1]
            if float(np.dot(d, mu)) < 0.0:
                d = -d
            lines.append((mu, d, pts))
        a_mat, b_vec = np.zeros((2, 2)), np.zeros(2)
        for mu, d, _ in lines:
            proj = np.eye(2) - np.outer(d, d)
            a_mat += proj
            b_vec += proj @ mu
        junction = np.linalg.solve(a_mat, b_vec)
        arms = []
        for mu, d, pts in lines:
            length = float(np.percentile((pts - junction) @ d, 98))
            arms.append((float(d[0]), float(d[1]), max(0.3 * radius, length)))
        return (float(cx2 + junction[0] / asp), float(cy2 + junction[1])), arms
    except Exception as exc:
        log.warning("Y-Erkennung fehlgeschlagen: %s", exc)
        return None


class Throw:
    def __init__(self, rng: random.Random, cell: int, side: float, now: float):
        self.cell = cell
        self.side = side
        self.t0 = now
        self.dur = rng.uniform(*THROW_SECONDS)
        self.swirl = rng.choice((-1.0, 1.0))
        self.seed = rng.uniform(1.0, 200.0)
        self.y0 = rng.uniform(-0.15, 0.3)
        self.name = OBJECT_NAMES[cell % len(OBJECT_NAMES)]
        self.spin0 = 0.0
        self.reverse_t0: float | None = None
        self.reverse_p = 0.0

    def progress(self, now: float) -> float:
        if self.reverse_t0 is not None:
            return self.reverse_p - (now - self.reverse_t0) / self.dur * 4.0
        return (now - self.t0) / self.dur

    def reverse(self, now: float) -> None:
        if self.reverse_t0 is None:
            self.reverse_p = self.progress(now)
            self.reverse_t0 = now

    def done(self, now: float) -> bool:
        p = self.progress(now)
        return p >= 1.0 or p < -0.05


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "flux_scene.png")
        obj_path = Path(os.environ.get("KITT_FLUX_OBJECTS") or (ASSETS / "flux_objects.png"))
        self.objects = _load_rgba(obj_path) if obj_path.exists() else None
        if self.objects is None:
            log.warning("Objektbogen %s fehlt - Würfe bleiben unsichtbar (zum Testen KITT_FLUX_OBJECTS=<6x4-Bogen>)", obj_path)
        self.photo = _load_rgba(PHOTO)
        cfg_center = tuple(float(v) for v in scene_cfg.get("center", [0.5, 0.55]))
        self.radius = float(scene_cfg.get("radius", 0.12))
        self.center = cfg_center
        self.arms = [(-0.8, 0.6, 1.5 * self.radius), (0.76, 0.65, 1.15 * self.radius), (0.0, -1.0, 1.2 * self.radius)]
        found = _detect_y(self.scene, cfg_center, self.radius) if self.scene is not None else None
        if found:
            self.center, self.arms = found
            log.info("Y erkannt: Knoten (%.3f, %.3f), Arme %s", self.center[0], self.center[1],
                     ", ".join(f"({a[0]:.2f}, {a[1]:.2f}) x {a[2]:.3f}" for a in self.arms))
        else:
            log.info("Y nicht erkannt, nehme [scenes.flux] center %s", cfg_center)
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.last_beat = 0.0
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.hue = 0.0
        self.hue_target = 0.0
        self.spin_t = 0.0
        self.spin_dir = 1.0
        self.spin_rate = 0.0
        self.rings: list[float] = []
        self.throws: list[Throw | None] = [None] * SLOTS
        self.last_cells: list[int] = []
        self.storm_t0: float | None = None
        self.bolts: list[tuple[float, float, float]] = []      # (Zeit, x, Seed)
        self.next_bolt = 0.0
        self.eject_t0: float | None = None
        self.eject_burst_done = False
        self.over_t0 = -10.0
        self.fade = 0.0
        self.polaroid = 0.0
        self.zoom = 0.0
        self.zoom_target = 0.0
        self.led_back_at: float | None = None
        self.demo_next = time.monotonic() + 3.0
        log.info("Fluxkompensator: Szene %s, Objekte %s, Foto %s", "ok" if self.scene is not None else "fehlt",
                 "ok" if self.objects is not None else "fehlt", "ok" if self.photo is not None else "fehlt")

    # -- Aktionen ----------------------------------------------------------
    def throw(self, side: str) -> None:
        now = time.monotonic()
        slot = next((i for i, th in enumerate(self.throws) if th is None), None)
        if slot is None:
            slot = max(range(SLOTS), key=lambda i: self.throws[i].progress(now))
            if self.throws[slot].progress(now) < 0.6:
                return
        pool = [c for c in range(24) if c not in self.last_cells[-6:]]
        cell = self.rng.choice(pool)
        self.last_cells.append(cell)
        self.throws[slot] = Throw(self.rng, cell, -1.0 if side == "left" else 1.0, now)
        self.throws[slot].spin0 = self.spin_t
        self._led_event("flux_throw", now + 3.0)
        log.info("Geworfen: %s von %s", self.throws[slot].name, side)

    def storm(self) -> None:
        now = time.monotonic()
        if self.storm_t0 is not None and now - self.storm_t0 < 5.0:
            return
        self.storm_t0 = now
        self.next_bolt = now + 0.6
        self._led_event("flux_storm", now + STORM_SECONDS)
        log.info("Gewitter zieht auf")

    def eject(self) -> None:
        now = time.monotonic()
        if self.eject_t0 is not None and now - self.eject_t0 < EJECT_SECONDS:
            return
        self.eject_t0 = now
        self.eject_burst_done = False
        self.fade = 0.0
        self._led_event("flux_eject", now + EJECT_SECONDS)
        log.info("Paradoxon: alles kommt rückwärts heraus, das Foto verblasst")

    def overload(self) -> None:
        now = time.monotonic()
        if now - self.over_t0 < OVER_SECONDS:
            return
        self.over_t0 = now
        self.rings += [now, now + 0.15, now + 0.3]
        self._led_event("flux_overload", now + OVER_SECONDS)
        log.info("1,21 Gigawatt!")

    def _bolt(self, now: float) -> None:
        self.bolts.append((now, self.rng.uniform(0.3, 0.75), self.rng.uniform(1.0, 50.0)))
        self.bolts = self.bolts[-BOLTS:]
        self.rings.append(now)

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.spin_dir = -self.spin_dir
        self.hue_target = self.rng.choice([-1.2, -0.7, 0.9, 1.6, 2.4])   # weißblau -> orange / violett / grün
        self.rings += [now, now + 0.25, now + 0.5]
        log.info("Drop: das Y wechselt die Farbe, die Zeitschleifen laufen rückwärts")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.throw("left")
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.throw("right")
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.storm()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.eject()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.overload()
        elif ev.key == pygame.K_SPACE:
            self.zoom_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.zoom_target = 0.0

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        return {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1),
                "uObjTex": (self.objects if self.objects is not None else self.blank, 1),
                "uPhotoTex": (self.photo if self.photo is not None else self.blank, 1)}

    def uniform_names(self):
        names = ["uSceneTex", "uObjTex", "uPhotoTex", "uSceneSize", "uObjSize", "uPhotoSize", "uSeed", "uCenter", "uRadius",
                 "uArm0", "uArm1", "uArm2", "uBassS", "uMidS", "uHighS", "uEnergy", "uLive", "uBeatPulse", "uBeatStep",
                 "uFlash", "uHue", "uSpinT", "uSpinRate", "uZoom", "uStormT", "uEjectT", "uOverT", "uFade", "uPolaroid"]
        names += [f"uRing{i}" for i in range(6)]
        names += [f"uBolt{i}" for i in range(BOLTS)]
        for i in range(SLOTS):
            names += [f"uThrow{i}", f"uThrowPar{i}"]
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
        self.mid_s += (mid - self.mid_s) * min(1.0, dt / 0.3)
        self.high_s += (high - self.high_s) * min(1.0, dt / 0.1)
        self.live_s += (live - self.live_s) * min(1.0, dt / (0.5 if live else 3.0))
        e_fast = self.energy + (rms - self.energy) * min(1.0, dt / 0.3)
        self.energy += (rms - self.energy) * min(1.0, dt / 2.5)
        storming = self.storm_t0 is not None
        is_beat = False
        if beat > 0.5 and now - self.last_beat > 0.25:
            is_beat = True
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            self.rings.append(now)
            self.spin_t += 0.3 * self.spin_dir
            if storming and now - self.storm_t0 > 0.5 and self.rng.random() < 0.3 and (not self.bolts or now - self.bolts[-1][0] > 0.8):
                self._bolt(now)
        self.beat_pulse = max(0.0, self.beat_pulse - dt / 0.4)
        self.spin_rate = self.spin_dir * (0.3 + 2.0 * self.bass_s + 0.5 * self.energy) * (3.0 if storming else 1.0)
        self.spin_t += dt * self.spin_rate
        if abs(self.spin_t) > 100000.0:                 # sehr selten: Nullpunkt verschieben, Würfe mitnehmen
            for th in self.throws:
                if th is not None:
                    th.spin0 -= self.spin_t
            self.spin_t = 0.0
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
        self.hue += (self.hue_target - self.hue) * min(1.0, dt / 1.5)
        if now - self.last_drop > 12.0:
            self.hue_target = 0.0
        self.rings = [r for r in self.rings if now - r < 3.0][-6:]
        self.zoom += (self.zoom_target - self.zoom) * min(1.0, dt / 1.8)
        # Gewitter: Blitze nach Plan, Beats schlagen zusätzlich ein
        storm_t = -1.0
        if storming:
            storm_t = now - self.storm_t0
            if storm_t >= STORM_SECONDS:
                self.storm_t0 = None
                storm_t = -1.0
            elif now >= self.next_bolt:
                self._bolt(now)
                self.next_bolt = now + self.rng.uniform(1.2, 3.5)
        # Paradoxon: Anschwellen, Ausbruch (Würfe rückwärts), Polaroid verblasst, Beats holen es zurück
        eject_t = -1.0
        if self.eject_t0 is not None:
            eject_t = now - self.eject_t0
            if eject_t >= EJECT_SECONDS:
                self.eject_t0 = None
                eject_t = -1.0
            elif eject_t >= EJECT_BURST_AT and not self.eject_burst_done:
                self.eject_burst_done = True
                for th in self.throws:
                    if th is not None:
                        th.reverse(now)
                self.rings += [now, now + 0.2, now + 0.4, now + 0.6]
        if eject_t >= 0.0:
            self.polaroid += (1.0 - self.polaroid) * min(1.0, dt / 0.6)
            self.fade = min(1.0, self.fade + dt / 5.5)
            if is_beat:
                self.fade = max(0.0, self.fade - 0.22)
        else:
            self.polaroid = max(0.0, self.polaroid - dt / 1.5)
            self.fade = max(0.0, self.fade - dt / 1.5)
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async("flux")
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "storm", "eject", "over", "drop"))
            {"left": lambda: self.throw("left"), "right": lambda: self.throw("right"), "storm": self.storm,
             "eject": self.eject, "over": self.overload, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 9.0
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (1.0, 1.0)
        out = {
            "uSceneSize": size(self.scene), "uObjSize": size(self.objects), "uPhotoSize": size(self.photo), "uSeed": self.seed,
            "uCenter": self.center, "uRadius": self.radius, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s,
            "uEnergy": self.energy, "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step),
            "uFlash": self.flash, "uHue": self.hue, "uSpinT": self.spin_t, "uSpinRate": self.spin_rate, "uZoom": self.zoom,
            "uStormT": storm_t,
            "uEjectT": eject_t, "uOverT": (now - self.over_t0) if now - self.over_t0 < OVER_SECONDS else -1.0,
            "uFade": self.fade, "uPolaroid": self.polaroid,
        }
        for i, arm in enumerate(self.arms):
            out[f"uArm{i}"] = (arm[0], arm[1], arm[2], 0.0)
        for i in range(6):
            out[f"uRing{i}"] = max(0.0, now - self.rings[i]) if i < len(self.rings) else 99.0
        for i in range(BOLTS):
            if i < len(self.bolts):
                b = self.bolts[i]
                out[f"uBolt{i}"] = (now - b[0], b[1], b[2], 0.0)
            else:
                out[f"uBolt{i}"] = (99.0, 0.5, 1.0, 0.0)
        for i, th in enumerate(self.throws):
            if th is not None and th.done(now):
                if th.reverse_t0:
                    log.info("%s kommt rückwärts zurück", th.name)
                else:
                    log.info("%s in Blitze aufgelöst", th.name)
                    self.rings += [now, now + 0.2]        # Lichtstoß durch die Arme
                self.throws[i] = th = None
            if th is None:
                out[f"uThrow{i}"] = (0.0, 0.0, 0.0, 0.0)
                out[f"uThrowPar{i}"] = (0.0, 0.0, 0.0, 0.0)
            else:
                out[f"uThrow{i}"] = (max(0.0, min(1.0, th.progress(now))), float(th.cell), th.side, th.seed)
                out[f"uThrowPar{i}"] = (th.swirl * th.dur, 1.0 if th.reverse_t0 else 0.0, th.y0, th.spin0)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = [("FLUXKOMPENSATOR   1,21 GW", 0.02, 0.5, 0.95, (170, 210, 255), 0.55)]
        y = 0.05
        for th in self.throws:
            if th is None:
                continue
            p = th.progress(now)
            a = 0.8 * min(1.0, max(0.0, p) * 8.0) * min(1.0, (1.0 - p) * 6.0)
            if th.reverse_t0 is not None:
                label = f"{th.name}  -  KOMMT RÜCKWÄRTS ZURÜCK"
            elif p > 0.78:
                label = f"{th.name}  -  LÖST SICH IN BLITZE AUF"
            elif p > 0.2:
                label = f"{th.name}  -  {int(p * 100):02d} % IN DER ZEITSCHLEIFE"
            else:
                label = f"{th.name}  -  WIRD ANGEZOGEN"
            out.append((label, 0.018, 0.5, y, (255, 190, 110), a))
            y += 0.035
        if self.storm_t0 is not None:
            st = now - self.storm_t0
            a = min(1.0, st / 0.6) * min(1.0, (STORM_SECONDS - st) / 1.5)
            out.append(("G E W I T T E R", 0.028, 0.5, 0.9, (190, 210, 255), 0.6 * a))
        if self.eject_t0 is not None:
            et = now - self.eject_t0
            a = min(1.0, et / 0.6) * min(1.0, (EJECT_SECONDS - et) / 1.5)
            out.append(("PARADOXON  -  DAS FOTO VERBLASST", 0.04, 0.5, 0.5, (235, 200, 150), 0.85 * a))
        if now - self.over_t0 < 1.4:
            out.append(("1,21 GIGAWATT!!!", 0.06, 0.5, 0.5, (255, 255, 255), 1.0 - (now - self.over_t0) / 1.4))
        return out
