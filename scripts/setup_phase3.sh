#!/usr/bin/env bash
# Phase 3: RetroPie (EmulationStation + RetroArch + Cores) aus RetroPie-Setup installieren.
#
# Auf Debian 13 (trixie) gibt es keine RetroPie-Binärpakete, alles wird aus dem Quellcode
# gebaut. Dauer auf dem Pi 5: etwa 45–90 Minuten. Das Skript ist idempotent, ein bereits
# installiertes Modul wird übersprungen (Datei in logs/retropie/<modul>.done).
#
# Aufruf:  nohup scripts/setup_phase3.sh > logs/retropie_install.log 2>&1 &
# Nur Vorprüfung (nichts installieren):  scripts/setup_phase3.sh --check
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RP_SETUP="$HOME/RetroPie-Setup"
LOGDIR="$ROOT/logs/retropie"
mkdir -p "$LOGDIR"

# Reihenfolge ist wichtig: sdl2 vor retroarch/emulationstation, Cores danach.
MODULES=(
  sdl2                 # SDL 2.32.10 (RetroPie-Build mit KMS/X11), ersetzt System-SDL
  retroarch            # Frontend für alle libretro-Cores
  emulationstation     # Menü-Oberfläche
  retropiemenu         # "RetroPie"-System in ES (Konfiguration, Audio, Controller)
  runcommand           # Start-Wrapper, den ES benutzt
  lr-fceumm            # NES
  lr-snes9x            # SNES
  lr-genesis-plus-gx   # Mega Drive / Genesis (+ Master System, Game Gear)
  lr-gambatte          # Game Boy / Game Boy Color
  lr-mgba              # Game Boy Advance
  lr-pcsx-rearmed      # PlayStation 1
)

say() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

say "Vorprüfung"
. /etc/os-release
echo "OS: $PRETTY_NAME  Arch: $(dpkg --print-architecture)  Modell: $(tr -d '\0' < /proc/device-tree/model)"
[ -d /sys/module/vc4 ] && echo "KMS: vc4 geladen (RetroPie-Platform-Flags: rpi5 kms mesa gles3)" || echo "WARNUNG: vc4 nicht geladen"
df -h / | tail -1 | awk '{print "Frei auf /: "$4}'
if [ "${VERSION_ID:-0}" -ge 13 ]; then
  echo "Hinweis: Debian $VERSION_ID hat keine RetroPie-Binärpakete, Quellcode-Builds (lange Laufzeit)."
fi
if [ "${1:-}" = "--check" ]; then
  echo "Nur Prüfung, nichts installiert."; exit 0
fi

say "Basis-Pakete"
sudo apt-get update -qq
# pipewire-alsa: RetroArch und SDL (RetroPie-Build) sprechen nur ALSA, damit landet der Ton bei PipeWire.
# x11-xserver-utils: xrandr für runcommand unter (X)Wayland.
sudo apt-get install -y -qq git lsb-release dialog pipewire-alsa x11-xserver-utils unclutter-xfixes 2>&1 | tail -2 || true

say "RetroPie-Setup klonen/aktualisieren"
if [ -d "$RP_SETUP/.git" ]; then
  git -C "$RP_SETUP" pull --ff-only 2>&1 | tail -1
else
  git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git "$RP_SETUP"
fi
git -C "$RP_SETUP" log -1 --format='RetroPie-Setup Commit: %h %cd' --date=short

cd "$RP_SETUP"
failed=()
for m in "${MODULES[@]}"; do
  if [ -f "$LOGDIR/$m.done" ]; then
    say "$m bereits installiert, übersprungen"; continue
  fi
  say "Installiere $m (Log: logs/retropie/$m.log)"
  start=$(date +%s)
  if sudo ./retropie_packages.sh "$m" > "$LOGDIR/$m.log" 2>&1; then
    echo "  OK nach $((($(date +%s)-start)/60)) min"
    date > "$LOGDIR/$m.done"
  else
    echo "  FEHLER bei $m, siehe logs/retropie/$m.log (letzte Zeilen:)"
    tail -15 "$LOGDIR/$m.log" | sed 's/^/    /'
    failed+=("$m")
    # Ohne sdl2/retroarch/emulationstation hat der Rest keinen Sinn
    case "$m" in sdl2|retroarch|emulationstation) say "Abbruch."; exit 1;; esac
  fi
done

say "Gaming-Konfiguration anwenden"
"$ROOT/scripts/configure_gaming.sh"

say "Ergebnis"
ls -1 /opt/retropie/libretrocores/ 2>/dev/null | sed 's/^/  core: /'
command -v emulationstation && emulationstation --help 2>/dev/null | head -1
[ ${#failed[@]} -eq 0 ] && echo "Alle Module installiert." || echo "Fehlgeschlagen: ${failed[*]}"
