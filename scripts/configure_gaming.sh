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
# RetroPie legt beim ES-Install bereits eine es_input.cfg nur mit der onfinish-Action an.
# Fehlt darin die Tastatur, wird unser <inputConfig type="keyboard"> vor </inputList> eingefügt.
if [ ! -f "$ES_DIR/es_input.cfg" ]; then
  cp "$ROOT/config/es_input.cfg" "$ES_DIR/es_input.cfg"
  echo "  es_input.cfg angelegt (Tastatur: Pfeile, X=A, Z=B, S=X, A=Y, Enter=Start, RShift=Select)"
elif grep -q 'type="keyboard"' "$ES_DIR/es_input.cfg"; then
  echo "  es_input.cfg enthält bereits eine Tastatur, nicht angefasst"
else
  python3 - "$ES_DIR/es_input.cfg" "$ROOT/config/es_input.cfg" <<'PY'
import re, sys
dst, src = sys.argv[1], sys.argv[2]
cur = open(dst).read()
kb = re.search(r'<inputConfig type="keyboard".*?</inputConfig>', open(src).read(), re.S).group(0)
cur = cur.replace("</inputList>", "  " + kb + "\n</inputList>")
open(dst, "w").write(cur)
PY
  echo "  Tastatur in bestehende es_input.cfg eingefügt"
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
echo "== runcommand-Hooks (Spielstatistik für KITT) =="
if [ -d /opt/retropie/configs/all ]; then
  for h in onstart onend; do
    sudo install -m 755 "$ROOT/scripts/retropie_hooks/runcommand-$h.sh" "/opt/retropie/configs/all/runcommand-$h.sh"
  done
  echo "  /opt/retropie/configs/all/runcommand-onstart.sh und -onend.sh schreiben logs/games.jsonl"
fi
echo "fertig"
