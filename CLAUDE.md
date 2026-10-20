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

### Startknopf (HID-Code 266)
→ Injiziert `KEY_ENTER` – universelle Bestätigung / Losfliegen im Planeten-Modus

### Kippschalter (HID-Code 267) – Toggle
Statusbehaftet – jeder Druck wechselt den Zustand:
- **AN** (erster Druck) → injiziert `KEY_SPACE` → startet Warp-Flug (Planeten)
- **AUS** (zweiter Druck) → injiziert `KEY_BACKSPACE` → stoppt Warp-Flug
- Bei HAL 3000 (Taste 4): nur mit `[hal].kipp_talk = true` (Standard aus) AN = Sprechmodus, AUS = Musik normal

### Sprechtaste (Action `talk`)
Beliebige Board-Taste in `config/keymap.toml` auf `action = "talk"` (`code = N`, Code steht im Launcher-Log als
"Taste ohne Belegung"). Launcher injiziert dann `KEY_F15`; HAL 3000 schaltet damit den Sprechmodus um
(Musik auf `duck_percent`, Mikrofon an; nochmal = zurück; nach `[hal].talk_timeout` s ohne Gespräch von selbst aus).
Test: `scripts/kittctl talk`.

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

## Schwarzes Loch (`visualizers/scenes/blackhole.py`)
D-Pad LINKS/RECHTS/OBEN/UNTEN = Planet aus `config/planets.toml` von dieser Seite ins Loch werfen
(wird über ~1 Minute zum Band gestreckt, wogt zur Musik). ENTER = Jet, SPACE = Nahaufnahme, BACKSPACE = zurück.

## HAL 3000 Hintergrund (`kitt/hal/motion.py`)
Korridor bewegt sich nur über `uDrift` (langsam, Richtung ±1, Wechsel beim Drop), nicht über die Zeit.
`uVariant` 0–4 Zellenmuster pro Start, `uAccent` hüpfende Einzelzelle, `uWash` Farbwelle. Test:
`KITT_HAL_VARIANT=n python -m kitt.hal --demo` (Demo nutzt das Testsignal als Musik).

## Planeten-Visualizer (`visualizers/scenes/planets.py`)
Sternenhimmel mit Warp-Flug-Modus.

| Taste | Wirkung |
|---|---|
| SPACE / ENTER | Warp-Flug starten |
| BACKSPACE | Warp-Flug stoppen (zurück zu Drift) |
| ESC | Beenden |

## /dev/uinput Berechtigung
udev-Regel in `/etc/udev/rules.d/99-uinput.rules`:
```
KERNEL=="uinput", MODE="0660", GROUP="input"
```
Nötig damit `dpad_remap.py` virtuelle Tastatur-Events injizieren kann.
