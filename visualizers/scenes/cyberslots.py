"""Pachinko, Konzern, Netzgeister (Taste 5 im Thema CYBERPUNK): drei Automaten mit je fünf Walzen (slots_themes.CYBER),
Rahmen assets/slots/cyber_frame.png (Chrom, Neonröhren, Drohne hängt über die Walzen).
Spiellogik, Walzen, Musik und Rahmen kommen aus slots.Controller; Shader visualizers/shaders/slots mit uStyle 2:
Chips regnen bei Gewinn, Hologramm-Feuerwerk und der Samurai tanzt (assets/cyber/oracle_figures.png Zellen 0-7) bei
großem, Jackpot = die Halle explodiert in Neon, Drop = Glitch.
"""
from __future__ import annotations

from launcher import config as lcfg
from visualizers.scenes import slots, slots_themes as art


class Controller(slots.Controller):
    THEMES = art.CYBER
    LED = ("cyberslots", "cyberslots_win", "cyberslots_jackpot")
    STAKES = [("CHIP", 10, 1), ("DECK", 50, 5), ("IMPLANT", 200, 20)]
    CURRENCY = "€$"
    FRAME = "cyber_frame.png"
    FIGURES = lcfg.ROOT / "assets" / "cyber" / "oracle_figures.png"
    FIG_CELLS = (0, 8)                     # Samurai tanzt
    STYLE = 2
    COUNTER = "cyberslots_theme.txt"
    SEED_BASE = 11000
    TITLE_COLOR, SUBTITLE_COLOR, INFO_COLOR = (255, 80, 220), (120, 220, 255), (180, 200, 230)
    LOG = "Pachinko"
