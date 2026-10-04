#!/usr/bin/env bash
# Läuft innerhalb der labwc-Session (WAYLAND_DISPLAY ist gesetzt): Umgebung an systemd --user
# übergeben und den Launcher-Dienst starten. Der Dienst startet den Launcher bei Absturz neu.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "[$(date '+%F %T')] session_start: WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-?} DISPLAY=${DISPLAY:-?}"
command -v swaybg >/dev/null 2>&1 && { swaybg -c '#000000' & }
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP XDG_RUNTIME_DIR 2>/dev/null
systemctl --user reset-failed kitt-launcher.service 2>/dev/null
systemctl --user restart kitt-launcher.service
