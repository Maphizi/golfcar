"""D-Pad + Button Remapper: physische HID-Events -> echte Tastatur-Events via uinput.

- ABS_HAT0X/Y  (D-Pad)                -> KEY_LEFT/RIGHT/UP/DOWN
- Startknopf   ([buttons].start_code) -> KEY_ENTER   (universell: Auswahl, Losfliegen)
- Kippschalter ([buttons].kipp_code)  -> KEY_SPACE (AN) / KEY_BACKSPACE (AUS)
                                         kipp_mode = "toggle": jeder Druck wechselt AN/AUS
                                         kipp_mode = "state":  value 1 = AN, value 0 = AUS (echter Schalter)
- Sprechtaste  ([buttons].talk_code)  -> KEY_F15 (HAL 3000: Musik leise + Mikrofon an/aus); alternativ
                                         Action "talk" in keymap.toml -> inject_talk() vom Launcher
Die Codes stehen in config/settings.toml [buttons]; scripts/input_monitor.py zeigt, welche Taste
welchen Code sendet und ob eine Taste von selbst dauernd sendet. Wiederholte Ereignisse derselben
Taste innerhalb von debounce_ms werden verworfen (Prellen, periodisch sendende Schalter).
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

KIPP_KEY_AN  = ecodes.KEY_SPACE      # Kippschalter AN  -> Losfliegen / scharf
KIPP_KEY_AUS = ecodes.KEY_BACKSPACE  # Kippschalter AUS -> Stoppen
START_KEY = ecodes.KEY_ENTER
TALK_KEY       = ecodes.KEY_F15  # Sprechtaste: HAL 3000 Musik leise + Mikrofon an/aus
ATTRACT_KEY_ON  = ecodes.KEY_F16  # Autopilot-Schalter AN
ATTRACT_KEY_OFF = ecodes.KEY_F17  # Autopilot-Schalter AUS

ALL_KEYS = list(HAT_TO_KEY.values()) + [START_KEY, KIPP_KEY_AN, KIPP_KEY_AUS, TALK_KEY, ATTRACT_KEY_ON, ATTRACT_KEY_OFF]
DEFAULTS = {"start_code": 266, "kipp_code": 267, "kipp_mode": "toggle", "talk_code": 0, "attract_code": 0, "horn_code": 0,
            "horn2_code": 0, "debounce_ms": 300}


class DPadRemap(threading.Thread):
    def __init__(self, cfg: dict | None = None):
        super().__init__(name="dpad-remap", daemon=True)
        c = {**DEFAULTS, **(cfg or {})}
        self._stop = threading.Event()
        self._kipp_state = False  # False = AUS, True = AN
        self.last_event = time.monotonic()        # letzte Eingabe am Board (Vorführmodus des Launchers)
        self.on_attract = None                    # Launcher-Callback für den Autopilot-Schalter (das uinput-Gerät liest der Launcher nicht)
        self.on_horn    = None                    # Launcher-Callback für den Hupe-Schalter (Code 269): True = runter, False = hoch
        self.on_horn2   = None                    # zweite Seite des Hupen-Schalters ([buttons].horn2_code): True = gedrückt
        self._ui = None
        self.start_code = int(c["start_code"])
        self.kipp_code = int(c["kipp_code"])
        self.kipp_mode = str(c["kipp_mode"]).lower()
        self.talk_code    = int(c["talk_code"])
        self.attract_code = int(c["attract_code"])
        self.horn_code    = int(c["horn_code"])
        self.horn2_code   = int(c["horn2_code"])
        self.debounce = max(0.0, float(c["debounce_ms"]) / 1000.0)
        self._last_press: dict[int, float] = {}
        log.info("Tasten: Start=%d, Kippschalter=%d (%s), Sprechtaste=%s, Autopilot=%s, Hupe=%s, Entprellung %.0f ms",
                 self.start_code, self.kipp_code, self.kipp_mode, self.talk_code or "keine", self.attract_code or "keine", self.horn_code or "keine", self.debounce * 1000)

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

    def _debounced(self, code: int) -> bool:
        """True, wenn dieselbe Taste gerade erst kam (dann ignorieren)."""
        now = time.monotonic()
        last = self._last_press.get(code, 0.0)
        self._last_press[code] = now
        return now - last < self.debounce

    def _kipp(self, ui, on: bool) -> None:
        if on == self._kipp_state and self.kipp_mode == "state":
            return                                   # Schalter meldet denselben Zustand nochmal: nichts tun
        self._kipp_state = on
        key = KIPP_KEY_AN if on else KIPP_KEY_AUS
        self._inject(ui, key)
        log.info("Kippschalter %s -> %s", "AN" if on else "AUS", ecodes.KEY.get(key))

    def _loop(self, dev, ui) -> None:
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([dev.fd], [], [], 0.5)
                if not r:
                    continue
                for ev in dev.read():
                    if ev.type in (ecodes.EV_ABS, ecodes.EV_KEY) and ev.value != 0:
                        self.last_event = time.monotonic()
                    # D-Pad Achsen -> Pfeiltasten
                    if ev.type == ecodes.EV_ABS and ev.value != 0:
                        key = HAT_TO_KEY.get((ev.code, ev.value))
                        if key:
                            self._inject(ui, key)
                            log.debug("HAT -> %s", ecodes.KEY.get(key))
                        continue
                    if ev.type != ecodes.EV_KEY:
                        continue
                    # Kippschalter als echter Schalter: Zustand aus value (1 = unten/AN, 0 = oben/AUS)
                    if ev.code == self.kipp_code and self.kipp_mode == "state" and ev.value in (0, 1):
                        self._kipp(ui, ev.value == 1)
                        continue
                    # Autopilot-Schalter (echter Kippschalter, state): 1 = unten/AN, 0 = oben/AUS
                    if self.attract_code and ev.code == self.attract_code and ev.value in (0, 1):
                        key = ATTRACT_KEY_ON if ev.value == 1 else ATTRACT_KEY_OFF
                        self._inject(ui, key)                 # an den laufenden Modus: kurze Anzeige AUTOPILOT AN/AUS
                        if self.on_attract:
                            try:
                                self.on_attract(ev.value == 1)
                            except Exception:
                                log.exception("Autopilot-Schalter")
                        log.info("Autopilot-Schalter %s -> %s", "AN" if ev.value == 1 else "AUS", ecodes.KEY.get(key))
                        continue
                    # Hupe-Schalter (echter Kippschalter, state): 1 = unten/AN, 0 = oben/AUS
                    if self.horn_code and ev.code == self.horn_code and ev.value in (0, 1):
                        if self.on_horn:
                            try:
                                self.on_horn(ev.value == 1)
                            except Exception:
                                log.exception("Hupe-Schalter")
                        log.info("Hupe-Schalter %s", "AN" if ev.value == 1 else "AUS")
                        continue
                    # Hupe, zweite Seite (Schalter in die andere Richtung): 1 = gedrückt -> zweiter Ton
                    if self.horn2_code and ev.code == self.horn2_code and ev.value in (0, 1):
                        if self.on_horn2 and ev.value == 1:
                            try:
                                self.on_horn2(True)
                            except Exception:
                                log.exception("Hupe-Schalter 2")
                        log.info("Hupe-Schalter Seite 2 %s", "AN" if ev.value == 1 else "AUS")
                        continue
                    if ev.value != 1:                # nur Tastendruck, keine Repeats (2) oder Loslassen (0)
                        continue
                    if self._debounced(ev.code):
                        log.debug("Taste %d innerhalb der Entprellung ignoriert", ev.code)
                        continue
                    if ev.code == self.kipp_code:
                        self._kipp(ui, not self._kipp_state)
                    elif ev.code == self.start_code:
                        self._inject(ui, START_KEY)
                        log.info("Startknopf -> KEY_ENTER")
                    elif self.talk_code and ev.code == self.talk_code:
                        self._inject(ui, TALK_KEY)
                        log.info("Sprechtaste (%d) -> KEY_F15", ev.code)
            except OSError:
                break

    def stop(self) -> None:
        self._stop.set()
