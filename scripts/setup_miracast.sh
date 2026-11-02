#!/usr/bin/env bash
# Miracast: den Bildschirm des Pi drahtlos an einen Miracast-Empfänger schicken (z. B. "HD Wireless Screen Mirroring",
# 530E1F_P2P). Wi-Fi Direct über NetworkManager NEBEN dem normalen WLAN; Vodafone/Hotspot und Tailscale bleiben
# verbunden. Sender: scripts/miracast.py, Einstellungen: config/settings.toml [miracast].
#
#   scripts/setup_miracast.sh             Prüfen (ändert nichts): WLAN-Chip, NetworkManager, Tailscale, Programme,
#                                          Empfänger in der Nähe suchen. Ausgabe zum Weitergeben.
#   scripts/setup_miracast.sh --install   wf-recorder + ffmpeg installieren, Dienst kitt-miracast anlegen (nicht aktiv)
#   scripts/setup_miracast.sh --test [S]  ein Versuch, S Sekunden senden (Standard 60). Sicherheitsnetz: nach 5 min
#                                          baut ein Timer Wi-Fi Direct ab und verbindet wlan0 neu, falls etwas hängt.
#   scripts/setup_miracast.sh --enable    Autostart an (Dienst sucht den Empfänger, verbindet, bei Abbruch neu)
#   scripts/setup_miracast.sh --disable   Autostart aus, Verbindung trennen
#   scripts/setup_miracast.sh --status    Dienst, letzte Meldungen, Verbindungen
#   scripts/setup_miracast.sh --undo      Dienst und Wi-Fi-Direct-Profil entfernen (Pakete bleiben)
#
# Hinweis: Miracast hat 50-150 ms Verzögerung, bei Retro-Spielen spürbar. Der Pi 5 kodiert in Software (libx264),
# das kostet etwa einen CPU-Kern bei 720p30.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="check"
SECS=60
while [ $# -gt 0 ]; do
  case "$1" in
    --install) MODE="install" ;;
    --test) MODE="test"; [ "${2:-}" ] && [ "${2#-}" = "$2" ] && { SECS="$2"; shift; } ;;
    --enable) MODE="enable" ;;
    --disable) MODE="disable" ;;
    --status) MODE="status" ;;
    --undo) MODE="undo" ;;
    --check) MODE="check" ;;
    *) echo "unbekannte Option: $1"; exit 2 ;;
  esac
  shift
done
WIFI="$(python3 -c "import tomllib;print(tomllib.load(open('$ROOT/config/settings.toml','rb')).get('miracast',{}).get('wifi','wlan0'))" 2>/dev/null || echo wlan0)"
UNIT=/etc/systemd/system/kitt-miracast.service
NMCONF=/etc/NetworkManager/conf.d/90-kitt-miracast.conf        # Gruppenschnittstellen p2p-wlan0-N gehören miracast.py
IW="$(command -v iw || echo /usr/sbin/iw)"                    # liegt in /usr/sbin, nicht im PATH normaler Benutzer
mkdir -p "$ROOT/logs"

