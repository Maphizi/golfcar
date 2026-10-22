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
(`start_code`, `kipp_code`, `kipp_mode`, `talk_code`, `debounce_ms`), nicht mehr im Python-Code.
`scripts/input_monitor.py 10` zeigt je Taste Code, Werte, Rate und ob sie von selbst periodisch sendet.

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
- Stimme: `launcher/volume_knob.py`, ABS-Achse aus `config/settings.toml` `[volume].axis` (leer = nur
  Beobachtung, Log meldet bewegte Achsen) -> `logs/voice_volume.txt`, von Piper je Satz gelesen.
- Musik: `launcher/music_knob.py`, KEY_VOLUMEUP/DOWN (immer), REL_MISC (`[music].rel`) oder ABS-Achse
  (`[music].axis`) -> mpv-Socket `/tmp/mpv.sock` (`scripts/music.sh` startet mpv mit Socket).

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

## Lagerfeuer (`visualizers/scenes/campfire.py`)
Cinemagraph: Foto `assets/campfire/scene.png` + Flammen-Spritesheet `assets/campfire/flames.png` (8x5). Feuerstelle
`[scenes.campfire] fire = [x, y, w, h]`; uDay Farbstimmung über `cycle_minutes`, uWind, uSpark, uBassS. Neue Bilder:
`scripts/campfire_assets.py`. Test: `python -m visualizers.engine campfire --test-signal --demo`.

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
Kaleidoskop-Varianten `uVariant` (0 klassisch, 1 Tunnel, 2 Blüte, 3 Zellen; `_next_variant`, Überblendung 3 s), Wanderung
alle 15-30 s, Beat = Drehstoß. Test: `python -m visualizers.engine trip --demo`.

