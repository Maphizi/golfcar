# Thema ZURÜCK IN DIE ZUKUNFT – Plan, Bilder, Prompts

Das Thema `future` (Taxistand: ZURÜCK IN DIE ZUKUNFT, Zeitreise-Fahrer) bekommt wie GREEN und CYBERPUNK sechs eigene
Modi auf den Tasten 2–7. Gleiches Prinzip: echtes Bildmaterial (Szenenfoto + Spritebögen) plus Shader-Leben, alles
reagiert auf die Musik (Bass, Beat, Mitten, Höhen, Energie, Drop, Stille), Knüppel und Tasten haben feste Rollen.
Roter Faden: vier Epochen (1885 Wilder Westen, 1955 Kleinstadt, 1985 Vorstadt, 2015 Zukunft), 88 Meilen pro Stunde,
1,21 Gigawatt, Feuerspuren, der Uhrturm um 22:04, das verblassende Foto.

Die Bilder legt der Bot unter **`assets/future/raw/`** mit exakt den Dateinamen unten ab (PNG oder WEBP, Name ohne
Endung muss stimmen). Daraus baut `scripts/future_assets.sh` die Atlanten unter `assets/future/`. Bis die Bilder da
sind, laufen die Modi mit leeren Texturen.

| Taste | Space-Modus | Zukunft-Modus | Datei | Kurz |
|---|---|---|---|---|
| 2 | Navigationscomputer | **ZEITSPRUNG** `timejump` | `visualizers/scenes/timejump.py` | Gas geben bis 88, Blitz, Sprung in eine andere Epoche |
| 3 | Schwarzes Loch | **FLUXKOMPENSATOR** `flux` | `visualizers/scenes/flux.py` | Dinge aus allen Epochen werden zu Feuerspuren und Blitzen |
| 4 | HAL 3000 | **UHRTURM** `clocktower` | `visualizers/scenes/clocktower.py` | Gewitter am Uhrturm, Zeiger im Takt, acht Fenster = Spektrum |
| 5 | Slotmaschine | **ALMANACH** `almanacslots` | `visualizers/scenes/almanacslots.py` | Casino-Automat aus dem falschen 1985 |
| 6 | Lagerfeuer | **MARKTPLATZ** `square` | `visualizers/scenes/square.py` | Derselbe Platz in vier Epochen, Zeitsprung per Knüppel |
| 7 | Systemfehler | **PARADOXON** `paradox` | `visualizers/scenes/paradox.py` | Die Zeitlinie bricht, Anachronismen, das Foto verblasst |

Stimme: der verrückte Professor (`de_DE-karlsson-low`, schneller, etwas höher, leicht atemlos, ohne Roboter, Hauch
Hall wie in der Werkstatt), eigene Sätze je Modus ("Großer Gott!", "Wo wir hinfahren, brauchen wir keine Straßen").

---

## Taste 2 – ZEITSPRUNG (`timejump`)

Fahrt aus der Windschutzscheibe der Zeitmaschine. Startknopf = Gas geben, der Tacho steigt mit der Energie der Musik
(laute Musik = schneller; unter Stille rollt man aus), Fahrt endet nur per Kippschalter (Zeitkreise aus, wie
Navigationscomputer). Erreicht der Tacho 88, zündet der Zeitsprung: Blaulicht-Blitze um die Karosserie, Weißblitz,
Feuerspuren auf der Straße, und die Straße ist in einer anderen Epoche (1885 Wilder Westen, 1955 Kleinstadt, 1985
Vorstadt, 2015 Zukunft mit fliegenden Autos; Reihenfolge zufällig, nie zweimal dieselbe). Die Zeitkreis-Anzeige
(Zielzeit / Jetzt / Zuletzt) läuft als Overlay in roten, grünen und gelben Ziffern. Bass = Motor und Kamera-Vibration,
Beat = Straßenlaternen und Schilder blitzen, Feuerspuren flackern, Höhen = Funken/Staub/Regen je Epoche, Mitten =
Verkehr dichter. Drop = sofortiger Zeitsprung. Knüppel links/rechts = Spur wechseln (Bild kippt), oben = Hupe
(Verkehr weicht, in 2015 fliegen alle hoch), unten = Zeitkreise umschalten (nächste Epoche vorwählen, Anzeige
rattert). Ereignisse alle 30–60 s je Epoche: Pferdekutsche/Zug (1885), Mistwagen/Tanzball (1955), Skateboarder/
Einkaufszentrum (1985), Hoverboards/Hologramm-Hai (2015), Gewitter (immer).

