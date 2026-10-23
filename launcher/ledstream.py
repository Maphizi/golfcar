"""LED-Buttonboard live zur Musik: eigene LED-Bilder per UDP (WLED-Echtzeitprotokoll DRGB, Port 21324) aus dem
Modusprozess heraus, 25 Bilder je Sekunde, direkt aus der Musikanalyse (Bass, Beat, Höhen, Drop, Stille).

Der Launcher setzt beim Moduswechsel weiter das Profil aus config/wled.toml per HTTP; sobald eine Szene streamt,
zeigt WLED die Bilder von hier, und `timeout` Sekunden nach dem letzten Paket (Szene beendet) fällt es von selbst auf
das Profil zurück. Farben kommen aus dem Modusprofil (col = Hauptfarbe, col2 = Akzent, col3 = Funkeln), Programm aus
dem fx des Profils (Feuer-Effekte -> Feuer, Scanner -> KITT-Scanner, Rainbow -> Regenbogen, sonst VU-Meter in der
Modusfarbe: Grund dunkel, Bass von der Mitte nach außen, Beat = Blitz einer LED-Gruppe, Höhen = einzelne Funken) oder aus
`Controller.led_state()` der Szene (z. B. "error": Ausfälle, Flackern, wachsendes Rot). Ereignis-Profile, die Szenen
über wled.apply_mode_async() schicken (slots_jackpot, campfire_log ...), spielt der Stream als kurzen Blitz in der
Profilfarbe. Gesamthelligkeit: Profil-bri x [controller].dim. In WLED muss "UDP-Echtzeit empfangen" an sein (Standard).
Test ohne Board: `KITT_LEDS=1 python -m visualizers.engine error --test-signal` loggt die Paketrate."""
from __future__ import annotations

import json
import logging
import math
import random
import socket
import threading
import time
import urllib.request

import numpy as np

from launcher import wled

log = logging.getLogger("leds")

DRGB = 2
MAX_LEDS = 490                               # ein DRGB-Paket
GREEN = np.array([30.0, 255.0, 50.0])
RED = np.array([255.0, 18.0, 8.0])
YELLOW = np.array([255.0, 170.0, 0.0])
BLUE = np.array([40.0, 120.0, 255.0])
ORANGE = np.array([255.0, 110.0, 0.0])
WHITE = np.array([255.0, 255.0, 255.0])


def _rgb(v, default) -> np.ndarray:
    try:
        return np.array([max(0.0, min(255.0, float(c))) for c in list(v)[:3]], dtype=float)
    except (TypeError, ValueError):
        return np.array(default, dtype=float)