## Moorsee (`visualizers/scenes/pond.py`, Thema green ersetzt Taste 3)
`themes.toml` `modes = { blackhole = "pond" }`. Waldsee `assets/pond/lake.png` + Seegrund `bottom.png` + Kreaturen-Atlas
`creatures.png` (6x4 à 160, `scripts/trip_assets.py atlas`), Wesen aus `assets/trip/beings.png`/`config/trip.toml`.
`[scenes.pond] vortex = [x, y]`, `water = [y0, y1, x0, x1]` (Wassermaske). Uferleben: `assets/pond/shore.png` (4x6 à 192,
`trip_assets.py slice ... 4 6 192`; Spalte = Stufe, Reihe = Art), Plätze `SHORE` (x, Fußlinie, Größe, Seite, im Wasser),
`plant_stage` 0..3 fließend (`_plants_tick`: Wachstum mit Energie, voll hält, welkt; Stille welkt alles; Drop = alles blüht),
Shader `uPlantN`/`uPlantSN`, Sporen `uSporeT`. LINKS/RECHTS = `sprout(side)`. Wesen fallen nur noch von selbst (`AUTO_THROW`,
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
Spektrumband i (`FROGS` Position/Größe, `uBands0/1`). Besetzung folgt der Musik (`_frogs_tick`: Ziel 0 bei Stille bis 8 bei
hoher Energie; kommen per `PH_EMERGE`, gehen per `PH_DIVE`), Hüpfen `PH_HOP` bei Bandspitzen/Chor/Drop, Tauchspiel auf Beats
(`returning`, `under_beats`). Shader `uFrogN` = (x, y, Größe, Art), `uFrogPhN` = (Phase 0 leer 1 auftauchen 2 sitzt 3 hüpft
4 springt 5 unten, Fortschritt, rechts = spiegeln). Zwerge `GNOMES` (x, Fußlinie, Größe, Zelle), `uGnomeN`/`uGnomeSN` (Pose
A, B, Mischung, aufgetaucht), unterhalb der Fußlinie abgeschnitten (`gnome()`), `_gnomes_tick` (Beat = ducken, alle 2-5 s
winkt einer). Beat -> `uStep`/`uPattern` Lauflicht auf den türkisen Stellen des Fotos, Drop -> `uFlash`, `uSporeT`, Auge
Feuer + neue Irisfarbe. Auge über `uBlink` (Öffnung, Reihe 0) und `uEyeA/uEyeB/uEyeMix` (Blickzelle). Knüppel LINKS Eule /
RECHTS Zwerge / OBEN beide (`uFig`, `uOwl`), UNTEN Kaleidoskop, ENTER Froschchor (`uChorusT`), SPACE/BACKSPACE Zoom.
`[scenes.woodeye] eye = [x, y, Breite]`.
Test: `python -m visualizers.engine woodeye --test-signal --demo`.

## Pilzautomat (`visualizers/scenes/forestslots.py`, Thema green ersetzt Taste 5 / Slots)
`themes.toml` `modes = { slots = "forestslots" }`. Erbt `slots.Controller` (Walzen, Planung, Gewinne); Basis ist dafür
parametrisiert: `self.themes`, `self.led` (WLED-Profile Modus/Gewinn/Jackpot), `self.bet`, `self.payout_mult`,
`self.strip_row`, `_pick_theme()`. Eigener Atlas: Bogen `assets/forestslots/symbols.png` 3x3 à 384x256 (Schwarz = frei),
Thema `slots_themes.FOREST` (letztes Symbol = Lichthirsch = Jackpot). Szene `assets/forestslots/scene.png`, Fenster
`[scenes.forestslots] windows = [[x0,x1],...]`, `window_y = [y0,y1]`. Knüppel links/rechts = Einsatz `STAKES`
(Eichel/Pilz/Hirsch) statt Automatenwechsel. Shader zeichnet Trommeln in den Fenstern (`drum()`), Pilze im Foto pulsieren
(helle gesättigte Stellen), `uWin` 1 Glühwürmchen, 2 Blätter + Fuchs (`assets/woodeye/figures.png`), 3/4 Lichthirsch
galoppiert; Drop `uFlash`/`uSporeT`, nächste Drehung schneller (`drop_boost`).
Test: `python -m visualizers.engine forestslots --test-signal`.

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
springen auf Beats (`lunge_t0`). Beat = `uCut` Bildsprung + Negativ, Drop = `uFlash` + alle Wesen. Knüppel L/R Gegengift
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
Fahrmodus wie Navigationscomputer: ENTER = losfahren, SPACE/BACKSPACE = anhalten. LINKS/RECHTS `change_lane` (`uLane`),
OBEN `honk` (`uHonkT`), UNTEN `toggle_mirror` (`uMirror`). `Mover` (cell, side/lane, z, seed, kind 0 Holo / 1 Auto / 2 Flieger)
-> `uHolo0..9`, `uCar0..5`, `uFly0..5` (cell, side, z, seed; z < 0 = leer). Hologramme `neonrace_holo.png` 8x3 à 160,
Verkehr `neonrace_traffic.png` 8x2 à 192. Ereignisse `EVENTS` alle 30-60 s (`uEvent/uEventT/uEventLen`), Nitro bei lauter
Musik (`uNitro`), `uSpeed/uDist/uDriving`. `[scenes.neonrace] vanish = [x, y]`.
Test: `python -m visualizers.engine neonrace --test-signal --demo`.

### Der Kern (`visualizers/scenes/core.py`, Taste 3)
Wie Schwarzes Loch: `Throw` (cell 0-23 aus `core_objects.png` 6x4 à 192, side, swirl, seed, y0, reverse), `SLOTS` 3,
`THROW_SECONDS` 40-60 -> `uThrow0..2` (Fortschritt, Zelle, Seite, Seed) / `uThrowPar0..2` (swirl, reverse, y0), Pixelauflösung
+ Datenstrom im Shader. OBEN Schwarm `uSwarmT` (30 s), UNTEN Auswurf `uEjectT` (8 s, Burst bei 1.2), ENTER EMP `uEmpT`,
SPACE/BACKSPACE Zoom. Beat-Ringe `uRing0..5` (Alter), `uSpinT`, `uHue` wechselt beim Drop. `[scenes.core] center`, `radius`.
Test: `python -m visualizers.engine core --test-signal --demo`.

### Das Orakel (`visualizers/scenes/oracle.py`, Taste 4 / HAL)
Maske `oracle_mask.png` 8x3 à 192 (Reihe 0 Ausdrücke 0-7, 1 Farben 8-15, 2 Glitch 16-23) über `uMaskA/uMaskB/uMaskMix`,
`uAwake` folgt der Energie (Stille = schläft). Figuren `oracle_figures.png` 8x3 à 192 (Reihe 0 Samurai 0-7, 1 Katze 8-15,
2 Glyphenpaneele 16-23). Acht Paneele = Spektrumbänder (`uBands0/1`, `uPeaks0/1`), Lauflicht `uStep/uStepPhase/uPattern`.
ENTER `speak()` (`ORACLE_LINES` getippt, `uSpeakT`), LINKS Samurai / RECHTS Katze (`uCat` = x, cellA, cellB, dir) / OBEN beide
(`uFig`, `uSam`), UNTEN `toggle_glitch` (`uGlitch`), SPACE/BACKSPACE Zoom, Drop `uBurstT` + neue Farbe. `[scenes.oracle]
frame = [x, y, Breite]`, `panels = [x0, x7, y, Breite]`. Test: `python -m visualizers.engine oracle --test-signal --demo`.

### Pachinko (`visualizers/scenes/cyberslots.py`, Taste 5 / Slots)
Erbt `slots.Controller` wie der Pilzautomat. Thema `CYBER` (Symbole `cyberslots_symbols.png` 3x3 à 384x256, letztes =
KI-Kern = Jackpot), `STAKES` CHIP 10/x1, DECK 50/x5, IMPLANT 200/x20 (LINKS/RECHTS). Extra-Uniforms `uGlitchT, uStake,
uStakeT, uSam, uStep, uStepPhase, uStopT`, `uObjTex` = `core_objects.png` (Drohne Zelle 0, Koffer Zelle 20 beim Jackpot),
`uFigTex` = Samurai tanzt bei großem Gewinn, Chips regnen. Zoom im Shader (center 0.5/0.52, 1.22), Symbolbreite
`symW = min(1, 1.5*winAspect*1.08)`. `[scenes.cyberslots] windows`, `window_y`.
Test: `python -m visualizers.engine cyberslots --test-signal`.

### Dachterrasse (`visualizers/scenes/rooftop.py`, Taste 6 / Lagerfeuer)
`WEATHER` REGEN/NEBEL/SÄUREREGEN/ASCHE als `uWeather` 0..4 fließend (LINKS/RECHTS Ziel, sonst `cycle_minutes`), Partikel
`rooftop_particles.png` 8x3 à 160 (Reihe 0 Tropfen/Funken, 1 Blüten/Konfetti, 2 Schnee/Asche). Beat-Wellen durch die
Türme `uPulseA/B`, Suchscheinwerfer `uSearchT`, Verkehr `uTrafficT`. OBEN Feuerwerk (8 s), UNTEN Blackout (14 s, Blöcke
kommen mit Beats zurück `uBlackBeats`), ENTER Blitz, SPACE/BACKSPACE Blick nach unten `uLook`. WLED je Wetter
`rooftop_rain|fog|acid|ash` + `rooftop_fireworks|blackout|lightning`. `[scenes.rooftop] skyline`, `cycle_minutes`.
Test: `python -m visualizers.engine rooftop --test-signal --demo`.

### Black Ice (`visualizers/scenes/blackice.py`, Taste 7 / Systemfehler)
Abgeleitet von der Überdosis (gleiche Uniform-Namen): Phasen EINBRUCH/TRACE/BLACK ICE/FLATLINE (`PHASE_LEN`), Daemonen
`blackice_daemons.png` 4x3 à 256 (`uCreN/uCrePN`), `uGodTex` = `oracle_mask.png` (Glitch-Reihe 16-23), `uFaceTex` =
Fahndungsplakat (Barcode/Fadenkreuz im Shader), `uFigTex` = `oracle_figures.png` Katze (`CAT_CELLS` 8-11 über `uOwl`).
LINKS/RECHTS `ANTIDOTES` (`uRelief`, Rückfall 4 s), OBEN Reboot `uVomitT` (Bild rollt, Bootzeilen), UNTEN Stecker ziehen
`uEyes`, ENTER Fixer-Katze `uHelpT`, SPACE/BACKSPACE Jack out `uShock`. Overlay Puls/Trace, Flatline-EKG, `WHISPERS`.
Test: `python -m visualizers.engine blackice --test-signal --demo`.

## Thema ZURÜCK IN DIE ZUKUNFT (`future`, ersetzt Tasten 2-7)
`themes.toml` `modes = { viz_psychedelic = "timejump", blackhole = "flux", hal = "clocktower", slots = "almanacslots",
campfire = "square", error = "paradox" }`, Stimme `de_DE-karlsson-low` (`announce.toml` `[themes.future]`, schnell, kurzer Hall).
Bilder vom Bot nach `assets/future/raw/` (Prompts/Dateinamen `docs/future_plan.md`), `scripts/future_assets.sh` baut daraus
Szenen und Atlanten unter `assets/future/`. Fahrerfoto `assets/taxi/future/driver.png` = das verblassende Foto (flux, paradox).
Alle sechs Modi: `[scenes.<modus>]` in `visualizer.toml`, WLED `<modus>` + Ereignisse in `wled.toml`, Labels `modes.toml`,
Aktionen `launcher/actions.py`. Shader-Hinweis (llvmpipe): `pow(x, 2.0)` mit negativem x und `exp()` mit sehr großem
negativem Argument liefern NaN/weiße Blöcke, daher `sq()` statt pow und `exp(max(x, -60))`.

### Zeitsprung (`visualizers/scenes/timejump.py`, Taste 2)
Wie Neonfahrt: ENTER = Gas (`uDriving`), `mph` folgt der Energie, bei `MPH_JUMP` 88 `jump()` (`uJumpT` 0..3 s, Weißblitz bei 1,5 s,
`_swap_era()`), SPACE/BACKSPACE = anhalten, LINKS/RECHTS `uLane`, OBEN `uHonkT`, UNTEN `toggle_circuits` (`uCircuitT`). Cockpit
`timejump_cockpit.png` (Alpha aus der schwarzen Scheibe, `_windshield_mask`, `SHIELD_Y0` 0.50; `cockpit_drop` schiebt das Bild
nach unten, Shader bekommt `uShield` = Scheibenkante auf dem Schirm + Drop in .w), Epochen `uEra0..3Tex` (`uEraA/uEraB/uEraMix`),
Verkehr `timejump_traffic.png` 8x4 à 192 (Reihe = Epoche) als `uMov0..9`/`uMovP0..9`. `EVENTS` je Epoche + Gewitter (`uEvent/
uEventT/uEventLen`). Overlay Zeitkreise (rot/grün/gelb, Positionen minus Drop) und "NN MPH". `KITT_TIMEJUMP_ERA` = Startepoche.
Test: `python -m visualizers.engine timejump --test-signal --demo`.

### Fluxkompensator (`visualizers/scenes/flux.py`, Taste 3)
Wie Der Kern: `Throw` (3 Slots, 40-60 s, `uThrow0..2`/`uThrowPar0..2`, Feuerspuren, Zeitschleife, Blitze), Objekte
`flux_objects.png` 6x4 à 192 (`OBJECT_NAMES`). Y-Erkennung beim Start (weißblaue Röhren um `center`/`radius`, PCA je Arm ->
`uCenter`, `uArm0..2`). OBEN Gewitter `uStormT` (20 s, `uBolt0..2`), UNTEN Paradoxon `uEjectT` (8 s, Polaroid `uPolaroid`,
`uFade`), ENTER `uOverT` 1,21 GW (2,5 s), SPACE/BACKSPACE `uZoom`. Beat-Ringe `uRing0..5`, Drop `uFlash`/`uHue`, Oszilloskope
aus `uAudioTex`. Test: `python -m visualizers.engine flux --test-signal --demo`.

### Uhrturm (`visualizers/scenes/clocktower.py`, Taste 4 / HAL)
Wie Orakel: Zeiger `uHands` (h, m, s in Umdrehungen; Sekunde tickt je Beat, `uClockT` 21:00 -> 22:04 mit Energie), Blitz
`strike()` (`uStrikeT`, `uBoltSeed`, `uCableGlow`, danach 10 s Stillstand, Rücklauf), acht Schaufenster = Bänder (`uBands0/1`,
`uPeaks0/1`), Lauflicht `uStep/uStepPhase/uPattern`, Wetterleuchten `uSheet`. Figuren `clocktower_figures.png` 8x3 à 192 (Reihe 0
Professor, 1 Zeitmaschine, 2 Tanzpaar; Bogen ungleichmäßig, `_fit_cells()` misst je Zelle -> `uCarFit`, `uDocFitA/B`,
`uDancerFitA/B`). LINKS `uDoc`, RECHTS `uCar`/`uCarPar`, OBEN beide (`uFig`), UNTEN Tanzball `uDance`/`uDancer`, ENTER Blitz,
SPACE/BACKSPACE `uZoom`. `[scenes.clocktower] clock = [x, y, r]`, `windows = [x0, x7, y, w]`, `cable = [x0, y0, x1, y1]`.
Test: `python -m visualizers.engine clocktower --test-signal --demo`.

### Almanach (`visualizers/scenes/almanacslots.py`, Taste 5 / Slots)
Erbt `slots.Controller` wie Pilzautomat/Pachinko. Thema `FUTURE` (`almanac_symbols.png` 3x3 à 384x256, letztes = 22:04 =
Jackpot), `STAKES` CENT 1955 10/x1, DOLLAR 1985 50/x5, KARTE 2015 200/x20. Extra-Uniforms `uBoltT/uBoltSeed` (Drop-Blitz),
`uSepia` (Schwarzweiß beim Jackpot), `uStake/uStakeT`, `uFig` (Professor/Tanzpaar aus `clocktower_figures.png`, Reihe 0 als
192x256 gelesen), `uStep/uStepPhase/uStopT`. Dollarregen und Feuerspuren prozedural. `[scenes.almanacslots] windows`, `window_y`.
Test: `python -m visualizers.engine almanacslots --test-signal`.

### Marktplatz (`visualizers/scenes/square.py`, Taste 6 / Lagerfeuer)
Wie Dachterrasse, Wetter -> Epoche: `uEra` 0..4, `uEraA/uEraB/uEraMix`, Sprung `jump()` (`uJumpT` 0..3 s, `uJumpDir`,
Wechsel bei 1,1 s), automatisch alle `cycle_minutes`. Epochen `square_1885|1955|1985|2015.png` (`uEra0..3Tex`, fehlende fallen
auf die nächste zurück), Teilchen `square_particles.png` 8x3 à 160 (echte Alpha, Reihe je Epoche). `clocks`/`grounds` je Epoche
(`uClock`, `uGround`, beim Sprung überblendet). Beat-Wellen `uPulseA/B` vom Turm, Verkehr `uTrafficT`, OBEN `uFireT`/`uFireSeed`,
UNTEN `uBlackT`/`uBlackBeats`, ENTER `uLightT`/`uLightSeed`, SPACE/BACKSPACE `uZoom`. Test: `python -m visualizers.engine square --test-signal --demo`.

### Paradoxon (`visualizers/scenes/paradox.py`, Taste 7 / Systemfehler)
Wie Black Ice: Phasen STÖRUNG/PARADOXON/1,21 GIGAWATT/AUSLÖSCHUNG (`PHASE_LEN`, `PHASE_NAMES`), Anachronismen
`paradox_intruders.png` 4x3 à 256 (`uCre0..4`/`uCreP0..4`, `lunge_t0`), Foto `uPhotoTex` (driver.png, 512 px) im Polaroid
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
