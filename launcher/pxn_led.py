"""PXN-CB1 Buttonboard LED-Steuerung per HID Output Report.

Byte 0: 0x24 (Report ID), Byte 1: 0x20, Bytes 2-4: R,G,B.
Gerät: /dev/hidraw2 (PXN-CB1 Joystick-Interface, vendor=0x36e6).
"""
from __future__ import annotations
import logging, threading
from pathlib import Path

log = logging.getLogger("pxn_led")

# Basis-Paket aus USB-Capture (64 Bytes, unveränderliche Teile)
_BASE = bytes.fromhex(
    "2420" "000000" "080000" "00000000"
    "ff0000ff" "ff0000ff" "0000ffff" "0000ff00" "0000ff00"
) + b'\x00' * 32

# Farben pro Modus (R, G, B)
MODE_COLORS: dict[str, tuple[int,int,int]] = {
    "home":             (255, 190,  60),  # Taxi-Gold
    "boot":             (255,   0,   0),  # KITT-Rot
    "gaming":           (  0, 200, 255),  # Arcade-Cyan
    "viz_psychedelic":  (  0, 100, 255),  # Weltraum-Blau
    "viz_crt":          (  0, 255,  60),  # Phosphor-Grün
    "viz_eye":          (160,   0, 255),  # Violett
    "kitt":             (255,   0,   0),  # KITT-Rot
    "campfire":         (255,  70,   0),  # Feuer-Orange
    "news":             ( 30, 110, 255),  # Studio-Blau
    "droid":            (255, 100,   0),  # BIBO-Orange
    "slots":            (255, 210,   0),  # Casino-Gold
    "error":            (255,   0,   0),  # Alarm-Rot (blinkt)
    "blackhole":        ( 80,   0, 200),  # Kosmisch-Violett
    "hal":              (255,  15,   5),  # HAL-Rot
    "menu":             (255, 255, 255),  # Weiß
}

_lock = threading.Lock()
_dev: str | None = None


def _find_device() -> str | None:
    """hidraw-Gerät des PXN-CB1 (vendor 0x36e6) finden."""
    import fcntl, struct, array
    HIDIOCGRAWINFO = 0x80084803
    for i in range(8):
        path = f"/dev/hidraw{i}"
        try:
            with open(path, 'rb+') as f:
                buf = array.array('B', [0] * 8)
                fcntl.ioctl(f, HIDIOCGRAWINFO, buf)
                _, vendor, _ = struct.unpack('IHH', bytes(buf))
                if vendor == 0x36e6:
                    # Joystick-Interface (größerer Descriptor) bevorzugen
                    desc_size = _get_desc_size(f)
                    if desc_size > 60:
                        return path
        except Exception:
            pass
    return None


def _get_desc_size(f) -> int:
    import fcntl, struct, array
    HIDIOCGRDESCSIZE = 0x80044801
    buf = array.array('B', [0] * 4)
    try:
        fcntl.ioctl(f, HIDIOCGRDESCSIZE, buf)
        return struct.unpack('I', bytes(buf))[0]
    except Exception:
        return 0


def set_color(r: int, g: int, b: int) -> bool:
    """Buttonboard-Farbe setzen. Gibt True zurück wenn erfolgreich."""
    global _dev
    with _lock:
        if _dev is None:
            _dev = _find_device()
        if _dev is None:
            log.debug("PXN-CB1 hidraw nicht gefunden")
            return False
        try:
            pkt = _BASE[:2] + bytes([r, g, b]) + _BASE[5:]
            with open(_dev, 'rb+') as f:
                f.write(pkt)
            log.debug("PXN LED: RGB(%d,%d,%d)", r, g, b)
            return True
        except Exception as exc:
            log.warning("PXN LED Fehler: %s", exc)
            _dev = None
            return False


def apply_mode(mode: str) -> bool:
    """Farbe für den gegebenen Modus setzen."""
    col = MODE_COLORS.get(mode)
    if col is None:
        log.debug("Kein PXN-Farbprofil für Modus '%s'", mode)
        return False
    return set_color(*col)


def apply_mode_async(mode: str) -> None:
    threading.Thread(target=apply_mode, args=(mode,), daemon=True, name=f"pxn-led-{mode}").start()
