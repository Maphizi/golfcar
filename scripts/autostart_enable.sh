#!/usr/bin/env bash
# Phase 9: Appliance-Autostart einschalten.
#   lightdm meldet maphizi automatisch in der Session "KITT-Cart" an (labwc ohne Desktop),
#   die Session startet den systemd-User-Dienst kitt-launcher, der den Launcher überwacht.
# Rückgängig: scripts/autostart_disable.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LDM=/etc/lightdm/lightdm.conf
echo "== Pakete =="
sudo apt-get install -y -qq swaybg 2>&1 | tail -1 || true
echo "== Session-Datei =="
sed "s|__ROOT__|$ROOT|g" "$ROOT/systemd/kitt-cart.desktop" | sudo tee /usr/share/wayland-sessions/kitt-cart.desktop >/dev/null
chmod +x "$ROOT"/scripts/session_kitt.sh "$ROOT"/scripts/session_start.sh "$ROOT"/scripts/run_launcher.sh
echo "  /usr/share/wayland-sessions/kitt-cart.desktop"
echo "== systemd --user ==" 
mkdir -p ~/.config/systemd/user
sed "s|__ROOT__|$ROOT|g" "$ROOT/systemd/kitt-launcher.service" > ~/.config/systemd/user/kitt-launcher.service
systemctl --user daemon-reload
# Benutzer-Dienste sollen schon beim Boot laufen dürfen (nicht erst nach Login)
sudo loginctl enable-linger "$USER"
echo "== lightdm =="
[ -f "$LDM.kitt-backup" ] || sudo cp "$LDM" "$LDM.kitt-backup"
sudo sed -i -E 's/^#?(autologin-session)=.*/\1=kitt-cart/; s/^#?(user-session)=.*/\1=kitt-cart/' "$LDM"
grep -qE '^autologin-session=' "$LDM" || echo "autologin-session=kitt-cart" | sudo tee -a "$LDM" >/dev/null
grep -qE "^autologin-user=$USER" "$LDM" || sudo sed -i -E "s/^#?autologin-user=.*/autologin-user=$USER/" "$LDM"
grep -E '^(autologin-user|autologin-session|user-session)=' "$LDM" | sed 's/^/  /'
echo
echo "Autostart aktiv. Wirksam nach Neustart:  sudo reboot"
echo "Zurück zum normalen Desktop:  scripts/autostart_disable.sh && sudo reboot"
