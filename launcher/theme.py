"""Thema des ganzen Programms: Liste aus config/themes.toml, Auswahl in logs/theme.txt.

    from launcher import theme
    theme.current()          -> dict des gewählten Themas (name, title, color_a, ...)
    theme.set_current(name)  -> speichert die Wahl
Modi bekommen den Namen zusätzlich als Umgebungsvariable KITT_THEME.
"""
from __future__ import annotations

import os

from . import config

STATE = config.ROOT / "logs" / "theme.txt"


def themes() -> list[dict]:
    try:
        return list(config._load("themes.toml").get("themes", []))
    except Exception:
        return []


def current_name() -> str:
    env = os.environ.get("KITT_THEME", "")
    if env:
        return env
    try:
        return STATE.read_text().strip()
    except OSError:
        return ""


def current() -> dict:
    all_ = themes()
    if not all_:
        return {"name": "default", "title": "KITT-CART", "tagline": "", "color_a": [0.95, 0.8, 0.25],
                "color_b": [0.15, 0.45, 0.85], "tint": [0.95, 0.75, 0.25], "cover_style": 0}
    name = current_name()
    for t in all_:
        if t.get("name") == name:
            return t
    return all_[0]


def set_current(name: str) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(name)
    except OSError:
        pass
