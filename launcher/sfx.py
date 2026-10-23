"""Hupe und Effekte je Thema: assets/sfx/real/<thema>_horn.wav, <thema>_fx1..3.wav (echte Klänge, scripts/sfx_fetch.py),
sonst die synthetischen aus assets/sfx/ (scripts/sfx_build.py).

`play("horn")` spielt die Hupe des aktuellen Themas, `play("fx")` einen zufälligen Effekt (nie zweimal derselbe
hintereinander), nicht-blockierend über pw-play (PipeWire) oder aplay. Lautstärke: settings.toml [sfx] volume.
Fehlt das Thema, fällt es auf spacetaxi zurück."""
from __future__ import annotations

import logging
import random
import shutil
import subprocess

from launcher import config as lcfg

log = logging.getLogger("sfx")
SFX_DIR = lcfg.ROOT / "assets" / "sfx"
N_FX = 3
_last_fx = -1
_current: subprocess.Popen | None = None


def _theme_name() -> str:
    try:
        from launcher import theme
        return theme.current_name() or "spacetaxi"
    except Exception:
        return "spacetaxi"


def path_for(kind: str) -> tuple[str, "lcfg.Path | None"]:
    """(Beschreibung, Pfad) für "horn", "fx", "attract_on", "attract_off" im aktuellen Thema."""
    global _last_fx
    th = _theme_name()
    if kind == "fx":
        choices = [i for i in range(1, N_FX + 1) if i != _last_fx]
        i = random.choice(choices)
        _last_fx = i
        name = f"{th}_fx{i}"
    else:
        name = f"{th}_{kind}"
    p = SFX_DIR / "real" / f"{name}.wav"                  # echte Klänge (scripts/sfx_fetch.py) vor den synthetischen
    if not p.exists():
        p = SFX_DIR / f"{name}.wav"
    if not p.exists():
        fallback = f"spacetaxi_{kind}" if kind not in ("fx",) else "spacetaxi_fx1"
        p = SFX_DIR / f"{fallback}.wav"
    return name, (p if p.exists() else None)


def play(kind: str) -> bool:
    global _current
    settings = lcfg.load_settings()
    cfg = settings.get("sfx", {})
    if not cfg.get("enabled", True):
        return False
    name, p = path_for(kind)
    if p is None:
        log.warning("Klangeffekt %s fehlt (scripts/sfx_build.py ausführen)", name)
        return False
    vol = float(cfg.get("volume", 1.0))
    if shutil.which("pw-play"):
        cmd = ["pw-play", "-P", f"media.volume={vol}", str(p)]
    elif shutil.which("aplay"):
        cmd = ["aplay", "-q", str(p)]
    else:
        log.warning("Kein Abspielprogramm (pw-play/aplay)")
        return False
    if _current and _current.poll() is None and kind == "horn":
        _current.kill()                                   # Hupe unterbricht eine laufende Hupe
    try:
        _current = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info("Klang: %s", name)
        return True
    except OSError as exc:
        log.warning("Klang %s: %s", name, exc)
        return False
