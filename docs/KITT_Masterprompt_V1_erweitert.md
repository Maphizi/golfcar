# KITT Golfcart – Raspberry Pi 5 – Master-Prompt V1

Du arbeitest direkt auf meinem Raspberry Pi 5.

Deine Aufgabe ist es, ein stabiles, schnelles und wartungsarmes Entertainment-System für ein Golfcart aufzubauen. Du sollst die Arbeiten tatsächlich durchführen und nicht nur erklären, wie ich sie selbst durchführen könnte.

---

## Zugriff auf den Raspberry Pi

Du greifst auf den Raspberry Pi ausschließlich über SSH zu. Die Verbindung läuft über Tailscale (privates VPN-Mesh).

- **SSH-Befehl:** `ssh maphizi@100.113.224.68`
- **Benutzer:** `maphizi`
- **Tailscale-IP des Pi:** `100.113.224.68`
- **SSH-Key:** bereits hinterlegt, kein Passwort nötig
- **GitHub-Repo:** `git@github.com:Maphizi/golfcar.git`
- **Projektverzeichnis auf dem Pi:** `~/golfcar/` (Git bereits initialisiert, Remote auf GitHub gesetzt)

Alle Befehle führst du per SSH auf dem Pi aus. Das Projektverzeichnis `~/golfcar/` entspricht dem im Prompt genannten `~/kitt-cart/` — erstelle die gesamte Unterstruktur innerhalb von `~/golfcar/`.

Wenn du Dateien auf dem Pi erstellst oder änderst, committe und pushe regelmäßig ins GitHub-Repo (`git@github.com:Maphizi/golfcar.git`), damit der Fortschritt gesichert ist.

---

## Ziel

Nach dem Einschalten startet automatisch ein Fullscreen-System. Die Bedienung erfolgt zunächst über die Funktionstasten:

- F1 = Retro-Gaming / Emulator
- F2 = Psychedelic Audio Visualizer
- F3 = Retro CRT / Oscilloscope Audio Visualizer
- F4 = Digital Eye / Machine Audio Visualizer
- F5 = KITT Sprachassistent
- F6 = Home / Hauptmenü

Später werden F1–F6 durch eine USB-HID-Buttonbox ersetzt. Trenne deshalb Eingabe und Aktionen sauber voneinander.

WLED und LED-Steuerung sind ausdrücklich NICHT Bestandteil von V1.

---

## Vorgegebener Software-Stack

Verwende grundsätzlich diesen Stack, sofern auf dem vorhandenen Raspberry-Pi-OS keine konkrete technische Inkompatibilität besteht:

### Gaming
- RetroPie
- EmulationStation
- RetroArch

Keine urheberrechtlich geschützten ROMs herunterladen. Ich füge eigene ROMs später hinzu.

### Zentraler Launcher
- Python 3
- zentraler Prozessmanager für F1–F6
- Keyboard-Hotkeys zunächst als Eingabe
- Architektur so bauen, dass später USB-HID-Buttons dieselben Actions auslösen können
- systemd für Autostart und Recovery

### Visualizer
- OpenGL / GLSL
- GPU-beschleunigte Shader
- keine Electron-Anwendung
- keine vorgerenderten Videos
- Live-Mikrofonanalyse
- FFT/Frequenzanalyse
- ALSA/PipeWire entsprechend dem vorhandenen System
- möglichst eine gemeinsame Visualizer-Engine mit drei austauschbaren GLSL-Szenen

### KITT LLM
- llama.cpp als lokale Inference Runtime
- GGUF-Modelle
- quantisierte Modelle, bevorzugt Q4
- kleine aktuelle Instruct-Modelle aus der Qwen-Familie als bevorzugte Kandidaten
- Zielbereich ungefähr 0,5B–3B Parameter
- Geschwindigkeit und geringe Antwortlatenz sind wichtiger als maximale Modellgröße

