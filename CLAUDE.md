# GolfCar – Tastenbelegung & Eingabe-Architektur

## PXN-CB1 Buttonboard + Joystick

### Eingabe-Architektur
Der PXN-CB1 hat zwei Linux-Interfaces:
- **event5** (Keyboard-Interface): sendet F-Tasten – wird vom Launcher **ignoriert**
- **event7** (Gamepad-Interface): sendet BTN-Codes – verarbeitet vom Launcher
- **dpad_remap.py**: eigenständiger Thread, liest event7 und injiziert echte Key-Events via uinput

### D-Pad (Joystick-Pfeiltasten)
Werden via `dpad_remap.py` als echte Pfeiltasten injiziert (KEY_LEFT/RIGHT/UP/DOWN).
Funktionieren systemweit in EmulationStation, KITT und allen anderen Apps.

| Richtung | Injizierter Key |
|---|---|
| Links | KEY_LEFT |
| Rechts | KEY_RIGHT |
| Oben | KEY_UP |
| Unten | KEY_DOWN |

Die HID-Codes von Startknopf, Kippschalter und Sprechtaste stehen in `config/settings.toml` `[buttons]`
(`start_code`, `kipp_code`, `kipp_mode`, `talk_code`, `attract_code` 275, `horn_code` 269, `horn2_code` 268, `debounce_ms`), nicht mehr
im Python-Code. Kippschalter A = 271 (unten) / 270 (oben), B = 273 / 272 in `keymap.toml` (Standard: A = `fx`, B = `talk`). Der andere
Drehknopf sendet KEY_VOLUMEUP/DOWN (Lautstärke), der andere KEY_NEXTSONG/PREVIOUSSONG (LED-Helligkeit). REL_MISC schickt das Board
dauernd mit fester Stellung, das ist kein Knopf.
`scripts/input_monitor.py 10` zeigt je Taste Code, Werte, Rate und ob sie von selbst periodisch sendet. `scripts/board_learn.py [sek]`:
5 s Ruhephase (was das Board von selbst schickt), dann 60 s freie Zeit für Hupe Seite 2, Kippschalter A/B (unten/oben) und beide
Drehknöpfe; gibt den Zeitverlauf und die Einträge für `[buttons]`/`keymap.toml` aus (Codes 268/270-274 sind die noch unbelegten Schalter).

### Startknopf (HID-Code 266, `[buttons].start_code`)
→ Injiziert `KEY_ENTER` – universelle Bestätigung / Losfliegen im Planeten-Modus

### Kippschalter (HID-Code 267, `[buttons].kipp_code`) – Toggle
Statusbehaftet (`kipp_mode = "toggle"`) – jeder Druck wechselt den Zustand; `"state"` nimmt value 1/0 als AN/AUS:
- **AN** (erster Druck) → injiziert `KEY_SPACE` → startet Warp-Flug (Planeten)
- **AUS** (zweiter Druck) → injiziert `KEY_BACKSPACE` → stoppt Warp-Flug
- Bei HAL 3000 (Taste 4): nur mit `[hal].kipp_talk = true` (Standard aus) AN = Sprechmodus, AUS = Musik normal

### Sprechtaste (Action `talk` oder `[buttons].talk_code`)
Nur mit `[hal].mic = true` (Standard false: HAL ohne Mikrofon, Musik wird nie abgesenkt).
Eigene Taste, NICHT der Kippschalter (der bleibt SPACE/BACKSPACE für den Navigationscomputer). Entweder
`[buttons].talk_code = N` in settings.toml oder in `config/keymap.toml` `code = N` mit `action = "talk"` (Code steht
im Launcher-Log als "Taste ohne Belegung" oder im input_monitor). Soll der Kippschalter bei HAL den Sprechmodus
schalten, stattdessen `[hal].kipp_talk = true`. Launcher injiziert dann `KEY_F15`; HAL 3000 schaltet damit den Sprechmodus um
(Musik auf `duck_percent`, Mikrofon an; nochmal = zurück; nach `[hal].talk_timeout` s ohne Gespräch von selbst aus).
Test: `scripts/kittctl talk`. Ohne Sprechmodus ist der Mikrofonstream geschlossen (`AudioCapture.suspend()`),
sonst zwingt ein Bluetooth-Headset die Musik ins HFP-Profil (leise, mono). `[capture].avoid_bluetooth_mic` nimmt
ein USB-Mikrofon, wenn vorhanden. Diagnose: `scripts/hal_audio_check.sh`, A2DP-Sperre: `scripts/bt_a2dp_lock.sh`.

### Drehknöpfe
- Lautstärke (Knopf 1, KEY_VOLUMEUP/DOWN): `launcher/music_knob.py`, mpv-Socket oder ohne mpv der ganze Ausgang (wpctl).
- LED-Helligkeit (Knopf 2, KEY_NEXTSONG/PREVIOUSSONG): `launcher/led_knob.py` -> `logs/led_brightness.txt` (Faktor 0..1.4,
  `[led_knob]` step/start/min/max); `wled.knob_factor()` (mtime-Cache) geht in `wled.dim()` ein (HTTP-Profile) und
  `LedStream` führt `bri` alle 0,5 s nach (`bri_prof` x min(1, dim x Faktor)). keymap `led_up`/`led_down`.
- Stimme: `launcher/volume_knob.py` (`[volume].enabled = false` am Cart; Stimme folgt der Musik über `voice_gain`): nimmt
  KEY_NEXTSONG/PREVIOUSSONG (`keys`), REL (`rel`) oder ABS-Achse `axis` -> `logs/voice_volume.txt`, von Piper je Satz gelesen. Grundlautstärke aller
  Sprecher im Verhältnis zur Musik: `[volume].voice_gain` 0.35 (`piper_tts.voice_gain()`, nach mtime gecacht; `voice_volume()` =
  Knopf x Gain, gilt für KITT, HAL, BIBO und die Ansagen in `kitt/announce.py` zusätzlich zu `announce.toml` `volume`).
  REL-Modus nimmt REL_MISC/DIAL/WHEEL/HWHEEL (`REL_CODES`), `RelDecoder` (auch für den Musikknopf): das PXN-CB1 schickt REL_MISC
  ~60/s mit der Knopfstellung, daher 1 s Anlauf, dann zählen nur Änderungen (Differenz 8 Bit, max. 3 Schritte); echte Dreher
  (nur Ereignisse beim Drehen) werden erkannt. Log "Stimme NN% -> voice_volume.txt"; Prüfung auf dem Pi:
  `scripts/voice_knob_check.py [faktor]` (Geräte, 10 s Ereignisse, Datei, Ansage).
- Musik: `launcher/music_knob.py`, KEY_VOLUMEUP/DOWN (immer), REL_MISC/DIAL/WHEEL (`[music].rel`) oder ABS-Achse
  (`[music].axis`) -> mpv-Socket `/tmp/mpv.sock` (`scripts/music.sh` startet mpv mit Socket); ohne mpv (Musik vom Handy)
  stattdessen der ganze Ausgang per `wpctl set-volume -l max_percent @DEFAULT_AUDIO_SINK@ N%+/-` (Stimme folgt mit,
  Stimmenknopf regelt relativ dazu), Log "Musikknopf: ...".
- Knöpfe als Tasten: melden die Dreher BTN-Codes, `config/keymap.toml` `action = "voice_up"/"voice_down"/"music_up"/
  "music_down"` (`Action.VOICE_UP` ..., `core.py` -> `vknob.nudge()`/`mknob.nudge()`).

### Launcher-Tasten (BTN-Codes von event7)

| Physische Taste | BTN-Code | Launcher-Aktion |
|---|---|---|
| Taste 1 (HANDLE) | BTN_MISC | home – Startbildschirm Space-Taxi |
| Taste 2 (CRUISE) | BTN_1 | viz_psychedelic – Navigationscomputer / Hyperraum |
| Taste 3 (FLASH) | BTN_2 | blackhole – Schwarzes Loch |
| Taste 4 (AUDIO) | BTN_3 | hal – HAL 3000 |
| Taste 5 (WIPERS) | BTN_4 | slots – Space-Slotmaschine |
| Taste 6 (MAP) | BTN_5 | campfire – Lagerfeuer |
| Taste 7 (LIGHT) | BTN_6 | error – Systemfehler |
| Taste 8 (E-TALK) | BTN_7 | gaming – Holo-Arcade (RetroPie) |
| Taste 9 | BTN_8 | quit – Beenden |
| Taste 10 | BTN_9 | kitt – Bordcomputer |

Nicht auf dem Board, über `scripts/kittctl <modus>`: droid (BIBO), news, viz_crt, viz_eye, planeten, menu, status.

