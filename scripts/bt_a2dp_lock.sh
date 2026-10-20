#!/usr/bin/env bash
# Bluetooth-Headset (z. B. Bose QC35 II) im Musikprofil A2DP halten: WirePlumber soll NICHT auf das
# Headset-Profil HFP umschalten, sobald irgendein Programm das Mikrofon öffnet (dann wird die Musik
# leise und blechern). Legt eine WirePlumber-Konfiguration an und startet WirePlumber neu.
#   scripts/bt_a2dp_lock.sh          einrichten
#   scripts/bt_a2dp_lock.sh --undo   wieder entfernen
# Folge: Das Mikrofon des Headsets ist dann nicht mehr nutzbar; HAL/KITT brauchen ein anderes
# Mikrofon (USB). config/audio.toml [capture].avoid_bluetooth_mic sorgt dafür, dass es gewählt wird.
set -uo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DIR="$HOME/.config/wireplumber/wireplumber.conf.d"
FILE="$DIR/50-kitt-bluez-no-autoswitch.conf"
if [ "${1:-}" = "--undo" ]; then
  rm -f "$FILE" && echo "entfernt: $FILE"
else
  mkdir -p "$DIR"
  cat > "$FILE" <<'CONF'
# KITT-Cart: Bluetooth-Headset bleibt im A2DP-Musikprofil, auch wenn ein Mikrofonstream geöffnet wird.
monitor.bluez.properties = {
  bluez5.autoswitch-to-headset-profile = false
}
CONF
  echo "geschrieben: $FILE"
fi
systemctl --user restart wireplumber 2>&1 && echo "WirePlumber neu gestartet" || echo "WirePlumber-Neustart fehlgeschlagen (systemctl --user restart wireplumber)"
sleep 2
echo "== Bluetooth-Geräte und Profile =="
wpctl status 2>/dev/null | sed -n '/Audio/,/Video/p' | grep -iE "bluez|bose|headset|a2dp|hfp|hsp" || echo "(kein Bluetooth-Audiogerät sichtbar)"
