#!/usr/bin/env bash
# Autostart für Wartung abschalten. Der Launcher wird gestoppt und startet beim Boot nicht mehr.
systemctl --user disable --now kitt-launcher.service 2>/dev/null || true
echo "Autostart deaktiviert. Wieder einschalten: scripts/autostart_enable.sh"
