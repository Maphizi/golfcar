"""Drehknopf am PXN-CB1 -> Lautstärke des Standard-Ausgangs (PipeWire, wpctl).

Liest alle Achsenwerte (EV_ABS) der PXN-Geräte außer dem D-Pad (HAT0X/Y). Welche Achse der Knopf
ist, steht in config/settings.toml [volume].axis (z. B. "ABS_Z"); leer = die erste Achse, die sich
bewegt, wird genommen und ins Log geschrieben. Der Wertebereich kommt aus den Achsendaten des
Geräts und wird auf min_percent..max_percent abgebildet. Höchstens zehn Änderungen pro Sekunde.
"""
from __future__ import annotations

import logging
import select
import subprocess
import threading
import time

import evdev
from evdev import ecodes

log = logging.getLogger("volume")
DEVICE_NAME = "PXN"
SKIP = {ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y}


class VolumeKnob(threading.Thread):
    def __init__(self, cfg: dict | None = None):
        super().__init__(name="volume-knob", daemon=True)
        cfg = cfg or {}
        self._stop = threading.Event()
        self.axis = ecodes.ecodes.get(str(cfg.get("axis", "")), None)
        self.min_pct = int(cfg.get("min_percent", 0))
        self.max_pct = int(cfg.get("max_percent", 100))
        self.invert = bool(cfg.get("invert", False))
        self.target = str(cfg.get("target", "@DEFAULT_AUDIO_SINK@"))
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
                    time.sleep(3)
                    continue
                names = ", ".join(f"{d.name} ({d.path})" for d in devs)
                log.info("Lautstärkeknopf: lese Achsen von %s", names)
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
                axes = [c for c, _ in d.capabilities().get(ecodes.EV_ABS, []) if c not in SKIP]
                if DEVICE_NAME in d.name and axes:
                    out.append(d)
                else:
                    d.close()
            except Exception:
                pass
        return out

    def _loop(self, devs: list[evdev.InputDevice]) -> None:
        info = {}
        for d in devs:
            for code, ai in d.capabilities(absinfo=True).get(ecodes.EV_ABS, []):
                if isinstance(ai, evdev.AbsInfo):
                    info[(d.fd, code)] = ai
        while not self._stop.is_set():
            r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
            for d in devs:
                if d.fd not in r:
                    continue
                try:
                    for ev in d.read():
                        if ev.type != ecodes.EV_ABS or ev.code in SKIP:
                            continue
                        if self.axis is None:
                            self.axis = ev.code
                            log.info("Drehknopf erkannt: Achse %s (in settings.toml [volume].axis eintragen)",
                                     ecodes.ABS.get(ev.code, ev.code))
                        if ev.code != self.axis:
                            continue
                        ai = info.get((d.fd, ev.code))
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

    def _apply(self, pct: int) -> None:
        if pct == self.last_pct:
            return
        self.last_pct = pct
        try:
            subprocess.run(["wpctl", "set-volume", self.target, f"{pct}%"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            log.debug("Lautstärke %d%%", pct)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("wpctl fehlgeschlagen: %s", exc)
