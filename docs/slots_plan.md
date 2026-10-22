# Slotmaschinen neu – Vollbild-Walzen, Themenrahmen, drei Automaten je Thema

Vorbild ist die Space-Slotmaschine (`visualizers/scenes/slots.py`, Shader `visualizers/shaders/slots/frag.glsl`): drei
Walzen füllen das ganze Bild (Nahaufnahme, Traum-Unschärfe beim Drehen), drei Automaten (ORBIT, COMIC, WAHNSINN) mit je
eigenem Symbolbogen, Knüppel links/rechts wechselt den Automaten. Genau so sollen alle Themen-Slotmaschinen aussehen:

- **Vollbild-Walzen** wie bei Space, kein kleiner Automat mehr in einem Foto.
- **Themenrahmen**: ein Bild je Thema, das als Rand über den Walzen liegt (Mitte reines Schwarz = Walzen sichtbar).
  Teile des Rahmens dürfen über die Walzen hängen (Natur: 2-3 Pilze, die leicht zur Musik blinken).
- **Drei Automaten je Thema**, Knüppel links/rechts wechselt (wie bei Space), Knüppel oben/unten = Einsatz.
- **Walzenzahl je Thema**: Space 3, Zurück in die Zukunft 3 (klassisches Casino), Natur 4, Cyberpunk 5. Die Walzen teilen
  sich die Bildbreite, Symbole bleiben 3:2. Gewinne bei 4/5 Walzen: drei gleiche nebeneinander = klein, alle bis auf eine
  = groß, alle gleich = Jackpot (Jackpot-Symbol auf allen = Mega).
- Musik: Rahmen-Lichter (helle, gesättigte Stellen des Rahmenbilds) pulsen zum Bass, Lauflicht über die Stege auf
  den Beat, Drop = Blitz und schnellere Drehung, Gewinn-/Jackpot-Effekte je Thema bleiben.

| Thema | Modus | Rahmen | Automaten (Symbolbögen 3x3, letztes Symbol = Jackpot) |
|---|---|---|---|
| Space | `slots` | `space_frame` (neu, optional, sonst Blende wie bisher) | 3 Walzen: ORBIT `real.png`, COMIC `cartoon.png`, WAHNSINN `crazy.png` (vorhanden) |
| Natur | `forestslots` | `forest_frame` (Holz, Moos, Pilze hängen über) | 4 Walzen: PILZAUTOMAT `forest.png` (vorhanden), TIERE DES WALDES `forest_animals`, WALDGEISTER `forest_magic` |
| Cyberpunk | `cyberslots` | `cyber_frame` (Chrom, Neonröhren, Kabel) | 5 Walzen: PACHINKO `cyberslots_symbols` (vorhanden), KONZERN `cyber_konzern`, NETZGEISTER `cyber_netzgeister` |
| Zurück in die Zukunft | `almanacslots` | `future_frame` (Casino-Gold 1985, Flux-Lämpchen) | 3 Walzen: ALMANACH `almanac_symbols` (vorhanden), WILDER WESTEN `future_1885`, ZUKUNFT 2015 `future_2015` |

Die Bilder legt der Bot unter **`assets/slots/raw/`** ab (PNG, Name exakt wie unten). `scripts/slots_assets.sh` skaliert
die Symbolbögen auf das Format der Space-Bögen (768x510, Kacheln 256x170) und die Rahmen auf 1920x1080.

## Prompts (für den Bot; Dateiname = Name ohne Endung)

Rahmen: 16:9, mindestens 1600 Pixel breit, fotorealistisch, kein lesbarer Text. **Wichtig: die Mitte ist eine einzige
reine Schwarzfläche** (etwa 80 % der Breite und 85 % der Höhe, leicht abgerundete Ecken), der Rahmen ist nur der Rand.
Symbolbögen: exakt 3 Spalten x 3 Reihen, gleich große Querformat-Zellen 3:2, jedes Symbol zentriert auf reinem Schwarz
(oder vor passendem dunklen Hintergrund je Zelle wie bei den Space-Bögen), kein Text.

