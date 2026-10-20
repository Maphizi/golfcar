"""WLED-Integration: das LED-Buttonboard (Dig_Next_2) wechselt mit dem Modus.

Beim Moduswechsel schickt der Launcher das Profil aus config/wled.toml [modes.<modus>] per HTTP-API an
den Controller. Modi können zusätzlich Ereignis-Profile schicken (z. B. "slots_jackpot", "hal_alien",
"blackhole_eject"); dafür apply_mode_async() aus dem Modusprozess heraus. Fehler werden geloggt, aber
nie nach oben weitergegeben: die LEDs dürfen nichts blockieren.

Profil-Schlüssel: bri 0-255, fx Effekt-ID, col [R,G,B], col2/col3 Zweit-/Drittfarbe, sx Geschwindigkeit,
ix Intensität, pal Palette-ID (optional). col kann beim Aufruf überschrieben werden (Themenfarbe).
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import urllib.request
from typing import Any

log = logging.getLogger("wled")

_cfg: dict | None = None   # geladen beim ersten Aufruf


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


def _rgb(v: Any, default: list[int]) -> list[int]:
    try:
        return [max(0, min(255, int(c))) for c in list(v)[:3]] if v is not None else default
    except (TypeError, ValueError):
        return default


def payload_for(profile: dict[str, Any], col: list[int] | None = None) -> dict:
    """JSON-Zustand für ein Profil; col überschreibt die Hauptfarbe (z. B. Themenfarbe)."""
    c1 = _rgb(col, _rgb(profile.get("col"), [255, 255, 255]))
    c2 = _rgb(profile.get("col2"), [0, 0, 0])
    c3 = _rgb(profile.get("col3"), [0, 0, 0])
    seg: dict[str, Any] = {
        "id":  0,
        "fx":  int(profile.get("fx", 0)),
        "sx":  int(profile.get("sx", 128)),
        "ix":  int(profile.get("ix", 128)),
        "col": [c1, c2, c3],
    }
    if "pal" in profile:
        seg["pal"] = int(profile["pal"])
    return {"on": True, "bri": int(profile.get("bri", 128)), "seg": [seg]}


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
    payload = payload_for(mode_cfg, col)
    return send(payload, f"'{mode}' -> fx={payload['seg'][0]['fx']} bri={payload['bri']} col={payload['seg'][0]['col'][0]}")


def apply_mode_async(mode: str, col: list[int] | None = None) -> None:
    """Wie apply_mode, aber im Hintergrund (für Modusprozesse, die nicht auf HTTP warten sollen)."""
    threading.Thread(target=apply_mode, args=(mode, col), name=f"wled-{mode}", daemon=True).start()
