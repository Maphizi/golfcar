#!/usr/bin/env bash
# Modus F1: EmulationStation starten. Wird vom Launcher aufgerufen (modes.toml).
#
# Backend-Wahl (Umgebungsvariable KITT_GAMING_BACKEND, Standard "xwayland"):
#   xwayland  ES und RetroArch laufen als X11-Clients unter labwc (RetroPies RetroArch-Build
#             hat keinen Wayland-Support, der RetroPie-SDL-Build evtl. auch nicht).
#   wayland   ES nativ über SDL-Wayland (nur falls der SDL-Build Wayland kann), RetroArch via X11.
set -u
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DISPLAY="${DISPLAY:-:0}"
export TERM="${TERM:-linux}"      # der ES-Wrapper ruft tput/clear auf
backend="${KITT_GAMING_BACKEND:-xwayland}"
if [ "$backend" = "xwayland" ]; then
  unset WAYLAND_DISPLAY          # sonst zwingt der ES-Wrapper SDL auf Wayland
  export SDL_VIDEODRIVER=x11
fi
# Mauszeiger unter X verstecken, solange der Modus läuft
if command -v unclutter >/dev/null 2>&1; then
  unclutter --timeout 1 --start-hidden >/dev/null 2>&1 &
  UNCL=$!
  trap 'kill $UNCL 2>/dev/null' EXIT
fi
echo "run_gaming: backend=$backend DISPLAY=$DISPLAY SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-<leer>}"
# --no-splash: schneller Start; ES beendet sich über Menü > Quit, der Launcher geht dann auf Home
emulationstation --no-splash
echo "run_gaming: emulationstation exit $?"
