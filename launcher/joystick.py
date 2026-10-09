"""Joystick-zu-Tastatur-Bridge für den PXN-CB1 Steuerknüppel.

Der Joystick sendet REL_MISC-Events kontinuierlich solange er gehalten wird.
Die Bridge feuert KEY_LEFT / KEY_RIGHT genau einmal pro Geste — wenn der
Stick losgelassen wird (150ms Stille nach letztem Event).

Positiver Wert  → KEY_RIGHT
Negativer Wert  → KEY_LEFT

Zusätzlicher Throttle: min. 400ms zwischen zwei Aktionen.
"""
from __future__ import annotations

import logging
import select
import threading
import time

import evdev
from evdev import UInput, ecodes as ec

log = logging.getLogger("joystick")

REL_MISC   = ec.REL_MISC   # = 9
THROTTLE_S = 0.4            # Mindestpause zwischen zwei Aktionen
SILENCE_S  = 0.15           # Pause nach letztem Event = "Stick losgelassen"


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
        devices: list[evdev.InputDevice] = []
        for attempt in range(30):
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

        ui = UInput(
            {ec.EV_KEY: [ec.KEY_LEFT, ec.KEY_RIGHT, ec.KEY_UP, ec.KEY_DOWN]},
            name="KITT Joystick Bridge",
        )
        log.info("JoystickBridge aktiv: %d PXN-Gerät(e)", len(devices))

        last_inject  = 0.0
        last_event_t = 0.0   # Zeitpunkt des letzten REL_MISC-Events
        pending_key  = None  # Richtung, die beim Loslassen gefeuert wird

        while not self._stop.is_set():
            r, _, _ = select.select(devices, [], [], 0.05)
            now = time.monotonic()

            # Events lesen und Richtung merken
            for dev in r:
                try:
                    for ev in dev.read():
                        if ev.type != ec.EV_REL or ev.code != REL_MISC:
                            continue
                        if ev.value == 0:
                            continue
                        last_event_t = now
                        # Richtung beim ersten Event der Geste merken
                        if pending_key is None and now - last_inject >= THROTTLE_S:
                            pending_key = ec.KEY_RIGHT if ev.value > 0 else ec.KEY_LEFT
                except OSError:
                    pass

            # Key feuern wenn Stick losgelassen (SILENCE_S Pause)
            if pending_key is not None and now - last_event_t >= SILENCE_S:
                ui.write(ec.EV_KEY, pending_key, 1)
                ui.syn()
                time.sleep(0.02)
                ui.write(ec.EV_KEY, pending_key, 0)
                ui.syn()
                log.debug(
                    "Joystick → %s",
                    "KEY_RIGHT" if pending_key == ec.KEY_RIGHT else "KEY_LEFT",
                )
                last_inject = now
                pending_key = None

        ui.close()
        log.info("JoystickBridge gestoppt")
