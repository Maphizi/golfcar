#!/usr/bin/env bash
# Pi als Bluetooth-Lautsprecher (A2DP-Senke) "KITT-Cart": Handy koppeln, Musik läuft über den
# Standard-Sink des Pi und steht den Visualizern als Quelle "playback" zur Verfügung.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${1:-KITT-Cart}"
echo "== Pakete =="
sudo apt-get install -y -qq bluez libspa-0.2-bluetooth bluez-tools 2>&1 | tail -1
sudo systemctl enable --now bluetooth >/dev/null 2>&1
# WirePlumber: A2DP-Senke erlauben (Standard ist nur Quelle/Headset)
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
cat > ~/.config/wireplumber/wireplumber.conf.d/51-kitt-bluetooth.conf <<'CONF'
monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source ]
  bluez5.enable-sbc-xq = true
  bluez5.enable-msbc = false
  bluez5.enable-hw-volume = true
}
CONF
systemctl --user restart wireplumber pipewire pipewire-pulse 2>/dev/null
sleep 2
echo "== Adapter =="
bluetoothctl system-alias "$NAME" >/dev/null 2>&1
bluetoothctl power on >/dev/null
bluetoothctl discoverable-timeout 0 >/dev/null 2>&1
bluetoothctl pairable on >/dev/null
bluetoothctl discoverable on >/dev/null
bluetoothctl show | grep -E "Name|Alias|Powered|Discoverable|Pairable" | sed 's/^/  /'
echo "== Auto-Pairing-Agent (systemd --user) =="
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/kitt-bt-agent.service <<'UNIT'
[Unit]
Description=KITT Bluetooth Auto-Pairing-Agent
After=bluetooth.target

[Service]
ExecStart=/usr/bin/bt-agent -c NoInputNoOutput
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now kitt-bt-agent.service
systemctl --user is-active kitt-bt-agent.service | sed 's/^/  Agent: /'
echo
echo "Jetzt am Handy Bluetooth öffnen und mit \"$NAME\" koppeln. Musik abspielen, dann prüfen:"
echo "  wpctl status   (unter Sources erscheint bluez_input..., der Ton läuft auf den Standard-Sink)"
echo "Visualizer auf Wiedergabe umstellen: in config/audio.toml  source = \"playback\""
