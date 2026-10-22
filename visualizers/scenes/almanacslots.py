"""Almanach, Wilder Westen, Zukunft 2015 (Taste 5 im Thema ZURÜCK IN DIE ZUKUNFT): drei Automaten mit je drei Walzen
(slots_themes.FUTURE), Rahmen assets/slots/future_frame.png (Casino-Gold 1985, Hoverboard lehnt über die Walzen).
Spiellogik, Walzen, Musik und Rahmen kommen aus slots.Controller; Shader visualizers/shaders/slots mit uStyle 3:
Dollarscheine regnen bei Gewinn, Feuerspuren und der Professor tanzt (assets/future/clocktower_figures.png Zellen 0-7)
bei großem, Jackpot = Blitz, die Zeitmaschine (Zellen 14/15) fährt durch, alles kippt kurz nach Schwarzweiß wie 1955
(uSepia), Drop = Blitz.
"""
from __future__ import annotations

from launcher import config as lcfg
from visualizers.scenes import slots, slots_themes as art


class Controller(slots.Controller):
    THEMES = art.FUTURE
    LED = ("almanacslots", "almanacslots_win", "almanacslots_jackpot")
    STAKES = [("CENT 1955", 10, 1), ("DOLLAR 1985", 50, 5), ("KARTE 2015", 200, 20)]
    CURRENCY = "$"
    FRAME = "future_frame.png"
    FIGURES = lcfg.ROOT / "assets" / "future" / "clocktower_figures.png"
    FIG_CELLS = (0, 8)                     # Professor tanzt
    STYLE = 3
    COUNTER = "almanacslots_theme.txt"
    SEED_BASE = 15000
    TITLE_COLOR, SUBTITLE_COLOR, INFO_COLOR = (255, 215, 80), (255, 120, 90), (230, 210, 170)
    SEPIA_ON_JACKPOT = True
    LOG = "Almanach"
