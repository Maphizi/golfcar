"""Drehknopf am PXN-CB1 -> Lautstärke der Sprachausgabe (KITT, HAL, BIBO, Ansagen).

Schreibt den Faktor 0..max_percent/100 nach logs/voice_volume.txt; die Sprecher lesen ihn vor jedem
Satz. Die Musik bleibt davon unberührt (dafür launcher/music_knob.py). Mit target = "sink" regelt
der Knopf stattdessen den ganzen Ausgang über wpctl.

Zwei Modi:
  ABS-Achse (axis = "ABS_Z" o. ä.): absoluter Wert wird auf min_percent..max_percent abgebildet.
  REL-Modus (rel = true): jedes Dreh-Ereignis (REL_MISC, REL_DIAL, REL_WHEEL, REL_HWHEEL) ändert die Lautstärke um ±step Prozent.
Erscheint der Knopf als Tasten (zwei BTN-Codes, Launcher-Log "Taste ohne Belegung"), in config/keymap.toml action = "voice_up" /
"voice_down" belegen. Prüfen auf dem Pi: scripts/voice_knob_check.py (Geräte, Ereignisse beim Drehen, Faktor in logs/voice_volume.txt).
"""
from __future__ import annotations

import logging
import select
import subprocess
import threading
import time

import evdev
from evdev import ecodes

from pathlib import Path

log = logging.getLogger("volume")
VOICE_FILE = Path(__file__).resolve().parents[1] / "logs" / "voice_volume.txt"
DEVICE_NAME = "PXN"
SKIP = {ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y}
REL_CODES = {ecodes.REL_MISC, ecodes.REL_DIAL, ecodes.REL_WHEEL, ecodes.REL_HWHEEL}   # Dreh-Ereignisse des Knopfs


class RelDecoder:
    """Macht aus REL-Ereignissen des PXN Schritte (+1/-1 je Ereignis). Zwei Arten von Geräten:
    - echte Schritte: nur beim Drehen kommt ein Ereignis mit +n / -n (224 = -32 bei 8 Bit)
    - Stellung: das Board schickt den Wert dauernd (~60/s) und er ändert sich nur beim Drehen (PXN-CB1: REL_MISC)
    Die erste Sekunde nach dem ersten Ereignis ist Anlauf (Ereignisse werden verworfen): kommen darin >= REPEAT
    Ereignisse mit demselben Wert, ist es ein Stellungsgeber (ein echter Dreher schickt ohne Drehen gar nichts); dann
    zählt nur eine Änderung, Richtung aus der Differenz (8 Bit mit Überlauf)."""
    REPEAT = 25
    WARMUP_S = 1.0

    def __init__(self, name: str):
        self.name = name
        self.last = None
        self.t0 = 0.0
        self.warm: list[int] = []
        self.decided = False
        self.positional = False

    def step(self, value: int) -> int:
        """Schritte (-3..3) für ein REL-Ereignis, 0 = nichts."""
        now = time.monotonic()
        if not self.decided:
            if not self.t0:
                self.t0 = now
            self.warm.append(value)
            self.last = value
            if now - self.t0 < self.WARMUP_S:
                return 0
            self.decided = True
            top = max(self.warm.count(v) for v in set(self.warm))
            self.positional = top >= self.REPEAT
            log.info("%s: %d Ereignisse im Anlauf -> %s", self.name, len(self.warm),
                     "Knopf meldet die Stellung, nur Änderungen zählen" if self.positional else "echte Dreh-Schritte")
            return 0
        prev, self.last = self.last, value
        if self.positional:
            if prev is None or value == prev:
                return 0
            d = ((value - prev + 128) % 256) - 128
            return max(-3, min(3, d))
        if value == 0:
            return 0
        val = value - 256 if 128 <= value < 256 else value       # 224 = -32 bei 8-Bit-Drehern
        return 1 if val > 0 else -1