class LedStream:
    def __init__(self, mode: str, scene: str, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        cfg = wled._load_cfg()
        ctrl = cfg.get("controller", {})
        self.enabled = bool(ctrl.get("enabled", True)) and bool(ctrl.get("realtime", True)) and bool(ctrl.get("host"))
        self.host = str(ctrl.get("host", ""))
        self.http_port = int(ctrl.get("port", 80))
        self.udp_port = int(ctrl.get("udp_port", 21324))
        self.fps = float(ctrl.get("fps", 25))
        self.timeout = max(1, int(ctrl.get("realtime_timeout", 2)))
        self.dim = float(ctrl.get("dim", 1.0))
        self.n = int(ctrl.get("leds", 0))                         # 0 = beim Controller nachfragen
        prof = wled.profiles().get(mode) or wled.profiles().get(scene) or {}
        self.col = _rgb(prof.get("col"), [255, 255, 255])
        if mode == "home":                                        # Taxistand: Themenfarbe wie beim Launcher
            try:
                from launcher import theme
                self.col = np.clip(np.array(theme.current().get("color_a", [1, 0.8, 0.25])[:3], dtype=float) * 255.0, 0, 255)
            except Exception:
                pass
        self.col2 = _rgb(prof.get("col2"), [0, 0, 0])
        self.col3 = _rgb(prof.get("col3"), [0, 0, 0])
        if self.col2.max() < 8:
            self.col2 = np.clip(self.col * 0.5 + WHITE * 0.5, 0, 255)
        if self.col3.max() < 8:
            self.col3 = WHITE.copy()
        self.bri = float(prof.get("bri", 160)) / 255.0 * self.dim
        self.fx = int(prof.get("fx", 0))
        self.sock = None
        self.next_send = 0.0
        self.sent = 0
        self.last_log = time.monotonic()
        self.last_fail = 0.0
        # Zustand der Programme
        self.bass_s = 0.0
        self.energy = 0.0
        self.e_fast = 0.0
        self.glow = None                                          # Nachleuchten je LED
        self.pulses: list[tuple[float, int]] = []                 # (Startzeit, Richtung) der Beat-Wellen
        self.beat_mask = None                                     # LED-Gruppe des letzten Beats
        self.beat_glow = 0.0
        self.last_beat = 0.0
        self.last_drop = 0.0
        self.beats = 0
        self.flash = 0.0                                          # Drop/Ereignis-Blitz 0..1
        self.flash_col = WHITE.copy()
        self.event_until = 0.0
        self.scan_pos = 0.0
        self.scan_dir = 1.0
        self.hue = self.rng.random()
        self.fire = None
        self.order = None                                         # Reihenfolge der LEDs (Fehlerprogramm)
        self.dead = None                                          # Ausfallzeit je LED (0 = lebt)
        self.red = None                                           # Rotanteil je LED
        self.flick = None
        self.err_phase = ""
        self.hunt = 0.0
        wled.set_stream_hook(self.event)
        if self.enabled:
            threading.Thread(target=self._setup, name="leds-setup", daemon=True).start()

    # -- Aufbau --------------------------------------------------------------------------------------------------
    def _setup(self) -> None:
        if self.n <= 0:
            try:
                with urllib.request.urlopen(f"http://{self.host}:{self.http_port}/json/info", timeout=3) as r:
                    info = json.loads(r.read().decode())
                self.n = int(info.get("leds", {}).get("count", 0))
            except Exception as exc:
                log.warning("LED-Anzahl nicht abfragbar (%s): %s", self.host, exc)
                return
        self.n = min(self.n, MAX_LEDS)
        if self.n <= 0:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            self.sock = sock
            log.info("LED-Stream: %d LEDs an %s:%d, %d fps, Helligkeit %.0f %%", self.n, self.host, self.udp_port,
                     int(self.fps), self.bri * 100)
        except OSError as exc:
            log.warning("LED-Stream: kein Socket: %s", exc)

    def _ensure_arrays(self) -> None:
        if self.glow is None or len(self.glow) != self.n:
            n = self.n
            self.glow = np.zeros(n)
            self.fire = self.rng.choices(range(100), k=n)
            self.fire = np.array(self.fire, dtype=float) / 100.0
            self.order = np.array(self.rng.sample(range(n), n))
            self.dead = np.zeros(n)
            self.red = np.zeros(n)
            self.flick = np.ones(n)
            self.beat_mask = np.zeros(n)

    # -- Ereignisse ----------------------------------------------------------------------------------------------
    def event(self, name: str, profile: dict) -> None:
        """Ereignis-Profil einer Szene (wled.apply_mode_async): kurzer Blitz in der Profilfarbe."""
        self.flash = 1.0
        self.flash_col = _rgb(profile.get("col"), [255, 255, 255])
        self.event_until = time.monotonic() + 1.5

    # -- je Bild -------------------------------------------------------------------------------------------------
    def update(self, now: float, f, state: dict | None = None) -> None:
        if self.sock is None or self.n <= 0:
            return
        if now < self.next_send:
            return
        self.next_send = now + 1.0 / self.fps
        self._ensure_arrays()
        dt = 1.0 / self.fps
        live = 0.0 if getattr(f, "silent", True) else 1.0
        rms = float(getattr(f, "rms", 0.0)) * live
        bass = float(getattr(f, "bass", 0.0)) * live
        high = float(getattr(f, "high", 0.0)) * live
        beat = float(getattr(f, "beat", 0.0)) * live
        self.bass_s += (bass - self.bass_s) * (0.5 if bass > self.bass_s else 0.12)
        self.e_fast += (rms - self.e_fast) * 0.3
        self.energy += (rms - self.energy) * 0.02
        is_beat = beat > 0.9 and now - self.last_beat > 0.18
        if is_beat:
            self.last_beat = now
            self.beats += 1
        if live and self.e_fast > 1.5 * self.energy + 0.15 and self.energy > 0.1 and now - self.last_drop > 8.0:
            self.last_drop = now
            self.flash = 1.0                                      # Drop: alles blitzt
            self.flash_col = self.col3
        self.flash *= 0.82
        self.glow *= 0.80
        program = (state or {}).get("program", "")
        if program == "error":
            frame = self._error(now, dt, state or {}, bass, high, is_beat, live)
        elif self.fx in (45, 66, 42):
            frame = self._fire(now, dt, bass, high, is_beat, live)
        elif self.fx == 40:
            frame = self._scanner(now, dt, bass, high, is_beat, live)
        elif self.fx in (9, 94):
            frame = self._rainbow(now, dt, bass, high, is_beat, live)
        else:
            frame = self._music(now, dt, bass, high, is_beat, live)
        if self.flash > 0.02:
            frame = frame + (self.flash_col - frame) * self.flash
        frame = np.clip(frame * self.bri, 0, 255).astype(np.uint8)
        self._send(frame, now)

    # -- Programme -----------------------------------------------------------------------------------------------
    def _idx(self) -> np.ndarray:
        return np.arange(self.n) / max(1, self.n - 1)

    def _music(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        """Grundzustand dunkel. Bass = Pegel von der Mitte nach außen (VU-Meter) in der Modusfarbe, Beat = kurzer Blitz
        einer zufälligen LED-Gruppe, Höhen = selten ein einzelner Funke, Stille = eine LED atmet langsam."""
        n = self.n
        x = self._idx()
        if is_beat:
            k = max(1, int(n * (0.25 + 0.2 * self.e_fast)))
            self.beat_mask = np.zeros(n)
            self.beat_mask[self.rng.sample(range(n), k)] = 1.0
            self.beat_glow = 1.0
        self.beat_glow *= 0.72
        vu = min(1.0, self.bass_s * 1.15) * live
        dist = np.abs(x - 0.5) * 2.0                              # 0 Mitte .. 1 Rand
        meter = np.clip((vu - dist) / (2.0 / max(2, n)) + 0.5, 0.0, 1.0)
        frame = np.outer(meter * (0.35 + 0.65 * vu), self.col)
        frame += np.outer(self.beat_mask * self.beat_glow, self.col * 0.6 + WHITE * 0.4) * 0.9
        if high > 0.35 and self.rng.random() < high * high * 0.35:
            self.glow[self.rng.randrange(n)] = 1.0
        frame += np.outer(self.glow, self.col * 0.5 + WHITE * 0.5) * 0.6
        if live < 0.5:                                            # Stille: eine LED wandert und atmet
            pos = (math.sin(now * 0.15) * 0.5 + 0.5)
            w = np.exp(-((x - pos) / 0.06) ** 2) * (0.2 + 0.15 * math.sin(now * 1.2))
            frame = np.outer(w, self.col)
        return frame

    def _fire(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        """Feuerflackern: jede LED hat ihr eigenes Glühen zwischen col (Glut) und col2 (Flamme), mehr mit der Energie."""
        n = self.n
        self.fire += (np.array([self.rng.random() for _ in range(n)]) - self.fire) * (0.25 + 0.4 * self.e_fast)
        heat = np.clip(0.05 + 0.95 * self.fire * (0.3 + 0.7 * self.bass_s) * live + (1.0 - live) * 0.12 * self.fire, 0, 1)
        if is_beat:
            heat = np.clip(heat + 0.35, 0, 1)
        frame = np.outer(heat, self.col) * 0.7 + np.outer(heat * heat, self.col2) * 0.6
        if high > 0.3:
            i = self.rng.randrange(n)
            self.glow[i] = 1.0
        frame += np.outer(self.glow, self.col3) * 0.7
        return frame

    def _scanner(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        """KITT-Scanner: läuft hin und her, Tempo mit der Energie, Beat = Richtungswechsel und Aufblitzen."""
        n = self.n
        speed = (0.5 + 2.0 * self.e_fast) * live + 0.3 * (1.0 - live)
        self.scan_pos += self.scan_dir * speed * dt
        if self.scan_pos > 1.0 or self.scan_pos < 0.0:
            self.scan_dir *= -1.0
            self.scan_pos = min(1.0, max(0.0, self.scan_pos))
        if is_beat:
            self.scan_dir *= -1.0
        x = self._idx()
        w = np.exp(-((x - self.scan_pos) / (0.06 + 0.08 * self.bass_s)) ** 2)
        frame = np.outer(np.full(n, 0.02 + 0.06 * self.bass_s), self.col) + np.outer(w, self.col) * (0.7 + 0.3 * self.bass_s)
        if is_beat:
            frame += self.col * 0.25
        return frame

    def _rainbow(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        n = self.n
        self.hue = (self.hue + dt * (0.03 + 0.25 * self.e_fast)) % 1.0
        if is_beat:
            self.hue = (self.hue + 0.12) % 1.0
        x = self._idx()
        h = (self.hue + x * 0.7) % 1.0
        frame = np.array([_hsv(hh, 1.0, 1.0) for hh in h])
        level = (0.2 + 0.6 * self.bass_s) * live + (1.0 - live) * 0.1
        frame = frame * level + np.outer(self.glow, WHITE) * 0.6
        if high > 0.3 and self.rng.random() < high:
            self.glow[self.rng.randrange(n)] = 1.0
        return frame

    def _error(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Systemfehler: Grün als Grundzustand, LEDs fallen aus und flackern, bei roten Fehlern werden es immer
        mehr rote; Eingabe-Aufforderung gelb mit Restzeit, Virus rot von einem Ende, Schilde blau, Eindringling
        orange auf der Jagd, Neustart als Scanner."""
        n = self.n
        phase = st.get("phase", "code")
        k = float(st.get("k", 0.0))                               # Fortschritt der Phase 0..1
        pct = float(st.get("pct", 0.0))
        good = bool(st.get("good", False))
        if phase != self.err_phase:
            self.err_phase = phase
            if phase in ("code", "stable", "reboot"):
                self.dead[:] = 0.0
            if phase == "code":
                self.red[:] = 0.0
        # Ausfälle: zufällige LEDs sterben für 0,2-1,5 s, Rate je Phase (Code selten, Zusammenbruch viel)
        rate = {"code": 0.15, "break": 2.0 + 6.0 * k, "error": 3.0, "alarm": 5.0, "recovery": 1.5 * (1.0 - k),
                "virus": 1.0 + 3.0 * pct, "shields": 2.0 * (1.0 - pct), "intruder": 0.8, "prompt": 0.3 + k, "stable": 0.0,
                "reboot": 0.0}.get(phase, 0.5)
        if self.rng.random() < rate * dt:
            i = self.rng.randrange(n)
            self.dead[i] = now + self.rng.uniform(0.2, 1.5)
        alive = (self.dead < now).astype(float)
        # Rotanteil: Fehler/Alarm -> in Reihenfolge `order` immer mehr rot; Erholung -> wieder zurück
        if phase in ("error", "alarm"):
            target = 0.25 + 0.75 * k
        elif phase == "recovery":
            target = 0.8 * (1.0 - k)
        elif phase == "virus":
            target = pct
        elif phase == "intruder" and not good and k > 0.85:
            target = 1.0
        else:
            target = 0.0
        want = int(round(target * n))
        rank = np.empty(n)
        rank[self.order] = np.arange(n)
        red_mask = (rank < want).astype(float)
        if phase == "virus":                                      # Infektion breitet sich von einem Ende aus
            red_mask = (np.arange(n) < want).astype(float)
        self.red += (red_mask - self.red) * 0.35
        # Flackern: lebende LEDs zittern, stärker bei Alarm und auf den Bass
        jitter = np.array([self.rng.random() for _ in range(n)])
        amp = {"code": 0.15, "break": 0.5, "error": 0.45, "alarm": 0.7, "recovery": 0.3, "stable": 0.05}.get(phase, 0.3)
        self.flick = 1.0 - amp * jitter * (0.5 + 0.5 * bass)
        base_level = (0.05 + 0.45 * self.bass_s) * live + (1.0 - live) * 0.1
        green = np.outer(np.full(n, base_level), GREEN)
        if phase == "code":                                       # Code läuft: einzelne LEDs blitzen wie Daten
            if self.rng.random() < (2.0 + 10.0 * high) * dt:
                self.glow[self.rng.randrange(n)] = 1.0
        frame = green * (1.0 - self.red[:, None]) + np.outer(self.red, RED) * (0.6 + 0.4 * self.bass_s)
        if phase in ("error", "alarm") and is_beat:               # Alarm: alle roten blitzen auf den Beat
            frame += np.outer(self.red, RED) * 0.6
        if phase == "alarm":
            frame *= 0.6 + 0.4 * (1.0 if int(now * 6.0) % 2 == 0 else 0.3)
        x = self._idx()
        if phase == "prompt":                                     # gelb, blinkt schneller, Balken = Restzeit
            blink = 1.0 if math.sin(now * (4.0 + 20.0 * k)) > 0.0 else 0.35
            bar = (x <= 1.0 - k).astype(float)
            frame = np.outer(bar * blink * 0.9 + 0.08, YELLOW)
        elif phase == "shields":                                  # blauer Balken = Schilde in Prozent
            bar = (x <= pct).astype(float)
            frame = np.outer(bar, BLUE) * (0.6 + 0.4 * self.bass_s) + np.outer((1.0 - bar) * self.flick, RED) * 0.25
        elif phase == "intruder":                                 # ein orangener Punkt jagt durch das Board
            self.hunt = (self.hunt + dt * (0.8 + 2.0 * pct) * (1.0 if int(now) % 2 == 0 else -1.0)) % 1.0
            w = np.exp(-((x - self.hunt) / 0.05) ** 2)
            frame = frame * 0.5 + np.outer(w, ORANGE)
            if good and k >= 0.99:
                frame = np.outer(np.full(n, 0.8), BLUE)
        elif phase == "reboot":                                   # Scanner von rot nach grün, am Ende alles grün
            w = np.exp(-((x - k) / 0.08) ** 2)
            frame = np.outer((x < k).astype(float) * 0.7, GREEN) + np.outer(w, WHITE)
            alive[:] = 1.0
        elif phase == "stable":
            frame = np.outer(np.full(n, 0.5 + 0.3 * math.sin(now * 2.0) + 0.2 * self.bass_s), GREEN)
        frame = frame * (alive * self.flick)[:, None] + np.outer(self.glow, WHITE) * 0.8
        return frame

    # -- Senden --------------------------------------------------------------------------------------------------
    def _send(self, frame: np.ndarray, now: float) -> None:
        data = bytes([DRGB, self.timeout]) + frame.tobytes()
        try:
            self.sock.sendto(data, (self.host, self.udp_port))
            self.sent += 1
        except OSError as exc:
            if now - self.last_fail > 30.0:
                self.last_fail = now
                log.warning("LED-Stream: %s", exc)
        if now - self.last_log >= 30.0:
            log.info("LED-Stream: %d Pakete in %.0f s", self.sent, now - self.last_log)
            self.last_log, self.sent = now, 0

    def stop(self) -> None:
        wled.set_stream_hook(None)
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


def _hsv(h: float, s: float, v: float) -> np.ndarray:
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i]
    return np.array([r * 255.0, g * 255.0, b * 255.0])
