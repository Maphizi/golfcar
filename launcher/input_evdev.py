"""Tastatur- und HID-Eingabe über evdev (funktioniert unter Wayland, X11 und Konsole).

Liest alle Geräte, die Tasten liefern, ohne sie exklusiv zu greifen. Die
laufende Anwendung (Emulator, Visualizer) sieht die Tasten also weiterhin.
Neue Geräte (z. B. eine später eingesteckte USB-Buttonbox) werden beim
periodischen Rescan automatisch aufgenommen.

Mapping Keycode -> Action kommt aus config/keymap.toml.
Unterstützt auch:
  - Numerische Codes (key = 266) für unbenannte HID-Tasten
  - Hat-Switch-Achsen (hat_bindings) für D-Pad/Joystick
"""
from __future__ import annotations

import fnmatch
import logging
import select
import threading
import time
from queue import Queue

import evdev
from evdev import ecodes

from .actions import Action, parse_action

log = logging.getLogger("input.evdev")

# Hat-Switch-Achse + Richtungswert -> Action
HatKey = tuple[int, int]  # (axis_code, value)


class EvdevInput(threading.Thread):
    def __init__(self, keymap_cfg: dict, queue: Queue, rescan_interval: float = 3.0):
        super().__init__(name="evdev-input", daemon=True)
        self.queue = queue
        self.rescan_interval = rescan_interval
        self._stop_event = threading.Event()
        self._devices: dict[str, evdev.InputDevice] = {}
        self.device_patterns: list[str] = keymap_cfg.get("devices", {}).get("include", ["*"])
        self.device_excludes: list[str] = keymap_cfg.get("devices", {}).get("exclude", [])

        # EV_KEY-Bindings (name oder numerischer code)
        self.bindings: dict[int, Action] = {}
        for b in keymap_cfg.get("bindings", []):
            action = parse_action(b.get("action", ""))
            if action is None:
                log.warning("Ungültige Action ignoriert: %s", b)
                continue
            # Numerischer Code direkt
            if "code" in b:
                code = int(b["code"])
            else:
                code = ecodes.ecodes.get(b.get("key", ""))
            if code is None:
                log.warning("Ungültiger Key ignoriert: %s", b)
                continue
            self.bindings[code] = action

        # Hat-Switch-Bindings (D-Pad Achsen)
        self.hat_bindings: dict[HatKey, Action] = {}
        for h in keymap_cfg.get("hat_bindings", []):
            axis_name = h.get("axis", "")
            value = int(h.get("value", 0))
            action = parse_action(h.get("action", ""))
            axis_code = ecodes.ecodes.get(axis_name)
            if axis_code is None or action is None or value == 0:
                log.warning("Ungültiges Hat-Binding ignoriert: %s", h)
                continue
            self.hat_bindings[(axis_code, value)] = action

        log.info("Key-Bindings: %s", {
            (ecodes.KEY.get(c) or ecodes.BTN.get(c) or str(c)): a.value
            for c, a in self.bindings.items()
        })
        log.info("Hat-Bindings: %s", {
            f"{ecodes.ABS.get(ax,'?')}={v}": a.value
            for (ax, v), a in self.hat_bindings.items()
        })

    # -- Geräte ----------------------------------------------------------
    def _wanted(self, dev: evdev.InputDevice) -> bool:
        caps = dev.capabilities()
        has_wanted_key = bool(
            self.bindings and
            any(code in caps.get(ecodes.EV_KEY, []) for code in self.bindings)
        )
        has_wanted_hat = bool(
            self.hat_bindings and
            any(
                any(ax == code for (ax, _) in self.hat_bindings)
                for code, _ in caps.get(ecodes.EV_ABS, [])
            )
        )
        if not (has_wanted_key or has_wanted_hat):
            return False
        if any(fnmatch.fnmatch(dev.name, pat) for pat in self.device_excludes):
            return False
        return any(fnmatch.fnmatch(dev.name, pat) for pat in self.device_patterns)

    def _rescan(self) -> None:
        current = set(evdev.list_devices())
        for path in list(self._devices):
            if path not in current:
                log.info("Gerät entfernt: %s", self._devices[path].name)
                try:
                    self._devices[path].close()
                except Exception:
                    pass
                del self._devices[path]
        for path in current:
            if path in self._devices:
                continue
            try:
                dev = evdev.InputDevice(path)
                if self._wanted(dev):
                    self._devices[path] = dev
                    log.info("Gerät aktiv: %s (%s)", dev.name, path)
                else:
                    dev.close()
            except (OSError, PermissionError) as exc:
                log.debug("Gerät %s nicht lesbar: %s", path, exc)

    # -- Loop ------------------------------------------------------------
    def run(self) -> None:
        last_scan = 0.0
        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - last_scan >= self.rescan_interval:
                self._rescan()
                last_scan = now
            if not self._devices:
                time.sleep(0.5)
                continue
            fds = {d.fd: d for d in self._devices.values()}
            try:
                ready, _, _ = select.select(list(fds), [], [], 0.5)
            except (OSError, ValueError):
                self._devices.clear()
                continue
            for fd in ready:
                dev = fds[fd]
                try:
                    for ev in dev.read():
                        self._on_event(ev, dev)
                except OSError:
                    log.info("Gerät weg: %s", dev.name)
                    self._devices = {p: d for p, d in self._devices.items() if d is not dev}

    def _on_event(self, ev, dev) -> None:
        # EV_KEY: nur Tastendruck (value=1), keine Repeats (value=2)
        if ev.type == ecodes.EV_KEY and ev.value == 1:
            action = self.bindings.get(ev.code)
            if action is not None:
                log.debug("KEY %s -> %s (%s)", ev.code, action.value, dev.name)
                self.queue.put(action)

        # EV_ABS: Hat-Switch D-Pad (ignoriere value=0 = losgelassen)
        elif ev.type == ecodes.EV_ABS and ev.value != 0:
            action = self.hat_bindings.get((ev.code, ev.value))
            if action is not None:
                aname = ecodes.ABS.get(ev.code, ev.code)
                log.debug("HAT %s=%d -> %s (%s)", aname, ev.value, action.value, dev.name)
                self.queue.put(action)

    def stop(self) -> None:
        self._stop_event.set()
