# Lagerfeuer neu (Space-Taxi, Taste 6): "Rast am Rand der Galaxis"

Komplett neu, ganz entspannt: ein Lagerfeuer auf einem fremden Hochplateau, die Milchstraße über uns, ein riesiger
Ringplanet geht langsam auf, zwei Monde, das Space-Taxi parkt im Hintergrund. Das Feuer ist der Herzschlag der Szene und
atmet mit der Musik: bei leiser Musik nur Glut mit kleinen Flämmchen, bei mittlerer ein normales Lagerfeuer, bei lauter
Musik ein großes Feuer bis über die Steine, beim Drop ein Funkensturm. Nichts blitzt, alles blendet weich über.

## Was passiert (von selbst, alles langsam)
- **Feuerstufen** `GLUT / KLEIN / NORMAL / GROSS` aus drei Flammenbögen (klein, mittel, groß), weiche Überblendung über
  mehrere Sekunden; Stufe folgt der Energie der Musik mit Trägheit (keine Zuckungen), Bass = Flammen pulsen leicht,
  Beat = ein Funke mehr, nie ein Sprung.
- **Holz nachlegen** alle 2-4 Minuten von selbst (oder Knüppel OBEN): ein Scheit fliegt ins Feuer, Funkenwolke, das Feuer
  wird für eine Weile groß und sinkt dann wieder.
- **Fremder Brennstoff** selten (alle 5-8 Minuten, oder beim Drop bei lauter Musik): ein glühender Kristall fällt ins
  Feuer, die Flammen werden für 30-60 s blau-violett (eigener Flammenbogen), Funken steigen wie Sterne auf.
- **Funken** steigen auf und werden am Himmel zu Sternen (kurz aufleuchten, verblassen), Rauch zieht träge mit dem Wind.
- **Himmel**: Milchstraße dreht sich unmerklich, Sternschnuppen alle 20-60 s, der Ringplanet steigt über eine Stunde
  (`cycle_minutes`), Polarlicht-Schleier am Horizont pulst sehr langsam mit dem Bass, die Monde wandern.
- **Leben am Feuer**: ein Kessel über dem Feuer dampft, ab und zu ein Marshmallow am Stock von rechts (ENTER), leuchtende
  Raummotten kreisen um das Feuer (Höhen), ein kleines Alien lugt hinter einem Stein hervor und verschwindet wieder
  (selten), das Taxi im Hintergrund blinkt alle paar Minuten kurz mit den Positionslichtern.
- **Tasten**: Knüppel LINKS/RECHTS = Wind von links/rechts (Flammen und Rauch legen sich, Glut glüht auf), OBEN = Holz
  nachlegen, UNTEN = im Feuer stochern (Funkenwolke, Glut hell), ENTER = Marshmallow, Kippschalter AN = Nahaufnahme des
  Feuers, AUS = zurück.

## Bilder (Bot, nach `assets/campfire/raw/`)
Alle fotorealistisch, kein Text, Szenen 16:9 mindestens 1920 px breit, Bögen auf reinem Schwarz mit exakt der
Spalten-/Reihenzahl, gleich große Zellen, Objekt zentriert.

- `campfire_scene` (16:9): die Szene OHNE Flammen: Feuerstelle aus Steinen mit glühender Glut und verkohlten Scheiten in
  der unteren Bildmitte, drumherum dunkler Fels und Moos eines fremden Hochplateaus, ein paar Sitzsteine, ein Dreibein mit
  Kessel über der Glut, Milchstraße über allem, ein großer Ringplanet rechts tief am Himmel, zwei Monde, am linken Rand
  im Hintergrund ein geparkter futuristischer Taxi-Gleiter mit gelb-schwarzem Muster, warmes Glutlicht auf den Steinen.
- `campfire_flames_small` (8x4, 32 Bilder, Zellen 256): kleine Flämmchen über Glut, fortlaufende Schleife (Bild 32 passt
  zu Bild 1), Fußpunkt unten in der Zelle, reines Schwarz.
- `campfire_flames_mid` (8x4): normales Lagerfeuer, dieselbe Art Schleife, Flammen füllen die Zelle zu zwei Dritteln.
- `campfire_flames_big` (8x4): großes Feuer, hohe züngelnde Flammen bis an den Zellenrand, Funken darin.
- `campfire_flames_blue` (8x4): dasselbe wie mittel, aber blau-violette Flammen mit weißem Kern (fremder Brennstoff).
- `campfire_sparks` (8x2, 16 Teile, Zellen 128): Funken, Glutstücke, glühende Holzsplitter, kleine Aschewölkchen, zwei
  Sternfunken (Vier-Strahl-Glanz).
- `campfire_items` (8x2, 16 Teile, Zellen 192): Holzscheit, Ast, Tannenzapfen, Kristall glühend blau, Stock mit Marshmallow
  roh, Stock mit Marshmallow goldbraun, Stock mit Marshmallow verkohlt, Kessel, Blechtasse, Raummotte leuchtend (3
  Flügelstellungen), kleines Alien das hinter einem Stein hervorlugt (2 Posen: Augen, ganzer Kopf), Sternschnuppe.

