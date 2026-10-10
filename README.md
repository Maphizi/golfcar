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
| 1 HANDLE | `BTN_MISC` | `gaming` | Retro-Gaming (EmulationStation, ab Phase 3) |
| 2 CRUISE | `BTN_1` | `viz_psychedelic` | Navigationscomputer / Hyperraum |
| 3 FLASH | `BTN_2` | `viz_crt` | Zielcomputer |
| 4 AUDIO | `BTN_3` | `viz_eye` | Taktik-Scanner |
| 5 WIPERS | `BTN_4` | `kitt` | KITT Sprachassistent mit Oberfläche |
| 6 MAP | `BTN_5` | `home` | Home-Screen |
| 7 LIGHT | `BTN_6` | `campfire` | Lagerfeuer (Pixel-Art) |
| 8 E-TALK | `BTN_7` | `error` | Systemfehler-Visualizer (grüner Code, der zusammenbricht) |
| 9 | `BTN_8` | `quit` | Launcher beenden (nur wenn `dev_emergency_exit = true`) |
| 10 | `BTN_9` | `planeten` | Planeten-Flug (pygame, Kippschalter = Warp) |
| ESC | `KEY_ESC` | `quit` | Notausstieg an der Tastatur |

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

- `campfire` (F7): Pixel-Art-Lagerfeuer auf 90 Zeilen Raster. Zündet nach dem Start in etwa fünf
  Sekunden an (Funke, dann wachsende Flamme), zwei gekreuzte Scheite mit Glut, aufsteigende Funken,
  flackernder Lichtschein auf dem Boden, Sternenhimmel. Braucht kein Mikrofon; mit Musik werden
  Flamme und Funken etwas lebhafter. Rendert mit `render_scale 0.5`, da das Pixelraster ohnehin grob ist.
- `error` (Taste 8): grüner Code, der alle 24 Sekunden zusammenbricht. Beschreibung unter
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
| F1 | HOLO-ARCADE | RetroPie, unverändert |
| F2 | HYPERRAUM | `navcomputer`: Navigationscomputer mit Planetenkatalog und Anflug (siehe unten). Alternative ohne Steuerung: `hyperspace` |
| F3 | ZIELCOMPUTER | `target`: gelber Drahtgitter-Graben in Perspektive (Tempo nach Bass, jede vierte Strebe rot), Zähler, Statusfelder nach Bändern, unten Zielkreis mit Sweep und Waveform, fremde Schrift |
| F4 | TAKTIK-SCANNER | `tactical`: grünes Gitter, weißes 3D-Drahtgitter eines Gleiters (dreht mit den Mitten, Triebwerk glüht mit Bass), Radar mit Blips aus dem Spektrum, Waveform, rote Pegelbalken |
| F5 | BORDCOMPUTER | `shipcomputer`: gelbes Pixel-OLED mit Panels, Radar, Spektrum, Status-Symbolen (Kreis, Sanduhr, Dreieck), Thermometer und sechs Balken, Zustände EMPFANG, DROIDENKERN RECHNET, SENDE |
| F7 | LAGERFEUER / AUSSENPOSTEN | `campfire`: Pixel-Feuer mit violettem Saum unter zwei Monden, Ringplanet, Nebel, Sternschnuppen, dazu Hintergrund-Ereignisse (siehe unten) |
| 8 | SYSTEMFEHLER | `error`: grüner Code in sechs Varianten, Zusammenbruch, rotes Fehlerbild in sechs Varianten, Wiederherstellung, Neustart (siehe unten) |

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

**Lagerfeuer-Ereignisse (F7):** Alle 16 Sekunden ein Zeitfenster, der Inhalt kommt aus einem
Hash der Fensternummer (zwei von sechzehn Fenstern bleiben leer), 14 Ereignisse: Transporter mit
Positionslichtern, zwei Jäger mit roten Schweifen, vierbeiniger Läufer am Horizont, Gleiter mit
Staubfahne, Sonde mit rotem Scanstrahl, Großschiff weit oben, ferne Gefechtsblitze mit Leuchtspuren,
Shuttle, das hinten landet, kurz steht und wieder startet, Konvoi aus drei Fahrzeugen, rollender
Droide nah am Feuer, Raupenkriecher am Horizont, Meteorschauer, Suchscheinwerfer einer fernen Basis
und eine Patrouille aus Transporter mit Jägereskorte. Dazu in jedem dritten Fenster eine driftende
Orbitalstation und die Sternschnuppe alle neun Sekunden. Alles sind eigene Pixel-Silhouetten im
Shader (`visualizers/shaders/campfire/frag.glsl`, Funktion `events`). Die Fahrzeuge kommen vom
Rand herein, in den ersten Sekunden eines Fensters ist also noch nichts zu sehen, und am Horizont
verdeckt das Feuer sie in der Bildmitte kurz. Zum Prüfen lässt sich ein Ereignis erzwingen:
`scripts/viz_test.sh campfire --test-signal --seconds 5 --uniform uEventForce=8` (Wert = Nummer + 1,
1 Transporter … 14 Patrouille). `--uniform NAME=WERT` setzt allgemein ein Shader-Uniform fest und
ist mehrfach erlaubt.

