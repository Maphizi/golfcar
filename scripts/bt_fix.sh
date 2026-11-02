#!/usr/bin/env bash
# Aufräumen nach dem Miracast-Abend (2026-11-02): entfernt miraclecast (vom Bot aus dem Quellcode gebaut und
# installiert, taucht in apt nicht auf) samt Diensten und D-Bus-Dateien. Fasst sonst NICHTS an.
# Gibt am Ende aus, was entfernt wurde und ob ein Neustart nötig ist.
#   scripts/bt_fix.sh          ausführen (braucht sudo)
#   scripts/bt_fix.sh --dry    nur zeigen, was entfernt würde
set -uo pipefail
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1
removed=0
say() { printf '%s\n' "$*"; }
rm_path() { # rm_path PFAD : löschen, wenn vorhanden
  for p in "$@"; do
    [ -e "$p" ] || continue
    if [ "$DRY" = 1 ]; then say "  würde entfernen: $p"; else sudo rm -rf "$p" && say "  entfernt: $p"; fi
    removed=$((removed+1))
  done
}

say "== miraclecast: Dienste und Prozesse =="
for u in miracle-wifid miracle-dispd miracle-sinkctl; do
  if systemctl list-unit-files --no-legend 2>/dev/null | grep -q "^$u"; then
    say "  Dienst $u: $(systemctl is-active "$u" 2>/dev/null) / $(systemctl is-enabled "$u" 2>/dev/null)"
    [ "$DRY" = 1 ] || sudo systemctl disable --now "$u" 2>/dev/null
    removed=$((removed+1))
  fi
  if systemctl --user list-unit-files --no-legend 2>/dev/null | grep -q "^$u"; then
    say "  Benutzerdienst $u"; [ "$DRY" = 1 ] || systemctl --user disable --now "$u" 2>/dev/null; removed=$((removed+1))
  fi
done
if pgrep -f 'miracle-(wifid|dispd|sinkctl|wifictl)' >/dev/null; then
  pgrep -af 'miracle-(wifid|dispd|sinkctl|wifictl)' | sed 's/^/  läuft: /'
  [ "$DRY" = 1 ] || sudo pkill -f 'miracle-(wifid|dispd|sinkctl|wifictl)'
fi

say "== miraclecast: Dateien =="
rm_path /usr/local/bin/miracle-wifid /usr/local/bin/miracle-dispd /usr/local/bin/miracle-sinkctl /usr/local/bin/miracle-wifictl \
        /usr/local/bin/miracle-omxplayer /usr/local/bin/miracle-gst /usr/local/bin/gstplayer /usr/local/bin/uibc-viewer \
        /usr/local/lib/systemd/system/miracle-wifid.service /usr/local/lib/systemd/system/miracle-dispd.service \
        /etc/systemd/system/miracle-wifid.service /etc/systemd/system/miracle-dispd.service \
        /usr/local/share/dbus-1/system-services/org.freedesktop.miracle.wifi.service \
        /usr/local/share/dbus-1/system-services/org.freedesktop.miracle.disp.service \
        /usr/local/share/dbus-1/system.d/org.freedesktop.miracle.conf /etc/dbus-1/system.d/org.freedesktop.miracle.conf \
        /usr/local/share/miraclecast /usr/local/etc/miraclecast /usr/local/include/miraclecast
for f in /usr/local/lib/libmiracle* /usr/local/lib/aarch64-linux-gnu/libmiracle* /usr/local/lib/miraclecast*; do rm_path "$f"; done
# was sonst noch "miracle" heißt (nur anzeigen, nicht blind löschen)
rest="$(find /usr/local /etc /opt /usr/lib/systemd /usr/share/dbus-1 -iname '*miracle*' 2>/dev/null)"
[ -n "$rest" ] && { say "  noch vorhanden (bitte melden):"; echo "$rest" | sed 's/^/    /'; }
src="$(ls -d "$HOME"/miraclecast* /tmp/miraclecast* /root/miraclecast* 2>/dev/null)"
[ -n "$src" ] && say "  Quellcode-Ordner (harmlos, kann weg): $src"

if [ "$DRY" = 0 ] && [ "$removed" -gt 0 ]; then
  sudo ldconfig 2>/dev/null; sudo systemctl daemon-reload 2>/dev/null; systemctl --user daemon-reload 2>/dev/null
  sudo systemctl reload dbus 2>/dev/null || true
fi
say "== Ergebnis =="
if [ "$removed" -gt 0 ]; then
  [ "$DRY" = 1 ] && say "  $removed Fundstellen (Probelauf, nichts geändert)." || say "  $removed Fundstellen entfernt. NEUSTART NÖTIG: sudo reboot"
else
  say "  Nichts von miraclecast gefunden, nichts geändert."
fi
