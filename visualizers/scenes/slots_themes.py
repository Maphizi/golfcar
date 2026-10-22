"""Die Automaten aller Slotmaschinen: je ein Bildbogen mit 3x3 Symbolen (assets/slots/*.png, 768x510, Kacheln
256x170, scripts/slots_assets.sh) plus Farben, Walzenzahl und Sprüche. Das letzte Symbol ist jeweils das Jackpot-Symbol.

Je Thema drei Automaten (Knüppel links/rechts wechselt): THEMES = Space (Taste 5), FOREST = Natur (Pilzautomat),
CYBER = Cyberpunk (Pachinko), FUTURE = Zurück in die Zukunft (Almanach). Die Walzenzahl steht je Automat im Dict
("reels", 3..5, Standard 3) und ist je Thema gleich: Space 3, Zukunft 3, Natur 4, Cyberpunk 5.
"keyed": Schwarz im Bogen ist frei (Symbol liegt auf dem Walzenband), sonst ist die ganze Kachel ein gedrucktes Etikett.
Fehlt ein Bogen (die neuen Bögen vom Bot liegen noch nicht vor), läuft der Automat mit dem ersten Bogen seines Themas.
"""
from __future__ import annotations

from launcher import config as lcfg

SHEET_DIR = lcfg.ROOT / "assets" / "slots"
SHEET_COLS, SHEET_ROWS = 3, 3
TILE_W, TILE_H = 256, 170
MIN_REELS, MAX_REELS = 3, 5

