# KITT-Cart – Golfcart Entertainment auf Raspberry Pi 5

Fullscreen-Appliance: Retro-Gaming, drei GPU-Audio-Visualizer und der lokale
Sprachassistent KITT. Bedienung über F1–F6, später über eine USB-HID-Buttonbox.

Stand: **Space-Thema** (alle Modi im Raumschiff-Look, Roboterstimme, Lagerfeuer am Außenposten) auf Phase 10 + Extras.
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
| `kitt/llm/` | llama-server-Wrapper, Streaming-Client, Dialogzustand, Benchmark |
| `kitt/personality/` | KITT-System-Prompt und Benchmark-Fragen |
| `kitt/tts/` | Piper-Sprachausgabe mit Streaming-Wiedergabe |
| `kitt/voice/` | Pipeline-Zustandsmaschine, Satz-Splitter, Headless-Runner |
| `kitt/ui/` | KITT-Vollbildoberfläche (F5), bindet Szene `kitt` und Pipeline zusammen |
| `config/kitt.toml` | STT-, VAD-, LLM- und TTS-Einstellungen |
| `models/` | Whisper-, VAD-, LLM-, TTS-Modelle (nicht im Repo) |
| `vendor/` | whisper.cpp, llama.cpp (nicht im Repo) |
| `scripts/` | Setup, Start, Steuerung, Inventur, Autostart |
| `systemd/` | User-Unit für den Autostart |
| `logs/` | Logs (nicht im Repo) |
| `docs/` | Master-Prompt, Inventur, Phasen-Notizen |

## Tastatursteuerung

Gesteuert wird über das PXN-CB1-Buttonboard (BTN-Codes des Gamepad-Interfaces, siehe
`CLAUDE.md` für D-Pad, Startknopf und Kippschalter). Die F-Tasten sind nicht mehr gebunden, weil das
Board sie über sein Tastatur-Interface ungewollt mitsendet.

| Taste | BTN-Code | Action | Modus |
|---|---|---|---|
| 1 HANDLE | `BTN_MISC` | `home` | Startbildschirm Space-Taxi (siehe unten) |
| 2 CRUISE | `BTN_1` | `viz_psychedelic` | Navigationscomputer / Hyperraum |
| 3 FLASH | `BTN_2` | `blackhole` | Schwarzes Loch (Strahlverfolgung mit Lichtkrümmung, reagiert auf Musik) |
| 4 AUDIO | `BTN_3` | `hal` | HAL 3000: ruhiger Bordrechner mit rotem Auge, spricht mit dem Sprachmodell |
| 5 WIPERS | `BTN_4` | `slots` | Space-Slotmaschine (siehe Space-Thema) |
| 6 MAP | `BTN_5` | `campfire` | Lagerfeuer: Rast am Rand der Galaxis |
| 7 LIGHT | `BTN_6` | `error` | Systemfehler-Visualizer (grüner Code, der zusammenbricht) |
| 8 E-TALK | `BTN_7` | `gaming` | Retro-Gaming (EmulationStation, RetroPie) |
| 9 | `BTN_8` | `quit` | Launcher beenden (nur wenn `dev_emergency_exit = true`) |
| 10 | `BTN_9` | `kitt` | KITT Sprachassistent mit Oberfläche (Bordcomputer) |
| ESC | `KEY_ESC` | `quit` | Notausstieg an der Tastatur |

Der einfache Planeten-Flug (`planeten`), der Zielcomputer (`viz_crt`), der Taktik-Scanner
(`viz_eye`), die Galaktischen Nachrichten (`news`) und der Bord-Droide BIBO (`droid`) sind nicht mehr auf dem Board, bleiben aber als Modi über `scripts/kittctl <modus>`
erreichbar. Das Tastaturlayout der ganzen KITT-Sitzung (auch RetroPie unter Xwayland) ist QWERTY,
gesetzt in `scripts/session_kitt.sh` über `XKB_DEFAULT_LAYOUT`. Startknopf und Kippschalter des Boards kommen als
ENTER bzw. Leertaste (AN) und Rücktaste (AUS) an, siehe `CLAUDE.md`.

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
| Entwicklung, Vordergrund (auf dem Desktop) | `scripts/run_launcher.sh` |
| Appliance-Autostart einschalten | `scripts/autostart_enable.sh && sudo reboot` |
| Wartung: zurück zum normalen Desktop | `scripts/autostart_disable.sh && sudo reboot` |
| Zustand anzeigen | `scripts/autostart_status.sh` |
| Launcher-Dienst stoppen / starten (in der Appliance-Session) | `systemctl --user stop kitt-launcher`, `... restart kitt-launcher` |
| Modus per SSH wechseln | `scripts/kittctl home` usw. |

## Logs

Alle Logs liegen in `logs/` (Pfad in `config/settings.toml`, kann auf ein tmpfs zeigen):

- `launcher.log` – Kern: Moduswechsel, Exit-Codes, alle 60 s Temperatur/Last/RAM
- `home.log`, `gaming.log`, `viz_*.log`, `kitt.log` – stdout/stderr des jeweiligen Modus
- `retropie/<modul>.log` – Build-Logs der RetroPie-Installation, EmulationStation schreibt zusätzlich `~/.emulationstation/es_log.txt`

- `viz_<szene>.log` enthält alle 10 s FPS und die Audio-Pegel, dazu das Capture-Backend

- `stt.log` – STT-Werkzeug und Listener, `whisper-server.log` – Ausgabe des Servers

- `llm.log` – LLM-Werkzeug, `llama-server.log` – Ausgabe des Servers

- `kitt.log` – Sprachpipeline: Zustände, Transkripte, Antworten, Zeiten je Runde

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
- **Sprachmodell: llama-server startet nicht oder antwortet Kauderwelsch:** `logs/llama-server.log`.
  Port 8179 belegt, Modell fehlt, oder ein zu neues Modellformat für den Build
  (`scripts/setup_phase6.sh` zieht llama.cpp nach und baut neu, wenn `vendor/llama.cpp/build` gelöscht wird).
- **F5 zeigt lange "SYSTEME LADEN":** beide Server lesen ihre Modelle; kalt von der SD-Karte dauert
  das bis zu 90 s, aus dem RAM-Cache etwa 20 s. Der Launcher liest die Modelle deshalb nach dem Start
  im Hintergrund vor (`prefetch_models` in `settings.toml`, Log-Zeile "Prefetch fertig"). `logs/kitt.log`.
- **KITT antwortet zu lang oder mit Floskeln:** System-Prompt in `kitt/personality/system_prompt.txt`,
  `max_tokens` und `temperature` in `config/kitt.toml`.
- **Sprachausgabe stumm:** `wpctl status` zeigt unter Sinks nur "Dummy Output", wenn kein
  Audioausgang da ist (HDMI-Ton nur, wenn das Display ihn annimmt). USB-Soundkarte oder
  HDMI-Sink wählen und in `config/audio.toml` `[output].target` eintragen.
- **KITT hört sich selbst / antwortet auf sich:** `resume_delay_ms` erhöhen, Mikrofon vom
  Lautsprecher weg, `require_name = true`.
- **Nach dem Boot schwarzer Bildschirm, kein Home:** per SSH `scripts/autostart_status.sh` und
  `journalctl --user -u kitt-launcher -n 50`. Steht dort "Kein Wayland-Socket", ist die Session nicht
  gestartet: `cat ~/golfcar/logs/session.log` und `grep session /etc/lightdm/lightdm.conf`.
  Notausgang: `scripts/autostart_disable.sh && sudo reboot` bringt den Desktop zurück.
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

- `campfire` (Taste 6): Lagerfeuer als Cinemagraph aus einem Foto mit echten Flammen (siehe Abschnitt
  Lagerfeuer).
- `error` (Taste 7): grüner Code, der alle 24 Sekunden zusammenbricht. Beschreibung unter
  „Systemfehler-Modus“ weiter unten.

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

## F5 – Sprachmodell (Phase 6)