Bilder:
- `timejump_cockpit` (16:9): Blick vom Fahrersitz einer Zeitmaschine aus Edelstahl: Armaturenbrett mit Schaltern,
  Kabeln, Röhren, Zeitkreis-Kasten mit drei dunklen Anzeigen (ohne Ziffern), Flügeltür-Rahmen am Rand. Die ganze
  Windschutzscheibe ist **reines Schwarz** (dort wird die Epoche eingeblendet).
- `timejump_1885`, `timejump_1955`, `timejump_1985`, `timejump_2015` (je 16:9): die Straße geradeaus zum Horizont aus
  niedriger Autoperspektive, ohne Armaturenbrett, Epoche siehe Prompts.
- `timejump_traffic` (8x4 Bogen, schwarz): eine Reihe je Epoche, acht Dinge, die auf oder über der Straße
  vorbeiziehen (von hinten/schräg).

## Taste 3 – FLUXKOMPENSATOR (`flux`)

Gegenstück zum Schwarzen Loch: der leuchtende Fluxkompensator in der Werkstatt, drei Lichtarme, die zur Musik
pulsen. Knüppel links/rechts wirft ein Objekt aus den Epochen von dieser Seite hinein (Hoverboard, Almanach,
Skateboard, E-Gitarre, Plutoniumkoffer, Walkie-Talkie, Kassette, Hund, Cowboyhut, Modellzug, Wecker, Videokamera,
Brief, Turnschuh …): es wird angezogen, zieht zwei Feuerspuren hinter sich her, dehnt sich zur Zeitschleife und
löst sich in Blitze auf, die in die drei Arme laufen. Oben = Gewitter (Blitze schlagen in den Blitzableiter ein,
Schleifen tanzen), unten = Paradoxon: alles kommt rückwärts wieder heraus, dazu verblasst das Fahrerfoto
(`assets/taxi/future/driver.png`) und kehrt mit dem Beat zurück. Startknopf = 1,21 Gigawatt (Überladung: Weißblitz,
Lichtbögen über alle Kabel, Bild zittert). Kippschalter = Nahaufnahme. Bass = Arme pulsen, Beat = Blitze, Höhen =
Funken, Drop = Farbwechsel und die Zeitschleifen laufen rückwärts.

Bilder:
- `flux_scene` (16:9): Dunkle Erfinderwerkstatt/Garage bei Nacht, in der Mitte ein leuchtender Fluxkompensator (Kasten
  mit Y aus drei Lichtröhren, die sich in der Mitte treffen), ringsum Kabel, Röhren, Oszilloskope, Werkzeug, Tafel
  mit Kreideskizzen ohne Text, Funken.
- `flux_objects` (6x4 Bogen, schwarz): 24 Objekte zum Hineinwerfen (siehe oben), einzeln auf Schwarz.

## Taste 4 – UHRTURM (`clocktower`)