**forest_frame**
```
Photorealistic frame of an enchanted forest slot machine seen frontally and filling the whole image: the border is made of
old mossy bark and twisted roots with ferns, glowing blue and orange mushrooms, fireflies and dew drops; two or three large
bioluminescent mushrooms grow from the top edge and the left edge and hang into the central area; the entire central area
is one solid pure black rectangle with slightly rounded corners, about 80 percent of the width and 85 percent of the height,
nothing drawn inside it except the overhanging mushrooms; dark night forest mood, no text, 16:9
```
**forest_animals** (TIERE DES WALDES)
```
Sprite sheet, exactly 3 columns and 3 rows of equally sized landscape cells (3:2), each cell one photorealistic forest
animal centered on a dark mossy forest background, same scale: hedgehog, badger, roe deer, wild boar, wolf, raven, bat, lynx,
and last (bottom right) a glowing white stag made of light. No text, no borders
```
**forest_magic** (WALDGEISTER)
```
Sprite sheet, exactly 3 columns and 3 rows of equally sized landscape cells (3:2), each cell one magical forest object
centered on a dark enchanted forest background, same scale: a tiny fairy with glowing wings, a will-o-the-wisp flame, a ring
of mushrooms, a dreamcatcher of twigs, a full moon through branches, a glowing crystal in moss, a garden gnome peeking from
roots, a mandrake root, and last (bottom right) the face of an ancient forest god made of bark with glowing eyes. No text
```
**cyber_frame**
```
Photorealistic frame of a cyberpunk slot machine seen frontally and filling the whole image: the border is chrome and black
metal covered in glowing neon tubes (magenta and cyan), small screens showing only abstract patterns, thick cables and
warning stripes; a small delivery drone hangs from the top edge into the central area and a neon lucky cat sits on the lower
right corner; the entire central area is one solid pure black rectangle with slightly rounded corners, about 80 percent of
the width and 85 percent of the height, nothing drawn inside it except the hanging drone; no text, 16:9
```
**cyber_konzern** (KONZERN)
```
Sprite sheet, exactly 3 columns and 3 rows of equally sized landscape cells (3:2), each cell one photorealistic cyberpunk
object centered on a dark neon background, same scale: briefcase full of credit chips, security robot, black corporate logo
cube with glowing edges, surveillance camera, chip card, server rack, android executive in a suit, hover limousine, and last
(bottom right) a glowing AI core sphere. No text, no borders
```
**cyber_netzgeister** (NETZGEISTER)
```
Sprite sheet, exactly 3 columns and 3 rows of equally sized landscape cells (3:2), each cell one glowing digital creature
centered on black with faint data rain, same scale: glitching mask, spider made of circuit boards, spiked virus sphere,
holographic skull, fish made of pixels, eye made of scanlines, hand made of fiber optics, wireframe face, and last (bottom
right) a glowing AI core sphere. No text, no borders
```
**future_frame**
```
Photorealistic frame of a flashy 1985 casino slot machine seen frontally and filling the whole image: the border is gold with
mirrors, chrome, rows of blinking light bulbs, red and blue neon stripes; a small glowing flux capacitor device (box with a Y
of light tubes) sits on the upper right corner and a pink hoverboard leans on the lower left corner into the central area;
the entire central area is one solid pure black rectangle with slightly rounded corners, about 80 percent of the width and
85 percent of the height, nothing drawn inside it except the hoverboard; no text, 16:9
```
**future_1885** (WILDER WESTEN)
```
Sprite sheet, exactly 3 columns and 3 rows of equally sized landscape cells (3:2), each cell one photorealistic wild west
object centered on a dusty sepia background, same scale: revolver, cowboy hat, sheriff star, horseshoe, cactus, steam
locomotive, whiskey bottle, wanted poster without readable text, and last (bottom right) a round clock face showing four
minutes past ten with lightning. No text, no borders
```
**future_2015** (ZUKUNFT 2015)
```
Sprite sheet, exactly 3 columns and 3 rows of equally sized landscape cells (3:2), each cell one photorealistic object from
the future of 2015 as imagined in the 1980s, centered on a dark glossy background, same scale: pink hoverboard, flying car,
self-lacing sneaker, holographic shark, small home fusion reactor on a car, delivery drone, video glasses, robot waiter, and
last (bottom right) a round clock face showing four minutes past ten with lightning. No text, no borders
```
**space_frame** (optional, Space-Thema)
```
Photorealistic frame of a space station slot machine seen frontally and filling the whole image: the border is brushed steel
and dark panels with small blinking indicator lights, orange warning stripes, a round porthole with stars in the upper left
corner and a small astronaut figure holding on to the lower right corner; the entire central area is one solid pure black
rectangle with slightly rounded corners, about 80 percent of the width and 85 percent of the height, nothing drawn inside
it; no text, 16:9
```

## Anweisung an den Bot

Erzeuge die 10 Bilder aus `docs/slots_plan.md` (Abschnitt "Prompts") und speichere sie als PNG unter
`assets/slots/raw/<name>.png`: `forest_frame`, `forest_animals`, `forest_magic`, `cyber_frame`, `cyber_konzern`,
`cyber_netzgeister`, `future_frame`, `future_1885`, `future_2015`, `space_frame`. Rahmen 16:9, mindestens 1600 Pixel
breit, die Mitte eine einzige reine Schwarzfläche (nur die beschriebenen Teile dürfen hineinragen). Symbolbögen exakt
3x3 gleich große Querformat-Zellen 3:2, Jackpot-Symbol unten rechts. Kein lesbarer Text. Danach auf den Branch
`claude/new-session-3cbx1m` committen und pushen (vorher `git pull --no-rebase origin claude/new-session-3cbx1m`).
