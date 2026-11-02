#!/usr/bin/env bash
# Bluetooth-/Funk-Diagnose für den Pi: sammelt alles Relevante in EINE Datei und pusht sie auf den Branch "diag",
# damit die Auswertung ohne Abtippen möglich ist. Ändert NICHTS am System (nur lesen).
#   scripts/bt_diag.sh            -> diag/bt_diag_<datum>.txt, Push nach origin/diag (ohne Einfluss auf den Arbeitsbranch)
#   scripts/bt_diag.sh --no-push  -> nur die Datei schreiben und ausgeben
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
PATH="$PATH:/usr/sbin:/sbin"
STAMP="$(date '+%Y%m%d_%H%M%S')"
OUTDIR="$ROOT/diag"; mkdir -p "$OUTDIR"
OUT="$OUTDIR/bt_diag_$STAMP.txt"
PUSH=1; [ "${1:-}" = "--no-push" ] && PUSH=0
S() { printf '\n===== %s =====\n' "$1"; }
run() { # run "Titel" cmd... : Befehl ausführen, Fehler nicht abbrechen lassen
  local t="$1"; shift; S "$t"; "$@" 2>&1 || echo "(rc=$?)"; }
sudo_ok() { sudo -n true 2>/dev/null; }

{
S "Allgemein"
date; uptime; uname -r; cat /etc/os-release | grep PRETTY; echo "Benutzer: $(id -un), sudo ohne Passwort: $(sudo_ok && echo ja || echo nein)"
run "Throttling / Temperatur" sh -c 'vcgencmd get_throttled; vcgencmd measure_temp'

S "apt history seit 2026-10-01: alle Läufe (Commandline), Remove/Purge komplett, Install/Upgrade nur Kernel/Firmware/Audio/BT"
zcat -f /var/log/apt/history.log* 2>/dev/null | awk '/^Start-Date: 2026-(1[0-2])-/{p=1} /^Start-Date: 2026-0/{p=0} p' | while IFS= read -r l; do
  case "$l" in
    Start-Date:*|Commandline:*|End-Date:*) echo "$l" ;;
    Remove:*|Purge:*) echo "$l" | cut -c1-1200 ;;
    Install:*|Upgrade:*) k="${l%%:*}"; echo "$l" | sed 's/^[A-Za-z]*: //' | tr ',' '\n' | grep -iE 'linux-image|raspi-firmware|firmware-brcm|bluez|pi-bluetooth|pipewire|libspa|wireplumber|rtkit|raspberrypi-sys|wpasupplicant|network-manager' | sed "s/^ */  $k: /" ;;
  esac; done
S "Pakete Bluetooth/Audio/Firmware (ii = installiert, rc = entfernt, Konfig da, fehlt = nie/ganz weg)"
for p in bluez bluez-firmware pi-bluetooth libspa-0.2-bluetooth pipewire pipewire-pulse pipewire-audio wireplumber \
         firmware-brcm80211 raspi-firmware raspberrypi-sys-mods rfkill bluez-tools libldacbt-enc2 libfreeaptx0 libopenaptx0; do
  st="$(dpkg-query -W -f='${db:Status-Abbrev} ${Version}' "$p" 2>/dev/null || echo "fehlt")"; printf '  %-24s %s\n' "$p" "$st"
done
run "Bluetooth-Firmware-Dateien" sh -c 'ls -la /lib/firmware/brcm/BCM4345C0* /lib/firmware/updates/brcm/BCM4345C0* /lib/firmware/synaptics/*4345* 2>&1 | head'

S "Kernel: Bluetooth/HCI/BCM/brcmfmac seit Boot (ohne 'continuation frame', erste 40 Zeilen)"
dmesg -T 2>/dev/null | grep -iE 'bluetooth|hci0|hci_uart|bcm43|brcmf|serial.*uart|ttyAMA' | grep -v 'continuation frame' | head -n 40 || echo "(dmesg nicht lesbar)"
S "Kernel: letzte 15 Bluetooth-Zeilen ohne 'continuation frame'"
dmesg -T 2>/dev/null | grep -iE 'bluetooth|hci0' | grep -v 'continuation frame' | tail -n 15
S "Rate der 'continuation frame'-Meldungen und ACL-Empfang in 10 s"
c0="$(dmesg 2>/dev/null | grep -c 'continuation frame')"; a0="$(hciconfig hci0 2>/dev/null | grep -oE 'RX bytes:[0-9]+ acl:[0-9]+')"
sleep 10
c1="$(dmesg 2>/dev/null | grep -c 'continuation frame')"; a1="$(hciconfig hci0 2>/dev/null | grep -oE 'RX bytes:[0-9]+ acl:[0-9]+')"
echo "  continuation: $c0 -> $c1 (+$((c1-c0)) in 10 s)"; echo "  hci0 vorher:  $a0"; echo "  hci0 nachher: $a1"
S "'Unexpected continuation frame' je Boot (0 = aktueller Boot; frühere Boots = Zustand VOR heute)"
journalctl --list-boots --no-pager 2>/dev/null | tail -n 8
for b in 0 -1 -2 -3 -4 -5; do
  n="$(journalctl -b $b -k --no-pager 2>/dev/null | grep -c 'continuation frame')"
  t="$(journalctl -b $b --no-pager -o short-iso 2>/dev/null | head -n 1 | cut -c1-19)"
  [ -n "$t" ] && echo "  Boot $b ($t): $n Zeilen"
