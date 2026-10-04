#!/usr/bin/env bash
# Wayland-Session "KITT-Cart": wird von lightdm beim Autologin gestartet (statt rpd-labwc).
# Startet labwc mit unserer Minimal-Konfiguration; labwc ruft dann session_start.sh auf.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export XDG_CURRENT_DESKTOP=labwc
export XDG_SESSION_TYPE=wayland
export PYGAME_HIDE_SUPPORT_PROMPT=1
mkdir -p "$ROOT/logs"
exec labwc -C "$ROOT/config/labwc" -s "$ROOT/scripts/session_start.sh" >> "$ROOT/logs/session.log" 2>&1