**Systemfehler-Modus (Taste 8, `error`):** Ein Durchlauf dauert 24 Sekunden und hat fünf
Phasen. Zuerst 12 bis 16 Sekunden grüner Code, pro Durchlauf eine von sechs Varianten: fallender
Zeichenregen, scrollender Hexdump mit Adressen und Klartextspalte, Boot-Protokoll mit `[ OK ]`,
`[WARN]`, `[FAIL]` und Ladebalken (gegen Ende häufen sich die FAIL-Zeilen), Bitraster aus kippenden
Nullen und Einsen, eingerückter Quelltext mit Schlüsselwörtern, Strings und roten FEHLERCODE-Zeilen,
oder ein Analysator, der das Spektrum als Zeichensäulen zeigt. Dann 2,5 Sekunden Zusammenbruch:
Zeilen reißen, Blöcke springen, ein roter Geist des Codes schiebt sich daneben, Blöcke invertieren,
Rauschen, alles kippt nach Rot, ERROR-Stempel tauchen auf. Dann 4,5 Sekunden Fehlerbild, wieder
eine von sechs Varianten: riesiges zitterndes ERROR mit Fehlercode, rot blinkende Kachelfläche aus
SYSTEMFEHLER mit Warnband, Kaskade aus ERROR-Zeilen, die das Bild füllt und dann bebt, Kernel-Panic-
Protokoll mit roten Meldungen und blinkendem Kasten, Countdown von 9 mit KERN INSTABIL und Weißblitz
bei 0, oder Bildrauschen mit ERROR als rotem Loch und SIGNAL VERLOREN. Danach ein stotternder
WIEDERHERSTELLUNG-Balken und ein getipptes NEUSTART, und es geht mit neuem Code von vorn.

Musik: Bass steuert Tempo, Helligkeit, Spurlänge und Zittern, Mitten lassen die Zeichen schneller
wechseln, Höhen erzeugen Funken, der Beat lässt Spalten aufblitzen, verschiebt Zeilen und blitzt im
Fehlerbild, das Spektrum färbt Spalten und Ringe. Jeder Durchlauf hat einen eigenen Hash-Seed, der
Code wiederholt sich also nicht. Schrift ist ein eigener 5×6-Pixelfont im Shader, alle Texte sind
Deutsch oder generisch (ERROR, FATAL, CORE DUMP). Shader: `visualizers/shaders/error/frag.glsl`,
`render_scale 0.6`. Zum Prüfen einzelner Teile: `--uniform uPhaseForce=3` hält die Phase fest (1 Code,
2 Zusammenbruch, 3 Fehler, 4 Wiederherstellung, 5 Neustart), `uCodeForce=1..6` und `uErrorForce=1..6`
wählen die Variante, z. B. `scripts/viz_test.sh error --test-signal --seconds 8 --uniform uPhaseForce=3 --uniform uErrorForce=5`.

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

## Noch offen (Hardware und Inhalte, kein Code)

- **USB-Soundkarte oder USB-Mikrofon plus Lautsprecher** am Pi. Ohne Mikrofon hört KITT nichts und
  die Visualizer reagieren nicht; ohne Lautsprecher spricht KITT stumm. Danach
  `scripts/audio_check.sh` ausführen und bei Bedarf `target` in `config/audio.toml` setzen.
- **ROMs** nach `~/RetroPie/roms/<system>`, PS1-BIOS nach `~/RetroPie/BIOS`.
- **Gamepad** in EmulationStation über Start → Configure Input einrichten.
- **USB-HID-Buttonbox** statt F1–F7: siehe Abschnitt oben, meist nur `config/keymap.toml`.
- **Bluetooth** nur, wenn gewünscht: `scripts/setup_bluetooth.sh`, dann Handy koppeln.
- Für den Alltag `dev_emergency_exit = false` in `config/settings.toml`.
