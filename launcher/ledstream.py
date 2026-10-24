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
import re
import socket
import threading
import time
import urllib.request

import numpy as np

from launcher import wled

log = logging.getLogger("leds")

# Grundprogramm je Szene (ruhig; Specials kommen aus den Ereignissen der Szene über wled.apply_mode_async / led_state)
SCENE_BASE = {
    "navcomputer": "stars", "planets": "stars", "timejump": "timejump", "neonrace": "stars", "splash": "stars",
    "campfire": "fire",
    "blackhole": "vortex", "core": "vortex", "flux": "vortex", "pond": "vortex",
    "rooftop": "rain",
    "taxi": "breathe", "oracle": "breathe", "clocktower": "breathe", "woodeye": "breathe", "trip": "breathe",
    "hearttree": "breathe", "square": "breathe",
    "blackice": "glitch", "paradox": "glitch", "overdose": "glitch",
    "hal": "hal",
}
PLANET_COLORS = ([235.0, 160.0, 60.0], [70.0, 120.0, 255.0], [220.0, 60.0, 40.0], [90.0, 200.0, 110.0],
                 [170.0, 90.0, 255.0], [180.0, 230.0, 255.0], [255.0, 200.0, 120.0])
STATE_PROFILE = re.compile(r"^(rooftop_(rain|fog|acid|ash)|hearttree_(spring|summer|autumn|winter)|square_\d+|campfire_big)$")
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
        self.marquee = [_saturate(self.col, 1.4), _saturate(self.col, 1.4) * 0.35, _saturate(acc, 1.4)]
        self.mq_pos = 0.0
        self.mq_target = 0.0                                      # Blockschritte (je Beat einer)
        self.mq_pos_s = 0.0
        self.mq_tick = 0.0
        self.mq_dir = 1.0
        self.mq_rot = 0
        self.mq_beats = 0
        self.mq_flip_at = 0.0
        # zweites Muster "Lauflicht": ein Block an, einer aus, im Wechsel; hüpft je Beat einen Block weiter, Drop = Richtung
        # umkehren und meist neue Farbe; wechselt sich mit der Markise ab (mq_mode 0 Markise, 1 Lauflicht, mq_mix = Überblendung)
        self.mq_mode = 0
        self.mq_mix = 0.0
        self.mq_mode_at = time.monotonic() + self.rng.uniform(45.0, 90.0)
        self.chase_ci = 0                                         # Lauflichtfarbe: 0 A, 1 B, 2 A mit gedrehtem Farbton
        self.chase_hue = 0.0
        self.ch_step = 0                                          # Lauflicht: Schritt in Ansteuerpunkten, hart je Beat
        self.ch_tick = 0.0
        self.sp_next = time.monotonic() + self.rng.uniform(15.0, 30.0)   # Specials: einzelner Läufer, Überholer, Kreuzung
        self.base = SCENE_BASE.get(scene, "")
        self.specials: list[dict] = []                            # aktive Specials (kind, t0, len, col, ...)
        self.tint = None                                          # Grundfarbe überschrieben (Wetter, Jahreszeit, blaues Feuer)
        self.tint_until = 0.0
        self.boost_until = 0.0                                    # Sterne schneller/heller (Start, Nitro, Zeitsprung)
        self.planet_next = time.monotonic() + self.rng.uniform(25.0, 45.0)
        self.stars = None
        self.drips: list[list] = []
        self.drip_next = 0.0
        self.vdots = None
        self.c_red, self.c_green = RED.copy(), GREEN.copy()       # Farben des Störprogramms (Systemfehler rot/grün, sonst Thema)
        self.scr_col = None                                       # Bildschirmfarbe (Hauptfarbe, Akzent), weich nachgeführt
        self.field = None                                         # HAL: ein einzelnes Feld wandert im Beat-Schritt durch
        self.field_next = time.monotonic() + self.rng.uniform(20.0, 50.0)
        self.field_pos_s = 0.0
        self.hal_phase = 0.0                                      # Lauf der Korridorfelder
        self.fronts: list[dict] = []                              # Zeitsprung: Farbfronten (col, pos)
        self.front_next = 0.0
        self.front_col_i = 0
        # Helligkeit je Modus steht allein im Profil-bri (wled.toml), damit Stream und HTTP-Rückfall gleich hell sind
        self.scr_acc = None
        self.scr_target = None
        self.step_s = 0.0                                         # Beat-Schritt: 1 2 3 4, weich eingerastet (Muster rückt nach hinten)
        self.bar_lift = 0.0                                       # die "1" eines Takts hebt kurz an
        if self.base == "glitch":
            a, b = self.col.copy(), self.col2.copy()
            for c in (a, b):
                if c.max() > 0:
                    c *= 200.0 / c.max()
            self.c_red, self.c_green = a, b
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
            self.embers = np.clip(self.nrng.random(n) * 1.4 - 0.2, 0.0, 1.0) ** 1.5   # nicht jede LED glüht gleich
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
        """Ereignis-Profil einer Szene (wled.apply_mode_async) -> passendes Special statt Blitz: throw = verschluckt,
        eject/emp/overload = Druckwelle von der Mitte, lightning/strike/storm = Blitz mit Grollen, fireworks, blackout,
        log = Funken, blue = blaue Tönung, start/nitro/jump = Schub, horn = Doppelblink, Wetter/Jahreszeit/Epoche =
        neue Grundfarbe, alles andere = eine Welle in der Profilfarbe."""
        now = time.monotonic()
        col = _rgb(profile.get("col"), [255, 255, 255])
        col2 = _rgb(profile.get("col2"), [0, 0, 0])
        n = name.lower()
        if STATE_PROFILE.match(n):
            self.tint, self.tint_until = (col, col2), now + 1e9
            return
        if n in ("campfire", "rooftop", "hearttree", "square", "woodeye", "oracle", "clocktower", "blackhole", "core",
                 "flux", "neonrace", "timejump", "slots") and self.tint is not None:
            self.tint = None                                      # zurück auf das Modusprofil
            return
        if "throw" in n:
            self._add(now, "swallow", 2.2, col, d=self.rng.choice((1.0, -1.0)))
        elif "eject" in n or "emp" in n or "overload" in n or "discharge" in n:
            self._add(now, "burst", 1.6, col)
        elif "lightning" in n or "strike" in n or "storm" in n:
            self._add(now, "lightning", 1.8, col)
        elif "fireworks" in n:
            self._add(now, "fireworks", 3.5, col)
        elif "blackout" in n:
            self._add(now, "blackout", 3.0, col)
        elif "log" in n:
            self._add(now, "sparks", 2.5, col)
        elif "blue" in n:
            self.tint, self.tint_until = (col, col2), now + 30.0
        elif "jump" in n:
            self.boost_until = now + 3.0
            self._add(now, "lightning", 1.2, col)
        elif "start" in n or "nitro" in n:
            self.boost_until = now + 3.0
            self._add(now, "wave", 2.2, col, d=1.0)
        elif n == "horn":
            self._add(now, "blink2", 0.7, col)
        elif n == "fx":
            self._add(now, "wave", 2.5, self.col3, d=self.rng.choice((1.0, -1.0)))
        else:
            self._add(now, "wave", 2.8, col, d=self.rng.choice((1.0, -1.0)))

    def wants_screen(self) -> bool:
        """Grundprogramme folgen der Bildschirmfarbe; Systemfehler und Markise haben feste Farben."""
        return self.base not in ("", "error") and self.sock is not None

    def set_screen(self, px) -> None:
        """Winziges Abbild des Schirms (h, w, 3) -> Hauptfarbe (satt gewichteter Mittelwert) und Akzent (andere Farbe
        im Bild, sonst Farbton um 50 Grad gedreht). Wird im update() langsam nachgeführt."""
        try:
            p = np.asarray(px, dtype=float).reshape(-1, 3)
        except Exception:
            return
        mx = p.max(axis=1)
        mn = p.min(axis=1)
        sat = np.where(mx > 1.0, (mx - mn) / np.maximum(mx, 1.0), 0.0)
        w = sat * (mx / 255.0) + 0.02
        main = (p * w[:, None]).sum(axis=0) / w.sum()
        main = _saturate(main, 1.4)
        hue = _hue(p)
        h0 = _hue(main[None, :])[0]
        dh = np.abs(((hue - h0 + 180.0) % 360.0) - 180.0)
        other = (dh > 50.0) & (sat > 0.3) & (mx > 60.0)
        if other.sum() >= max(3, len(p) // 40):
            w2 = (sat * mx / 255.0)[other]
            acc = _saturate((p[other] * w2[:, None]).sum(axis=0) / w2.sum(), 1.4)
        else:
            acc = _hsv(((h0 + 50.0) / 360.0) % 1.0, 0.9, 1.0)
        self.scr_target = (main, acc)

    def _add(self, now: float, kind: str, length: float, col, **p) -> None:
        if len(self.specials) >= 4:
            self.specials.pop(0)
        sp = {"kind": kind, "t0": now, "len": length, "col": np.array(col, dtype=float)}
        if kind == "fireworks":
            sp["blooms"] = [(self.rng.random(), self.rng.uniform(0.0, length - 1.0), np.array(self.rng.choice(PLANET_COLORS)))
                            for _ in range(6)]
        if kind == "blackout":
            sp["back"] = self.nrng.uniform(0.0, 1.0, self.n) if self.n else None
        sp.update(p)
        self.specials.append(sp)

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
            if self.beats % 4 == 1:
                self.bar_lift = 1.0                               # die "1"
        self.step_s += (float(self.beats) - self.step_s) * min(1.0, dt * 5.0)   # Schritt rastet weich ein (~0,3 s)
        self.bar_lift *= 0.9
        if self.scr_target is not None:                           # Bildschirmfarbe langsam übernehmen (~1 s)
            tm, ta = self.scr_target
            if self.scr_col is None:
                self.scr_col, self.scr_acc = tm.copy(), ta.copy()
            else:
                self.scr_col += (tm - self.scr_col) * min(1.0, dt * 1.5)
                self.scr_acc += (ta - self.scr_acc) * min(1.0, dt * 1.5)
            if self.base == "glitch":
                self.c_red, self.c_green = self.scr_col, self.scr_acc
        if live and self.e_fast > 1.5 * self.energy + 0.15 and self.energy > 0.1 and now - self.last_drop > 12.0:
            self.last_drop = now
            self.flash = 0.55                                     # Drop: ein weicher Aufheller, kein Stroboskop
            self.flash_col = self.col3
        self.flash *= 0.86
        self.glow *= 0.80
        st = state or {}
        program = st.get("program", "") or self.base
        if not program:
            program = "fire" if self.fx in (45, 66, 42) else ("scanner" if self.fx == 40 else ("rainbow" if self.fx in (9, 94) else "pulse"))
        if program == "error":
            frame = self._error(now, dt, st, bass, high, is_beat, live)
        elif program == "glitch":                                 # Black Ice, Paradoxon, Überdosis: Störprogramm in Themenfarben
            cyc = (now * 0.025) % 1.0
            phase, k = (("code", cyc / 0.3) if cyc < 0.3 else ("break", (cyc - 0.3) / 0.25) if cyc < 0.55 else
                        ("error", (cyc - 0.55) / 0.2) if cyc < 0.75 else ("recovery", (cyc - 0.75) / 0.25))
            frame = self._error(now, dt, {"phase": phase, "k": k, "pct": k, "good": False}, bass, high, is_beat, live)
        elif program == "slots":
            frame = self._slots(now, dt, st, bass, high, is_beat, live)
        elif program == "stars":
            frame = self._stars(now, dt, st, bass, high, is_beat, live)
        elif program == "hal":
            frame = self._hal(now, dt, st, bass, high, is_beat, live)
        elif program == "timejump":
            frame = self._timejump(now, dt, st, bass, high, is_beat, live)
        elif program == "vortex":
            frame = self._vortex(now, dt, st, bass, high, is_beat, live)
        elif program == "breathe":
            frame = self._breathe(now, dt, st, bass, high, is_beat, live)
        elif program == "rain":
            frame = self._rain(now, dt, st, bass, high, is_beat, live)
        elif program == "fire":
            frame = self._fire(now, dt, st, bass, high, is_beat, live)
        elif program == "scanner":
            frame = self._scanner(now, dt, bass, high, is_beat, live)
        elif program == "rainbow":
            frame = self._rainbow(now, dt, bass, high, is_beat, live)
        else:
            frame = self._music(now, dt, bass, high, is_beat, live)
        frame = self._apply_specials(frame, now, dt, bass)
        if self.flash > 0.02:
            fc = self.c_red if program in ("error", "glitch") else self.flash_col
            frame = frame + (fc - frame) * self.flash
        frame = np.clip(frame * self.bri, 0, 255).astype(np.uint8)
        self._send(frame, now)

    # -- Programme -----------------------------------------------------------------------------------------------
    def _slots(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Casino-Markise wie ein Vegas-Eingang: Blöcke in derselben Farbe (Farbe A hell, Farbe A gedimmt, Farbe B hell im Wechsel, kein Weiß), alle an, nur die Helligkeit wandert leicht; das Muster rückt genau einen Block je Beat weiter (1 2 3 4), weich eingerastet, mal vor, mal zurück,
        beim Drehen läuft es schnell von selbst; alle paar Beats wechseln die Farben durch, ab und zu kehrt die Richtung um. Zweites Muster
        (Lauflicht, wechselt sich alle 45-90 s mit der Markise ab, weich überblendet): ein Ansteuerpunkt an, der nächste aus, ganz mechanisch
        ohne Gleiten und Flimmern; auf jedem Beat springt das Muster hart einen Punkt weiter (an wird aus, aus wird an), beim Drop kommt
        eine neue Farbe. Gewinn: klein = zweimal
        Blitzen, groß = heller Lauf von vorne, Jackpot = Gold/Weiß-Stroboskop und Funkeln."""
        n = self.n
        x = self._idx()
        idx = np.arange(n)
        spinning = bool(st.get("spinning", False))
        win = int(st.get("win", 0))
        cols = st.get("colors") or []
        if len(cols) >= 2:                                        # Lichtfarben des Automaten auf dem Schirm: A, Warmweiß, B
            a = _saturate(np.array(cols[0], dtype=float), 1.5)   # satt, kein Weiß
            b = _saturate(np.array(cols[1], dtype=float), 1.5)
            mid = a * 0.35                                        # dritter Block: Farbe A gedimmt (Mischung von Gegenfarben wäre weiß)
            self.marquee = [a, mid, b]
        age = float(st.get("win_age", 0.0))
        is_drop = 0.0 < now - self.last_drop <= dt * 1.5         # update() hat gerade einen Drop erkannt
        if now >= self.mq_mode_at and win == 0 and not spinning:  # Muster wechseln: Markise <-> Lauflicht
            self.mq_mode = 1 - self.mq_mode
            self.mq_mode_at = now + self.rng.uniform(45.0, 90.0)
        self.mq_mix += (float(self.mq_mode) - self.mq_mix) * min(1.0, dt / 1.5)
        if is_drop:                                               # Drop: Richtung umkehren, meist neue Lauflichtfarbe
            self.mq_dir *= -1.0
            self.mq_flip_at = now + self.rng.uniform(6.0, 14.0)
            self.chase_ci = (self.chase_ci + self.rng.choice((1, 2))) % 3
            self.chase_hue = self.rng.uniform(0.12, 0.5)
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
        block = max(3, n // 60)                                   # Blockgröße nach LED-Dichte (784 LEDs -> 13 LEDs, ~8 cm)
        period = 3 * block
        if spinning:                                              # Walzen drehen: läuft von selbst, schnell
            self.mq_pos += self.mq_dir * block * 4.0 * dt
        else:                                                     # sonst genau ein Block je Beat, weich eingerastet (1 2 3 4)
            if now - self.last_beat > 2.0 and now - self.mq_tick > 0.6:   # ohne Beats im eigenen langsamen Takt
                self.mq_tick = now
                self.mq_target += 1.0
            if is_beat:
                self.mq_target += 1.0
            self.mq_pos_s += (self.mq_target - self.mq_pos_s) * min(1.0, dt * 5.0)
            self.mq_pos = self.mq_dir * self.mq_pos_s * block
        self.mq_pos %= 2 * period                                # 6 Blöcke: Markise (3) und Lauflicht (2) teilen die Lage
        shift = idx + int(self.mq_pos)
        if self.reverse:
            shift = (n - 1 - idx) + int(self.mq_pos)
        ci = ((shift // block) + self.mq_rot) % 3
        colors = np.array(self.marquee)[ci]
        twinkle = 0.8 + 0.2 * np.sin(now * 1.7 + idx * 0.35) * np.sin(now * 0.9 + idx * 0.11)
        level = twinkle * ((0.75 + 0.25 * self.bass_s) * live + (1.0 - live) * 0.5)
        if spinning:
            level = twinkle * 1.0
        frame = colors * level[:, None]
        if is_beat or (now - self.last_beat > 2.0 and now - self.ch_tick > 0.6):   # Lauflicht-Schritt: hart, je Beat ein Punkt
            self.ch_tick = now
            self.ch_step += 1
        if self.mq_mix > 0.01:                                    # Lauflicht: Ansteuerpunkt an, nächster aus, mechanisch
            if self.chase_ci == 0:
                ccol = self.marquee[0]
            elif self.chase_ci == 1:
                ccol = self.marquee[2]
            else:
                h0 = float(_hue(self.marquee[0][None, :])[0]) / 360.0
                ccol = _hsv((h0 + self.chase_hue) % 1.0, 1.0, min(1.0, float(self.marquee[0].max()) / 255.0))
            on = ((idx + self.ch_step) % 2 == 0).astype(float)    # Punkt für Punkt im Wechsel, springt je Beat um einen Punkt
            lvl = 1.0 * live + (1.0 - live) * 0.5                 # konstant hell, kein Flimmern
            chase = np.outer(on * lvl, ccol)
            frame = frame * (1.0 - self.mq_mix) + chase * self.mq_mix
        gold = self.marquee[0]
        white = _saturate(self.marquee[0] * 0.7 + WHITE * 0.3, 1.2)   # Glanzlicht: aufgehellte Hauptfarbe statt Weiß
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
                self.mq_pos = (self.mq_pos + self.mq_dir * block * 3.0 * dt) % period
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

    def _base_col(self) -> tuple:
        """Grund- und Akzentfarbe: Tönung (Wetter, Jahreszeit, blaues Feuer) vor Bildschirmfarbe vor Modusprofil."""
        if self.tint is not None and time.monotonic() < self.tint_until:
            a, b = self.tint
            return a, (b if b.max() > 8 else self.col2)
        if self.scr_col is not None:
            return self.scr_col, self.scr_acc
        return self.col, self.col2

    def _music(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        """Rückfall für Szenen ohne eigenes Programm: Pegel vom Bass von der Mitte nach außen, Beat = sanfte Welle."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        if is_beat:
            self.pulses.append((now, 1))
        travel = 2.0 - 0.5 * self.e_fast
        self.pulses = [(t0, d) for t0, d in self.pulses if now - t0 < travel + 0.2]
        vu = min(1.0, self.bass_s * 1.15) * live
        dist = np.abs(x - 0.5) * 2.0
        meter = np.clip((vu - dist) / (2.0 / max(2, n)) + 0.5, 0.0, 1.0)
        frame = np.outer(meter * (0.3 + 0.5 * vu), col)
        for t0, _ in self.pulses:
            pos = (now - t0) / travel
            w = np.exp(-((x - pos) / 0.05) ** 2) * max(0.0, 1.0 - pos * 0.6)
            frame += np.outer(w, col * 0.7 + col2 * 0.3) * 0.7
        if live < 0.5:
            pos = (math.sin(now * 0.15) * 0.5 + 0.5)
            frame = np.outer(np.exp(-((x - pos) / 0.06) ** 2) * (0.2 + 0.15 * math.sin(now * 1.2)), col)
        return frame

    def _stars(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Sternenflug, mellow: ein langsames Farbfeld in Bildschirmfarbe und Akzent (zwei lange Wellen, treiben kaum),
        darüber wenige Sterne, die langsam nach hinten ziehen; auf jedem Beat (1 2 3 4) rückt alles einen Schritt nach
        hinten, weich eingerastet, die 1 hebt kurz an. Specials: alle 25-45 s ein Planet (weiche Kugel, füllt im Vorbeiflug
        kurz alles in seiner Farbe); Navigationscomputer: Kometenschauer = einzelne Kometen, Asteroidenfeld = graue Brocken,
        Wurmloch/Sonne/Nebel = Tönung; Start/Nitro/Zeitsprung = Schub."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        r = self.nrng
        if self.stars is None:
            k = max(4, n // 70)
            self.stars = np.stack([r.uniform(0.0, 1.0, k), r.uniform(0.02, 0.05, k), r.uniform(0.3, 0.8, k)], axis=1)
        ev = str(st.get("event", "")).upper()
        flying = bool(st.get("flying", True))
        boost = 1.0 if now >= self.boost_until else 2.2
        drift = ((0.4 + 0.6 * self.e_fast) * live + (1.0 - live) * 0.4) * boost * (1.0 if flying else 0.4)
        self.stars[:, 0] += self.stars[:, 1] * drift * dt
        wrap = self.stars[:, 0] > 1.05
        self.stars[wrap, 0] = -0.05
        self.stars[wrap, 2] = r.uniform(0.3, 0.8, int(wrap.sum()))
        step = self.step_s * 0.06                                 # je Beat ein Sechzehntel der Kette nach hinten
        xs = (x - step) % 1.0
        f1 = 0.5 + 0.5 * np.sin(xs * 2.0 * math.pi * 1.3 - now * 0.08)
        f2 = 0.5 + 0.5 * np.sin(xs * 2.0 * math.pi * 0.7 + now * 0.05 + 1.7)
        level = (0.08 + 0.18 * self.bass_s + 0.08 * self.bar_lift) * live + (1.0 - live) * 0.06
        frame = np.outer(f1 * level, col) + np.outer(f2 * f2 * level * 0.8, col2)
        star_col = col * 0.3 + WHITE * 0.7
        if "ASTEROID" in ev:
            star_col = np.array([150.0, 150.0, 140.0])
        pos = ((self.stars[:, 0] + step) % 1.1 - 0.05)[:, None]
        g = np.exp(-((x[None, :] - pos) / 0.004) ** 2) * self.stars[:, 2][:, None]
        frame += np.outer(g.sum(axis=0) * (0.5 + 0.3 * self.bar_lift) * (1.0 if boost < 2 else 1.4), star_col)
        if "KOMET" in ev and r.random() < 0.35 * dt:              # Kometenschauer: ab und zu ein Komet mit Schweif
            self._add(now, "comet", 2.0, np.array([200.0, 230.0, 255.0]), d=1.0)
        if "WURMLOCH" in ev:
            frame = frame * 0.6 + np.outer(np.full(n, 0.12 + 0.08 * math.sin(now * 1.2)), np.array([170.0, 80.0, 255.0]))
        elif "SONNE" in ev:
            frame += np.outer(np.full(n, 0.12 + 0.08 * math.sin(now * 0.7)), np.array([255.0, 140.0, 30.0]))
        elif "NEBEL" in ev:
            frame += np.outer(0.5 + 0.5 * np.sin(x * 6.0 + now * 0.3), _hsv((now * 0.03) % 1.0, 0.8, 0.25))
        if now >= self.planet_next and not ev:                    # Planet zieht vorbei
            self.planet_next = now + self.rng.uniform(25.0, 45.0)
            self._add(now, "planet", 4.5, np.array(self.rng.choice(PLANET_COLORS)), d=1.0)
        return frame

    def _hal(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """HAL 3000: dunkel- und hellrote Felder wie die Korridorzellen ziehen langsam und immer in eine Richtung vorbei
        (Bildschirmfarbe, 25 % dunkler als die anderen). Special: ab und zu kommt von einem Ende ein einzelnes helles Feld
        und wandert im Beat-Schritt durch die ganze Kette, rund eine Minute lang; mal von vorne, mal von hinten, ab und zu
        ein Schritt zurück."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        # Grund: dunkel- und hellrote Felder wie die Zellen des Korridors ziehen immer in eine Richtung vorbei
        # (von vorne nach hinten), langsam, etwas schneller mit der Energie; der Bass hebt die hellen Felder leicht
        self.hal_phase += dt * (0.035 + 0.05 * self.e_fast) * live + dt * 0.03 * (1.0 - live)
        cells = 8.0                                               # Paare hell/dunkel über die Kette
        wave = np.sin((x - self.hal_phase) * 2.0 * math.pi * cells)
        bright = np.clip(wave * 2.5, -1.0, 1.0) * 0.5 + 0.5       # blockig statt sinusförmig
        edge = np.clip((np.abs(wave) * 2.5), 0.0, 1.0)            # weiche Kanten zwischen den Feldern
        lvl_dark, lvl_bright = 0.12, 0.42 + 0.25 * self.bass_s * live + 0.08 * self.bar_lift
        level = (lvl_dark + (lvl_bright - lvl_dark) * bright) * (0.85 + 0.15 * edge)
        frame = np.outer(level, col)
        if self.field is None and now >= self.field_next:
            d = self.rng.choice((1.0, -1.0))
            self.field = {"pos": 0.0 if d > 0 else 1.0, "dir": d, "last": now, "steps": 0}
            self.field_pos_s = self.field["pos"]
        fd = self.field
        if fd is not None:
            step_due = is_beat or (now - self.last_beat > 2.0 and now - fd["last"] > 0.55)   # ohne Beats im eigenen Takt
            if step_due and now - fd["last"] > 0.2:
                fd["last"] = now
                fd["steps"] += 1
                back = self.rng.random() < 0.12 and fd["steps"] > 3                        # ab und zu ein Schritt zurück
                fd["pos"] += fd["dir"] * (1.0 / 95.0) * (-1.0 if back else 1.0)          # mit Rückschritten ~110 Beats = eine Minute
            self.field_pos_s += (fd["pos"] - self.field_pos_s) * min(1.0, dt * 6.0)
            w = np.exp(-((x - self.field_pos_s) / 0.009) ** 2)                            # weiches Feld, ~14 LEDs
            frame += np.outer(w * (0.55 + 0.25 * self.bass_s), col * 0.55 + WHITE * 0.45)
            if (fd["dir"] > 0 and fd["pos"] > 1.04) or (fd["dir"] < 0 and fd["pos"] < -0.04):
                self.field = None
                self.field_next = now + self.rng.uniform(40.0, 90.0)
        return frame

    def _timejump(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Zeitsprung: Farbfronten kommen langsam von vorne herein und füllen die Kette, jede schiebt die vorige nach hinten
        (Farben aus der Bildschirmfarbe, im Farbton gedreht); auf jedem Beat ein kleiner Schub nach hinten. Zeitsprung
        (`timejump_jump` -> `boost_until`) = Volldampf: Fronten rasen, elektrische Farben, Kometen; danach wieder mellow."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        boost = now < self.boost_until
        if not self.fronts:
            self.fronts.append({"col": _saturate(col, 1.3), "pos": 1.2})
        if now >= self.front_next:                                # neue Front von vorne
            self.front_next = now + (self.rng.uniform(0.25, 0.5) if boost else self.rng.uniform(8.0, 15.0))
            self.front_col_i += 1
            if boost:
                c = np.array(self.rng.choice(([180.0, 220.0, 255.0], [80.0, 160.0, 255.0], [255.0, 255.0, 255.0], [255.0, 170.0, 60.0])))
            else:
                base = col if self.front_col_i % 2 == 0 else col2
                h = (_hue(base[None, :])[0] + self.rng.uniform(-60.0, 60.0)) / 360.0
                c = _hsv(h % 1.0, 0.9, 1.0)
            self.fronts.append({"col": c, "pos": -0.05})
        speed = ((0.03 + 0.03 * self.e_fast) * live + (1.0 - live) * 0.02) * (14.0 if boost else 1.0)
        frame = np.zeros((n, 3))
        keep = []
        for i, fr in enumerate(self.fronts):
            fr["pos"] += speed * dt
            if is_beat and not boost:
                fr["pos"] += 0.012                                # Beat: kleiner Schub nach hinten
            keep.append(fr)
        # jede Front überdeckt die vorigen bis zu ihrer Position (weiche Kante); Fronten jenseits der Kette bleiben als Grund
        while len(keep) > 1 and keep[1]["pos"] > 1.15:
            keep.pop(0)
        self.fronts = keep
        for fr in self.fronts:
            cover = np.clip((fr["pos"] - x) / 0.04 + 0.5, 0.0, 1.0)
            frame = frame * (1.0 - cover)[:, None] + np.outer(cover, fr["col"])
        lvl = (0.25 + 0.3 * self.bass_s + 0.08 * self.bar_lift) * live + (1.0 - live) * 0.2
        if boost:
            lvl = 0.6 + 0.3 * math.sin(now * 25.0)
            if self.nrng.random() < 2.5 * dt:
                self._add(now, "comet", 0.8, np.array([200.0, 230.0, 255.0]), d=1.0)
        return frame * lvl

    def _vortex(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Strudel: schwache Punkte driften von beiden Enden zur Mitte, die Mitte glimmt mit dem Bass in der Akzentfarbe.
        Specials aus der Szene: Objekt geworfen = Punkt läuft zur Mitte und wird verschluckt (Aufleuchten), Umkehrung/EMP =
        Druckwelle von der Mitte nach außen."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        r = self.nrng
        if self.vdots is None:
            k = max(6, n // 50)
            self.vdots = np.stack([r.uniform(0.0, 1.0, k), r.uniform(0.03, 0.07, k)], axis=1)
        speed = (0.3 + 0.5 * self.e_fast) * live + (1.0 - live) * 0.3
        d = self.vdots[:, 0]
        d += np.where(d < 0.5, 1.0, -1.0) * self.vdots[:, 1] * speed * dt
        if is_beat:
            d += np.where(d < 0.5, 1.0, -1.0) * 0.03                 # Beat: ein Ruck zur Mitte
        gone = np.abs(d - 0.5) < 0.02
        self.vdots[gone, 0] = np.where(r.random(int(gone.sum())) < 0.5, 0.0, 1.0)
        g = np.exp(-((x[None, :] - d[:, None]) / 0.005) ** 2)
        frame = np.outer(g.sum(axis=0) * 0.6, col)
        centre = np.exp(-((x - 0.5) / (0.05 + 0.1 * self.bass_s)) ** 2) * (0.2 + 0.6 * self.bass_s) * live
        frame += np.outer(centre, col2 if col2.max() > 60 else col * 0.6 + WHITE * 0.4)
        frame += np.outer(np.full(n, 0.02), col)
        frame += np.outer(np.exp(-((x - 0.5) / 0.15) ** 2) * 0.2 * self.bar_lift, col)   # die 1 des Takts zieht an
        return frame

    def _breathe(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Atmen: die Kette atmet langsam in der Grundfarbe, zwei weiche Wolken in der Akzentfarbe wandern,
        der Bass hebt das Ganze, Höhen setzen seltene Funken. Specials: Wellen aus den Szenen-Ereignissen."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        breath = 0.08 + 0.07 * math.sin(now * 0.5) + 0.2 * self.bass_s * live + 0.06 * self.bar_lift
        frame = np.outer(np.full(n, breath), col)
        for i, (f, ph) in enumerate(((0.05, 0.0), (0.035, 2.1))):
            c = (0.5 + 0.45 * math.sin(now * f + ph) + self.step_s * 0.04) % 1.0   # Wolken rücken je Beat nach hinten
            w = np.exp(-((x - c) / 0.12) ** 2) * (0.12 + 0.2 * self.bass_s)
            frame += np.outer(w, col2 if col2.max() > 60 else col)
        if high > 0.4 and self.rng.random() < high * 0.15:
            self.glow[self.nrng.integers(0, n)] = 1.0
        frame += np.outer(self.glow, col * 0.5 + WHITE * 0.5) * 0.5
        return frame

    def _rain(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Regen auf der Dachterrasse: Tropfen laufen von hinten nach vorne, mehr mit der Energie, Grund in der
        Akzentfarbe; Wetter kommt als Tönung aus der Szene. Specials: Blitz mit Grollen, Feuerwerk, Stromausfall."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        if now >= self.drip_next:
            self.drip_next = now + self.rng.uniform(0.5, 1.5) / (0.5 + 0.8 * self.e_fast)
            self.drips.append([now, self.rng.uniform(0.15, 0.3), self.rng.uniform(0.5, 1.0)])
        frame = np.outer(np.full(n, 0.04 + 0.1 * self.bass_s), col2 if col2.max() > 40 else col * 0.4)
        keep = []
        for dr in self.drips:
            pos = 1.0 - (now - dr[0]) * dr[1]
            if pos > -0.05:
                keep.append(dr)
                frame += np.outer(np.exp(-((x - pos) / 0.006) ** 2) * dr[2], col)
        self.drips = keep[-40:]
        return frame

    def _fire(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Lagerfeuer: warmweißes Fackellicht, das je LED träge glimmt und mit der Feuerstufe heller wird, dazu ein leises
        Wabern der ganzen Kette wie Wind in den Flammen; brennt das Feuer blau (Kristall), wird das Licht so lange blau.
        Specials aus der Szene: Holz = Funken."""
        n = self.n
        warm = np.array([255.0, 125.0, 30.0])                  # Kerzenlicht: auf LEDs wirkt erst dieses Orange warmweiß
        blue = np.array([70.0, 120.0, 255.0])
        bk = float(st.get("blue", 0.0)) if st else 0.0
        if self.tint is not None and time.monotonic() < self.tint_until:  # campfire_blue-Profil (Rückfall ohne led_state)
            bk = max(bk, 0.8)
        col = warm * (1.0 - bk) + blue * bk
        lvl = float(st.get("level", 1.5)) / 3.0 if st else 0.5
        self.fire += (self.nrng.random(n) - self.fire) * (0.05 + 0.1 * self.e_fast)
        gust = 0.85 + 0.15 * math.sin(now * 1.7) * math.sin(now * 0.43 + 1.0)                     # Wind in den Flammen
        base = 0.25 + 0.45 * lvl + 0.15 * self.bass_s * live
        heat = np.clip(base * (0.55 + 0.45 * self.fire) * gust, 0.0, 1.0) * (0.6 + 0.4 * self.embers)
        if is_beat and bass > 0.6:
            heat = np.clip(heat + 0.08, 0, 1)
        frame = np.outer(heat, col)
        return frame

    def _scanner(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        """KITT-Scanner: läuft hin und her, Tempo mit der Energie, kräftiger Beat = Richtungswechsel."""
        n = self.n
        col, col2 = self._base_col()
        speed = (0.4 + 1.2 * self.e_fast) * live + 0.25 * (1.0 - live)
        self.scan_pos += self.scan_dir * speed * dt
        if self.scan_pos > 1.0 or self.scan_pos < 0.0:
            self.scan_dir *= -1.0
            self.scan_pos = min(1.0, max(0.0, self.scan_pos))
        if is_beat and bass > 0.7:
            self.scan_dir *= -1.0
        x = self._idx()
        w = np.exp(-((x - self.scan_pos) / (0.06 + 0.06 * self.bass_s)) ** 2)
        return np.outer(np.full(n, 0.02 + 0.05 * self.bass_s), col) + np.outer(w, col) * (0.7 + 0.3 * self.bass_s)

    def _rainbow(self, now, dt, bass, high, is_beat, live) -> np.ndarray:
        n = self.n
        self.hue = (self.hue + dt * (0.02 + 0.12 * self.e_fast)) % 1.0
        x = self._idx()
        h = (self.hue + x * 0.7) % 1.0
        frame = np.array([_hsv(hh, 1.0, 1.0) for hh in h])
        level = (0.15 + 0.5 * self.bass_s) * live + (1.0 - live) * 0.1
        return frame * level

    # -- Specials --------------------------------------------------------------------------------------------------
    def _apply_specials(self, frame: np.ndarray, now: float, dt: float, bass: float) -> np.ndarray:
        n = self.n
        x = self._idx()
        keep = []
        for sp in self.specials:
            k = now - sp["t0"]
            if k > sp["len"]:
                continue
            keep.append(sp)
            u = k / sp["len"]
            col = sp["col"]
            kind = sp["kind"]
            d = float(sp.get("d", 1.0))
            if kind == "planet":                                  # weiche Kugel zieht vorbei und füllt kurz alles
                pos = u if d > 0 else 1.0 - u
                body = np.exp(-((x - pos) / 0.1) ** 2)
                flood = math.exp(-((u - 0.5) / 0.14) ** 2) * 0.75
                frame = frame * (1.0 - 0.5 * flood) + np.outer(body * 0.9 + flood, col)
            elif kind == "wave":
                pos = u if d > 0 else 1.0 - u
                frame += np.outer(np.exp(-((x - pos) / 0.07) ** 2) * (1.0 - 0.5 * u), col)
            elif kind == "comet":
                pos = u * 1.1 if d > 0 else 1.0 - u * 1.1
                head = np.exp(-((x - pos) / 0.008) ** 2) * 0.8
                tail = np.exp(-((x - (pos - d * 0.05)) / 0.04) ** 2) * 0.35
                frame += np.outer(head + tail, col)
            elif kind == "swallow":                               # Punkt zur Mitte, dann Aufleuchten in der Mitte
                if u < 0.6:
                    pos = (0.0 if d > 0 else 1.0) + d * 0.5 * (u / 0.6)
                    frame += np.outer(np.exp(-((x - pos) / 0.01) ** 2), col)
                else:
                    g = (1.0 - (u - 0.6) / 0.4)
                    frame += np.outer(np.exp(-((x - 0.5) / (0.06 + 0.2 * (1.0 - g))) ** 2) * g, col)
            elif kind == "burst":                                 # Druckwelle von der Mitte nach außen
                rad = u * 0.55
                band = np.exp(-((np.abs(x - 0.5) - rad) / 0.05) ** 2) * (1.0 - u)
                frame += np.outer(band, col)
            elif kind == "lightning":                             # zwei kurze Blitze, dann Grollen
                if k < 0.08 or 0.2 < k < 0.32:
                    frame = frame * 0.3 + np.outer(np.ones(n), col * 0.4 + WHITE * 0.6) * 0.9
                elif k > 0.4:
                    rum = (1.0 - u) * 0.25
                    frame += np.outer((self.nrng.random(n) < 0.3) * rum, col * 0.5 + WHITE * 0.5)
            elif kind == "fireworks":                             # Blüten gehen auf und verblassen
                for pos, t0, c in sp["blooms"]:
                    kk = k - t0
                    if 0.0 <= kk < 1.2:
                        w = 0.01 + 0.09 * kk
                        frame += np.outer(np.exp(-((x - pos) / w) ** 2) * (1.0 - kk / 1.2) * 0.9, c)
            elif kind == "blackout":                              # alles aus, dann kommen Abschnitte zögernd zurück
                if k < 1.5:
                    frame = frame * 0.0
                else:
                    back = sp["back"]
                    if back is not None and len(back) == n:
                        frame = frame * (back < (k - 1.5) / (sp["len"] - 1.5))[:, None]
            elif kind == "sparks":                                # Funken poppen auf und verglühen
                if self.nrng.random() < 0.9:
                    self.glow[self.nrng.integers(0, n, size=max(1, n // 80))] = 1.0
                frame += np.outer(self.glow, col) * 0.8
            elif kind == "blink2":
                if k < 0.12 or 0.3 < k < 0.42:
                    frame = frame * 0.2 + np.outer(np.ones(n), col) * 0.8
        self.specials = keep
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
        RED_, GREEN_ = self.c_red, self.c_green                 # Systemfehler rot/grün, Black Ice/Paradoxon/Überdosis Themenfarben
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
        frame = np.outer(work * red, RED_) + np.outer(work * green, GREEN_)
        # Kampf an der Front: schnelles Sirren rot/grün, mit dem Bass heller
        side = np.sin(now * (2.0 + 2.5 * bass) + x * 40.0 + self.noise_ph[1] * 3.0) > 0.0        # langsames Wabern an der Front
        fight = contested * (0.3 + 0.5 * bass) * (0.4 + 0.4 * sev) * (0.15 + 0.85 * self.onmask)
        frame += np.outer(fight * side, RED_) + np.outer(fight * ~side, GREEN_)
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
            frame[i0:i1] = (RED_ if colr == "red" else GREEN_) * (0.85 + 0.15 * math.sin(now * 90.0))
        t0, d, colr, dur = self.sweep
        if now - t0 < dur:
            pos = (now - t0) / dur
            pos = pos if d > 0 else 1.0 - pos
            w = np.exp(-((x - pos) / 0.02) ** 2)
            frame += np.outer(w, RED_ if colr == "red" else GREEN_)
        i0, i1, until = self.storm
        if now < until:
            if self.storm_noise is None or len(self.storm_noise) != i1 - i0 or int(now * 8.0) != self.storm_tick:
                self.storm_noise, self.storm_tick = r.random(i1 - i0), int(now * 8.0)
            noise = self.storm_noise
            frame[i0:i1] = np.outer((noise > 0.7) * noise, RED_) + np.outer((noise < 0.25) * (1.0 - noise), GREEN_) * 0.7
        if phase == "reboot":                                     # Neustart: grüne Linie fegt von vorne, dahinter ruhiges Grün
            w = np.exp(-((x - k) / 0.03) ** 2)
            frame = np.outer((x < k).astype(float) * 0.3 * self.onmask, GREEN_) + np.outer(w, GREEN_)
        elif phase == "stable":
            breath = 0.25 + 0.15 * math.sin(now * 1.5) + 0.2 * self.bass_s
            frame = np.outer(self.onmask * breath, GREEN_) + np.outer(self.glow, GREEN_) * 0.6
            if r.random() < 0.3:
                self.glow[r.integers(0, n)] = 1.0
        if now < self.black_until:                                # Totalausfall
            frame[:] = 0.0
        if phase in ("error", "alarm") and is_beat:               # Alarm: alles Rote zuckt auf den Beat
            frame += np.outer(red * self.onmask, RED_) * 0.5
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


def _saturate(c: np.ndarray, k: float) -> np.ndarray:
    """Farbe auf volle Leuchtkraft bringen und die Sättigung anheben (für LEDs: satt statt pastellig)."""
    c = np.asarray(c, dtype=float)
    if c.max() <= 1.0:
        return np.array([120.0, 120.0, 120.0])
    c = c * (255.0 / c.max())
    m = c.mean()
    return np.clip(m + (c - m) * k, 0.0, 255.0)


def _hue(p: np.ndarray) -> np.ndarray:
    """Farbton in Grad je Zeile (r, g, b)."""
    r, g, b = p[:, 0], p[:, 1], p[:, 2]
    mx = p.max(axis=1)
    mn = p.min(axis=1)
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, (g - b) / d % 6.0, np.where(mx == g, (b - r) / d + 2.0, (r - g) / d + 4.0))
    return (h * 60.0) % 360.0


def _hsv(h: float, s: float, v: float) -> np.ndarray:
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i]
    return np.array([r * 255.0, g * 255.0, b * 255.0])