Gegenstück zu HAL: der Uhrturm des Rathauses in einer Gewitternacht, das Zifferblatt ist das Gesicht. Der Sekunden-
zeiger tickt auf jeden Beat, die großen Zeiger kriechen mit der Energie Richtung 22:04; Bass = die Wolken leuchten
von innen und der Turm bebt, Mitten = Wetterleuchten, Höhen = Regen und Funken am Kabel. Acht Schaufenster des
Platzes unter dem Turm sind die acht Spektrumbänder. Beat = Lauflicht durch die Fenster. Drop = der Blitz schlägt in
den Turm, das Kabel glüht, Weißblitz, Zeiger springen auf 22:04. Stille = Wolken ziehen, nur Wetterleuchten. Knüppel
links = der Professor hängt am Zifferblatt und kämpft mit dem Kabel (Posen auf den Beat), rechts = die Zeitmaschine
rast über den Platz und hinterlässt Feuerspuren, oben = beide (der große Moment), unten = Tanzball (Girlanden-Lichter
über dem Platz, ein Paar aus 1955 tanzt zum Beat). Startknopf = 22:04 (Blitz von Hand, Uhr bleibt stehen).
Kippschalter = Nahaufnahme aufs Zifferblatt.

Bilder:
- `clocktower_scene` (16:9): Rathaus mit hohem Uhrturm bei Nacht im Gewitter, großes rundes Zifferblatt **ohne
  Zeiger** (leer, beleuchtet), ein Kabel vom Turm hinunter zu einer Straßenlaterne, unten eine Häuserzeile mit acht
  gleich großen dunklen Schaufenstern nebeneinander, nasser Platz, kein Text.
- `clocktower_figures` (8x3 Bogen, schwarz): Reihe 1 ein verrückter Professor mit wirren weißen Haaren und weißem
  Kittel in acht Posen (hängt an einem Zeiger, klettert, zeigt, jubelt, erschrickt, zieht an einem Kabel, winkt,
  rutscht ab), Reihe 2 eine silberne Flügeltür-Sportwagen-Zeitmaschine in acht Ansichten einer Fahrt von links nach
  rechts (seitlich, mit leuchtenden Zeitkreisen, zuletzt mit Feuerspuren), Reihe 3 ein tanzendes Paar aus den 50ern in
  acht Tanzposen.

## Taste 5 – ALMANACH (`almanacslots`)

Casino-Automat aus dem falschen 1985 (das Hotel-Casino des Schurken), drei Fenster, Spiellogik der Slotmaschine.
Knüppel links/rechts = Einsatz (1955 Cent 10, 1985 Dollar 50, 2015 Kreditkarte 200), Startknopf = drehen. Neonröhren
und Spiegel im Foto pulsen mit dem Bass, Lauflicht durch die drei Säulen auf den Beat, Höhen = Funken, Drop =
Blitz und die nächste Drehung schneller. Gewinne: klein = Dollarscheine regnen, groß = Feuerspuren laufen durch
das Bild und der Professor tanzt, Jackpot (Uhr 22:04 dreifach) = Blitz, die Zeitmaschine fährt durch den Automaten,
alles kippt kurz in Schwarzweiß wie 1955.

Bilder:
- `almanac_scene` (16:9): Ein einzelner protziger Spielautomat frontal in einem 80er-Jahre-Casino (Gold, Spiegel,
  Neon, Teppich mit Muster), drei gleich große leere dunkle Fenster nebeneinander in der Mitte, rechts ein Hebel,
  kein Text.
- `almanac_symbols` (3x3 Bogen, schwarz, Querformat-Zellen 3:2): Hoverboard, Sportalmanach (Buch, kein lesbarer
  Text), Plutoniumkoffer, Skateboard, Kassette, Hund, selbstschnürender Turnschuh, Fluxkompensator, zuletzt (unten
  rechts) ein Zifferblatt, das 22:04 zeigt = Jackpot.

## Taste 6 – MARKTPLATZ (`square`)