## Hupe, Effekte und Vorführmodus (`launcher/sfx.py`, `scripts/sfx_build.py`, `launcher/core.py`)
Aktionen `horn`, `horn2` und `fx` (`config/keymap.toml`, Beispiele am Ende der Datei; Taste frei wählbar) spielen die Hupe, den
zweiten Ton bzw. einen zufälligen Effekt des aktuellen Themas aus `assets/sfx/<thema>_horn.wav` / `<thema>_horn2.wav` / `<thema>_fx1..3.wav` (synthetisch erzeugt von
`scripts/sfx_build.py`, 22 kHz mono; davor `assets/sfx/real/` aus `scripts/sfx_fetch.py`: echte Aufnahmen der Scratch-Soundbibliothek
(CC BY-SA 2.0, `SOUNDS` Name -> md5, URL `assets.scratch.mit.edu/internalapi/asset/<md5>.wav/get/`, Rohdateien `assets/sfx/raw/`,
Rezepte `recipes()`; beides gitignored, `update.sh` ruft es auf, `--rebuild` baut neu; fehlt eine Quelle, bleibt die synthetische
Datei); pw-play/aplay nicht-blockierend, `settings.toml` `[sfx] enabled/volume`) und blitzen die
LEDs (WLED-Profile `horn`/`fx`, PXN weiß; `led_back_at` setzt danach das Modusprofil zurück). Hupen-Schalter (fällt in die Mitte
zurück): Seite 1 `[buttons].horn_code` 269 (`dpad_remap.on_horn`, zurück = `HORN_OFF` tut nichts), Seite 2 `[buttons].horn2_code`
(`on_horn2` -> `HORN2` = `horn2`; Code aus dem Launcher-Log "Taste ohne Belegung"). Weitere Kippschalter: `keymap.toml` `code = N`,
je Stellung eine Aktion (`on = "down"` Standard, `on = "up"` beim Zurücklegen -> `EvdevInput.release_bindings`). Vorführmodus `[attract]`:
läuft standardmäßig NUR über den Autopilot-Schalter (`enabled = false`; `DPadRemap._initial_switches()` liest beim Start per
`active_keys()`, ob der Schalter schon AN steht, und meldet das). Mit `enabled = true` zusätzlich Leerlauf-Automatik:
nach `idle_minutes` 5 ohne Eingabe (Launcher-Actions und Board-Events via `DPadRemap.last_event`) wechselt `_attract_tick()`
alle `every_seconds` 180 zufällig durch `ATTRACT_BASE` (Tasten 2-7 im aktuellen Thema, nie dieselbe zweimal, mit Ansage);
jede Eingabe beendet ihn; nicht bei `boot`/`gaming`.
Autopilot-Schalter (echter Kippschalter, `[buttons].attract_code` 275, `dpad_remap.py`): Zustand 1/0 -> `on_attract`-Callback
(Queue `Action.ATTRACT_ON/OFF`, der Launcher liest das uinput-Gerät nicht) + Taste F16/F17 an den laufenden Modus. AN =
`attract_forced`: Vorführmodus sofort (erster Wechsel nach 2 s) und dauerhaft, Eingaben beenden ihn nicht; AUS = Vorführmodus
und Leerlauf-Automatik aus. Anzeige "AUTOPILOT AN/AUS" 2,5 s in der Bildmitte: Engine (`__main__.py`, alle Szenen; Splash
endet dabei nicht) und HAL (`kitt/hal/app.py`); `pygame.key.key_code("F16")`, da pygame keine Konstante hat.

## Startbildschirm (`visualizers/scenes/splash.py`, Modus `boot`)
`config/modes.toml` `[modes.boot]` startet `visualizers.engine splash` statt `launcher.boot_screen`: Titelbild
`assets/splash/scene.png` (3:2, `[scenes.splash] crop` beschneidet auf 16:9) bildfüllend, Sonne (`sun`) glüht mit dem Bass
und wirft drehende Strahlen (Energie), Beat = Zoom-Stoß, Höhen = Staub/Funken, Drop = Weißblitz. Knopf `button = [x, y, w, h]`
als Neonpille im Shader (glüht mit dem Bass, hüpft auf den Beat, Lauflicht am Rand), Text "READY TO LIFT OFF" als Overlay.
Bleibt stehen, bis die erste Taste kommt: jeder KEYDOWN (Knüppel, Startknopf, Kippschalter) postet `pygame.QUIT`, die Engine
endet, der Launcher startet Home; Board-Tasten wechseln über den Launcher direkt den Modus. `boot_seconds > 0` in
`settings.toml` bleibt der Schalter, ob der Startbildschirm überhaupt kommt. Test: `python -m visualizers.engine splash --test-signal`.

## Bildschirme von Black Ice ohne scipy (`visualizers/engine/blobs.py`)
Der Pi hat kein scipy. `blobs.erode/label/sizes/boxes/blur3` ersetzen `ndimage` (Zeilenläufe + Union-Find), genutzt von
`blackice._find_screens` und `timejump._windshield_mask`. Das Ergebnis der Bildschirm-Suche liegt als npz im Bild-Cache
(`images.derived`, `blackice.find_screens_cached`, `warm_cache.py` wärmt es mit).

## Moduswechsel und Startzeit (`visualizers/engine/images.py`, `launcher/process_manager.py`)
Jeder Modus ist ein eigener Prozess; die Zeit bis zum ersten Bild steht im Log `logs/viz_<szene>.log` als Zeile
"Start <szene>: Imports, Fenster, Controller, Shader, Bilder, Audio, erstes Bild". Bilder laden alle Szenen über
`images.load_rgba()` mit npy-Cache unter `.cache/img/` (Schlüssel Pfad+mtime+Größe; `scripts/warm_cache.py` wärmt ihn in
`update.sh` vor). Der Prozessmanager setzt `MESA_SHADER_CACHE_DIR=.cache/mesa`, damit V3D die Shader nur einmal compiliert.
Die Engine ruft `pygame.display.init()`/`font.init()` statt `pygame.init()` (kein SDL-Audio/Mixer). Launcher-Log: "Beende
Modus ... / Modus beendet" zeigt die Stoppzeit (`stop_timeout` in modes.toml).