check() {
  echo "== System =="
  echo "  $(uname -r), $(. /etc/os-release; echo "$PRETTY_NAME"), NetworkManager $(nmcli --version 2>/dev/null | awk '{print $NF}')"
  echo "== WLAN (darf nie wegfallen) =="
  nmcli -f DEVICE,TYPE,STATE,CONNECTION device 2>/dev/null | sed 's/^/  /'
  echo "  Tailscale: $(ip -4 -o addr show tailscale0 2>/dev/null | awk '{print $4}' || echo -) $(tailscale status --self --peers=false 2>/dev/null | head -1)"
  echo "== Wi-Fi-Direct-Gerät =="
  if nmcli -t -f DEVICE,TYPE device | grep -q "^p2p-dev-$WIFI:wifi-p2p"; then
    echo "  p2p-dev-$WIFI vorhanden (NetworkManager kann Wi-Fi Direct)"
  else
    echo "  FEHLT: p2p-dev-$WIFI nicht in NetworkManager -> wpa_supplicant ohne P2P oder NM zu alt"
  fi
  echo "== Chip: gleichzeitige Verbindungen (iw list) =="
  phy="$($IW dev "$WIFI" info 2>/dev/null | awk '/wiphy/{print "phy"$2}')"
  combos="$($IW phy "$phy" info 2>/dev/null | grep -A6 "valid interface combinations")"
  echo "${combos:-  (iw liefert nichts)}" | head -8 | sed 's/^/  /'
  if echo "$combos" | grep -q "#channels <= 1"; then
    echo "  ACHTUNG: nur ein Kanal gleichzeitig. Wi-Fi Direct klappt nur, wenn der Empfänger den Kanal des WLANs nimmt;"
    echo "           sonst zweiter USB-WLAN-Stick für Miracast ([miracast] wifi = \"wlan1\")."
  fi
  echo "  WLAN-Kanal jetzt: $($IW dev "$WIFI" info 2>/dev/null | awk '/channel/{print $2, $3, $4}')"
  echo "== NetworkManager-Ausnahme für p2p-$WIFI-* =="
  [ -f "$NMCONF" ] && sed 's/^/  /' "$NMCONF" || echo "  noch nicht angelegt (kommt mit --install/--test)"
  echo "== Programme =="
  for p in wf-recorder ffmpeg nmcli busctl; do printf "  %-12s %s\n" "$p" "$(command -v $p || echo fehlt)"; done
  # erst ganz lesen, dann suchen: grep -q bricht die Ausgabe ab, mit pipefail sähe das wie "fehlt" aus
  enc="$(ffmpeg -hide_banner -encoders 2>/dev/null)"
  case "$enc" in *libx264*) echo "  libx264      ok" ;; *) echo "  libx264      fehlt (ffmpeg ohne x264)" ;; esac
  wf-recorder --help 2>&1 | grep -c -- "--codec" >/dev/null && echo "  wf-recorder  $(wf-recorder --version 2>&1 | head -1)"
  echo "== Bildschirm-Session =="
  pgrep -a -x labwc | head -1 | sed 's/^/  /'; ls /run/user/*/wayland-* 2>/dev/null | sed 's/^/  /'
  echo "== Empfänger in der Nähe (15 s) =="
  sudo python3 "$ROOT/scripts/miracast.py" scan 15 | sed 's/^/  /'
  echo "== Status =="
  [ -f "$ROOT/logs/miracast_status.txt" ] && sed 's/^/  /' "$ROOT/logs/miracast_status.txt" || echo "  (noch kein Versuch)"
}

nm_conf() {
  # NetworkManager soll die Wi-Fi-Direct-Gruppenschnittstelle (p2p-wlan0-N) nicht anfassen (IP macht miracast.py selbst)
  printf '%s\n' "# KITT-Cart Miracast (scripts/setup_miracast.sh): Gruppenschnittstellen verwaltet scripts/miracast.py selbst" \
    "[keyfile]" "unmanaged-devices=interface-name:p2p-$WIFI-*" | sudo tee "$NMCONF" >/dev/null
  sudo nmcli general reload conf 2>/dev/null || true
}

install_unit() {
  sudo apt-get install -y wf-recorder ffmpeg
  sed -e "s|__ROOT__|$ROOT|g" -e "s|__USER__|$(id -un)|g" "$ROOT/systemd/kitt-miracast.service" | sudo tee "$UNIT" >/dev/null
  sudo systemctl daemon-reload
  nm_conf
  echo "Dienst kitt-miracast angelegt (aus). Test: scripts/setup_miracast.sh --test, Autostart: --enable"
}

guard_on() {
  # Sicherheitsnetz: falls der Test hängt oder das WLAN verliert, nach 5 min alles zurück
  # $WIFI wird NUR neu verbunden, wenn es wirklich getrennt ist (ein "device connect" auf ein verbundenes WLAN
  # würde es kurz trennen -> Tailscale weg, der Bot verliert den Pi)
  sudo systemd-run --quiet --unit=kitt-miracast-guard --on-active=300 /bin/sh -c \
    "pkill -f 'scripts/miracast.py run'; nmcli connection down kitt-miracast 2>/dev/null; \
     nmcli -g GENERAL.STATE device show $WIFI | grep -q '^100' || nmcli device connect $WIFI" 2>/dev/null \
    && echo "Sicherheitsnetz aktiv: in 5 min wird Wi-Fi Direct getrennt und $WIFI nur bei Bedarf neu verbunden."
}
guard_off() { sudo systemctl stop kitt-miracast-guard.timer 2>/dev/null; true; }

case "$MODE" in
  check) check ;;
  install) install_unit ;;
  test)
    systemctl is-active --quiet kitt-miracast && { echo "Dienst läuft schon, erst --disable"; exit 1; }
    [ -f "$NMCONF" ] || nm_conf
    guard_off; guard_on
    echo "Test: $SECS s senden. Ausführlich: KITT_MIRACAST_DEBUG=1 davor."
    t0="$(date '+%Y-%m-%d %H:%M:%S')"
    # nur für die Testdauer genauer protokollieren (ändert keine Verbindung, danach zurück auf Standard)
    sudo nmcli general logging level DEBUG domains WIFI,SUPPLICANT 2>/dev/null
    sudo busctl set-property fi.w1.wpa_supplicant1 /fi/w1/wpa_supplicant1 fi.w1.wpa_supplicant1 DebugLevel s debug 2>/dev/null
    sudo -E python3 "$ROOT/scripts/miracast.py" run --once --seconds "$SECS"
    rc=$?
    guard_off
    sudo nmcli general logging level INFO domains DEFAULT 2>/dev/null
    sudo busctl set-property fi.w1.wpa_supplicant1 /fi/w1/wpa_supplicant1 fi.w1.wpa_supplicant1 DebugLevel s info 2>/dev/null
    echo "== Wi-Fi Direct im Systemprotokoll (NetworkManager, wpa_supplicant) =="
    sudo journalctl --no-pager -o short-precise --since "$t0" -u NetworkManager -u wpa_supplicant 2>/dev/null > "$ROOT/logs/miracast_journal.txt"
    # Kurzfassung: Verhandlung, Rolle, Gruppe, WPS, Fehler; die vielen Lausch-/Suchzeilen bleiben in der Datei
    grep -iE "go.?neg|go intent|invitation|provision|wps|group|status|kitt-miracast|p2p-dev-$WIFI\)|fail|error|timeout|reject|unknown|sending|received|beacon|p2p-$WIFI-|dhcp|role|managed" "$ROOT/logs/miracast_journal.txt" \
      | grep -viE "remain-on-channel|listen|probe re|scan res|bss |device-found|device-lost|rx frame|roc_|scan_res|supp_state|signal" \
      | sed -E 's/^[A-Za-z]+ +[0-9]+ ([0-9:.]+) [^ ]+ wpa_supplicant\[[0-9]+\]: /  \1 wpas: /; s/^[A-Za-z]+ +[0-9]+ ([0-9:.]+) [^ ]+ NetworkManager\[[0-9]+\]: /  \1 nm:   /' \
      | cut -c1-220 | head -n 160
    echo "  ($(grep -c . "$ROOT/logs/miracast_journal.txt") Zeilen gesamt in logs/miracast_journal.txt)"
    grep -i suppressed "$ROOT/logs/miracast_journal.txt" | head -2 | sed 's/^/  ACHTUNG journald: /'
    echo "== Treiber (dmesg brcmfmac, letzte Zeilen) =="
    sudo dmesg -T 2>/dev/null | grep -iE "brcmf|p2p" | tail -n 12 | sed 's/^/  /'
    echo "== WLAN-Verbindung =="
    $IW dev "$WIFI" link 2>/dev/null | grep -E "Connected|freq|SSID" | sed 's/^/  /'
    echo "Ende (Code $rc). Status: $(cat "$ROOT/logs/miracast_status.txt" 2>/dev/null)"
    nmcli -f DEVICE,STATE,CONNECTION device | grep -E "^$WIFI " | sed 's/^/WLAN: /'
    ;;
  enable) [ -f "$UNIT" ] || install_unit; sudo systemctl enable --now kitt-miracast && echo "Autostart an." ;;
  disable) sudo systemctl disable --now kitt-miracast 2>/dev/null; sudo nmcli connection down kitt-miracast 2>/dev/null; echo "Autostart aus." ;;
  status)
    echo "Dienst: $(systemctl is-enabled kitt-miracast 2>/dev/null || echo fehlt) / $(systemctl is-active kitt-miracast 2>/dev/null)"
    [ -f "$ROOT/logs/miracast_status.txt" ] && echo "Status: $(cat "$ROOT/logs/miracast_status.txt")"
    nmcli -f DEVICE,TYPE,STATE,CONNECTION device | sed 's/^/  /'
    tail -n 15 "$ROOT/logs/miracast.log" 2>/dev/null | sed 's/^/  /'
    ;;
  undo)
    sudo systemctl disable --now kitt-miracast 2>/dev/null
    sudo rm -f "$UNIT" "$NMCONF"; sudo systemctl daemon-reload; sudo nmcli general reload conf 2>/dev/null
    sudo nmcli connection delete kitt-miracast 2>/dev/null
    echo "Dienst und Profil entfernt."
    ;;
esac
