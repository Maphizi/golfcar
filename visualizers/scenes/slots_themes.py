"""Die drei Automaten der Space-Slotmaschine: je ein Bildbogen mit 3x3 Symbolen (assets/slots/*.png,
768x510, Kacheln 256x170) plus Farben und Sprüche. Das letzte Symbol ist jeweils das Jackpot-Symbol.
Die Bildbögen hat der Pilot selbst erzeugt und ins Repo gegeben.
"""
from __future__ import annotations

from launcher import config as lcfg

SHEET_DIR = lcfg.ROOT / "assets" / "slots"
SHEET_COLS, SHEET_ROWS = 3, 3
TILE_W, TILE_H = 256, 170

THEMES = [
    {
        "name": "ORBIT", "sheet": "real.png",
        "title": "ORBITAL CASINO", "subtitle": "ECHTE STERNE. ECHTE VERLUSTE.",
        "colors": ((0.95, 0.65, 0.25), (0.25, 0.45, 0.85)),
        "symbols": ["ASTRONAUT", "ALIEN", "UFO", "SATURN", "ASTEROID", "KRISTALL", "MOND", "RAUMSCHIFF", "SCHWARZES LOCH"],
        "lose": ["Verloren. Das Universum ist groß und gleichgültig.", "Nichts. Der Mond schaut weg.",
                 "Verlust. Der Asteroid nimmt Kurs auf dein Konto.", "Kein Gewinn. Die Sterne schweigen."],
        "near": ["Fast. Ein Symbol fehlte, wie der Sauerstoff.", "Zwei Treffer. Das dritte kreist noch im Orbit.", "Knapp. Der Alien grinst."],
        "small": ["Kleiner Gewinn. Ein Mondstein.", "Gewonnen. Der Astronaut salutiert."],
        "big": ["Drei gleiche. Die Umlaufbahn ist erreicht.", "Gewinn. Das UFO blinkt anerkennend."],
        "jackpot": ["SCHWARZES LOCH dreifach. Alles wird eingesogen, auch dein Gewinn.", "Jackpot. Die Gravitation ist heute auf deiner Seite."],
    },
    {
        "name": "COMIC", "sheet": "cartoon.png",
        "title": "SPACE-ARCADE AUTOMAT", "subtitle": "BUNT. LAUT. UNFAIR.",
        "colors": ((0.35, 0.85, 1.00), (0.95, 0.35, 0.65)),
        "symbols": ["ASTRONAUT", "ALIEN", "UFO", "SATURN", "ASTEROID", "KRISTALL", "MOND", "RAKETE", "SCHWARZES LOCH"],
        "lose": ["Verloren. Der grüne Alien kichert.", "Nichts. Die Rakete fliegt ohne dich.",
                 "Verlust. Der Kristall glitzert trotzdem.", "Kein Gewinn. Der Mond zuckt mit den Kratern."],
        "near": ["Fast. Die Rakete stand schon auf der Rampe.", "Zwei Treffer. Der dritte hängt im Asteroidengürtel.", "Knapp. Das UFO winkt."],
        "small": ["Kleiner Gewinn. Ein Kristallsplitter.", "Gewonnen. Der Alien applaudiert mit drei Fingern."],
        "big": ["Drei gleiche. Zündung. Abheben.", "Gewinn. Saturn dreht eine Ehrenrunde."],
        "jackpot": ["SCHWARZES LOCH dreifach. Die Arcade explodiert in Farben.", "Jackpot. Das UFO nimmt dich mit."],
    },
    {
        "name": "WAHNSINN", "sheet": "crazy.png",
        "title": "KOSMISCHER WAHNSINN", "subtitle": "NICHTS HIER IST GESUND. AUCH NICHT DIE QUOTE.",
        "colors": ((0.95, 0.20, 0.80), (0.30, 1.00, 0.30)),
        "symbols": ["ALIEN-LADY", "ALIEN-PILOT", "KUH-ENTFUEHRUNG", "PIZZA", "TOTENKOPF-PLANET", "AUGENMONSTER", "SKELETT", "ATOMRAKETE", "SCHWARZES LOCH"],
        "lose": ["Verloren. Die Pizza hat dich angesehen.", "Nichts. Die Kuh wurde trotzdem entführt.",
                 "Verlust. Das Augenmonster blinzelt siebenfach.", "Kein Gewinn. Das Skelett lacht. Es hat Zeit."],
        "near": ["Fast. Die Atomrakete hat gezischt.", "Zwei Treffer. Der dritte schmilzt noch.", "Knapp. Die Alien-Lady schaut enttäuscht."],
        "small": ["Kleiner Gewinn. Ein Stück Pizza mit Auge.", "Gewonnen. Das Monster sabbert vor Freude."],
        "big": ["Drei gleiche. Der Totenkopf-Planet jubelt.", "Gewinn. Die Kuh ist zurück. Verändert, aber zurück."],
        "jackpot": ["SCHWARZES LOCH dreifach. Der Wahnsinn gehört dir.", "Jackpot. Die Pizza ist jetzt dein Chef."],
    },
]

# Der Pilzautomat (Thema THE POWER OF THE GREEN, visualizers/scenes/forestslots.py): eigener Bogen, eigene Zeile,
# nicht Teil der drei Space-Automaten. Letztes Symbol = Jackpot (Lichthirsch).
FOREST = {
    "name": "PILZAUTOMAT", "sheet": "forest.png",
    "title": "DER PILZAUTOMAT", "subtitle": "DER WALD GIBT. DER WALD NIMMT. MEIST NIMMT ER.",
    "colors": ((0.35, 0.95, 0.70), (0.95, 0.70, 0.25)),
    "symbols": ["FLIEGENPILZ", "FROSCH", "EULE", "GLUEHWUERMCHEN", "EICHEL", "FARN", "SCHNECKE", "FUCHS", "LICHTHIRSCH"],
    "lose": ["Verloren. Die Schnecke war schneller als dein Glück.", "Nichts. Die Eule hat es kommen sehen.",
             "Verlust. Der Fliegenpilz lacht sich die Punkte vom Hut.", "Kein Gewinn. Der Wald behält seine Eicheln.",
             "Nichts. Der Fuchs hat deinen Einsatz schon vergraben."],
    "near": ["Fast. Der Farn hat sich im letzten Moment weggedreht.", "Zwei Treffer. Das dritte hängt noch am Ast.",
             "Knapp. Der Frosch hat gezuckt."],
    "small": ["Kleiner Gewinn. Eine Handvoll Eicheln.", "Gewonnen. Das Glühwürmchen leuchtet für dich."],
    "big": ["Drei gleiche. Der Wald rauscht Beifall.", "Gewinn. Die Pilze leuchten in deiner Farbe."],
    "jackpot": ["LICHTHIRSCH dreifach. Der Wald gehört heute Nacht dir.", "Jackpot. Der Hirsch galoppiert durch den Wald."],
}
