"""kitt.toml laden und Pfade auflösen."""
from __future__ import annotations

import os
from pathlib import Path

from launcher import config as lcfg


def load() -> dict:
    return lcfg._load("kitt.toml")


def path(p: str) -> Path:
    p = p.replace("{root}", str(lcfg.ROOT)).replace("{home}", str(Path.home()))
    return Path(os.path.expanduser(p))