THEMES = [
    {
        "name": "ORBIT", "sheet": "real.png", "reels": 3,
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
        "name": "COMIC", "sheet": "cartoon.png", "reels": 3,
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
        "name": "WAHNSINN", "sheet": "crazy.png", "reels": 3,
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

# Thema THE POWER OF THE GREEN (visualizers/scenes/forestslots.py): vier Walzen, Schwarz im Bogen ist frei.
FOREST = [
    {
        "name": "PILZAUTOMAT", "sheet": "forest.png", "reels": 4, "keyed": True,
        "title": "DER PILZAUTOMAT", "subtitle": "DER WALD GIBT. DER WALD NIMMT. MEIST NIMMT ER.",
        "colors": ((0.35, 0.95, 0.70), (0.95, 0.70, 0.25)),
        "symbols": ["FLIEGENPILZ", "FROSCH", "EULE", "GLUEHWUERMCHEN", "EICHEL", "FARN", "SCHNECKE", "FUCHS", "LICHTHIRSCH"],
        "lose": ["Verloren. Die Schnecke war schneller als dein Glück.", "Nichts. Die Eule hat es kommen sehen.",
                 "Verlust. Der Fliegenpilz lacht sich die Punkte vom Hut.", "Kein Gewinn. Der Wald behält seine Eicheln.",
                 "Nichts. Der Fuchs hat deinen Einsatz schon vergraben."],
        "near": ["Fast. Der Farn hat sich im letzten Moment weggedreht.", "Zwei Treffer. Das dritte hängt noch am Ast.",
                 "Knapp. Der Frosch hat gezuckt."],
        "small": ["Kleiner Gewinn. Eine Handvoll Eicheln.", "Gewonnen. Das Glühwürmchen leuchtet für dich."],
        "big": ["Drei nebeneinander. Der Wald rauscht Beifall.", "Gewinn. Die Pilze leuchten in deiner Farbe."],
        "jackpot": ["Alle Walzen gleich. Der Wald gehört heute Nacht dir.", "Jackpot. Der Lichthirsch galoppiert durch den Wald."],
        "big_text": "D E R   W A L D   G I B T", "jackpot_text": "L I C H T H I R S C H",
    },
    {
        "name": "TIERE DES WALDES", "sheet": "forest_animals.png", "reels": 4, "keyed": True,
        "title": "TIERE DES WALDES", "subtitle": "WER NACHTS SPIELT, WIRD BEOBACHTET.",
        "colors": ((0.60, 0.85, 0.45), (0.40, 0.30, 0.20)),
        "symbols": ["IGEL", "DACHS", "REH", "WILDSCHWEIN", "WOLF", "RABE", "FLEDERMAUS", "LUCHS", "LICHTHIRSCH"],
        "lose": ["Verloren. Der Dachs gräbt deinen Einsatz ein.", "Nichts. Der Rabe hat gelacht. Raben lachen nicht.",
                 "Verlust. Das Wildschwein hat die Walzen umgepflügt.", "Kein Gewinn. Der Wolf heult. Nicht für dich."],
        "near": ["Fast. Der Luchs hat im letzten Moment weggeschaut.", "Zwei Treffer. Das Reh ist davongesprungen.",
                 "Knapp. Die Fledermaus hing falsch herum."],
        "small": ["Kleiner Gewinn. Der Igel rollt dir ein paar Eicheln zu.", "Gewonnen. Das Reh nickt."],
        "big": ["Drei nebeneinander. Das Rudel heult Beifall.", "Gewinn. Der Luchs schnurrt. Angeblich."],
        "jackpot": ["Alle Walzen gleich. Der ganze Wald steht still.", "Jackpot. Der Lichthirsch tritt aus dem Nebel."],
        "big_text": "D A S   R U D E L   J U B E L T", "jackpot_text": "L I C H T H I R S C H",
    },
    {
        "name": "WALDGEISTER", "sheet": "forest_magic.png", "reels": 4, "keyed": True,
        "title": "WALDGEISTER", "subtitle": "DIE FEEN DREHEN. DIE WURZELN ZAHLEN AUS.",
        "colors": ((0.55, 0.45, 0.95), (0.30, 0.95, 0.60)),
        "symbols": ["FEE", "IRRLICHT", "HEXENRING", "TRAUMFAENGER", "VOLLMOND", "KRISTALL", "ZWERG", "ALRAUNE", "WALDGOTT"],
        "lose": ["Verloren. Das Irrlicht hat dich in die Irre geführt.", "Nichts. Die Alraune hat geschrien. Wie immer.",
                 "Verlust. Der Zwerg kichert unter der Wurzel.", "Kein Gewinn. Der Vollmond hat sich hinter eine Wolke gedreht."],
        "near": ["Fast. Die Fee hat die letzte Walze angestupst. Falsch herum.", "Zwei Treffer. Der Hexenring war nicht geschlossen.",
                 "Knapp. Der Traumfänger hat den Gewinn gefangen. Für sich."],
        "small": ["Kleiner Gewinn. Ein Kristallsplitter aus dem Moos.", "Gewonnen. Das Irrlicht tanzt für dich."],
        "big": ["Drei nebeneinander. Die Feen streuen Funken.", "Gewinn. Der Zwerg verneigt sich."],
        "jackpot": ["Alle Walzen gleich. Der Waldgott öffnet die Augen.", "Jackpot. Die Wurzeln tragen dir das Gold herauf."],
        "big_text": "D I E   F E E N   T A N Z E N", "jackpot_text": "W A L D G O T T",
    },
]

# Thema CYBERPUNK (visualizers/scenes/cyberslots.py): fünf Walzen.
CYBER = [
    {
        "name": "PACHINKO", "sheet": "cyberslots_symbols.png", "reels": 5, "keyed": True,
        "title": "PACHINKO SEKTOR 7", "subtitle": "DIE BANK IST EIN KONZERN. DER KONZERN GEWINNT.",
        "colors": ((0.95, 0.20, 0.80), (0.20, 0.85, 1.00)),
        "symbols": ["NEUROCHIP", "DROHNE", "RAMEN", "KATANA", "CYBERDECK", "NEONKATZE", "CREDITCHIP", "CHROMSCHÄDEL", "KI-KERN"],
        "lose": ["Verloren. Die Drohne hat deine Eddies schon abgeholt.", "Nichts. Der Konzern dankt.",
                 "Verlust. Der Chromschädel grinst. Er grinst immer.", "Kein Gewinn. Dein Implant meldet: erwartbar.",
                 "Nichts. Die Neonkatze hat nicht mal hingesehen."],
        "near": ["Fast. Das Katana hat die Walze gestreift.", "Zwei Treffer. Der Rest hängt im Lag.",
                 "Knapp. Der Ramen war noch heiß."],
        "small": ["Kleiner Gewinn. Ein paar Eddies, steuerfrei. Angeblich.", "Gewonnen. Die Katze blinzelt anerkennend."],
        "big": ["Vier gleiche. Die Halle rauscht Beifall.", "Gewinn. Das Hologramm tanzt für dich."],
        "jackpot": ["Alle Walzen gleich. Der Konzern schickt Drohnen. Mit Koffern.", "Jackpot. Sektor 7 gehört heute Nacht dir."],
        "big_text": "S E K T O R   7   Z A H L T", "jackpot_text": "K I - K E R N",
    },
    {
        "name": "KONZERN", "sheet": "cyber_konzern.png", "reels": 5, "keyed": True,
        "title": "KONZERN-LOTTERIE", "subtitle": "JEDER GEWINN IST VERTRAGLICH GEREGELT. GEGEN DICH.",
        "colors": ((0.20, 0.60, 1.00), (0.95, 0.80, 0.20)),
        "symbols": ["KOFFER", "WACHROBOTER", "LOGOWUERFEL", "KAMERA", "CHIPKARTE", "SERVER", "ANDROID", "LIMOUSINE", "KI-KERN"],
        "lose": ["Verloren. Die Kamera hat es gesehen. Alle haben es gesehen.", "Nichts. Der Android lächelt vertraglich.",
                 "Verlust. Der Server hat deinen Einsatz archiviert.", "Kein Gewinn. Die Limousine fährt ohne dich."],
        "near": ["Fast. Der Wachroboter hat die letzte Walze festgehalten.", "Zwei Treffer. Die Chipkarte wurde abgelehnt.",
                 "Knapp. Der Logowürfel hat sich noch einmal gedreht."],
        "small": ["Kleiner Gewinn. Ein Bonus, abzüglich Gebühren.", "Gewonnen. Der Android nickt. Protokolliert."],
        "big": ["Vier gleiche. Die Vorstandsetage leuchtet auf.", "Gewinn. Der Koffer klickt auf."],
        "jackpot": ["Alle Walzen gleich. Der Konzern gehört dir. Für eine Nacht.", "Jackpot. Die Limousine wartet unten."],
        "big_text": "D E R   V O R S T A N D   Z A H L T", "jackpot_text": "K I - K E R N",
    },
    {
        "name": "NETZGEISTER", "sheet": "cyber_netzgeister.png", "reels": 5, "keyed": True,
        "title": "NETZGEISTER", "subtitle": "HINTER DER FIREWALL WIRD GEWÜRFELT.",
        "colors": ((0.20, 0.95, 0.60), (0.80, 0.20, 0.95)),
        "symbols": ["MASKE", "SPINNE", "VIRUS", "HOLOSCHAEDEL", "PIXELFISCH", "SCANAUGE", "GLASFASERHAND", "DRAHTGESICHT", "KI-KERN"],
        "lose": ["Verloren. Die Spinne hat dein Konto eingesponnen.", "Nichts. Der Virus hat die Quote gefressen.",
                 "Verlust. Das Scanauge blinzelt nicht. Nie.", "Kein Gewinn. Der Pixelfisch ist weggeschwommen."],
        "near": ["Fast. Die Glasfaserhand hat die letzte Walze gestreift.", "Zwei Treffer. Das Drahtgesicht hat gelacht.",
                 "Knapp. Die Maske hat geglitcht."],
        "small": ["Kleiner Gewinn. Ein paar Bits aus dem Datenstrom.", "Gewonnen. Der Holoschädel grinst freundlich."],
        "big": ["Vier gleiche. Das Netz flackert Beifall.", "Gewinn. Die Geister tanzen durch die Leitung."],
        "jackpot": ["Alle Walzen gleich. Die Firewall fällt. Alles gehört dir.", "Jackpot. Der KI-Kern erwacht."],
        "big_text": "D A S   N E T Z   Z A H L T", "jackpot_text": "K I - K E R N",
    },
]

# Thema ZURÜCK IN DIE ZUKUNFT (visualizers/scenes/almanacslots.py): drei Walzen, klassisches Casino.
FUTURE = [
    {
        "name": "ALMANACH", "sheet": "almanac_symbols.png", "reels": 3, "keyed": True,
        "title": "ALMANACH CASINO 1985", "subtitle": "DAS FALSCHE 1985. DAS HAUS KENNT DAS ERGEBNIS SCHON.",
        "colors": ((1.00, 0.80, 0.25), (0.95, 0.15, 0.15)),
        "symbols": ["HOVERBOARD", "ALMANACH", "PLUTONIUM", "SKATEBOARD", "KASSETTE", "EINSTEIN", "TURNSCHUH", "FLUX", "22:04"],
        "lose": ["Verloren. Der Almanach hätte es gewusst. Du hast ihn nicht.", "Nichts. Das Haus kennt die Zukunft, du nicht.",
                 "Verlust. Das Plutonium ist alle, dein Geld auch.", "Kein Gewinn. Einstein schaut weg.",
                 "Nichts. Die Kassette spielt nur noch Rauschen."],
        "near": ["Fast. Das Hoverboard ist über der Linie hängen geblieben.", "Zwei Treffer. Der dritte steckt noch in 1955.",
                 "Knapp. Der Fluxkompensator hat gezuckt."],
        "small": ["Kleiner Gewinn. Ein paar Dollar aus dem falschen Jahr.", "Gewonnen. Einstein wedelt mit dem Schwanz."],
        "big": ["Drei gleiche. 1,21 Gigawatt! Der Professor tanzt.", "Gewinn. Feuerspuren auf dem Casinoteppich."],
        "jackpot": ["GROSSER GOTT! 22:04 dreifach. Der Blitz zahlt aus.", "GROSSER GOTT! Die Zeitmaschine kommt. Mit Koffern."],
        "big_text": "1 , 2 1   G I G A W A T T", "jackpot_text": "G R O S S E R   G O T T !",
    },
    {
        "name": "WILDER WESTEN", "sheet": "future_1885.png", "reels": 3, "keyed": True,
        "title": "SALOON 1885", "subtitle": "DER SHERIFF SPIELT MIT. DER SHERIFF GEWINNT.",
        "colors": ((0.90, 0.65, 0.30), (0.55, 0.35, 0.15)),
        "symbols": ["REVOLVER", "HUT", "SHERIFFSTERN", "HUFEISEN", "KAKTUS", "LOKOMOTIVE", "WHISKEY", "STECKBRIEF", "22:04"],
        "lose": ["Verloren. Der Whiskey war das Beste am Abend.", "Nichts. Der Sheriff zuckt mit dem Stern.",
                 "Verlust. Die Lokomotive hat deinen Einsatz mitgenommen.", "Kein Gewinn. Der Kaktus bleibt stachelig."],
        "near": ["Fast. Das Hufeisen hing schon über der Tür.", "Zwei Treffer. Der dritte reitet noch.",
                 "Knapp. Der Revolver hat geklickt. Leer."],
        "small": ["Kleiner Gewinn. Ein paar Dollar in Silber.", "Gewonnen. Der Hut geht herum."],
        "big": ["Drei gleiche. Der Saloon johlt.", "Gewinn. Der Pianist spielt schneller."],
        "jackpot": ["GROSSER GOTT! 22:04 dreifach. Der Blitz trifft die Uhr.", "Jackpot. Die Lokomotive schiebt dich in die Zukunft."],
        "big_text": "D E R   S A L O O N   J O H L T", "jackpot_text": "G R O S S E R   G O T T !",
    },
    {
        "name": "ZUKUNFT 2015", "sheet": "future_2015.png", "reels": 3, "keyed": True,
        "title": "CAFE 80S CASINO 2015", "subtitle": "DIE ZUKUNFT, WIE MAN SIE SICH 1985 VORSTELLTE.",
        "colors": ((0.95, 0.40, 0.80), (0.20, 0.80, 1.00)),
        "symbols": ["HOVERBOARD", "FLUGAUTO", "TURNSCHUH", "HOLOHAI", "FUSIONSREAKTOR", "DROHNE", "VIDEOBRILLE", "ROBOTERKELLNER", "22:04"],
        "lose": ["Verloren. Der Holohai hat zugeschnappt.", "Nichts. Der Roboterkellner bringt die Rechnung.",
                 "Verlust. Das Flugauto parkt auf deinem Konto.", "Kein Gewinn. Die Videobrille zeigt nur Werbung."],
        "near": ["Fast. Der Turnschuh hat sich nicht selbst geschnürt.", "Zwei Treffer. Der dritte schwebt noch.",
                 "Knapp. Die Drohne hat das Symbol verfehlt."],
        "small": ["Kleiner Gewinn. Ein paar Dollar, bitte in bar.", "Gewonnen. Der Roboterkellner applaudiert."],
        "big": ["Drei gleiche. Der Fusionsreaktor zündet.", "Gewinn. Das Hoverboard dreht eine Runde."],
        "jackpot": ["GROSSER GOTT! 22:04 dreifach. Der Blitz kommt pünktlich.", "Jackpot. Die Zeitmaschine landet im Cafe."],
        "big_text": "1 , 2 1   G I G A W A T T", "jackpot_text": "G R O S S E R   G O T T !",
    },
]
