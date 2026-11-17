#!/usr/bin/env bash
# Desktop-Modus: lightdm meldet den Benutzer im NORMALEN Pi-Desktop an (rpd-labwc: Hintergrund, Leiste, Dateimanager),
# der Launcher startet darin automatisch als Benutzer-Dienst und legt seine Vollbild-Szenen über den Desktop.
# Taste 9 / ESC / `scripts/kittctl quit` beendet den Launcher sauber -> der Desktop ist wieder da (Dienst bleibt aus,
# Restart=on-failure). Wieder starten: Desktop-Symbol "KITT-Cart" oder  systemctl --user restart kitt-launcher
# Zurück zur reinen Cart-Sitzung ohne Desktop: scripts/autostart_enable.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LDM=/etc/lightdm/lightdm.conf
echo "== systemd --user: kitt-launcher.service =="
mkdir -p ~/.config/systemd/user ~/.config/autostart ~/.local/share/applications
sed "s|__ROOT__|$ROOT|g" "$ROOT/systemd/kitt-launcher.service" > ~/.config/systemd/user/kitt-launcher.service
systemctl --user daemon-reload
sudo loginctl enable-linger "$USER"
chmod +x "$ROOT"/scripts/session_start.sh "$ROOT"/scripts/run_launcher.sh
echo "== Autostart im Desktop (~/.config/autostart/kitt-launcher.desktop) =="
cat > ~/.config/autostart/kitt-launcher.desktop <<DESK
[Desktop Entry]
Type=Application
Name=KITT-Cart Launcher
Comment=Startet den Cart-Launcher im Desktop
Exec=/bin/bash -c "$ROOT/scripts/session_start.sh --desktop"
X-GNOME-Autostart-enabled=true
NoDisplay=true
DESK
echo "== Desktop-Symbol und Menüeintrag: KITT-Cart =="
cat > ~/.local/share/applications/kitt-cart.desktop <<DESK
[Desktop Entry]
Type=Application
Name=KITT-Cart
Comment=Cart-Launcher starten (Taste 9 beendet ihn wieder)
Exec=/bin/bash -c "$ROOT/scripts/session_start.sh --desktop"
Icon=$ROOT/assets/splash/scene.png
Terminal=false
Categories=AudioVideo;Game;
DESK
mkdir -p ~/Desktop && cp ~/.local/share/applications/kitt-cart.desktop ~/Desktop/ && chmod +x ~/Desktop/kitt-cart.desktop
echo "== lightdm: normaler Pi-Desktop mit Autologin =="
[ -f "$LDM.kitt-backup" ] || sudo cp "$LDM" "$LDM.kitt-backup"
sudo sed -i -E 's/^#?(autologin-session)=.*/\1=rpd-labwc/; s/^#?(user-session)=.*/\1=rpd-labwc/' "$LDM"
grep -qE '^autologin-session=' "$LDM" || echo "autologin-session=rpd-labwc" | sudo tee -a "$LDM" >/dev/null
grep -qE "^autologin-user=$USER" "$LDM" || sudo sed -i -E "s/^#?autologin-user=.*/autologin-user=$USER/" "$LDM"
grep -E '^(autologin-user|autologin-session|user-session)=' "$LDM" | sed 's/^/  /'
echo
echo "Desktop-Modus aktiv. Wirksam nach Neustart:  sudo reboot"
echo "Launcher beenden: Taste 9 oder scripts/kittctl quit -> Desktop. Starten: Symbol KITT-Cart oder systemctl --user restart kitt-launcher"
