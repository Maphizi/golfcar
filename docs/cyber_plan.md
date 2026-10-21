# Thema CYBERPUNK – Plan, Bilder, Prompts

Das Thema `cyber` (Taxistand: CYBERPUNK, Neon-Fahrer) bekommt wie THE POWER OF THE GREEN sechs eigene Modi auf den
Tasten 2–7. Alle Modi folgen dem bewährten Prinzip: echtes Bildmaterial (Szenenfoto + Spritebögen) plus Shader-Leben,
alles reagiert auf die Musik (Bass, Beat, Mitten, Höhen, Energie, Drop, Stille), Knüppel und Tasten haben feste Rollen.

Die Bilder legt der Bot unter **`assets/cyber/raw/`** mit exakt den Dateinamen unten ab (PNG oder WEBP, Name ohne
Endung muss stimmen). Daraus baut `scripts/cyber_assets.sh` die Atlanten. Bis die Bilder da sind, laufen die Modi
mit leeren Texturen (kein Absturz, nur leer).

| Taste | Space-Modus | Cyber-Modus | Datei | Kurz |
|---|---|---|---|---|
| 2 | Navigationscomputer | **NEONFAHRT** `neonrace` | `visualizers/scenes/neonrace.py` | Fahrt durch die Regenstadt, Ereignisse unterwegs |
| 3 | Schwarzes Loch | **DER KERN** `core` | `visualizers/scenes/core.py` | Reaktorkern verschluckt Drohnen, Autos, Androiden als Datenstrom |
| 4 | HAL 3000 | **DAS ORAKEL** `oracle` | `visualizers/scenes/oracle.py` | Hologramm-Maske in der Serverhalle, acht Neonzeichen = Spektrum |
| 5 | Slotmaschine | **PACHINKO** `cyberslots` | `visualizers/scenes/cyberslots.py` | Neon-Automat, Einsatz in Eddies |
| 6 | Lagerfeuer | **DACHTERRASSE** `rooftop` | `visualizers/scenes/rooftop.py` | Regen, Stadt pulst, Wetter wechselt |
| 7 | Systemfehler | **BLACK ICE** `blackice` | `visualizers/scenes/blackice.py` | Einbruch ins Netz, Daemonen, Flatline |

Stimme: eigene KI-Stimme (`de_DE-kerstin-low`, leicht robotisch, kurzer Hall), eigene Sätze je Modus.

---

## Taste 2 – NEONFAHRT (`neonrace`)

Fahrt durch eine Neonstadt bei Nacht und Regen, aus der Windschutzscheibe. Startknopf = losfahren, Fahrt endet nur per
Kippschalter (wie Navigationscomputer). Geschwindigkeit folgt der Energie der Musik (Straßenlicht-Streifen, Regen
schräger), Bass = Motor/Kamera-Vibration, Beat = Neonschilder und Werbe-Hologramme blitzen im Takt, Höhen =
Regentropfen auf der Scheibe funkeln, Mitten = Scheibenwischer-Tempo. Drop = Nitro: Tunnel aus Licht, Farben kippen.
Knüppel links/rechts = Spur wechseln (Bild kippt, Hologramme ziehen vorbei), oben = Hupe/Lichthupe (alle Schilder
blitzen), unten = Rückspiegel-Blick (Verfolger). Ereignisse alle 30–60 s: Polizeidrohnen, Werbeblimp, Regensturm,
Tunnel, Konzernturm, Straßenmarkt, Kirschblüten-Allee.

Bilder:
- `neonrace_scene` (16:9): Blick aus der Windschutzscheibe eines Autos auf eine nasse Neonstraße bei Nacht, die
  Straße läuft zum Horizont, links und rechts Hochhäuser mit Neonschildern (ohne lesbaren Text), Regen, Pfützen
  spiegeln Neon, Armaturenbrett unten im Bild leicht angeschnitten. Das Bild ist die feste Platte, die Straße wird
  im Shader bewegt.