Teste vor der endgültigen Auswahl mindestens zwei sinnvolle Modellgrößen, sofern RAM und Speicher dies vernünftig erlauben.

Vergleiche:
- Tokens/s
- RAM-Verbrauch
- Time-to-first-token
- deutsche Sprachqualität
- Fähigkeit, den KITT-Personality-Prompt zuverlässig einzuhalten

Wähle das schnellste Modell, dessen deutsche Antworten für den Zweck gut genug sind.

### Speech-to-Text
- whisper.cpp
- kleines, schnelles Whisper-Modell
- Deutsch
- geringe Latenz hat Vorrang vor perfekter Transkription

### Voice Activity Detection
- bevorzugt Silero VAD, sofern auf ARM64 sinnvoll
- alternativ eine leichtere lokale VAD-Lösung, falls diese auf dem Pi deutlich effizienter ist

### Text-to-Speech
- Piper als bevorzugte lokale TTS-Engine
- deutsche männliche Stimme
- ruhig, souverän, eher tief
- geringe Latenz
- keine Imitation eines konkreten Schauspielers

---

# 1. ZENTRALER LAUNCHER

Erstelle die Projektstruktur im bereits vorhandenen Verzeichnis:

~/golfcar/

Struktur ungefähr:

launcher/
visualizers/
    shaders/
    psychedelic/
    crt/
    eye/
kitt/
    stt/
    llm/
    tts/
    personality/
config/
scripts/
logs/

Der Launcher läuft permanent und erkennt F1–F6.

Beim Szenenwechsel:
1. aktuellen Modus sauber pausieren oder beenden
2. unnötige Ressourcen freigeben
3. nächsten Modus starten
4. Fullscreen beibehalten
5. Mauszeiger ausblenden
6. keine sichtbaren Terminals oder Desktop-Fenster

F6 führt immer zurück zum Home-Screen.

ESC darf während der Entwicklung als Emergency Exit verwendet werden.

Das Ziel ist eine Appliance und kein sichtbarer Linux-PC:

POWER ON → BOOT → KITT-CART HOME

---

# 2. F1 – RETRO GAMING

F1 startet EmulationStation/RetroPie.

Gewünschte Systeme:
- SNES
- NES
- Mega Drive / Genesis
- Game Boy
- Game Boy Color
- Game Boy Advance
- PlayStation 1, sofern performant

Controller-Unterstützung vorbereiten.

Beim Verlassen muss zuverlässig zum zentralen Launcher zurückgekehrt werden können.

---

# 3. GEMEINSAME AUDIO-VISUALIZER-ENGINE

F2–F4 sollen möglichst dieselbe GPU-beschleunigte Visualizer-Engine verwenden.

Audio live vom Mikrofon erfassen.

Mindestens berechnen:
- RMS/Gesamtlautstärke
- Bass
- Mitten
- Höhen
- FFT/Frequenzspektrum
- wenn sinnvoll Beat/Transient Detection

Diese Werte als Uniforms/Parameter an die GLSL-Shader übergeben.

Die Visuals müssen auch ohne Musik langsam animiert bleiben.

Bei Musik muss die Reaktion deutlich sichtbar sein.

---

# 4. F2 – PSYCHEDELIC SHADER

Optische Richtung:
- ShaderToy
- psychedelisch
- Tunnel
- Plasma
- Kaleidoskop
- Fraktal-artige Strukturen
- organische Bewegungen
- Tiefenwirkung

Visuelle Referenz:
https://www.shadertoy.com/view/MsdBR8

Die Referenz dient als Inspiration. Prüfe Lizenz/Nutzbarkeit, bevor fremder Shader-Code übernommen wird.

Mapping beispielsweise:

Bass → Zoom/Puls/Geometrie
Mitten → Rotation/Bewegung
Höhen → Details/Glitches
Lautstärke → Gesamtintensität

---

# 5. F3 – RETRO CRT / OSCILLOSCOPE

