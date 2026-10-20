"""Joystick-zu-Tastatur-Bridge für den PXN-CB1.

REL_MISC-Joystick  → KEY_LEFT / KEY_RIGHT  (Flanken-Erkennung, 1× pro Geste)

Kippschalter (267) und Startknopf (266) werden von DPadRemap behandelt.
"""
from __future__ import annotations

import logging
import select
import threading
import time

import evdev
from evdev import UInput, ecodes as ec

log = logging.getLogger("joystick")

REL_MISC   = ec.REL_MISC   # 9
THROTTLE_S = 0.4
SILENCE_S  = 0.15


class JoystickBridge(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="joystick-bridge", daemon=True)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:
            log.warning("JoystickBridge beendet: %s", exc)

    def _loop(self) -> None:
        devices: list[evdev.InputDevice] = []
        for _ in range(30):
            devices = [
                evdev.InputDevice(p)
                for p in evdev.list_devices()
                if "PXN" in evdev.InputDevice(p).name
            ]
            if devices:
                break
            time.sleep(0.5)

        if not devices:
            log.warning("Kein PXN-Gerät gefunden, Bridge inaktiv")
            return

        # Nur Geräte mit REL_MISC (Joystick-Achse)
        devices = [d for d in devices if ec.REL_MISC in d.capabilities().get(ec.EV_REL, [])]
        if not devices:
            log.warning("Kein PXN-Gerät mit REL_MISC gefunden, Bridge inaktiv")
            for d in devices:
                d.close()
            return

        ui = UInput(
            {ec.EV_KEY: [ec.KEY_LEFT, ec.KEY_RIGHT, ec.KEY_UP, ec.KEY_DOWN]},
            name="KITT Joystick Bridge",
        )
        log.info("JoystickBridge aktiv: %d PXN-Gerät(e) mit Joystick", len(devices))

        last_inject  = 0.0
        last_event_t = 0.0
        pending_key  = None

        def inject(key: int) -> None:
            ui.write(ec.EV_KEY, key, 1); ui.syn()
            time.sleep(0.02)
            ui.write(ec.EV_KEY, key, 0); ui.syn()

        while not self._stop.is_set():
            r, _, _ = select.select(devices, [], [], 0.05)
            now = time.monotonic()

            for dev in r:
                try:
                    for ev in dev.read():
                        if ev.type == ec.EV_REL and ev.code == REL_MISC:
                            if ev.value == 0:
                                continue
                            last_event_t = now
                            if pending_key is None and now - last_inject >= THROTTLE_S:
                                pending_key = ec.KEY_RIGHT if ev.value > 0 else ec.KEY_LEFT
                except OSError:
                    pass

            if pending_key is not None and now - last_event_t >= SILENCE_S:
                inject(pending_key)
                log.debug("Joystick → %s", "KEY_RIGHT" if pending_key == ec.KEY_RIGHT else "KEY_LEFT")
                last_inject = now
                pending_key = None

        ui.close()
        log.info("JoystickBridge gestoppt")
