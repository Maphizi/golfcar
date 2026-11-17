#!/usr/bin/env bash
# miracast_watch.sh - Überwacht P2P und verbindet mit Miracast-Dongle 530E1F_P2P
# Läuft als systemd-User-Service in der labwc-Wayland-Session

set -euo pipefail

TARGET_OUI="530e1f"
P2P_IFACE="p2p-dev-wlan0"
WPA_CLI="sudo /usr/sbin/wpa_cli"
LOG_TAG="miracast-watch"
CONNECTED_MAC=""
GND_PID=""

log() { echo "[$(date '+%F %T')] [$LOG_TAG] $*" >&2; systemd-cat -t "$LOG_TAG" echo "$*" 2>/dev/null || true; }

cleanup() {
    log "Aufräumen..."
    $WPA_CLI -i "$P2P_IFACE" p2p_stop_find 2>/dev/null || true
    if [[ -n "$GND_PID" ]] && kill -0 "$GND_PID" 2>/dev/null; then
        kill "$GND_PID"
    fi
}
trap cleanup EXIT

start_gnome_network_displays() {
    log "Starte gnome-network-displays..."
    if [[ -n "$GND_PID" ]] && kill -0 "$GND_PID" 2>/dev/null; then
        log "gnome-network-displays läuft bereits (PID $GND_PID)"
        return
    fi
    WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}" \
    DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}" \
    gnome-network-displays &
    GND_PID=$!
    log "gnome-network-displays gestartet (PID $GND_PID)"
}

connect_p2p() {
    local mac="$1"
    log "Verbinde mit P2P-Gerät $mac..."
    # PBC (Push Button Configuration) - Dongle akzeptiert alle Verbindungen
    $WPA_CLI -i "$P2P_IFACE" p2p_connect "$mac" pbc 2>/dev/null || \
    $WPA_CLI -i wlan0 p2p_connect "$mac" pbc 2>/dev/null || true
}

main() {
    log "P2P-Watch gestartet. Suche nach Gerät mit OUI $TARGET_OUI..."

    # Sicherstellen dass XDG-Portal läuft
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}" \
    DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}" \
    systemctl --user start xdg-desktop-portal xdg-desktop-portal-wlr 2>/dev/null || true

    # gnome-network-displays direkt starten (zeigt verfügbare Miracast-Geräte)
    start_gnome_network_displays

    # P2P-Scan starten
    $WPA_CLI -i "$P2P_IFACE" p2p_find type=progressive 2>/dev/null || \
    $WPA_CLI -i wlan0 p2p_find type=progressive 2>/dev/null || {
        log "WARNUNG: p2p_find fehlgeschlagen"
        sleep 10
        exec "$0" "$@"
    }

    log "P2P-Scan aktiv. Überwache Ereignisse..."

    # Gerät überwachen via wpa_cli events (-p = monitor mode)
    $WPA_CLI -i "$P2P_IFACE" -a /dev/stdin 2>/dev/null &
    WPA_MON_PID=$!

    # Alternativ: periodisch nach peers suchen
    while sleep 15; do
        # Prüfe ob gnome-network-displays noch läuft
        if [[ -n "$GND_PID" ]] && ! kill -0 "$GND_PID" 2>/dev/null; then
            log "gnome-network-displays beendet, starte neu..."
            start_gnome_network_displays
        fi

        # P2P-Peers prüfen
        PEERS=$($WPA_CLI -i "$P2P_IFACE" p2p_peers 2>/dev/null || \
                $WPA_CLI -i wlan0 p2p_peers 2>/dev/null || echo "")
        
        if echo "$PEERS" | grep -qi "$TARGET_OUI"; then
            FOUND_MAC=$(echo "$PEERS" | grep -i "$TARGET_OUI" | head -1 | tr -d '[:space:]')
            if [[ "$FOUND_MAC" != "$CONNECTED_MAC" ]]; then
                log "Miracast-Dongle gefunden: $FOUND_MAC"
                CONNECTED_MAC="$FOUND_MAC"
                connect_p2p "$FOUND_MAC"
            fi
        else
            # Scan erneuern alle 60s
            $WPA_CLI -i "$P2P_IFACE" p2p_find type=progressive 2>/dev/null || true
        fi
    done
}

main "$@"