- `neonrace_holo` (8x3 Bogen, schwarz): Hologramm-Werbungen und Neonschilder als Einzelobjekte (Geisha-Gesicht,
  Ramen-Schale, Koi, Drache, Pfeil, Herz, Cyber-Auge, Katze, Totenkopf, Pillen, Sushi, Schriftzeichen-Tafeln ohne
  echte Worte usw.), leuchtend, auf Schwarz.
- `neonrace_traffic` (8x2 Bogen, schwarz): Reihe 1 acht Fahrzeuge von hinten (Schwebeautos, Motorräder, Taxi, Truck,
  Polizeidrohne), Reihe 2 acht fliegende Objekte (Drohnen, Werbeblimp, Polizeigleiter, Lieferdrohne, Papierlaterne,
  Kirschblüte, Blimp mit Leuchtfläche, Hologramm-Fisch).

## Taste 3 – DER KERN (`core`)

Gegenstück zum Schwarzen Loch: ein Reaktorkern/Datenwirbel in einer Serverkathedrale. Knüppel links/rechts wirft ein
Objekt (Drohne, Schwebeauto, Android, Vending-Automat, Konzernlogo-Würfel, Katze mit Visor, Ramen-Stand, Cyberdeck …)
von dieser Seite hinein: es wird angesogen, zerfällt in Pixelblöcke und Datenströme, die als Spirale im Takt in den
Kern laufen (Hue-Verschiebung, Glitch). Oben = Drohnenschwarm, unten = Überlast: der Kern spuckt alles als
Trümmer und Lichtbögen aus, Blitz, Druckwelle, 8 s. Startknopf = EMP-Puls (Ring, kurz Schwarzweiß). Kippschalter =
Nahaufnahme. Bass = Kern pulst und Lichtbögen, Beat = Ringe/Blitze, Höhen = Funken, Drop = Kern wechselt Farbe und
dreht rückwärts.

Bilder:
- `core_scene` (16:9): Innenraum einer riesigen Serverkathedrale bei Nacht, in der Mitte ein leuchtender kugelförmiger
  Reaktorkern/Energiewirbel (cyan/magenta), ringsum Serverschränke mit Lichtern, Kabel, Dampf, Gitterboden, kein Text.
- `core_objects` (6x4 Bogen, schwarz): 24 Objekte, die geworfen werden (siehe oben), einzeln auf Schwarz, klar frei.

## Taste 4 – DAS ORAKEL (`oracle`)

Gegenstück zu HAL/Auge: eine riesige holografische Geisha-/KI-Maske schwebt in einer Serverhalle. Bass = Maske atmet
und das Hologramm flackert, Beat = Lauflicht durch die Serverschränke 1-2-3-4 (Muster wechseln), Spektrum = acht
Neonzeichen-Tafeln unter der Maske sind die acht Frequenzbänder (leuchten mit der Bandenergie, flackern bei Spitzen),
Mitten = Datenregen im Hintergrund, Höhen = Funken an den Kabeln. Drop = Maske glitcht und wechselt Ausdruck/Farbe,
Datenexplosion. Stille = Maske erlischt zu einem Drahtgitter. Knüppel links = Samurai-Android tanzt, rechts =
Cyberkatze mit Visor streift herum, oben = beide, unten = Glitch-Modus (Bild zerfällt in Blöcke, Farbkanäle laufen
auseinander). Startknopf = die Maske spricht (Mund-Sequenz, Flüsterzeilen laufen durch). Kippschalter = Nahaufnahme.

Bilder:
- `oracle_scene` (16:9): Dunkle Serverhalle, Mitte oben ein leerer Hologramm-Projektionsrahmen (nur Lichtkegel,
  keine Maske), darunter in einer Reihe acht gleich große dunkle Neon-Tafeln (aus, ohne Text), links und rechts
  Serverschränke mit Lichtpunkten, Kabel, Nebel am Boden.
- `oracle_mask` (8x3 Bogen, schwarz): Reihe 1 acht Ausdrücke derselben holografischen Geisha-Maske (neutral,
  lächelnd, ernst, überrascht, zornig, schlafend/Augen zu, Mund offen sprechend, Mund weit offen), Reihe 2 dieselbe
  neutrale Maske in acht Neonfarben (cyan, magenta, gold, grün, rot, violett, weiß, orange), Reihe 3 acht
  Glitch-Varianten (zerrissen, Blöcke, Drahtgitter, halb aufgelöst, doppelt, Scanlines, Negativ, Rauschen).
