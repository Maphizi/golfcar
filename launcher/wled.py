"""WLED-Integration: das LED-Buttonboard (Dig_Next_2) wechselt mit dem Modus.

Beim Moduswechsel schickt der Launcher das Profil aus config/wled.toml [modes.<modus>] per HTTP-API an
den Controller. Modi können zusätzlich Ereignis-Profile schicken (z. B. "slots_jackpot", "hal_alien",
"blackhole_eject"); dafür apply_mode_async() aus dem Modusprozess heraus. Fehler werden geloggt, aber
nie nach oben weitergegeben: die LEDs dürfen nichts blockieren.

Profil-Schlüssel: bri 0-255, fx Effekt-ID, col [R,G,B], col2/col3 Zweit-/Drittfarbe, sx Geschwindigkeit,
ix Intensität, pal Palette-ID (optional). col kann beim Aufruf überschrieben werden (Themenfarbe).
"""
from __future__ import annotations

from pathlib import Path

import json
import logging
import socket
import threading
import urllib.request
from typing import Any

log = logging.getLogger("wled")

_cfg: dict | None = None   # geladen beim ersten Aufruf
_stream_hook = None        # LedStream der laufenden Szene: Ereignis-Profile werden auch dort gespielt


def set_stream_hook(fn) -> None:
    global _stream_hook
    _stream_hook = fn


BRIGHT_FILE = Path(__file__).resolve().parents[1] / "logs" / "led_brightness.txt"
_bright_cache: tuple[float, float] = (-1.0, 1.0)                  # (mtime, Faktor)


def knob_factor() -> float:
    """Faktor des Helligkeitsknopfs (launcher/led_knob.py -> logs/led_brightness.txt), 1.0 ohne Datei; nach mtime gecacht,
    darf je Bild aufgerufen werden."""
    global _bright_cache
    try:
        mtime = BRIGHT_FILE.stat().st_mtime
    except OSError:
        return 1.0
    if mtime != _bright_cache[0]:
        try:
            _bright_cache = (mtime, max(0.0, min(2.0, float(BRIGHT_FILE.read_text().strip()))))
        except (OSError, ValueError):
            _bright_cache = (mtime, 1.0)
    return _bright_cache[1]


def dim() -> float:
    """Gesamtdämpfung aller Profile ([controller].dim, 0.7 = 30 % leiser) mal Helligkeitsknopf, höchstens 1.0."""
    try:
        base = max(0.0, min(1.0, float(_load_cfg().get("controller", {}).get("dim", 1.0))))
    except (TypeError, ValueError):
        base = 1.0
    return max(0.0, min(1.0, base * knob_factor()))


def _load_cfg() -> dict:
    global _cfg
    if _cfg is not None:
        return _cfg
    try:
        from . import config as lcfg
        raw = lcfg._load("wled.toml")
    except Exception as exc:
        log.warning("wled.toml nicht lesbar: %s", exc)
        raw = {}
    _cfg = raw
    return _cfg


def _controller() -> tuple[str, int, int] | None:
    ctrl = _load_cfg().get("controller", {})
    if not ctrl.get("enabled", True):
        return None
    host = ctrl.get("host", "")
    if not host:
        return None
    return host, int(ctrl.get("port", 80)), int(ctrl.get("timeout", 2))


def _post(host: str, port: int, timeout: int, payload: dict) -> None:
    url  = f"http://{host}:{port}/json/state"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


_info: dict | None = None  # /json/info (LED-Anzahl), höchstens alle INFO_TTL s neu
_info_at = 0.0
INFO_TTL = 60.0
_extra_segs: list[int] | None = None   # Segment-IDs > 0 beim ersten Senden (werden gelöscht)