Gegenstück zum Lagerfeuer/Herzbaum: derselbe Marktplatz mit dem Rathaus in vier Epochen. Knüppel links/rechts =
Zeitsprung in die vorige/nächste Epoche (Weißblitz, Feuerspuren laufen über den Platz, Überblendung), sonst wandert
die Zeit alle `cycle_minutes` von selbst. Die Stadt lebt mit der Musik: Fenster und Schilder leuchten mit dem Bass,
Beats laufen als Lichtwelle durch die Häuserzeile, Mitten = Verkehr/Passanten-Lichter, Höhen = Staub (1885), Regen
(1955), Neon-Flackern (1985), Hologramm-Funken (2015). Drop = Blitz in den Uhrturm und Sprung in eine zufällige
Epoche. Oben = Feuerwerk (1885 Kanone, 2015 Drohnenshow), unten = Stromausfall (Platz geht aus, kommt mit Beats
zurück), Startknopf = Blitz, Kippschalter = Nahaufnahme auf das Zifferblatt.

Bilder:
- `square_1885`, `square_1955`, `square_1985`, `square_2015` (je 16:9): derselbe Marktplatz mit Rathaus und Uhrturm in
  der Mitte, vom selben Standpunkt, bei Nacht, Epoche siehe Prompts.
- `square_particles` (8x3 Bogen, transparent oder schwarz): Reihe 1 Staub, Steppenläufer, Funken, Hufeisen, Patronen,
  Federn, Glut, Rauch; Reihe 2 Konfetti, Luftballon, Schallplatte, Milchshake-Becher, Luftschlange, Kassette,
  Pappbecher, Neonsplitter; Reihe 3 Hologramm-Scherben, Mini-Drohne, Lichtpunkt, Feuerspur-Stück, Regentropfen,
  Blatt, Pizza, Schneeflocke.

## Taste 7 – PARADOXON (`paradox`)

