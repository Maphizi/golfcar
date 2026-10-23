"""LED-Buttonboard live zur Musik: eigene LED-Bilder per UDP (WLED-Echtzeitprotokoll DRGB, Port 21324) aus dem
Modusprozess heraus, 25 Bilder je Sekunde, direkt aus der Musikanalyse (Bass, Beat, Höhen, Drop, Stille).

Der Launcher setzt beim Moduswechsel weiter das Profil aus config/wled.toml per HTTP; sobald eine Szene streamt,
zeigt WLED die Bilder von hier, und `timeout` Sekunden nach dem letzten Paket (Szene beendet) fällt es von selbst auf
das Profil zurück. Farben kommen aus dem Modusprofil (col = Hauptfarbe, col2 = Akzent, col3 = Funkeln), Programm aus
dem fx des Profils (Feuer-Effekte -> Feuer, Scanner -> KITT-Scanner, Rainbow -> Regenbogen, sonst VU-Meter in der
Modusfarbe: Grund dunkel, Bass von der Mitte nach außen, Beat = Welle von vorne nach hinten, kräftige Beats dazu eine
LED-Gruppe, Höhen = einzelne Funken). Kette: Index 0 = vorne am Cart ([controller].reverse dreht um) oder aus
`Controller.led_state()` der Szene (z. B. "error": Kampf Rot gegen Grün, kaputt flackernd). Ereignis-Profile, die Szenen
über wled.apply_mode_async() schicken (slots_jackpot, campfire_log ...), spielt der Stream als kurzen Blitz in der
Profilfarbe. Gesamthelligkeit: Profil-bri x [controller].dim. In WLED muss "UDP-Echtzeit empfangen" an sein (Standard).
Ketten über 490 LEDs gehen als DNRGB-Pakete mit Startindex raus. Test ohne Board: `KITT_LEDS=1 python -m
visualizers.engine error --test-signal` loggt die Paketrate."""
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