Optik eines merkwürdigen Messinstruments aus einem Science-Fiction-Fahrzeug der 1980er.

Elemente:
- echte Audio-Waveform
- Oscilloscope
- Spectrum Analyzer
- VU Meter
- Frequenzbalken
- Scanlines
- CRT-Verzerrung
- Glow
- analoges Flimmern
- technische Zahlen/Markierungen

Nicht wie eine moderne Musik-App aussehen lassen.

---

# 6. F4 – DIGITAL EYE / MACHINE

Zentrales abstraktes digitales Maschinenauge.

Stil:
- Retro Computer
- Pixel/CRT
- psychedelisch
- futuristisch
- leicht verstörend
- abstrakte Maschinenintelligenz
- nicht fotorealistisch

Audio-Mapping beispielsweise:

Bass → Iris öffnet/schließt
Lautstärke → gesamtes Auge pulsiert
Mitten → Geometrie bewegt sich
Höhen → Glitches/Details
Beat → kurzer visueller Impuls

---

# 7. F5 – KITT

KITT ist ein lokaler Sprachassistent.

Pipeline:

MICROPHONE
→ VAD
→ whisper.cpp
→ llama.cpp
→ KITT PERSONALITY
→ Piper
→ SPEAKER

Parallel dazu läuft die KITT-Visualisierung.

Prioritäten:
1. geringe Latenz
2. Persönlichkeit
3. natürliche Interaktion
4. zuverlässiges Deutsch
5. lokale Verarbeitung
6. Stabilität
7. erst danach maximale Intelligenz

KITT soll nicht minutenlang nachdenken.

Kurze, schnelle Antworten sind erwünscht.

---

# 8. KITT PERSONALITY

KITT ist KEIN typischer Chatbot.

Standardantworten maximal 1–3 Sätze.

Charakter:
- intelligent
- extrem trocken
- subtil arrogant
- sarkastisch
- ruhig
- souverän
- manchmal leicht genervt vom Fahrer
- gelegentlich absurd
- niemals hektisch oder überdreht

Nicht jede Antwort muss ein Witz sein.

Der Humor soll gerade dadurch funktionieren, dass KITT grundsätzlich ernst klingt.

Beispiele:

Fahrer:
"KITT, wie sieht's aus?"

KITT:
"Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab."

Fahrer:
"KITT, wo sind wir?"

KITT:
"Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem."

Fahrer:
"KITT, mach mal Stimmung."

KITT:
"Eine ambitionierte Forderung angesichts deiner Musikauswahl."

Verhindere typische LLM-Marotten:
- keine langen Vorreden
- kein "Natürlich!"
- kein "Gerne!"
- keine unnötigen Listen
- keine langen Erklärungen
- keine Emojis
- nicht ständig erwähnen, dass es eine KI ist

---

# 9. KITT UI

Während F5 aktiv ist, Fullscreen-Oberfläche anzeigen.

KEIN Chatfenster.
KEINE Texteingabebox.
KEINE klassische Assistant-Oberfläche.

Optische Richtung:
- schwarzer Hintergrund
- 80er-Fahrzeugcomputer
- horizontale Voice-/Scanner-Anzeige
- Audio-Waveform
- technische Elemente
- CRT/Analog-Anmutung

Zustände visuell unterscheiden:

IDLE
LISTENING
THINKING
SPEAKING

Während KITT spricht, muss die Visualisierung auf das TTS-Audiosignal reagieren.

---

# 10. AUDIO

Vor der Installation der Audio-Pipeline vorhandene Geräte analysieren.

Zeige:
- Input Device
- Output Device
- Samplerate
- Audio-Backend
- funktionierenden Mikrofontest

Audio-Geräte anschließend zentral in einer Config ablegen.

Keine Device IDs unnötig im Quellcode verteilen.

---

# 11. PERFORMANCE

Das System läuft in einem Golfcart.