done
S "journal bluetooth/wireplumber (letzte 40)"
journalctl -b --no-pager 2>/dev/null | grep -iE 'bluetoothd|bluez|wireplumber|hci0' | grep -v 'continuation frame' | tail -n 40

run "hciconfig -a" hciconfig -a
run "btmgmt info" sh -c 'command -v btmgmt >/dev/null && (sudo -n btmgmt info 2>/dev/null || btmgmt info)'
run "rfkill" rfkill list
run "bluetoothctl show" bluetoothctl show
run "bluetoothctl devices" bluetoothctl devices
S "bluetoothctl info (alle bekannten Geräte)"
bluetoothctl devices 2>/dev/null | awk '{print $2}' | while read -r m; do echo "-- $m"; bluetoothctl info "$m" 2>/dev/null | grep -E 'Name|Alias|Class|Paired|Trusted|Blocked|Connected|UUID: (Audio|Advanced|A/V|Handsfree|Headset)|RSSI|Battery'; done
run "hcitool con (Rolle)" hcitool con
run "/etc/bluetooth/main.conf (ohne Kommentare)" sh -c 'grep -vE "^\s*#|^\s*$" /etc/bluetooth/main.conf'

S "Boot-Konfiguration (config.txt, cmdline.txt) + Änderungszeit"
ls -la --time-style=full-iso /boot/firmware/config.txt /boot/firmware/cmdline.txt 2>/dev/null
grep -vE '^\s*#|^\s*$' /boot/firmware/config.txt 2>/dev/null; echo "cmdline: $(cat /boot/firmware/cmdline.txt 2>/dev/null)"

