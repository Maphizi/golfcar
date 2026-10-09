"""Joystick-zu-Tastatur-Bridge für den PXN-CB1 Steuerknüppel.

Der Joystick sendet REL_MISC-Events. Dieses Modul liest sie und
injiziert KEY_LEFT / KEY_RIGHT über ein virtuelles uinput-Gerät,
damit alle laufenden Anwendungen (pygame, evdev-Launcher) sie sehen.

Positiver Wert  → KEY_RIGHT
Negativer Wert  → KEY_LEFT
Null            → ignoriert

Throttle: max. 8 Ereignisse/Sekunde (125 ms Mindestabstand).
"""
from __future__ import annotations

import logging
import select
import threading
import time

import evdev
from evdev import UInput, ecodes as ec

log = logging.getLogger("joystick")

REL_MISC = ec.REL_MISC   # = 9
THROTTLE_S = 0.125        # 8 Hz max


class JoystickBridge(threading.Thread):
    """Läuft als Daemon-Thread neben dem Launcher."""

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
        # Warte bis ein PXN-Gerät vorhanden ist
        devices: list[evdev.InputDevice] = []
        for attempt in range(30):          # max 15 s warten
            devices = [
                evdev.InputDevice(p)
                for p in evdev.list_devices()
                if "PXN" in evdev.InputDevice(p).name
            ]
            if devices:
                break
            time.sleep(0.5)

        if not devices:
            log.warning("Kein PXN-Gerät gefunden, Joystick-Bridge inaktiv")
            return

        # Virtuelles Tastatur-Gerät für die Ausgabe
        ui = UInput(
            {ec.EV_KEY: [ec.KEY_LEFT, ec.KEY_RIGHT, ec.KEY_UP, ec.KEY_DOWN]},
            name="KITT Joystick Bridge",
        )
        log.info("JoystickBridge aktiv: %d PXN-Gerät(e)", len(devices))

        last_inject = 0.0

        while not self._stop.is_set():
            r, _, _ = select.select(devices, [], [], 0.2)
            for dev in r:
                try:
                    for ev in dev.read():
                        if ev.type != ec.EV_REL or ev.code != REL_MISC:
                            continue
                        if ev.value == 0:
                            continue
                        now = time.monotonic()
                        if now - last_inject < THROTTLE_S:
                            continue
                        last_inject = now
                        key = ec.KEY_RIGHT if ev.value > 0 else ec.KEY_LEFT
                        ui.write(ec.EV_KEY, key, 1)
                        ui.syn()
                        time.sleep(0.02)
                        ui.write(ec.EV_KEY, key, 0)
                        ui.syn()
                        log.debug(
                            "Joystick REL_MISC=%d → %s",
                            ev.value,
                            "KEY_RIGHT" if key == ec.KEY_RIGHT else "KEY_LEFT",
                        )
                except OSError:
                    pass

        ui.close()
        log.info("JoystickBridge gestoppt")
