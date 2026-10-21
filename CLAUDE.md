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
Ereignisse `EVENTS` (alle 16-28 s; `EV_ROOTS` Wurzeln mit optional `assets/trip/roots.png`, `EV_GOD` Waldgott alle 22-28 s
nur mit `assets/trip/gods.png` 3x2 à 512, `GOD_NAMES`/`GOD_LINES`), Symbolsätze `SYMBOL_SETS` (Zellen im 8x5-Atlas).
Kaleidoskop-Varianten `uVariant` (0 klassisch, 1 Tunnel, 2 Blüte, 3 Zellen; `_next_variant`, Überblendung 3 s), Wanderung
alle 12-22 s, Beat = Drehstoß. Test: `python -m visualizers.engine trip --demo`.

## Moorsee (`visualizers/scenes/pond.py`, Thema green ersetzt Taste 3)
`themes.toml` `modes = { blackhole = "pond" }`. Waldsee `assets/pond/lake.png` + Seegrund `bottom.png` + Kreaturen-Atlas
`creatures.png` (6x4 à 160, `scripts/trip_assets.py atlas`), Wesen aus `assets/trip/beings.png`/`config/trip.toml`.
`[scenes.pond] vortex = [x, y]`, `water = [y0, y1, x0, x1]` (Wassermaske). LINKS/RECHTS = Wesen werfen (Band im
Strudel, ~40-60 s), OBEN = Blätterregen, UNTEN = Umkehrung (Fontäne, Seegrund), ENTER = Stein hüpft, SPACE/BACKSPACE =
Zoom. Beat = Ring, Drop = `uFlash`. Wasserebene perspektivisch: Shader-Konstante `FLAT` (y gestaucht).
Test: `python -m visualizers.engine pond --test-signal --demo`.

## Auge des Waldes (`visualizers/scenes/woodeye.py`, Thema green ersetzt Taste 4 / HAL)
`themes.toml` `modes = { hal = "woodeye" }`. Szene `assets/woodeye/scene.png`, Augen `eyes.png` (8x3 à 224: Reihe 0 Öffnen
0..7, Reihe 1 Irisfarben 8..15, Reihe 2: 16 links, 17 Mitte, 18 rechts, 19 oben, 20 unten, 21 halb, 22 Feuer, 23 Spirale),
Figuren `figures.png` (8x4 à 192: Reihe 0 Frösche sitzend, 1 Kehlsack, 2 Sprung, 3 Fuchs 24-27 / Eule 28-31), gebaut mit
`scripts/trip_assets.py grid AUS.png BOGEN.png 8 3 224` (Zellen in Bildreihenfolge). Frosch i = Spektrumband i (`FROGS`
Position/Größe im Controller, `uBands0/1`, `uFrogN.w` Sprungphase). Beat -> `uStep`/`uPattern` Lauflicht auf den türkisen
Stellen des Fotos (Shader erkennt Türkis), Drop -> `uFlash`, `uSporeT`, Auge Feuer + neue Irisfarbe. Auge über `uBlink`
(Öffnung, Reihe 0) und `uEyeA/uEyeB/uEyeMix` (Blickzelle). Knüppel LINKS Fuchs / RECHTS Eule / OBEN beide (`uFig`, `uOwl`),
UNTEN Kaleidoskop, ENTER Froschchor (`uChorusT`, Tauchwelle), SPACE/BACKSPACE Zoom. `[scenes.woodeye] eye = [x, y, Breite]`.
Tauchspiel: `phase[i]` (sit/dive/under/emerge, `_frogs_tick` auf Beats), Shader `uFrogPhN` = (Phase, Fortschritt, Schwimmer);
`SWIMMERS` (0, 7) sitzen halb im Wasser. Nachbilder und Spritzer im Shader (`frog()`).
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