def _get(host: str, port: int, timeout: int, path: str) -> dict:
    with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def led_count() -> int:
    """LED-Anzahl des Controllers (0 = unbekannt); [controller].leds überstimmt die Abfrage."""
    global _info
    ctrl = _controller()
    if ctrl is None:
        return 0
    n = int(_load_cfg().get("controller", {}).get("leds", 0) or 0)
    if n > 0:
        return n
    global _info_at
    import time
    if _info is None or time.monotonic() - _info_at > INFO_TTL:   # LED-Anzahl kann sich ändern (wled_setup.py)
        try:
            _info = _get(ctrl[0], ctrl[1], ctrl[2], "/json/info")
        except Exception as exc:
            log.debug("WLED /json/info: %s", exc)
            _info = _info or {}
        _info_at = time.monotonic()
    try:
        return int(_info.get("leds", {}).get("count", 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def _cleanup_segments() -> list[dict]:
    """Zusätzliche Segmente (id > 0) löschen: sie liefen sonst mit eigenem Effekt und eigener Farbe weiter."""
    global _extra_segs
    ctrl = _controller()
    if ctrl is None:
        return []
    if _extra_segs is None:
        try:
            st = _get(ctrl[0], ctrl[1], ctrl[2], "/json/state")
            _extra_segs = [int(sg.get("id", i)) for i, sg in enumerate(st.get("seg", [])) if int(sg.get("id", i)) > 0]
            if _extra_segs:
                log.info("WLED: lösche Segmente %s (nur Segment 0 wird gesteuert)", _extra_segs)
        except Exception as exc:
            log.debug("WLED /json/state: %s", exc)
            _extra_segs = []
    segs = [{"id": i, "stop": 0} for i in _extra_segs]
    _extra_segs = []
    return segs


def _rgb(v: Any, default: list[int]) -> list[int]:
    try:
        return [max(0, min(255, int(c))) for c in list(v)[:3]] if v is not None else default
    except (TypeError, ValueError):
        return default


def _col_remap(rgb: list[int]) -> list[int]:
    """Kanal-Remap für Strip mit Drahtfolge W,R,G,B: [R,G,B] → [R,W=0,G,B] als 4-Kanal-Col."""
    remap = _load_cfg().get("controller", {}).get("col_remap", None)
    if remap is None:
        return rgb  # kein Remap konfiguriert
    src = list(rgb) + [0] * (4 - len(rgb))   # auf 4 Kanäle auffüllen (W=0)
    try:
        return [src[i] for i in remap]
    except (IndexError, TypeError):
        return rgb


def payload_for(profile: dict[str, Any], col: list[int] | None = None) -> dict:
    """JSON-Zustand für ein Profil; col überschreibt die Hauptfarbe (z. B. Themenfarbe)."""
    c1 = _col_remap(_rgb(col, _rgb(profile.get("col"), [255, 255, 255])))
    c2 = _col_remap(_rgb(profile.get("col2"), [0, 0, 0]))
    c3 = _col_remap(_rgb(profile.get("col3"), [0, 0, 0]))
    seg: dict[str, Any] = {
        "id":  0, "start": 0, "grp": 1, "spc": 0, "of": 0, "on": True, "bri": 255, "frz": False, "sel": True,
        "rev": False, "mi": False,
        "fx":  int(profile.get("fx", 0)),
        "sx":  int(profile.get("sx", 128)),
        "ix":  int(profile.get("ix", 128)),
        "col": [c1, c2, c3],
        # Palette immer setzen: sonst bleibt die letzte (z. B. Regenbogen) und viele Effekte malen damit statt mit col
        "pal": int(profile.get("pal", 3 if "col2" in profile else 2)),
    }
    n = led_count()
    if n > 0:
        seg["stop"] = n
    return {"on": True, "bri": max(1, int(int(profile.get("bri", 128)) * dim())), "transition": 2,
            "pl": -1, "lor": 0, "nl": {"on": False}, "seg": [seg] + _cleanup_segments()}


def profiles() -> dict[str, dict]:
    return dict(_load_cfg().get("modes", {}))


def send(payload: dict, what: str = "") -> bool:
    ctrl = _controller()
    if ctrl is None:
        return False
    host, port, timeout = ctrl
    try:
        _post(host, port, timeout, payload)
        if what:
            log.info("WLED: %s", what)
        return True
    except (OSError, socket.timeout, Exception) as exc:
        log.warning("WLED nicht erreichbar (%s): %s", host, exc)
        return False


def apply_mode(mode: str, col: list[int] | None = None) -> bool:
    """Profil für den Modus (oder ein Ereignis wie 'slots_jackpot') an den Controller senden."""
    mode_cfg: dict[str, Any] = profiles().get(mode, {})
    if not mode_cfg:
        log.debug("Kein WLED-Profil für '%s', übersprungen", mode)
        return False
    if _stream_hook is not None:
        try:
            _stream_hook(mode, mode_cfg)
        except Exception:
            log.exception("LED-Stream-Ereignis %s", mode)
    payload = payload_for(mode_cfg, col)
    return send(payload, f"'{mode}' -> fx={payload['seg'][0]['fx']} bri={payload['bri']} col={payload['seg'][0]['col'][0]}")


def apply_mode_async(mode: str, col: list[int] | None = None) -> None:
    """Wie apply_mode, aber im Hintergrund (für Modusprozesse, die nicht auf HTTP warten sollen)."""
    threading.Thread(target=apply_mode, args=(mode, col), name=f"wled-{mode}", daemon=True).start()