## Prompts

**campfire_scene**
```
Photorealistic night scene on a rocky alien plateau: a campfire pit made of stones in the lower center with glowing
orange embers and charred logs but NO flames, a tripod with a hanging kettle above the embers, a few flat sitting
stones around it, dark rock and blue-green moss, in the background on the left a parked futuristic hover taxi with a
yellow and black checker pattern, above everything a brilliant Milky Way, a huge ringed planet low on the right side of
the sky, two small moons, faint green aurora on the horizon, warm ember light on the nearest stones, calm and cozy,
cinematic, 16:9, no text
```
**campfire_flames_small**
```
Sprite sheet, exactly 8 columns and 4 rows, 32 cells of identical size, pure black background, a seamless looping
animation of small gentle flames licking over glowing embers, each cell one frame in order left to right then top to
bottom, the last frame matches the first, flames rooted at the bottom center of each cell, photorealistic fire with
transparent black around it, no text, no borders, no grid lines
```
**campfire_flames_mid**
```
Sprite sheet, exactly 8 columns and 4 rows, 32 cells of identical size, pure black background, a seamless looping
animation of a medium campfire, flames filling about two thirds of each cell, each cell one frame in order left to
right then top to bottom, the last frame matches the first, flames rooted at the bottom center, photorealistic fire,
no text, no borders, no grid lines
```
**campfire_flames_big**
```
Sprite sheet, exactly 8 columns and 4 rows, 32 cells of identical size, pure black background, a seamless looping
animation of a large roaring campfire with tall twisting flames reaching the top of each cell and sparks inside,
each cell one frame in order, the last frame matches the first, flames rooted at the bottom center, photorealistic,
no text, no borders, no grid lines
```
**campfire_flames_blue**
```
Sprite sheet, exactly 8 columns and 4 rows, 32 cells of identical size, pure black background, a seamless looping
animation of a medium campfire burning with blue and violet flames with a white hot core, like an alien crystal
fuel, each cell one frame in order, the last frame matches the first, flames rooted at the bottom center,
photorealistic, no text, no borders, no grid lines
```
**campfire_sparks**
```
Sprite sheet, exactly 8 columns and 2 rows, 16 cells of identical size, pure black background, each cell one small
glowing object centered at the same scale: orange sparks of different shapes, glowing ember chunks, glowing wood
splinters, two small grey ash puffs, two four-pointed star sparkles, photorealistic, no text, no borders
```
**campfire_items**
```
Sprite sheet, exactly 8 columns and 2 rows, 16 cells of identical size, pure black background, each cell one object
centered at the same scale, photorealistic: a firewood log, a dry branch, a pine cone, a glowing blue crystal, a
wooden stick with a raw white marshmallow, a stick with a golden toasted marshmallow, a stick with a burnt black
marshmallow, a black iron kettle, a tin cup, a glowing space moth with wings up, the moth with wings level, the moth
with wings down, a small cute alien peeking with only big eyes visible above a rock, the same alien with its whole
head visible, a shooting star streak, a small pile of embers. No text, no borders
```

## Anweisung an den Bot

Erzeuge die sieben Bilder aus `docs/campfire_plan.md`, Abschnitt "Prompts": `campfire_scene` (16:9),
`campfire_flames_small`, `campfire_flames_mid`, `campfire_flames_big`, `campfire_flames_blue` (je 8x4),
`campfire_sparks` (8x2), `campfire_items` (8x2), als PNG unter `assets/campfire/raw/<name>.png`. Wichtig: die Szene
ohne Flammen (nur Glut), die Flammenbögen als fortlaufende Schleife mit Fußpunkt unten in jeder Zelle, Bögen auf reinem
Schwarz, kein Text. Danach `git pull --no-rebase origin claude/new-session-3cbx1m`, committen und pushen.

## Umsetzung (nach den Bildern)
Neue Szene `visualizers/scenes/campfire.py` + Shader von Grund auf: Plate, vier Flammenbögen (`uFlameA/uFlameB` + Mix,
Stufe aus der Energie mit Trägheit, Schleife mit Überblendung), Feuerlicht auf den Steinen (Luma-Maske nahe der
Feuerstelle, flackert mit den Flammen), Funken/Rauch/Hitzeflimmern, Himmel (Sterne funkeln mit den Höhen, Sternschnuppen,
Planet/Monde wandern über `cycle_minutes`, Polarlicht mit dem Bass), Teilchen aus `campfire_sparks`, Gegenstände aus
`campfire_items` (Scheit fliegt, Kristall, Marshmallow-Stock von rechts mit Röstgrad, Motten, Alien, Taxi-Blinker),
Tasten wie oben, WLED-Profile `campfire`, `campfire_big`, `campfire_blue`, `campfire_log`. Schnitt:
`scripts/campfire_assets.py` (plate, `cut` 8 4 256 256 0 glow für die Flammen, `grid` für sparks/items).
