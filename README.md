# KITT-Cart – Golfcart Entertainment auf Raspberry Pi 5

Fullscreen-Appliance: Retro-Gaming, drei GPU-Audio-Visualizer und der lokale
Sprachassistent KITT. Bedienung über F1–F6, später über eine USB-HID-Buttonbox.

Stand: **Phase 9** (alle Modi, Appliance-Autostart mit Recovery).
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

| Taste | Action | Modus |
|---|---|---|
| F1 | `gaming` | Retro-Gaming (EmulationStation, ab Phase 3) |
| F2 | `viz_psychedelic` | Psychedelic Visualizer |
| F3 | `viz_crt` | CRT / Oscilloscope |
| F4 | `viz_eye` | Digital Eye |
| F5 | `kitt` | KITT Sprachassistent mit Oberfläche |
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

## Noch offen

- Installierte Pakete, Repositories, Modelle, Audio- und LLM-Konfiguration, Shader-Verzeichnis:
  werden mit den jeweiligen Phasen ergänzt.