- `oracle_figures` (8x3 Bogen, schwarz): Reihe 1 Samurai-Android in acht Tanzposen, Reihe 2 Cyberkatze mit Visor in
  acht Posen (sitzen, gehen, springen, putzen, fauchen, liegen, schauen, winken), Reihe 3 acht leuchtende
  Neon-Schriftzeichen-Tafeln (stilisiert, keine echte Sprache) in verschiedenen Farben für die Bänder.

## Taste 5 – PACHINKO (`cyberslots`)

Neon-Automat in einer Pachinko-Halle, drei Fenster, Spiellogik der Slotmaschine. Knüppel links/rechts = Einsatz
(Chip 10, Deck 50, Implant 200 Eddies), Startknopf = drehen. Neonröhren und Bildschirme im Foto pulsen mit dem Bass,
Lauflicht durch die drei Säulen auf den Beat, Höhen = Funken, Drop = Automat glitcht, nächste Drehung schneller.
Gewinne: klein = Credits regnen, groß = Hologramm-Feuerwerk und der Android tanzt, Jackpot (KI-Kern dreifach) = die
Halle explodiert in Neon, Drohnen bringen Geldkoffer.

Bilder:
- `cyberslots_scene` (16:9): Ein einzelner Neon-Spielautomat frontal in einer Pachinko-Halle, drei gleich große
  leere dunkle Fenster nebeneinander in der Mitte, rechts ein Hebel/Knopf, viele Neonröhren und kleine Bildschirme am
  Gehäuse und ringsum, Regen-Neonlicht durch ein Fenster, kein Text.
- `cyberslots_symbols` (3x3 Bogen, schwarz, Querformat-Zellen 3:2): Neuro-Chip, Lieferdrohne, Ramen-Schale,
  Katana, Cyberdeck, Neonkatze, Credit-Chip, Chrom-Totenkopf, zuletzt (unten rechts) der leuchtende KI-Kern =
  Jackpot.

## Taste 6 – DACHTERRASSE (`rooftop`)

Gegenstück zum Herzbaum/Lagerfeuer: Dachterrasse hoch über der Neonstadt bei Nacht. Die Stadt pulst mit der
Musik: Fenster und Werbeflächen leuchten mit dem Bass, Beats laufen als Welle von Fensterlichtern durch die Türme,
Suchscheinwerfer schwenken mit den Mitten, Höhen = Regentropfen und Funken auf dem Geländer, Energie = Verkehr
(Lichtstreifen). Drop = Blitz über der Stadt, Werbeflächen wechseln Farbe, Feuerwerk. Wetter/Zeit (Knüppel
links/rechts, wandert sonst alle `cycle_minutes`): Regen, Nebel, Säureregen (grün), Schnee/Asche. Oben = Feuerwerk,
unten = Stromausfall (Stadt geht blockweise aus und kommt mit der Musik zurück), Startknopf = Blitz, Kippschalter =
Blick über das Geländer nach unten.

Bilder:
- `rooftop_scene` (16:9): Von einer Dachterrasse mit Geländer im Vordergrund der Blick über eine Neon-Megacity bei
  Nacht und leichtem Regen, Türme mit vielen leuchtenden Fenstern und großen Werbeflächen (ohne Text), fliegende
  Lichter, Nebel zwischen den Gebäuden, links eine Neonreklame am Dach, rechts eine Antenne.
- `rooftop_particles` (8x3 Bogen, transparent oder schwarz): Reihe 1 Regen/Tropfen/Spritzer-Formen und Funken,
  Reihe 2 acht Kirschblüten/Neon-Konfetti/Papierfetzen/Hologramm-Splitter, Reihe 3 Schneeflocken, Aschestücke,
  Glutpartikel, Eiskristalle.

## Taste 7 – BLACK ICE (`blackice`)

