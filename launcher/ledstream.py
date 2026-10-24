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
    "navcomputer": "stars", "planets": "stars", "timejump": "timejump", "neonrace": "drive", "splash": "stars",
    "campfire": "fire",
    "blackhole": "vortex", "core": "vortex", "flux": "vortex", "pond": "vortex",
    "rooftop": "city",
    "taxi": "breathe", "oracle": "breathe", "clocktower": "clockwork", "woodeye": "forest", "trip": "trip",
    "hearttree": "heart", "square": "square",
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
CW_WIN = np.array([[255, 107, 173], [64, 242, 224], [255, 194, 71], [173, 133, 255],          # Uhrturm: die acht Neonfarben
                   [115, 255, 148], [255, 128, 82], [107, 173, 255], [255, 158, 107]], dtype=float)  # der Schaufenster


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
        self.bri_prof = float(prof.get("bri", 160)) / 255.0
        self.bri = self.bri_prof * min(1.0, self.dim * wled.knob_factor())
        self.bri_check = 0.0
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
        self.t_first = 0.0                                        # erstes Bild (Drop-Erkennung braucht erst Anlauf)
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
        self.mq_mode = 1                                          # Basis ist das Lauflicht; Markise nur als Special
        self.mq_mix = 1.0
        self.mq_marq_until = 0.0                                  # Markise läuft bis dahin (nach Drop oder Gewinn)
        self.sp_launch = False                                    # Läufer-Special beim nächsten Bild starten (Drop)
        self.chase_ci = 0                                         # Lauflichtfarbe: 0 A, 1 B, 2 A mit gedrehtem Farbton
        self.chase_hue = 0.0
        self.ch_step = 0                                          # Lauflicht: Schritt in Ansteuerpunkten, hart je Beat
        self.ch_tick = 0.0
        # Special "Zellteilung": ein Punkt in anderer Farbe wandert in den leeren LEDs, teilt sich zweimal, läuft dann zurück
        self.cell = None
        self.cell_next = time.monotonic() + self.rng.uniform(25.0, 45.0)
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
        if self.base == "heart" and ("roots" in n or n.endswith("_beat")):
            hb = self._heart_state()
            if "roots" in n:
                hb["flow_t0"] = now                               # Wurzeln/Myzel in der Szene = Aderfluss auf der Kette
            else:
                hb["pulses"].append((now, 1.5))                   # großer Herzschlag (Startknopf)
                hb["pulses"].append((now + 0.3, 0.9))
            return
        if self.base == "square":                                 # Marktplatz: nur der Zeitsprung blitzt, sonst alles ruhig
            if "lightning" in n:
                self._add(now, "wave", 3.5, np.array([255.0, 230.0, 190.0]) * 0.6, d=self.rng.choice((1.0, -1.0)))
                return
            if "blackout" in n:
                self.sq_dim_until = now + 14.0                    # Stromausfall: nur gedämpft, nie aus
                return
        if self.base == "clockwork" and n.startswith("clocktower"):
            return                                                # Uhrturm: Blitz, Figuren, Tanzball kommen aus led_state
        if self.base == "drive" and n.startswith("neonrace_"):
            return                                                # Neonfahrt: Start, Nitro, Hupe, Polizei kommen aus led_state
        if self.base == "city" and ("lightning" in n or "blackout" in n or "fireworks" in n):
            return                                                # Dachterrasse: Blitz, Stromausfall, Feuerwerk kommen aus led_state
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
            if self.base != "timejump":
                self._add(now, "lightning", 1.2, col)                 # Zeitsprung: kein Blitz, das Programm beschleunigt weich
        elif "start" in n or "nitro" in n:
            if self.base != "timejump":                           # Zeitsprung: Losfahren ist kein Sprung
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
        if not self.t_first:
            self.t_first = now
        if now >= self.bri_check:                                 # Helligkeitsknopf (logs/led_brightness.txt) nachführen
            self.bri_check = now + 0.5
            self.bri = self.bri_prof * min(1.0, self.dim * wled.knob_factor())
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
        if live and self.e_fast > 1.5 * self.energy + 0.15 and self.energy > 0.1 and now - self.last_drop > 12.0 and now - self.t_first > 5.0:
            self.last_drop = now
            self.flash = 0.0 if self.base in ("heart", "trip", "forest", "clockwork") else 0.55   # Drop: weicher Aufheller (ruhige Programme: keiner)
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
        elif program == "square":                                 # Marktplatz: ruhiges Laternenlicht in der Epochenfarbe
            frame = self._square(now, dt, st, bass, high, is_beat, live)
        elif program == "clockwork":                              # Uhrturm: Zeitbalken bis 22:04, Sekundenzeiger, Gewitter
            frame = self._clockwork(now, dt, st, bass, high, is_beat, live)
        elif program == "drive":                                  # Neonfahrt: Straße mit Laternen und Schildern + zwei Felder
            frame = self._drive(now, dt, st, bass, high, is_beat, live)
        elif program == "duel":                                   # zwei Felder im Beat (allein)
            frame = self._duel(now, dt, st, bass, high, is_beat, live)
        elif program == "heart":                                  # Herzbaum: Herzschlag von vorne nach hinten
            frame = self._heart(now, dt, st, bass, high, is_beat, live)
        elif program == "forest":                                 # Auge des Waldes: Grün, türkiser Nebel; Kaleidoskop bunt
            frame = self._forest(now, dt, st, bass, high, is_beat, live)
        elif program == "trip":                                   # Waldtresen: bunt, ganz langsam, morphend
            frame = self._trip(now, dt, st, bass, high, is_beat, live)
        elif program == "city":                                   # Dachterrasse: Fensterfront der Stadt
            frame = self._city(now, dt, st, bass, high, is_beat, live)
        elif program == "stars":
            frame = self._stars(now, dt, st, bass, high, is_beat, live)
        elif program == "panels":                                 # Orakel: je LED eine Tafelfarbe
            frame = self._panels(now, dt, st, bass, high, is_beat, live)
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
        """Casino-Lauflicht als Basis: ein Ansteuerpunkt an, der nächste aus, ganz mechanisch ohne Gleiten und Flimmern; auf jedem Beat
        springt das Muster hart einen Punkt weiter (an wird aus, aus wird an), in den Lichtfarben des Automaten, alle paar Takte auf dem Beat
        eine andere Farbe. Specials nur beim Drop und beim Gewinn: die Markise (Blöcke aus je drei Ansteuerpunkten: Farbe A hell, Farbe A
        gedimmt, Farbe B hell, kein Weiß, rückt einen Block je Beat, mal vor, mal zurück, beim Drehen schnell) für ein paar Takte, oder ein
        einzelner Läufer, der bei anziehendem Beat überholt wird, oder zwei Läufer, die sich kreuzen. Gewinn: klein = zweimal
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
        if win >= 2 and age < 0.1:                                # großer Gewinn/Jackpot: Markise als Special dazu
            self.mq_marq_until = max(self.mq_marq_until, now + (7.0 if win >= 3 else 4.0))
        if is_drop:                                               # Drop: neue Farbe, dazu ein Special (Markise oder Läufer)
            self.mq_dir *= -1.0
            self.mq_flip_at = now + self.rng.uniform(6.0, 14.0)
            self.chase_ci = (self.chase_ci + self.rng.choice((1, 2))) % 3
            self.chase_hue = self.rng.uniform(0.12, 0.5)
            if self.rng.random() < 0.5 or self.runners:
                self.mq_marq_until = now + self.rng.uniform(6.0, 12.0)   # Markise für ein paar Takte
            else:
                self.sp_launch = True
        self.mq_mode = 0 if now < self.mq_marq_until else 1
        self.mq_mix += (float(self.mq_mode) - self.mq_mix) * min(1.0, dt / 0.8)
        if is_beat:
            self.mq_beats += 1
            if self.mq_beats % 8 == 0 and self.rng.random() < 0.5:   # ab und zu auf dem Beat eine andere Lauflichtfarbe
                self.chase_ci = (self.chase_ci + self.rng.choice((1, 2))) % 3
                self.chase_hue = self.rng.uniform(0.12, 0.5)
            if self.mq_beats % 4 == 0:                            # alle vier Beats die Farben weiterrücken
                self.mq_rot += 1
            if self.mq_beats % 16 == 0 or (bass > 0.8 and self.rng.random() < 0.15):
                self.mq_dir *= -1.0
                self.mq_flip_at = now + self.rng.uniform(6.0, 14.0)
        if now >= self.mq_flip_at:                                # auch ohne Musik ab und zu umkehren
            self.mq_dir *= -1.0
            self.mq_flip_at = now + self.rng.uniform(6.0, 14.0)
        block = 3                                                 # drei Ansteuerpunkte je Farbe, kurze Blöcke wie am Casino-Eingang
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
        stepped = False
        if is_beat or (now - self.last_beat > 2.0 and now - self.ch_tick > 0.6):   # Lauflicht-Schritt: hart, je Beat ein Punkt
            self.ch_tick = now
            self.ch_step += 1
            stepped = True
        if self.chase_ci == 0:
            ccol = self.marquee[0]
        elif self.chase_ci == 1:
            ccol = self.marquee[2]
        else:
            h0 = float(_hue(self.marquee[0][None, :])[0]) / 360.0
            ccol = _hsv((h0 + self.chase_hue) % 1.0, 1.0, min(1.0, float(self.marquee[0].max()) / 255.0))
        if self.mq_mix > 0.01:                                    # Lauflicht: Ansteuerpunkt an, nächster aus, mechanisch
            on = ((idx + self.ch_step) % 2 == 0).astype(float)    # Punkt für Punkt im Wechsel, springt je Beat um einen Punkt
            lvl = 1.0 * live + (1.0 - live) * 0.5                 # konstant hell, kein Flimmern
            chase = np.outer(on * lvl, ccol)
            frame = frame * (1.0 - self.mq_mix) + chase * self.mq_mix
        frame = self._cell_special(frame, now, stepped, ccol, win, spinning, live)
        gold = self.marquee[0]
        white = _saturate(self.marquee[0] * 0.7 + WHITE * 0.3, 1.2)   # Glanzlicht: aufgehellte Hauptfarbe statt Weiß
        acc = self.marquee[2]
        # Specials (nur beim Drop): ein einzelner heller Punkt läuft durch; wird der Beat dabei kräftiger, überholt ihn ein
        # zweiter in der Akzentfarbe; oder zwei Läufer von beiden Enden kreuzen sich in der Mitte
        if self.sp_launch and win == 0 and not spinning and not self.runners:
            self.sp_launch = False
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

    CELL_PHASES = (15.0, 15.0, 12.0)                              # Zellteilung: ein Punkt, zwei, vier; dann zurück

    def _cell_special(self, frame, now, stepped, ccol, win, spinning, live) -> np.ndarray:
        """Sahnehäubchen im Casino-Lauflicht: ab und zu erscheint in EINER leeren LED ein Punkt in einer anderen Farbe und geht
        mit jedem Lauflicht-Schritt eine LED weiter (bleibt so immer in den leeren LEDs). Nach ~15 s teilt er sich: einer geht
        links, einer rechts; nach weiteren ~15 s teilt sich jeder nochmal. Dann laufen alle ihren Weg Schritt für Schritt
        rückwärts, treffen sich an den Teilungsstellen wieder und verschwinden am Startpunkt."""
        n = self.n
        c = self.cell
        if c is None:
            if (now >= self.cell_next and stepped and live and win == 0 and not spinning and self.mq_mix > 0.9
                    and not self.runners):
                pos = self.rng.randrange(n)
                if (pos + self.ch_step) % 2 == 0:                 # muss eine leere LED sein
                    pos = (pos + 1) % n
                h0 = float(_hue(np.asarray(ccol, dtype=float)[None, :])[0]) / 360.0
                col = _hsv((h0 + self.rng.choice((0.33, 0.5, 0.66))) % 1.0, 1.0, 1.0)   # deutlich andere Farbe, satt
                self.cell = {"dots": [[pos, self.rng.choice((1, -1))]], "hist": [], "phase": 0, "t0": now,
                             "back": False, "col": col}
                log.info("Casino-Special Zellteilung ab LED %d", pos)
            return frame
        if stepped:
            if c["back"]:
                if not c["hist"]:                                 # am Startpunkt angekommen: weg
                    self.cell = None
                    self.cell_next = now + self.rng.uniform(45.0, 90.0)
                    return frame
                c["dots"] = c["hist"].pop()
            else:
                if c["phase"] < len(self.CELL_PHASES) and now - c["t0"] >= self.CELL_PHASES[c["phase"]]:
                    c["phase"] += 1
                    c["t0"] = now
                    if c["phase"] < len(self.CELL_PHASES):         # teilen: einer links, einer rechts
                        c["dots"] = [[p, d] for p, _ in c["dots"] for d in (-1, 1)]
                    else:                                         # Ende: rückwärts
                        c["back"] = True
                if not c["back"]:
                    c["hist"].append([list(d) for d in c["dots"]])
                    c["dots"] = [[(p + d) % n, d] for p, d in c["dots"]]
                elif c["hist"]:
                    c["dots"] = c["hist"].pop()
        k = 1.0 * live + (1.0 - live) * 0.5
        for p, _ in c["dots"]:
            frame[int(p) % n] = c["col"] * k
        return frame

    def _panels(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Orakel: die acht Tafeln unter dem Kopf auf der Kette, je Ansteuerpunkt eine Tafelfarbe (1 2 3 ... 8, 1 2 3 ...).
        Eine LED leuchtet, solange ihre Tafel an ist (Beat-Muster der Szene: Lauflicht, Spiegel, Paare, Zufall ...), aus = kaum
        Glimmen; bei Stille atmen alle leise."""
        n = self.n
        cols = np.array(st.get("cols") or [[255, 30, 20]] * 8, dtype=float)[:8]
        lvl = np.array((list(st.get("lvl") or []) + [0.0] * 8)[:8], dtype=float)
        pos = np.arange(n) if not self.reverse else n - 1 - np.arange(n)
        x = pos / max(1, n - 1)
        ps = getattr(self, "panelled", None)
        if ps is None:
            ps = self.panelled = {"rot": 0, "spin_t": 0.0}
        mk = float(st.get("mask_k", 0.0))
        ma = now - float(st.get("mask_t0", -100.0))
        # Maske auf: einmal durchdrehen (2,5 s Farbwirbel), danach rücken die Farben je Beat einen Platz weiter
        if mk > 0.5 and 0.0 <= ma < 2.5:
            if now - ps["spin_t"] > 0.08:
                ps["spin_t"] = now
                ps["rot"] += 1
        elif mk > 0.5 and is_beat:
            ps["rot"] += 1
        k = (pos + ps["rot"]) % len(cols)
        lk = pos % len(cols)                                      # Tafel an/aus bleibt am Platz, die Farbe wandert
        if live:
            level = 0.04 + 0.96 * lvl[lk] * (0.85 + 0.15 * self.bass_s)
        else:
            level = np.full(n, 0.12 + 0.08 * np.sin(now * 0.8))
        if mk > 0.5 and 0.0 <= ma < 2.5:                          # beim Aufsetzen: alles an, pumpt mit dem Bass
            level = np.maximum(level, 0.55 + 0.45 * math.sin(ma * 9.0) ** 2)
        frame = cols[k] * level[:, None]
        # Scanner: grüner Streifen läuft einmal von vorne nach hinten, Schweif dahinter, kleine Funken
        sa = now - float(st.get("scan_t0", -100.0))
        slen = float(st.get("scan_len", 2.4))
        if 0.0 <= sa < slen:
            head = -0.05 + 1.1 * sa / slen
            dx = x - head
            line = np.exp(-(dx / 0.006) ** 2) + 0.45 * np.exp(dx / 0.06) * (dx < 0)
            sparks = (self.nrng.random(n) < 0.03) * (np.abs(dx) < 0.03) * 0.6
            frame = frame + np.outer(line + sparks, np.array([75.0, 255.0, 205.0]))
        # Datenexplosion: Ring startet in der Mitte und läuft zu beiden Enden, bunte Datenblöcke fliegen mit
        ba = now - float(st.get("burst_t0", -100.0))
        if 0.0 <= ba < 2.2:
            r = ba / 2.0 * 0.5
            d = np.abs(x - 0.5)
            ring = np.exp(-((d - r) / 0.01) ** 2) * math.exp(-ba * 0.8)
            frame = frame + np.outer(ring, np.array([150.0, 230.0, 255.0]))
            if ps.get("burst") != st.get("burst_t0"):
                ps["burst"] = st.get("burst_t0")
                ps["chunks"] = [(self.rng.choice((-1, 1)) * self.rng.uniform(0.25, 1.0), self.rng.randrange(len(cols))) for _ in range(14)]
            for sp, ci in ps.get("chunks", []):
                c = (0.5 + sp * r) * (n - 1)
                a0, a1 = int(max(0, c - 2)), int(min(n, c + 2))
                if a0 < a1:
                    frame[a0:a1] = frame[a0:a1] * 0.3 + cols[ci] * math.exp(-ba * 0.9)
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

    def _square(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Marktplatz (Zurück in die Zukunft, Taste 6): viel an und ganz ruhig. Die ganze Kette leuchtet im Laternenlicht der
        Epoche (Tönung aus der Szene, ohne Weißstich) auf 55-70 %, Laternenkegel etwa alle 60 LEDs atmen ganz langsam (8-12 s),
        zwei breite Wolken in der Zweitfarbe ziehen kaum merklich; die 1 im Takt hebt die Kegel einen Hauch. Ereignisse: nur der
        Zeitsprung blitzt (Special aus `square_jump`), Blitz-Taste = sanfte Lichtwelle, Stromausfall = 14 s gedämpft auf 45 %."""
        n = self.n
        x = self._idx()
        col, col2 = self._base_col()
        col = _no_white(np.asarray(col, dtype=float))
        col2 = _no_white(np.asarray(col2, dtype=float)) if np.asarray(col2).max() > 8 else col
        T = now
        base = 0.55 + 0.05 * math.sin(T * 0.21) + 0.1 * self.bass_s * live
        pools = 0.5 + 0.5 * np.sin(2.0 * math.pi * x * 13.0)        # Laternenkegel ~ alle 60 LEDs
        breathe = 0.5 + 0.5 * np.sin(T * 0.6 + x * 37.0)            # jeder Kegel atmet versetzt, 8-12 s
        lvl = base + (0.12 + 0.04 * self.bar_lift) * pools ** 3 * (0.6 + 0.4 * breathe)
        frame = np.outer(lvl, col)
        for f, ph in ((0.004, 0.0), (0.003, 2.7)):                 # Wolken in der Zweitfarbe, fast stehend
            c = (0.5 + 0.45 * math.sin(T * f * 6.28 + ph)) % 1.0
            w = np.exp(-((x - c) / 0.15) ** 2) * 0.3
            frame = frame * (1.0 - w)[:, None] + np.outer(w * lvl, col2)
        if now < getattr(self, "sq_dim_until", 0.0):
            k = min(1.0, (self.sq_dim_until - now) / 1.5, (now - (self.sq_dim_until - 14.0)) / 1.5)
            frame *= 1.0 - 0.55 * max(0.0, k)
        if not live:
            frame *= 0.75
        return frame

    CW_LAMP = 48                                                  # Uhrturm: Abstand der Laternen in LEDs

    def _clockwork(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Uhrturm (Zurück in die Zukunft, Taste 4): die Nacht bis 22:04 auf der Kette. Grund Gewitterblau mit Regenschimmer
        (im Gewitter mehr), warme Laternen alle CW_LAMP LEDs. Zeitbalken in Gold wächst von vorne nach hinten von 21:00 bis
        22:04 (`clock_k`), heller Kopf; Sekundenzeiger als orangeroter Punkt, tickt mit der Szene. Wetterleuchten = weiche
        blaue Aufhellung an der Stelle des Schirms, ferne Blitze schmal und hell. Countdown: Funken am Balkenende, vorne
        flackern die Zeitkreise der wartenden Zeitmaschine blau. 22:04: Blitz über die ganze Kette, die Zeitmaschine rast als
        Feuerspur von vorne nach hinten (liegt 4 s), 10 s blau-weißes Flackern (Uhr steht), dann läuft der Balken mit grünem
        Kopf zurück. Figuren: Professor = warmweißes Wischen, Funke = Punkt läuft durch, Paar im Fenster = Fleck in der
        Fensterfarbe, Tanzball = Girlanden in den acht Fensterfarben, je Beat im Wechsel."""
        n = self.n
        x = self._idx()
        cw = getattr(self, "cw", None)
        if cw is None or len(cw["rain"]) != n:
            cw = self.cw = {"rain": np.zeros(n), "spark": np.zeros(n)}
        st = st or {}
        T = now
        storm = float(st.get("storm", 0.0))
        final = float(st.get("final", 0.0))
        clock_k = float(st.get("clock_k", (T * 0.004) % 1.0))
        sa = float(st.get("strike_age", 1e3))
        act = int(st.get("act", 0))
        # Grund: Gewitterblau, der Bass hebt ihn, Regen schimmert auf einzelnen LEDs
        lvl = 0.22 + 0.03 * math.sin(T * 0.37) + 0.08 * storm + 0.1 * self.bass_s * live
        frame = np.outer(np.full(n, lvl), np.array([30.0, 70.0, 255.0]))
        rain = cw["rain"]
        rain *= 0.82
        hit = self.nrng.random(n) < 0.003 + 0.02 * storm + 0.01 * high
        rain[hit] = self.nrng.uniform(0.4, 1.0, int(hit.sum()))
        frame += np.outer(rain, np.array([140.0, 170.0, 255.0])) * 0.5
        # Laternen
        lp = (x * (n - 1) / self.CW_LAMP) % 1.0
        lamp = np.exp(-(((lp - 0.5) * self.CW_LAMP) / 2.2) ** 2) * (0.45 + 0.1 * np.sin(T * 0.5 + x * 23.0))
        frame += np.outer(lamp, np.array([255.0, 140.0, 45.0]))
        # Zeitbalken 21:00 -> 22:04
        rewind = act == 3 and sa >= 10.0
        bar = np.clip((clock_k - x) * n / 3.0 + 0.5, 0.0, 1.0)
        bk = 0.4 if (act == 3 and sa < 10.0) else 1.0                     # Uhr steht: Balken gedimmt, Feuerspur und Flackern davor
        frame = frame * (1.0 - 0.75 * bar * bk)[:, None] + np.outer(bar * (0.42 + 0.08 * self.bar_lift) * bk, np.array([255.0, 165.0, 35.0]))
        head = np.exp(-((x - clock_k) * n / 2.5) ** 2)
        frame += np.outer(head, np.array([90.0, 255.0, 140.0]) if rewind else np.array([255.0, 220.0, 140.0])) * 0.9
        # Countdown: Funken am Balkenende
        spark = cw["spark"]
        spark *= 0.7
        if final > 0.01:
            near = (np.abs(x - clock_k) * n < 14.0) & (self.nrng.random(n) < 0.25 * final)
            spark[near] = 1.0
        frame += np.outer(spark, np.array([255.0, 230.0, 180.0]))
        # Sekundenzeiger
        sec = float(st.get("sec", (T / 60.0) % 1.0))
        d = ((x - sec + 0.5) % 1.0) - 0.5
        frame += np.outer(np.exp(-(d * n / 1.8) ** 2) * (0.9 + 0.4 * final), np.array([255.0, 90.0, 40.0]))
        # Wetterleuchten und ferne Blitze
        sh_age, sh_x, sh_k = st.get("sheet", (9.0, 0.5, 0.0))
        if sh_age < 1.2 and sh_k > 0.0:
            amp = sh_k * math.exp(-sh_age * 5.0) * (0.7 + 0.3 * (self.nrng.random() < 0.65))
            frame += np.outer(np.exp(-((x - sh_x) / 0.14) ** 2) * amp * 0.6, np.array([150.0, 170.0, 255.0]))
        fa, fx, fk = st.get("far", (9.0, 0.5, 0.0))
        if fa < 0.6 and fk > 0.0:
            amp = fk * math.exp(-fa * 7.0) * (0.55 + 0.45 * (self.nrng.random() < 0.6))
            w = np.exp(-((x - fx) / 0.04) ** 2) + 0.25 * np.exp(-((x - fx) / 0.2) ** 2)
            frame += np.outer(w * amp, np.array([210.0, 220.0, 255.0]))
        # Funke übers Kabel: läuft in 1,2 s von vorne nach hinten
        spa = float(st.get("spark_age", 9.0))
        if spa < 1.6:
            pos = spa / 1.2
            frame += np.outer(np.exp(-((x - pos) * n / 2.0) ** 2), np.array([255.0, 235.0, 190.0]))
            trail = np.where(x < pos, np.exp(-(pos - x) * n / 25.0), 0.0) * (0.5 + 0.5 * self.nrng.random(n))
            frame += np.outer(trail * 0.5, np.array([255.0, 140.0, 40.0]))
        # Professor: warmweißes Wischen
        doc = float(st.get("doc", 0.0))
        if doc > 0.01:
            c = 0.5 + 0.45 * math.sin(T * 2.0 * math.pi / 7.0)
            frame += np.outer(np.exp(-((x - c) / 0.07) ** 2) * 0.45 * doc, np.array([255.0, 215.0, 165.0]))
        # Paar im Fenster
        wi, wvis = st.get("couple", (0, 0.0))
        if wvis > 0.01:
            w0, w7 = st.get("windows", (0.186, 0.613))
            pos = w0 + int(wi) * (w7 - w0) / 7.0
            amp = wvis * (0.55 + 0.35 * math.exp(-(T - self.last_beat) / 0.3))
            frame += np.outer(np.exp(-((x - pos) / 0.03) ** 2) * amp, CW_WIN[int(wi) % 8])
        # Tanzball: Girlanden, Birnen alle 6 LEDs in den Fensterfarben, je Beat im Wechsel
        dance = float(st.get("dance", 0.0))
        if dance > 0.01:
            k = x * (n - 1) / 6.0
            ki = np.floor(k).astype(int)
            bulb = np.exp(-(((k % 1.0) - 0.5) * 6.0 / 1.2) ** 2)
            on = 0.3 + 0.7 * (((ki + int(st.get("beat_step", self.beats))) % 4) == 0)
            frame = frame * (1.0 - 0.5 * dance) + (bulb * on * dance * 0.8)[:, None] * CW_WIN[ki % 8]
        # Zeitmaschine: wartet vorne (Zeitkreise flackern blau), rast nach dem Blitz als Feuerspur nach hinten
        if st.get("car_wait"):
            fl = 0.5 + 0.5 * math.sin(T * 25.0) * math.sin(T * 7.0)
            frame += np.outer(np.exp(-((x - 0.03) / 0.02) ** 2) * (0.4 + 0.5 * fl), np.array([80.0, 160.0, 255.0]))
        car = st.get("car")
        if car:
            cx, sp = car
            ages = (cx - x) / max(sp, 0.05)
            k = np.where((ages > 0.0) & (ages < 4.0), (1.0 - ages / 4.0) ** 2, 0.0)
            fl = self.nrng.random(n)
            fire = np.outer(1.0 - fl, np.array([255.0, 70.0, 5.0])) + np.outer(fl, np.array([255.0, 175.0, 50.0]))
            frame = frame * (1.0 - 0.6 * k)[:, None] + fire * (k * (0.6 + 0.4 * fl))[:, None]
            frame += np.outer(np.exp(-((x - cx) * n / 3.0) ** 2), np.array([200.0, 225.0, 255.0]))
        # 22:04: Blitz über die ganze Kette, dann blau-weißes Flackern solange die Uhr steht
        if sa < 0.7:
            k = min(1.0, math.exp(-sa * 6.0) + (0.8 * math.exp(-(sa - 0.28) * 8.0) if sa > 0.28 else 0.0))
            frame = frame * (1.0 - k) + np.array([225.0, 232.0, 255.0]) * k
        elif sa < 10.0:
            blk = np.floor(x * (n - 1) / 8.0)
            h = (np.sin(blk * 12.9898) * 43758.5453) % 1.0
            fl = 0.5 + 0.5 * np.sin(T * (3.0 + 5.0 * h) + h * 20.0)
            amt = 0.35 * (1.0 - 0.5 * (sa - 0.7) / 9.3)
            frame += np.outer(fl * amt, np.array([150.0, 180.0, 255.0]))
        if not live:
            frame *= 0.8
        return frame

    LAMP_EVERY = 34                                               # Neonfahrt: Abstand der Straßenlaternen in LEDs
    DRIVE_K = 30.0                                                # LEDs je Streckeneinheit der Szene (uDist): ruhig, ~18 LEDs/s bei Reisetempo
    DUEL_EVERY = 2                                                # Felder gehen nur jeden 2. Beat
    DUEL_STEP = 5                                                 # ... und dann nur ein halbes Feld weit

    def _drive(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Neonfahrt: die Kette ist die Straße, an der man vorbeifährt. Straßenlaternen (alle LAMP_EVERY LEDs, Lichtkegel) und
        Neonschilder (6-15 LEDs in Haupt-, Akzentfarbe und Bernstein, Farbton springt je Beat weiter) ziehen genau mit der
        gefahrenen Strecke der Szene von vorne nach hinten; steht der Wagen, stehen sie. Die Straße glimmt in der
        Bildschirmfarbe. Darüber hell die zwei Felder (`_duel`). Specials aus led_state: Nitro = Lichtstreifen, Hupe = zweimal
        Aufblinken, Beinahe-Treffer = weißer Streifen huscht nach hinten, Viertelwechsel = Lichtwand von vorne nach hinten,
        Polizeidrohnen = rot-blauer Blinker überholt von hinten nach vorne."""
        n = self.n
        idx = np.arange(n)
        if self.reverse:
            idx = n - 1 - idx
        dv = getattr(self, "drv", None)
        if dv is None or dv["L"] != 2 * n:
            L = 2 * n
            sign = np.full(L, -1)
            u = self.rng.randint(4, 10)
            while u < L - 20:
                if self.rng.random() < 0.65:
                    a = u + self.rng.randint(5, self.LAMP_EVERY - 18)
                    w = self.rng.randint(6, 15)
                    sign[a:min(L, a + w)] = self.rng.randrange(3)
                u += self.LAMP_EVERY
            dv = self.drv = {"L": L, "sign": sign, "hue_step": 0.0, "hue_s": 0.0}
        main, acc = self._base_col()
        main = _no_white(np.asarray(main, dtype=float))
        acc = _no_white(np.asarray(acc, dtype=float)) if np.asarray(acc).max() > 8 else main
        dist = float(st.get("dist", 0.0)) if st else now * 0.3
        speed = float(st.get("speed", 0.4)) if st else 0.4
        driving = bool(st.get("driving", True)) if st else True
        nitro = float(st.get("nitro", 0.0)) if st else 0.0
        off = dist * self.DRIVE_K
        if is_beat:
            dv["beats"] = dv.get("beats", 0) + 1
            if dv["beats"] % 4 == 0:
                dv["hue_step"] += 0.06                            # Schilder wechseln die Farbe nur alle 4 Beats, weich
        dv["hue_s"] += (dv["hue_step"] - dv["hue_s"]) * min(1.0, dt * 1.2)
        # Straße: Grundglimmen in der Bildschirmfarbe
        frame = np.tile(main * (0.07 + 0.03 * self.bass_s), (n, 1))
        # Neonschilder (Straßenkoordinate u = Position - Versatz)
        uu = (idx - int(off)) % dv["L"]
        sc = dv["sign"][uu]
        hm = float(_hue(main[None, :])[0]) / 360.0
        ha = float(_hue(acc[None, :])[0]) / 360.0
        pal = np.array([_hsv((hm + dv["hue_s"]) % 1.0, 1.0, 1.0), _hsv((ha + dv["hue_s"]) % 1.0, 1.0, 1.0),
                        _hsv((0.09 + dv["hue_s"] * 0.3) % 1.0, 1.0, 1.0)])
        m = sc >= 0
        flick = 0.92 + 0.08 * np.sin(now * 2.2 + uu * 0.7)
        frame[m] = pal[sc[m]] * (0.55 + 0.25 * self.bass_s) * flick[m][:, None]
        # Laternen mit Lichtkegel; bei Nitro ziehen sie sich zu Streifen
        ph = (idx - off) % self.LAMP_EVERY
        dd = ph - self.LAMP_EVERY / 2.0
        trail = 2.0 + 14.0 * nitro + 2.0 * speed
        lamp = np.exp(-(dd / 1.6) ** 2) + 0.25 * np.exp(-(dd / 5.0) ** 2) + np.where(dd < 0, 0.45 * np.exp(dd / trail), 0.0)
        lamp_col = np.clip(acc * 0.5 + np.array([255.0, 200.0, 140.0]) * 0.5, 0, 255)
        frame += np.outer(np.clip(lamp, 0.0, 1.2) * (0.7 if driving else 0.45), lamp_col)
        # die zwei Felder im Beat darüber, hell
        duel = self._duel(now, dt, st, bass, high, is_beat, live)
        bright = duel.max(axis=1) > 60
        frame[bright] = duel[bright]
        # Specials
        t_h = now - float(st.get("honk_t0", -100.0)) if st else 99.0
        if 0.0 <= t_h < 0.9:
            k = math.sin(math.pi * min(1.0, t_h / 0.45)) if t_h < 0.45 else math.sin(math.pi * (t_h - 0.45) / 0.45) * 0.7
            frame = frame * (1.0 + 0.4 * k) + main * 0.12 * k
        t_n = now - float(st.get("near_t0", -100.0)) if st else 99.0
        if 0.0 <= t_n < 1.2:
            pos = t_n / 1.2
            x = idx / max(1, n - 1)
            frame += np.outer(np.exp(-((x - pos) / 0.03) ** 2), np.array([230.0, 235.0, 255.0]))
        t_d = now - float(st.get("district_t0", -100.0)) if st else 99.0
        dlen = float(st.get("district_len", 3.2)) if st else 3.2
        if 0.0 <= t_d < dlen:
            pos = t_d / dlen
            x = idx / max(1, n - 1)
            wall = np.exp(-((x - pos) / 0.02) ** 2)
            frame = frame * (1.0 - 0.5 * np.exp(-((x - pos) / 0.08) ** 2))[:, None] + np.outer(wall, acc * 0.6 + WHITE * 0.3)
        t_p = now - float(st.get("police_t0", -100.0)) if st else 99.0
        if 0.0 <= t_p < float(st.get("police_len", 14.0) if st else 14.0):
            u = (t_p % 7.0) / 5.0                                 # alle 7 s überholt einer, 5 s von hinten nach vorne
            if u <= 1.0:
                pos = 1.0 - u
                px = int(round(pos * (n - 1)))
                red = (now * 1.6) % 1.0 < 0.5
                for o in range(-2, 3):
                    j = px + o
                    if 0 <= j < n:
                        frame[j if not self.reverse else n - 1 - j] = np.array([255.0, 0.0, 0.0]) if (red ^ (o > 0)) else np.array([0.0, 40.0, 255.0])
        if not live:
            frame *= 0.75
        return frame

    DUEL_W = 10                                                   # Neonfahrt: Breite eines Felds in Ansteuerpunkten

    def _duel(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Neonfahrt: zwei Felder aus je DUEL_W LEDs in Haupt- und Akzentfarbe des Bildschirms gehen auf jedem Beat ein Feld
        nach links oder rechts und wechseln immer wieder die Richtung (frei). Ab und zu laufen sie im Gleichschritt, ab und zu
        aufeinander zu: dann liegen sie übereinander und leuchten in einer dritten Farbe, gehen kurz als eines weiter und teilen
        sich wieder (auseinander). Wo sie sich nur kreuzen, wird die Überlappung ebenfalls dritte Farbe. Dazwischen glimmt die
        Kette ganz leicht in der Bildschirmfarbe."""
        n = self.n
        w = self.DUEL_W
        d = getattr(self, "duel", None)
        if d is None:
            p0 = self.rng.uniform(0.2, 0.4) * n
            p1 = self.rng.uniform(0.6, 0.8) * n
            d = self.duel = {"pos": [p0, p1], "pos_s": [p0, p1], "dir": [1, -1], "mode": "free",
                             "mode_beats": self.rng.randint(12, 24), "merge_beats": 0, "tick": 0.0}
        a, b = self._base_col()
        a = _saturate(np.asarray(a, dtype=float), 1.5)
        b = _saturate(np.asarray(b, dtype=float), 1.5)
        a = a * (255.0 / max(1.0, float(a.max())))                # voll ausgesteuert, die Helligkeit macht das Profil
        b = b * (255.0 / max(1.0, float(b.max())))
        ha, hb = float(_hue(a[None, :])[0]) / 360.0, float(_hue(b[None, :])[0]) / 360.0
        if min(abs(ha - hb), 1 - abs(ha - hb)) < 0.12:            # zu ähnlich: Akzent drehen
            hb = (ha + 0.45) % 1.0
            b = _hsv(hb, 1.0, max(0.6, float(b.max()) / 255.0))
        mid = (ha + hb) / 2.0 if abs(ha - hb) <= 0.5 else ((ha + hb) / 2.0 + 0.5) % 1.0
        c3 = _hsv((mid + 0.5) % 1.0, 1.0, 1.0)                  # dritte Farbe: weit weg von beiden
        step = self.DUEL_STEP * (2 if now < self.boost_until else 1)
        if is_beat:
            d["beat_n"] = d.get("beat_n", 0) + 1
        tick = (is_beat and d["beat_n"] % self.DUEL_EVERY == 0) or (now - self.last_beat > 2.0 and now - d["tick"] > 1.0)
        if tick:
            d["tick"] = now
            pos, dirs = d["pos"], d["dir"]
            d["mode_beats"] -= 1
            if d["mode"] == "free":
                for i in (0, 1):
                    if self.rng.random() < 0.28:
                        dirs[i] = -dirs[i]
                if d["mode_beats"] <= 0:
                    d["mode"] = self.rng.choice(("lock", "meet", "meet"))
                    d["mode_beats"] = self.rng.randint(6, 12) if d["mode"] == "lock" else 40
                    if d["mode"] == "lock":                       # Gleichschritt: beide in dieselbe Richtung, weg vom nahen Ende
                        centre = (pos[0] + pos[1]) / 2.0
                        dirs[0] = dirs[1] = 1 if centre < n / 2 else -1
            elif d["mode"] == "lock":
                if self.rng.random() < 0.12:
                    dirs[0] = dirs[1] = -dirs[0]
                if d["mode_beats"] <= 0:
                    d["mode"], d["mode_beats"] = "free", self.rng.randint(12, 24)
            elif d["mode"] == "meet":                             # aufeinander zu
                lo, hi = (0, 1) if pos[0] <= pos[1] else (1, 0)
                dirs[lo], dirs[hi] = 1, -1
                if abs(pos[1] - pos[0]) <= 2 * step:              # treffen: übereinander, dritte Farbe
                    m = (pos[0] + pos[1]) / 2.0
                    pos[0] = pos[1] = m
                    d["mode"] = "merged"
                    d["merge_beats"] = self.rng.randint(2, 5)
                    dirs[0] = dirs[1] = self.rng.choice((1, -1))
                elif d["mode_beats"] <= 0:
                    d["mode"], d["mode_beats"] = "free", self.rng.randint(12, 24)
            elif d["mode"] == "merged":                           # kurz als eines weiter, dann teilen
                d["merge_beats"] -= 1
                if d["merge_beats"] <= 0:
                    dirs[0], dirs[1] = -1, 1
                    d["mode"], d["mode_beats"] = "free", self.rng.randint(14, 26)
                    d["split_free"] = 3                           # die ersten Beats nach dem Teilen nicht umdrehen
            if d.get("split_free", 0) > 0:
                d["split_free"] -= 1
                if d["mode"] == "free":
                    dirs[0], dirs[1] = (-1, 1) if pos[0] <= pos[1] else (1, -1)
            if d["mode"] == "merged":                             # verschmolzen: beide genau gleich
                dirs[1] = dirs[0]
            for i in (0, 1):
                nxt = pos[i] + dirs[i] * step
                if nxt < 0 or nxt > n - w:                         # an den Enden umkehren
                    dirs[i] = -dirs[i]
                    if d["mode"] == "merged":
                        dirs[1 - i] = dirs[i]
                    nxt = pos[i] + dirs[i] * step
                pos[i] = min(max(nxt, 0.0), float(n - w))
        for i in (0, 1):                                           # kurz eingerastet (~0,1 s)
            d["pos_s"][i] += (d["pos"][i] - d["pos_s"][i]) * min(1.0, dt * 4.0)   # weich gleiten (~0,4 s)
        base = (a * 0.03 + b * 0.02) * (live * (0.7 + 0.3 * self.bass_s) + (1.0 - live) * 0.6)
        frame = np.tile(base, (n, 1))
        lvl = (0.85 + 0.15 * self.bar_lift) * live + (1.0 - live) * 0.45
        idx = np.arange(n)
        m0 = (idx >= int(round(d["pos_s"][0]))) & (idx < int(round(d["pos_s"][0])) + w)
        m1 = (idx >= int(round(d["pos_s"][1]))) & (idx < int(round(d["pos_s"][1])) + w)
        if self.reverse:
            m0, m1 = m0[::-1], m1[::-1]
        if d["mode"] == "merged":
            frame[m0 | m1] = c3 * lvl
        else:
            frame[m0] = a * lvl
            frame[m1] = b * lvl
            frame[m0 & m1] = c3 * lvl                              # beim Kreuzen: Überlappung in der dritten Farbe
        return frame

    def _heart_state(self) -> dict:
        hb = getattr(self, "heartled", None)
        if hb is None:
            hb = self.heartled = {"pulses": [], "tick": 0.0, "flow_t0": -100.0,
                                  "flow_next": time.monotonic() + self.rng.uniform(20.0, 40.0)}
        return hb

    def _heart(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Herzbaum: die Kette ist vorne hell und wird nach hinten dunkler; ein ruhiger Herzschlag (Doppelschlag, kräftig dann
        schwächer) läuft von vorne nach hinten und klingt dabei aus. Schlag auf jedem zweiten Beat (ruhig, ~60-70/min), ohne
        Musik 64/min. Farben der Jahreszeit (Tönung aus der Szene) ohne Weißanteil, hinten zur Zweitfarbe hin. Special Aderfluss
        (alle 30-60 s und wenn in der Szene die Wurzeln laufen): Energie fließt als Strom mit pulsierenden Teilchen von vorne
        nach hinten durch."""
        n = self.n
        x = self._idx()
        hb = self._heart_state()
        a, b = self._base_col()
        a = _no_white(np.asarray(a, dtype=float))
        b = _no_white(np.asarray(b, dtype=float)) if np.asarray(b).max() > 8 else a * np.array([0.6, 0.6, 0.6])
        # Herzschlag auslösen
        beat_now = is_beat and self.beats % 2 == 1
        idle = now - self.last_beat > 2.5 and now - hb["tick"] > 60.0 / 64.0
        if beat_now or idle:
            hb["tick"] = now
            amp = 0.75 + 0.35 * self.bass_s if live else 0.6
            hb["pulses"].append((now, amp))
            hb["pulses"].append((now + 0.28, amp * 0.55))           # "lub-dub"
        hb["pulses"] = [p for p in hb["pulses"] if now - p[0] < 2.6]
        # Grund: vorne hell, hinten dunkler, Farbe wandert zur Zweitfarbe
        grad = 0.16 + 0.34 * (1.0 - x) ** 1.3
        ha = float(_hue(a[None, :])[0]) / 360.0                  # Farbton wandert auf dem Farbkreis zur Zweitfarbe (kein Grau)
        hb_ = float(_hue(b[None, :])[0]) / 360.0
        dh = ((hb_ - ha + 0.5) % 1.0) - 0.5
        colx = _hsv_arr((ha + dh * 0.55 * x) % 1.0, 0.95, 1.0)
        level = grad * (1.0 if live else 0.7)
        for t0, amp in hb["pulses"]:
            age = now - t0
            if age < 0.0:
                continue
            pos = age * 0.55                                       # läuft ruhig nach hinten
            wave = np.exp(-((x - pos) / 0.13) ** 2) * (1.0 - 0.65 * x)
            swell = np.exp(-x / 0.12) * math.exp(-age / 0.3)       # vorne zieht sich das Herz zusammen
            level = level + amp * math.exp(-age / 1.6) * (0.55 * wave + 0.35 * swell)
        frame = colx * np.clip(level, 0.0, 1.1)[:, None]
        # Aderfluss
        if now >= hb["flow_next"] and now - hb["flow_t0"] > 20.0:
            hb["flow_t0"] = now
        if now - hb["flow_t0"] < 0.1:
            hb["flow_next"] = now + self.rng.uniform(30.0, 60.0)
        fa = now - hb["flow_t0"]
        if 0.0 <= fa < 13.0:
            head = fa * 0.1
            body = np.clip(1.0 - (head - x) / 0.3, 0.0, 1.0) * (x <= head + 0.01)
            cells = 0.55 + 0.45 * np.sin(2.0 * math.pi * ((x - fa * 0.16) * 45.0)) ** 2   # Teilchen strömen schneller als der Kopf
            k = body * cells * (0.75 + 0.25 * self.bass_s) * min(1.0, fa / 0.8) * min(1.0, (13.0 - fa) / 2.0)
            fcol = _hsv((ha + dh * 0.3) % 1.0, 1.0, 1.0)
            frame = frame * (1.0 - 0.5 * k[:, None]) + np.outer(k, fcol)
        return frame

    FOREST_DEEP = np.array([0.0, 90.0, 22.0])
    FOREST_GREEN = np.array([30.0, 170.0, 40.0])
    FOREST_TURQ = np.array([0.0, 215.0, 175.0])

    FOREST_PAD = np.array([170.0, 255.0, 40.0])                   # Seerose mit Frosch: gelbgrün
    FOREST_LILY = np.array([0.0, 120.0, 45.0])                    # leere Seerose
    FOREST_FLY = np.array([255.0, 190.0, 50.0])                   # Glühwürmchen, Sporen
    FOREST_OWL = np.array([200.0, 180.0, 150.0])

    @staticmethod
    def _blob(acc: np.ndarray, c: float, sigma: float, amp: float) -> None:
        """Gauß-Fleck um LED-Position c (in LEDs) in acc (n) addieren, nur im Umkreis von 3 sigma."""
        n = len(acc)
        lo, hi = max(0, int(c - 3 * sigma)), min(n, int(c + 3 * sigma) + 2)
        if lo >= hi or amp == 0.0:
            return
        d = np.arange(lo, hi) - c
        acc[lo:hi] += np.exp(-(d / sigma) ** 2) * amp

    def _myc_active(self, zone: np.ndarray, step: int, pattern: int) -> np.ndarray:
        """Myzel-Lauflicht wie in der Szene: Zone 0-3 an/aus je Schritt und Muster (0 läuft, 1 Wechsel, 2 Spiegel, 3 alle außer)."""
        if pattern == 0:
            return (zone == step).astype(float)
        if pattern == 1:
            return ((zone + step) % 2 == 0).astype(float)
        if pattern == 2:
            return ((zone == step) | (zone == 3 - step)).astype(float)
        return (zone != step).astype(float)

    def _forest(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Auge des Waldes: viel Grün (tiefes Grün mit Moosflecken), türkiser Nebel in Schwaden, der als Myzel-Lauflicht 1-2-3-4
        im Beat und im Muster der Szene aufleuchtet (Kette in Zonen à ~48 LEDs, Zone 0-3 im Wechsel). Seerosen: acht Blätter =
        acht Bänder, viermal über die Kette; sitzt ein Frosch, glüht das Blatt gelbgrün mit seinem Band, Hüpfer = Punkt springt
        kurz hoch, Auftauchen/Abtauchen = Wellenring. Lidschlag = Kette dunkelt von beiden Enden zur Mitte. Nach dem Drop
        färbt die neue Irisfarbe den Nebel (7 s) und eine goldene Sporenwolke breitet sich von der Mitte aus. Glühwürmchen mit
        den Höhen, die Eule gleitet als heller Schatten, ein winkender Zwerg zwinkert warm, Froschchor = Welle über alle
        Blätter. Nie aus. Kaleidoskop (Knüppel unten, `kaleido`): feste Regenbogenfolge, nur vor und zurück, Tempo wechselt."""
        n = self.n
        x = self._idx()
        idx = np.arange(n)
        fo = getattr(self, "forestled", None)
        if fo is None:
            fo = self.forestled = {"T": self.rng.uniform(0.0, 300.0), "glow": 0.0, "off": 0.0, "vt": self.rng.uniform(0.0, 50.0),
                                   "flies": [], "act": None, "spores": None}
        st = st or {}
        k = float(st.get("kaleido", 0.0))
        fo["T"] += dt * (0.7 + 0.3 * self.energy)
        T = fo["T"]
        tau = 2.0 * math.pi
        if is_beat:
            fo["glow"] = 1.0
        fo["glow"] *= math.exp(-dt / 0.45)
        awake = float(st.get("awake", 1.0))
        # Grün: Moosflecken treiben ganz langsam
        moss = 0.5 + 0.5 * np.sin(tau * (x * 3.1 + T * 0.004)) * np.sin(tau * (x * 1.3 - T * 0.003) + 1.7)
        frame = self.FOREST_DEEP[None, :] * (0.75 + 0.25 * moss[:, None]) + self.FOREST_GREEN[None, :] * (0.35 * moss[:, None])
        # Nebel als Myzel: Zonen leuchten im Lauflicht der Szene, weich überblendet
        mist = (0.5 + 0.5 * np.sin(tau * (x * 2.2 + T * 0.011))) * (0.5 + 0.5 * np.sin(tau * (x * 0.8 - T * 0.007) + 2.0))
        mist = np.clip((mist - 0.12) / 0.5, 0.0, 1.0) ** 1.2
        zone = (idx // 48) % 4
        target = self._myc_active(zone, int(st.get("step", 0)) % 4, int(st.get("pattern", 0)) % 4) if "step" in st else np.ones(n)
        if fo["act"] is None or len(fo["act"]) != n:
            fo["act"] = target.copy()
        fo["act"] += (target - fo["act"]) * min(1.0, dt / 0.18)
        iris = st.get("iris")
        mist_col = np.asarray(iris, dtype=float) if iris is not None else self.FOREST_TURQ
        lum = (0.25 + 0.75 * fo["act"]) * (0.45 + 0.3 * self.bass_s + 0.25 * fo["glow"]) * (1.0 if live else 0.6) * (0.4 + 0.6 * awake)
        frame += mist_col[None, :] * (mist * lum)[:, None]
        # Seerosen: acht Blätter je Gruppe, viermal über die Kette
        bands = list(st.get("bands") or [0.0] * 8)[:8] + [0.0] * 8
        phase = list(st.get("phase") or [0] * 8)[:8] + [0] * 8
        page = list(st.get("phase_age") or [9.0] * 8)[:8] + [9.0] * 8
        spacing = n / 32.0
        chorus = now - float(st.get("chorus_t0", -100.0))
        pad, lily, ring = np.zeros(n), np.zeros(n), np.zeros(n)
        for g in range(4):
            for i in range(8):
                c = (g * 8 + i + 0.5) * spacing
                ph, age, bnd = phase[i], page[i], bands[i]
                if ph in (2, 3, 1):                                   # sitzt, hüpft, taucht auf
                    lv = 0.3 + 0.7 * bnd
                    shift = 0.0
                    if ph == 3:                                       # Hüpfer: Punkt springt kurz zur Seite und zurück
                        u = min(1.0, age / 0.6)
                        shift = 3.0 * math.sin(math.pi * u) * (1 if (g + i) % 2 else -1)
                        lv += 0.4 * math.sin(math.pi * u)
                    if ph == 1:
                        lv *= min(1.0, age / 0.8)
                    self._blob(pad, c + shift, 1.4, lv)
                else:
                    self._blob(lily, c, 1.4, 0.25)
                if ph in (1, 4) and age < 0.9:                        # Auf- oder Abtauchen: Wellenring
                    r = 1.5 + age * 9.0
                    amp = (1.0 - age / 0.9) * 0.6
                    self._blob(ring, c - r, 1.0, amp)
                    self._blob(ring, c + r, 1.0, amp)
                if 0.0 <= chorus < 4.0:                               # Froschchor: Welle über alle Blätter
                    tt = chorus - (0.3 + i * 0.14 + g * 0.05)
                    if 0.0 <= tt < 0.35:
                        self._blob(pad, c, 2.0, math.sin(math.pi * tt / 0.35))
        frame += np.outer(pad, self.FOREST_PAD) + np.outer(lily, self.FOREST_LILY) + np.outer(ring, self.FOREST_TURQ)
        # Glühwürmchen mit den Höhen
        if live and self.rng.random() < dt * (0.5 + 6.0 * high):
            fo["flies"].append([now, self.rng.uniform(0.0, 1.0), self.rng.uniform(-0.004, 0.004), self.rng.uniform(1.5, 3.0)])
        gold = np.zeros(n)
        keep = []
        for fl in fo["flies"]:
            age = now - fl[0]
            if age < fl[3]:
                keep.append(fl)
                pos = (fl[1] + fl[2] * age) * (n - 1)
                self._blob(gold, pos if not self.reverse else n - 1 - pos, 1.2, math.sin(math.pi * age / fl[3]) * 0.9)
        fo["flies"] = keep[-40:]
        # Sporenwolke nach dem Drop: goldene Punkte von der Mitte nach außen
        sa = now - float(st.get("spore_t0", -100.0))
        if 0.0 <= sa < 4.0:
            if fo["spores"] is None or fo["spores"][0] != st.get("spore_t0"):
                fo["spores"] = (st.get("spore_t0"), self.nrng.uniform(-0.5, 0.5, 40), self.nrng.uniform(0.6, 1.0, 40))
            _, dirs, br = fo["spores"]
            pos = 0.5 + dirs * min(1.0, 0.15 + sa / 2.5)            # starten schon etwas verteilt
            fade = (1.0 - sa / 4.0)
            for p_, b_ in zip(pos, br):
                self._blob(gold, p_ * (n - 1), 1.5, b_ * fade)
        frame += np.outer(np.minimum(gold, 1.0), self.FOREST_FLY)   # gedeckelt: kein weißer Fleck
        # Eule gleitet als heller Schatten
        if st.get("owl"):
            ot = float(st.get("owl_t", 0.0))
            pos = (ot * 0.35) % 1.3 - 0.15
            wing = 0.7 + 0.3 * math.sin(ot * 40.0)
            frame += np.outer(np.exp(-((x - pos) / 0.008) ** 2) * wing * 0.8, self.FOREST_OWL)
        # Zwerg winkt: warmes Zwinkern an einer Stelle
        wa = now - float(st.get("wave_t0", -100.0))
        if 0.0 <= wa < 1.3:
            spot = (float(st.get("wave_t0", 0.0)) * 7.31) % 1.0
            blink2 = 1.0 if (wa % 0.5) < 0.22 else 0.15
            frame += np.outer(np.exp(-((x - spot) * n / 2.0) ** 2) * blink2, np.array([255.0, 140.0, 40.0]))
        # Lidschlag: von beiden Enden zur Mitte dunkler
        bl = float(st.get("blink", 1.0))
        if bl < 0.98:
            closed = 1.0 - bl
            edge = np.minimum(x, 1.0 - x)                           # 0 an den Enden, 0.5 in der Mitte
            lid = np.clip((closed * 0.55 - edge) / 0.04, 0.0, 1.0)
            frame = frame * (1.0 - 0.8 * lid)[:, None]
        frame = np.maximum(frame, self.FOREST_DEEP * 0.4)          # nie aus
        if k > 0.01:                                               # Kaleidoskop: feste Farbfolge, vor und zurück
            fo["vt"] += dt
            vt = fo["vt"]
            v = 0.045 * math.sin(tau * vt / 23.0) + 0.025 * math.sin(tau * vt / 9.7 + 1.0) + 0.012 * math.sin(tau * vt / 4.1)
            v *= 1.0 + 0.8 * self.bass_s
            fo["off"] = (fo["off"] + v * dt) % 1.0
            hue = (x * 6.0 + fo["off"] * 6.0) % 1.0
            rainbow = _hsv_arr(hue, 1.0, 0.85 + 0.15 * self.bass_s)
            frame = frame * (1.0 - k) + rainbow * k
        return frame

    TRIP_DG = np.array([0.0, 95.0, 18.0])                         # Dunkelgrün des Waldes (häufig, nie ganz aus)

    def _trip(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Waldtresen (Thema green, Taste 2): ein ganz langsam fließendes, morphendes Farbfeld in den Farben des Bildschirms
        (Grundton = Bildschirmfarbe, die Wellen fächern ihn auf), dazu schmale Akzentbänder (~7 LEDs, etwa alle 30-45 LEDs)
        abwechselnd in der Akzentfarbe des Bildschirms und der Gegenfarbe, die langsam mitwandern und in der Breite atmen;
        dazwischen dunkelgrüne Täler, nie ganz aus. Beat = winziger, weich eingerasteter Phasenschritt, Drop = Farbton gleitet
        ein Stück weiter. Am Tresen (vor der Reise) mehr Dunkelgrün, während der Reise voll bunt."""
        n = self.n
        x = self._idx()
        tp = getattr(self, "tripled", None)
        if tp is None:
            tp = self.tripled = {"T": self.rng.uniform(0.0, 500.0), "ph": 0.0, "ph_s": 0.0, "hue": 0.0, "hue_s": 0.0}
        inten = float(st.get("intensity", 1.0)) if st else 1.0
        inten = 0.25 + 0.75 * max(0.0, min(1.0, inten))
        tp["T"] += dt * (0.6 + 0.4 * self.energy) * (1.0 if live else 0.6)
        if is_beat:
            tp["ph"] += 0.012
        if 0.0 < now - self.last_drop <= dt * 1.5:
            tp["hue"] += self.rng.uniform(0.06, 0.14)
        tp["ph_s"] += (tp["ph"] - tp["ph_s"]) * min(1.0, dt * 1.2)
        tp["hue_s"] += (tp["hue"] - tp["hue_s"]) * min(1.0, dt / 4.0)
        T = tp["T"]
        tau = 2.0 * math.pi
        main, acc = self._base_col()
        hm = float(_hue(np.asarray(main, dtype=float)[None, :] + 1e-3)[0]) / 360.0      # Grundton vom Bildschirm
        ha = float(_hue(np.asarray(acc, dtype=float)[None, :] + 1e-3)[0]) / 360.0
        if min(abs(ha - hm), 1.0 - abs(ha - hm)) < 0.1:
            ha = (hm + 0.33) % 1.0
        k1 = 2.6 + 1.2 * math.sin(T * 0.011)                       # kürzere Farbflächen, Blasen teilen und vereinen sich
        k2 = 4.8 + 2.0 * math.sin(T * 0.007 + 1.0)
        warp = 0.12 * np.sin(tau * (x * 0.7 + T * 0.006))
        field = 0.6 * np.sin(tau * (x * k1 + T * 0.012 + warp)) + 0.4 * np.sin(tau * (x * k2 - T * 0.009 + tp["ph_s"]))
        hue = hm + tp["hue_s"] + (0.17 * field + 0.07 * np.sin(tau * (x * 0.8 - T * 0.003))) * inten   # um die Bildschirmfarbe gefächert
        val = 0.55 + 0.3 * (0.5 + 0.5 * np.sin(tau * (x * 1.3 - T * 0.01) + field)) + 0.12 * self.bass_s
        col = _hsv_arr(hue % 1.0, 1.0, np.clip(val, 0.0, 1.0))
        # Akzente: schmale Bänder, abwechselnd Akzentfarbe und Gegenfarbe, wandern langsam, Breite atmet
        k_acc = 21.0 + 5.0 * math.sin(T * 0.009)
        ua = x * k_acc + T * 0.01 + 0.15 * field + tp["ph_s"] * 2.0
        width = 0.5 + 0.12 * math.sin(T * 0.017)
        am = np.clip((np.sin(tau * ua) - width) / 0.25, 0.0, 1.0)
        band = np.floor(ua).astype(int) % 2
        acc_hue = np.where(band == 0, ha, (hm + 0.5) % 1.0) + tp["hue_s"]
        acc_col = _hsv_arr(acc_hue % 1.0, 1.0, 0.95)
        am = am * (0.6 + 0.4 * inten)
        col = col * (1.0 - am[:, None]) + acc_col * am[:, None]
        m = 0.5 + 0.5 * np.sin(tau * (x * (0.9 + 0.4 * math.sin(T * 0.005)) + T * 0.008 + 0.3 * field))
        dg = np.clip((m - 0.6) / 0.3, 0.0, 1.0)                   # dunkelgrüne Täler, wandern mit
        dg = np.maximum(dg, (1.0 - inten) * 0.55) * (1.0 - am)    # am Tresen mehr Dunkelgrün, Akzente bleiben
        frame = col * (1.0 - dg[:, None]) + self.TRIP_DG * (0.8 + 0.2 * self.bass_s) * dg[:, None]
        frame = np.maximum(frame, self.TRIP_DG * 0.35)            # nie ganz aus
        return frame

    CITY_PAL = np.array([[255, 0, 170], [0, 220, 255], [255, 140, 10], [140, 40, 255]], dtype=float)   # Magenta, Cyan, Bernstein, Violett
    CITY_W = np.array([0.34, 0.32, 0.24, 0.10])

    def _city_setup(self) -> dict:
        """Häuserzeile: Fenster aus 2-4 LEDs mit 1-2 LED Lücke, zwischen Häusern 3-6 LEDs Lücke; je Fenster eine Neonfarbe."""
        n = self.n
        starts, lens, house = [], [], []
        pos, h = 0, 0
        left = self.rng.randint(4, 9)                             # Fenster bis zum nächsten Haus
        while pos < n:
            w = self.rng.choice((2, 3, 3, 4))
            if pos + w > n:
                break
            starts.append(pos)
            lens.append(w)
            house.append(h)
            pos += w + self.rng.choice((1, 1, 2))
            left -= 1
            if left <= 0:
                pos += self.rng.randint(3, 6)
                h += 1
                left = self.rng.randint(4, 9)
        nw = len(starts)
        win_of = np.full(n, -1)
        for i, (a, w) in enumerate(zip(starts, lens)):
            win_of[a:a + w] = i
        cols = self.CITY_PAL[self.nrng.choice(len(self.CITY_PAL), size=nw, p=self.CITY_W)]
        on = (self.nrng.random(nw) < 0.4).astype(float)
        return {"win_of": win_of, "starts": np.array(starts), "house": np.array(house), "nw": nw, "cols": cols,
                "on": on, "lvl": on.copy(), "rank": self.nrng.random(nw), "burnt": np.zeros(nw, dtype=bool),
                "emerg": self.nrng.random(nw) < 0.05, "last_state": 0, "state_t0": 0.0, "flash_t": -100.0,
                "lt_seen": -100.0, "fire_seen": -100.0, "car_next": time.monotonic() + self.rng.uniform(15.0, 30.0),
                "drone_next": time.monotonic() + self.rng.uniform(50.0, 90.0), "cars": [], "beats": 0,
                "boards": None, "board_pat": 0}

    def _city(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Dachterrasse: die Kette ist eine Fensterfront der Stadt. Fenster aus 2-4 LEDs in Magenta, Cyan, Bernstein, Violett,
        etwa 40 % an; auf jedem Beat gehen ein paar an oder aus. Darüber der Lichtzustand der Szene (ROTER ALARM rot mit
        wanderndem Drehlicht, SÄURE giftgrün mit flackernden Röhren, ÜBERLAST fast alles hell, Blöcke brennen durch, NUR WERBUNG
        lange Reklamen mit Lauflicht, BLACKOUT Notstrom und rote Flugwarnlichter, BLITZSCHLAG der einzige echte Blitz), das
        Wetter (Regenschimmer, Nebel, Säure, Asche) und Ereignisse ohne Blitz (Stromausfall blockweise, EMP als Welle).
        Specials: fliegendes Auto, Polizeidrohne, Feuerwerk."""
        n = self.n
        c = getattr(self, "city", None)
        if c is None or len(c["win_of"]) != n:
            c = self.city = self._city_setup()
        nw, win_of = c["nw"], c["win_of"]
        state = int(st.get("state", 0))
        mix = float(st.get("mix", 1.0 if state else 0.0))
        weather = int(st.get("weather", 0))
        x = self._idx()
        if state != c["last_state"]:
            c["last_state"], c["state_t0"] = state, now
            c["burnt"][:] = False
            if state == 6 and now - c["flash_t"] > 8.0:          # Blitzschlag: der einzige echte Blitz
                c["flash_t"] = now
        lt = float(st.get("lightning_t0", -100.0))
        if lt > c["lt_seen"] + 0.5:                               # Drop-Blitz der Szene: höchstens alle 30 s
            c["lt_seen"] = lt
            if now - lt < 1.0 and now - c["flash_t"] > 30.0:
                c["flash_t"] = now
        ft = float(st.get("fire_t0", -100.0))
        if ft > c["fire_seen"] + 0.5:
            c["fire_seen"] = ft
            if now - ft < 1.0:
                self._add(now, "fireworks", 3.5, self.CITY_PAL[self.rng.randrange(4)])
        # Fenster gehen im Takt an und aus (Ziel ~40 %, mit Energie etwas mehr)
        if is_beat or (now - self.last_beat > 2.0 and now - c.get("tick", 0.0) > 0.7):
            c["tick"] = now
            c["beats"] += 1
            target = 0.36 + 0.14 * self.energy
            k = max(2, int(nw * (0.015 + 0.03 * self.e_fast)))
            idx = self.nrng.choice(nw, size=k, replace=False)
            for i in idx:
                ratio = c["on"].mean()
                c["on"][i] = 1.0 if (self.rng.random() < (0.5 + (target - ratio) * 3.0)) else 0.0
            if state == 4 and c["beats"] % 4 == 0:                # Überlast: ein Block brennt durch
                h = self.rng.choice(c["house"])
                c["burnt"] |= c["house"] == h
            if state == 5:
                c["board_pat"] = (c["board_pat"] + 1) % 3
        c["lvl"] += (c["on"] - c["lvl"]) * min(1.0, dt * 10.0)
        wl = c["lvl"].copy()
        wcol = c["cols"].copy()
        # Ereignisse der Szene (ohne Blitz): Stromausfall blockweise, EMP als Welle
        bo = now - float(st.get("blackout_t0", -100.0))
        emp = now - float(st.get("emp_t0", -100.0))
        dark = np.zeros(nw)
        bo_black = 1.0                                            # Stromausfall: Faktor für die ganze Kette (0 = schwarz)
        if 0.0 <= bo < 14.0:
            # 1) 0-0,8 s: Fenster gehen in einer schnellen Welle aus, 2) bis 4,5 s alles ganz dunkel (auch Regen, Autos,
            # Warnlichter), 3) ab 4,5 s kommen die Häuser im Beat zurück, knallbunt (je Haus eigener Farbton, der je Beat
            # weiterspringt), ab 9 s ist alles bunt da, die letzten 1,5 s gleitet es zurück in die normale Stadt
            t0 = float(st.get("blackout_t0", 0.0))
            if c.get("bo_t0") != t0:
                c["bo_t0"] = t0
                nh = int(c["house"].max()) + 1
                c["bo_hue"] = self.nrng.random(nh)
                c["bo_order"] = self.nrng.random(nh)
                c["bo_rot"] = 0.0
            if is_beat:
                c["bo_rot"] += 0.09
            if bo < 0.8:
                dark = (c["rank"] < bo / 0.8).astype(float)
            elif bo < 4.5:
                bo_black = 0.0
            else:
                back = min(1.0, (bo - 4.5) / 4.5)                  # Anteil der Häuser, die wieder da sind
                there = c["bo_order"][c["house"]] < back
                hue = (c["bo_hue"][c["house"]] + c["bo_rot"]) % 1.0
                bunt = _hsv_arr(hue, 1.0, 1.0)
                k_b = 1.0 if bo < 12.5 else max(0.0, (14.0 - bo) / 1.5)
                lv_b = np.where(there, np.where(c["rank"] < 0.85, 1.0, 0.0), 0.0)
                wl = wl * (1.0 - k_b) + lv_b * k_b
                wcol = wcol * (1.0 - k_b) + bunt * k_b
        elif 0.0 <= emp < 10.0:
            seed = float(st.get("emp_seed", 50.0))
            centre = (seed * 0.6180339) % 1.0
            xs = (c["starts"] / max(1, n - 1))
            radius = min(1.2, emp * 0.25)
            inside = np.abs(xs - centre) < radius
            back = (emp - 3.5) / 6.5 if emp > 3.5 else 0.0     # ab 3,5 s kommen Fenster einzeln zurück
            dark = (inside & (c["rank"] >= back)).astype(float)
            edge = np.abs(np.abs(xs - centre) - radius) < 0.015
            wl = np.where(edge & (self.nrng.random(nw) < 0.5), 1.0, wl)
        wl = wl * (1.0 - dark)
        emerg_only = state == 1 and not (0.0 <= bo < 14.0)
        # Lichtzustand
        sc = None
        if state == 1 or emerg_only:                              # Blackout: Notstrom
            k1 = 1.0 if emerg_only and state != 1 else mix
            flick = 0.55 + 0.45 * np.sin(now * 3.1 + c["rank"] * 40.0) ** 2
            el = np.where(c["emerg"], flick, 0.0)
            wl = wl * (1.0 - k1) + el * k1
            wcol = wcol * (1.0 - k1) + np.array([255, 90, 20]) * k1
        elif state == 2:                                          # roter Alarm
            wcol = wcol * (1.0 - mix) + np.array([255, 0, 0]) * mix
            wl = wl * (1.0 - 0.4 * mix)
        elif state == 3:                                          # Säure: giftgrün, Röhren flackern
            wcol = wcol * (1.0 - mix) + np.array([60, 255, 20]) * mix
            drop = self.nrng.random(nw) < 0.06 * mix
            wl = np.where(drop, wl * 0.15, wl)
        elif state == 4:                                          # Überlast: fast alles hell, Blöcke brennen durch
            wl = wl * (1.0 - mix) + mix * np.where(c["burnt"], 0.0, np.where(c["rank"] < 0.85, 1.0, 0.0))
            wcol = wcol * (1.0 - mix) + np.array([255, 190, 80]) * mix
        elif state == 5:                                          # nur Werbung: Fenster aus
            wl = wl * (1.0 - mix)
        elif state == 6:                                          # nach dem Blitz: Stadt blau-weiß
            wcol = wcol * (1.0 - mix) + np.array([90, 140, 255]) * mix
        frame = np.zeros((n, 3))
        m = win_of >= 0
        frame[m] = wcol[win_of[m]] * wl[win_of[m]][:, None] * 0.9
        if state == 2:                                            # Drehlicht wandert hin und her
            pos = abs(((now - c["state_t0"]) * 0.35) % 2.0 - 1.0)
            frame += np.outer(np.exp(-((x - pos) / 0.035) ** 2) * mix, np.array([255.0, 0.0, 0.0]))
        if state == 5:                                            # Leuchtreklamen mit Lauflicht
            if c["boards"] is None:
                c["boards"] = [(int(self.rng.uniform(0.05, 0.9) * n), self.rng.randint(15, 20), self.rng.randrange(2)) for _ in range(4)]
            for (a, w, ci) in c["boards"]:
                seg = np.arange(a, min(n, a + w))
                rel = seg - a
                if c["board_pat"] == 0:
                    lit = ((rel + int(now * 8)) // 3) % 2 == 0
                elif c["board_pat"] == 1:
                    lit = ((rel - int(now * 8)) // 2) % 2 == 0
                else:
                    lit = np.ones(len(seg), dtype=bool)
                colb = self.CITY_PAL[ci]
                frame[seg] = np.outer(lit * (0.6 + 0.4 * self.bass_s) * mix, colb) + frame[seg] * (1.0 - mix)
        else:
            c["boards"] = None
        if emerg_only or state == 1:                              # rote Flugwarnlichter auf den Dächern
            blink = (now % 1.6) < 0.25
            for h in range(0, int(c["house"].max()) + 1, 3):
                ws = np.where(c["house"] == h)[0]
                if len(ws) and blink:
                    frame[int(c["starts"][ws[0]])] = np.array([255.0, 0.0, 0.0])
        # Wetter
        if weather == 0:                                          # Regen: Schimmer läuft über die Fenster
            if now >= self.drip_next:
                self.drip_next = now + self.rng.uniform(0.4, 1.0)
                self.drips.append([now, self.rng.uniform(0.18, 0.3), 1.0])
            shim = np.zeros(n)
            keep = []
            for dr in self.drips:
                pos = 1.0 - (now - dr[0]) * dr[1]
                if pos > -0.05:
                    keep.append(dr)
                    shim += np.exp(-((x - pos) / 0.02) ** 2)
            self.drips = keep[-20:]
            frame *= (1.0 + 0.6 * np.minimum(shim, 1.0))[:, None]
        elif weather == 1:                                        # Nebel: weich und blass
            mean = frame.mean(axis=0)
            frame = (frame * 0.45 + mean * 0.55) * 0.75
        elif weather == 2:                                        # Säureregen: grüner Stich
            frame = frame * 0.7 + frame.max(axis=1, keepdims=True) * np.array([0.12, 0.35, 0.05])
        elif weather == 3:                                        # Asche: glühende Punkte fallen
            if now >= self.drip_next:
                self.drip_next = now + self.rng.uniform(0.25, 0.7)
                self.drips.append([now, self.rng.uniform(0.03, 0.07), self.rng.random()])
            keep = []
            for dr in self.drips:
                pos = (dr[2] + (now - dr[0]) * dr[1] * (1 if dr[2] < 0.5 else -1))
                if 0.0 <= pos <= 1.0 and now - dr[0] < 6.0:
                    keep.append(dr)
                    glow = 0.6 + 0.4 * math.sin((now - dr[0]) * 7.0 + dr[2] * 20.0)
                    frame += np.outer(np.exp(-((x - pos) / 0.004) ** 2) * glow, np.array([255.0, 90.0, 10.0]))
            self.drips = keep[-24:]
        # Specials: fliegendes Auto, Polizeidrohne
        if now >= c["car_next"]:
            c["car_next"] = now + self.rng.uniform(25.0, 50.0)
            c["cars"].append({"t0": now, "d": self.rng.choice((1, -1)), "v": self.rng.uniform(0.12, 0.2), "kind": "car"})
        if now >= c["drone_next"]:
            c["drone_next"] = now + self.rng.uniform(60.0, 120.0)
            c["cars"].append({"t0": now, "d": self.rng.choice((1, -1)), "v": self.rng.uniform(0.06, 0.1), "kind": "drone",
                              "end": self.rng.uniform(0.35, 0.7)})
        keepc = []
        for car in c["cars"]:
            u = (now - car["t0"]) * car["v"]
            limit = car.get("end", 1.05)
            if u > limit + 0.05:
                continue
            keepc.append(car)
            pos = u if car["d"] > 0 else 1.0 - u
            px = int(round(pos * (n - 1)))
            dlt = car["d"] if not self.reverse else -car["d"]
            if car["kind"] == "car":                              # zwei Scheinwerfer vorne, zwei Rücklichter hinten
                for o, colc in ((0, (255, 235, 190)), (dlt, (255, 235, 190)), (-6 * dlt, (255, 0, 0)), (-7 * dlt, (255, 0, 0))):
                    j = px + o
                    if 0 <= j < n:
                        frame[j] = np.array(colc, dtype=float)
            else:                                                 # Drohne: rot/blau im Wechsel
                red = (now * 3.0) % 1.0 < 0.5
                for o in (-1, 0, 1):
                    j = px + o
                    if 0 <= j < n:
                        frame[j] = np.array([255.0, 0.0, 0.0]) if (red ^ (o == 1)) else np.array([0.0, 40.0, 255.0])
        c["cars"] = keepc
        if bo_black < 1.0:
            frame = frame * bo_black                              # Stromausfall: wirklich alles dunkel
        # Blitz (nur Blitzschlag oder kräftiger Drop): zweimal kurz bläulich-weiß, dann Nachglühen
        fa = now - c["flash_t"]
        if 0.0 <= fa < 0.7:
            k = 1.0 if fa < 0.08 or 0.18 < fa < 0.24 else max(0.0, 0.5 - fa) * 0.6
            frame = frame * (1.0 - k) + np.array([170.0, 200.0, 255.0]) * k
        if not live:
            frame *= 0.6
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

    TJ_K = 30.0                                                   # Zeitsprung: LEDs je Streckeneinheit (ruhig)
    TJ_DASH = 36                                                  # Abstand der Markierungen in LEDs

    def _timejump(self, now, dt, st: dict, bass, high, is_beat, live) -> np.ndarray:
        """Zurück in die Zukunft, Fahrt: farbreduziert, aber immer läuft etwas von vorne nach hinten. Grund: ganz langsame
        Farbfronten nur in Tönen nahe der Bildschirmfarbe (±20 Grad), gedämpft. Darüber Markierungen (je TJ_DASH LEDs ein
        Strich aus 4 LEDs) in einer Farbe, die mit der gefahrenen Strecke der Szene ruhig nach hinten ziehen; je näher an
        88 MPH, desto länger werden sie zu Lichtstreifen (Zeitkreise laden). Zeitsprung (`timejump_jump` -> `boost_until`):
        Fronten und Streifen beschleunigen weich, Elektroblau, ein paar Kometen, kein Flackern; danach wieder ruhig."""
        n = self.n
        x = self._idx()
        idx = np.arange(n) if not self.reverse else n - 1 - np.arange(n)
        col, col2 = self._base_col()
        col = _no_white(np.asarray(col, dtype=float))
        boost = now < self.boost_until
        bk = max(0.0, min(1.0, (self.boost_until - now) / 3.0)) if boost else 0.0   # 1 am Sprungbeginn, weich auslaufend
        hm = float(_hue(col[None, :])[0]) / 360.0
        if not self.fronts:
            self.fronts.append({"col": _hsv(hm, 0.85, 1.0), "pos": 1.2})
        if now >= self.front_next:                                # neue Front von vorne, nur Töne nahe der Bildschirmfarbe
            self.front_next = now + (self.rng.uniform(1.0, 2.0) if boost else self.rng.uniform(12.0, 20.0))
            self.front_col_i += 1
            if boost:
                c = np.array([80.0, 160.0, 255.0]) if self.front_col_i % 2 else np.array([150.0, 200.0, 255.0])
            else:
                c = _hsv((hm + self.rng.uniform(-0.055, 0.055)) % 1.0, self.rng.uniform(0.7, 0.95), 1.0)
            self.fronts.append({"col": c, "pos": -0.05})
        fspeed = ((0.02 + 0.02 * self.e_fast) * live + (1.0 - live) * 0.015) * (1.0 + 4.0 * bk)
        for fr in self.fronts:
            fr["pos"] += fspeed * dt
        while len(self.fronts) > 1 and self.fronts[1]["pos"] > 1.15:
            self.fronts.pop(0)
        frame = np.zeros((n, 3))
        for fr in self.fronts:
            cover = np.clip((fr["pos"] - x) / 0.05 + 0.5, 0.0, 1.0)
            frame = frame * (1.0 - cover)[:, None] + np.outer(cover, fr["col"])
        lvl = (0.16 + 0.12 * self.bass_s) * live + (1.0 - live) * 0.14
        frame = frame * lvl
        # Markierungen ziehen mit der Strecke nach hinten
        st = st or {}
        dist = float(st.get("dist", now * 0.3))
        mph = float(st.get("mph", 50.0))
        driving = bool(st.get("driving", True))
        off = dist * self.TJ_K * (1.0 + 2.0 * bk)
        load = max(0.0, min(1.0, (mph - 60.0) / 28.0))             # 60..88 MPH: Striche werden zu Streifen
        dash_len = 4.0 + 14.0 * load + 10.0 * bk
        ph = (idx - off) % self.TJ_DASH
        head = np.clip(1.0 - np.abs(ph - self.TJ_DASH / 2.0) / (dash_len / 2.0), 0.0, 1.0)
        dash_col = _hsv(hm, 0.55, 1.0) * (1.0 - bk) + np.array([120.0, 190.0, 255.0]) * bk
        frame += np.outer(head * (0.75 if driving else 0.35), dash_col)
        if bk > 0.3 and self.nrng.random() < 0.8 * dt:
            self._add(now, "comet", 1.2, np.array([170.0, 210.0, 255.0]), d=1.0)
        return frame

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


def _no_white(c: np.ndarray) -> np.ndarray:
    """Weißanteil raus: drei Viertel des kleinsten Kanals abziehen, dann voll aussteuern (Rosa -> Pink, Eisblau -> Blau)."""
    c = np.asarray(c, dtype=float)
    c = np.clip(c - 0.75 * c.min(), 0.0, None)
    return c * (255.0 / max(1.0, float(c.max())))


def _hsv_arr(h: np.ndarray, s: float, v) -> np.ndarray:
    """HSV -> RGB (0..255) für ganze Arrays (h 0..1, v Skalar oder Array)."""
    h6 = h * 6.0
    i = np.floor(h6).astype(int) % 6
    f = h6 - np.floor(h6)
    v = np.broadcast_to(np.asarray(v, dtype=float), h.shape)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=1) * 255.0


def _hsv(h: float, s: float, v: float) -> np.ndarray:
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i]
    return np.array([r * 255.0, g * 255.0, b * 255.0])
