"""Aktionen, die der Launcher kennt.

Eingabequellen (Tastatur, HID-Buttonbox, Steuer-Socket) erzeugen nur
Action-Werte. Was eine Action bewirkt, entscheidet allein der Kern.
So lässt sich die Eingabe später austauschen, ohne den Rest anzufassen.
"""
from enum import Enum


class Action(str, Enum):
    GAMING = "gaming"          # F1
    VIZ_PSYCHEDELIC = "viz_psychedelic"  # F2
    VIZ_CRT = "viz_crt"        # F3
    VIZ_EYE = "viz_eye"        # F4
    KITT = "kitt"              # F5
    HOME = "home"              # F6
    QUIT = "quit"              # ESC (nur Entwicklung)
    STATUS = "status"          # Zustand ins Log schreiben


# Welche Action startet welchen Modus (Modus-Namen siehe config/modes.toml)
ACTION_TO_MODE = {
    Action.GAMING: "gaming",
    Action.VIZ_PSYCHEDELIC: "viz_psychedelic",
    Action.VIZ_CRT: "viz_crt",
    Action.VIZ_EYE: "viz_eye",
    Action.KITT: "kitt",
    Action.HOME: "home",
}


def parse_action(name: str) -> "Action | None":
    try:
        return Action(name.strip().lower())
    except ValueError:
        return None
