#!/usr/bin/env bash
# Miracast-Sender manuell starten / Status anzeigen
# Nutzung: ./miracast_start.sh [start|stop|status|scan]

CMD="${1:-status}"
WPA_CLI="sudo /usr/sbin/wpa_cli"
XDG_ENV="WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus"

p() { echo -e "\033[1;36m$*\033[0m"; }
ok() { echo -e "\033[1;32m✓ $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }
err() { echo -e "\033[1;31m✗ $*\033[0m"; }

case "$CMD" in
  start)
    p "=== Miracast-Sender starten ==="
    # XDG-Portal starten
    eval "env $XDG_ENV" systemctl --user start xdg-desktop-portal xdg-desktop-portal-wlr
    sleep 1
    # kitt-miracast Service (re)starten
    systemctl --user reset-failed kitt-miracast.service 2>/dev/null
    systemctl --user restart kitt-miracast.service
    ok "Service gestartet"
    p "gnome-network-displays öffnet sich und scannt nach Miracast-Geräten."
    p "Sobald der Dongle (530E1F_P2P) in Reichweite ist → erscheint er in der Liste."
    ;;
  
  stop)
    p "=== Miracast-Sender stoppen ==="
    systemctl --user stop kitt-miracast.service
    $WPA_CLI -i p2p-dev-wlan0 p2p_stop_find 2>/dev/null || true
    pkill -f gnome-network-displays 2>/dev/null || true
    ok "Gestoppt"
    ;;
  
  scan)
    p "=== P2P-Scan (30s) ==="
    $WPA_CLI -i p2p-dev-wlan0 p2p_find type=progressive 2>/dev/null
    sleep 5
    for i in 1 2 3 4 5; do
      PEERS=$($WPA_CLI -i p2p-dev-wlan0 p2p_peers 2>/dev/null)
      if [[ -n "$PEERS" ]]; then
        ok "P2P Gerät(e) gefunden:"
        echo "$PEERS"
        $WPA_CLI -i p2p-dev-wlan0 p2p_peer "$PEERS" 2>/dev/null | head -10 || true
        break
      fi
      echo "Suche... ($((i*5))s)"
      sleep 5
    done
    PEERS=$($WPA_CLI -i p2p-dev-wlan0 p2p_peers 2>/dev/null)
    if [[ -z "$PEERS" ]]; then
      warn "Keine P2P-Geräte gefunden. Dongle eingeschaltet und in der Nähe?"
    fi
    ;;
  
  status)
    p "=== Miracast Status ==="
    if systemctl --user is-active kitt-miracast.service &>/dev/null; then
      ok "kitt-miracast.service: aktiv"
    else
      err "kitt-miracast.service: inaktiv"
    fi
    
    if pgrep -f gnome-network-displays &>/dev/null; then
      ok "gnome-network-displays: läuft"
    else
      warn "gnome-network-displays: nicht aktiv"
    fi
    
    if systemctl --user is-active xdg-desktop-portal &>/dev/null; then
      ok "xdg-desktop-portal: aktiv"
    else
      warn "xdg-desktop-portal: inaktiv"
    fi
    
    echo ""
    p "P2P Interface: $($WPA_CLI -i p2p-dev-wlan0 status 2>/dev/null | head -2)"
    PEERS=$($WPA_CLI -i p2p-dev-wlan0 p2p_peers 2>/dev/null || echo "keine")
    echo "P2P Peers: ${PEERS:-keine}"
    
    echo ""
    p "WLAN (Tailscale-Verbindung):"
    nmcli dev status | grep -E 'wlan0|tailscale'
    ;;
esac
