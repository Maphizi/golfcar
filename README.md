# KITT-Cart – Golfcart Entertainment auf Raspberry Pi 5

Fullscreen-Appliance: Retro-Gaming, drei GPU-Audio-Visualizer und der lokale
Sprachassistent KITT. Bedienung über F1–F6, später über eine USB-HID-Buttonbox.

Stand: **Phase 2** (Projektstruktur, Launcher, F1–F6-Grundfunktion mit Platzhaltern).
Phasenplan und Anforderungen: `docs/KITT_Masterprompt_V1_erweitert.md`.
Hardware-Inventur: `docs/inventory_phase1.txt`.

## Architektur

```
            Tastatur / HID-Buttonbox          scripts/kittctl (SSH, Tests)
                    │ evdev                            │ Unix-Socket
                    ▼                                  ▼
             launcher/input_evdev.py         launcher/input_socket.py
                    └──────────── Action ──────────────┘
                                   ▼
                          launcher/core.py  (Kern, kein Fenster, keine GPU)
                                   │
                          launcher/process_manager.py
                                   │  genau EIN Modus-Prozess zur Zeit
        ┌──────────┬───────────────┼───────────────┬──────────┐
      home       gaming      viz_psychedelic    viz_crt  viz_eye   kitt
   (pygame)   (EmulationStation)   (gemeinsame GL-Engine, Phase 4)  (Phase 5–8)
```

Grundsätze:

- **Eingabe und Aktion sind getrennt.** Eingabequellen erzeugen nur `Action`-Werte
  (`launcher/actions.py`). Eine Buttonbox ist später nur ein weiteres evdev-Gerät oder
  ein zusätzliches Mapping in `config/keymap.toml`.
- **Der Kern ist minimal und robust.** Er öffnet kein Fenster. Der Home-Screen ist ein
  gewöhnlicher Modus. Beendet sich ein Modus (normal oder Absturz), startet der Kern Home.
  Stürzt Home selbst wiederholt ab, wartet der Kern 10 s (Crash-Loop-Schutz).
- **Ein Modus zur Zeit.** Beim Wechsel: SIGTERM an die Prozessgruppe, nach `stop_timeout`
  SIGKILL, erst dann startet der nächste Modus. RetroPie und KITT laufen nie parallel.
- **Wayland-tauglich.** Tasten werden über evdev gelesen, nicht über den Compositor.
  Das funktioniert unter labwc, X11 und auf der Konsole. Die Tastatur wird nicht
  exklusiv gegriffen, die laufende Anwendung sieht die Tasten weiterhin.

## Verzeichnisse

| Pfad | Inhalt |
|---|---|
| `launcher/` | Kern, Eingabe, Prozessmanager, Home-Screen, Platzhalter |
| `config/settings.toml` | Display, Logging, Entwickler-Schalter |
| `config/keymap.toml` | Taste → Action |
| `config/modes.toml` | Modus → Kommando, Timeout, Label |
| `config/audio.toml` | Audio-Geräte (ab Phase 4) |
| `visualizers/` | GL-Engine und Shader (ab Phase 4) |
| `kitt/` | STT, LLM, TTS, Personality (ab Phase 5) |
| `scripts/` | Setup, Start, Steuerung, Inventur, Autostart |
| `systemd/` | User-Unit für den Autostart |
| `logs/` | Logs (nicht im Repo) |
| `docs/` | Master-Prompt, Inventur, Phasen-Notizen |

## Tastatursteuerung

| Taste | Action | Modus |
|---|---|---|
| F1 | `gaming` | Retro-Gaming (EmulationStation, ab Phase 3) |
| F2 | `viz_psychedelic` | Psychedelic Visualizer |
| F3 | `viz_crt` | CRT / Oscilloscope |
| F4 | `viz_eye` | Digital Eye |
| F5 | `kitt` | KITT Sprachassistent |
| F6 | `home` | Home-Screen |
| ESC | `quit` | Launcher beenden (nur wenn `dev_emergency_exit = true`) |

Ohne Tastatur, z. B. per SSH: `scripts/kittctl viz_crt`, `scripts/kittctl home`,
`scripts/kittctl state` (aktueller Modus), `scripts/kittctl status` (Werte ins Log).

## Installation (Phase 2)

```bash
cd ~/golfcar
scripts/setup_phase2.sh        # apt-Pakete, venv, Gruppen
scripts/run_launcher.sh        # Launcher im Vordergrund (Strg+C oder ESC beendet)
```

`run_launcher.sh` findet den Wayland-Socket des Desktops selbst, damit die Fenster auch
bei Start per SSH auf dem HDMI-Display erscheinen.

## Start / Stop

| Zweck | Befehl |
|---|---|
| Entwicklung, Vordergrund | `scripts/run_launcher.sh` |
| Autostart aktivieren | `scripts/autostart_enable.sh` dann `systemctl --user start kitt-launcher` |
| Autostart für Wartung aus | `scripts/autostart_disable.sh` |
| Status des Dienstes | `systemctl --user status kitt-launcher` |

Der Autostart wird erst in Phase 9 scharf geschaltet und getestet.

## Logs

Alle Logs liegen in `logs/` (Pfad in `config/settings.toml`, kann auf ein tmpfs zeigen):

- `launcher.log` – Kern: Moduswechsel, Exit-Codes, alle 60 s Temperatur/Last/RAM
- `home.log`, `gaming.log`, `viz_*.log`, `kitt.log` – stdout/stderr des jeweiligen Modus

Ab Phase 4/5 kommen `audio.log`, `stt.log`, `llm.log`, `tts.log` dazu.

## Fehlerdiagnose

- **Kein Fenster sichtbar:** `WAYLAND_DISPLAY` fehlt. `ls /run/user/1000/wayland-*` zeigt den
  Socket, `run_launcher.sh` setzt ihn automatisch. Alternativ `sdl_videodriver` in
  `settings.toml` auf `"x11"` (Xwayland) setzen.
- **Tasten werden nicht erkannt:** Benutzer muss in Gruppe `input` sein (`id`). Im
  `launcher.log` steht `Gerät aktiv: <Tastatur>`. Keycode-Namen prüfen mit
  `.venv/bin/python -m evdev.evtest`.
- **Tasten ohne Hardware testen:** `sudo .venv/bin/python scripts/inject_key.py KEY_F3`
  (virtuelles Gerät über uinput).
- **Modus startet nicht:** `logs/<modus>.log` ansehen, der Kern fällt auf Home zurück.
- **Launcher hängt:** `scripts/kittctl state` und `pgrep -af launcher`. Ein zweiter
  Launcher übernimmt den Socket, also vorher den alten beenden.

## USB-HID-Buttonbox (später)

Die meisten Buttonboxen melden sich als USB-Tastatur. Dann gibt es zwei Wege:

1. Box so programmieren, dass sie F1–F6 sendet. Nichts zu ändern.
2. Beliebige Keycodes der Box in `config/keymap.toml` als zusätzliche `[[bindings]]`
   eintragen. Über `[devices] include` lässt sich das Mapping auf den Gerätenamen der Box
   beschränken. Der Launcher erkennt ein nachträglich eingestecktes Gerät innerhalb von 3 s.

Eine Box, die kein Tastaturgerät ist (z. B. serielle Taster), schickt die Action-Namen an
den Unix-Socket `$XDG_RUNTIME_DIR/kitt-launcher.sock` (siehe `launcher/input_socket.py`).

## Noch offen

- Installierte Pakete, Repositories, Modelle, Audio- und LLM-Konfiguration, Shader-Verzeichnis:
  werden mit den jeweiligen Phasen ergänzt.