Gegenstück zum Systemfehler/Überdosis: die Zeitlinie bricht. Wellen: Störung (10 s, "ZEITKREISE DEFEKT", die
Anzeigen rattern, Puls steigt), Paradoxon (30 s, Doppelbilder, Farben kippen in Sepia und Blitzblau, Anachronismen
lauern an den Rändern und springen auf den Beat: Dinosaurier, Cowboys, Ritter, Roboter, deine eigene Hand wird
durchsichtig), 1,21 Gigawatt (20 s, Blitze überall, Negativ-Blitze und Bildsprünge auf den Beat, das Fahrerfoto
(`assets/taxi/future/driver.png`) verblasst Stück für Stück, Flüstertexte "DU LÖSCHST DICH AUS", "DEINE ELTERN HABEN
SICH NIE GETROFFEN"), Auslöschung (8 s, Schwarz mit Filmriss und Sepia-Nachbildern, dann "ZEITLINIE WIEDERHERGESTELLT.
NOCH EINMAL."). Bass = Herzschlag, Beat = Bildsprung, Höhen = Filmkorn und Knistern, Drop = Blitz. Knüppel
links/rechts = Gegenmaßnahme (Zeitkreise reset, Almanach verbrennen, Brief an den Professor, Blitzableiter, 88 mph):
kurz besser, dann schlimmer; oben = Zeitkreise neu starten (Bild rollt, Ziffern rattern); unten = Foto ansehen
(Dunkel, nur das verblassende Foto atmet); Startknopf = der Professor kommt mit der Zeitmaschine und holt dich fünf
Sekunden in ein klares Bild; Kippschalter AN = zurück in 1985 (klar), AUS = Rückfall.

Bilder:
- `paradox_scene` (16:9): Erfinderwerkstatt bei Nacht, Zeitkreis-Kasten auf dem Tisch mit sprühenden Funken,
  Oszilloskope mit Störbildern, Tafel mit Kreidezeichnungen (keine Worte), eine leere Polaroid-ähnliche Fotoecke
  auf dem Tisch, Blitzlicht durch das Fenster.
- `paradox_intruders` (4x3 Bogen, schwarz): 12 Anachronismen: Tyrannosaurus, Revolverheld, Ritter in Rüstung,
  römischer Legionär, Rocker aus den 50ern mit Lederjacke, Polizei-Schwebeauto, Chrom-Roboter, Höhlenmensch, Pirat,
  Astronaut, Mammut, halb durchsichtige verblassende Person.

---

## Prompts (für den Bot; Dateiname = Name ohne Endung)

Alle Bilder fotorealistisch, kein lesbarer Text, keine Wasserzeichen, keine Logos. Szenen 16:9, mindestens 1600 Pixel
breit. Bögen genau mit der Spalten-/Reihenzahl, gleich große Zellen, Objekte zentriert, gleiche Größe je Zelle, reines
Schwarz als Hintergrund (bei `square_particles` gern transparent).

**timejump_cockpit**
```
Photorealistic first-person view from the driver seat of a stainless steel time machine sports car at night, dashboard full of toggle switches, cables, vacuum tubes and a time circuit box with three dark empty digital displays, gullwing door frames at the edges, the entire windshield area is solid pure black with nothing visible through it, cinematic, 16:9
```
**timejump_1885**
```
Photorealistic low car-level view straight down a dusty main street of a wild west town in 1885 at dusk, wooden saloons and shops with porches on both sides, hitching posts, a windmill, mountains at the horizon, tumbleweeds, warm orange sky, no people, no text, 16:9
```
**timejump_1955**
```
Photorealistic low car-level view straight down the main street of an American small town in 1955 at night, 1950s diner with neon tubes, a movie theater marquee without readable text, vintage parked cars, street lamps, trees, clear starry sky, no people, no text, 16:9
```
**timejump_1985**
```
Photorealistic low car-level view straight down a suburban road in 1985 at night, a shopping mall with a big empty glowing sign in the distance, parked 1980s cars, sodium street lights, power lines, pine trees, light fog, no people, no text, 16:9
```
**timejump_2015**
```
Photorealistic low car-level view straight down the main street of a futuristic small town in 2015 as imagined in the 1980s, flying cars in the sky, holographic billboards without text, glossy curved buildings, neon trim, rain-wet road, floating traffic lights, no people, no text, 16:9
```
**timejump_traffic**
```
Sprite sheet, 8 columns and 4 rows, pure black background, same scale, centered, seen from behind at a slight angle. Row 1 (1885): horse rider, stagecoach, steam locomotive, covered wagon, cactus, tumbleweed, windmill, longhorn bull. Row 2 (1955): pink convertible, yellow school bus, milk truck, bicycle, manure truck, pickup truck, police car of the 1950s, ice cream van. Row 3 (1985): station wagon, pickup truck, skateboarder, delivery van, yellow taxi, motorcycle, jeep, sports car. Row 4 (2015): flying car, hover taxi, delivery drone, hoverboard rider, flying police car, pizza drone, hover bus, holographic shark. No text, no borders
```
**flux_scene**
```
Photorealistic dark inventor's garage workshop at night, in the center a glowing flux capacitor device: a metal box with three glass tubes of white-blue light forming a Y that meet in the middle, surrounded by cables, vacuum tubes, oscilloscopes, tools, a chalkboard with chalk sketches and no words, sparks, volumetric light, no people, no text, 16:9
```
**flux_objects**
```
Sprite sheet, 6 columns and 4 rows, pure black background, same scale, centered, photorealistic objects: hoverboard, thick sports almanac book without readable text, skateboard, electric guitar, yellow plutonium case, walkie talkie, cassette tape, shaggy dog sitting, cowboy hat, model steam train, alarm clock, 1980s video camera, sealed letter, sneaker, old soda bottle, jukebox, bicycle, sunglasses, lightning rod, polaroid photo, pizza, microwave oven, satellite dish, vintage radio. No text, no borders
```
**clocktower_scene**
```
Photorealistic town hall with a tall clock tower at night during a thunderstorm, the large round clock face is lit but completely blank with no hands and no numbers, a thick cable runs from the clock tower down to a street lamp, below a row of shops with eight identical dark rectangular shop windows side by side, wet town square, dramatic clouds, no people, no text, 16:9
```
**clocktower_figures**
```
Sprite sheet, 8 columns and 3 rows, pure black background, same scale, centered, full body. Row 1: a mad scientist with wild white hair and a white lab coat in eight poses (hanging from a bar, climbing, pointing, cheering, frightened, pulling a cable, waving, slipping). Row 2: a silver stainless steel sports car with gullwing doors in eight side views of a drive from left to right, lights on, the last two with fire trails behind the wheels. Row 3: a 1950s couple in eight dance poses. No text, no borders
```
**almanac_scene**
```
Photorealistic single flashy slot machine seen frontally in a gaudy 1980s casino, gold trim, mirrors, neon tubes, patterned carpet, three identical empty dark rectangular windows side by side in the center of the machine, a lever on the right side, more machines blurred in the background, no readable text, 16:9
```
**almanac_symbols**
```
Sprite sheet, 3 columns and 3 rows, each cell a single photorealistic object centered on pure black background, same scale, landscape cells 3:2. Row 1: pink hoverboard, thick sports almanac book without readable text, yellow plutonium case. Row 2: skateboard, cassette tape, shaggy dog. Row 3: self-lacing sneaker, glowing flux capacitor, round clock face showing four minutes past ten with lightning. No text, no borders
```
**square_1885**
```
Photorealistic town square with a town hall and clock tower in the center in 1885 at night, dirt square, wooden buildings, horses at hitching posts, oil lamps, a saloon on the left, construction scaffolding on the tower, stars, no people, no text, 16:9
```
**square_1955**
```
Photorealistic town square with a town hall and clock tower in the center in 1955 at night, paved square with lawn, 1950s cars parked, a diner with neon tubes on the left, a movie theater marquee without text on the right, warm street lamps, no people, no text, 16:9
```
**square_1985**
```
Photorealistic town square with a town hall and clock tower in the center in 1985 at night, slightly run down, an aerobics studio with neon on the left, a video rental store on the right, 1980s cars, sodium street lights, no people, no text, 16:9
```
**square_2015**
```
Photorealistic town square with a town hall and clock tower in the center in 2015 as imagined in the 1980s at night, glossy renovated buildings, holographic billboards without text, flying cars above, floating lamps, a pond in the square, neon trim, rain-wet ground, no people, no text, 16:9
```
**square_particles**
```
Sprite sheet, 8 columns and 3 rows, transparent background, same scale, centered. Row 1: dust puff, tumbleweed, spark, horseshoe, bullet, feather, ember, smoke wisp. Row 2: confetti piece, balloon, vinyl record, milkshake cup, streamer, cassette tape, paper cup, neon shard. Row 3: holographic shard, mini drone, light dot, piece of fire trail, rain drop, leaf, small pizza, snowflake. No text, no borders
```
**paradox_scene**
```
Photorealistic inventor's workshop at night, a time circuit box on the desk throwing sparks, oscilloscopes showing distorted waveforms, a chalkboard with chalk drawings and no words, an empty polaroid photo frame on the desk, lightning flashing through the window, cables everywhere, no people, no text, 16:9
```
**paradox_intruders**
```
Sprite sheet, 4 columns and 3 rows, each cell one figure centered on pure black background, same scale, photorealistic: tyrannosaurus, wild west gunslinger, knight in armor, roman legionary, 1950s greaser with leather jacket, hovering police car, chrome robot, caveman, pirate, astronaut, woolly mammoth, half transparent fading person. No text, no borders
```

---

## Anweisung an den Bot

Erzeuge die 19 Bilder oben mit den Prompts, speichere sie als PNG unter `assets/future/raw/<name>.png` (Name exakt wie
in Fettschrift, ohne Endung im Prompt-Titel) und committe sie auf den Branch `claude/new-session-3cbx1m`. Szenen 16:9
mit mindestens 1600 Pixel Breite, Bögen mit exakt der genannten Spalten- und Reihenzahl auf reinem Schwarz
(`square_particles` gern transparent). Fehlt ein Bild, läuft der Modus trotzdem, nur leer.
