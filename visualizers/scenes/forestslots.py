"""Pilzautomat, Tiere des Waldes, Waldgeister (Taste 5 im Thema THE POWER OF THE GREEN): drei Automaten mit je vier
Walzen (slots_themes.FOREST), Rahmen assets/slots/forest_frame.png (Holz, Moos, Pilze hängen über die Walzen).
Spiellogik, Walzen, Musik und Rahmen kommen aus slots.Controller; Shader visualizers/shaders/slots mit uStyle 1:
Glühwürmchen bei kleinem Gewinn, Blätterregen und der Fuchs tanzt (assets/woodeye/figures.png Zellen 24-27) bei
großem, Jackpot = der Lichthirsch (Jackpot-Symbol) galoppiert durchs Bild, Drop = Sporen.
"""
from __future__ import annotations

from launcher import config as lcfg
from visualizers.scenes import slots, slots_themes as art


class Controller(slots.Controller):
    THEMES = art.FOREST
    LED = ("forestslots", "forestslots_win", "forestslots_jackpot")
    STAKES = [("EICHEL", 10, 1), ("PILZ", 50, 5), ("HIRSCH", 200, 20)]
    CURRENCY = "CR"
    FRAME = "forest_frame.png"
    FIGURES = lcfg.ROOT / "assets" / "woodeye" / "figures.png"
    FIG_CELLS = (24, 4)                    # Fuchs tanzt
    STYLE = 1
    COUNTER = "forestslots_theme.txt"
    SEED_BASE = 7000
    TITLE_COLOR, SUBTITLE_COLOR, INFO_COLOR = (200, 255, 210), (190, 230, 200), (190, 210, 200)
    LOG = "Pilzautomat"