class VolumeKnob(threading.Thread):
    def __init__(self, cfg: dict | None = None):
        super().__init__(name="volume-knob", daemon=True)
        cfg = cfg or {}
        self._stop = threading.Event()
        self.axis = ecodes.ecodes.get(str(cfg.get("axis", "")), None)
        self.rel = bool(cfg.get("rel", False))
        self.step = int(cfg.get("step", 5))
        self.min_pct = int(cfg.get("min_percent", 0))
        self.max_pct = int(cfg.get("max_percent", 100))
        self.invert = bool(cfg.get("invert", False))
        self.target = str(cfg.get("target", "voice"))
        self.cur_pct = int(cfg.get("start_percent", 100))
        if self.rel:
            log.info("Lautstärkeknopf: REL_MISC-Modus, Schritt %d%%, Start %d%%", self.step, self.cur_pct)
        elif self.axis is None:
            log.info("Lautstärkeknopf: keine Achse konfiguriert, nur Beobachtung ([volume].axis in settings.toml)")
        self.last_set = 0.0
        self.last_pct = -1
        self.pending: int | None = None

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            while not self._stop.is_set():
                devs = self._find()
                if not devs:
                    if not getattr(self, "_warned", False):
                        self._warned = True
                        log.warning("Lautstärkeknopf: kein PXN-Gerät mit %s gefunden (scripts/voice_knob_check.py)",
                                    "Dreh-Ereignissen (REL)" if self.rel else "ABS-Achsen")
                    time.sleep(3)
                    continue
                names = ", ".join(f"{d.name} ({d.path})" for d in devs)
                log.info("Lautstärkeknopf: lese von %s", names)
                self._loop(devs)
                for d in devs:
                    d.close()
        except Exception as exc:
            log.warning("Lautstärkeknopf beendet: %s", exc)

    def _find(self) -> list[evdev.InputDevice]:
        out = []
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                if DEVICE_NAME not in d.name:
                    d.close()
                    continue
                if self.rel:
                    # Gerät mit Dreh-Ereignissen suchen (REL_MISC o. ä.)
                    if REL_CODES & set(d.capabilities().get(ecodes.EV_REL, [])):
                        out.append(d)
                        continue
                else:
                    # ABS-Achsen-Gerät suchen (ohne D-Pad)
                    axes = [c for c, _ in d.capabilities().get(ecodes.EV_ABS, []) if c not in SKIP]
                    if axes:
                        out.append(d)
                        continue
                d.close()
            except Exception:
                pass
        return out

    def _loop(self, devs: list[evdev.InputDevice]) -> None:
        abs_info = {}
        now_seen: dict[int, int] = {}
        last_log: dict[int, float] = {}
        for d in devs:
            for code, ai in d.capabilities(absinfo=True).get(ecodes.EV_ABS, []):
                if isinstance(ai, evdev.AbsInfo):
                    abs_info[(d.fd, code)] = ai
        rel_seen: set[int] = set()
        dec = RelDecoder("Lautstärkeknopf")
        while not self._stop.is_set():
            r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
            for d in devs:
                if d.fd not in r:
                    continue
                try:
                    for ev in d.read():
                        if self.rel:
                            # Dreh-Ereignis: jedes Ereignis = ein Schritt
                            if ev.type != ecodes.EV_REL or ev.code not in REL_CODES:
                                continue
                            n = dec.step(ev.value)
                            if n == 0:
                                continue
                            if ev.value not in rel_seen and len(rel_seen) < 12:
                                rel_seen.add(ev.value)
                                log.info("%s Rohwert %d -> %+d Schritt(e)", ecodes.REL.get(ev.code, ev.code), ev.value, n)
                            delta = self.step * n
                            if self.invert:
                                delta = -delta
                            self.cur_pct = max(self.min_pct, min(self.max_pct, self.cur_pct + delta))
                            self.pending = self.cur_pct
                        else:
                            # ABS-Achse: absoluter Wert
                            if ev.type != ecodes.EV_ABS or ev.code in SKIP:
                                continue
                            if self.axis is None:
                                key = ev.code
                                if now_seen.get(key) != ev.value and time.monotonic() - last_log.get(key, 0.0) > 5.0:
                                    log.info("Achse %s = %d (dann [volume].axis = \"%s\" in settings.toml)",
                                             ecodes.ABS.get(key, key), ev.value, ecodes.ABS.get(key, key))
                                    last_log[key] = time.monotonic()
                                    now_seen[key] = ev.value
                                continue
                            if ev.code != self.axis:
                                continue
                            ai = abs_info.get((d.fd, ev.code))
                            lo, hi = (ai.min, ai.max) if ai and ai.max > ai.min else (0, 255)
                            frac = (ev.value - lo) / float(hi - lo)
                            frac = min(1.0, max(0.0, frac))
                            if self.invert:
                                frac = 1.0 - frac
                            self.pending = int(round(self.min_pct + frac * (self.max_pct - self.min_pct)))
                except OSError:
                    return
            now = time.monotonic()
            if self.pending is not None and now - self.last_set >= 0.1:
                self._apply(self.pending)
                self.pending = None
                self.last_set = now

    def nudge(self, steps: int) -> None:
        """Stimme um steps x step Prozent lauter (>0) oder leiser (<0); von Tasten (keymap voice_up/voice_down)."""
        self.cur_pct = max(self.min_pct, min(self.max_pct, self.cur_pct + self.step * steps))
        self._apply(self.cur_pct)

    def _apply(self, pct: int) -> None:
        if pct == self.last_pct:
            return
        self.last_pct = pct
        if self.target == "sink":
            try:
                subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{pct}%"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            except (OSError, subprocess.TimeoutExpired) as exc:
                log.warning("wpctl fehlgeschlagen: %s", exc)
            return
        try:
            VOICE_FILE.parent.mkdir(parents=True, exist_ok=True)
            VOICE_FILE.write_text(f"{pct / 100.0:.2f}")
            log.info("Stimme %d%% -> %s", pct, VOICE_FILE.name)
        except OSError as exc:
            log.warning("voice_volume.txt: %s", exc)
