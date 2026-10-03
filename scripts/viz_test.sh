#!/usr/bin/env bash
# Visualizer-Szene direkt (ohne Launcher) testen, z. B. per SSH:
#   scripts/viz_test.sh crt                 Mikrofon, 12 s, Screenshot nach docs/
#   scripts/viz_test.sh eye --test-signal   synthetisches Musiksignal
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
scene="${1:?Szene: psychedelic | crt | eye}"; shift || true
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
  sock=$(ls "$XDG_RUNTIME_DIR"/wayland-[0-9]* 2>/dev/null | grep -v '\.lock$' | head -1 || true)
  [ -n "$sock" ] && export WAYLAND_DISPLAY="$(basename "$sock")"
fi
export DISPLAY="${DISPLAY:-:0}" PYGAME_HIDE_SUPPORT_PROMPT=1
mkdir -p docs
exec .venv/bin/python -m visualizers.engine "$scene" --seconds 12 --screenshot "docs/screenshot_viz_${scene}.png" "$@"
