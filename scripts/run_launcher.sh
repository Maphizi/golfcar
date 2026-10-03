#!/usr/bin/env bash
# Launcher im Vordergrund starten (Entwicklung, auch per SSH).
# Findet den Wayland-Socket des angemeldeten Desktops, damit Fenster auf dem HDMI-Display erscheinen.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
  sock=$(ls "$XDG_RUNTIME_DIR"/wayland-[0-9]* 2>/dev/null | grep -v '\.lock$' | head -1 || true)
  [ -n "$sock" ] && export WAYLAND_DISPLAY="$(basename "$sock")"
fi
export DISPLAY="${DISPLAY:-:0}"
export PYGAME_HIDE_SUPPORT_PROMPT=1

echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<leer>}  DISPLAY=$DISPLAY"
exec .venv/bin/python -m launcher "$@"
