"""Dachterrasse (Taste 6 im Thema CYBERPUNK, Gegenstück zum Lagerfeuer / Herzbaum).

Blick von einer Dachterrasse über die Neon-Megacity. Kern des Modus sind sieben Lichtzustände derselben Ansicht:
das Grundbild assets/cyber/rooftop_scene.png (Zustand 0) und assets/cyber/rooftop_light_1..6.png (Zustände 1..6,
siehe LIGHT_NAMES: Blackout, roter Alarm, Säure, Überlast, nur Werbung, Blitzschlag). Die Stadt spielt verrückt zum Beat: auf Beats schneidet sie hart für 1-3 Beats in einen anderen
Lichtzustand und zurück (uLightA = Grund, uLightB = Zustand, uLightMix hart 0/1 mit 60 ms Überblendung); bei hoher
Energie wechselt der Zustand auf jedem Beat, bei ruhiger Musik nur auf jedem zweiten, bei Stille bleibt das Grundbild
mit leichtem Flackern der Werbeflächen. Jedes Wetter (Knüppel links/rechts, wandert sonst alle cycle_minutes) hat
seinen Heimzustand (Regen = 5 nur Werbung, Nebel = 1 Blackout abgedunkelt, Säure = 3, Asche = 2 roter Alarm), der
als Grundbild mit dem Originalfoto gemischt wird (uGroundMix, Anteil WEATHER_HOME_MIX); das Originalfoto hat einen etwas
anderen Ausschnitt und wird per uBaseFit auf die Lichtbilder gelegt.
Bass = Werbeflächen pulsen, Höhen = Teilchen/Regen (assets/cyber/rooftop_particles.png 8x3 à 160: Reihe 0 Tropfen/
Funken, 1 Blüten/Konfetti, 2 Schnee/Asche), Mitten = Verkehr, Beats = Lichtwellen durch die Türme + Suchscheinwerfer.
OBEN = Feuerwerk, UNTEN = Stromausfall (14 s, Zustand 1 als Basis, Blöcke gehen aus, Beats holen blockweise zufällige
Zustände zurück, am Ende knallt alles auf Überlast), Startknopf = EMP (10 s, Welle vom Zentrum, dahinter alles aus, Flackern,
Rückkehr blockweise mit den Beats; kommt bei Energie > 0.4 auch von selbst alle 90-180 s), Drop = Blitz + Feuerwerk +
Gewitterbild, Kippschalter = Blick über das Geländer nach unten.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pygame

from launcher import wled

log = logging.getLogger("rooftop")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "cyber"
WEATHER = ["REGEN", "NEBEL", "SÄUREREGEN", "ASCHE"]
WEATHER_LED = ["rooftop_rain", "rooftop_fog", "rooftop_acid", "rooftop_ash"]
WEATHER_HOME = [5, 1, 3, 2]                    # Heimzustand je Wetter (Index in die Lichtbilder, 1..6)
WEATHER_HOME_MIX = [0.5, 0.55, 0.7, 0.6]       # Anteil des Heimzustands im Grundbild (Nebel: Blackout abgedunkelt)
# Lichtzustände 1..6 (rooftop_light_N.png), 0 = Grundbild rooftop_scene.png
LIGHT_NAMES = [
    "BLACKOUT",         # 1: totaler Ausfall, Stadt als dunkle Silhouette, nur wenige rote Notlichter und Flieger
    "ROTER ALARM",      # 2: alles rot, rote Suchscheinwerfer über den Türmen, roter Dunst
    "SÄURE",            # 3: giftgrün, grüne Wolken, grüne Tafeln und Fenster, Neon-Schild grün
    "ÜBERLAST",         # 4: alles gleißend weiß-gold, überbelichtet, Lichthöfe
    "NUR WERBUNG",      # 5: nur die Werbeflächen in Magenta/Cyan, alle Fenster dunkel
    "BLITZSCHLAG",      # 6: Blitz schlägt in den höchsten Turm, Stadt blau-weiß
]
N_LIGHTS = 6
FIREWORK_SECONDS = 8.0
BLACKOUT_SECONDS = 14.0
EMP_SECONDS = 10.0
EMP_RETURN_FROM = 3.5                          # ab hier zählen Beats die Blöcke zurück
CUT_FADE = 0.06                                # Überblendung der Beat-Schnitte (s)
N_PULSES = 6
# Grundbild (3:2, anderer Ausschnitt) auf die Lichtbilder (16:9) gelegt: uv_base = (uv - 0.5) * (sx, sy) + 0.5 + (ox, oy)
BASE_FIT = (0.995, 0.89, 0.0, 0.0525)


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


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.scene = _load_rgba(ASSETS / "rooftop_scene.png")
        self.lights = [_load_rgba(ASSETS / f"rooftop_light_{i + 1}.png") for i in range(N_LIGHTS)]
        self.particles = _load_rgba(ASSETS / "rooftop_particles.png")
        self.cycle = float(scene_cfg.get("cycle_minutes", 5.0)) * 60.0
        self.skyline = float(scene_cfg.get("skyline", 0.42))               # y, ab der die Stadt beginnt (Geländer darunter)
        fit = scene_cfg.get("base_fit", BASE_FIT)
        self.base_fit = tuple(float(v) for v in fit) if len(fit) == 4 else BASE_FIT
        self.home_mix = float(scene_cfg.get("home_mix", 1.0))              # Faktor auf WEATHER_HOME_MIX
        auto = scene_cfg.get("emp_auto", [90.0, 180.0])
        self.emp_auto = (float(auto[0]), float(auto[1]))
        self.emp_min_energy = float(scene_cfg.get("emp_min_energy", 0.4))
        self.weather = float(scene_cfg.get("start_weather", self.rng.randrange(4)))
        self.weather_target: float | None = None
        self.weather_shown = int(self.weather) % 4
        self.weather_t0 = -10.0
        self.seed = self.rng.uniform(1.0, 100.0)
        self.last = time.monotonic()
        self.bass_s = self.mid_s = self.high_s = 0.0
        self.energy = 0.0
        self.live_s = 0.0
        self.beat_pulse = 0.0
        self.beat_step = 0
        self.beat_count = 0
        self.last_beat = 0.0
        self.beat_times: list[float] = []
        self.pulses: list[float] = []
        self.quiet_since: float | None = None
        self.drop_armed = False
        self.last_drop = -100.0
        self.flash = 0.0
        self.hue = 0.0
        self.hue_target = 0.0
        # Lichtzustände: Grund (Heimzustand des Wetters) und Beat-Schnitt
        self.ground_a = WEATHER_HOME[self.weather_shown]
        self.ground_mix = 0.0
        self.cut_state = 0                     # 0 = kein Schnitt, sonst 1..6
        self.cut_mix = 0.0
        self.cut_t0 = -100.0
        self.cut_until = -100.0
        self.cut_last_state = 0
        self.firework_t0 = -100.0
        self.firework_seed = 0.0
        self.blackout_t0 = -100.0
        self.blackout_beats = 0
        self.emp_t0 = -100.0
        self.emp_beats = 0
        self.emp_seed = 0.0
        self.emp_next = time.monotonic() + self.rng.uniform(*self.emp_auto)
        self.lightning_t0 = -100.0
        self.lightning_x = 0.5
        self.search_t = 0.0
        self.traffic_t = 0.0
        self.look = 0.0
        self.look_target = 0.0
        self.led_back_at: float | None = None
        self.led_chain: tuple[str, float] | None = None
        self.demo_next = time.monotonic() + 4.0
        wled.apply_mode_async(WEATHER_LED[self.weather_shown])
        missing = [i + 1 for i, img in enumerate(self.lights) if img is None]
        log.info("Dachterrasse: Szene %s, Lichtbilder %s, Teilchen %s, Wetter %s", "ok" if self.scene is not None else "fehlt",
                 ("fehlen: %s" % missing) if missing else "ok", "ok" if self.particles is not None else "fehlt",
                 WEATHER[self.weather_shown])

    # -- Aktionen ----------------------------------------------------------
    def change_weather(self, d: int) -> None:
        cur = int(round(self.weather_target if self.weather_target is not None else self.weather)) % 4
        self.weather_target = float((cur + d) % 4)
        while self.weather_target - self.weather > 2.0:
            self.weather_target -= 4.0
        while self.weather_target - self.weather < -2.0:
            self.weather_target += 4.0
        log.info("Wetter: %s", WEATHER[int(self.weather_target) % 4])

    def fireworks(self) -> None:
        now = time.monotonic()
        if now - self.firework_t0 < 2.0:
            return
        self.firework_t0 = now
        self.firework_seed = self.rng.uniform(1.0, 100.0)
        self._led_event("rooftop_fireworks", now + FIREWORK_SECONDS)
        log.info("Feuerwerk")

    def blackout(self) -> None:
        now = time.monotonic()
        if now - self.blackout_t0 < 3.0 or now - self.emp_t0 < EMP_SECONDS:
            return
        self.blackout_t0 = now
        self.blackout_beats = 0
        self._end_cut()
        self._led_event("rooftop_blackout", now + BLACKOUT_SECONDS)
        log.info("Stromausfall")

    def emp(self) -> None:
        now = time.monotonic()
        if now - self.emp_t0 < 3.0 or now - self.blackout_t0 < BLACKOUT_SECONDS:
            return
        self.emp_t0 = now
        self.emp_beats = 0
        self.emp_seed = self.rng.uniform(1.0, 100.0)
        self.emp_next = now + self.rng.uniform(*self.emp_auto)
        self._end_cut()
        self.flash = max(self.flash, 0.8)
        self._led_event("rooftop_lightning", now + EMP_SECONDS)
        self.led_chain = ("rooftop_blackout", now + 1.5)
        log.info("EMP")

    def lightning(self) -> None:
        now = time.monotonic()
        if now - self.lightning_t0 < 0.8:
            return
        self.lightning_t0 = now
        self.lightning_x = self.rng.uniform(0.2, 0.8)
        self._led_event("rooftop_lightning", now + 1.5)

    def _led_event(self, profile: str, back_at: float) -> None:
        wled.apply_mode_async(profile)
        self.led_back_at = back_at
        self.led_chain = None

    def _drop(self, now: float) -> None:
        self.flash = 1.0
        self.lightning()
        self.hue_target = self.rng.choice([-1.5, -0.8, 0.8, 1.5, 2.2])
        self.firework_t0 = now
        self.firework_seed = self.rng.uniform(1.0, 100.0)
        if not self._event_active(now):
            self._start_cut(now, 6, beats=2)   # Gewitterbild zum Blitz
        log.info("Drop: Blitz, Werbeflächen wechseln, Feuerwerk, Gewitter-Schnitt")

    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.change_weather(-1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.change_weather(+1)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            self.fireworks()
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.blackout()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.emp()
        elif ev.key == pygame.K_SPACE:
            self.look_target = 1.0
        elif ev.key == pygame.K_BACKSPACE:
            self.look_target = 0.0

    # -- Beat-Schnitte -----------------------------------------------------
    def _event_active(self, now: float) -> bool:
        return now - self.blackout_t0 < BLACKOUT_SECONDS or now - self.emp_t0 < EMP_SECONDS

    def _beat_interval(self) -> float:
        d = [b - a for a, b in zip(self.beat_times, self.beat_times[1:]) if 0.25 <= b - a <= 1.5]
        if not d:
            return 0.5
        d.sort()
        return d[len(d) // 2]

    def _pick_state(self, avoid: tuple[int, ...]) -> int:
        pool = [i for i in range(1, N_LIGHTS + 1) if i not in avoid and self.lights[i - 1] is not None]
        if not pool:
            pool = [i for i in range(1, N_LIGHTS + 1) if self.lights[i - 1] is not None] or [self.ground_a]
        return self.rng.choice(pool)

    def _start_cut(self, now: float, state: int, beats: int) -> None:
        self.cut_state = state
        self.cut_last_state = state
        self.cut_t0 = now
        self.cut_until = now + self._beat_interval() * beats * 0.95

    def _end_cut(self) -> None:
        self.cut_state = 0
        self.cut_until = -100.0

    def _on_beat(self, now: float) -> None:
        """Die Stadt schneidet zum Beat in einen anderen Lichtzustand: ruhig = jeder zweite Beat, wild = jeder Beat."""
        if self._event_active(now):
            return
        wild = self.energy > 0.45
        if self.cut_state:
            if wild:                                                     # wild: Zustand wechselt auf jedem Beat
                self._start_cut(now, self._pick_state((self.ground_a, self.cut_state)), 1)
            return
        if wild:
            chance, beats = 0.9, 1
        elif self.energy > 0.2:
            chance, beats = 0.55, self.rng.randint(1, 3)
        else:
            if self.beat_count % 2:                                      # ruhig: nur jeder zweite Beat
                return
            chance, beats = 0.5, self.rng.randint(1, 2)
        if self.rng.random() < chance:
            self._start_cut(now, self._pick_state((self.ground_a, self.cut_last_state)), beats)

    # -- Engine ------------------------------------------------------------
    def images(self) -> dict:
        out = {"uSceneTex": (self.scene if self.scene is not None else self.blank, 1)}
        for i, img in enumerate(self.lights):
            out[f"uLight{i}Tex"] = (img if img is not None else self.blank, 1)
        out["uPartTex"] = (self.particles if self.particles is not None else self.blank, 1)
        return out

    def uniform_names(self):
        return ("uSceneTex", "uLight0Tex", "uLight1Tex", "uLight2Tex", "uLight3Tex", "uLight4Tex", "uLight5Tex", "uPartTex",
                "uSceneSize", "uLight0Size", "uLight1Size", "uLight2Size", "uLight3Size", "uLight4Size", "uLight5Size",
                "uPartSize", "uBaseFit", "uLightA", "uLightB", "uLightMix", "uGroundMix", "uCutT",
                "uSeed", "uSkyline", "uWeather", "uBassS", "uMidS", "uHighS",
                "uEnergy", "uLive", "uBeatPulse", "uBeatStep", "uFlash", "uHue", "uFireT", "uFireSeed", "uBlackT",
                "uBlackBeats", "uEmpT", "uEmpBeats", "uEmpSeed", "uLightT", "uLightX", "uSearchT", "uTrafficT", "uLook",
                "uPulseA", "uPulseB")

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
        in_blackout = now - self.blackout_t0 < BLACKOUT_SECONDS
        in_emp = now - self.emp_t0 < EMP_SECONDS
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_pulse = 1.0
            self.beat_step = (self.beat_step + 1) % 8
            self.beat_count += 1
            self.beat_times = (self.beat_times + [now])[-8:]
            self.pulses = (self.pulses + [now])[-N_PULSES:]
            if in_blackout:
                self.blackout_beats += 1
            if in_emp and now - self.emp_t0 >= EMP_RETURN_FROM:
                self.emp_beats += 1
            self._on_beat(now)
        if not live and now - self.last_beat > 2.5:
            self.last_beat = now
            self.pulses = (self.pulses + [now])[-N_PULSES:]
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
            self._drop(now)
        self.flash = max(0.0, self.flash - dt / 2.0)
        self.hue += (self.hue_target - self.hue) * min(1.0, dt / 1.5)
        if now - self.last_drop > 14.0:
            self.hue_target = 0.0
        self.search_t += dt * (0.15 + 0.6 * self.mid_s + 0.8 * self.beat_pulse)
        self.traffic_t += dt * (0.2 + 1.5 * self.energy)
        # Beat-Schnitt: harter Wechsel mit 60 ms Überblendung, endet nach 1-3 Beats oder bei Stille
        if self.cut_state and (now >= self.cut_until or (not live and now - self.cut_t0 > 1.0)):
            self._end_cut()
        self.cut_mix = min(1.0, self.cut_mix + dt / CUT_FADE) if self.cut_state else max(0.0, self.cut_mix - dt / CUT_FADE)
        # Wetter wandert, Heimzustand folgt (über das Grundbild aus- und wieder eingeblendet)
        if self.weather_target is not None:
            self.weather += (self.weather_target - self.weather) * min(1.0, dt / 1.5)
            if abs(self.weather_target - self.weather) < 0.01:
                self.weather = self.weather_target
                self.weather_target = None
        else:
            self.weather += dt / self.cycle
        self.weather %= 4.0
        shown = int(round(self.weather)) % 4
        if shown != self.weather_shown:
            self.weather_shown = shown
            self.weather_t0 = now
            wled.apply_mode_async(WEATHER_LED[shown])
            self.led_back_at = None
            self.led_chain = None
        home = WEATHER_HOME[self.weather_shown]
        if self.lights[home - 1] is None:
            home = self.ground_a if self.lights[self.ground_a - 1] is not None else 0
        if home != self.ground_a:
            self.ground_mix = max(0.0, self.ground_mix - dt / 1.2)
            if self.ground_mix <= 0.0:
                self.ground_a = home
        else:
            target = self.home_mix * WEATHER_HOME_MIX[self.weather_shown] if self.lights[home - 1] is not None else 0.0
            self.ground_mix += (target - self.ground_mix) * min(1.0, dt / 1.2)
        self.look += (self.look_target - self.look) * min(1.0, dt / 1.5)
        # EMP von selbst bei Energie, LED-Kette (Blitz -> Stromausfall) und Rückkehr zum Wetterprofil
        if now >= self.emp_next:
            if live and self.energy > self.emp_min_energy and not self._event_active(now):
                self.emp()
            else:
                self.emp_next = now + 10.0
        if self.led_chain is not None and now >= self.led_chain[1]:
            wled.apply_mode_async(self.led_chain[0])
            self.led_chain = None
        if self.led_back_at is not None and now >= self.led_back_at:
            self.led_back_at = None
            wled.apply_mode_async(WEATHER_LED[self.weather_shown])
        if self.demo and now >= self.demo_next:
            pick = self.rng.choice(("left", "right", "fire", "black", "emp", "drop"))
            {"left": lambda: self.change_weather(-1), "right": lambda: self.change_weather(+1), "fire": self.fireworks,
             "black": self.blackout, "emp": self.emp, "drop": lambda: self._drop(now)}[pick]()
            self.demo_next = now + 8.0
        self.pulses = [p for p in self.pulses if now - p < 3.0]
        ages = [max(0.0, now - p) for p in self.pulses[-N_PULSES:]]
        while len(ages) < N_PULSES:
            ages.append(99.0)
        size = lambda a: (float(a.shape[1]), float(a.shape[0])) if a is not None else (4.0, 4.0)
        out = {
            "uSceneSize": size(self.scene), "uPartSize": size(self.particles), "uBaseFit": self.base_fit,
            "uLightA": float(self.ground_a), "uLightB": float(self.cut_state or self.cut_last_state), "uLightMix": self.cut_mix,
            "uGroundMix": self.ground_mix, "uCutT": (now - self.cut_t0) if self.cut_state else -1.0,
            "uSeed": self.seed, "uSkyline": self.skyline,
            "uWeather": self.weather, "uBassS": self.bass_s, "uMidS": self.mid_s, "uHighS": self.high_s, "uEnergy": self.energy,
            "uLive": self.live_s, "uBeatPulse": self.beat_pulse, "uBeatStep": float(self.beat_step), "uFlash": self.flash,
            "uHue": self.hue, "uFireT": (now - self.firework_t0) if now - self.firework_t0 < FIREWORK_SECONDS else -1.0,
            "uFireSeed": self.firework_seed,
            "uBlackT": (now - self.blackout_t0) if in_blackout else -1.0, "uBlackBeats": float(self.blackout_beats),
            "uEmpT": (now - self.emp_t0) if in_emp else -1.0, "uEmpBeats": float(self.emp_beats), "uEmpSeed": self.emp_seed,
            "uLightT": (now - self.lightning_t0) if now - self.lightning_t0 < 1.5 else -1.0, "uLightX": self.lightning_x,
            "uSearchT": self.search_t % 1000.0, "uTrafficT": self.traffic_t % 1000.0, "uLook": self.look,
            "uPulseA": tuple(ages[0:3]), "uPulseB": tuple(ages[3:6]),
        }
        for i, img in enumerate(self.lights):
            out[f"uLight{i}Size"] = size(img)
        return out

    def overlays(self, t: float):
        now = time.monotonic()
        out = []
        if now - self.weather_t0 < 2.5:
            a = min(1.0, (now - self.weather_t0) / 0.4) * min(1.0, (2.5 - (now - self.weather_t0)) / 0.8)
            out.append((WEATHER[self.weather_shown], 0.03, 0.5, 0.5, (200, 230, 255), 0.8 * a))
        if now - self.blackout_t0 < BLACKOUT_SECONDS:
            k = now - self.blackout_t0
            out.append(("S T R O M A U S F A L L   S E K T O R   7", 0.03, 0.5, 0.9, (255, 80, 80),
                        0.7 * min(1.0, k * 2.0) * min(1.0, (BLACKOUT_SECONDS - k) / 1.0)))
        if now - self.emp_t0 < EMP_SECONDS:
            k = now - self.emp_t0
            a = min(1.0, k * 4.0) * min(1.0, (EMP_SECONDS - k) / 1.5)
            out.append(("E M P", 0.045, 0.5, 0.9, (160, 240, 255), 0.85 * a * (0.6 + 0.4 * (1.0 if int(k * 6.0) % 2 else 0.3))))
        if self.cut_state and 1 <= self.cut_state <= N_LIGHTS:
            k = now - self.cut_t0
            out.append((LIGHT_NAMES[self.cut_state - 1], 0.022, 0.5, 0.05, (200, 240, 255), 0.6 * min(1.0, k * 10.0)))
        return out
