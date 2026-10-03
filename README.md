# KITT-Cart – Golfcart Entertainment auf Raspberry Pi 5

Fullscreen-Appliance: Retro-Gaming, drei GPU-Audio-Visualizer und der lokale
Sprachassistent KITT. Bedienung über F1–F6, später über eine USB-HID-Buttonbox.

Stand: **Phase 5** (Launcher, RetroPie als F1, Visualizer F2–F4, Spracherkennung whisper.cpp + Silero VAD).
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
| `config/audio.toml` | Audio-Geräte, Capture-Backend, Analyse-Parameter |
| `config/visualizer.toml` | FPS, Render-Skalierung, Hot-Reload der Shader |
| `visualizers/engine/` | Audio-Capture, Analyse, GL-Engine |
| `visualizers/shaders/<szene>/frag.glsl` | die drei Szenen, `common/vert.glsl` gemeinsam |
| `kitt/stt/` | VAD, Listener, whisper.cpp-Client, Test-WAVs |
| `kitt/llm/`, `kitt/tts/`, `kitt/personality/` | ab Phase 6–8 |
| `config/kitt.toml` | STT-, VAD-, LLM- und TTS-Einstellungen |
| `models/` | Whisper-, VAD-, LLM-, TTS-Modelle (nicht im Repo) |
| `vendor/` | whisper.cpp, llama.cpp (nicht im Repo) |
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
- `retropie/<modul>.log` – Build-Logs der RetroPie-Installation, EmulationStation schreibt zusätzlich `~/.emulationstation/es_log.txt`

- `viz_<szene>.log` enthält alle 10 s FPS und die Audio-Pegel, dazu das Capture-Backend

- `stt.log` – STT-Werkzeug und Listener, `whisper-server.log` – Ausgabe des Servers

Ab Phase 6 kommen `llm.log` und `tts.log` dazu.

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
- **EmulationStation startet nicht:** `logs/gaming.log` und `~/.emulationstation/es_log.txt`.
  Steht dort ein SDL-Video-Fehler, in `run_gaming.sh` das Backend prüfen (`SDL_VIDEODRIVER=x11`
  braucht Xwayland, `DISPLAY=:0`).
- **Home-Screen nach RetroPie-Installation schwarz:** Das RetroPie-SDL hat evtl. keinen
  Wayland-Treiber. `sdl_videodriver = "x11"` in `config/settings.toml` setzen.
- **Visualizer reagiert nicht auf Musik:** `logs/viz_<szene>.log` zeigt `audio=none` und
  "Keine Audioquelle". `scripts/audio_check.sh` ausführen, Quelle in `config/audio.toml` eintragen.
  Steht dort `(Stille)` trotz Musik, `noise_gate` senken oder Mikrofonpegel erhöhen.
- **Visualizer ruckelt:** `render_scale` der Szene in `config/visualizer.toml` senken.
- **Visualizer: GL-Fehler oder schwarzes Bild unter Wayland:** PyOpenGL verfolgt den GL-Kontext über
  GLX und findet unter SDL/Wayland keinen. `engine.py` setzt deshalb `PYOPENGL_PLATFORM=egl`,
  schaltet die Fehlerprüfung ab und patcht die Kontextsuche (Abschnitt "contextdata").
- **Spracherkennung: whisper-server startet nicht:** `logs/whisper-server.log`. Port 8178 belegt
  (`ss -ltnp | grep 8178`), Modell fehlt in `models/`, oder Build fehlt (`scripts/setup_phase5.sh`).
- **VAD reagiert nicht / zu oft:** `scripts/stt_mic.sh` zeigt die Zustände. `start_threshold`
  (höher = unempfindlicher) und `end_silence_ms` (länger = weniger abgeschnittene Sätze) in `config/kitt.toml`.
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

## F1 – Retro-Gaming (Phase 3)