Gegenstück zur Überdosis: ein Hack geht schief. Wellen: Einbruch (10 s, Warnung "INTRUSION DETECTED", Scanlines,
Trace-Balken steigt), Trace (30 s, Bildschirme kippen, Doppelbild, Daemonen (ICE) lauern an den Rändern und greifen
auf den Beat an, Datenrauschen), Black ICE (20 s, ein Daemon-Gesicht füllt das Bild, Negativ-Blitze, Bildsprünge, dein
Gesicht als Fahndungsbild mit Barcode, Flüstertexte "TRACE COMPLETE", "WIR WISSEN WO DU BIST"), Flatline (8 s, Schwarz,
EKG-Linie, Piepton-Puls, dann Reboot). Bass = Herzschlag, Beat = Glitch und Bildsprung, Höhen = Rauschen, Drop =
Schrei-Blitz. Knüppel links/rechts = Gegenmaßnahme (Firewall, Proxy, Scrambler, Kill-Switch): kurz besser, dann
schlimmer; oben = Neustart-Versuch (Bild rollt, Bootmeldungen); unten = Stecker ziehen (Schwarz mit Nachbildern);
Startknopf = Hilferuf an den Fixer (Katze mit Visor bringt kurz Ruhe); Kippschalter = Jack out (kurz klar), AUS =
Rückfall.

Bilder:
- `blackice_scene` (16:9): Dunkle Hacker-Kammer, man sitzt vor einer Wand aus Bildschirmen und Kabeln, die
  Bildschirme zeigen nur abstrakte Muster/Störungen (kein Text), rote Warnlampen, Neon durch Jalousien, ein
  Neuro-Kabel liegt über dem Tisch.
- `blackice_daemons` (4x3 Bogen, schwarz): 12 ICE-Daemonen: Chrom-Schädel mit Kabeln, Drahtgitter-Gesicht,
  Auge aus Scanlines, Spinne aus Platinen, Schlange aus Datenblöcken, Maske mit Störungen, Hand aus Glasfasern,
  Totenkopf-Hologramm, Virus-Kugel mit Stacheln, Androidenkopf halb zerstört, Fisch aus Pixeln, Konzernwächter.

---

## Prompts (für den Bot; Dateiname = Name ohne Endung)

Alle Bilder fotorealistisch, kein lesbarer Text, keine Wasserzeichen. Szenen 16:9, mindestens 1600 Pixel breit.
Bögen genau mit der Spalten-/Reihenzahl, gleich große Zellen, Objekte zentriert, gleiche Größe je Zelle.

