#!/usr/bin/env bash
# Appliance-Autostart ausschalten: lightdm startet wieder den normalen Pi-Desktop (rpd-labwc).
# Der Launcher-Dienst wird gestoppt. Session-Datei und Unit bleiben installiert (harmlos).
set -uo pipefail
LDM=/etc/lightdm/lightdm.conf
systemctl --user stop kitt-launcher.service 2>/dev/null || true
sudo sed -i -E 's/^(autologin-session)=.*/\1=rpd-labwc/; s/^(user-session)=.*/\1=rpd-labwc/' "$LDM"
grep -E '^(autologin-user|autologin-session|user-session)=' "$LDM" | sed 's/^/  /'
echo "Autostart deaktiviert. Wirksam nach Neustart:  sudo reboot"
echo "Wieder einschalten:  scripts/autostart_enable.sh"
