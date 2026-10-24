"""Drehknopf am PXN-CB1 -> Helligkeit des LED-Boards (WLED).

Der Knopf sendet die Tasten KEY_NEXTSONG (rechts = heller) / KEY_PREVIOUSSONG (links = dunkler) über das
Tastatur-Interface des PXN; ein Raster = step Prozent. Der Faktor (start_percent/100 .. max_percent/100) steht in
logs/led_brightness.txt: wled.dim() multipliziert ihn auf [controller].dim (Profile per HTTP), der LED-Stream jeder
Szene (launcher/ledstream.py) liest ihn alle 0,5 s. 0 = LEDs aus. Auch über keymap.toml: action = "led_up" / "led_down".
"""
from __future__ import annotations

import logging
import select
import threading
import time
from pathlib import Path

import evdev
from evdev import ecodes

log = logging.getLogger("ledknob")
BRIGHT_FILE = Path(__file__).resolve().parents[1] / "logs" / "led_brightness.txt"
DEVICE_NAME = "PXN"
KEYS = {ecodes.KEY_NEXTSONG: 1, ecodes.KEY_PREVIOUSSONG: -1}


class LedKnob(threading.Thread):
    def __init__(self, cfg: dict | None = None):
        super().__init__(name="led-knob", daemon=True)
        cfg = cfg or {}
        self._stop = threading.Event()
        self.step = int(cfg.get("step", 5))
        self.min_pct = int(cfg.get("min_percent", 0))
        self.max_pct = int(cfg.get("max_percent", 140))
        self.invert = bool(cfg.get("invert", False))
        self.cur_pct = int(cfg.get("start_percent", 100))
        self.last_pct = -1
        self._apply(self.cur_pct)
        log.info("Helligkeitsknopf: Titel-Tasten, Schritt %d%%, Start %d%%, max %d%%", self.step, self.cur_pct, self.max_pct)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            while not self._stop.is_set():
                devs = self._find()
                if not devs:
                    if not getattr(self, "_warned", False):
                        self._warned = True
                        log.warning("Helligkeitsknopf: kein PXN-Gerät mit KEY_NEXTSONG/PREVIOUSSONG (scripts/board_learn.py)")
                    time.sleep(3)
                    continue
                log.info("Helligkeitsknopf: lese %s", ", ".join(d.name for d in devs))
                self._loop(devs)
                for d in devs:
                    d.close()
        except Exception as exc:
            log.warning("Helligkeitsknopf beendet: %s", exc)

    def _find(self) -> list[evdev.InputDevice]:
        out = []
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                keys = d.capabilities().get(ecodes.EV_KEY, [])
                if DEVICE_NAME in d.name and any(k in keys for k in KEYS):
                    out.append(d)
                else:
                    d.close()
            except Exception:
                pass
        return out

    def _loop(self, devs: list[evdev.InputDevice]) -> None:
        while not self._stop.is_set():
            r, _, _ = select.select([d.fd for d in devs], [], [], 0.3)
            for d in devs:
                if d.fd not in r:
                    continue
                try:
                    for ev in d.read():
                        if ev.type == ecodes.EV_KEY and ev.value == 1 and ev.code in KEYS:
                            self.nudge(KEYS[ev.code])
                except OSError:
                    return

    def nudge(self, steps: int) -> None:
        """Helligkeit um steps x step Prozent heller (>0) oder dunkler (<0)."""
        if self.invert:
            steps = -steps
        self.cur_pct = max(self.min_pct, min(self.max_pct, self.cur_pct + self.step * steps))
        self._apply(self.cur_pct)

    def _apply(self, pct: int) -> None:
        if pct == self.last_pct:
            return
        self.last_pct = pct
        try:
            BRIGHT_FILE.parent.mkdir(parents=True, exist_ok=True)
            BRIGHT_FILE.write_text(f"{pct / 100.0:.2f}")
            log.info("LED-Helligkeit %d%% -> %s", pct, BRIGHT_FILE.name)
        except OSError as exc:
            log.warning("led_brightness.txt: %s", exc)
