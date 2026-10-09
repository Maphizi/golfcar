"""Tastatur- und HID-Eingabe über evdev (funktioniert unter Wayland, X11 und Konsole).

Liest alle Geräte, die Tasten liefern, ohne sie exklusiv zu greifen. Die
laufende Anwendung (Emulator, Visualizer) sieht die Tasten also weiterhin.
Neue Geräte (z. B. eine später eingesteckte USB-Buttonbox) werden beim
periodischen Rescan automatisch aufgenommen.

Mapping Keycode -> Action kommt aus config/keymap.toml.
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


class EvdevInput(threading.Thread):
    def __init__(self, keymap_cfg: dict, queue: Queue, rescan_interval: float = 3.0):
        super().__init__(name="evdev-input", daemon=True)
        self.queue = queue
        self.rescan_interval = rescan_interval
        self._stop_event = threading.Event()
        self._devices: dict[str, evdev.InputDevice] = {}
        self.device_patterns: list[str] = keymap_cfg.get("devices", {}).get("include", ["*"])
        self.device_excludes: list[str] = keymap_cfg.get("devices", {}).get("exclude", [])
        self.bindings: dict[int, Action] = {}
        for b in keymap_cfg.get("bindings", []):
            code = ecodes.ecodes.get(b["key"])
            action = parse_action(b["action"])
            if code is None or action is None:
                log.warning("Ungültiges Binding ignoriert: %s", b)
                continue
            self.bindings[code] = action
        log.info("Bindings: %s", {(ecodes.KEY.get(c) or ecodes.BTN.get(c) or str(c)): a.value for c, a in self.bindings.items()})

    # -- Geräte ----------------------------------------------------------
    def _wanted(self, dev: evdev.InputDevice) -> bool:
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if not caps:
            return False
        # Nur Geräte, die mindestens eine der gebundenen Tasten liefern können
        if not any(code in caps for code in self.bindings):
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
        if ev.type != ecodes.EV_KEY or ev.value != 1:  # nur Tastendruck, keine Repeats
            return
        action = self.bindings.get(ev.code)
        if action is not None:
            log.debug("%s -> %s (%s)", ecodes.KEY.get(ev.code, ev.code), action.value, dev.name)
            self.queue.put(action)

    def stop(self) -> None:
        self._stop_event.set()