## Lagerfeuer "Rast am Rand der Galaxis" (`visualizers/scenes/campfire.py`, Space-Taxi Taste 6)
Foto `assets/campfire/scene.png` (Glut OHNE Flammen; Bot-Bilder `assets/campfire/raw/`, Prompts `docs/campfire_plan.md`,
Schnitt `scripts/campfire_assets.sh`: plate, `cut 8 4 128 256 0 glow` für die vier Flammenbögen `flames_small|mid|big|blue.png`
(8x4 à 128x256, Schleife, Fußpunkt unten), `sparks.png` 8x2 à 128 (`cut ... 1 glow`), `items.png` 8x2 à 192 (`cut ... 1 fill`:
0 Scheit, 1 Ast, 2 Zapfen, 3 Kristall, 4-6 Marshmallow roh/golden/verkohlt, 7 Kessel, 8 Tasse, 9-11 Motte, 12/13 Alien Augen/Kopf,
14 Sternschnuppe, 15 Glut). Feuerstufe `level` 0..3 folgt der Energie mit `LEVEL_TAU` 4 s (`_flame_mix`: 0-1 kleine Flammen
klein und blass = Glut, 1-2 klein->mittel, 2-3 mittel->groß) -> `uFlame` (Bogen A, B, Mischung, Größe), `uFlameK` (Deckkraft,
Blauanteil, Bild A, Bild B), `uFrameMix`; Holz `throw()` (OBEN, von selbst `LOG_EVERY` 2-4 min): Flug `flights` -> `_land`:
`boost` (klingt über `BOOST_DECAY` 90 s ab) + Funken; Kristall (`CRYSTAL_EVERY` 2,5-3,5 min oder Drop bei Energie > 0.5) =
`blue_until` 30-60 s blaue Flammen. Funken `Spark` (bis `N_SPARKS` 24, `uSp0..23` = x, y, Zelle, Größe; `star` = am Ende
Sternfunke), UNTEN `poke()` Funkenwolke + `ember`, LINKS/RECHTS `gust()` Wind `uWind` (Böen von selbst `GUST_EVERY`), ENTER
`marshmallow()` (`uMallow`, Röstgrad aus Feuerstufe, `mallow_result`), Motten `uMoth0..2` (Anzahl mit den Höhen), Alien
`ALIEN_EVERY` 90-200 s, Taxi-Lichter `uTaxiT` alle `TAXI_EVERY`, Sternschnuppen `uShoot` alle `SHOOT_EVERY`, Himmel steigt
`uSkyRise` über `cycle_minutes`, SPACE/BACKSPACE `uZoom`. Shader: Feuerlicht `near`/`lightK` auf Steinen (Glut = dunkler als
das Foto), Hitzeflimmern, Rauch im Wind, Kesseldampf `uKettle`, Sterne funkeln mit Höhen, Polarlicht bewegt sich (Band über dem
Horizont, nur grüne Pixel `gm`: Foto verschoben abgetastet = wogende Vorhänge, `rays` ziehen durch, Tempo mit der Energie, Bass). Demo = 8x
schneller. Der Bogen bringt unten eigene Scheite mit (bei großem Feuer hell angestrahlt): im unteren Zellenteil bleibt nur, was
hell UND satt wie eine Flamme ist (`flameLike` aus `lumF`/`satF`), die Scheite kommen aus dem Foto; der Kessel liegt vor den Flammen (`kettleMask`: Ellipse `kettle_box` = Mitte x, y, Radius x, y,
plus Henkelbogen und Tülle). `KITT_CAMPFIRE_CAL=1` zeichnet Flammenzelle (rot), Kesselform (blau) sowie Planet und Ring (grün) zum Einmessen auf dem
Gerät. Saturnring dreht sich: `[scenes.campfire] planet = [x, y, r]`, `ring = [a, b, Neigung, innen/a, dx, dy]` -> `uPlanet`, `uRing`,
`uRingOff`; im Ring-Anulus (Ellipsenraum, hinten vom Planeten verdeckt, vorne davor) laufen Klumpen (Sinus-Harmonische in
Winkel und Radius, innen schneller als außen wie bei Kepler, außen ~1 Umdrehung in 4 min) und Glitzer (mit den Höhen) um;
`uRingT` läuft mit der Energie bis 1,5x schneller. `[scenes.campfire] fire = [x, y, Zellbreite]`, `kettle`, `kettle_box`, `taxi`, `horizon`, `alien`, `mallow`, `cycle_minutes`.
WLED `campfire`, `campfire_big` (Stufe > 2.4), `campfire_blue`, `campfire_log`. Test: `python -m visualizers.engine campfire
--test-signal --demo`.

## Taxistand (`visualizers/scenes/taxi.py`)
Zwei Elemente: links Missionslogo (`mission.png`) mit schwebenden Figuren (`sprites.png` 8x3 à 96 px,
`scripts/taxi_sprites.py`), rechts der Taxischein (Themenfarbe) mit dem Fahrerfoto des Themas als digitale Lizenz: Beat-Zoom (uBeatZoom),
Kreisel in den Augen (`eyes`, `eye_r` in themes.toml), Glitch, Hologramm. Bildsätze je Thema: `assets/taxi/<dir>/`.

## Themen (`launcher/theme.py`, `config/themes.toml`)
Vier Themen: `spacetaxi` (default), `green`, `future`, `cyber`; je `dir` unter assets/taxi/ (mission.png, sprites.png, driver.png),
`eyes`/`eye_r`, `missions`, `driver_title`, `color_a` = Farbe des Scheins. `theme.content()` liefert den Inhaltssatz
("space" = die Weltraum-Programme).

## Waldtresen (`visualizers/scenes/trip.py`, Thema green ersetzt Taste 2)
Themen können Modi ersetzen: `themes.toml` `modes = { viz_psychedelic = "trip" }`, Launcher tauscht in `switch()`.
Browse (Knüppel links/rechts, ENTER = essen) -> eat -> trip (Kippschalter = zurück; Knüppel = Spiegel/Tempo) -> comedown.
Wesen `config/trip.toml` (Zelle im Atlas 5x4), Bilder `assets/trip/` (bar, beings, symbols, tex_*, optional face).
Ereignisse `EVENTS` (alle 20-40 s; `EV_ROOTS` Wurzeln mit optional `assets/trip/roots.png`, `EV_GOD` Waldgott selten:
`GOD_MIN_GAP` 60 s und nur bei `energy > 0.45`, Chance `GOD_CHANCE_PER_S`; nur mit `assets/trip/gods.png` 3x2 à 512,
`GOD_NAMES`/`GOD_LINES`), Symbolsätze `SYMBOL_SETS` (Zellen im 8x5-Atlas). Ein Programm für alle Wesen: Profil (mirrors,
tempo, palette, twist, warp, symbols_key) wird in `_set_phase(PH_TRIP)` gewürfelt, trip.toml-Profile sind unbenutzt.
Kaleidoskop-Varianten `uVariant` (0 klassisch, 1 Tunnel, 2 Blüte, 3 Zellen; `_next_variant`, Überblendung `VARIANT_FADE` 8 s), Wanderung
alle 15-30 s, Beat = Drehstoß. Hintergrund ruhig: eigene Zeit `bg_t` -> `uBgT` (nur `tripImage`, `BG_SLOW` 0.45, kaum Energie-Schwankung),
Drehung `spin` 0.04 statt 0.1, Spiegel/Palette gleiten 5/8 s; Symbole und Ereignisse laufen weiter auf `uTripT`. LED-Board:
`led_state()` -> Programm `trip`. Test: `python -m visualizers.engine trip --demo`.

## Moorsee (`visualizers/scenes/pond.py`, Thema green ersetzt Taste 3)
`themes.toml` `modes = { blackhole = "pond" }`. Waldsee `assets/pond/lake.png` + Seegrund `bottom.png` + Kreaturen-Atlas
`creatures.png` (6x4 à 160, `scripts/trip_assets.py atlas`), Wesen aus `assets/trip/beings.png`/`config/trip.toml`.
`[scenes.pond] vortex = [x, y]`, `water = [y0, y1, x0, x1]` (Wassermaske). Uferleben: `assets/pond/shore.png` (4x6 à 192,
`trip_assets.py slice ... 4 6 192`; Spalte = Stufe, Reihe = Art), Plätze `SHORE` (x, Fußlinie, Größe, Seite, im Wasser),
`plant_stage` 0..3 fließend (`_plants_tick`: Wachstum mit Energie, voll hält, welkt; Stille welkt alles; Drop = alles blüht),
Shader `uPlantN`/`uPlantSN` = (Stufe, Seite ±1/±2 im Wasser, Seed, Alter; Alter < 3 s = Sprießfunken), Sporen `uSporeT`.
LINKS/RECHTS = `sprout(side)`: sofort eine neue Pflanze auf der Seite (leerer Platz, sonst die älteste ersetzt), wächst mit
`SPROUT_RATE` in ~3 s unabhängig von der Musik, Nachbarn bekommen einen Schub. Von selbst nur `AUTO_PER_SIDE` 2 je Ufer alle
`AUTO_PLANT` 8-20 s. Beat im Wasser leise: Ring schwach, Druckwelle/Beben (`uQuakeT`) nur jeder 4. oder kräftige Beat. Wesen fallen nur noch von selbst (`AUTO_THROW`,
nur bei Energie > 0.3; Band im Strudel ~40-60 s), OBEN = Blätterregen, UNTEN = Umkehrung (Fontäne, Seegrund), ENTER = Stein hüpft, SPACE/BACKSPACE =
Zoom. Beat = Ring, Drop = `uFlash`. Wasserebene perspektivisch: Shader-Konstante `FLAT` (y gestaucht).
Test: `python -m visualizers.engine pond --test-signal --demo`.

## Auge des Waldes (`visualizers/scenes/woodeye.py`, Thema green ersetzt Taste 4 / HAL)
`themes.toml` `modes = { hal = "woodeye" }`. Szene `assets/woodeye/scene.png`, Augen `eyes.png` (8x3 à 224: Reihe 0 Öffnen
0..7, Reihe 1 Irisfarben 8..15, Reihe 2: 16 links, 17 Mitte, 18 rechts, 19 oben, 20 unten, 21 halb, 22 Feuer, 23 Spirale),
Figuren `figures.png` (8x4 à 192: Eule 28-31; Reihen 0-2 und Fuchs unbenutzt), Frösche `frogs.png` (8x4 à 160: Reihe = Art,
Spalte = Sprungbild 0 sitzt .. 7 Kehlsack), Tauchen `dive.png` (8x2 à 192: Reihe 0 springt ins Wasser, 1 taucht auf, grün,
im Shader je Art umgefärbt `speciesHue`), Zwerge `gnomes.png` (8x3 à 160: Reihe 0 gucken, 1 ducken, 2 winken); Bögen mit
`scripts/trip_assets.py slice AUS.png BOGEN.png SPALTEN REIHEN ZELLE` (gleich große Zellen, Fußpunkt unten). Blatt i =
Spektrumband i (`FROGS` Position/Größe, `uBands0/1`). Besetzung folgt der Musik (`_frogs_tick`: Ziel 0 bei Stille bis `MAX_FROGS` 4 bei
hoher Energie, Wechsel nur auf Beats; kommen per `PH_EMERGE` von unten aus dem Wasser, gehen per `PH_DIVE` im Bogen hinein, beides
mit den eigenen Sprungbildern, unter Wasser nur Blasen), Hüpfen `PH_HOP` nur auf den Beat (`hop_wish` aus Bandspitzen, max. 2 je Beat),
Tauchspiel selten (`returning`, `under_beats`). Frösche sitzen mit `FROG_DY` auf den Blättern. Shader `uFrogN` = (x, y, Größe, Art), `uFrogPhN` = (Phase 0 leer 1 auftauchen 2 sitzt 3 hüpft
4 springt 5 unten, Fortschritt, rechts = spiegeln). Zwerge `GNOMES` (x, Fußlinie, Größe, Zelle), `uGnomeN`/`uGnomeSN` (Pose
A, B, Mischung, aufgetaucht), unterhalb der Fußlinie abgeschnitten (`gnome()`), `_gnomes_tick` (nur `GNOMES_VISIBLE` 5 zufällige
Zwerge oben, `_gnome_pick`/`gnome_on`, Besetzung wechselt langsam; Beat = selten ducken, alle 5-10 s winkt einer). Beat -> `uStep`/`uPattern` Lauflicht auf den türkisen Stellen des Fotos, Drop -> `uFlash`, `uSporeT`, Auge
Feuer + neue Irisfarbe. Auge über `uBlink` (Öffnung, Reihe 0) und `uEyeA/uEyeB/uEyeMix` (Blickzelle). Knüppel LINKS Eule /
RECHTS Zwerge / OBEN beide (`uFig`, `uOwl`), UNTEN Kaleidoskop, ENTER Froschchor (`uChorusT`), SPACE/BACKSPACE Zoom.
LED-Board: `led_state()` -> Programm `forest` (siehe LED-Buttonboard).
`[scenes.woodeye] eye = [x, y, Breite]`.
Test: `python -m visualizers.engine woodeye --test-signal --demo`.

## Slotmaschinen (`visualizers/scenes/slots.py`, Shader `visualizers/shaders/slots/frag.glsl`, `docs/slots_plan.md`)
Eine Basis für alle vier Themen: Walzen füllen das Bild (`uArea` = `[scenes.<modus>] area`, sonst Standard), 3-5 Walzen je
Automat (`"reels"` im Theme-Dict, `MAX_REELS` 5, `uReel0..4` = Position/Drehzahl/Unschärfe/Stoppalter, `uNReels`), Gewinne
`_evaluate()`: 3 Walzen wie bisher (Paar klein, Drilling groß, Jackpot-Symbol = Jackpot, alle 9 = Mega, Diagonalen); 4 Walzen:
3 nebeneinander = groß, 3 mit Lücke = klein; 5 Walzen: 3 nebeneinander klein, 4 groß, alle = Jackpot, Jackpot-Symbol überall
= Mega (`uWinMask` je Walze, `uWinLine`). Tasten: ENTER/SPACE drehen, LINKS/RECHTS Automat (`ST_THEME`), OBEN/UNTEN Einsatz
(`STAKES`). Themenrahmen `assets/slots/<FRAME>` (1920x1080, Mitte reines Schwarz, `load_frame` Luma-Key mit weichem Rand,
`uFrameTex/uFrameOK`, `KITT_SLOTS_FRAME=<pfad>` zum Testen), Rahmenlichter pulsen zum Bass, Lauflicht `uStep/uStepPhase/
uPattern`, Höhen funkeln, Drop `uFlash` + `drop_boost`, Stille dimmt. Stil `uStyle` 0 Space / 1 Natur / 2 Cyber / 3 Zukunft
(Gewinn-Effekte: Goldregen; Glühwürmchen/Fuchs/Lichthirsch; Chips/Samurai/Neon-Explosion; Dollar/Feuerspuren/Professor/
Zeitmaschine/Sepia), Figuren `uFigTex`/`uFig`. Themen-Controller sind Klassenattribute (`THEMES, LED, STAKES, CURRENCY,
FRAME, FIGURES, FIG_CELLS, STYLE, COUNTER, SEED_BASE`). Bögen 768x510 (3x3 à 256x170) unter `assets/slots/`, neue Bögen und
Rahmen vom Bot nach `assets/slots/raw/` und `scripts/slots_assets.sh` (ruft `scripts/frame_clean.py`: nimmt das Hoverboard aus
dem Walzenfeld von `future_frame.png`, Regeln `CLEAN`). Rahmen (Luma-Key) und Symbolbögen (Kachelzeilen) liegen als npz im
Bild-Cache (`images.derived`, `load_frame`/`_sheet_tiles`, `warm_cache.py` wärmt sie). Automatenzähler `logs/<modus>_theme.txt`.

| Modus | Thema | Walzen | Rahmen | Automaten (`slots_themes.py`) |
|---|---|---|---|---|
| `slots` | Space | 3 | `space_frame.png` | `THEMES`: ORBIT `real.png`, COMIC `cartoon.png`, WAHNSINN `crazy.png` |
| `forestslots` | green | 4 | `forest_frame.png` | `FOREST`: PILZAUTOMAT `forest.png`, TIERE DES WALDES `forest_animals.png`, WALDGEISTER `forest_magic.png` |
| `cyberslots` | cyber | 5 | `cyber_frame.png` | `CYBER`: PACHINKO `cyberslots_symbols.png`, KONZERN `cyber_konzern.png`, NETZGEISTER `cyber_netzgeister.png` |
| `almanacslots` | future | 3 | `future_frame.png` | `FUTURE`: ALMANACH `almanac_symbols.png`, WILDER WESTEN `future_1885.png`, ZUKUNFT 2015 `future_2015.png` |

Test: `python -m visualizers.engine <slots|forestslots|cyberslots|almanacslots> --test-signal`.

## Herzbaum (`visualizers/scenes/hearttree.py`, Thema green ersetzt Taste 6 / Lagerfeuer)
`themes.toml` `modes = { campfire = "hearttree" }`. Szene `assets/hearttree/scene.png` (Shader erkennt Adern: Bernstein/Türkis),
Jahreszeiten-Bogen `seasons.png` (8x3 à 192: Reihe 0 Frühling, 1 Herbst, 2 Winter; `trip_assets.py grid ... 8 3 192`).
`uSeason` 0..4 fließend (0 Frühling, 1 Sommer, 2 Herbst, 3 Winter), Gewichte `seasonW()`; Knüppel links/rechts = Ziel,
sonst `cycle_minutes` je Jahreszeit. Herzschläge `uPulseA/B` (Alter der letzten 6 Impulse, Bass-Anstieg oder Beat),
Flackerwelle `uWaveT` (Richtung wechselt beim Drop), Drop `uFlash` + `uHue` + Sturm, OBEN `uStormT`/`uStormSeed`,
UNTEN `uRootsT`, ENTER `uBigBeat`, SPACE/BACKSPACE `uZoom` auf `[scenes.hearttree] trunk`. WLED je Jahreszeit
`hearttree_spring|summer|autumn|winter`, Ereignisse `hearttree_roots`, `hearttree_beat`.
Test: `python -m visualizers.engine hearttree --test-signal --demo`.

## Überdosis (`visualizers/scenes/overdose.py`, Thema green ersetzt Taste 7 / Systemfehler)
`themes.toml` `modes = { error = "overdose" }`. Szene `assets/overdose/scene.png`, Wesen `creatures.png` (4x3 à 256,
`trip_assets.py grid ... 4 3 256 1`), dazu `assets/trip/gods.png` (Horror-Gott), `assets/trip/face.png`, Eule aus
`assets/woodeye/figures.png`. Phasen `PH_WARN/POISON/HORROR/BLACKOUT` in Wellen (`PHASE_LEN`), `uPoison` 0..1 steuert
Doppelbild/Giftfarbe/Tunnel/Ranken (prozedural). Wesen `uCreN` (x, y, Größe, Zelle) / `uCrePN` (Alter, Sprung, Hue, Spiegel),
zucken selten auf Beats (`lunge_t0`; höchstens `MAX_CRE` 2 kleine Wesen am Rand, nicht überlagernd). Phasenlängen je Welle
zufällig (`PHASE_JITTER`), Ereignisse kommen von selbst (`AUTO_EVENT` 18-40 s: Erbrechen, Augen zu, Hilfe, Schock, Gegengift,
nur wenn 12 s keine Taste). Verschwimmen: kreisende Schmierunschärfe + drei Geisterbilder + Schmelzen (Shader).
Beat = `uCut` Bildsprung + Negativ, Drop = `uFlash` + alle Wesen. Knüppel L/R Gegengift
(`uRelief`, Rückfall nach 4 s), OBEN `uVomitT`, UNTEN `uEyes`, ENTER `uHelpT` (Eule), SPACE/BACKSPACE `uShock`.
WLED `overdose`, `overdose_horror`, `overdose_drop`, `overdose_blackout`, `overdose_help`. `WHISPERS`, `ANTIDOTES`.
Test: `python -m visualizers.engine overdose --test-signal --demo`.

## Thema CYBERPUNK (`cyber`, ersetzt Tasten 2-7)
`themes.toml` `modes = { viz_psychedelic = "neonrace", blackhole = "core", hal = "oracle", slots = "cyberslots",
campfire = "rooftop", error = "blackice" }`, Stimme `de_DE-kerstin-low` (`announce.toml` `[themes.cyber]`, robot + echo).
Bilder vom Bot nach `assets/cyber/raw/` (Prompts/Dateinamen `docs/cyber_plan.md`), `scripts/cyber_assets.sh` baut daraus
alle Atlanten unter `assets/cyber/` (plate/slice aus `trip_assets.py`). Alle sechs Modi: `[scenes.<modus>]` in
`visualizer.toml`, WLED-Profile `<modus>` + Ereignisse in `wled.toml`, Labels in `modes.toml`, Aktionen in `launcher/actions.py`.

### Neonfahrt (`visualizers/scenes/neonrace.py`, Taste 2)
Autopilot: nach `AUTO_START` 5 s fährt der Wagen von selbst (ENTER sofort, SPACE/BACKSPACE = anhalten, Wiederanfahrt nach
Pause). Tempo `uSpeed` = Energie + Beat-Schub `uBoost` + Nitro. Spur `uLane` fließend -1..1, `_best_lane()` weicht Verkehr und
Hindernissen aus (`_arm_reaction`: bei hohem Tempo gelegentlich zu spät = BEINAHE), Knüppel LINKS/RECHTS überstimmt 4 s
(MANUELL), OBEN Hupe `uHonkT`, UNTEN Rückspiegel `uMirror`. `Mover` kinds 0 Holo / 1 Auto / 2 Flieger / 3 Hindernis / 4 Querung
-> `uHolo0..9`, `uCar0..5`, `uFly0..5`, `uObs0..5` (+ `uObsTex` `neonrace_obstacles.png` 8x2 à 192: Reihe 0 steht auf der
Straße, Reihe 1 quert; `OBS_NAMES`). Schilder: je Hologramm eigener Hue-Versatz, springt je Beat (`uBeatStep`), Drop alle;
Lauflicht `uStep/uStepPhase/uPattern` durch die Fassaden. `EVENTS` alle 30-60 s. Stadtteile `DISTRICTS` (0 = `neonrace_scene.png`,
1-6 = `neonrace_district_N.png`, Prompts `docs/cyber_plan.md` Runde 4, fehlende werden übersprungen): alle `district_every`
70-120 s Fahrt `change_district()` -> Lichttor `uDistT` (3,2 s: Lichtstreifen aus dem Fluchtpunkt, Ränder dunkel, Blitz),
Überblendung `uDistMix` von innen nach außen zwischen `uSceneTex` (A) und `uSceneBTex` (B), in der Tormitte wird A das neue
Bild (`_district_tick`, Texturversionen `scene_ver`/`scene_b_ver`); Name/Zeile als Overlay. `[scenes.neonrace] vanish`,
`auto_start`, `district_every`. LED-Board: Programm `drive` (Straße, siehe LED-Buttonboard).
Test: `python -m visualizers.engine neonrace --test-signal --demo`.

### Der Kern (`visualizers/scenes/core.py`, Taste 3)
Wie Schwarzes Loch: `Throw` (cell 0-23 aus `core_objects.png` 6x4 à 192), `SLOTS` 3, `THROW_SECONDS` 40-60 -> `uThrow0..2` /
`uThrowPar0..2`. Automatik: `AUTO_THROW` 8-20 s (Energie > 0.3), `AUTO_SWARM` 60-120 s (Energie > 0.5), `AUTO_EJECT` 120-240 s,
EMP bei jedem Drop (Config `auto_throw`, `auto_swarm`, `auto_eject`). Beat = Ring `uRing0..5` durch die ganze Halle
(Schränke leuchten, Boden unter `FLOOR_Y` hebt sich), Bass-Schlag > `SHOCK_BASS` = Druckwelle `uShock0..2`, Lauflicht
`uStep/uStepPhase/uPattern` (Zonen links/rechts/oben/unten). Farbe `uHue` + `HUE_STEP` alle 8 Beats, Drop = Sprung + `uHallT`
(Halle komplementär), `uHue2` Datenströme. `uVariant` = (Variante, vorige, Mix): 0 Plasma, 1 Datenwürfel, 2 Blitzkugel,
Wechsel alle 30-60 s. OBEN `uSwarmT`, UNTEN `uEjectT`, ENTER `uEmpT`, SPACE/BACKSPACE Zoom. `[scenes.core] center`, `radius`.
Test: `python -m visualizers.engine core --test-signal --demo`.

### Das Orakel (`visualizers/scenes/oracle.py`, Taste 4 / HAL)
EIN Kopf mit 32 Gesten `oracle_main.png` 8x4 à 256x288 (`scripts/trip_assets.py cut ... 8 4 256 288 0 fill`: ganzer
Zellenausschnitt, gefüllte Silhouette, gleiche Lage in jeder Zelle; `GESTURE_NAMES`) im Rahmen `frame` über
`uHeadA/uHeadB/uHeadMix/uHeadGlitch` (Geste A -> B, kurze Überblendung `set_pose`), `uHue`, `uAwake` (Stille = Geste SCHLAF +
Drahtgitter), Schultern lösen sich im Shader unten auf. Gestensätze: `G_LEFT/G_RIGHT/G_UP/G_DOWN` (Knüppel, `gesture_dir`,
hält `MANUAL_HOLD` 2,2 s, nochmal = nächste), `IDLE_CALM/MID/WILD` nach Energie (Wechsel `_beat`: ruhig jeder 4., mittel
jeder 2., wild jeder Beat), `SPEAK_CYCLE` (ENTER, 7 Hz), Blinzeln `next_blink` 3-6 s (SCHLAF/ZWINKERN 0,14 s). Beat-Nicken
`uWobble.y`. Maske: `mask_on` beim Drop, im eigenen Takt `MASK_EVERY` 45-90 s bei Musik (`mask_next`, Energie > 0.2) und über
`_auto_event` "mask" nach `MASK_AUTO_AFTER` 120 s ohne Drop; `oracle_masks.png`
8x2 à 256 (`grid ... 8 2 256 12`, `MASK_NAMES`), `uMaskP` = (Index, Einblendung `mask_k`, Alter), Lage `[scenes.oracle]
mask_fit` = (dx, dy, Größe in Kopf-Einheiten), Wackeln `uWobble.x` (jeder Beat neu), Gesten `MASK_GESTURES`, ab nach
`MASK_BEATS` 8-16 Beats (`mask_off_beat`). Übergeben `vomit()` (SPACE / Kippschalter AN, `_auto_event` "vomit" bei Energie >
0.3 alle `AUTO_VOMIT_GAP` 90 s): `VOMIT_SEQ` Würgen 0,7 s -> Mund auf 0,5 -> Schwall 2,6 -> Wischen 1,3; Schwall `uVomitT`
ab `uMouth` (`[scenes.oracle] mouth`, Kopf-Einheiten) als Bogen im Shader, Teilchen `Garbage` (bis `N_GARB` 16, Schwerkraft
`GARB_GRAVITY`, weg unter `GARB_FLOOR`) -> `uGarb0..15` = (x, y, Zelle, Drehung) aus `oracle_garbage.png` 8x2 à 128 (`cut
... 128 128 1 glow`). BACKSPACE = Zoom zurück (Maske zoomt leicht). Tafeln `panels`: `_pattern_mask()` mit 8 Mustern
(`PATTERN_NAMES`), hart an/aus je Beat -> `uPanelOn0/1` (Nachglühen `AFTERGLOW`), Füllhöhe aus `uBands0/1`, Schrankzonen
`uZoneOn`. Automatik alle `auto_event` 20-40 s: `burst()` (`uBurstT`), Gesten-Salve (`salvo()`), Scanner `uScanT`, Glitch
4 s (`G`-Taste schaltet den Glitch-Modus), Spruch, Übergeben, Maske. WLED `oracle_mask`, `oracle_vomit`. LED-Board: Programm
`panels` (die acht Tafelfarben je ein Ansteuerpunkt im Wechsel, schalten mit den Tafeln, siehe LED-Buttonboard). `oracle_heads.png`
(alte 24 Köpfe) und `oracle_mask.png` unbenutzt, `oracle_figures.png` nur Reihe 2 (Glyphen).
Test: `python -m visualizers.engine oracle --test-signal --demo`.

### Pachinko (`visualizers/scenes/cyberslots.py`, Taste 5 / Slots)
Dünne Unterklasse der Slotmaschine (siehe "Slotmaschinen"): fünf Walzen, Rahmen `cyber_frame.png`, Automaten `CYBER`.
Test: `python -m visualizers.engine cyberslots --test-signal`.

### Dachterrasse (`visualizers/scenes/rooftop.py`, Taste 6 / Lagerfeuer)
Lichtzustände `LIGHT_NAMES`: 0 Grundbild `uSceneTex` (per `uBaseFit`/`BASE_FIT` auf die Lichtbilder gelegt), 1-6
`rooftop_light_1..6.png` als `uLight0..5Tex` (BLACKOUT, ROTER ALARM, SÄURE, ÜBERLAST, NUR WERBUNG, BLITZSCHLAG). Shader liest
je Pixel höchstens drei Bilder (`state(idx, uv)`). `WEATHER` REGEN/NEBEL/SÄUREREGEN/ASCHE (`uWeather`, LINKS/RECHTS,
`cycle_minutes`) mit Heimzuständen `WEATHER_HOME = [5, 1, 3, 2]` / `WEATHER_HOME_MIX` (`uLightA`, `uGroundMix`). Lichtwechsel:
`uLightB`, `uLightMix` (weich `SOFT_FADE` 0.9 s), `uCutT`; ein Zustand bleibt `_hold_beats` stehen (wild 6-10 Beats, mittel 6-12,
ruhig 8-16, dazwischen Grundbild 2-16 Beats), harte Schnitte (`CUT_FADE` 60 ms) auf jedem Beat nur `DROP_BURST_BEATS` 6 nach
dem Drop. ÜBERLAST im Shader auf 0.72 gedämpft, Lichter werden weich begrenzt (kein Ausbrennen). UNTEN Stromausfall `uBlackT`/`uBlackBeats` (Basis 1, Blöcke 9x5 aus Zuständen 2-6, Knall = 4), ENTER EMP
`uEmpT/uEmpBeats/uEmpSeed` (Ring, Basis 1, Blöcke 12x7, auch von selbst `emp_auto` 90-180 s bei `emp_min_energy`), Drop = Blitz
`uLightT/uLightX` + Feuerwerk `uFireT` + 2 Beats Zustand 6, OBEN Feuerwerk, SPACE/BACKSPACE `uLook`. Partikel
`rooftop_particles.png` 8x3 à 160. WLED `rooftop`, je Wetter `rooftop_rain|fog|acid|ash`, `rooftop_fireworks|blackout|lightning`.
LED-Board: Programm `city` (Fensterfront, spiegelt die Lichtzustände, siehe LED-Buttonboard).
`[scenes.rooftop] skyline`, `cycle_minutes`, `base_fit`, `home_mix`, `emp_auto`, `emp_min_energy`.
Test: `python -m visualizers.engine rooftop --test-signal --demo`.

### Black Ice (`visualizers/scenes/blackice.py`, Taste 7 / Systemfehler)
Phasen EINBRUCH/TRACE/BLACK ICE/FLATLINE (`PHASE_LEN` x `PHASE_STRETCH` 0.7-1.5). Bildschirme: `_find_screens()` erkennt beim
Start die schwarzen Monitore in `blackice_scene.png` (luma < `screen_black`, Erosion, Komponenten >= `screen_min_area`,
Rechteckfüllung >= 80 %) -> `uScr0..11` (x0, y0, x1, y1), `uNScr`, Maske als Alpha im Szenenbild. Inhalte `uScrC0..11` = (Typ,
Variante, Startzeit, Seed): 0 Atlaskachel `blackice_screens.png` 8x4 à 384x216 (`uScreenTex`, Zelle = Spalte + 8*Reihe, je Kachel
eigene Animation), 1 Auge prozedural (`uEyeLook`, `uEyeBlink`), 2 Countdown, 3 Warnung, 4 Rauschen/Testbild, 5 Fadenkreuz,
6 Barcode, 7 Fahndungsfoto (`uFaceTex`), 8 EKG, 9 aus, 10 Daemon (`blackice_daemons.png`), 11 Glitch-Maske (`uGodTex`), 12
Fixer-Katze (`uFigTex`/`uOwl`), 13 Bootzeilen, 14 Standby, 15 Atlas-Auge (Reihe 0, blinzelt 0->3->4->3->0, Blick 1/2, Horror
5/6/7). Je Beat wechseln 1-3 Schirme (Drop alle, 80 ms Schwarz), Gewichte je Phase, Stille = Standby. `EVENTS` alle 15-30 s
(`uEvent`: Augen-Salve, Countdown überall, Rauschsturm, Reboot). LINKS/RECHTS `ANTIDOTES` (`uRelief`/`uReliefT`), OBEN Reboot
`uVomitT`, UNTEN Stecker ziehen `uEyes`/`uEyesT`, ENTER `uHelpT`, SPACE/BACKSPACE `uShock`. Keine Wesen im Raum mehr.
`KITT_BLACKICE_PHASE=0..3` = Startphase. Test: `python -m visualizers.engine blackice --test-signal --demo`.

## Thema ZURÜCK IN DIE ZUKUNFT (`future`, ersetzt Tasten 2-7)
`themes.toml` `modes = { viz_psychedelic = "timejump", blackhole = "flux", hal = "clocktower", slots = "almanacslots",
campfire = "square", error = "paradox" }`, Stimme `de_DE-karlsson-low` (`announce.toml` `[themes.future]`, schnell, kurzer Hall).
Bilder vom Bot nach `assets/future/raw/` (Prompts/Dateinamen `docs/future_plan.md`), `scripts/future_assets.sh` baut daraus
Szenen und Atlanten unter `assets/future/`. Fahrerfoto `assets/taxi/future/driver.png` = das verblassende Foto (flux, paradox).
Alle sechs Modi: `[scenes.<modus>]` in `visualizer.toml`, WLED `<modus>` + Ereignisse in `wled.toml`, Labels `modes.toml`,
Aktionen `launcher/actions.py`. Shader-Hinweis (llvmpipe): `pow(x, 2.0)` mit negativem x und `exp()` mit sehr großem
negativem Argument liefern NaN/weiße Blöcke, daher `sq()` statt pow und `exp(max(x, -60))`.

### Zeitsprung (`visualizers/scenes/timejump.py`, Taste 2)
Wie Neonfahrt: Autopilot fährt nach `AUTO_START` 4 s von selbst (ENTER sofort, SPACE/BACKSPACE = anhalten, nach `AUTO_RESTART`
25 s wieder los). `mph` folgt der Energie (30 + 70·Energie + Schub bis 40), spätestens nach `JUMP_DUE` 35-60 s Fahrt laden die
Zeitkreise und das Tempo geht auf `MPH_JUMP` 88 -> `jump()` (`uJumpT` 0..3 s, Weißblitz bei 1,5 s, `_swap_era()`), Drop = sofort, LINKS/RECHTS `uLane`, OBEN `uHonkT`, UNTEN `toggle_circuits` (`uCircuitT`). Cockpit
`timejump_cockpit.png` (Alpha aus der schwarzen Scheibe, `_windshield_mask`, `SHIELD_Y0` 0.45; `cockpit_drop` schiebt das Bild
nach unten, Shader bekommt `uShield` = Scheibenkante auf dem Schirm + Drop in .w), Epochen `uEra0..3Tex` (`uEraA/uEraB/uEraMix`),
Verkehr `timejump_traffic.png` 8x4 à 192 (Reihe = Epoche) als `uMov0..9`/`uMovP0..9`. `EVENTS` je Epoche + Gewitter (`uEvent/
uEventT/uEventLen`). Overlay Zeitkreise: je Zeile fünf Felder MONTH/DAY/YEAR/HOUR/MIN einzeln in ihren Fenstern (`CIRCUIT_X[row][k]`,
`CIRCUIT_Y` Fenstermitte minus Drop, Text mit Unterkante gesetzt, `CIRCUIT_FONT`), beim Sprung und Knüppel unten laufen sie als
Zählwerk durch (`_date_fields(era, spin, t, row)`, rasten von links nach rechts ein), und "NN MPH" (`MPH_X/MPH_Y`). `KITT_TIMEJUMP_ERA` = Startepoche.
Test: `python -m visualizers.engine timejump --test-signal --demo`.

### Fluxkompensator (`visualizers/scenes/flux.py`, Taste 3)
Wie Der Kern: `Throw` (3 Slots, 40-60 s, `uThrow0..2`/`uThrowPar0..2`, Feuerspuren, Zeitschleife, Blitze), Objekte
`flux_objects.png` 6x4 à 192 (`OBJECT_NAMES`). Y-Erkennung beim Start (weißblaue Röhren um `center`/`radius`, PCA je Arm ->
`uCenter`, `uArm0..2`). Grundnähe `[scenes.flux] base_zoom` 0.5 (das Y füllt das Bild), SPACE = ganz nah, BACKSPACE zurück.
Ladung `uCharge` 0..1 (`charge`: steigt mit Energie/Bass/Beats, voll = `discharge()`: `uDischargeT` Weißstoß nach innen,
Funken aus allen Röhren, Lauflicht `uFlow` = (Richtung, Tempo) kehrt um; Stille entlädt langsam; Drop bei Ladung > 0.4 =
Entladung): im Shader ist der Röhrenteil bis `uCharge` hell (`nearFilled`), der Rest glimmt, Kopf `headGlow`, Streifen
`flowGlow`. Funken `uSpray` = (Alter, Arm 0-2 oder 3 = alle, Seed, Stärke) aus einem Röhrenende, von selbst alle 6-14 s bei
Energie > 0.2. OBEN Gewitter `uStormT` (20 s, `uBolt0..2`), UNTEN Paradoxon `uEjectT` (8 s, Polaroid `uPolaroid`,
`uFade`), ENTER `uOverT` 1,21 GW (2,5 s). Beat-Ringe `uRing0..5`, Drop `uFlash`/`uHue`, Oszilloskope aus `uAudioTex`. Test: `python -m visualizers.engine flux --test-signal --demo`.

### Uhrturm (`visualizers/scenes/clocktower.py`, Taste 4 / HAL)
Wie Orakel: Zeiger `uHands` (h, m, s in Umdrehungen; Sekunde tickt je Beat, `uClockT` 21:00 -> 22:04 mit Energie), Blitz
`strike()` (`uStrikeT`, `uBoltSeed`, `uCableGlow`, danach 10 s Stillstand, Rücklauf), acht Schaufenster = Bänder (`uBands0/1`,
`uPeaks0/1`), Lauflicht `uStep/uStepPhase/uPattern`, Wetterleuchten `uSheet`. Figuren `clocktower_figures.png` 8x3 à 192 (Reihe 0
Professor, 1 Zeitmaschine, 2 Tanzpaar; `_fit_cells()` misst je Zelle -> `uCarFit`, `uDocFitA/B`,
`uDancerFitA/B`). LINKS `uDoc`, RECHTS `uCar`/`uCarPar`, OBEN beide (`uFig`), UNTEN Tanzball `uDance`/`uDancer`, ENTER Blitz,
SPACE/BACKSPACE `uZoom`. `[scenes.clocktower] clock = [x, y, r]`, `windows = [x0, x7, y, w]`, `cable = [x0, y0, x1, y1]`.
Test: `python -m visualizers.engine clocktower --test-signal --demo`.

### Almanach (`visualizers/scenes/almanacslots.py`, Taste 5 / Slots)
Dünne Unterklasse der Slotmaschine (siehe "Slotmaschinen"): drei Walzen, Rahmen `future_frame.png`, Automaten `FUTURE`.
Test: `python -m visualizers.engine almanacslots --test-signal`.

### Marktplatz (`visualizers/scenes/square.py`, Taste 6 / Lagerfeuer)
Wie Dachterrasse, Wetter -> Epoche: `uEra` 0..4, `uEraA/uEraB/uEraMix`, Sprung `jump()` (`uJumpT` 0..3 s, `uJumpDir`,
Wechsel bei 1,1 s), automatisch alle `cycle_minutes`. Epochen `square_1885|1955|1985|2015.png` (`uEra0..3Tex`, fehlende fallen
auf die nächste zurück), Teilchen `square_particles.png` 8x3 à 160 (echte Alpha, Reihe je Epoche). `clocks`/`grounds` je Epoche
(`uClock`, `uGround`, beim Sprung überblendet). Beat-Wellen `uPulseA/B` vom Turm, Verkehr `uTrafficT`, OBEN `uFireT`/`uFireSeed`,
UNTEN `uBlackT`/`uBlackBeats`, ENTER `uLightT`/`uLightSeed`, SPACE/BACKSPACE `uZoom`. Test: `python -m visualizers.engine square --test-signal --demo`.

### Paradoxon (`visualizers/scenes/paradox.py`, Taste 7 / Systemfehler)
Wie Black Ice: Phasen STÖRUNG/PARADOXON/1,21 GIGAWATT/AUSLÖSCHUNG (`PHASE_LEN`, `PHASE_NAMES`), Anachronismen
`paradox_intruders.png` 4x3 à 256 als dauerhafte Geister: `uCre0..4` (x, y, Größe, Zelle), `uCreP0..4` (Sichtbarkeit 0..1,
Sprung, Hue, Spiegel/Seed), `uCreM0..4` (nächste Zelle, Morph 0..1, Seed, Alter); nach `life` 7-13 s `Creature.morph()` in
die nächste Zelle (`MORPH_LEN` 2,8 s, Shader `creatureMorph`: Verzerrung + Rauschmaske + Leuchtsaum), Auftauchen/Verschwinden
als Rauschauflösung (`FADE_IN` 2,5 s, `FADE_OUT` 3 s, `leave()` beim Phasenende), Beat-Sprung nur sanft (`lunge_t0`, in
der Gigawatt-Phase stärker), Drop = alle morphen; Zeitmaschine beim Hilferuf mit Funken aus Heck/Rädern und Lichtbögen, Foto `uPhotoTex` (driver.png, 512 px) im Polaroid
`uPhoto = [x, y, w]` mit `uFade` (fbm-Maske), Hand prozedural `uHand`. LINKS/RECHTS `ANTIDOTES` (`uRelief`), OBEN `uRebootT`,
UNTEN `uPhotoView`, ENTER `uHelpT` (Zeitmaschine `uCar` + Professor `uProf` aus `clocktower_figures.png`), SPACE/BACKSPACE
`uShock`. Beat `uCut`, Gigawatt-Blitze `uBolt`, `WHISPERS`. Test: `python -m visualizers.engine paradox --test-signal --demo`.

## Navigationscomputer (`visualizers/scenes/navcomputer.py`)
ENTER = Flug starten, Flug endet NUR per Kippschalter (SPACE oder BACKSPACE im Flug = Ankunft), nie von selbst
(Demo: cruise_seconds). Ereignisse alle 30–60 s (`EVENTS`): Asteroidenfeld, Farbnebel, Sonne, Wurmloch,
Raumstation, Kometenschauer; Shader-Uniforms uEvent/uEventT/uEventLen/uEventWarn/uImpact/uFlash/uShield.

## LED-Buttonboard (`launcher/wled.py`, `config/wled.toml`)
Profil je Modus `[modes.<modus>]` (bri, fx, col, col2, col3, sx, ix, pal); Ereignis-Profile `hal_astronaut`,
`hal_alien`, `hal_both`, `slots_win`, `slots_jackpot`, `blackhole_throw`, `blackhole_eject` schicken die Modi selbst
über `wled.apply_mode_async()`. Home nimmt die Themenfarbe (WLED und PXN-Tasten, schon beim Blättern am Taxistand). Test: `scripts/wledctl.py set --col R,G,B --fx N`.
Live zur Musik (`launcher/ledstream.py`, `LedStream`): jede Engine-Szene streamt unter dem Launcher (oder `KITT_LEDS=1`) 25 Bilder/s
per UDP (WLED-Echtzeit DRGB, `[controller] udp_port` 21324, `realtime_timeout` 2 s, LED-Anzahl aus `/json/info` oder `leds`);
`__main__.py` ruft je Bild `leds.update(now, f, ctrl.led_state())` (nur wenn `led_state` aufrufbar ist). Bildschirmfarbe: alle 4 Bilder
`renderer.screen_pixels()` (Blit des fertigen Bilds in einen 32x18-FBO, `glReadPixels` nur davon) -> `leds.set_screen(px)`:
Hauptfarbe = satt gewichteter Mittelwert (`_saturate` 1.4), Akzent = zweite Farbe im Bild (Farbton > 50 Grad entfernt) oder Farbton
+50 Grad; `update()` führt `scr_col`/`scr_acc` mit ~1 s nach, `_base_col()` nimmt sie vor dem Profil (Tönung geht vor; `error` und
`slots` behalten feste Farben, `glitch` nimmt sie als `c_red`/`c_green`). Beat-Schritt `step_s` (Beats weich eingerastet, ~0,3 s)
und `bar_lift` (die 1 im Takt): Sternenflug = Farbfeld (zwei lange Wellen in Haupt- und Akzentfarbe, treiben kaum) + wenige
langsame Sterne, alles rückt je Beat ein Sechzehntel nach hinten; Strudel-Punkte rucken je Beat zur Mitte; Atem-Wolken rücken
je Beat; Wellen 2,2-2,8 s, Kometen selten (0,35/s). Grundprogramm je
Szene `SCENE_BASE` (sonst nach fx des Profils: Feuer 45/66/42, Scanner 40, Rainbow 9/94, sonst `_music` Pegelmesser), alle ruhig,
Stroboskop nur als Special: `timejump`: Farbfronten
(`fronts`, alle 8-15 s eine neue aus Bildschirmfarbe/Akzent mit gedrehtem Farbton) kommen mit 0,03-0,06 Kette/s von vorne herein,
jede überdeckt die vorige (weiche Kante), Beat = kleiner Schub; `timejump_jump` -> `boost_until` 3 s Volldampf (14x, Fronten alle
0,25-0,5 s in Elektroblau/Weiß, Kometen, Flackern), danach wieder mellow. `drive` (neonrace, `neonrace.led_state()`: `dist`,
`speed`, `driving`, `nitro`, `honk_t0`, `near_t0`, `district_t0`/`district_len`, `police_t0`/`police_len`): Straße, Versatz =
`dist` x `DRIVE_K` 100 LEDs, Laternen alle `LAMP_EVERY` 26 LEDs mit Lichtkegel (bei Nitro Streifen nach vorne), Neonschilder 6-15
LEDs in einer Straßenkarte (`drv["sign"]`, Länge 2x Kette) in Haupt-/Akzentfarbe/Bernstein, Farbton +0,08 je Beat, Grundglimmen
7-10 % Bildschirmfarbe; darüber die Felder aus `_duel` (hell); Hupe zweimal Aufblinken, Beinahe-Treffer weißer Streifen 0,4 s,
Viertelwechsel Lichtwand von vorne nach hinten über `district_len`, Polizeidrohnen rot-blauer Blinker alle 4 s von hinten nach
vorne; `event()` ignoriert in `drive` alle `neonrace_*`-Profile. `duel`: zwei Felder à `DUEL_W` 10 LEDs in Bildschirm-Haupt- und Akzentfarbe (voll ausgesteuert, Akzent gedreht, wenn zu
ähnlich), je Beat ein Feld weiter (kurz eingerastet, Schub = 2 Felder), Modi in `duel["mode"]`: `free` (Richtung je Beat zu 28 %
gewechselt, 12-24 Beats), `lock` Gleichschritt 6-12 Beats, `meet` aufeinander zu -> `merged`: übereinander in dritter Farbe (Farbton
weit weg von beiden), 2-5 Beats als eines weiter, dann teilen (3 Beats auseinander); Kreuzen = Überlappung dritte Farbe; Rest 3 %
Glimmen. `stars` (navcomputer, planets, splash): wenige Sterne ziehen von vorne nach
hinten, Tempo mit der Energie, Beat hebt sie kurz; alle 25-45 s `planet` (weiche Kugel zieht vorbei und füllt im Vorbeiflug
kurz alles in ihrer Farbe); `navcomputer.led_state()` liefert `flying` und das laufende Ereignis: KOMETENSCHAUER = `comet`-Läufer,
ASTEROIDENFELD = graue Brocken schneller, WURMLOCH/SONNE/NEBEL = Tönung. `fire` (campfire, `led_state` level/blue): warmweißes
Fackellicht (255,125,30; auf LEDs wirkt erst das warmweiß), träges Glimmen je LED (`embers`), Wabern `gust`, Helligkeit mit der Feuerstufe, bei `blue` > 0 blau. `vortex` (blackhole, core, flux, pond): Punkte driften von beiden Enden zur Mitte, Mitte glimmt
mit dem Bass. `breathe` (taxi, clocktower, square): langsames Atmen + zwei wandernde Wolken. `heart` (hearttree): vorne hell, hinten dunkler
(`grad` 0.5 -> 0.16), Farbton der Jahreszeit (Tönung, `_no_white` + Interpolation auf dem Farbkreis zur Zweitfarbe, kein Grau),
Herzschlag auf jedem zweiten Beat (ohne Musik 64/min) als Doppelschlag (Stärke 1 und 0,55 nach 0,28 s): Welle läuft mit
0,55 Kette/s nach hinten und klingt ab, vorne zieht sich das Herz zusammen; `hearttree_beat` (ENTER) = großer Schlag. Aderfluss
alle 30-60 s und bei `hearttree_roots`: Strom mit Teilchen läuft in ~10 s von vorne nach hinten. Ruhige Programme (heart, trip,
forest) bekommen beim Drop keinen Aufheller. `forest` (woodeye, `led_state`
`kaleido` 0..1): tiefes Grün `FOREST_DEEP` mit treibenden Moosflecken, türkiser Nebel `FOREST_TURQ` in breiten Schwaden (~1/4 der
Kette), leuchtet mit dem Bass, glüht je Beat auf (0,45 s), nie aus; Kaleidoskop (Knüppel unten): feste Regenbogenfolge sechsmal
über die Kette, läuft nur vor/zurück mit wechselndem Tempo (Summe dreier Sinus, ±0,11 Kette/s, mit Bass schneller). `trip` (Waldtresen,
`led_state` intensity): Farbfeld aus zwei Sinuswellen mit langsam wandernden Wellenlängen (`k1`, `k2`, Blasen teilen/vereinen
sich), verbogen von `warp`, Farbton über den ganzen Farbkreis (`_hsv_arr`), dreht über Minuten; dunkelgrüne Täler `TRIP_DG` (~30 %),
nie aus (Boden 35 % Dunkelgrün); Beat = Phasenschritt 0.012 weich (~1 s), Drop = Palette dreht 0.2-0.45 über ~4 s; am Tresen
(intensity 0) überwiegt Dunkelgrün. `panels` (oracle,
`oracle.led_state()`: `cols` = Farben der acht Tafel-Glyphen aus `_panel_colors()` (Atlaszellen 16-23, hellste 20 %, Grauanteil
raus), `lvl` = `panel_lvl` mit Nachglühen): LED i zeigt Tafel i % 8, also Rot, Orange, Gelb, Grün, Türkis, Blau, Violett, Magenta
je ein Ansteuerpunkt, an solange die Tafel an ist (Beat-Muster der Szene), aus 4 %; Stille = alle leise atmend.
`city` (rooftop, `rooftop.led_state()`: `state` = laufender Lichtzustand 0-6 + `mix`, `weather`, Zeitpunkte `blackout_t0`,
`emp_t0`/`emp_seed`, `lightning_t0`, `fire_t0`): Fensterfront `_city_setup()` (Fenster 2-4 LEDs, Lücke 1-2, Häuser alle 4-9 Fenster
mit 3-6 Lücke; `CITY_PAL` Magenta/Cyan/Bernstein/Violett), ~40 % an, je Beat kippen 1,5-4,5 % der Fenster. Zustände: 1 Notstrom
(5 % Fenster warm flackernd, rote Flugwarnlichter), 2 rot + Drehlicht hin und her, 3 giftgrün mit Röhrenflackern, 4 Gold, 85 % an,
alle 4 Beats brennt ein Haus durch, 5 Fenster aus + 4 Reklamen à 15-20 LEDs mit Lauflicht (Muster je Beat), 6 blau-weiß; Wetter:
Regen-Schimmer, Nebel weich/blass, Säure grüner Stich, Asche glühende Punkte. Stromausfall blockweise aus, Notstrom, Rückkehr, am
Ende Gold; EMP als Welle vom Punkt aus, Fenster kommen einzeln zurück; Blitz nur beim Zustand 6 (höchstens alle 8 s) oder beim
Drop (höchstens alle 30 s); `event()` ignoriert in `city` lightning/blackout/fireworks-Profile (Feuerwerk kommt aus `fire_t0`).
Specials: fliegendes Auto alle 25-50 s (Scheinwerfer + Rücklichter), Polizeidrohne alle 60-120 s (rot/blau). `glitch` (blackice, paradox, overdose): das Störprogramm `_error` in den
Themenfarben (`c_red`/`c_green` aus col/col2) mit eigenem 40-s-Phasenzyklus. `error` = Systemfehler (oben beschrieben). `slots` (`slots.py` `led_state`, alle vier Automaten): Casino-Lauflicht `_slots` als Basis:
ein Ansteuerpunkt an, der nächste aus, konstant hell, `ch_step` springt hart je Beat (ohne Beats alle 0,6 s) um einen Punkt (an <-> aus),
Farbe `chase_ci` (0 Farbe A, 1 Farbe B, 2 Farbe A mit Farbton + `chase_hue`; `colors` aus `slots_themes.py`, `_saturate` 1.5, kein Weiß)
wechselt alle 8 Beats zu 50 % auf dem Beat und bei jedem Drop (`is_drop` aus `last_drop`). Specials nur beim Drop (je 50 %) und Gewinn:
Markise (`mq_mode` 0 bis `mq_marq_until`, Drop 6-12 s, Gewinn 2 = 4 s, >= 3 = 7 s, Überblendung `mq_mix` 0,8 s): Blöcke (`block` 3
Ansteuerpunkte) Farbe A hell / Farbe A gedimmt (0,35) / Farbe B hell, rückt einen Block je Beat (`mq_target`/`mq_pos_s`, weich eingerastet;
Drehen = 4 Blöcke/s), Richtung `mq_dir` kehrt alle 16 Beats, bei kräftigem Bass, alle 6-14 s und beim Drop um, Farben rücken alle 4
Beats (`mq_rot`), `mq_pos` modulo 6 Blöcke; oder Läufer (`sp_launch`): `runner` (ein Punkt läuft durch, zieht der Beat an, überholt ein
zweiter in der Akzentfarbe mit 1,9x), `cross` (zwei Läufer kreuzen sich), Lauflicht derweil 60 %. Gewinn 1 = zweimal Gold, 2 = weißer
Lauf von vorne + Markise schnell, >= 3 = Gold/Weiß-Strobo 3 s + Funkeln (Glanzlichter = aufgehellte Farbe A). Beim Drehen
`_reel_zones` (`slots.led_state` `reels` = je Walze Position, Drehzahl, Sekunden seit Einrasten): Kette in `n_reels` Abschnitte
(vorne = Walze 1), je Abschnitt ein Symbolband (`REEL_SYM` 14 LEDs: 10 hell in Farbe A / A gedimmt / B, 4 dunkel), Versatz =
Walzenposition x 14, läuft also genau mit Drehzahl, Abbremsen und Rückfedern der Walze; schnell = verwischt, Einrasten = 0,25 s
Aufleuchten; bis 0,5 s nach der letzten Walze, dann wieder Lauflicht. Special
Zellteilung `_cell_special` (`cell`, alle 45-90 s, erstes nach 25-45 s, nur im Lauflicht ohne Gewinn/Drehen/Läufer): ein Punkt
in Gegenfarbe (Farbton + 1/3, 1/2 oder 2/3) in einer leeren LED, je Lauflicht-Schritt eine LED weiter (bleibt so in den leeren),
`CELL_PHASES` 15/15/12 s: nach der ersten teilt jeder Punkt sich links/rechts, nach der zweiten nochmal, dann `back`: alle laufen
ihren Weg aus `hist` Schritt für Schritt zurück, treffen sich an den Teilungsstellen und verschwinden am Start (~85 s). Specials
(`_add`/`_apply_specials`, max. 4 gleichzeitig) aus den Ereignis-Profilen der Szenen (`wled.apply_mode_async` -> `event()`):
*throw* = `swallow` (Punkt zur Mitte, Aufleuchten), *eject/emp/overload/discharge* = `burst` (Druckwelle von der Mitte),
*lightning/strike/storm* = `lightning` (zwei Blitze, Grollen), *fireworks* = Blüten, *blackout* = aus und zögernd zurück,
*log* = `sparks`, *blue* = Tönung 30 s, *jump* = Schub + Blitz, *start/nitro* = Schub + Welle, `horn` = `blink2`, `fx` = Welle in
col3, sonst `wave` in der Profilfarbe; Zustandsprofile `STATE_PROFILE` (rooftop_rain|fog|acid|ash, hearttree_<Jahreszeit>,
square_<Jahr>, campfire_big) setzen die Grundfarbe (`tint`), das Modusprofil selbst setzt sie zurück. Drop = weicher Aufheller
(0.55, höchstens alle 12 s).
Gesamtdämpfung `[controller] dim` 0.7 für HTTP-Profile (`payload_for`) und Stream. Die Helligkeit je Modus steht allein im Profil-bri
(Stream nimmt denselben Wert): Standard 1/4 des ursprünglichen Werts, HAL 107, Casino 1/4. HAL 3000 streamt über `kitt/ui/persona.py`
(gleiche Schleife wie die Engine, `kitt/hal/app.py` `led_state` -> Programm `hal`): 8 Paare dunkel-/hellroter Felder
(`hal_phase`, blockig) ziehen immer von vorne nach hinten (0,035-0,085 Kette/s), Bass hebt die hellen; 25 % dunkler
(`bri *= 0.75`, Profil bri 142), alle 40-90 s ein einzelnes Feld (`field`, ~14 LEDs, heller), das im Beat-Schritt (1/95 je Beat,
12 % Rückschritte, ohne Beats alle 0,55 s) in rund einer Minute von einem Ende zum anderen wandert.
`payload_for` setzt immer `pal` (Profil, sonst 3 mit col2 / 2 ohne: sonst bleibt die letzte Palette, z. B. Regenbogen, und viele
Effekte malen damit), Segment 0 über die ganze Kette (`led_count()` aus `/json/info` oder `[controller].leds`), `pl = -1`
(Playlist aus), `lor = 0` (Live-Override aus), Nachtlicht aus; beim ersten Senden je Prozess löscht `_cleanup_segments()`
Segmente mit id > 0. Systemfehler-Profil und LED-Programm sind rein rot. Diagnose auf dem Pi: `scripts/wled_check.py`
(Info, Segmente, Playlist, lor, drei Tests: rot gedimmt/voll per HTTP, rot per UDP, danach `live`-Status). LED-Anzahl in WLED
setzen: `scripts/wled_setup.py --leds 784 --apply` (`/json/cfg` `hw.led.ins[0].len`; `--maxpwr` Strombegrenzung): LEDs hinter der
eingestellten Anzahl bekommen nie Daten und bleiben bunt an. Ketten über 490 LEDs streamt `LedStream._send` als DNRGB-Pakete
(Typ 4, Startindex, 489 je Paket); Ausfallrate im Fehlerprogramm gilt je 30 LEDs (`poisson`).

## Schwarzes Loch (`visualizers/scenes/blackhole.py`)
D-Pad LINKS/RECHTS = Planet aus `config/planets.toml` von dieser Seite ins Loch werfen (wird über ~1 Minute zum
Band gestreckt, wogt zur Musik). OBEN = Asteroidenschwarm (Perlenkette). UNTEN = Umkehrung (Loch spuckt aus:
Blitz, Druckwelle, Trümmer, Scheibe rückwärts, alles fliegt zurück, 8 s). ENTER = Jet, SPACE = Nahaufnahme,
BACKSPACE = zurück.

## HAL 3000 Hintergrund (`kitt/hal/motion.py`)
Korridor bewegt sich nur über `uDrift` (langsam, Richtung ±1, Wechsel beim Drop), nicht über die Zeit.
`uVariant` 0–4 Zellenmuster, `uAccent` hüpfende Einzelzelle, `uWash` Farbwelle, Beat-Zähler `uStep` 0–3 /
`uStepPhase` mit Lauflicht-Muster `uPattern` 0–5 (wechseln bei Drops und alle 25–45 s). Test:
`KITT_HAL_VARIANT=n python -m kitt.hal --demo` (Demo nutzt das Testsignal als Musik).
Figuren (`kitt/hal/figures.py`, Atlas `assets/hal/figures.png`): D-Pad LINKS Astronaut, RECHTS Alien, OBEN beide,
UNTEN HAL-Konsole; Test `KITT_HAL_FIGURE=1..3`. PersonaUI liefert Bilder über `images()` an den Renderer.

## Planeten-Visualizer (`visualizers/scenes/planets.py`)
Sternenhimmel mit Warp-Flug-Modus.

| Taste | Wirkung |
|---|---|
| SPACE / ENTER | Warp-Flug starten |
| BACKSPACE | Warp-Flug stoppen (zurück zu Drift) |
| ESC | Beenden |

## Ansagen und Themenstimmen (`kitt/announce.py`, `config/announce.toml`)
`[lines]` Standardsätze je Gruppe (Modusname, boot, home, theme). `[themes.<name>]` `voice`, `tts` (Overrides, u. a. `echo_ms`
Hall in `PiperTTS`), `[themes.<name>.lines]`. Build rendert je Thema mit eigener Stimme alle Gruppen (`<thema>__<gruppe>_<hash>.wav`),
lädt fehlende Stimmen per `piper.download_voices` nach. `play(group, target, theme=None)` nimmt das gewählte Thema.
Launcher: `switch()` gibt den effektiven Modus zurück, `announce(eff)`; Taxistand spielt `theme` beim Bestätigen.
Je hörbare Gruppe 6-8 Sätze; `_pick()` meidet die zuletzt gespielten (gut die Hälfte der Auswahl, `logs/announce_recent.json`,
Schlüssel `<thema|standard>:<gruppe>`). Build rendert Standardsätze nicht in der Themenstimme, wenn das Thema den Modus ersetzt
(`_replaced_modes()` aus themes.toml). Lautstärke aller Sprecher: `[volume].voice_gain` 0.35 in settings.toml.
`[themes.spacetaxi]` hat nur `tts` = die HAL-3000-Werte aus `kitt/hal/app.py` `prepare_cfg` (pitch 1.0, length 1.15, robot 35 Hz,
mix 0.25, ohne Bits, Kamm 3 ms): das Space-Programm sagt die Standardsätze mit HALs Stimme an; fehlen die Dateien noch, spielt
`play()` die Standardstimme. KITT (Taste 10) und BIBO behalten ihre eigene Stimme (`kitt.toml` `[tts]`).

## Musik vom Handy (`scripts/setup_cast.sh`)
Spotify Connect (`kitt-spotify`, librespot/raspotify, Premium nötig) und AirPlay (`kitt-airplay`, shairport-sync) als
`systemd --user`-Dienste über PipeWire auf den Standard-Sink; Systemdienste der Pakete werden abgeschaltet (kein
PipeWire-Zugriff). Kein Chromecast möglich. Android ohne AirPlay: `scripts/setup_bluetooth.sh`. Titel: `logs/now_playing.txt`
(`scripts/spotify_event.sh` via `--onevent`). Status: `scripts/setup_cast.sh --status`.

## /dev/uinput Berechtigung
udev-Regel in `/etc/udev/rules.d/99-uinput.rules`:
```
KERNEL=="uinput", MODE="0660", GROUP="input"
```
Nötig damit `dpad_remap.py` virtuelle Tastatur-Events injizieren kann.
