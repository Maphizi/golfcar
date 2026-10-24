"""Zweiter Drehknopf -> Musiklautstärke.

Läuft mpv mit --input-ipc-server=/tmp/mpv.sock (scripts/music.sh), regelt der Knopf nur den mpv-Stream. Ohne mpv
(Musik vom Handy: Spotify Connect, AirPlay, Bluetooth) regelt er den ganzen Ausgang über wpctl (Standard-Sink); die
Stimme folgt dann mit, der Stimmenknopf regelt sie relativ dazu. Der Knopf kann drei Dinge liefern, alle werden erkannt:
  - Consumer-Tasten KEY_VOLUMEUP/KEY_VOLUMEDOWN (Tastatur-Interface des PXN)
  - Dreh-Schritte REL_MISC/REL_DIAL/REL_WHEEL (relativ), wenn [music].rel = true
  - eine ABS-Achse, wenn [music].axis gesetzt ist (absolut 0..100 %)
Erscheint der Knopf als Tasten (zwei BTN-Codes), in config/keymap.toml action = "music_up" / "music_down" belegen.
"""
from __future__ import annotations

import json
import logging
import select
import socket
import subprocess
import threading
import time

import evdev
from evdev import ecodes

from launcher.volume_knob import REL_CODES, RelDecoder

log = logging.getLogger("music")
DEVICE_NAME = "PXN"


class MusicKnob(threading.Thread):
    def __init__(self, cfg: dict | None = None):
        super().__init__(name="music-knob", daemon=True)
        cfg = cfg or {}
        self._stop = threading.Event()
        self.sock_path = str(cfg.get("socket", "/tmp/mpv.sock"))
        self.step = int(cfg.get("step", 5))
        self.use_rel = bool(cfg.get("rel", False))
        self.axis = ecodes.ecodes.get(str(cfg.get("axis", "")), None)
        self.max_pct = int(cfg.get("max_percent", 100))
        self.last_abs = -1
        self.last_abs_t = 0.0
        self.sent = 0

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            while not self._stop.is_set():
                devs = self._find()
                if not devs:
                    time.sleep(3)
                    continue
                log.info("Musikknopf: lese %s", ", ".join(d.name for d in devs))
                self._loop(devs)
                for d in devs:
                    d.close()
        except Exception as exc:
            log.warning("Musikknopf beendet: %s", exc)

    def _find(self) -> list[evdev.InputDevice]:
        out = []
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                caps = d.capabilities()
                keys = caps.get(ecodes.EV_KEY, [])
                has_vol = ecodes.KEY_VOLUMEUP in keys or ecodes.KEY_VOLUMEDOWN in keys
                has_rel = self.use_rel and bool(REL_CODES & set(caps.get(ecodes.EV_REL, [])))
                has_abs = self.axis is not None and any(c == self.axis for c, _ in caps.get(ecodes.EV_ABS, []))
                if DEVICE_NAME in d.name and (has_vol or has_rel or has_abs):
                    out.append(d)
                else:
                    d.close()
            except Exception:
                pass
        return out

    def _loop(self, devs: list[evdev.InputDevice]) -> None:
        info = {}
        dec = RelDecoder("Musikknopf")
        for d in devs:
            for code, ai in d.capabilities(absinfo=True).get(ecodes.EV_ABS, []):
                if isinstance(ai, evdev.AbsInfo):
                    info[code] = ai
        while not self._stop.is_set():
            r, _, _ = select.select([d.fd for d in devs], [], [], 0.3)
            for d in devs:
                if d.fd not in r:
                    continue
                try:
                    for ev in d.read():
                        if ev.type == ecodes.EV_KEY and ev.value == 1:
                            if ev.code == ecodes.KEY_VOLUMEUP:
                                self.nudge(1)
                            elif ev.code == ecodes.KEY_VOLUMEDOWN:
                                self.nudge(-1)
                        elif ev.type == ecodes.EV_REL and ev.code in REL_CODES and self.use_rel:
                            n = dec.step(ev.value)
                            if n:
                                self.nudge(n)
                        elif ev.type == ecodes.EV_ABS and self.axis is not None and ev.code == self.axis:
                            ai = info.get(ev.code)
                            lo, hi = (ai.min, ai.max) if ai and ai.max > ai.min else (0, 255)
                            pct = int(round(min(1.0, max(0.0, (ev.value - lo) / float(hi - lo))) * self.max_pct))
                            now = time.monotonic()
                            if pct != self.last_abs and now - self.last_abs_t >= 0.1:
                                self.last_abs, self.last_abs_t = pct, now
                                self._send(["set_property", "volume", pct])
                except OSError:
                    return

    def nudge(self, steps: int) -> None:
        """Musik um steps x step Prozent lauter (>0) oder leiser (<0); auch von Tasten (keymap music_up/music_down)."""
        self._send(["add", "volume", self.step * steps])

    def _send(self, command: list) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(self.sock_path)
                s.sendall((json.dumps({"command": command}) + "\n").encode())
            self._log("mpv %s", command)
            return
        except OSError as exc:
            log.debug("mpv nicht erreichbar (%s): %s", self.sock_path, exc)
        # kein mpv: Musik kommt vom Handy -> ganzen Ausgang regeln
        try:
            if command[:2] == ["add", "volume"]:
                d = int(command[2])
                arg = f"{abs(d)}%{'+' if d > 0 else '-'}"
            else:
                arg = f"{int(command[2])}%"
            subprocess.run(["wpctl", "set-volume", "-l", f"{self.max_pct / 100.0:.2f}", "@DEFAULT_AUDIO_SINK@", arg],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            self._log("Ausgang (wpctl) %s", arg)
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as exc:
            log.warning("Musikknopf: weder mpv noch wpctl: %s", exc)

    def _log(self, fmt: str, *args) -> None:
        self.sent += 1
        (log.info if self.sent <= 20 or self.sent % 50 == 0 else log.debug)("Musikknopf: " + fmt, *args)