S "WLAN"
iw dev wlan0 link 2>/dev/null; iw dev wlan0 get power_save 2>/dev/null
iw dev wlan0 station dump 2>/dev/null | grep -E 'signal|bitrate|tx failed|tx retries|rx drop'
nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device 2>/dev/null
echo "NM conf.d:"; ls -la --time-style=long-iso /etc/NetworkManager/conf.d/ 2>/dev/null; cat /etc/NetworkManager/conf.d/*.conf 2>/dev/null | grep -vE '^\s*#|^\s*$'
echo "NM Verbindungen:"; nmcli -t -f NAME,TYPE,DEVICE connection show 2>/dev/null

S "PipeWire / WirePlumber: Dateien"
for d in ~/.config/wireplumber/wireplumber.conf.d ~/.config/wireplumber/bluetooth.lua.d ~/.config/pipewire /etc/wireplumber/wireplumber.conf.d /etc/pipewire/pipewire.conf.d /etc/pipewire/pipewire-pulse.conf.d; do
  [ -d "$d" ] || continue; echo "-- $d"; ls -la --time-style=long-iso "$d"; for f in "$d"/*; do [ -f "$f" ] && { echo "   [$f]"; sed 's/^/     /' "$f"; }; done
done
run "wpctl status" wpctl status
S "Standard-Sink: Bluetooth-Eigenschaften (Codec, Profil)"
wpctl inspect @DEFAULT_AUDIO_SINK@ 2>/dev/null | grep -iE 'node.name|node.description|api.bluez5|codec|device.profile|audio.channels|audio.rate|clock.quantum'
S "Bluetooth-Gerät in WirePlumber"
for id in $(wpctl status 2>/dev/null | sed -n '/Devices:/,/^$/p' | grep -iE 'bluez' | grep -oE '[0-9]+\.' | tr -d '.'); do wpctl inspect "$id" 2>/dev/null | grep -iE 'device.description|device.profile|api.bluez5|device.form'; done
run "pw-top (eine Aufnahme)" sh -c 'command -v pw-top >/dev/null && timeout 3 pw-top -b -n 2 2>/dev/null | tail -n 25'

S "Dienste und Autostart"
systemctl --user list-units --type=service --no-pager --no-legend 2>/dev/null | grep -iE 'kitt|pipewire|wireplumber|spotify|airplay|shairport|librespot|portal|network-displays|bt-agent' | sed 's/^/  user   /'
systemctl list-units --type=service --no-pager --no-legend 2>/dev/null | grep -iE 'kitt|bluetooth|hciuart|network|miracast|portal' | sed 's/^/  system /'
for d in ~/.config/autostart ~/.config/labwc /etc/xdg/autostart ~/.config/systemd/user; do [ -d "$d" ] && { echo "-- $d"; ls -la --time-style=long-iso "$d"; }; done
[ -f ~/.config/labwc/autostart ] && { echo "-- labwc autostart:"; cat ~/.config/labwc/autostart; }
echo "-- sudoers.d:"; sudo -n ls -la /etc/sudoers.d/ 2>/dev/null || ls -la /etc/sudoers.d/ 2>&1
echo "-- Prozesse (CPU):"; ps -eo pid,pcpu,pmem,stat,cmd --sort=-pcpu | head -n 14
echo "-- Prozesse mit Funkbezug:"; pgrep -af 'network-displays|miracast|btmon|hcitool|bluetoothctl|wpa_cli|iw |xdg-desktop' || echo "  keine"

S "Fremdinstallationen außerhalb von apt (/usr/local, /opt) und alles mit 'miracle'/'wifid'/'dispd'"
pgrep -af 'miracle|wifid|dispd' || echo "  kein miracle-Prozess"
systemctl list-unit-files --no-pager --no-legend 2>/dev/null | grep -iE 'miracle|wifid|dispd|network-displays' || echo "  keine miracle-Units"
ls -la --time-style=long-iso /usr/local/bin /usr/local/sbin /usr/local/lib/systemd/system /usr/local/share/dbus-1/system-services /usr/local/share/dbus-1/system.d 2>/dev/null
find /usr/local /opt /etc /usr/lib/systemd /usr/share/dbus-1 \( -iname '*miracle*' -o -iname '*wifid*' -o -iname '*dispd*' \) 2>/dev/null | head -n 40
S "Dateien außerhalb von /home, die seit dem 02.11. 19:40 neu/geändert sind (ohne Paketinhalte unter /usr/lib,/usr/share)"
find / -xdev -newermt '2026-11-02 19:40' -type f 2>/dev/null \
  | grep -vE '^/(proc|sys|run|tmp|var/(cache|lib/apt|lib/dpkg|log|tmp|backups)|home|usr/share/(doc|man|locale|icons|mime|applications)|usr/lib/(aarch64|python3|x86)|boot/firmware/overlays)' \
  | grep -vE '\.(pyc|cache)$' | head -n 120 | while read -r f; do ls -la --time-style=long-iso "$f" 2>/dev/null; done
S "NetworkManager-Profile (ohne Schlüssel)"
sudo -n sh -c 'for f in /etc/NetworkManager/system-connections/*; do echo "-- $f ($(stat -c %y "$f" | cut -c1-19))"; grep -vE "psk|password|^$" "$f"; done' 2>/dev/null || echo "  (kein sudo)"
S "rtkit (Echtzeitpriorität für PipeWire)"
dpkg-query -W -f='  rtkit ${db:Status-Abbrev} ${Version}\n' rtkit 2>/dev/null || echo "  rtkit fehlt"
systemctl is-active rtkit-daemon 2>/dev/null | sed 's/^/  rtkit-daemon: /'

S "Zuletzt geänderte Konfigurationsdateien (3 Tage, /etc und ~/.config)"
find /etc ~/.config -type f -mtime -3 2>/dev/null | grep -vE '/\.cache/|/logs?/' | head -n 60 | while read -r f; do ls -la --time-style=long-iso "$f"; done
} > "$OUT" 2>&1

echo "Diagnose geschrieben: $OUT ($(wc -l < "$OUT") Zeilen)"
if [ "$PUSH" = 1 ]; then
  # Datei als eigenständigen Commit auf den Branch "diag" pushen, ohne den Arbeitsbranch anzufassen
  if blob="$(git -C "$ROOT" hash-object -w "$OUT")" \
     && tree="$(printf '100644 blob %s\t%s\n' "$blob" "$(basename "$OUT")" | git -C "$ROOT" mktree)" \
     && commit="$(git -C "$ROOT" commit-tree "$tree" -m "Diagnose $STAMP von $(hostname)")" \
     && git -C "$ROOT" push -q -f origin "$commit:refs/heads/diag" 2>/tmp/bt_diag_push.err; then
    echo "Gepusht nach origin/diag (Commit ${commit:0:8}). Fertig, nichts weiter nötig."
  else
    echo "Push nach origin/diag fehlgeschlagen: $(cat /tmp/bt_diag_push.err 2>/dev/null | tail -n 2)"
    echo "Dann bitte den Inhalt der Datei unverändert weitergeben:"; echo "  cat $OUT"
  fi
else
  cat "$OUT"
fi