DRGB = 2                                     # bis 490 LEDs in einem Paket
DNRGB = 4                                    # mit Startindex, 489 LEDs je Paket (Ketten über 490 LEDs)
DRGBW = 3                                    # 4 Kanäle je LED (nur mit col_remap)
DNRGBW = 5                                   # 4 Kanäle mit Startindex
CHUNK = 489
MAX_LEDS = 2000
GREEN = np.array([0.0, 150.0, 4.0])      # sattes, nicht zu helles Grün (reiner Kanal, gedimmt)
RED = np.array([255.0, 6.0, 0.0])
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
        self.nrng = np.random.default_rng(self.rng.randrange(1 << 30))
        cfg = wled._load_cfg()
        ctrl = cfg.get("controller", {})
        self.enabled = bool(ctrl.get("enabled", True)) and bool(ctrl.get("realtime", True)) and bool(ctrl.get("host"))
        self.host = str(ctrl.get("host", ""))
        self.http_port = int(ctrl.get("port", 80))
        self.udp_port = int(ctrl.get("udp_port", 21324))
        remap_cfg = ctrl.get("col_remap", None)
        self._col_remap = list(remap_cfg) if remap_cfg is not None else None  # Kanal-Remap für WS2814 etc.
        self.fps = float(ctrl.get("fps", 25))
        self.timeout = max(1, int(ctrl.get("realtime_timeout", 2)))
        self.dim = float(ctrl.get("dim", 1.0))
        self.n = int(ctrl.get("leds", 0))                         # 0 = beim Controller nachfragen
        self.reverse = bool(ctrl.get("reverse", False))         # Kette: Index 0 = vorne am Cart, Ende = hinten; reverse dreht um
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
        # Casino-Markise (Slotmaschinen): drei Farben in Blöcken, Hauptfarbe, Warmweiß, Akzent
        acc = self.col3 if (self.col3.max() > 40 and not np.array_equal(self.col3, WHITE)) else (self.col2 if self.col2.max() > 120 else np.array([255.0, 40.0, 10.0]))
        self.marquee = [self.col, np.array([255.0, 225.0, 170.0]), acc]
        self.mq_pos = 0.0
        self.mq_dir = 1.0
        self.mq_rot = 0
        self.mq_beats = 0
        self.mq_flip_at = 0.0
        self.sp_next = time.monotonic() + self.rng.uniform(15.0, 30.0)   # Specials: einzelner Läufer, Überholer, Kreuzung
        self.runners: list[dict] = []
        self.sp_kind = ""
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
            self.fire = self.nrng.random(n)
            self.order = np.array(self.rng.sample(range(n), n))
            self.dead = np.zeros(n)
            self.red = np.zeros(n)
            self.flick = np.ones(n)
            self.beat_mask = np.zeros(n)
            self.terr = np.ones(n)                                # Fehlerprogramm: Besitz je LED (-1 rot .. 1 grün)
            # Abschnitte von 3-30 LEDs mit eigenem Lebenslauf: aus -> an (ruhig) -> flackern -> tot -> aus
            seg_id, i, k = [], 0, 0
            while i < n:
                w = int(self.nrng.integers(3, 31))
                seg_id += [k] * min(w, n - i)
                i += w
                k += 1
            self.seg_id = np.array(seg_id)
            self.nseg = int(self.seg_id.max()) + 1
            self.seg_state = np.zeros(self.nseg, dtype=int)       # 0 aus, 1 an, 2 flackert, 3 tot
            self.seg_next = self.nrng.uniform(0.0, 3.0, self.nseg)  # Zeitpunkt des nächsten Zustandswechsels (relativ zu jetzt)
            self.seg_lvl = self.nrng.uniform(0.3, 0.9, self.nseg)
            self.seg_flick = np.ones(self.nseg)
            self.seg_t0 = -1.0                                    # Zeitbasis der seg_next-Werte
            self.seg_tick = 0.0                                   # interner Takt ohne Beats
            self.onmask = np.zeros(n)
            self.level = np.full(n, 0.5)
            self.noise_ph = self.nrng.uniform(0.0, 6.28, 4)
            self.push = 0.0
            self.ev_next = 0.0
            self.strobe = (0, 0, 0.0, "red")
            self.sweep = (-10.0, 1.0, "red", 0.4)
            self.black_until = 0.0
            self.storm = (0, 0, 0.0)
            self.storm_noise = None
            self.storm_tick = -1

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
        elif program == "slots":
            frame = self._slots(now, dt, state or {}, bass, high, is_beat, live)
        elif self.fx in (45, 66, 42):
            frame = self._fire(now, dt, bass, high, is_beat, live)
        elif self.fx == 40:
            frame = self._scanner(now, dt, bass, high, is_beat, live)
        elif self.fx in (9, 94):
            frame = self._rainbow(now, dt, bass, high, is_beat, live)
        else:
            frame = self._music(now, dt, bass, high, is_beat, live)
        if self.flash > 0.02:
            fc = RED if program == "error" else self.flash_col
            frame = frame + (fc - frame) * self.flash
        frame = np.clip(frame * self.bri, 0, 255).astype(np.uint8)
        self._send(frame, now)

    # -- Programme -----------------------------------------------------------------------------------------------
    def _slots(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Casino-Markise wie ein Vegas-Eingang: Blöcke von 3 LEDs in derselben Farbe (Hauptfarbe, Warmweiß, Akzent im
        Wechsel), alle an, nur die Helligkeit wandert leicht; das Muster fährt langsam, mal vor, mal zurück, beim Drehen
        schnell; alle paar Beats wechseln die Farben durch, ab und zu kehrt die Richtung um. Gewinn: klein = zweimal
        Blitzen, groß = heller Lauf von vorne, Jackpot = Gold/Weiß-Stroboskop und Funkeln."""
        n = self.n
        x = self._idx()
        idx = np.arange(n)
        spinning = bool(st.get("spinning", False))
        win = int(st.get("win", 0))
        cols = st.get("colors") or []
        if len(cols) >= 2:                                        # Lichtfarben des Automaten auf dem Schirm: A, Warmweiß, B
            a, b = np.array(cols[0], dtype=float), np.array(cols[1], dtype=float)
            for c in (a, b):
                if c.max() > 0:
                    c *= 255.0 / c.max()                          # volle Leuchtkraft je Farbe
            self.marquee = [a, np.array([255.0, 225.0, 170.0]), b]
        age = float(st.get("win_age", 0.0))
        if is_beat:
            self.mq_beats += 1
            if self.mq_beats % 4 == 0:                            # alle vier Beats die Farben weiterrücken
                self.mq_rot += 1
            if self.mq_beats % 16 == 0 or (bass > 0.8 and self.rng.random() < 0.15):
                self.mq_dir *= -1.0
                self.mq_flip_at = now + self.rng.uniform(6.0, 14.0)
        if now >= self.mq_flip_at:                                # auch ohne Musik ab und zu umkehren
            self.mq_dir *= -1.0
            self.mq_flip_at = now + self.rng.uniform(6.0, 14.0)
        speed = 10.0 if spinning else ((2.5 + 4.0 * self.e_fast) * live + (1.0 - live) * 1.5)   # LED-Schritte je Sekunde
        self.mq_pos = (self.mq_pos + self.mq_dir * speed * dt) % 9.0
        shift = idx + int(self.mq_pos)
        if self.reverse:
            shift = (n - 1 - idx) + int(self.mq_pos)
        ci = ((shift // 3) + self.mq_rot) % 3
        colors = np.array(self.marquee)[ci]
        twinkle = 0.8 + 0.2 * np.sin(now * 1.7 + idx * 0.35) * np.sin(now * 0.9 + idx * 0.11)
        level = twinkle * ((0.75 + 0.25 * self.bass_s) * live + (1.0 - live) * 0.5)
        if spinning:
            level = twinkle * 1.0
        frame = colors * level[:, None]
        gold = self.marquee[0]
        white = self.marquee[1]
        acc = self.marquee[2]
        # Specials: ab und zu läuft ein einzelner heller Punkt durch; wird der Beat dabei kräftiger, überholt ihn ein
        # zweiter in der Akzentfarbe; oder zwei Läufer von beiden Enden kreuzen sich in der Mitte
        if now >= self.sp_next and win == 0 and not spinning:
            self.sp_next = now + self.rng.uniform(20.0, 45.0)
            d = self.rng.choice((1.0, -1.0))
            spd = self.rng.uniform(0.2, 0.35)                     # Anteil der Kette je Sekunde
            if self.rng.random() < 0.7:
                self.sp_kind = "runner"
                self.runners = [{"t0": now, "start": 0.0 if d > 0 else 1.0, "dir": d, "speed": spd, "col": white, "e0": self.e_fast, "b0": bass}]
            else:
                self.sp_kind = "cross"
                self.runners = [{"t0": now, "start": 0.0, "dir": 1.0, "speed": spd, "col": white},
                                {"t0": now, "start": 1.0, "dir": -1.0, "speed": spd, "col": acc}]
        if self.sp_kind == "runner" and len(self.runners) == 1:
            r0 = self.runners[0]
            prog = (now - r0["t0"]) * r0["speed"]
            rising = (is_beat and bass > r0["b0"] + 0.12) or self.e_fast > r0["e0"] + 0.15
            if rising and 0.15 < prog < 0.6:                       # Beat zieht an: Überholer startet
                self.runners.append({"t0": now, "start": r0["start"], "dir": r0["dir"], "speed": r0["speed"] * 1.9, "col": acc})
        if self.runners:
            frame = frame * 0.6                                   # Markise zurück, damit die Läufer stechen
            keep = []
            for rn in self.runners:
                pos = rn["start"] + rn["dir"] * rn["speed"] * (now - rn["t0"])
                if -0.05 <= pos <= 1.05:
                    keep.append(rn)
                    head = np.exp(-((x - pos) / 0.012) ** 2)
                    tail = np.exp(-((x - (pos - rn["dir"] * 0.035)) / 0.03) ** 2) * 0.35
                    frame += np.outer(head * 1.3 + tail, rn["col"])
            self.runners = keep
            if not keep:
                self.sp_kind = ""
        if win == 1 and age < 1.2:                                # kleiner Gewinn: zweimal aufblitzen
            if int(age * 5.0) % 2 == 0 and age < 0.8:
                frame = np.outer(np.ones(n), gold)
        elif win == 2 and age < 4.0:                              # großer Gewinn: heller Lauf von vorne, dann Markise schnell
            if age < 1.2:
                pos = age / 1.2
                w = np.exp(-((x - pos) / 0.12) ** 2)
                frame = frame * 0.5 + np.outer(w, white)
            else:
                self.mq_pos = (self.mq_pos + self.mq_dir * 12.0 * dt) % 9.0
        elif win >= 3 and age < 7.0:                              # Jackpot: Stroboskop Gold/Weiß, dann Goldfunkeln
            if age < 3.0:
                frame = np.outer(np.ones(n), gold if int(age * 8.0) % 2 == 0 else white)
            else:
                if self.rng.random() < 0.9:
                    self.glow[self.nrng.integers(0, n, size=max(1, n // 60))] = 1.0
                frame = frame * 0.6 + np.outer(self.glow, white)
        return frame

    def _idx(self) -> np.ndarray:
        """0 = vorne am Cart .. 1 = hinten."""
        x = np.arange(self.n) / max(1, self.n - 1)
        return 1.0 - x if self.reverse else x

    def _music(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        """Grundzustand dunkel. Bass = Pegel von der Mitte nach außen (VU-Meter) in der Modusfarbe, Beat = kurzer Blitz
        einer zufälligen LED-Gruppe, Höhen = selten ein einzelner Funke, Stille = eine LED atmet langsam."""
        n = self.n
        x = self._idx()
        if is_beat:
            self.pulses.append((now, 1))                          # Welle von vorne nach hinten (Fahrtrichtung)
            if bass > 0.55:                                       # kräftiger Beat: dazu eine zufällige Gruppe
                k = max(1, int(n * (0.15 + 0.15 * self.e_fast)))
                self.beat_mask = np.zeros(n)
                self.beat_mask[self.rng.sample(range(n), k)] = 1.0
                self.beat_glow = 1.0
        self.beat_glow *= 0.72
        travel = 0.9 - 0.45 * self.e_fast                         # schneller bei lauter Musik
        self.pulses = [(t0, d) for t0, d in self.pulses if now - t0 < travel + 0.2]
        vu = min(1.0, self.bass_s * 1.15) * live
        dist = np.abs(x - 0.5) * 2.0                              # 0 Mitte .. 1 Rand
        meter = np.clip((vu - dist) / (2.0 / max(2, n)) + 0.5, 0.0, 1.0)
        frame = np.outer(meter * (0.35 + 0.65 * vu), self.col)
        frame += np.outer(self.beat_mask * self.beat_glow, self.col * 0.6 + WHITE * 0.4) * 0.9
        for t0, _ in self.pulses:
            pos = (now - t0) / travel
            w = np.exp(-((x - pos) / 0.045) ** 2) * max(0.0, 1.0 - pos * 0.6)
            frame += np.outer(w, self.col * 0.7 + WHITE * 0.3)
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
        self.fire += (self.nrng.random(n) - self.fire) * (0.25 + 0.4 * self.e_fast)
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
        """Systemfehler: Kampf zwischen Grün (System) und Rot (Fehler). Jede LED gehört einer Seite (`terr` -1 rot .. +1
        grün); die Front liegt auf einem langsam wandernden Rauschfeld (Blasen statt Sortierung), ihr Anteil folgt der Phase,
        Beats stoßen die stärkere Seite vor, der Bass heizt den Kampf an. Umkämpfte LEDs sirren schnell rot/grün. Es sieht
        kaputt aus: Abschnitte von 3-30 LEDs mit eigenem Lebenslauf (aus -> ruhig an -> flackern -> tot), nur ein Teil
        arbeitet, gedimmt; alles eher träge als hektisch; Kurzschluss-Blöcke
        blitzen voll und sterben, Störlinien rasen durch, kurze Totalausfälle, Rauschstürme, Ausfälle je LED (`dead`)."""
        n = self.n
        x = self._idx()
        r = self.nrng
        phase = st.get("phase", "code")
        k = float(st.get("k", 0.0))
        pct = float(st.get("pct", 0.0))
        good = bool(st.get("good", False))
        if phase != self.err_phase:
            self.err_phase = phase
            self.ev_next = now + r.uniform(0.3, 1.2)
            if phase == "reboot":
                self.dead[:] = 0.0
        # Ziel-Rotanteil und Schwere je Phase
        if phase == "code":
            target, sev = 0.06 + 0.06 * math.sin(now * 0.7), 0.25
        elif phase == "break":
            target, sev = 0.15 + 0.45 * k, 0.6 + 0.3 * k
        elif phase == "error":
            target, sev = 0.5 + 0.4 * k, 0.85
        elif phase == "alarm":
            target, sev = 0.9, 1.0
        elif phase == "recovery":
            target, sev = 0.75 * (1.0 - k), 0.5
        elif phase == "prompt":
            target, sev = 0.5 + 0.4 * math.sin(now * (2.0 + 8.0 * k)), 0.5 + 0.4 * k
        elif phase == "virus":
            target, sev = (pct if not good else pct * 0.6), 0.7
        elif phase == "shields":
            target, sev = 1.0 - pct, 0.6
        elif phase == "intruder":
            target, sev = 0.08, 0.45
        elif phase == "stable":
            target, sev = 0.0, 0.1
        else:                                                     # reboot
            target, sev = 0.0, 0.3
        # Gelände: wanderndes Rauschfeld; Virus/Schilde von hinten her
        self.noise_ph += dt * np.array([0.15, 0.27, 0.41, 0.63]) * (0.04 + 0.12 * sev + 0.08 * bass)   # Front ruht fast, Beats stoßen
        field = (np.sin(x * 2.0 * math.pi * 1.5 + self.noise_ph[0]) + 0.6 * np.sin(x * 2.0 * math.pi * 3.7 + self.noise_ph[1])
                 + 0.35 * np.sin(x * 2.0 * math.pi * 7.3 + self.noise_ph[2]) + 0.2 * np.sin(x * 2.0 * math.pi * 13.1 + self.noise_ph[3]))
        if phase in ("virus", "shields"):
            field = 0.35 * field + (0.5 - x) * 3.0                 # hinten (x = 1) zuerst rot
        if is_beat:                                               # Vorstoß der stärkeren Seite
            self.push = (0.45 if target > 0.5 else -0.45) * (0.5 + 0.5 * bass)
        self.push *= 0.9
        target = min(1.0, max(0.0, target))
        if target <= 0.0:
            red_now = np.zeros(n, dtype=bool)
        elif target >= 1.0:
            red_now = np.ones(n, dtype=bool)
        else:
            red_now = field < np.quantile(field, target) + self.push
        self.terr += (np.where(red_now, -1.0, 1.0) - self.terr) * min(1.0, (0.03 + 0.12 * bass + 0.1 * sev) * dt * 25.0 * 0.4)
        if phase == "intruder":                                   # roter Läufer hinterlässt eine Spur, Grün heilt sie
            self.hunt = (self.hunt + dt * (0.5 + 1.5 * pct)) % 1.0
            self.terr[np.abs(x - self.hunt) < 0.02] = -1.0
        red = np.clip(-self.terr, 0.0, 1.0)
        green = np.clip(self.terr, 0.0, 1.0)
        contested = (1.0 - np.abs(self.terr)) ** 2
        # Arbeitende LEDs: wenige, gedimmt, zuckend
        p_on = 0.05 + 0.14 * sev + 0.1 * bass * live                # wenige LEDs arbeiten überhaupt
        if self.seg_t0 < 0.0:
            self.seg_t0 = now
        # Wechsel nur auf den Beat (ohne Beats alle ~2 s): fällige Abschnitte schalten, dazu wandern ein paar Leuchtende
        # zu einem Nachbarabschnitt ("andere LED-Reihe")
        tick = is_beat or (now - self.last_beat > 2.5 and now >= self.seg_tick)
        due = np.where(now - self.seg_t0 >= self.seg_next)[0] if tick else np.array([], dtype=int)
        if tick:
            self.seg_tick = now + 2.0
            lit = np.where((self.seg_state == 1) | (self.seg_state == 2))[0]
            k = max(1, len(lit) // 6) if len(lit) else 0
            for si in (r.choice(lit, size=k, replace=False) if k else []):
                nb = int(min(self.nseg - 1, max(0, si + r.integers(-3, 4))))
                if nb != si and self.seg_state[nb] == 0:
                    self.seg_state[si], self.seg_next[si] = 0, now - self.seg_t0 + r.uniform(1.0, 4.0)
                    self.seg_state[nb], self.seg_lvl[nb] = 1, self.seg_lvl[si]
                    self.seg_next[nb] = now - self.seg_t0 + r.uniform(3.0, 12.0)
        if len(due):
            on_frac = float(np.mean(self.seg_state == 1) + np.mean(self.seg_state == 2))
            for si in due:
                stt = self.seg_state[si]
                if stt == 0:                                      # aus: nur anschalten, wenn zu wenige arbeiten
                    if on_frac < p_on * 1.3 and r.random() < 0.7:
                        self.seg_state[si] = 1
                        self.seg_lvl[si] = r.uniform(0.3, 0.9)
                        self.seg_next[si] = now - self.seg_t0 + r.uniform(3.0, 12.0) * (1.4 - 0.8 * sev)   # bleibt länger an
                        on_frac += 1.0 / self.nseg
                    else:
                        self.seg_next[si] = now - self.seg_t0 + r.uniform(0.5, 3.0)
                elif stt == 1:                                    # an -> flackern
                    self.seg_state[si] = 2
                    self.seg_next[si] = now - self.seg_t0 + r.uniform(1.0, 4.0)
                elif stt == 2:                                    # flackern -> tot (oder doch noch einmal ruhig)
                    if r.random() < 0.25:
                        self.seg_state[si] = 1
                        self.seg_next[si] = now - self.seg_t0 + r.uniform(1.0, 4.0)
                    else:
                        self.seg_state[si] = 3
                        self.seg_next[si] = now - self.seg_t0 + r.uniform(1.0, 5.0)
                else:                                             # tot -> aus
                    self.seg_state[si] = 0
                    self.seg_next[si] = now - self.seg_t0 + r.uniform(0.2, 2.0)
        # Flackern: träge gefilterter Zufall je Abschnitt, mit Aussetzern
        target_f = np.where(self.seg_state == 2, r.random(self.nseg), 1.0)
        self.seg_flick += (target_f - self.seg_flick) * 0.15                                   # träges Flackern
        flick = np.where(self.seg_state == 2, np.where(self.seg_flick < 0.15, 0.0, 0.4 + 0.6 * self.seg_flick), 1.0)
        seg_on = ((self.seg_state == 1) | (self.seg_state == 2)).astype(float)
        self.onmask = seg_on[self.seg_id]
        self.level = (self.seg_lvl * flick)[self.seg_id]
        work = self.onmask * self.level * (0.6 + 0.4 * live) * (1.0 - 0.03 * sev * r.random(n))
        frame = np.outer(work * red, RED) + np.outer(work * green, GREEN)
        # Kampf an der Front: schnelles Sirren rot/grün, mit dem Bass heller
        side = np.sin(now * (2.0 + 2.5 * bass) + x * 40.0 + self.noise_ph[1] * 3.0) > 0.0        # langsames Wabern an der Front
        fight = contested * (0.3 + 0.5 * bass) * (0.4 + 0.4 * sev) * (0.15 + 0.85 * self.onmask)
        frame += np.outer(fight * side, RED) + np.outer(fight * ~side, GREEN)
        # Störungen
        if now >= self.ev_next:
            self.ev_next = now + r.uniform(4.0, 14.0) / (0.6 + 0.6 * sev)
            kind = r.choice(["strobe", "sweep", "black", "storm", "strobe", "sweep"])
            if kind == "strobe":                                  # Kurzschluss: Block blitzt voll und stirbt
                i0 = r.integers(0, n); w = int(r.integers(8, max(9, n // 12)))
                hold = r.uniform(0.15, 0.5)
                self.strobe = (i0, min(n, i0 + w), now + hold, "red" if r.random() < target + 0.2 else "green")
                self.dead[i0:min(n, i0 + w)] = now + hold + r.uniform(1.0, 5.0)
            elif kind == "sweep":                                 # Störlinie rast durch
                self.sweep = (now, 1.0 if r.random() < 0.5 else -1.0, "red" if r.random() < target + 0.3 else "green", r.uniform(0.8, 2.0))
            elif kind == "black":
                self.black_until = now + r.uniform(0.15, 0.6)
            else:                                                 # Rauschsturm in einem Bereich
                i0 = r.integers(0, n); w = int(r.integers(n // 10, max(n // 10 + 1, n // 3)))
                self.storm = (i0, min(n, i0 + w), now + r.uniform(1.0, 3.0))
        i0, i1, until, colr = self.strobe
        if now < until:
            frame[i0:i1] = (RED if colr == "red" else GREEN) * (0.85 + 0.15 * math.sin(now * 90.0))
        t0, d, colr, dur = self.sweep
        if now - t0 < dur:
            pos = (now - t0) / dur
            pos = pos if d > 0 else 1.0 - pos
            w = np.exp(-((x - pos) / 0.02) ** 2)
            frame += np.outer(w, RED if colr == "red" else GREEN)
        i0, i1, until = self.storm
        if now < until:
            if self.storm_noise is None or len(self.storm_noise) != i1 - i0 or int(now * 8.0) != self.storm_tick:
                self.storm_noise, self.storm_tick = r.random(i1 - i0), int(now * 8.0)
            noise = self.storm_noise
            frame[i0:i1] = np.outer((noise > 0.7) * noise, RED) + np.outer((noise < 0.25) * (1.0 - noise), GREEN) * 0.7
        if phase == "reboot":                                     # Neustart: grüne Linie fegt von vorne, dahinter ruhiges Grün
            w = np.exp(-((x - k) / 0.03) ** 2)
            frame = np.outer((x < k).astype(float) * 0.3 * self.onmask, GREEN) + np.outer(w, GREEN)
        elif phase == "stable":
            breath = 0.25 + 0.15 * math.sin(now * 1.5) + 0.2 * self.bass_s
            frame = np.outer(self.onmask * breath, GREEN) + np.outer(self.glow, GREEN) * 0.6
            if r.random() < 0.3:
                self.glow[r.integers(0, n)] = 1.0
        if now < self.black_until:                                # Totalausfall
            frame[:] = 0.0
        if phase in ("error", "alarm") and is_beat:               # Alarm: alles Rote zuckt auf den Beat
            frame += np.outer(red * self.onmask, RED) * 0.5
        alive = (self.dead < now).astype(float)
        return frame * alive[:, None]

    # -- Senden --------------------------------------------------------------------------------------------------
    def _send(self, frame: np.ndarray, now: float) -> None:
        try:
            # Kanal-Remap falls konfiguriert (z. B. WS2814: Drahtfolge W,R,G,B → col_remap=[0,3,1,2])
            remap = self._col_remap
            if remap is not None:
                src = np.zeros((frame.shape[0], 4), dtype=np.uint8)
                src[:, :3] = frame                                # RGB in erste 3 Kanäle, W=0
                frame4 = np.stack([src[:, i] for i in remap], axis=1)
            else:
                frame4 = None
            if self.n <= 490:
                if frame4 is not None:
                    self.sock.sendto(bytes([DRGBW, self.timeout]) + frame4.tobytes(), (self.host, self.udp_port))
                else:
                    self.sock.sendto(bytes([DRGB, self.timeout]) + frame.tobytes(), (self.host, self.udp_port))
            else:
                data = frame4 if frame4 is not None else frame
                proto = DNRGBW if frame4 is not None else DNRGB
                bpp = 4 if frame4 is not None else 3
                chunk = CHUNK if bpp == 3 else (CHUNK * 3 // 4)
                for start in range(0, self.n, chunk):             # Indexed: Startindex (2 Byte, big endian) je Paket
                    part = data[start:start + chunk]
                    head = bytes([proto, self.timeout, (start >> 8) & 0xFF, start & 0xFF])
                    self.sock.sendto(head + part.tobytes(), (self.host, self.udp_port))
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
