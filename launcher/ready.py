"""Bereitschaftsmeldung eines Modus an den Launcher (nahtloser Moduswechsel).

Der Prozessmanager startet den neuen Modus, während der alte noch läuft, und reicht ihm das Schreibende einer Pipe als
Umgebungsvariable KITT_READY_FD. Sobald der neue Modus sein erstes Bild gezeichnet hat, ruft er signal_ready(); erst
dann beendet der Launcher den alten Modus. Ohne KITT_READY_FD (Start von Hand, Tests) passiert nichts.
"""
from __future__ import annotations

import os

_done = False


def signal_ready() -> None:
    global _done
    if _done:
        return
    _done = True
    fd = os.environ.get("KITT_READY_FD")
    if not fd:
        return
    try:
        os.write(int(fd), b"ready\n")
        os.close(int(fd))
    except (OSError, ValueError):
        pass
