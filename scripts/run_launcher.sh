#!/usr/bin/env bash
# Launcher im Vordergrund starten (Entwicklung, auch per SSH).
# Findet den Wayland-Socket des angemeldeten Desktops, damit Fenster auf dem HDMI-Display erscheinen.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
# Auf den Compositor warten (beim Boot startet der Dienst evtl. vor dem Wayland-Socket)
for i in $(seq 1 40); do
  if [ -z "${WAYLAND_DISPLAY:-}" ]; then
    sock=$(ls "$XDG_RUNTIME_DIR"/wayland-[0-9]* 2>/dev/null | grep -v '\.lock$' | head -1 || true)
    [ -n "$sock" ] && export WAYLAND_DISPLAY="$(basename "$sock")"
  fi
  [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] && break
  [ "$i" -eq 1 ] && echo "warte auf Wayland-Socket in $XDG_RUNTIME_DIR ..."
  sleep 0.5
done
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
  echo "Kein Wayland-Socket gefunden, Abbruch (exit 1, systemd startet neu)"; exit 1
fi
export DISPLAY="${DISPLAY:-:0}"
export PYGAME_HIDE_SUPPORT_PROMPT=1

echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<leer>}  DISPLAY=$DISPLAY"
exec .venv/bin/python -m launcher "$@"