**Installation:** `scripts/setup_phase6.sh` baut [llama.cpp](https://github.com/ggml-org/llama.cpp)
nach `vendor/llama.cpp` (CPU, NEON, ohne libcurl) und lädt die Kandidaten aus
`config/kitt.toml` `[llm.bench].models` nach `models/`:

| Datei | Quelle | Parameter |
|---|---|---|
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | 1,5 B |
| `Qwen3.5-0.8B-Q4_K_M.gguf` | huggingface.co/unsloth/Qwen3.5-0.8B-GGUF | 0,8 B |
| `Qwen3.5-2B-Q4_K_M.gguf` | huggingface.co/unsloth/Qwen3.5-2B-GGUF | 2 B |
| `Qwen3.5-4B-Q4_K_M.gguf` | huggingface.co/unsloth/Qwen3.5-4B-GGUF | 4 B (Obergrenze) |

Alle Q4_K_M. Qwen3/Qwen3.5 sind Thinking-Modelle, das Denken ist abgeschaltet
(`--reasoning-budget 0`, `enable_thinking=false`), weil KITT sofort antworten soll.

**Betrieb** (`kitt/llm/llama_client.py`): `llama-server` läuft dauerhaft auf 127.0.0.1:8179 mit
geladenem Modell (OpenAI-kompatible API, `--jinja` für die Qwen-Chat-Templates). Der Client
streamt Tokens, damit Phase 7 satzweise an die Sprachausgabe übergeben kann, und misst
Time-to-first-token und Tokens/s. `Kitt` hält System-Prompt und die letzten `history_turns`
Dialogrunden. Antwortlänge ist auf `max_tokens = 80` begrenzt.

**Personality:** `kitt/personality/system_prompt.txt` (Charakter, Regeln, die drei Beispiele aus dem
Master-Prompt als Few-Shot). Phase 8 verfeinert ihn anhand echter Dialoge.

**Modellwahl:** `scripts/llm_bench.sh` lädt nacheinander alle Kandidaten, stellt die zehn Fragen aus
`kitt/personality/bench_prompts.txt` jeweils ohne Vorgeschichte und schreibt nach
`docs/llm_bench_phase6.md`: Ladezeit, RSS, TTFT, Tokens/s, Antwortzeit, Antworttext und
automatisch erkannte Regelverstöße (mehr als 3 Sätze, Emoji, "Natürlich"/"Gerne", Listen,
englische Antwort). Deutsche Sprachqualität und Persona bewertet man an den Texten. Das gewählte
Modell kommt in `[llm].model`. Einzelfragen: `scripts/kitt_ask.sh "KITT, wie sieht's aus?"`.

## F5 – Sprachausgabe und komplette Pipeline (Phase 7)

**Installation:** `scripts/setup_phase7.sh` installiert das pip-Paket `piper-tts` (bringt espeak-ng-Daten
und läuft über onnxruntime), lädt die Stimmen aus `config/kitt.toml` `[tts]` nach `models/piper/`
(Quelle huggingface.co/rhasspy/piper-voices) und schreibt Hörproben nach `docs/tts_sample_*.wav`.

| Stimme | Charakter |
|---|---|
| `de_DE-thorsten-medium` (Standard) | männlich, ruhig, neutral, schnell |
| `de_DE-thorsten-high` | dieselbe Stimme, höhere Qualität, langsamer |

Beide sind synthetische Stimmen aus dem offenen Thorsten-Voice-Datensatz, keine Imitation eines
Schauspielers. `pitch_factor = 0.94` spielt die Ausgabe etwas langsamer und damit tiefer ab,
`length_scale` steuert das Tempo. Wiedergabe über `pw-play` (PipeWire), Fallback `aplay`; das Ziel
kommt aus `config/audio.toml` `[output]`.

**Pipeline** (`kitt/voice/pipeline.py`):

```
Mikrofon (48 kHz) → Listener/VAD → whisper-server → llama-server → Satz-Splitter → Piper → pw-play
   idle              listening       thinking         thinking/speaking            speaking      idle
```

- Beide Server starten parallel und bleiben geladen. Ein Warm-up füllt den Prompt-Cache des LLM.
- Antworten werden satzweise gesprochen, sobald ein Satz aus dem Token-Strom vollständig ist. Die
  erste Sprache kommt so nach LLM-TTFT plus einem Satz, nicht erst nach der ganzen Antwort.
- Während KITT spricht, ist der Listener pausiert (`resume_delay_ms` Nachlauf), damit er sich
  nicht selbst hört.
- `[voice].ignore_phrases` filtert typische Whisper-Halluzinationen bei Stille ("Untertitel",
  "Vielen Dank"), `min_words` verwirft Einwort-Fetzen, `require_name = true` lässt KITT nur auf
  Anrede reagieren.
- Jeder Audio-Block der Sprachausgabe geht per Callback an die UI (Phase 8), damit die
  Visualisierung auf das TTS-Signal reagiert.

**Tests ohne Oberfläche:** `scripts/kitt_voice.sh --say "Text"` (nur TTS),
`scripts/kitt_voice.sh --text "KITT, wie sieht's aus?"` (LLM + TTS ohne Mikrofon),
`scripts/kitt_voice.sh --seconds 60` (voller Mikrofonbetrieb, Zustände im Terminal). Das Log
`logs/kitt.log` enthält je Runde STT-Zeit, LLM-TTFT, Zeit bis zur ersten Sprache und Gesamtzeit.

## F5 – KITT-Oberfläche und Persönlichkeit (Phase 8)

`python -m kitt.ui` ist der F5-Modus: dieselbe GL-Engine wie die Visualizer mit der Szene
`visualizers/shaders/kitt/frag.glsl`, dazu die Sprachpipeline in Threads. Kein Chatfenster, keine
Eingabe. Schwarzer Hintergrund, 80er-Fahrzeugcomputer:

- oben der horizontale Scanner (32 Segmente, Tempo je Zustand), darunter vier Zustands-LEDs
- in der Mitte der Voice-Modulator mit drei Säulen, die beim Sprechen mit dem TTS-Signal
  ausschlagen und beim Zuhören mit der VAD-Wahrscheinlichkeit
- unten die Waveform (Mikrofon oder Stimme), Readouts mit Pegel und Sekunden im Zustand
- eine Readout-Zeile mit dem letzten Transkript bzw. dem gesprochenen Satz (`[ui].show_text`)
- CRT-Scanlines, Wölbung, Flimmern

| Zustand | Anzeige |
|---|---|
| SYSTEME LADEN | Scanner schnell, Säulen atmen, bis whisper-server und llama-server bereit sind |
| BEREIT | Scanner langsam, Säulen ruhen |
| HÖRE ZU | Säulen grünlich, folgen dem Mikrofonpegel, Waveform aktiv |
| VERARBEITE | Scanner rast, zufällige Segmente flackern, LED bernstein |
| SPRECHE | Säulen und Scanner pulsen mit der Stimme, Waveform bernstein |

Während KITT spricht, speist die Pipeline das Piper-Audio direkt in die Analyse (kein Monitor-Capture
nötig). `python -m kitt.ui --demo` läuft die Zustände ohne Server und Hardware durch, mit
`--screenshot` zur Kontrolle.

**Persönlichkeit:** Der System-Prompt in `kitt/personality/system_prompt.txt` wurde nach dem
Benchmark nachgeschärft (keine erfundenen Uhrzeiten oder Messwerte, Beispiele nicht wörtlich
wiederholen, keine Selbsterzählungen). Zusätzlich greifen zwei Mechanismen in der Pipeline:
`[voice].strip_openers` streicht Floskeln wie "Natürlich!" am Satzanfang, und `max_sentences`
bricht die Generierung nach drei gesprochenen Sätzen ab (die Verbindung zum llama-server wird
geschlossen, der Slot wird frei, die Historie enthält nur das Gesagte).

**Prozess-Hygiene:** whisper-server und llama-server laufen in der Prozessgruppe des F5-Modus.
Der Launcher beendet beim Moduswechsel oder nach einem Absturz immer die ganze Gruppe, damit
keine Server mit belegten Ports zurückbleiben.

## Autostart und Recovery (Phase 9)

```
Strom an → Raspberry Pi OS → lightdm (Autologin maphizi) → Session "KITT-Cart"
        → labwc (config/labwc/, ohne Panel und Desktop, schwarzer Hintergrund)
        → scripts/session_start.sh → systemd --user: kitt-launcher.service
        → scripts/run_launcher.sh → Launcher → Home-Screen
```

`scripts/autostart_enable.sh` installiert die Wayland-Session `/usr/share/wayland-sessions/kitt-cart.desktop`,
die User-Unit `~/.config/systemd/user/kitt-launcher.service`, aktiviert Linger für den Benutzer und
setzt in `/etc/lightdm/lightdm.conf` `autologin-session=kitt-cart` (Backup in
`lightdm.conf.kitt-backup`). Der normale Pi-Desktop bleibt installiert; `scripts/autostart_disable.sh`
schaltet lightdm zurück auf `rpd-labwc`. Beides wird mit dem nächsten Neustart wirksam. SSH geht
in beiden Betriebsarten.

**Recovery, drei Ebenen:**

1. Stürzt ein Modus ab (Spiel, Visualizer, KITT), startet der Launcher-Kern Home. Stürzt Home
   wiederholt ab, wartet er 10 s.
2. Stürzt der Launcher selbst ab, startet systemd ihn nach 2 s neu (`Restart=on-failure`, ohne
   Ratenlimit). Beim Stop wird die ganze Prozessgruppe beendet (Emulatoren, Server).
3. Stürzt der Compositor, beendet lightdm die Session und meldet neu an.

Ein sauberes Ende per ESC (`dev_emergency_exit = true`) oder `systemctl --user stop` wird nicht
neu gestartet, der Bildschirm bleibt schwarz, bis `systemctl --user restart kitt-launcher` oder ein
Neustart kommt. Für den Alltag `dev_emergency_exit = false` setzen.

**SD-Karte:** Logs werden rotiert (Launcher-Logs 512 KB × 3, Modus-Logs 2 MB × 2). Wer gar nicht
auf die Karte schreiben will, setzt in `config/settings.toml` `dir = "/run/user/1000/kitt-logs"`
(tmpfs, weg nach dem Neustart).

## Space-Thema

Alle Oberflächen sind auf Raumschiff-Optik umgestellt (eigene Entwürfe, keine fremden Assets,
Markennamen oder Figuren). Die klassischen Shader liegen zum Zurückschalten in
`visualizers/shaders/_classic/`; welcher Shader hinter welcher Taste steckt, steht in
`config/visualizer.toml` (`[scenes.<modus>].shader`).

| Taste | Modus | Szene |
|---|---|---|
| 8 | HOLO-ARCADE | RetroPie, unverändert |
| 2 | HYPERRAUM | `navcomputer`: Navigationscomputer mit Planetenkatalog und Anflug (siehe unten). Alternative ohne Steuerung: `hyperspace` |
| 3 | SCHWARZES LOCH | `blackhole`: Strahlverfolgung mit Lichtkrümmung (siehe unten) |
| 4 | HAL 3000 | `hal`: rotes Auge im Korridor aus Speicherbänken (siehe unten) |
| 5 | SPACE-SLOTS | `slots`: Walzen-Nahaufnahme, sechs Themen (siehe unten) |
| 6 | LAGERFEUER / AUSSENPOSTEN | `campfire`: realistisches Feuer unter Mond, Ringplanet, Nebel, Sternschnuppen, dazu Hintergrund-Ereignisse (siehe unten) |
| 7 | SYSTEMFEHLER | `error`: grüner Code in sechs Varianten, Zusammenbruch, rotes Fehlerbild in sechs Varianten, Wiederherstellung, Neustart (siehe unten) |
| 10 | BORDCOMPUTER | `shipcomputer`: gelbes Pixel-OLED mit Panels, Radar, Spektrum, Status-Symbolen, Zustände EMPFANG, DROIDENKERN RECHNET, SENDE |
| kittctl | ZIELCOMPUTER | `target`: gelber Drahtgitter-Graben in Perspektive, Zähler, Statusfelder, Zielkreis mit Sweep und Waveform (`viz_crt`) |
| kittctl | TAKTIK-SCANNER | `tactical`: grünes Gitter, 3D-Drahtgitter eines Gleiters, Radar mit Blips, Pegelbalken (`viz_eye`) |

Die fremde Schrift in den Szenen ist ein eigenes Zufallsmuster aus 3×5-Pixelglyphen, keine
lesbare oder fremde Schriftart. Home- und Boot-Screen sind gelb-monochrom mit Glyphenzeilen.

**Navigationscomputer (F2):** `config/planets.toml` enthält 32 bekannte Welten der Saga mit Typ
(Wüste, Eis, Wald, Ozean, Stadt, Vulkan, Gasriese, Sumpf, Gras, Fels, Kristall), Farben, Größe, Monden,
Ringen und einer eigenen Kurzbeschreibung. Der Shader rendert daraus eine beleuchtete Kugel mit
typischer Oberfläche (Stadtlichter auf der Nachtseite, Lavaadern, Wolken, Bänder), Atmosphärensaum,
Monden und Ringen. Bedienung: Maus links / Pfeil links = vorheriger Planet, Maus rechts / Pfeil
rechts = nächster, Mausrad blättert, Maus Mitte / Enter / Leertaste = Kurs setzen. Ablauf: ruhende
Sterne mit Planet rechts und Katalogtext links, beim Start weicht der Planet zurück und die Sterne
ziehen sich über 3,5 s zu langen Streifen, dann 14 s träger psychedelischer Schweif (Farben wandern,
Bass pulst den Tunnel, Beat blitzt), zum Schluss bricht der Tunnel zusammen und das Ziel wächst aus
der Mitte. Zeiten in `config/visualizer.toml` unter `[scenes.psychedelic]`. Die Logik steckt in
`visualizers/scenes/navcomputer.py` (Szenen-Controller der Engine: Eingabe, Phasen, Text-Overlays),
weitere Welten einfach an die TOML anhängen.

**Lagerfeuer (Taste 6, `campfire`): Rast am Rand der Galaxis.** Ein Lagerfeuer auf einem fremden Hochplateau unter der
Milchstraße, ein Ringplanet geht über eine Stunde auf (sein Ring dreht sich langsam, innen schneller als außen, und glitzert
mit den Höhen), zwei Monde, das Space-Taxi parkt im Hintergrund
(`assets/campfire/scene.png`, Glut ohne Flammen). Das Feuer ist der ruhige Herzschlag und atmet mit der Musik, nie mit
Sprüngen: bei leiser Musik Glut mit kleinen Flämmchen, bei mittlerer ein normales Lagerfeuer, bei lauter ein großes Feuer über
die Steine (drei Flammenbögen `flames_small|mid|big.png`, weich gemischt), Stille lässt es zur Glut herunterbrennen. Alle zwei bis
vier Minuten fliegt von selbst ein Scheit ins Feuer (Funkenwolke, das Feuer wird eine Weile größer), etwa alle drei Minuten ein
glühender Kristall: dann brennt es 30 bis 60 Sekunden blau-violett (`flames_blue.png`). Funken steigen auf, driften im Wind und werden am
Himmel kurz zu Sternen. Der Kessel dampft, Raummotten kreisen (mehr mit den Höhen), ein kleines Alien lugt ab und zu hinter dem
Stein hervor, das Taxi blinkt alle paar Minuten mit den Positionslichtern, Sternschnuppen, das Polarlicht wogt in Vorhängen und Strahlen über den Horizont und pulst mit dem Bass, die
Sterne funkeln mit den Höhen. Knüppel links/rechts = Windstoß (Flammen und Rauch legen sich), oben = Holz nachlegen, unten = im
Feuer stochern, Startknopf = Marshmallow am Stock (röstet je nach Feuer: roh, golden oder verkohlt), Kippschalter AN =
Nahaufnahme, AUS = zurück. Board `campfire`, `campfire_big`, `campfire_blue`, `campfire_log`. Bilder vom Bot nach
`assets/campfire/raw/` (Prompts `docs/campfire_plan.md`), Schnitt `scripts/campfire_assets.sh`. Controller
`visualizers/scenes/campfire.py`, Shader `visualizers/shaders/campfire/frag.glsl`.
Test: `python -m visualizers.engine campfire --test-signal --demo`.

**Katalog des Navigationscomputers:** `config/planets.toml` enthält jetzt 56 Objekte in drei
Gruppen, die als Beschriftung erscheinen: ECHTER HIMMEL (Sonne, Erde, Mond, Mars, Venus, Jupiter,
Saturn mit Ringen, Neptun, Pluto, Europa, Titan, Beteigeuze, Sirius, Hale-Bopp, Halley, Proxima b),
FERNE GALAXIS (die Welten der Saga und der Todesstern) und ERDACHTE WELT (Arrakis, Pandora, Vulkan,
LV-426, Krypton, Magrathea, Gallifrey). Neue Objekttypen im Shader: `star` (kochende Granulation,
Flecken, Korona mit Protuberanzen, pulst mit dem Bass), `comet` (Kern mit Koma und Schweif) und
`station` (Panelraster, Äquatorgraben, Superlaser-Schüssel mit grünem Fokus). Im Hyperraum zieht
etwa alle 25 Sekunden eines der anderen Objekte seitlich vorbei (wächst, driftet, verschwindet, mit
„PASSIERE …“ oben). Unten rechts steht „SPONSORED BY SPACEX“; liegt ein Logo als
`assets/sponsor.png` auf dem Pi (3:1, weißer Hintergrund wird durchsichtig), zeichnet der Shader es
daneben. Die Datei ist nicht im Repo (Markenrechte), lege sie selbst ab.

**Zwei Drehknöpfe, Musik und Stimme getrennt:**
- Stimme: `launcher/volume_knob.py` liest die ABS-Achse des einen Knopfs (`[volume].axis`, ohne
  Eintrag nur Beobachtung mit Log-Meldung „Achse ABS_… = …“) und schreibt einen Faktor nach
  `logs/voice_volume.txt`; jeder Sprecher (KITT, HAL, BIBO, Ansagen) liest ihn vor jedem Satz.
  `max_percent` 130 erlaubt etwas lauter als normal. `target = "sink"` regelt stattdessen alles.
  Die Grundlautstärke aller Sprecher im Verhältnis zur Musik steht in `[volume].voice_gain` (0.5 = halb so laut wie
  gerendert); der Knopf regelt darauf, die Ansagen nehmen dazu noch `announce.toml` `volume`. Das PXN-CB1 meldet die
  Knopfstellung dauernd (etwa 60-mal je Sekunde), deshalb zählt der Launcher nur Änderungen des Werts als Schritte. Tut der Knopf nichts:
  `scripts/voice_knob_check.py` zeigt die Geräte, was beim Drehen ankommt und den Faktor in der Datei, und spielt eine Ansage.
- Musik: `launcher/music_knob.py` steuert mpv über dessen Socket `/tmp/mpv.sock`, und wenn kein mpv läuft
  (Musik vom Handy über Spotify Connect, AirPlay oder Bluetooth) den ganzen Ausgang über `wpctl`; die Stimme folgt
  dann mit, der Stimmenknopf regelt sie relativ dazu. Consumer-Tasten
  Lauter/Leiser werden immer erkannt, `[music].rel = true` nimmt Dreh-Schritte (REL_MISC u. a.), `axis` eine
  absolute Achse; `step` Prozent je Schritt. Melden die Knöpfe beim Drehen Tastencodes, bindet man sie in
  `config/keymap.toml` auf `voice_up`/`voice_down` bzw. `music_up`/`music_down`. mpv startet man mit `scripts/music.sh [Ordner|Datei|URL]`
  (Zufall, Endlosschleife, Startlautstärke `[music].start_percent`), das setzt den Socket. Läuft mpv
  anderswo, genügt dort `--input-ipc-server=/tmp/mpv.sock`.

**Pi aktualisieren:** `scripts/update.sh` holt den neuesten Stand, rendert fehlende Ansagen und
startet den Launcher neu. Das ist der Standardweg für jede Änderung.

**Verkehr im Hyperraum:** Zwischen den Planeten-Vorbeiflügen zieht alle 15 bis 30
Sekunden ein kleiner Komet mit Schweif vorbei (aus der Tiefe oder querend), nur zum Anschauen. Der
Shader kennt auch Schiffe (Jäger, Satellit, Kreuzer, Ringstation, Modulstation als eigene
Silhouetten), sie sind über `TRAFFIC_KINDS` in `visualizers/scenes/navcomputer.py` abgeschaltet und
lassen sich dort wieder einschalten (die Ringstation nutzt das Ereignis RAUMSTATION). Das frühere
Abschießen mit Fadenkreuz und Laser ist entfernt; die Shader-Routinen dafür liegen noch im Code,
bekommen aber keine Werte mehr. Die Texte im Navigationscomputer verwackeln ganz dezent zur Musik
(wenige Pixel bei Bass und Beat). Schiffswinkel werden auf
0 bis 2π reduziert, weil große Winkelwerte auf der GPU ungenaue Sinus-Werte liefern.

**Waldtresen (Taste 2 im Thema THE POWER OF THE GREEN, `trip`):** Im grünen Thema ersetzt der
Waldtresen den Navigationscomputer (`config/themes.toml` `modes = { viz_psychedelic = "trip" }`; der
Launcher tauscht den Modus beim Umschalten). Ein Tresen aus Moos und Wurzeln (`assets/trip/bar.png`,
vom Piloten erzeugt) mit Glühwürmchen und atmendem Kerzenlicht, auf dem Holzteller das gewählte
Wesen aus der Speisekarte (`config/trip.toml`, 20 Stück, echt und erdacht: Fliegenpilz, Psilocybe,
Blauer Lotus, Peyote, Salvia, Bufo-Kröte, Kugelfisch, Laubfrosch, Pfeilgiftfrosch, Bananenschnecke,
Kristallpilz, Flüsterfarn, Spiegelbeere, Mondmoos, Zimtwurm, Regenbogenlurch, Nebelqualle,
Augenblume, Spiralschnecke, Honigschleim; Bilder `assets/trip/beings.png`). Knüppel links/rechts
blättert, Name, Herkunft und Wirkung stehen links. Startknopf = essen: das Wesen fliegt auf die
Kamera zu, Biss-Blitz, die Augenlider schließen sich, dann beginnt die Reise. Jedes Wesen hat ein
Profil (Farbwelt, Tempo, Spiegelzahl, Verdrehung, Symbolsatz, Verzerrung): ein Kaleidoskop aus den
Naturtexturen (`assets/trip/tex_*.png`: Blätterdach, Frosch auf Lotus, Fliegenpilz-Haut) mit
Spiralverdrehung, Rauschverzerrung, wandernden Farben, Lichtadern, Tunnelringen, das über etwa 25
Sekunden an Intensität gewinnt; Symbole aus `assets/trip/symbols.png` (Augenblüten, Frösche,
Schmetterlinge, Blätter, Farne, Schnecken, Federn, Pilze, Pollen) kreisen im Kaleidoskop und ziehen
frei durchs Bild. Musik: Bass lässt alles atmen, Beats pulsen Zoom und Lichtadern, Höhen funkeln,
Drops wechseln Palette oder Spiegelzahl. Ereignisse alle 30 bis 60 Sekunden: Froschkonzert mit
Schallringen, Pilzregen, der Wald schaut (Augen öffnen sich und blinzeln), Schmetterlingsschwarm,
Pollensturm, Lichthirsch, und wenn `assets/trip/face.png` vorhanden ist, das eigene Gesicht riesig
und wabernd. Während der Reise: Knüppel links/rechts = Spiegelzahl, oben/unten = Tempo. Die Reise
endet nur per Kippschalter: das Bild kehrt an den Tresen zurück und eine Bilanz erscheint ("Du warst
4 min 12 s weg. Der Fuchs hat dein Taxi bewacht."). Bildmaterial vorbereiten:
`scripts/trip_assets.py beings|symbols|texture|bar`. Controller `visualizers/scenes/trip.py`,
Shader `visualizers/shaders/trip/frag.glsl`. Test: `python -m visualizers.engine trip --test-signal --demo`.
Die Reise lebt von der Musik: Beats geben einen Drehstoß und einen Zoom-Puls, Bass treibt Tempo und Drehung, Mitten
verbiegen das Bild, Drops wechseln Palette, Spiegelzahl oder die Kaleidoskop-Variante (klassisch, Tunnel, Blüte,
Zellen; wechselt auch von selbst alle 25-50 s mit Überblendung) und versetzen die Texturen. Es gibt ein Programm für
alle Wesen: Spiegelzahl, Tempo, Palette, Verdrehung, Verzerrung und Symbolsatz werden bei jeder Reise neu gewürfelt
(die Profile in `config/trip.toml` sind nur noch Name, Bild und Wirkung), und alle 15-30 s wandert zufällig etwas
davon. Ereignisse kommen alle 20-40 s, dabei: Wurzeln, die von allen Seiten hereinwachsen und sich in der Mitte
verknoten (mit `assets/trip/roots.png` aus echtem Wurzelbild, sonst prozedural). Selten, frühestens nach einer
Minute und nur wenn die Musik richtig aufdreht, erscheint ein Waldgott aus der Mitte (`assets/trip/gods.png`, Atlas 3x2 à 512 aus einem Bogen mit sechs
Gesichtern: `scripts/trip_assets.py grid assets/trip/gods.png BOGEN.png 3 2 512`), atmet mit dem Bass, flackert
mit dem Beat, spricht eine Zeile (`GOD_LINES`) und löst sich wieder auf; ohne das Bild fällt das Ereignis aus.

**Moorsee (Taste 3 im Thema THE POWER OF THE GREEN, `pond`):** Das Gegenstück zum Schwarzen Loch
(`themes.toml` `modes = { blackhole = "pond" }`). Ein Waldsee bei Nacht (`assets/pond/lake.png`) mit einem
Strudel in der Mitte, der sich mit dem Bass dreht. An beiden Ufern lebt es zur Musik: auf zehn Plätzen
(`SHORE` im Controller, zwei davon im Wasser) keimen Pflanzen aus `assets/pond/shore.png` (Fliegenpilze, Farn,
Leuchtpilze, Lotus, Schilf mit Libelle, Fleischfresser; je vier Stufen Keim, jung, voll, verwelkt, fließend
überblendet), wachsen mit der Energie der Musik, stehen voll da und pulsieren mit dem Bass, platzen auf Beats Sporen
und Pollen ab, wiegen sich mit den Mitten und verwelken wieder; je lauter, desto öfter keimt etwas Neues, beim Drop
blüht das ganze Ufer, in der Stille welkt alles langsam. Knüppel links/rechts lässt auf dieser Seite gezielt etwas
sprießen. Selten (alle 50-100 s, nur bei lauter Musik) fällt von selbst ein Wesen der Speisekarte
(`assets/trip/beings.png`, `config/trip.toml`) in den See: Platscher, kurzes Treiben, dann zieht der Strudel es
über etwa eine Minute in Spiralen nach innen und streckt es zu einem immer längeren Band, das schlangenförmig zur
Musik wogt, bis es im Trichter verschwindet (Luftblasen steigen auf).
Oben = Blätterregen: Blätter und Seerosenblätter fallen, landen und drehen sich im Strudel zur Spirale.
Unten = Umkehrung: der See bäumt sich auf, eine Fontäne schleudert Frösche, Kois, Libellen, Seerosen und
Wesen zurück in die Luft, Wellen laufen zum Ufer, der Nebel reißt auf und kurz liegt der leuchtende
Seegrund frei (`assets/pond/bottom.png`). Startknopf = ein Stein hüpft über das Wasser (Ringe, Spritzer).
Kippschalter AN = Nahaufnahme in den Strudel, AUS = zurück. Musik: Bass und Beat treiben die Drehung (Drehstoß
auf jeden Beat), mit Bass greift der Strudel weiter über den See, die drei Schaumarme springen auf jeden Beat ein
Stück weiter und blitzen im Trichter auf, jeder Beat lässt das Wasser beben (Druckwelle als heller Ring vom Strudel
über den ganzen See, Zittern der Wasserfläche, kurzes Kamerarütteln) und wirft einen Ring aufs Wasser, Drops lassen
den See von innen leuchten, der Nebel und die Mondspiegelung atmen mit dem Bass,
Glühwürmchen funkeln mit den Höhen. Alle zufälligen Kreaturen (`assets/pond/creatures.png`, Atlas 6x4 via
`scripts/trip_assets.py atlas`) und Positionen (`config/visualizer.toml` `[scenes.pond]` `vortex`,
`water`) sind konfigurierbar. Controller `visualizers/scenes/pond.py`, Shader
`visualizers/shaders/pond/frag.glsl`. Test: `python -m visualizers.engine pond --test-signal --demo`.

**Das Auge des Waldes (Taste 4 im Thema THE POWER OF THE GREEN, `woodeye`):** Das Gegenstück zu HAL 3000
(`themes.toml` `modes = { hal = "woodeye" }`). Ein uralter Baum bei Nacht (`assets/woodeye/scene.png`), in der
Rinde ein riesiges Auge (`assets/woodeye/eyes.png`, 8x3: Öffnen in acht Schritten, acht Irisfarben, Blickrichtungen,
Feuer, Spirale). Jedes Musikmerkmal hat sein eigenes Element: der Bass weitet die Pupille (Linse), lässt die Rinde
pumpen und die Kamera atmen; jeder Beat schaltet das Myzel in den Wurzeln einen Schritt weiter (Lauflicht 1-2-3-4,
Muster wechseln alle 25-45 s) und lässt den Mond pulsen; acht Seerosenblätter sind die acht Frequenzbänder, links
der Bass, rechts die Höhen: wer dort sitzt, bläht den Kehlsack mit der Bandenergie, laute Bänder lassen ihn hüpfen
(flüssige Sprungfolge aus acht Bildern, `assets/woodeye/frogs.png`, vier Arten), das Auge schaut zum lautesten.
Wie viele Frösche da sind, entscheidet die Musik: in der Stille keiner, bei leiser Musik vereinzelt, wenn sie
richtig loslegt, kommen alle acht aus dem Wasser (Auftauch-Sequenz, `assets/woodeye/dive.png`), und wenn es wieder
leiser wird, springen sie nacheinander hinein. Dazu das Tauchspiel im Takt: auf Beats springt mal einer kopfüber
ins Wasser (Spritzer, Ringe, psychedelische Nachbilder), wabert als bunter Schatten unter der Oberfläche und taucht
ein paar Beats später wieder auf; die Mitten wiegen das Kronendach und lassen Pollen steigen; die Höhen
funkeln als Glühwürmchen und Tautropfen. Beim Drop blinzelt das Auge und brennt, die Iris wechselt die Farbe, eine
Sporenwolke steigt auf, alle Frösche springen, das Lauflicht wechselt die Richtung und eine Farbwelle läuft durchs
Myzel. In der Stille schließt sich das Auge langsam, das Myzel glimmt nur noch, die Blätter sind leer. Knüppel links =
die Eule kreist um den Baum (Flügelschlag auf den Beat), rechts = zwölf kleine Zwerge lugen über die Wurzeln
(`assets/woodeye/gnomes.png`, steigen nacheinander auf, wippen mit dem Bass, ducken sich auf den Beat, ab und zu
winkt einer), oben = beide, nochmal = aus; unten = Kaleidoskop (Spiral-Iris, Farben kreisen). Startknopf = Froschchor
(Welle durch alle Blätter, leere bekommen Besuch), Kippschalter AN = Nahaufnahme ins Auge, AUS = zurück. Board: Türkis,
Zwerge/Eule/Chor als
den Beat), oben = beide, nochmal = aus; unten = Kaleidoskop (Spiral-Iris, Farben kreisen). Startknopf = Froschchor
(Welle durch alle Frösche), Kippschalter AN = Nahaufnahme ins Auge, AUS = zurück. Board: Türkis, Fuchs/Eule/Chor als
Ereignisprofile (`config/wled.toml` `woodeye_*`). Augenmitte und -größe: `config/visualizer.toml` `[scenes.woodeye]`
`eye`. Bildmaterial: `scripts/trip_assets.py plate|grid|slice` (`slice` schneidet Animationsbögen in gleich große Zellen). Controller
`visualizers/scenes/woodeye.py`, Shader `visualizers/shaders/woodeye/frag.glsl`.
Test: `python -m visualizers.engine woodeye --test-signal --demo`.

**Der Pilzautomat (Taste 5 im Thema THE POWER OF THE GREEN, `forestslots`):** Das Gegenstück zur Space-Slotmaschine
(`themes.toml` `modes = { slots = "forestslots" }`), gleicher Aufbau wie diese: **vier Walzen** füllen das Bild, darüber
liegt der Waldrahmen (`assets/slots/forest_frame.png`: Rinde, Moos, Farne, Glühwürmchen; drei leuchtende Pilze hängen
von oben und links über die Walzen und blinken zum Bass). Drei Automaten, Knüppel links/rechts wechselt: PILZAUTOMAT
(`assets/slots/forest.png`: Fliegenpilz, Frosch, Eule, Glühwürmchen, Eichel, Farn, Schnecke, Fuchs, Lichthirsch =
Jackpot), TIERE DES WALDES (`forest_animals.png`: Igel, Dachs, Reh, Wildschwein, Wolf, Rabe, Fledermaus, Luchs,
Lichthirsch) und WALDGEISTER (`forest_magic.png`: Fee, Irrlicht, Hexenring, Traumfänger, Mond, Kristall, Zwerg, Alraune,
Waldgott). Knüppel oben/unten = Einsatz (Eichel, Pilz, Hirsch), Startknopf = drehen. Gewinne bei vier Walzen: drei
gleiche nebeneinander = groß, drei mit Lücke = klein, alle vier = Jackpot, Lichthirsch überall = Mega. Rahmenlichter und
Pilze pulsen zum Bass, Lauflicht über die Stege auf den Beat, Höhen funkeln, Drop = Blitz und die nächste Drehung läuft
schneller. Gewinn = Glühwürmchen und Blätter, großer Gewinn = der Fuchs tanzt (`assets/woodeye/figures.png`), Jackpot =
der Lichthirsch galoppiert mit Sporenfeuerwerk. Board `forestslots`, `forestslots_win`, `forestslots_jackpot`.
`config/visualizer.toml` `[scenes.forestslots]` `area` (Walzenfläche = Schwarzfläche des Rahmens). Controller
`visualizers/scenes/forestslots.py` (dünne Unterklasse), Shader gemeinsam `visualizers/shaders/slots/frag.glsl`.
Test: `python -m visualizers.engine forestslots --test-signal`.

**Der Herzbaum (Taste 6 im Thema THE POWER OF THE GREEN, `hearttree`):** Das Gegenstück zum Lagerfeuer
(`themes.toml` `modes = { campfire = "hearttree" }`). Ein uralter Baum bei Nacht (`assets/hearttree/scene.png`), durch
Wurzeln, Stamm und Äste laufen Adern aus leuchtendem Saft. Der Shader erkennt die Adern im Foto (Bernstein, Türkis)
und lässt sie pulsieren: der Bass ist der Herzschlag, bei jedem Schlag läuft ein Lichtimpuls von den Wurzeln durch
den Stamm in die Krone und der Stamm weitet sich; Beats schieben eine Leuchtwelle durch die Adern (Tempo folgt der
Musik, Richtung wechselt beim Drop); die Energie der Musik ist das Grundglühen, in der Stille bleibt nur ein langsamer
Ruhepuls wie bei einem schlafenden Herzen; die Mitten wiegen das Blätterdach und lassen Pollen steigen; die Höhen
funkeln als Tautropfen und Glühwürmchen. Beim Drop blüht der Baum auf: Sturm aus der Krone, die Adern wechseln die
Farbe, Lichtblitz aus den Wurzeln. Jahreszeiten (Knüppel links/rechts, wandern sonst von selbst alle
`cycle_minutes` weiter): Frühling (Laub zartgrün, Blüten, Blütenblätter, Pusteblumen), Sommer (sattgrün,
Glühwürmchen), Herbst (Krone rot-gold, Laub fällt), Winter (Frost auf dem Laub, Schnee auf den Wurzeln, Adern
eisblau, Schneeflocken). Fallende Teile aus `assets/hearttree/seasons.png` (8x3, `scripts/trip_assets.py grid`).
Oben = Sturm von Hand, unten = Wurzeln leuchten und Myzel breitet sich als Ring aus, Startknopf = großer Herzschlag
(der ganze Baum flackert auf), Kippschalter AN = Nahaufnahme an die Rinde, AUS = zurück. Board je Jahreszeit und für
Wurzeln/Herzschlag (`config/wled.toml` `hearttree_*`). `config/visualizer.toml` `[scenes.hearttree]`: `trunk`
(Stammmitte), `cycle_minutes`, `start_season`. Controller `visualizers/scenes/hearttree.py`, Shader
`visualizers/shaders/hearttree/frag.glsl`. Test: `python -m visualizers.engine hearttree --test-signal --demo`.

**Die Überdosis (Taste 7 im Thema THE POWER OF THE GREEN, `overdose`):** Das Gegenstück zum Systemfehler
(`themes.toml` `modes = { error = "overdose" }`). Kein Bluescreen, sondern der Trip, der kippt: zu viel am Waldtresen
gegessen. Albtraumwald (`assets/overdose/scene.png`) in Wellen, die sich wiederholen und jedes Mal etwas anders sind:
Warnung (10 s, das Bild atmet, Ranken kriechen herein, "ZU VIEL GEGESSEN" flackert, der Puls oben links steigt),
Vergiftung (30 s, Doppelbilder, Farben kippen ins Giftgrün und Violett, verzerrte Wesen aus
`assets/overdose/creatures.png` lauern an den Rändern und rücken auf jeden Beat näher, Fliegen schwärmen, Tunnelblick
auf jeden Bassschlag), Horror (20 s, Waldgott mit glühenden Augen lacht aus der Mitte, Negativ-Blitze und Bildsprünge
auf den Beat, dein Gesicht mit Pilzen, die daraus wachsen, Flüstertexte, Wesen springen an die Kamera), Blackout
(8 s, Schwarz mit Nachbildern, nur der Puls, dann "DU WACHST AUF. NOCH EINMAL."). Musik: Bass ist Herzschlag und
Tunnelblick, Beats sind Negativflackern und Bildsprünge, Höhen Fliegen und Rauschen, Mitten verbiegen die Ränder, laute
Musik vergiftet schneller. Drop = Schrei-Blitz in Rot-Schwarz, alle Wesen springen gleichzeitig ins Bild. Stille =
schweres Atmen, Dunkelheit kriecht. Knüppel links/rechts = Gegengift (Wasser, Kohle, Salz, Moos kauen, Froschtee):
kurz besser, dann schlimmer. Oben = Erbrechen (Bild kippt, grüne Schleimwelle, etwas Gift weg). Unten = Augen zu
(Dunkelheit mit atmenden Farbflecken, die Geräusche bleiben; nochmal = auf). Startknopf = Hilferuf, die Eule holt dich
für fünf Sekunden in ein klares Bild. Kippschalter AN = Kaltwasserschock (klar und kalt), AUS = Rückfall. Board:
Giftgrün/Violett, Horror rotes Stroboskop, Drop weiß, Blackout fast aus (`config/wled.toml` `overdose_*`). Controller
`visualizers/scenes/overdose.py`, Shader `visualizers/shaders/overdose/frag.glsl`.
Test: `python -m visualizers.engine overdose --test-signal --demo`.

**Thema CYBERPUNK (`cyber`):** Das dritte Thema ersetzt die Tasten 2 bis 7 komplett (`config/themes.toml`
`modes = { viz_psychedelic = "neonrace", blackhole = "core", hal = "oracle", slots = "cyberslots", campfire = "rooftop",
error = "blackice" }`), spricht mit eigener Stimme (`de_DE-kerstin-low`, leicht robotisch mit kurzem Hall, Sätze in
`config/announce.toml` `[themes.cyber]`) und färbt Board und Taxischein in Magenta/Cyan. Alle Bilder kommen vom Bot
(Prompts und Dateinamen in `docs/cyber_plan.md`, Rohbilder `assets/cyber/raw/`), `scripts/cyber_assets.sh` schneidet
daraus die Szenenbilder und Atlanten unter `assets/cyber/` (nach neuen Rohbildern erneut ausführen).

**Neonfahrt (Taste 2 im Thema CYBERPUNK, `neonrace`):** Das Gegenstück zum Navigationscomputer. Blick durch die
Windschutzscheibe auf eine regennasse Neonstraße (`assets/cyber/neonrace_scene.png`). Der Wagen fährt nach fünf
Sekunden von selbst los (AUTOPILOT), Startknopf startet sofort, Kippschalter hält an. Das Tempo folgt der Energie der
Musik, Beats geben einen Schub, Drops zünden Nitro. Der Autopilot wählt die Spur fließend und weicht Verkehr und
Hindernissen aus (`neonrace_obstacles.png`, 8x2: Barriere, Kiste, Hütchen, Fass, Pannenwagen, dazu querende Fußgänger,
Katzen, Händlerkarren, Roller), knapp vorbeiziehende Objekte rucken, bei hohem Tempo reagiert er gelegentlich zu spät
(BEINAHE). Knüppel links/rechts überstimmt ihn vier Sekunden, oben = Lichthupe, unten = Rückspiegel. Hologramme und
Neonschilder wechseln ihre Farbe auf jeden Beat, beim Drop alle zusammen, Lauflicht durch die Fassaden, Höhen lassen
die Hologramme flackern. Alle 30 bis 60 Sekunden ein Ereignis (Polizeidrohnen, Werbeblimp, Regensturm, Tunnel,
Konzernturm, Straßenmarkt, Kirschblütenallee). Board `neonrace`, `neonrace_start`, `neonrace_nitro`, `neonrace_honk`,
`neonrace_police`. `config/visualizer.toml` `[scenes.neonrace]` `vanish`. Controller `visualizers/scenes/neonrace.py`,
Shader `visualizers/shaders/neonrace/frag.glsl`. Test: `python -m visualizers.engine neonrace --test-signal --demo`.

**Der Kern (Taste 3 im Thema CYBERPUNK, `core`):** Das Gegenstück zum Schwarzen Loch. Ein KI-Kern in der Serverhalle
(`assets/cyber/core_scene.png`) saugt Daten ein. Jeder Beat schickt eine Welle durch die Halle (Serverschränke leuchten
auf, das Bodengitter hebt sich), harte Bassschläge werden zur Druckwelle, Lauflicht über die Schrankreihen. Objekte aus
`core_objects.png` (6x4: Drohnen, Chips, Decks, Katzen, Köpfe, Koffer) fliegen von selbst hinein (bei lauter Musik
öfter) oder per Knüppel links/rechts, spiralen 40 bis 60 Sekunden, lösen sich in Pixel auf und werden zum Datenstrom.
Oben = Drohnenschwarm (kommt auch von selbst), unten = Auswurf, Startknopf = EMP (bei jedem Drop auch von selbst),
Kippschalter AN = Nahaufnahme, AUS = zurück. Die Kernfarbe wandert alle acht Beats und springt beim Drop mit
komplementärer Halle, drei Darstellungen (Plasma, Datenwürfel, Blitzkugel) wechseln alle 30 bis 60 Sekunden. Stille =
der Kern atmet, die Halle wird dunkel. Board `core`, `core_throw`, `core_eject`, `core_emp`. `[scenes.core]` `center`,
`radius`, `auto_throw`, `auto_swarm`, `auto_eject`. Controller `visualizers/scenes/core.py`, Shader
`visualizers/shaders/core/frag.glsl`. Test: `python -m visualizers.engine core --test-signal --demo`.

**Das Orakel (Taste 4 im Thema CYBERPUNK, `oracle`):** Das Gegenstück zu HAL 3000. Im Projektionsrahmen des Schreins
(`assets/cyber/oracle_scene.png`) schwebt EIN Hologramm-Kopf, eine Android-Orakelfrau mit 32 Gesten
(`oracle_main.png`, 8x4: Blick links/rechts/oben/unten, Kopfneigungen, Halbprofile, Kinn hoch, Lauern, Schlaf, Zwinkern,
Braue, Schreck, Lächeln, Grinsen, Lachen, Zorn, Schrei, zwei Sprechmünder, Zunge, Backen, Schwindel, Glitch, Nicken,
Würgen, Übergeben, Schwall, Wischen, Brüllen). Sie wechselt die Geste im Takt: ruhig jeder vierte Beat, mittel jeder
zweite, wild jeder Beat, blinzelt alle paar Sekunden, nickt auf den Beat, atmet mit dem Bass, dreht sich leicht mit den
Mitten, Höhen = Funkenregen, Stille = sie schläft als Drahtgitter-Schemen. Beim Drop setzt sie sich eine von 16 Masken auf
(`oracle_masks.png`: Oni, Kitsune, Gasmaske, VR-Visier, Porzellan, Chromschädel, Mempo, Hockey, Pestdoktor, Neonkatze,
Clown, Glitchmaske, Goldene Totenmaske, Geisha, Drahtgitter, Schweißer) und wackelt damit 8 bis 16 Beats heftig im Takt,
mit wilden Gesten, dann nimmt sie sie ab. Die acht Neontafeln gehen auf jeden Beat hart an und aus nach wechselnden
Mustern, die Füllhöhe ist das Spektrumband, die Schranklichter blinken mit. Knüppel links/rechts/oben/unten = sie
schaut, dreht oder neigt sich dorthin (nochmal drücken = die nächste Geste der Richtung), Startknopf = das Orakel
spricht (Sprechmünder, Spruch wird getippt), Kippschalter AN = sie übergibt sich: Würgen, Mund auf, ein Schwall aus
Datenmüll (`oracle_garbage.png`: Pixelwürfel, kaputte Glyphen, Fehlerdreieck, Kabel, Chip, Diskette, Skull-Emojis,
Icons, Zahnrad, Pixelauge, Pixelherz), der über die Tafeln fällt, dann wischt sie sich den Mund; Kippschalter AUS =
Nahaufnahme zurück. Alle 20 bis 40 Sekunden von selbst ein Ereignis: Datenexplosion, Gesten-Salve, Scanner-Welle,
kurzer Glitch, Spruch, selten Übergeben, und eine Maske auch ohne Drop, wenn lange keiner kam. Board `oracle`,
`oracle_speak`, `oracle_both` (Explosion), `oracle_mask`, `oracle_vomit`. `[scenes.oracle]` `frame`, `panels`,
`mask_fit` (Lage/Größe der Maske auf dem Gesicht), `mouth` (Mund für den Schwall), `auto_event`. Controller
`visualizers/scenes/oracle.py`, Shader `visualizers/shaders/oracle/frag.glsl`.
Test: `python -m visualizers.engine oracle --test-signal --demo`.

**Pachinko (Taste 5 im Thema CYBERPUNK, `cyberslots`):** Das Gegenstück zur Slotmaschine, gleicher Aufbau: **fünf
Walzen** füllen das Bild, darüber der Chromrahmen (`assets/slots/cyber_frame.png`: Neonröhren, kleine Bildschirme,
Kabel; eine Lieferdrohne hängt von oben über die Walzen, die Neonkatze sitzt unten rechts). Drei Automaten (Knüppel
links/rechts): PACHINKO (`assets/slots/cyberslots_symbols.png`: Neurochip, Drohne, Ramen, Katana, Deck, Neonkatze,
Credit-Chip, Chromschädel, KI-Kern = Jackpot), KONZERN (`cyber_konzern.png`: Koffer voller Chips, Sicherheitsroboter,
Konzernwürfel, Überwachungskamera, Chipkarte, Serverschrank, Android im Anzug, Schwebelimousine, KI-Kern) und
NETZGEISTER (`cyber_netzgeister.png`: Glitch-Maske, Platinenspinne, Virus, Hologramm-Schädel, Pixelfisch,
Scanlinien-Auge, Glasfaserhand, Drahtgitter-Gesicht, KI-Kern). Knüppel oben/unten = Einsatz (CHIP, DECK, IMPLANT),
Startknopf = drehen. Gewinne bei fünf Walzen: drei gleiche nebeneinander = klein, vier = groß, alle fünf = Jackpot,
KI-Kern überall = Mega. Neonröhren pulsen zum Bass, Lauflicht auf den Beat, Drop = Blitz und schnellere Drehung.
Gewinn = Credit-Chips regnen und Holo-Ringe, großer Gewinn = der Samurai tanzt (`assets/cyber/oracle_figures.png`),
Jackpot = Neon-Explosion. Board `cyberslots`, `cyberslots_win`, `cyberslots_jackpot`. `[scenes.cyberslots]` `area`.
Controller `visualizers/scenes/cyberslots.py`, Shader gemeinsam `visualizers/shaders/slots/frag.glsl`.
Test: `python -m visualizers.engine cyberslots --test-signal`.

**Dachterrasse (Taste 6 im Thema CYBERPUNK, `rooftop`):** Das Gegenstück zum Lagerfeuer. Blick von einem Dach über
die Skyline (`assets/cyber/rooftop_scene.png`) und sechs Lichtzustände derselben Stadt (`rooftop_light_1..6.png`:
Blackout, roter Alarm, Säuregrün, Überlast, nur Werbung, Blitzschlag). Die Stadt wechselt im Takt ihr Licht: ein Zustand
bleibt ein paar Takte stehen und blendet weich zurück, bei lauter Musik öfter, bei Stille nur das Grundbild; nur nach einem
Drop schneidet sie ein paar Beats lang hart auf jedem Schlag
mit flackernden Werbeflächen. Vier Wetter (Regen, Nebel, Säureregen, Asche; Knüppel links/rechts, sonst
`cycle_minutes`) haben je einen Heimzustand. Unten = Stromausfall (14 s): die Stadt geht aus, Beats holen Blöcke
zurück, jeder Block mit einem anderen Lichtzustand, am Ende ein Überlast-Knall. Startknopf = EMP (10 s): Ring vom
Stadtzentrum nach außen, dahinter alles aus, Blöcke flackern und kommen mit den Beats zurück; kommt auch von selbst
alle 90 bis 180 Sekunden. Oben = Feuerwerk, Kippschalter AN = Blick nach unten, AUS = zurück. Drop = Blitz in den
höchsten Turm plus Feuerwerk. Bass = Werbeflächen, Mitten = Verkehr und Suchscheinwerfer, Höhen = Regen und Funken
(`rooftop_particles.png`). Board `rooftop`, je Wetter `rooftop_rain|fog|acid|ash`, `rooftop_fireworks`,
`rooftop_blackout`, `rooftop_lightning`. `[scenes.rooftop]` `skyline`, `cycle_minutes`, `base_fit`, `home_mix`,
`emp_auto`, `emp_min_energy`. Controller `visualizers/scenes/rooftop.py`, Shader `visualizers/shaders/rooftop/frag.glsl`.
Test: `python -m visualizers.engine rooftop --test-signal --demo`.

**Black Ice (Taste 7 im Thema CYBERPUNK, `blackice`):** Das Gegenstück zum Systemfehler: ein Hack, der schiefgeht, in
Wellen (Einbruch, Trace, Black Ice, Flatline, Phasenlängen zufällig). Alles passiert auf den Bildschirmen der
Hacker-Kammer (`assets/cyber/blackice_scene.png`): die schwarzen Monitore werden beim Start erkannt und zeigen
wechselnde Inhalte aus `blackice_screens.png` (8x4: acht Zustände eines digitalen Auges, Schädel, Warndreieck, Radar,
Fadenkreuz, Fingerabdruck, Schloss, Virus, Wellenform, Herzlinie, Weltkarte, Barcode, Countdown, Glyphenregen, Platine,
Spirale, Rauschen, Testbild, DNA, Gehirnscan, Chromhand, rotes Auge), jede Kachel animiert (Glyphenregen läuft mit dem
Bass, die Wellenform ist die echte Musik, Radar dreht, Fadenkreuz rastet auf den Beat ein), dazu prozedurale Augen,
Countdown, Rauschen, dein Fahndungsplakat, EKG, Daemonen, die Glitch-Maske, Bootzeilen. Auf jedem Beat wechseln ein bis
drei Schirme, beim Drop alle, in der Black-Ice-Phase schauen viele Augen zum Betrachter, Stille = Standby mit blinkendem
Cursor. Alle 15 bis 30 Sekunden von selbst ein Ereignis (Augen-Salve, Countdown überall, Rauschsturm, kurzer Reboot).
Raum: Doppelbild, Farbkippen, Bildsprung auf den Beat, rote Warnlampen pulsen zum Bass. Knüppel links/rechts =
Gegenmaßnahme (alle Schirme kurz Schloss "OK", dann Rückfall), oben = Reboot (Bootzeilen auf allen Schirmen), unten =
Stecker ziehen (Raum dunkel, Augen öffnen sich langsam im Dunkeln), Startknopf = Fixer-Katze auf allen Schirmen,
Kippschalter AN = Jack out (klar), AUS = Rückfall. Flatline = Raum fast aus, EKG auf allen Schirmen wird flach. Board
`blackice`, `blackice_horror`, `blackice_drop`, `blackice_blackout`, `blackice_help`. `[scenes.blackice]` optional
`screen_min_area`, `screen_black`. Controller `visualizers/scenes/blackice.py`, Shader
`visualizers/shaders/blackice/frag.glsl`. Test: `python -m visualizers.engine blackice --test-signal --demo`
(`KITT_BLACKICE_PHASE=0..3` = Startphase).

**Thema ZURÜCK IN DIE ZUKUNFT (`future`):** Das vierte Thema ersetzt die Tasten 2 bis 7 (`config/themes.toml`
`modes = { viz_psychedelic = "timejump", blackhole = "flux", hal = "clocktower", slots = "almanacslots",
campfire = "square", error = "paradox" }`), spricht als verrückter Professor (`de_DE-karlsson-low`, schnell, etwas höher,
Hauch Werkstatt-Hall, Sätze in `config/announce.toml` `[themes.future]`). Roter Faden: vier Epochen (1885, 1955, 1985,
2015), 88 Meilen pro Stunde, 1,21 Gigawatt, Feuerspuren, der Uhrturm um 22:04 und das verblassende Fahrerfoto
(`assets/taxi/future/driver.png`). Bilder vom Bot (Prompts und Dateinamen in `docs/future_plan.md`, Rohbilder
`assets/future/raw/`), `scripts/future_assets.sh` schneidet daraus Szenen und Atlanten unter `assets/future/`.

**Zeitsprung (Taste 2 im Thema ZURÜCK IN DIE ZUKUNFT, `timejump`):** Das Gegenstück zum Navigationscomputer. Blick aus
dem Cockpit der Zeitmaschine (`assets/future/timejump_cockpit.png`, die Scheibe ist im Bild schwarz und zeigt die
Epochenstraße dahinter; `cockpit_drop` schiebt die Armaturen etwas nach unten). Der Autopilot gibt nach vier Sekunden von selbst Gas
(Startknopf = sofort), der Tacho folgt der Energie der Musik, laute Musik hält den Schub, Stille lässt ausrollen; spätestens
nach 35 bis 60 Sekunden Fahrt laden die Zeitkreise und er zieht auf 88, beim Drop sofort. Bei 88 zündet der Zeitsprung: Blaulicht um die
Scheibe, zwei Feuerspuren zum Fluchtpunkt, Weißblitz, und die Straße ist in einer anderen Epoche (`timejump_1885|1955|
1985|2015.png`, nie zweimal dieselbe). Kippschalter = anhalten (egal welche Richtung), nach 25 Sekunden fährt er wieder an. Knüppel links/rechts = Spur,
oben = Hupe (Verkehr weicht, in 2015 steigt alles auf), unten = Zeitkreise umschalten (nächste Epoche vorwählen, die
Anzeige rattert). Zeitkreis-Anzeige im Cockpit: ZIELZEIT rot, JETZTZEIT grün, ZULETZT gelb, Tacho "NN MPH" unten.
Verkehr je Epoche aus `timejump_traffic.png` (8x4: Reiter und Kutschen, 50er-Autos, 80er-Autos, Flugautos und
Hoverboards). Musik: Bass ist Motorvibration, Beats lassen Laternen, Schilder und Feuerspuren blitzen, Höhen sind
Staub, Sterne, Regen oder Hologramm-Funken je Epoche, Mitten machen den Verkehr dichter, Drop = sofortiger Sprung.
Ereignisse alle 30 bis 60 Sekunden je Epoche: Pferdekutsche, Dampflok, Mistwagen, Tanzball, Skateboarder,
Einkaufszentrum, Hoverboards, Hologramm-Hai, und immer Gewitter. Board `timejump`, `timejump_start`, `timejump_jump`,
`timejump_honk`, `timejump_storm`. `config/visualizer.toml` `[scenes.timejump]` `vanish`, `windshield`, `cockpit_drop`.
Controller `visualizers/scenes/timejump.py`, Shader `visualizers/shaders/timejump/frag.glsl`.
Test: `python -m visualizers.engine timejump --test-signal --demo` (`KITT_TIMEJUMP_ERA=0..3` setzt die Startepoche).

**Fluxkompensator (Taste 3 im Thema ZURÜCK IN DIE ZUKUNFT, `flux`):** Das Gegenstück zum Schwarzen Loch. Die Werkstatt
mit dem leuchtenden Y (`assets/future/flux_scene.png`; die drei Lichtarme werden beim Start im Foto erkannt und pulsen
zum Bass, Lichtstöße laufen auf jeden Beat vom Knoten durch die Arme, die Oszilloskope zeigen die Wellenform). Knüppel
links/rechts wirft ein Objekt aus `flux_objects.png` (6x4: Hoverboard, Almanach, Skateboard, E-Gitarre, Plutoniumkoffer,
Hund, Kassette, Jukebox und mehr) von dieser Seite hinein: es wird angezogen, zieht zwei Feuerspuren, dehnt sich zur
Zeitschleife um das Y und löst sich in Blitze auf, die in die Arme laufen (40 bis 60 Sekunden). Oben = Gewitter (Blitze
schlagen in die Kabel über dem Kasten, Y flackert, Regen am Fenster), unten = Paradoxon (alles kommt rückwärts wieder
heraus, das Fahrerfoto erscheint als Polaroid und verblasst, jeder Beat holt ein Stück zurück), Startknopf = 1,21
Gigawatt (Weißblitz, Lichtbögen über alle Kabel, kurz Negativ), Kippschalter AN = Nahaufnahme, AUS = zurück. Drop =
Farbwechsel des Y und die Schleifen laufen rückwärts, Stille = nur Glimmen und Oszilloskope. Board `flux`, `flux_throw`,
`flux_storm`, `flux_eject`, `flux_overload`. `[scenes.flux]` `center`, `radius` (Suchzentrum für die Y-Erkennung).
Controller `visualizers/scenes/flux.py`, Shader `visualizers/shaders/flux/frag.glsl`.
Test: `python -m visualizers.engine flux --test-signal --demo`.

**Uhrturm (Taste 4 im Thema ZURÜCK IN DIE ZUKUNFT, `clocktower`):** Das Gegenstück zu HAL 3000. Das Rathaus in der
Gewitternacht (`assets/future/clocktower_scene.png`), das leere Zifferblatt bekommt im Shader seine Zeiger: der
Sekundenzeiger tickt auf jeden Beat, die großen Zeiger kriechen mit der Energie von 21:00 Richtung 22:04, in Stille
tickt die Uhr wie eine echte. Bei 22:04 (oder Drop oder Startknopf) schlägt der Blitz in den Turm, das Kabel zur
Laterne glüht, Weißblitz, die Uhr bleibt zehn Sekunden stehen und läuft dann zurück. Die acht Schaufenster unter dem
Turm sind die acht Spektrumbänder, Lauflicht über Fenster und Laternen auf den Beat, Bass lässt die Wolken von innen
leuchten und den Turm beben, Mitten sind Wetterleuchten, Höhen Regen und Funken am Kabel. Knüppel links = der
Professor hängt am Zifferblatt (Posen auf den Beat, beim Blitz erschrickt er), rechts = die Zeitmaschine rast mit
Feuerspuren über den Platz, oben = beide, unten = Tanzball (Girlanden-Lichter über dem Platz blinken im Takt, ein Paar
aus 1955 tanzt), Kippschalter AN = Nahaufnahme aufs Zifferblatt, AUS = zurück. Figuren aus `clocktower_figures.png`
(8x3: Professor, Zeitmaschine, Tanzpaar). Board `clocktower`, `clocktower_doc`, `clocktower_car`, `clocktower_both`,
`clocktower_dance`, `clocktower_strike`. `[scenes.clocktower]` `clock` (x, y, Radius), `windows` (x erste, x letzte,
y, Breite), `cable` (Turm zu Laterne). Controller `visualizers/scenes/clocktower.py`, Shader
`visualizers/shaders/clocktower/frag.glsl`. Test: `python -m visualizers.engine clocktower --test-signal --demo`.

**Almanach (Taste 5 im Thema ZURÜCK IN DIE ZUKUNFT, `almanacslots`):** Das Gegenstück zur Slotmaschine, gleicher
Aufbau: **drei Walzen** füllen das Bild, darüber der Casino-Rahmen von 1985 (`assets/slots/future_frame.png`: Gold,
Spiegel, Glühbirnenreihen, Neonstreifen; der Fluxkompensator leuchtet oben rechts, ein Hoverboard lehnt unten links über
die Walzen). Drei Automaten (Knüppel links/rechts): ALMANACH (`assets/slots/almanac_symbols.png`: Hoverboard, Almanach,
Plutonium, Skateboard, Kassette, Hund, Turnschuh, Fluxkompensator, Uhr 22:04 = Jackpot), WILDER WESTEN
(`future_1885.png`: Revolver, Cowboyhut, Sheriffstern, Hufeisen, Kaktus, Dampflok, Whiskey, Steckbrief, Uhr 22:04) und
ZUKUNFT 2015 (`future_2015.png`: Hoverboard, Flugauto, Turnschuh, Hologramm-Hai, Fusionsreaktor, Drohne, Videobrille,
Roboterkellner, Uhr 22:04). Knüppel oben/unten = Einsatz (CENT 1955, DOLLAR 1985, KARTE 2015), Startknopf = drehen.
Glühbirnen und Neon pulsen zum Bass, Lauflicht auf den Beat, Drop = Blitz von oben und schnellere Drehung. Gewinn =
Dollarscheine regnen, großer Gewinn = Feuerspuren und der Professor tanzt (`assets/future/clocktower_figures.png`),
Jackpot = Blitz, die Zeitmaschine fährt durch und alles kippt kurz nach Schwarzweiß wie 1955. Board `almanacslots`,
`almanacslots_win`, `almanacslots_jackpot`. `[scenes.almanacslots]` `area`. Controller
`visualizers/scenes/almanacslots.py`, Shader gemeinsam `visualizers/shaders/slots/frag.glsl`.
Test: `python -m visualizers.engine almanacslots --test-signal`.

**Marktplatz (Taste 6 im Thema ZURÜCK IN DIE ZUKUNFT, `square`):** Das Gegenstück zum Lagerfeuer. Derselbe Marktplatz
mit Rathaus und Uhrturm in vier Epochen (`assets/future/square_1885|1955|1985|2015.png`). Knüppel links/rechts =
Zeitsprung zurück/vor: Weißblitz, zwei Feuerspuren laufen über den Platz, und der Platz ist ein anderes Jahr; sonst
wandert die Zeit alle `cycle_minutes` von selbst. Fenster und Schilder leuchten mit dem Bass, Beats laufen als Lichtwelle
vom Uhrturm durch die Häuserzeile, Mitten sind Verkehrs- und Passantenlichter, Höhen je Epoche Staub, Regen,
Neon-Flackern oder Hologramm-Funken, dazu Teilchen aus `square_particles.png` (8x3: Steppenläufer, Konfetti, Ballons,
Schallplatten, Drohnen, Pizza). Drop = Blitz in den Uhrturm und Sprung in eine zufällige andere Epoche. Oben =
Feuerwerk (1885 Kanonenblitze, 2015 Drohnenshow), unten = Stromausfall (der Platz geht blockweise aus und kommt mit
den Beats zurück), Startknopf = Blitz, Kippschalter AN = Nahaufnahme auf das Zifferblatt, AUS = zurück. Board `square`
und je Epoche `square_1885|1955|1985|2015`, Ereignisse `square_jump`, `square_fireworks`, `square_blackout`,
`square_lightning`. `[scenes.square]` `clocks` (Zifferblatt je Epoche), `grounds` (Bodenkante je Epoche),
`cycle_minutes`. Controller `visualizers/scenes/square.py`, Shader `visualizers/shaders/square/frag.glsl`.
Test: `python -m visualizers.engine square --test-signal --demo`.

**Paradoxon (Taste 7 im Thema ZURÜCK IN DIE ZUKUNFT, `paradox`):** Das Gegenstück zum Systemfehler, aufgebaut wie
Überdosis und Black Ice: die Zeitlinie bricht, in Wellen. Störung (10 s, "ZEITKREISE DEFEKT", die drei Zeitkreis-Zeilen
rattern, der Puls steigt), Paradoxon (30 s, Doppelbilder, Sepia und Blitzblau, Anachronismen aus
`assets/future/paradox_intruders.png` (4x3: Tyrannosaurus, Revolverheld, Ritter, Legionär, Rocker, Polizei-Schwebeauto,
Roboter, Höhlenmensch, Pirat, Astronaut, Mammut, verblassende Person) lauern am Rand und springen auf den Beat, deine
Hand unten im Bild wird durchsichtig), 1,21 Gigawatt (20 s, Blitze auf jeden Beat, Negativ-Blitze und Bildsprünge, das
Fahrerfoto auf dem Tisch verblasst Stück für Stück, Flüstertexte "DU LÖSCHST DICH AUS"), Auslöschung (8 s, Schwarz mit
Brandloch und Filmriss, dann "ZEITLINIE WIEDERHERGESTELLT. NOCH EINMAL."). Oben links "PULS n" und "ZEITLINIE n %".
Musik: Bass = Herzschlag, Beat = Bildsprung, Höhen = Filmkorn und Kratzer, Mitten = Ränder verbiegen, Drop = Blitz und
alle Anachronismen springen, Stille = schweres Atmen, Sepia kriecht. Knüppel links/rechts = Gegenmaßnahme (Zeitkreise
reset, Almanach verbrennen, Brief an den Professor, Blitzableiter, 88 MPH: das Foto kehrt kurz zurück, dann Rückfall),
oben = Zeitkreise neu starten (Bild rollt, Ziffern rattern), unten = Foto ansehen (Dunkel, nur das Polaroid atmet und
verblasst), Startknopf = der Professor kommt mit der Zeitmaschine und holt dich fünf Sekunden in ein klares Bild,
Kippschalter AN = zurück in 1985 (klar), AUS = Rückfall. Board `paradox`, `paradox_horror`, `paradox_drop`,
`paradox_blackout`, `paradox_help`. `[scenes.paradox]` optional `photo = [x, y, Breite]`, `hand = [x, y, Größe]`.
Controller `visualizers/scenes/paradox.py`, Shader `visualizers/shaders/paradox/frag.glsl`.
Test: `python -m visualizers.engine paradox --test-signal --demo`.

**Startbildschirm (Modus `boot`):** Statt der alten Bootsequenz zeigt der Pi nach dem Start das Titelbild
"Marcs Taxi to Madness" (`assets/splash/scene.png`) bildfüllend und lebendig zur Musik: die Sonne glüht mit dem Bass
und wirft drehende Lichtstrahlen, Beats stoßen das Bild kurz heran, Höhen lassen Staub und Funken aufsteigen, Drops
blitzen. Links oben im Himmel leuchtet der Knopf "READY TO LIFT OFF" als Neonpille, die mit dem Bass glüht, auf den Beat
hüpft und ein Lauflicht am Rand hat. Das Bild bleibt stehen, bis der erste Knopf gedrückt wird: Startknopf, Knüppel oder
Kippschalter führen zum Taxistand, eine Modustaste direkt in den Modus. `config/visualizer.toml` `[scenes.splash]`
`button`, `sun`, `crop`; `config/modes.toml` `[modes.boot]`; aus mit `boot_seconds = 0` in `config/settings.toml`.
Controller `visualizers/scenes/splash.py`, Shader `visualizers/shaders/splash/frag.glsl`.
Test: `python -m visualizers.engine splash --test-signal`.

**Flug und Ankunft im Navigationscomputer:** Der Startknopf startet den Flug (Kippschalter AN
zeigt vorher nur SCHARF an). Der Hyperraumflug endet nie von selbst: erst wenn der Pilot den
Kippschalter umlegt (egal in welche Richtung), kommt die Ankunft. Nur im `--demo` gilt die feste
Flugdauer aus `config/visualizer.toml`. Logik in `visualizers/scenes/navcomputer.py`, `end_flight`.

**Ereignisse unterwegs:** Alle 30 bis 60 Sekunden passiert im Hyperraum zufällig etwas, drei
Sekunden vorher blinkt "ACHTUNG ... VORAUS" und der Bildrand pulst rot. Asteroidenfeld: Brocken
strömen aus der Tiefe vorbei, Einschläge lassen das Bild rucken, blitzen auf dem Schild mit
Wabenschimmer, die Schildanzeige im HUD sinkt und erholt sich danach. Farbnebel: dichte, treibende
Schwaden in wandernden Farben, gezackte Blitze vom Bildrand zur Mitte, "SENSOREN GESTÖRT". Sonne:
zieht riesig am Bildrand vorbei, mit Granulation, Korona, Protuberanzen, Lens-Flare und Hitzeglühen,
"HITZESCHILD AKTIV". Wurmloch: rasende Ringe mit Spiralverdrehung und kippenden Farben, am Ende
Durchbruch mit Weißblitz. Raumstation: eine große Ringstation quert das Bild, "ANDOCKEN VERWEIGERT".
Kometenschauer: ein Komet nach dem anderen, "FEUER FREI", abschießbar mit dem Startknopf. Tabelle
`EVENTS` im Controller, Effekte im Shader (`asteroidField`, `nebulaFx`, `sunFx`, `wormholeFx`).

**Space-Slotmaschine (Taste 5, `slots`):** Nahaufnahme von drei Walzen, die das ganze Bild füllen:
gedruckte Symbole auf gewölbten Trommeln mit Papierkorn, Licht von oben, dunkle Trennstege, Glasreflex.
Die Maschine steht still; nur eine Walze, die sich dreht, verschwimmt (weiche Unschärfe,
Bewegungsunschärfe, wanderndes Doppelbild), und sobald sie steht, ist sie wieder scharf. Die
Trommeln tragen tiefe, ruhige Farben des Themas, die langsam ineinanderfließen, jedes Symbol auf
einem etwas helleren Etikett. Die Walzen laufen gemächlich, das Einrasten hat einen kleinen
Rückprall. Drei Automaten mit echten Bildern: ORBITAL CASINO (fotorealistische Weltraumobjekte),
SPACE-ARCADE AUTOMAT (Comic-Stil) und KOSMISCHER WAHNSINN (grell, psychedelisch, mit
Alien-Lady, Augenpizza und Kuh-Entführung). Die Bildbögen liegen in `assets/slots/*.png`
(je 3×3 Kacheln à 256×170, vom Piloten selbst erzeugt), jedes Einschalten des Modus bringt den
nächsten Automaten (Zähler in `logs/slots_theme.txt`), der Steuerknüppel bzw. D-Pad links/rechts
wechselt von Hand (derselbe Knüppel, der beim Navigationscomputer die Planeten wechselt). Jeder
Automat hat neun Symbole (das letzte, das Schwarze Loch, ist das Jackpot-Symbol), zwei Farben für
Rahmen und Trommelband, Titel und Sprüche für Verlust, Beinahe-Treffer, kleinen Gewinn, großen
Gewinn und Jackpot. Das Spiel läuft von selbst, der Startknopf (ENTER) dreht sofort. Die
Walzen bleiben in wechselnden Mustern stehen: nacheinander, zwei zugleich, alle zugleich, eine früh
und die anderen drehen lange weiter, die letzte zögert; nach einer Niete dreht gelegentlich eine
Walze noch einmal nach. Quoten: 62 % Verlust (davon fast die Hälfte knapp daneben, das passende
Symbol steht dann direkt über oder unter der Linie), 22 % zwei gleiche, 12 % drei gleiche, 4 %
Jackpot. Die Walzen laufen zügig (Anlauf unter einer halben Sekunde, Stopp nach ein bis zwei Sekunden),
Nieten werden nur kurz gezeigt (gut eine Sekunde), Gewinne dürfen wirken (3, 5 bzw. 8 Sekunden).
Gewinn-Effekte: Aufblitzen und kurzer Stoß der Maschine, pulsierende Gewinnsymbole, Lichtstreifen,
aufsteigende Funken aus den Gewinnsymbolen, leuchtende Stege und Blende; bei großem Gewinn
Lichtstrahlen aus der Gewinnlinie; beim Jackpot dazu Goldregen über das ganze Bild und laufende
Farben. Bei Verlust dunkeln die Walzen kurz ab. Guthaben
startet bei 1337 Credits, Einsatz 10, Gewinne 25 / 150 / 1000.
Technik: Die Bildbögen werden beim Start zu einem Atlas zusammengesetzt (Zeile je Automat, neun
Kacheln nebeneinander, darunter die Walzenstreifen), den der Controller (`visualizers/scenes/slots.py`)
als Textur an den Shader (`visualizers/shaders/slots/frag.glsl`) gibt; die Engine lädt
Controller-Bilder über `images()` hoch. Neuer Automat: Bildbogen 768×510 (3×3) nach `assets/slots/`
und Eintrag in `visualizers/scenes/slots_themes.py` (Symbolnamen, Farben, Sprüche).

**Taxistand und Themenwahl (`home`, Taste 1):** Kein Menü, zwei Dinge. Links groß das Missionslogo (`assets/taxi/mission.png`, vom Piloten erzeugt), additiv über den Sternen, pulst leicht mit dem Bass, ein Lichtschein wandert darüber; darüber schweben zwölf kleine Figuren aus dem Figurenbogen des Piloten (`assets/taxi/sprites.png`, Atlas aus `scripts/taxi_sprites.py`: Köpfe, Planeten, Pizza, Bier, Handtuch, Ente, Buddha), jede auf eigener Bahn, wippt und dreht sich leicht, mit dem Bass etwas stärker. Unter dem Logo MISSION mit wechselndem Auftrag, Funkspruch und die Themenzeile (D-Pad links/rechts blättert, Start wählt). Rechts der Taxischein: das gelbe Taxischild als Karte in Themenfarbe mit Karo-Bändern und Leuchtkasten TAXI, darauf das Fahrerfoto (`assets/taxi/driver.png`) als digitale Lizenz: der Kopf wiegt und atmet leicht, Hologramm-Zeilen und Lichtwischer, jeder Beat zoomt ins Gesicht und in den Augen drehen psychedelische Kreisel, harte Beats lösen Glitch-Streifen aus (Augenmitten in `config/visualizer.toml` `[scenes.taxi] eyes`, `eye_r`). Darunter Name, Taxinummer, Lizenz, Fahrten, Beschwerden, Taxameter, letzter Fahrgast und ein Strichcode; der Rand pulst in Rahmenfarbe. Ohne driver.png wird das alte Porträt `assets/pilot.png` verwendet. Schon beim Blättern nehmen das LED-Board (WLED) und die Tastenbeleuchtung des PXN-Boards die Farbe des angezeigten Themas an, beim Bestätigen blitzt der Schein kurz auf. Vier Themen (`config/themes.toml`), beide nach demselben Prinzip mit eigenem Bildsatz unter `assets/taxi/<dir>/` (Logo, Figuren-Atlas, Fahrerfoto, Augenpositionen, Aufträge, Titel des Scheins, Farbe): PER ANHALTER DURCH DIE GALAXIS (gelber Schein, Space-Taxi-Fahrer) und THE POWER OF THE GREEN (grüner Schein, Waldfahrer, Blätter, Pilze, Käfer, Schmetterlinge und Tiere als schwebende Figuren) und ZURÜCK IN DIE ZUKUNFT (oranger Schein, Zeitreise-Fahrer, DeLoreans, Fluxkompensator, Hoverboard, Uhrturm und Zeitanzeige als schwebende Figuren) und CYBERPUNK (magentafarbener Schein, Neon-Fahrer, Neon-Objekte aus Nacht-Tokio: Drachen, Schwerter, Masken, Drohnen, Bonsai, Koi). `scripts/taxi_sprites.py LOGO BOGEN --out assets/taxi/<dir>` baut Logo und Atlas und rechnet dabei schwarzen Hintergrund oder ein eingebranntes Transparenz-Schachbrett heraus; `--split N` trennt Objekte, die sich im Bogen berühren, `--prefer-large` nimmt die größten Teile zuerst; auf schwarzem Grund werden Objekte als gefüllte Flächen genommen. Das Logo wird in seinem eigenen Seitenverhältnis gezeichnet.

**Schwarzes Loch (Taste 3, `blackhole`):** Echte Strahlverfolgung mit Lichtkrümmung im Shader
(64 Schritte pro Pixel, Newton-Näherung der Ablenkung): Die Akkretionsscheibe aus glühendem Gas
wölbt sich über und unter das Loch, der ferne Teil der Scheibe erscheint als Bogen oben und als
dünner Ring unten, der Photonenring entsteht aus Strahlen, die dem Horizont knapp entkommen sind,
Sterne und Nebel im Hintergrund werden mitgezogen. Doppler-Helligkeit: die Seite, die auf uns
zukommt, ist heller und heißer. Das Gas rotiert keplersch (innen schnell), mit Wirbeln und zwei
Spiralarmen. Musik: das Spektrum liegt als Ringe auf der Scheibe (innen Bass, außen Höhen), der
Bass pulst Scheibe, Dunst und Linsenstärke, Mitten färben das Gas blauweiß, Höhen lassen es funkeln,
jeder kräftige Beat zündet einen Jet aus den Polen (klingt über drei Sekunden ab) und einen kurzen
Flare. Pro Start zufällig: eine von drei Gaspaletten (orange/weiß, blau/violett, gold/rot),
Neigung, Orbitrichtung und Tempo der langsam kreisenden Kamera. Start zündet den Jet,
Kippschalter AN fährt näher heran.
Planeten werfen: Steuerknüppel LINKS/RECHTS wirft einen zufälligen Planeten aus dem
Katalog (`config/planets.toml`, auch Sterne, Kometen, der Todesstern) von dieser Bildseite ins Loch.
Er erscheint erst als Kugel (mit Ringen, Streifen, Stadtlichtern je nach Typ), wird über 50 bis 70
Sekunden spiralig eingezogen und dabei zu einem immer längeren, dünneren Band gestreckt
(Spaghettisierung), das sich schlangenförmig zur Musik windet (Bass und Mitten bestimmen Ausschlag
und Tempo der Wellen, alles sehr langsam), dessen Farben mit zunehmender Streckung psychedelisch
durchwandern, und das nahe am Horizont rot verglüht und verschwindet. Zwei Planeten können
gleichzeitig unterwegs sein; ihr Name steht klein am oberen Rand.
OBEN wirft einen Asteroidenschwarm: zwei Dutzend unregelmäßige Brocken fallen als Perlenkette von
oben hinein, quer zur Bahn gestreut, jeder wackelt für sich zur Musik, Bass lässt Glut in den
Rissen leuchten, Höhen lassen einzelne Brocken funkeln, nahe am Loch werden sie in Bahnrichtung
langgezogen und verglühen. UNTEN löst die Umkehrung aus, das Loch spuckt aus: gut eine Sekunde
schwillt die Glut um das Loch pulsierend an und das Bild wird nach innen gezogen, dann Blitz,
Druckwelle als Ring nach außen, Jet an beiden Polen, eine Trümmerfontäne aus über vierzig glühenden
Brocken mit Schweif, die Akkretionsscheibe läuft vier Sekunden rückwärts, und alles, was gerade
hineinfällt (Planeten, Schwarm), fliegt seine Spiralbahn mit dreifacher Geschwindigkeit wieder
hinaus ("WIRD AUSGESPUCKT"). Nach acht Sekunden ist alles wieder normal. `visualizers/scenes/blackhole.py`
(Hüllkurven, Kamera, Würfe), Shader `visualizers/shaders/blackhole/frag.glsl` (Band in
Bildkoordinaten über dem Strahlverfolgungsbild), `render_scale 0.35` mit 36 Schritten (auf dem
Pi 5 liefen 64 Schritte bei 0.5 nur mit 9 fps).

**Galaktische Nachrichten (`news`, über `scripts/kittctl news`):** Holo-Studio des Senders GNN mit Lichtkegeln,
drehendem Holo-Globus und einem Droiden-Sprecher, dessen Mundbalken zur Stimme schwingen. Das lokale
Sprachmodell erfindet absurde Meldungen in strengem Nachrichtenton (Ressorts GALAXIS, GOLFPLATZ,
SPORT, WIRTSCHAFT, PROMI, TECHNIK, VERKEHR; beim Golfplatz fließen Uhrzeit und gespielte Spiele aus
dem Bordbuch ein), jeweils Schlagzeile plus ein bis zwei Sätze, vorgelesen von der Roboterstimme.
Bauchbinde unten links, Laufband mit den letzten Schlagzeilen, jede fünfte Meldung EILMELDUNG mit
rotem Balken, jede vierte Runde ein Wetterpanel für drei Planeten. Die nächste Meldung wird
erzeugt, während die aktuelle vorgelesen wird. Start = nächste Meldung, LINKS/RECHTS = Ressort,
Kippschalter = Pause. Ohne Sprachmodell oder im `--demo` laufen feste Meldungen. Prompt in
`kitt/personality/news_prompt.txt`, Logik in `kitt/news/app.py`, Shader `newsroom`. Der Modus
startet nur den llama-server, keine Spracherkennung.

**HAL 3000 (Taste 4, `hal`):** Ein Korridor aus roten Speicherbänken in Perspektive, dessen
Lichtzellen träge mit der Musik leuchten, in der Mitte die schwarze Konsole mit Chromring, Lautsprechergitter und
dem roten Auge: Linse mit Tiefe, Lichtbögen, glühender Kern, der mit der Stimme pulst, beim Hören
mit dem Pegel atmet und beim Nachdenken eine wandernde Markierung zeigt. HAL spricht ohne Weckwort
über das Sprachmodell, ruhig, höflich, leicht beunruhigend, höchstens zwei Sätze, oft mit leiser
Gegenfrage, nennt den Piloten beim Namen (`pilot_name`). Alle 50 bis 100 Sekunden Stille sagt er
von sich aus etwas (erfundene Wahrscheinlichkeiten, kleine Unregelmäßigkeiten, Vertrauensfragen).
Stimme langsamer als der Bordcomputer, mit nur einem Hauch Ringmodulation. Start = HAL soll etwas
sagen, OBEN/UNTEN = Blende.
Figuren statt Konsole: Steuerknüppel LINKS blendet die HAL-Konsole aus und lässt einen Astronauten
durch den Gang schweben, RECHTS ein Alien, OBEN beide zugleich (nebeneinander), UNTEN wieder HAL.
Die Figuren (`assets/hal/figures.png`, freigestellt mit `scripts/hal_figures.py`, vom Piloten
erzeugt) treiben auf langsamen Bahnen, drehen sich träge und tanzen zur Musik: Bass lässt sie
federn, jeder Beat gibt einen Schwung in die Drehung, Mitten lassen den Körper wellig schwingen
(Kopf und Beine gegenläufig), Höhen ein feines Zittern; das Lauflicht des Gangs streift sie, rotes
Umgebungslicht und ein weicher Schein setzen sie in den Raum. HAL spricht dabei weiter.
Standard ist `[hal].mic = false`: HAL hört nicht zu, öffnet kein Mikrofon, senkt die Musik nie ab
und lädt keine Spracherkennung; er spricht nur von sich aus und auf den Startknopf. Alles Folgende
zum Sprechmodus gilt erst mit `mic = true`.
Musik und Stimme getrennt: Der Korridor hört die Musik (Quelle `playback`, also alles, was über den
Pi läuft) und reagiert bewusst langsam darauf (`kitt/hal/motion.py`): Der Gang treibt ganz langsam
nach vorn oder hinten (Tempo aus der über Sekunden geglätteten Energie, nichts zuckt im Takt), ein
Drop (Beat nach einer leisen Stelle) lässt den Gang anschwellen und kehrt meist die Fahrtrichtung
um (der Gang bremst weich ab und fährt rückwärts an; ohne Drops alle ein bis zwei Minuten von
selbst). Lauflicht im Takt: Ein Beat-Zähler schaltet bei jedem Beat 1-2-3-4 weiter (ohne erkannte Beats
läuft er im zuletzt gemessenen Tempo weiter, bei Stille gemächlich), und je Schritt leuchtet ein
anderer Teil des Gangs in Schrittfarbe auf (weißrot, orange, magenta, gold), der Rest dunkelt beim
Anschlag kurz ab. Sechs Lauflicht-Muster, die alle 25 bis 45 Sekunden und bei jedem Drop wechseln:
Tiefenviertel von hinten nach vorn, Reihen von innen nach außen, Streben-Abschnitte, Wand um Wand,
jede vierte Spalte, ein Ring, der im Beat nach vorn läuft. Wellen laufen durch die Wände, das Rot
wandert mit der Energie nach Orange und Magenta (je Zelle leicht anders), Höhen lassen einzelne
Zellen funkeln, in Wandfenstern erscheinen weiße Schriftzeichen, weiße Lichtstreifen gleiten durch.
Variationen: fünf Zellenmuster (Speicherbänke, schmale Lamellen, große Tafeln, Punktraster,
Rhythmus-Spalten), das Muster wechselt alle ein bis zwei Minuten; alle 5 bis 15 Sekunden hüpft eine
einzelne andersfarbige Zelle (cyan, grün, weiß, violett, gelb) im Takt durch eine Wand; alle 20 bis
50 Sekunden läuft eine breite Farbwelle von hinten nach vorn durch den Gang. Rot bleibt die
Hauptfarbe. Das Auge reagiert nur auf HALs eigene Stimme (`uVoice`). Sprechmodus über die Sprechtaste: ein Druck senkt die
Musik auf `[volume].duck_percent` der aktuellen Lautstärke und schaltet das Mikrofon ein; während
HAL antwortet, geht die Lautstärke kurz auf normal, danach wieder leise. Der nächste Druck stellt
die Lautstärke wieder her und schaltet das Mikrofon ab. Die Sprechtaste ist eine eigene Taste des
Boards (nicht der Kippschalter, der bleibt dem Navigationscomputer): entweder `[buttons].talk_code = N`
in `config/settings.toml` (der Remapper schickt dann direkt F15) oder in `config/keymap.toml`
`code = N` mit `action = "talk"` (der Launcher schickt F15 nur, wenn HAL läuft). Den Code zeigt
`scripts/input_monitor.py 10` oder das Launcher-Log als "Taste ohne Belegung: code = N". Test ohne Taste: `scripts/kittctl talk`.
Mit `[hal].kipp_talk = true` schaltet zusätzlich wie früher der Kippschalter (unten = an, oben = aus).
Ohne Sprechmodus hört HAL nicht zu und der Mikrofonstream ist wirklich geschlossen
(`AudioCapture.suspend()`), die Musik läuft normal. Nach `[hal].talk_timeout` Sekunden
ohne Gespräch (Standard 150) endet der Sprechmodus von selbst, damit die Musik nicht versehentlich
leise bleibt. Bluetooth-Headset als Lautsprecher (z. B. Bose QC35 II): Ein Bluetooth-Headset kann Musik in
Stereo (A2DP) oder Mikrofon plus Mono-Ton (HFP) liefern, nie beides. Sobald irgendein Programm das
Headset-Mikrofon öffnet, schaltet WirePlumber auf HFP um, die Musik wird leise und blechern. Darum
hält HAL das Mikrofon nur im Sprechmodus offen, und `config/audio.toml`
`[capture].avoid_bluetooth_mic = true` lässt die Spracherkennung ein anderes Mikrofon (USB) nehmen,
wenn eines da ist. Gibt es nur das Headset-Mikrofon, bleibt Sprechen mit HAL nur im HFP-Profil
möglich (Musik solange mono); für Musik und Gespräch gleichzeitig ein USB-Mikrofon anschließen.
`scripts/bt_a2dp_lock.sh` verbietet WirePlumber das Umschalten ganz (Headset bleibt immer bei A2DP,
`--undo` hebt es auf). `scripts/hal_audio_check.sh` zeigt in einer Ausgabe Standardgeräte,
Bluetooth-Profil, ob Musik-Monitor und Mikrofon Daten liefern und die letzten Audio-Logzeilen.
Allgemein: Persona-Szenen können über
`music_source()` eine eigene Musikquelle wählen und bekommen dann `uVoice` als Stimmpegel. Prompt `kitt/personality/hal_prompt.txt`, Logik `kitt/hal/app.py`,
Shader `visualizers/shaders/hal/frag.glsl`. Eigene Gestaltung, keine Fremdgrafik.

**Klügere Antworten:** Die Prompts von HAL und BIBO beginnen jetzt mit der Regel „erst auf die
Frage eingehen, dann Charakter“, nutzen Allgemeinwissen ausdrücklich und halten nur Wetter,
Position und Messwerte für unbekannt (vorher verbot der Prompt dem kleinen Modell zu viel). HAL:
bis zu drei Sätze, Temperatur 0.55. Wer mehr Verstand will, trägt in `config/settings.toml`
`smart_model = "Qwen3.5-4B-Q4_K_M.gguf"` ein (nur für HAL, liegt nach `scripts/llm_bench.sh` unter
`models/`): deutlich klügere Antworten, aber etwa doppelte Antwortzeit auf dem Pi.
Wenn der Roboter an einer Frage vorbeiredet, zuerst die Zeile „> …“ am unteren Rand prüfen: Das ist,
was die Spracherkennung verstanden hat. Stimmt die nicht, liegt es am Mikrofon, nicht am Modell.

**Startzeit der Figuren:** Die Oberfläche ist bereit, sobald die Server laufen; das Füllen des
Prompt-Caches („Systemcheck“, auf dem Pi rund 35 Sekunden) läuft im Hintergrund. HAL zeigt unten
rechts eine kleine Musikanzeige (Quelle, Stille oder Pegelbalken), damit man ohne Log sieht, ob die
Musik ankommt. Die Musikquelle `playback` versucht zuerst den Monitor des Standard-Sinks über
`stream.capture.sink`, dann ausdrücklich mit `--target <Sink>`.

**Antwortzeit:** Der Faktenblock (Uhrzeit, Laufzeit, Spiele) hängt nicht mehr am System-Prompt,
sondern am Ende der jeweiligen Anfrage. Vorher änderte er sich jede Minute, der Prompt-Cache des
Servers wurde bei jeder Antwort verworfen und der ganze Prompt neu gerechnet (auf dem Pi etwa
35 Sekunden). Jetzt bleiben System-Prompt und Historie im Cache, nur die neue Zeile wird gerechnet.
Erwartung auf dem Pi: erstes gesprochenes Wort nach etwa 10 bis 15 Sekunden (Spracherkennung
4 bis 6 s, Modell 5 bis 8 s), Messung mit `scripts/kitt_latency.sh`.

**Stimme einstellen:** `[tts]` in `config/kitt.toml` kennt neben `length_scale` (Tempo) und
`pitch_factor` jetzt `noise_scale` (Ausdruck, 0.667 Standard, 1.0 überdreht) und `noise_w`
(Variation der Silbendauer). BIBO spricht hell, schnell und ohne Maschineneffekt, mit viel Ausdruck,
und ruft eher, als dass er redet.

**Bord-Droide BIBO (`droid`, über `scripts/kittctl droid`):** Ein kleiner Pixel-Droide im Hangar, der zur Musik tanzt
(Beat = Hüpfen, Mitten = Arme und Kopf), mit Auge, Antenne, Mundgitter und Ohrschüsseln, die beim
Hören leuchten. Er hat Laune, Energie und Öl, die in `logs/droid_state.json` über Tage erhalten
bleiben: Energie und Öl sinken mit der Zeit, bei wenig Öl rostet er sichtbar, bei wenig Energie
hängen die Lider, die Laune färbt Auge und Mundwinkel (rot, blau, grün). Nach einem Tag Abwesenheit
begrüßt er beleidigt. D-Pad OBEN ölt (Tropfen, Funkeln), UNTEN füttert (Batterie fliegt in den
Bauch), LINKS/RECHTS schubst (er wackelt, wird sauer), Start lässt ihn sofort etwas fragen.
Gespräch ohne Weckwort: BIBO hört auf alles, antwortet in Droidisch (verständliches Deutsch mit
verdrehtem Satzbau, technischen Wörtern für Alltagsdinge, gelegentlichem Piepen, niedlich falscher
Logik) und stellt alle 30 bis 80 Sekunden Stille von sich aus eine Frage, erzählt eine falsche
Theorie oder gesteht etwas. Höhere, schnellere Roboterstimme als der Bordcomputer. Prompt in
`kitt/personality/droid_prompt.txt`, Logik in `kitt/droid/app.py`, Shader `droid`. Beide Figuren
nutzen die gemeinsame Oberfläche `kitt/ui/persona.py` und die Sprachpipeline mit Regieanweisungen
(`handle_text(..., hidden=...)`).

**Systemfehler-Modus (Taste 7, `error`):** Grüner Code, der zusammenbricht. Den Ablauf steuert
`visualizers/scenes/error.py`, jeder Durchlauf fällt anders aus, und auch der Einstieg ist zufällig
(meist mitten in einer Code-Phase, manchmal direkt in einem Ereignis): 9 bis 18 Sekunden Code in einer
von sechs Varianten (Zeichenregen, Hexdump, Boot-Protokoll mit `[ OK ]`/`[WARN]`/`[FAIL]`, Bitraster,
Quelltext mit roten FEHLERCODE-Zeilen, Spektrum als Zeichensäulen; nie zweimal dieselbe
hintereinander), dann würfelt der Controller, was passiert:

- **Absturz (gut die Hälfte):** Zusammenbruch mit zufälliger Stärke (Zeilen reißen, Blöcke springen,
  roter Geist des Codes, Rauschen, ERROR-Stempel), dann eines von sechs Fehlerbildern (riesiges
  zitterndes ERROR mit Fehlercode, rot blinkende SYSTEMFEHLER-Kacheln mit Warnband, ERROR-Kaskade,
  Kernel-Panic-Protokoll, Countdown mit KERN INSTABIL und Weißblitz, Bildrauschen mit SIGNAL
  VERLOREN), danach WIEDERHERSTELLUNG-Balken und getipptes NEUSTART.
- **Eingabe erforderlich (selten, etwa jeder achte Durchlauf, nie zweimal nacheinander):** ein
  Kasten mit Pfeil und DRUECKE OBEN / UNTEN / LINKS / RECHTS oder START samt Restzeit-Balken.
  Richtig gedrückt: ZUGRIFF GEWAEHRT, SYSTEM STABIL, der Code läuft sauber weiter. Falsch: ALARM mit
  FALSCHE EINGABE, SPERRE AKTIV, dann harter Absturz. Keine Antwort: KEINE ANTWORT, SYSTEM
  UEBERNIMMT, direkt ins Fehlerbild. D-Pad und Startknopf des Boards kommen als Pfeiltasten und
  ENTER an.
- **Virus entdeckt:** eine rote Infektion frisst sich durch den Code, Scanzeile, Prozentanzeige.
  Startknopf = QUARANTAENE, die Infektion zieht sich zurück; sonst manchmal von selbst, manchmal
  Absturz.
- **Schilde ausgesetzt:** Sechseck-Schild, Prozent fallen, Segmente fallen aus, das Bild flackert,
  Einschläge; mal SCHILDE WIEDER OBEN, mal Absturz.
- **Eindringling im System:** ein Cursor springt durch den Code, ORTUNG läuft hoch; mal ISOLIERT,
  mal ALARM und Fehlerbild.
- **Fehlalarm:** kurzer Riss, FEHLALARM, weiter geht es.

Musik: Bass steuert Tempo, Helligkeit, Spurlänge und Zittern, Mitten lassen die Zeichen schneller
wechseln, Höhen erzeugen Funken, der Beat lässt Spalten aufblitzen, verschiebt Zeilen und blitzt im
Fehlerbild, das Spektrum färbt Spalten und Ringe. Jeder Durchlauf hat einen eigenen Zufalls-Seed,
auch über Neustarts hinweg. Schrift ist ein eigener 5×6-Pixelfont im Shader, alle Texte sind
Deutsch oder generisch. Shader: `visualizers/shaders/error/frag.glsl`, `render_scale 0.6`. Zum
Prüfen einzelner Teile überstimmt `--uniform` den Controller, z. B.
`scripts/viz_test.sh error --test-signal --seconds 5 --uniform uPhase=6 --uniform uPrompt=2`
(Phasen: 1 Code, 2 Zusammenbruch, 3 Fehler, 4 Wiederherstellung, 5 Neustart, 6 Eingabe, 7 Virus,
8 Schilde, 9 Stabil, 10 Alarm, 11 Eindringling; dazu `uCodeVar`/`uErrVar` 0..5, `uPct`, `uOutcome`).
`--demo` beantwortet Aufforderungen von selbst.

**Roboterstimme:** `[tts].robot = true` legt Ringmodulation (`robot_freq`), einen kurzen Kammfilter
(`robot_comb_ms`) und Bit-Reduktion (`robot_bits`) über die Piper-Stimme. `robot_mix` regelt den
Anteil, 0 = normale Stimme. Nach einer Änderung `scripts/announce_build.sh` erneut ausführen, damit
auch die Ansagen die neue Stimme bekommen (vorher `rm models/announce/*.wav`).

**Persönlichkeit:** KITT ist jetzt der Bordcomputer eines getarnten Raumgleiters, redet in
Raumfahrtbegriffen (Sektor, Schilde, Hyperantrieb, Basis statt Clubhaus), bleibt aber trocken und
erfindet keine Markennamen oder Figuren. Ansagen in `config/announce.toml` entsprechend.

## Extras

**Ansagen beim Moduswechsel** (`config/announce.toml`): KITT kommentiert jeden Tastendruck mit einem
zufälligen Satz aus der Liste des Modus, dazu eine Boot-Ansage. Die Sätze werden einmal mit Piper
vorgerendert (`scripts/announce_build.sh`, nach jeder Textänderung erneut) und liegen als WAV in
`models/announce/`. Der Launcher spielt sie ohne Modell-Ladezeit über `pw-play` ab. Aus mit
`announce = false` in `settings.toml` oder einer leeren Liste je Modus.

**Boot-Sequenz:** vor dem Home-Screen vier Sekunden Scanner, Systemcheck-Zeilen und "KITT-CART
ONLINE" mit Sprachansage (`boot_seconds` in `settings.toml`, 0 = aus). Der Boot-Modus ist ein
gewöhnlicher Modus, der sich selbst beendet.

**Bluetooth vom Handy als Musikquelle:** `scripts/setup_bluetooth.sh` macht den Pi zum
Bluetooth-Lautsprecher "KITT-Cart" (A2DP-Senke über PipeWire, Auto-Pairing-Agent als User-Dienst).
Musik vom Telefon läuft über den Standard-Sink des Pi. Mit `source = "playback"` in
`config/audio.toml` analysieren die Visualizer das Abgespielte statt des Mikrofons, also Bluetooth,
Spiele und KITTs Stimme, ganz ohne Mikrofon. Die Spracherkennung bleibt immer am Mikrofon.
Test: `scripts/viz_test.sh crt --source playback`.

**Spotify Connect und AirPlay (Musik vom Handy schicken):** `scripts/setup_cast.sh` richtet zwei
Benutzerdienste über PipeWire ein: `kitt-spotify` (librespot aus dem raspotify-Paket, der Pi erscheint in der
Spotify-App unter "Geräte" als "KITT-Cart", braucht Spotify Premium) und `kitt-airplay` (shairport-sync, der Pi ist
auf iPhone/iPad/Mac ein AirPlay-Lautsprecher "KITT-Cart", damit SoundCloud, YouTube und alles andere). Beides landet
auf dem Standard-Sink (Bose-Headset oder Klinke), und die Visualizer sehen die Musik über `source = "playback"`.
Einen echten Chromecast-Empfänger gibt es für den Pi nicht (Google-Protokoll); Android-Handys ohne AirPlay nehmen
die Bluetooth-Senke (`scripts/setup_bluetooth.sh`). Die Lautstärke von Spotify und AirPlay regelt das Handy, der
Musik-Drehknopf nur mpv. Der laufende Spotify-Titel steht in `logs/now_playing.txt` (`scripts/spotify_event.sh`).
Prüfen: `scripts/setup_cast.sh --status`, anderer Name: `--name NAME`, entfernen: `--undo`.

**Eigene Stimme und eigene Sätze je Thema:** `config/announce.toml` kann je Thema einen Block `[themes.<name>]`
mit `voice` (Piper-Stimme, wird beim Rendern nachgeladen), `tts` (Abweichungen vom KITT-Profil in `kitt.toml`, z. B.
`pitch_factor`, `length_scale`, `robot = false`, `echo_ms`/`echo_mix`/`echo_decay` für Hall) und `[themes.<name>.lines]`
mit eigenen Sätzen je Gruppe haben. THE POWER OF THE GREEN spricht als Waldgeist (`de_DE-pavoque-low`, tief, langsam,
mit Hall), CYBERPUNK als Netz-KI (`de_DE-kerstin-low`, leicht robotisch mit kurzem Hall), ZURÜCK IN DIE ZUKUNFT als verrückter Professor (`de_DE-karlsson-low`, schnell und atemlos); alle haben für jeden Modus eigene Sätze; Gruppen, die im Thema fehlen, werden mit den Standardsätzen in der
Themenstimme gesprochen. Der Launcher sagt immer den tatsächlich gestarteten Modus an (im grünen Thema also das Auge
des Waldes statt HAL), und der Taxistand begrüßt beim Bestätigen eines Themas mit dessen Stimme (Gruppe `theme`).
Rendern: `scripts/announce_build.sh` (läuft bei jedem `update.sh`; Dateien `models/announce/<thema>__<gruppe>_<hash>.wav`).
Test: `python -m kitt.announce --play woodeye green`.

**Spielstatistik für KITT:** `scripts/configure_gaming.sh` installiert zwei RetroPie-Hooks
(`runcommand-onstart.sh`, `runcommand-onend.sh`), die jeden Spielstart und jedes Spielende nach
`logs/games.jsonl` schreiben. `kitt/context.py` macht daraus ein kurzes Bordbuch (zuletzt gespieltes
Spiel mit System, Uhrzeit und Dauer, Sitzungen heute, meistgespieltes Spiel) plus Uhrzeit und Laufzeit,
das je Anfrage an den System-Prompt gehängt wird. KITT darf diese Fakten nennen, alles andere weiterhin
nicht erfinden. Aus mit `context = false` in `[voice]`.

**Tagesform:** KITT hat jeden Tag eine andere Laune aus `kitt/personality/moods.toml` (neutral,
genervt, pedantisch, nostalgisch, gönnerhaft, philosophisch, effizient, verschwörerisch, sportlich,
melancholisch), gewichtet und deterministisch aus dem Datum gewählt, also den ganzen Tag gleich. Der
Satz hängt am System-Prompt. `mood_fixed = "pedantisch"` in `[voice]` erzwingt eine Laune, `mood = false`
schaltet ab. Der Benchmark läuft ohne Tagesform, damit die Zahlen vergleichbar bleiben;
`scripts/kitt_ask.sh` zeigt sie an.

**Anrede-Erkennung:** Mit `require_name = true` (Standard) reagiert KITT nur, wenn "KITT" in der
Äußerung vorkommt. Die Prüfung macht ein zweiter whisper-server mit `ggml-tiny.bin` auf Port 8177
in etwa 0,3 s; erst bei Treffer läuft die genaue Erkennung mit dem großen Modell. Gespräche im Cart
ohne Anrede kosten so kaum CPU. `name_variants` enthält die Schreibweisen, die whisper für den
Namen liefert ("Kit", "Kid", "Kitty"). Fehlt das tiny-Modell (`scripts/setup_phase5.sh` lädt es nach),
prüft das Hauptmodell die Anrede.

## Gesamttest und Performance (Phase 10)

| Werkzeug | Zweck |
|---|---|
| `scripts/health.sh` | Momentaufnahme: Temperatur, Throttling-Flags, Takt, RAM, Launcher, Server, Audio |
| `scripts/soak_test.sh [--hours N] [--stay MODUS]` | Dauertest gegen den laufenden Launcher: schaltet alle Modi im Kreis (Gaming 5 min, jede Szene 5 min, KITT 8 min) und schreibt alle 30 s eine Zeile nach `logs/soak.csv` |
| `scripts/kitt_latency.sh` | zehn Fragen in einer Server-Sitzung, Latenzen je Runde in `logs/kitt.log` |
| `scripts/perf_report.py` | wertet `soak.csv` und alle Logs aus: Temperatur je Modus, Throttling, Launcher-Neustarts, FPS je Szene, KITT-Latenzen, Fehlerzeilen. Ergebnis `docs/perf_phase10.md` |

Abnahmekriterien für den Golfcart-Betrieb:

- Throttling-Flags bleiben `0x0` über die gesamte Laufzeit (kein `0x80000` = Temperaturlimit seit Boot,
  kein `0x50000` = Unterspannung seit Boot). Sonst Kühlung bzw. Netzteil/Spannungswandler prüfen.
- RAM-Belegung steigt über Stunden nicht an (keine Lecks), Launcher-Neustarts = 0.
- Visualizer über 50 fps bei 1080p; sonst `render_scale` der Szene senken.
- KITT: erste Sprache unter 3 s nach Ende der Äußerung ist das Ziel. Größter Posten ist die
  Spracherkennung (small-q5_1 ≈ 4 s je Satz). Schneller geht `ggml-base.bin` in `[stt].model`,
  mit spürbar schlechterer Erkennung; die Benchmarks in `docs/stt_bench_phase5.md` zeigen beides.

Performance-Entscheidungen, die bereits drin sind: Modelle werden beim Launcher-Start in den
RAM-Cache vorgelesen; whisper mit greedy decoding und `audio_ctx 512`; LLM-Antworten auf 60 Tokens
und 3 Sätze begrenzt mit Abbruch der Generierung; Prompt-Cache im llama-server; Szenen mit
`render_scale`; Logs rotiert; genau ein Modus-Prozess zur Zeit, KITT und RetroPie nie parallel.

## LED-Buttonboard (WLED)

Das beleuchtete Buttonboard hängt an einem WLED-Controller (`config/wled.toml` `[controller]`, Host
192.168.2.150). Beim Moduswechsel schickt der Launcher das Profil `[modes.<modus>]` per HTTP-API
(`launcher/wled.py`): Helligkeit, Effekt, Haupt-, Zweit- und Drittfarbe, Geschwindigkeit, Intensität,
optional Palette; alle Profile sind über `[controller] dim` (0.7 = 30 %) gedämpft. **Live zur Musik:** Sobald ein
Modus läuft, streamt er 25 Bilder pro Sekunde eigene LED-Bilder per UDP an den Controller (WLED-Echtzeit, dafür muss in WLED
"UDP-Echtzeit empfangen" an sein, Standard). Die Kette nimmt dabei immer die Farbe des Bildschirms: Der Modus liest sein eigenes Bild winzig aus und macht daraus Haupt- und
Akzentfarbe, die LEDs folgen in etwa einer Sekunde. Alles ist mellow: Muster rücken auf jedem Beat (1, 2, 3, 4) einen Schritt
nach hinten, weich eingerastet, die Eins hebt kurz an, dazwischen treibt alles nur langsam. Jeder Modus hat ein ruhiges
Grundprogramm, und die Specials kommen aus dem, was auf dem Schirm passiert:
Beim Zeitsprung kommen langsam Farbfronten von vorne herein und füllen die Kette, eine nach der anderen; beim Sprung selbst
geht alles auf Volldampf, danach wieder ganz mellow. Beim Flug (Navigationscomputer, Planeten, Neonfahrt) ziehen Sterne von vorne nach hinten über den Cart, schneller
mit der Musik, und alle halbe Minute zieht ein Planet vorbei, der im Vorbeiflug kurz die ganze Kette in seiner Farbe füllt;
Kometenschauer schickt Kometen, das Asteroidenfeld graue Brocken, Wurmloch, Sonne und Nebel färben alles. Am Lagerfeuer ist die
Kette warmweißes Fackellicht, das träge glimmt und mit dem Feuer heller wird; brennt das Feuer blau, wird auch das Licht blau,
Holz nachlegen wirft Funken. Schwarzes Loch, Kern, Fluxkompensator und Moorsee sind ein
Strudel: Punkte driften von beiden Enden zur Mitte, die Mitte glimmt mit dem Bass, ein geworfenes Objekt läuft zur Mitte und wird
verschluckt, die Umkehrung ist eine Druckwelle nach außen. Taxistand, Orakel, Uhrturm, Auge des Waldes, Waldtresen, Herzbaum
und Marktplatz atmen langsam mit zwei wandernden Wolken, Jahreszeit und Epoche färben die Kette, Ereignisse laufen als Welle
durch. Auf der Dachterrasse regnet es von hinten nach vorne, das Wetter färbt, Blitze schlagen zweimal ein und grollen nach,
Feuerwerk geht in Blüten auf, der Stromausfall macht alles aus und lässt es zögernd zurückkommen. Black Ice, Paradoxon und
Überdosis bekommen das Störprogramm des Systemfehlers in ihren Themenfarben. Bei HAL 3000 ziehen dunkel- und hellrote Felder wie die
Zellen des Korridors langsam und immer in dieselbe Richtung vorbei, ein Viertel dunkler als der Rest, und ab und zu kommt von einem Ende ein einzelnes helles Feld, das im Takt Schritt für Schritt rund eine Minute
über die ganze Kette wandert, mal von vorne, mal von hinten, mit gelegentlichem Schritt zurück. Die Slotmaschinen haben ein mechanisches Lauflicht in den Lichtfarben des
gewählten Automaten: ein Ansteuerpunkt an, der nächste aus, auf jedem Beat springt das Muster hart um einen Punkt weiter (an wird aus,
aus wird an), alle paar Takte kommt auf dem Beat eine andere Farbe. Specials gibt es nur beim Drop und beim Gewinn: für ein paar Takte
die Casino-Markise (kurze Blöcke aus je drei Punkten in Farbe A hell, Farbe A gedimmt und Farbe B hell, kein Weiß, rückt je Beat einen
Block weiter, mal vor, mal zurück, beim Drehen schnell), oder ein einzelner Punkt läuft durch und wird bei anziehendem Beat überholt,
oder zwei Läufer kreuzen sich; kleiner Gewinn blitzt zweimal, großer Gewinn schickt einen weißen Lauf, Jackpot ist Gold-Weiß-Stroboskop
mit Funkeln. Im Systemfehler
ist das Board ein Kampf zwischen Grün (das System) und Rot (der Fehler), sonst nichts: Die Front wandert in Blasen über die
Kette, je nach Phase gewinnt Rot (Zusammenbruch, Alarm) oder Grün (Erholung), jeder Beat ist ein Vorstoß der stärkeren Seite,
der Bass heizt den Kampf an, umkämpfte Stellen sirren rot-grün. Und es sieht kaputt aus, aber träge statt hektisch: Abschnitte von ein paar LEDs
gehen an, bleiben eine Weile ruhig, fangen an zu flackern und fallen aus, andere kommen dazu; nur ein kleiner Teil arbeitet
überhaupt, gedimmt. Dazwischen Kurzschluss-Blöcke, die aufblitzen und sterben, Störlinien, kurze Totalausfälle, Rauschstürme. Der Virus frisst sich von hinten durch, der Eindringling ist ein roter Läufer, dessen Spur Grün wieder heilt,
der Neustart eine grüne Linie von vorne, danach ruhiges grünes Atmen.
Endet der Modus, fällt WLED nach zwei Sekunden von selbst auf das Profil zurück. Beim Senden setzt der Launcher immer
auch die Palette (sonst bliebe die letzte, etwa der Regenbogen, in jedem Effekt hängen), stoppt Playlists, schaltet den
Live-Override aus und löscht zusätzliche Segmente. Tut das Board nicht, was es soll: `scripts/wled_check.py` auf dem Pi zeigt
Version, LED-Anzahl, Segmente und Live-Status und fährt drei rote Tests (HTTP gedimmt, HTTP voll, UDP-Stream). Zeigt WLED weniger
LEDs als die Kette hat, bleiben die übrigen mit Zufallsfarben an: `scripts/wled_setup.py --leds 784 --apply` setzt die Anzahl
(oder im Browser unter Config, LED Preferences, Length). Jeder Modus hat sein eigenes Licht: Taxistand gelb atmend (und in der Farbe des
gewählten Themas, sobald eines bestätigt ist), Navigationscomputer blau-cyane Kometen, Schwarzes
Loch oranger Meteor, HAL tiefrotes Atmen, Slotmaschine goldenes Pulsieren, Lagerfeuer Feuer,
Systemfehler nur Rot (auch live: Ausfälle, Flackern, wachsendes Hellrot), Arcade Regenbogen, Bordcomputer KITT-Scanner, Planeten weißblaues
Funkeln, Nachrichten Studioblau, BIBO orange, CRT grün, Auge violett.
Ereignisse innerhalb eines Modus schicken eigene Profile und fallen danach zurück: bei HAL
Astronaut (weiß), Alien (grün), beide (weiß und grün als Kometen); Slotmaschine großer Gewinn (Gold
funkelt, 5 s) und Jackpot (Feuerwerk, 8 s); Schwarzes Loch Wurf (heller Meteor, 3 s) und
Umkehrung (weißblaues Stroboskop, 8 s). Alles asynchron mit zwei Sekunden Timeout, die LEDs
blockieren nie etwas.
Ausprobieren ohne Eintrag: `scripts/wledctl.py set --col 0,255,0 --fx 2 --bri 200` (dazu `--col2`,
`--col3`, `--sx`, `--ix`, `--pal`), ein Profil senden: `scripts/wledctl.py mode hal`, alle zeigen:
`scripts/wledctl.py list`. Gefällt eine Kombination, die Werte in `config/wled.toml` eintragen.

## Noch offen (Hardware und Inhalte, kein Code)

- **USB-Soundkarte oder USB-Mikrofon plus Lautsprecher** am Pi. Ohne Mikrofon hört KITT nichts und
  die Visualizer reagieren nicht; ohne Lautsprecher spricht KITT stumm. Danach
  `scripts/audio_check.sh` ausführen und bei Bedarf `target` in `config/audio.toml` setzen.
- **ROMs** nach `~/RetroPie/roms/<system>`, PS1-BIOS nach `~/RetroPie/BIOS`.
- **Gamepad** in EmulationStation über Start → Configure Input einrichten.
- **USB-HID-Buttonbox** statt F1–F7: siehe Abschnitt oben, meist nur `config/keymap.toml`.
- **Bluetooth** nur, wenn gewünscht: `scripts/setup_bluetooth.sh`, dann Handy koppeln.
- Für den Alltag `dev_emergency_exit = false` in `config/settings.toml`.


**Hupe und Effekte:** Die Aktionen `horn`, `horn2` und `fx` lassen sich in `config/keymap.toml` auf freie Tasten legen. `horn` spielt die
Hupe des Themas (Raumschiff-Klaxon, Cyber-Sirene, 80er-Autohupe mit Flux-Brummen, Alphorn), `horn2` den zweiten Ton für die andere
Seite des Hupen-Schalters (Schiffshorn, Sirene auf und ab, Doppelhupen, Kuckuck; `settings.toml` `[buttons] horn2_code`), `fx` einen zufälligen Effekt
(Laser, Warp, Roboter-Piepsen; Glitch, Alarm, Synth; Zeitkreis-Piepser, Donner, Knistern; Eule, Frosch, Windspiel), beide mit
LED-Blitz. Klänge: echte Aufnahmen aus der Scratch-Soundbibliothek (scratch.mit.edu, CC BY-SA 2.0; Autohupe, Polizeisirene,
Gans, Raumschiff, Teleport, Alarm, Uhr, Gewitter, Eule, Wolf, Grillen), `scripts/sfx_fetch.py` lädt sie beim `update.sh` auf dem Pi
nach `assets/sfx/raw/` und baut je Thema `assets/sfx/real/` (Space: Hupe tiefer mit Hall; Cyberpunk: verzerrte Tiefhupe mit
Sirene; Zukunft: Autohupe pur; Natur: Gans). Fehlen sie, laufen die synthetischen aus `assets/sfx/` (`scripts/sfx_build.py`).
Lautstärke `settings.toml` `[sfx]`.

**Weitere Kippschalter:** Die zwei Schalter unten neben dem Autopilot bekommen in `config/keymap.toml` je Stellung eine
Aktion: `code = N` mit `on = "down"` (Standard) beim Umlegen und `on = "up"` beim Zurücklegen; den Code N zeigt das Launcher-Log beim
ersten Umlegen als "Taste ohne Belegung". Erlaubt sind alle Modi und `fx`, `horn`, `horn2`, `talk`, `attract_on/off`, `voice_up/down`,
`music_up/down`.

**Vorführmodus:** Kommt fünf Minuten keine Eingabe, wechselt das System alle drei Minuten von selbst durch die Modi des
Themas (Tasten 2 bis 7, mit Ansage). Jede Taste beendet ihn. Einstellungen `settings.toml` `[attract]`. Mit dem
Autopilot-Kippschalter (`[buttons].attract_code`) läuft er sofort und dauerhaft (AN) oder ist ganz aus (AUS); beim Umschalten
zeigt der Bildschirm kurz "AUTOPILOT AN" bzw. "AUTOPILOT AUS".
