#!/usr/bin/env bash
# Phase 3: RetroPie an den Launcher anpassen. Idempotent, läuft ohne Build.
#  - ROM-Verzeichnisse anlegen
#  - Tastatur in EmulationStation vorkonfigurieren (kein "NO GAMEPADS DETECTED"-Dialog)
#  - RetroArch-Hotkeys auf F2/F4/F6 abschalten (die Tasten gehören dem Launcher)
#  - Audio über ALSA-Default (= PipeWire)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ES_DIR="$HOME/.emulationstation"
RA_CFG="/opt/retropie/configs/all/retroarch.cfg"

echo "== ROM-Verzeichnisse =="
for s in nes snes megadrive gb gbc gba psx; do
  mkdir -p "$HOME/RetroPie/roms/$s"
done
mkdir -p "$HOME/RetroPie/BIOS"
echo "  ~/RetroPie/roms/{nes,snes,megadrive,gb,gbc,gba,psx}  (PS1 braucht zusätzlich BIOS in ~/RetroPie/BIOS)"

echo "== EmulationStation: Tastatur vorkonfigurieren =="
mkdir -p "$ES_DIR"
if [ ! -f "$ES_DIR/es_input.cfg" ]; then
  cp "$ROOT/config/es_input.cfg" "$ES_DIR/es_input.cfg"
  echo "  es_input.cfg angelegt (Tastatur: Pfeile, X=A, Z=B, S=X, A=Y, Enter=Start, RShift=Select)"
else
  echo "  es_input.cfg existiert, nicht angefasst"
fi

echo "== RetroArch: Hotkeys an den Launcher abgeben =="
if [ -f "$RA_CFG" ]; then
  set_ra() {  # set_ra key value
    if grep -qE "^[[:space:]]*$1[[:space:]]*=" "$RA_CFG"; then
      sudo sed -i -E "s|^[[:space:]]*$1[[:space:]]*=.*|$1 = \"$2\"|" "$RA_CFG"
    else
      echo "$1 = \"$2\"" | sudo tee -a "$RA_CFG" >/dev/null
    fi
  }
  set_ra input_save_state nul            # Standard F2 -> Launcher: Psychedelic
  set_ra input_load_state nul            # Standard F4 -> Launcher: Digital Eye
  set_ra input_state_slot_decrease nul   # Standard F6 -> Launcher: Home
  set_ra input_state_slot_increase nul   # F7, der Vollständigkeit halber
  set_ra audio_driver alsathread
  set_ra audio_device default            # ALSA default = PipeWire (pipewire-alsa)
  set_ra video_fullscreen true
  set_ra video_vsync true
  echo "  $RA_CFG angepasst (F1 bleibt RetroArch-Menü, ESC beendet das Spiel)"
else
  echo "  $RA_CFG fehlt, RetroArch noch nicht installiert"
fi
echo "fertig"
