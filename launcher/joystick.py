"""Joystick-zu-Tastatur-Bridge für den PXN-CB1.

REL_MISC-Joystick  → KEY_LEFT / KEY_RIGHT  (Flanken-Erkennung, 1× pro Geste)
BTN_TR  (code 267) → KEY_F13               (Kippschalter: Arm/Disarm toggle)
BTN_1   (code 257) → KEY_F14               (Startknopf: Launch wenn armed)
"""
from __future__ import annotations

import logging
import select
import threading
import time

import evdev
from evdev import UInput, ecodes as ec

log = logging.getLogger("joystick")

REL_MISC     = ec.REL_MISC   # 9
BTN_TR       = 267            # Kippschalter
BTN_START_HW = 257            # Startknopf (BTN_1)
THROTTLE_S   = 0.4
SILENCE_S    = 0.15


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

        ui = UInput(
            {ec.EV_KEY: [ec.KEY_LEFT, ec.KEY_RIGHT,
                           ec.KEY_UP, ec.KEY_DOWN,
                           ec.KEY_F13, ec.KEY_F14]},
            name="KITT Joystick Bridge",
        )
        log.info("JoystickBridge aktiv: %d PXN-Gerät(e)", len(devices))

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
                        # ── Kippschalter & Startknopf ────────────────
                        if ev.type == ec.EV_KEY and ev.value == 1:
                            if ev.code == BTN_TR:
                                inject(ec.KEY_F13)
                                log.debug("Kippschalter → KEY_F13")
                            elif ev.code == BTN_START_HW:
                                inject(ec.KEY_F14)
                                log.debug("Startknopf → KEY_F14")

                        # ── Joystick Links/Rechts ─────────────────────
                        elif ev.type == ec.EV_REL and ev.code == REL_MISC:
                            if ev.value == 0:
                                continue
                            last_event_t = now
                            if pending_key is None and now - last_inject >= THROTTLE_S:
                                pending_key = ec.KEY_RIGHT if ev.value > 0 else ec.KEY_LEFT
                except OSError:
                    pass

            # Joystick-Key feuern wenn Stick losgelassen
            if pending_key is not None and now - last_event_t >= SILENCE_S:
                inject(pending_key)
                log.debug("Joystick → %s", "KEY_RIGHT" if pending_key == ec.KEY_RIGHT else "KEY_LEFT")
                last_inject = now
                pending_key = None

        ui.close()
        log.info("JoystickBridge gestoppt")
