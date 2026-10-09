"""WLED-Integration für den KITT-Cart Launcher.

Beim Moduswechsel wird der LED-Controller (Dig_Next_2) per HTTP-API
auf den passenden Effekt umgeschaltet. Fehler werden geloggt aber nie
nach oben weitergegeben – die LEDs dürfen den Launcher nie blockieren.
"""
from __future__ import annotations

import json
import logging
import socket
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


def apply_mode(mode: str) -> None:
    """Effekt für den gegebenen Modus an den Controller senden."""
    cfg = _load_cfg()
    ctrl = cfg.get("controller", {})
    if not ctrl.get("enabled", True):
        return

    host    = ctrl.get("host", "")
    port    = int(ctrl.get("port", 80))
    timeout = int(ctrl.get("timeout", 2))

    if not host:
        return

    mode_cfg: dict[str, Any] = cfg.get("modes", {}).get(mode, {})
    if not mode_cfg:
        log.debug("Kein WLED-Profil für Modus '%s', übersprungen", mode)
        return

    bri = int(mode_cfg.get("bri", 128))
    fx  = int(mode_cfg.get("fx",  0))
    sx  = int(mode_cfg.get("sx",  128))
    ix  = int(mode_cfg.get("ix",  128))
    col = mode_cfg.get("col", [255, 255, 255])

    payload = {
        "on":  True,
        "bri": bri,
        "seg": [{
            "id":  0,
            "fx":  fx,
            "sx":  sx,
            "ix":  ix,
            "col": [col, [0, 0, 0], [0, 0, 0]],
        }],
    }

    try:
        _post(host, port, timeout, payload)
        log.info("WLED: Modus '%s' → fx=%d bri=%d", mode, fx, bri)
    except (OSError, socket.timeout, Exception) as exc:
        log.warning("WLED nicht erreichbar (%s): %s", host, exc)
