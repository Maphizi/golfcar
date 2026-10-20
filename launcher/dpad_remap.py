"""D-Pad + Button Remapper: physische HID-Events -> echte Tastatur-Events via uinput.

- ABS_HAT0X/Y  (D-Pad)       -> KEY_LEFT/RIGHT/UP/DOWN
- code 266     (Startknopf)  -> KEY_ENTER  (universell: Auswahl, Losfliegen)
- code 267     (Kippschalter)-> KEY_F15 (Sprechtaste: HAL Mikrofon an/aus)
- Action "talk" (keymap.toml) -> KEY_F15 über inject_talk(): HAL schaltet Sprechmodus um
"""
from __future__ import annotations
import logging, select, threading, time
import evdev
from evdev import ecodes, UInput

log = logging.getLogger("dpad")

DEVICE_NAME = "PXN-CB1"

# Hat-Achsen -> Pfeiltasten
HAT_TO_KEY = {
    (ecodes.ABS_HAT0X, -1): ecodes.KEY_LEFT,
    (ecodes.ABS_HAT0X,  1): ecodes.KEY_RIGHT,
    (ecodes.ABS_HAT0Y, -1): ecodes.KEY_UP,
    (ecodes.ABS_HAT0Y,  1): ecodes.KEY_DOWN,
}

# Unbenannte Button-Codes -> Key (Kippschalter ist toggle, wird separat behandelt)
BTN_TO_KEY = {
    266: ecodes.KEY_ENTER,   # Startknopf
}

KIPPSCHALTER_CODE = 267
KIPP_KEY_AN  = ecodes.KEY_SPACE      # Kippschalter AN  -> Losfliegen
KIPP_KEY_AUS = ecodes.KEY_BACKSPACE  # Kippschalter AUS -> Stoppen

TALK_KEY = ecodes.KEY_F15            # Sprechtaste (Action "talk"): HAL 3000 Musik leise + Mikrofon an/aus

ALL_KEYS = list(HAT_TO_KEY.values()) + list(BTN_TO_KEY.values()) + [KIPP_KEY_AN, KIPP_KEY_AUS, TALK_KEY]


class DPadRemap(threading.Thread):
    def __init__(self):
        super().__init__(name="dpad-remap", daemon=True)
        self._stop = threading.Event()
        self._kipp_state = False  # False = AUS, True = AN
        self._ui = None

    def inject_talk(self) -> bool:
        """Sprechtaste an den laufenden Modus schicken (vom Launcher-Thread aufgerufen)."""
        ui = self._ui
        if ui is None:
            log.warning("Sprechtaste: uinput nicht bereit")
            return False
        self._inject(ui, TALK_KEY)
        return True

    def run(self) -> None:
        ui = UInput({ecodes.EV_KEY: ALL_KEYS}, name="GolfCar D-Pad")
        self._ui = ui
        log.info("D-Pad Remapper gestartet (uinput: %s)", ui.device)
        try:
            while not self._stop.is_set():
                dev = self._find_device()
                if dev is None:
                    time.sleep(2)
                    continue
                log.info("D-Pad Gerät gefunden: %s (%s)", dev.name, dev.path)
                self._loop(dev, ui)
                dev.close()
        finally:
            self._ui = None
            ui.close()

    def _find_device(self):
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                caps = d.capabilities()
                has_hat = any(
                    code in [ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y]
                    for code, _ in caps.get(ecodes.EV_ABS, [])
                )
                if DEVICE_NAME in d.name and has_hat:
                    return d
                d.close()
            except Exception:
                pass
        return None

    def _inject(self, ui, key: int) -> None:
        ui.write(ecodes.EV_KEY, key, 1)
        ui.write(ecodes.EV_KEY, key, 0)
        ui.syn()

    def _loop(self, dev, ui) -> None:
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([dev.fd], [], [], 0.5)
                if not r:
                    continue
                for ev in dev.read():
                    # D-Pad Achsen -> Pfeiltasten
                    if ev.type == ecodes.EV_ABS and ev.value != 0:
                        key = HAT_TO_KEY.get((ev.code, ev.value))
                        if key:
                            self._inject(ui, key)
                            log.debug("HAT -> %s", ecodes.KEY.get(key))

                    # Buttons (EV_KEY, nur Press = value 1)
                    elif ev.type == ecodes.EV_KEY and ev.value == 1:
                        if ev.code == KIPPSCHALTER_CODE:
                            # Sprechtaste: HAL Mikrofon an/aus (KEY_F15)
                            self._inject(ui, TALK_KEY)
                            log.info("Kippschalter -> TALK (KEY_F15)")
                        else:
                            key = BTN_TO_KEY.get(ev.code)
                            if key:
                                self._inject(ui, key)
                                log.debug("BTN %d -> %s", ev.code, ecodes.KEY.get(key))
            except OSError:
                break

    def stop(self) -> None:
        self._stop.set()
