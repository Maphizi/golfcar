"""Konfiguration laden (TOML) und Projektpfade auflösen."""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def _load(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def load_settings() -> dict:
    return _load("settings.toml")


def load_keymap() -> dict:
    return _load("keymap.toml")


def load_modes() -> dict:
    return _load("modes.toml")


def runtime_dir() -> Path:
    """tmpfs-Verzeichnis für Socket und Statusdatei (keine SD-Schreibzugriffe)."""
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    p = Path(base)
    if not p.is_dir():
        p = Path("/tmp")
    return p


def logs_dir(settings: dict) -> Path:
    raw = settings.get("logging", {}).get("dir", "logs")
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not p.is_absolute():
        p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def socket_path() -> Path:
    return runtime_dir() / "kitt-launcher.sock"


def expand_command(cmd: list[str]) -> list[str]:
    """Platzhalter in Modus-Kommandos ersetzen."""
    subst = {
        "{python}": sys.executable,
        "{root}": str(ROOT),
        "{home}": str(Path.home()),
    }
    out = []
    for part in cmd:
        for key, val in subst.items():
            part = part.replace(key, val)
        out.append(os.path.expanduser(part))
    return out