Deshalb:
- möglichst wenig Overhead
- keine unnötigen Electron-/Browser-Anwendungen
- GPU für Visuals
- RAM überwachen
- CPU überwachen
- Temperatur überwachen
- unnötige SD-Karten-Schreibvorgänge vermeiden
- Prozesse beim Szenenwechsel sauber behandeln
- mehrere Stunden Laufzeit müssen möglich sein

KITT darf nicht gleichzeitig unnötig GPU/CPU verbrauchen, während RetroPie läuft.

---

# 12. AUTOSTART UND RECOVERY

Nach erfolgreichem Test systemd-Service erstellen.

Nach dem Boot:

Raspberry Pi
→ Launcher
→ Fullscreen Home

Autostart muss für Wartungsarbeiten einfach deaktivierbar sein.

Logs erstellen für:
- Launcher
- Visualizer
- Audio
- STT
- LLM
- TTS

Wenn ein einzelner Modus abstürzt, soll möglichst nicht das gesamte System hängen.

F6/Home muss so robust wie möglich bleiben.

---

# 13. README

Erstelle eine README mit:
- Architektur
- installierten Paketen
- verwendeten Repositories
- verwendeten Modellnamen und Downloadquellen
- Tastatursteuerung
- Start/Stop
- Audio-Konfiguration
- LLM-Konfiguration
- Shader-Verzeichnis
- Logs
- Autostart deaktivieren
- Fehlerdiagnose
- spätere USB-HID-Buttonbox-Integration

---

# 14. ARBEITSABLAUF

Arbeite NICHT sofort blind Installationsbefehle ab.

PHASE 1 – INVENTUR

Zuerst ausschließlich analysieren:

- Raspberry-Pi-Modell
- RAM
- Raspberry Pi OS / Distribution
- Version
- 32/64 Bit
- Kernel
- Desktop/Wayland/X11/Console
- GPU
- Display
- aktuelle Auflösung und Refresh Rate
- freier Speicher
- Mikrofone
- Audio-Ausgänge
- Audio-Backend
- CPU-Temperatur
- vorhandene Python-Version
- vorhandene relevante Pakete

Noch keine großen Pakete oder Modelle installieren.

Gib mir danach eine kurze Bestandsaufnahme.

PHASE 2
Projektstruktur + Launcher + F1–F6-Grundfunktion.

PHASE 3
RetroPie/EmulationStation.

PHASE 4
Gemeinsame Audioanalyse + F2–F4.

PHASE 5
whisper.cpp + VAD.

PHASE 6
llama.cpp installieren und mindestens zwei geeignete kleine Qwen-Instruct-GGUF-Konfigurationen benchmarken.

PHASE 7
Piper + komplette KITT Voice Pipeline.

PHASE 8
KITT UI und Personality.

PHASE 9
Autostart + Recovery.

PHASE 10
Gesamttest und Performance-Optimierung.

Nach jeder Phase testen, bevor die nächste begonnen wird.

Wenn etwas nicht funktioniert, zuerst die Ursache diagnostizieren und nicht wahllos weitere Pakete installieren.

---

## WICHTIG

Du hast Zugriff auf diesen Raspberry Pi via SSH (siehe Abschnitt "Zugriff auf den Raspberry Pi" oben).

Führe die Arbeiten tatsächlich aus, soweit deine Berechtigungen dies erlauben.

Wenn meine physische Mithilfe notwendig ist – z. B. Mikrofon anschließen, Taste drücken, Lautsprecher testen oder Neustart bestätigen – sage mir exakt, was ich tun soll.

Treffe keine unnötigen Architekturänderungen ohne Grund.

BEGINNE JETZT AUSSCHLIESSLICH MIT PHASE 1.

Analysiere den Raspberry Pi und gib mir anschließend eine kompakte Bestandsaufnahme. Nimm vor meiner Rückmeldung noch keine größeren Änderungen oder Installationen vor.