**Installation:** `scripts/setup_phase3.sh` klont [RetroPie-Setup](https://github.com/RetroPie/RetroPie-Setup)
nach `~/RetroPie-Setup` und installiert über `retropie_packages.sh` genau diese Module:

| Modul | Zweck |
|---|---|
| `sdl2` | SDL 2.32.10 (RetroPie-Build mit KMS/X11), ersetzt das System-SDL und wird per apt-hold festgehalten |
| `retroarch` | libretro-Frontend |
| `emulationstation`, `retropiemenu`, `runcommand` | Menü, RetroPie-Konfigurationssystem, Start-Wrapper |
| `lr-fceumm` | NES |
| `lr-snes9x` | SNES |
| `lr-genesis-plus-gx` | Mega Drive / Genesis |
| `lr-gambatte` | Game Boy, Game Boy Color |
| `lr-mgba` | Game Boy Advance |
| `lr-pcsx-rearmed` | PlayStation 1 (BIOS nach `~/RetroPie/BIOS`) |

Auf Debian 13 gibt es keine RetroPie-Binärpakete, alle Module werden aus dem Quellcode gebaut
(45 bis 90 Minuten). Das Skript ist idempotent, fertige Module werden übersprungen
(`logs/retropie/<modul>.done`). Nicht installiert wird `basic_install` von RetroPie, das wären
Dutzende Emulatoren.

**Anpassungen** (`scripts/configure_gaming.sh`, idempotent):

- ROM-Ordner `~/RetroPie/roms/{nes,snes,megadrive,gb,gbc,gba,psx}`. Eigene ROMs dort ablegen,
  danach in EmulationStation Start → Quit → Restart EmulationStation oder F6 und wieder F1.
- Tastatur ist in EmulationStation vorkonfiguriert (`config/es_input.cfg`): Pfeile, X=A, Z=B,
  S=X, A=Y, Q=L, W=R, Enter=Start, RShift=Select. Ein Gamepad wird in EmulationStation über
  Start → Configure Input eingerichtet, RetroPie übernimmt die Belegung dann für RetroArch.
- RetroArch-Hotkeys auf F2, F4, F6 sind abgeschaltet, diese Tasten gehören dem Launcher.
  F1 öffnet weiterhin das RetroArch-Menü, ESC beendet das laufende Spiel.
- Audio: RetroArch und SDL sprechen ALSA, `pipewire-alsa` leitet das an PipeWire weiter.

**Display-Backend:** RetroPies RetroArch wird ohne Wayland-Support gebaut. Der Gaming-Modus
(`scripts/run_gaming.sh`) läuft deshalb über Xwayland in der labwc-Session
(`KITT_GAMING_BACKEND=xwayland` in `config/modes.toml`). Falls das Probleme macht (Tearing,
kein Vollbild, Eingabe), ist der Fallback die X11-Session von Raspberry Pi OS:
`sudo raspi-config nonint do_wayland W1` und Neustart. Der Launcher läuft dort unverändert.

**Verlassen:** EmulationStation Start → Quit → Quit EmulationStation beendet den Prozess, der
Launcher zeigt wieder Home. F6 beendet den Gaming-Modus jederzeit hart (SIGTERM, nach 8 s SIGKILL).

## F2–F4 – Audio-Visualizer (Phase 4)

**Audio-Konfiguration** (`config/audio.toml`): Geräte werden nicht im Code, sondern nur hier
eingetragen. `scripts/audio_check.sh` zeigt Backend (PipeWire), Quellen, Senken, Samplerate und
macht einen 3-Sekunden-Mikrofontest mit Pegelanzeige. Der Capture-Prozess ist `pw-record`
(PipeWire), Fallback `arecord` über `pipewire-alsa`. Es werden keine Audio-Bindings kompiliert.
`target` bleibt leer für die Standardquelle oder bekommt den Node-Namen aus `wpctl status`.

**Analyse** (`visualizers/engine/analysis.py`), ~60 Updates/s über einen 2048er-FFT:

| Wert | Bedeutung |
|---|---|
| `uRms` | Gesamtlautstärke 0..1, Auto-Gain, geglättet |
| `uBass`, `uMid`, `uHigh` | 20–150 Hz, 150–2000 Hz, 2–12 kHz, je 0..1 |
| `uBeat` | 1.0 bei Bass-Transient über 1,6× Mittel der letzten Sekunde, klingt ab |
| `uSilent` | 1.0 unter `noise_gate`, dann laufen die Visuals nur über `iTime` weiter |
| `uAudioTex` | 512×2-Textur: Zeile 0.25 = Spektrum (64 log-Bins), Zeile 0.75 = Waveform |

**Engine** (`visualizers/engine/engine.py`): pygame-Fenster mit OpenGL-3.1-Kontext, ein
Vollbild-Dreieck, ein Fragment-Shader pro Szene (`#version 140`). `render_scale` in
`config/visualizer.toml` rendert in einen kleineren Framebuffer und skaliert hoch, um GPU-Zeit zu
sparen. Shader-Dateien werden bei Änderung automatisch neu geladen, ein Fehler lässt den alten
Shader laufen und steht im Log.

**Szenen:**

- `psychedelic` (F2): Kaleidoskop-Tunnel mit FBM-Plasma. Bass zoomt und pulst den Kern,
  Mitten drehen, Höhen erzeugen Glitch-Zeilen, Lautstärke steuert die Intensität. Die
  ShaderToy-Referenz MsdBR8 diente nur als optische Orientierung, es wurde kein Code übernommen
  (ShaderToy-Shader stehen standardmäßig unter CC BY-NC-SA 3.0).
- `crt` (F3): grünes Phosphor-Instrument mit echter Waveform, 32 Spektrum-Balken, zwei
  VU-Metern, Zahlenanzeigen (Bass/Mitten/Höhen in Prozent, Zeit), Statusleuchte, Scanlines,
  Wölbung, Flimmern, Rollbalken, Rauschen.
- `eye` (F4): Maschinenauge mit Lid und Lidschlag. Bass öffnet die Pupille, Lautstärke pulst
  das ganze Auge, Mitten drehen die Iris, Höhen verschieben Zeilen, der Beat sendet einen Ring
  nach außen. Pixelraster und Scanlines.

**Testen ohne Mikrofon:** `scripts/viz_test.sh crt --test-signal` spielt ein synthetisches
Signal (Kick 120 BPM, Melodie, Hi-Hats, alle 24 s vier Sekunden Pause) ein und legt nach 12 s
einen Screenshot in `docs/` ab. `--windowed` öffnet ein Fenster statt Vollbild. Standalone
beendet ESC die Szene, unter dem Launcher übernimmt F6.

## F5 – Spracherkennung (Phase 5)

**Installation:** `scripts/setup_phase5.sh` baut [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
nach `vendor/whisper.cpp` (CPU, NEON), lädt die Modelle nach `models/` und erzeugt deutsche
Test-WAVs mit espeak-ng in `kitt/stt/testdata/`.

| Datei | Quelle | Zweck |
|---|---|---|
| `ggml-base.bin` (148 MB) | huggingface.co/ggerganov/whisper.cpp | Whisper base, multilingual |
| `ggml-small-q5_1.bin` (190 MB) | huggingface.co/ggerganov/whisper.cpp | Whisper small, 5-bit quantisiert |
| `silero_vad.onnx` (2,3 MB) | github.com/snakers4/silero-vad (MIT) | Silero VAD v5 |

**Pipeline** (`kitt/stt/`): Der Audiostrom kommt mit 48 kHz vom gemeinsamen Capture
(`visualizers/engine/audio_capture.py`, Subscriber-Callback), wird auf 16 kHz dezimiert und in
32-ms-Chunks durch Silero VAD geschickt (`vad.py`, onnxruntime, ~0,2 ms je Chunk). Der
`Listener` schneidet Äußerungen: Sprache ab `start_threshold` für `start_ms`, Ende nach
`end_silence_ms` Stille, mit `pre_roll_ms` Vorlauf und einer Obergrenze `max_speech_ms`. Ohne
onnxruntime fällt die VAD auf eine energiebasierte Variante zurück.

`whisper-server` läuft dauerhaft mit geladenem Modell auf 127.0.0.1:8178 (kein Modell-Laden pro
Anfrage). `whisper_client.py` startet ihn und schickt Äußerungen als WAV per HTTP. Decoding ist
greedy (`beam_size = 1`, `best_of = 1`), `audio_ctx = 768` verkürzt die Encoder-Zeit für kurze
Äußerungen. Alle Parameter stehen in `config/kitt.toml` unter `[stt]` und `[vad]`.

**Modellwahl:** `scripts/stt_bench.sh` lädt nacheinander alle Modelle aus `[stt.bench].models`,
transkribiert die Test-WAVs und schreibt Ladezeit, RAM, Latenz, Real-Time-Faktor und Text nach
`docs/stt_bench_phase5.md`. Das gewählte Modell kommt in `[stt].model`.

**Live-Test:** `scripts/stt_mic.sh` hört über das Mikrofon, zeigt die Zustände `listening`/`idle`
und gibt Transkripte mit Latenz aus. Einzelne Dateien: `.venv/bin/python -m kitt.stt --wav datei.wav`.

## Noch offen

- Installierte Pakete, Repositories, Modelle, Audio- und LLM-Konfiguration, Shader-Verzeichnis:
  werden mit den jeweiligen Phasen ergänzt.
