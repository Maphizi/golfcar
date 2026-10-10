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

### Launcher-Tasten (BTN-Codes von event7)

| Physische Taste | BTN-Code | Launcher-Aktion |
|---|---|---|
| Taste 1 (HANDLE) | BTN_MISC | gaming – Holo-Arcade (RetroPie) |
| Taste 2 (CRUISE) | BTN_1 | viz_psychedelic – Hyperraum |
| Taste 3 (FLASH) | BTN_2 | viz_crt – Zielcomputer |
| Taste 4 (AUDIO) | BTN_3 | viz_eye – Taktik-Scanner |
| Taste 5 (WIPERS) | BTN_4 | kitt – Bordcomputer |
| Taste 6 (MAP) | BTN_5 | home – Hauptmenü |
| Taste 7 (LIGHT) | BTN_6 | campfire – Lagerfeuer |
| Taste 8 (E-TALK) | BTN_7 | status – Log-Ausgabe |
| Taste 9 | BTN_8 | quit – Beenden |
| Taste 10 | BTN_9 | planeten – Planeten-Flug |

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
