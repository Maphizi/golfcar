"""Kommandozeile: Action an den laufenden Launcher senden.

    python -m launcher.ctl home | gaming | viz_psychedelic | viz_crt | viz_eye | kitt | status | quit
    python -m launcher.ctl state   -> aktuellen Zustand ausgeben
"""
from __future__ import annotations

import json
import sys

from . import config
from .actions import Action, parse_action
from .input_socket import send


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    name = argv[0]
    if name == "state":
        f = config.runtime_dir() / "kitt-launcher.state"
        if not f.exists():
            print("Launcher läuft nicht (keine Statusdatei)")
            return 1
        print(json.dumps(json.loads(f.read_text()), indent=2))
        return 0
    if parse_action(name) is None:
        print(f"Unbekannte Action: {name}. Erlaubt: {', '.join(a.value for a in Action)}")
        return 2
    path = config.socket_path()
    if not path.exists():
        print(f"Launcher läuft nicht (kein Socket {path})")
        return 1
    send(path, name)
    print(f"gesendet: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
