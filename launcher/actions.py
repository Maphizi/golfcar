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
    CAMPFIRE = "campfire"      # F7
    HOME = "home"              # F6
    QUIT = "quit"              # ESC (nur Entwicklung)
    STATUS = "status"          # Zustand ins Log schreiben
    PLANETEN = "planeten"      # Planeten-Flug
    ERROR = "error"            # Systemfehler-Visualizer
    SLOTS = "slots"            # Space-Slotmaschine
    NEWS = "news"              # Galaktische Nachrichten
    BLACKHOLE = "blackhole"    # Schwarzes Loch
    DROID = "droid"            # Bord-Droide
    HAL = "hal"                # HAL 3000
    TRIP = "trip"              # Waldtresen (kittctl trip)
    POND = "pond"              # Moorsee (kittctl pond)
    WOODEYE = "woodeye"        # Auge des Waldes (kittctl woodeye)
    FORESTSLOTS = "forestslots"   # Pilzautomat (kittctl forestslots)
    HEARTTREE = "hearttree"    # Herzbaum (kittctl hearttree)
    OVERDOSE = "overdose"      # Überdosis (kittctl overdose)
    NEONRACE = "neonrace"      # Cyber: Neonfahrt
    CORE = "core"              # Cyber: Der Kern
    ORACLE = "oracle"          # Cyber: Das Orakel
    CYBERSLOTS = "cyberslots"  # Cyber: Pachinko
    ROOFTOP = "rooftop"        # Cyber: Dachterrasse
    BLACKICE = "blackice"      # Cyber: Black Ice
    TIMEJUMP = "timejump"      # Zukunft: Zeitsprung
    FLUX = "flux"              # Zukunft: Fluxkompensator
    CLOCKTOWER = "clocktower"  # Zukunft: Uhrturm
    ALMANACSLOTS = "almanacslots"  # Zukunft: Almanach
    SQUARE = "square"          # Zukunft: Marktplatz
    PARADOX = "paradox"        # Zukunft: Paradoxon
    TALK = "talk"              # Sprechtaste: bei HAL Musik leise + Mikrofon an/aus (Taste F15 an den Modus)
    HORN     = "horn"          # Hupe des Themas (assets/sfx/<thema>_horn.wav) + LED-Blitz
    HORN_OFF = "horn_off"      # Hupe-Schalter zurück in die Mitte: nichts (Ton läuft aus)
    HORN2    = "horn2"         # zweite Seite des Hupen-Schalters: zweiter Ton (assets/sfx/<thema>_horn2.wav)
    FX = "fx"                  # zufälliger Effekt des Themas (assets/sfx/<thema>_fx1..3.wav) + LED-Blitz
    ATTRACT_ON  = "attract_on"  # Autopilot-Schalter unten (an)
    ATTRACT_OFF = "attract_off" # Autopilot-Schalter oben (aus)
    VOICE_UP   = "voice_up"     # Drehknopf als Tasten: Stimme lauter/leiser (launcher/volume_knob.py)
    VOICE_DOWN = "voice_down"
    MUSIC_UP   = "music_up"     # Drehknopf als Tasten: Musik lauter/leiser (launcher/music_knob.py)
    MUSIC_DOWN = "music_down"
    LED_UP     = "led_up"       # LED-Helligkeit heller/dunkler (launcher/led_knob.py)
    LED_DOWN   = "led_down"


# Welche Action startet welchen Modus (Modus-Namen siehe config/modes.toml)
ACTION_TO_MODE = {
    Action.GAMING: "gaming",
    Action.VIZ_PSYCHEDELIC: "viz_psychedelic",
    Action.VIZ_CRT: "viz_crt",
    Action.VIZ_EYE: "viz_eye",
    Action.KITT: "kitt",
    Action.CAMPFIRE: "campfire",
    Action.PLANETEN: "planeten",
    Action.ERROR: "error",
    Action.SLOTS: "slots",
    Action.NEWS: "news",
    Action.BLACKHOLE: "blackhole",
    Action.DROID: "droid",
    Action.HAL: "hal",
    Action.TRIP: "trip",
    Action.POND: "pond",
    Action.WOODEYE: "woodeye",
    Action.FORESTSLOTS: "forestslots",
    Action.HEARTTREE: "hearttree",
    Action.OVERDOSE: "overdose",
    Action.NEONRACE: "neonrace",
    Action.CORE: "core",
    Action.ORACLE: "oracle",
    Action.CYBERSLOTS: "cyberslots",
    Action.ROOFTOP: "rooftop",
    Action.BLACKICE: "blackice",
    Action.TIMEJUMP: "timejump",
    Action.FLUX: "flux",
    Action.CLOCKTOWER: "clocktower",
    Action.ALMANACSLOTS: "almanacslots",
    Action.SQUARE: "square",
    Action.PARADOX: "paradox",
    Action.HOME: "home",
}


def parse_action(name: str) -> "Action | None":
    try:
        return Action(name.strip().lower())
    except ValueError:
        return None