**neonrace_scene**
```
Photorealistic first-person view through the windshield of a car driving down a wet neon-lit city street at night in the rain, straight road vanishing to the horizon, tall buildings on both sides covered in glowing neon signs without readable text, puddles reflecting magenta and cyan neon, light rain streaks on the glass, dashboard slightly visible at the bottom, cinematic, 16:9
```
**neonrace_holo**
```
Sprite sheet, 8 columns and 3 rows, pure black background, 24 glowing holographic neon signs and advertisements as single objects, same scale, centered: geisha face, ramen bowl, koi fish, dragon, arrow, heart, cyber eye, lucky cat, skull, pills, sushi, abstract glyph panel, cocktail glass, robot head, lotus, rocket, umbrella, crown, lightning bolt, moon, dice, pixel ghost, headphones, abstract circuit symbol. Neon glow, no readable text, no borders
```
**neonrace_traffic**
```
Sprite sheet, 8 columns and 2 rows, pure black background, same scale, centered. Row 1: eight futuristic vehicles seen from behind at night with glowing tail lights (hover car, motorcycle, yellow taxi, cargo truck, police hover car, sports car, tuk tuk, bus). Row 2: eight flying things seen from below and behind (delivery drone, advertising blimp with glowing panel, police glider, paper lantern, cherry blossom, holographic fish, surveillance drone, small airship). No text, no borders
```
**core_scene**
```
Photorealistic interior of a vast server cathedral at night, in the center a huge glowing spherical reactor core of swirling cyan and magenta energy floating above a grated floor, server racks with blinking lights on both sides, thick cables, steam, volumetric light, no people, no text, cinematic, 16:9
```
**core_objects**
```
Sprite sheet, 6 columns and 4 rows, pure black background, same scale, centered, photorealistic cyberpunk objects: delivery drone, hover car, android, vending machine, corporate logo cube, cat with visor, ramen cart, cyberdeck, neon sign, motorcycle, security robot, holographic koi, trash can, umbrella, arcade cabinet, server rack, chrome skull, pill bottle, synthesizer keyboard, street lamp, briefcase of credits, hover bike, surveillance camera, noodle bowl. No text, no borders
```
**oracle_scene**
```
Photorealistic dark server hall at night, in the upper center an empty holographic projection frame made only of light beams and a faint light cone with nothing inside, below it a horizontal row of eight identical dark unlit rectangular neon sign panels, server racks with small lights on the left and right, cables, fog on the floor, cyan and magenta accents, no text, 16:9
```
**oracle_mask**
```
Sprite sheet, 8 columns and 3 rows, pure black background, same scale and position in every cell, a holographic geisha AI mask, frontal. Row 1: eight expressions (neutral, smiling, serious, surprised, angry, eyes closed sleeping, mouth slightly open speaking, mouth wide open). Row 2: the neutral mask in eight neon colors (cyan, magenta, gold, green, red, violet, white, orange). Row 3: eight glitch variants (torn, pixel blocks, wireframe, half dissolved, doubled, scanlines, negative, static noise). No text, no borders
```
**oracle_figures**
```
Sprite sheet, 8 columns and 3 rows, pure black background, same scale, centered. Row 1: a samurai android in eight dance poses, full body. Row 2: a cyber cat with a glowing visor in eight poses (sitting, walking, jumping, grooming, hissing, lying, looking up, raising a paw). Row 3: eight glowing neon sign panels with abstract stylized glyphs that are not real language, each in a different color (red, orange, yellow, green, cyan, blue, violet, magenta). No text, no borders
```
**cyberslots_scene**
```
Photorealistic single neon slot machine seen frontally in a pachinko parlor at night, three identical empty dark rectangular windows side by side in the center of the machine, a lever on the right side, the cabinet covered in neon tubes and small screens showing only abstract patterns, more machines blurred in the background, magenta and cyan light, no readable text, 16:9
```
**cyberslots_symbols**
```
Sprite sheet, 3 columns and 3 rows, each cell a single photorealistic cyberpunk symbol centered on pure black background, same scale, landscape cells 3:2. Row 1: neural chip, delivery drone, ramen bowl. Row 2: katana, cyberdeck, neon lucky cat. Row 3: credit chip, chrome skull, glowing AI core sphere. No text, no borders
```
**rooftop_scene**
```
Photorealistic view from a rooftop terrace at night over a neon megacity in light rain, a wet metal railing in the foreground, towers with thousands of lit windows and large glowing advertising panels without text, flying lights between the buildings, fog, a neon sign on the roof at the left, an antenna at the right, cinematic, 16:9
```
**rooftop_particles**
```
Sprite sheet, 8 columns and 3 rows, transparent background, same scale, centered. Row 1: eight rain drop and splash shapes and sparks. Row 2: eight items: cherry blossom, neon confetti piece, torn paper, holographic shard, neon leaf, small lantern, bubble, feather. Row 3: eight winter items: snowflake, second snowflake, ash flake, ember, ice crystal, frost star, soot, hail. No text, no borders
```
**blackice_scene**
```
Photorealistic dark hacker den at night, a wall of many screens and cables in front of the viewer, the screens show only abstract glitch patterns and noise without text, red warning lights, neon light through window blinds, a neural interface cable lying across the desk, cinematic, 16:9
```
**blackice_daemons**
```
Sprite sheet, 4 columns and 3 rows, each cell one creature centered on pure black background, same scale, photorealistic intrusion countermeasure daemons: chrome skull with cables, wireframe face, eye made of scanlines, spider made of circuit boards, snake made of data blocks, mask with glitches, hand made of fiber optics, holographic skull, spiked virus sphere, half destroyed android head, fish made of pixels, corporate guardian robot. No text, no borders
```
