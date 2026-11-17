#!/usr/bin/env bash
# Läuft innerhalb der labwc-Session (WAYLAND_DISPLAY ist gesetzt): Umgebung an systemd --user
# übergeben und den Launcher-Dienst starten. Der Dienst startet den Launcher bei Absturz neu.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP=0; [ "${1:-}" = "--desktop" ] && DESKTOP=1     # im normalen Pi-Desktop (scripts/autostart_desktop.sh): Hintergrund und Leiste hat der Desktop
echo "[$(date '+%F %T')] session_start: WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-?} DISPLAY=${DISPLAY:-?} desktop=$DESKTOP"
[ "$DESKTOP" = 1 ] || { command -v swaybg >/dev/null 2>&1 && { swaybg -i "$ROOT/config/labwc/wallpaper.png" -m fill & }; }
# Pi-Leiste (WLAN, Bluetooth, Lautstärke) dauerhaft: liegt auf dem Desktop oben, Vollbild-Szenen decken sie ab.
# Abschalten: KITT_NO_PANEL=1 in ~/.config/environment.d/ oder die Zeile hier auskommentieren.
if [ "$DESKTOP" = 0 ] && [ -z "${KITT_NO_PANEL:-}" ]; then
  pgrep -x wf-panel-pi >/dev/null || { command -v wf-panel-pi >/dev/null 2>&1 && { wf-panel-pi & } || { command -v lxpanel >/dev/null 2>&1 && { lxpanel & }; }; }
fi
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP XDG_RUNTIME_DIR 2>/dev/null
systemctl --user reset-failed kitt-launcher.service 2>/dev/null
systemctl --user restart kitt-launcher.service
# Erster Start jeder Szene nach dem Boot: alles Nötige mit niedrigster Priorität in den Seitencache lesen (scripts/warm_pagecache.sh)
( sleep 8; ionice -c3 nice -n19 "$ROOT/scripts/warm_pagecache.sh" ) >/dev/null 2>&1 &
