#!/usr/bin/env bash
# KITT-Cart auf einem frisch aufgesetzten Raspberry Pi OS (64-bit, Trixie, Desktop) in EINEM Durchlauf einrichten.
# Idempotent: kann abgebrochen und erneut gestartet werden, fertige Schritte werden übersprungen oder sind harmlos.
#
#   scripts/install.sh                 Grundausstattung: Launcher, Eingabe, Bluetooth-Audio, Musik vom Handy, Stimmen, Autostart
#   scripts/install.sh --kitt          zusätzlich Sprachassistent (whisper.cpp + llama.cpp, ca. 5 GB, 30 min)
#   scripts/install.sh --retropie      zusätzlich RetroPie (aus dem Quellcode, 45-90 min)
#   scripts/install.sh --tailscale     zusätzlich Tailscale (Fernzugriff), danach:  sudo tailscale up
#   scripts/install.sh --wifi-5ghz     Heim-WLAN-Profil fest auf 5 GHz (Bluetooth-Schonung)
#   scripts/install.sh --all           alles oben
#   scripts/install.sh --no-upgrade    ohne apt full-upgrade
# Protokoll: logs/install.log. Vorbereitung und Handgriffe danach: docs/NEUINSTALLATION.md
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs
LOG="$ROOT/logs/install.log"
exec > >(tee -a "$LOG") 2>&1

KITT=0; RETROPIE=0; TAILSCALE=0; WIFI5=0; UPGRADE=1
for a in "$@"; do
  case "$a" in
    --kitt) KITT=1 ;; --retropie) RETROPIE=1 ;; --tailscale) TAILSCALE=1 ;; --wifi-5ghz) WIFI5=1 ;;
    --all) KITT=1; RETROPIE=1; TAILSCALE=1; WIFI5=1 ;; --no-upgrade) UPGRADE=0 ;;
    *) echo "unbekannte Option: $a"; exit 2 ;;
  esac
done
T0=$(date +%s)
step() { printf '\n\033[1m== [%s] %s ==\033[0m\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { echo; echo "FEHLER in Schritt: $*"; echo "Protokoll: $LOG. Nach Behebung einfach erneut starten: scripts/install.sh $*"; exit 1; }

step "Prüfungen"
. /etc/os-release
echo "  $PRETTY_NAME, Benutzer $USER, Projekt $ROOT"
[ "${VERSION_CODENAME:-}" = "trixie" ] || echo "  HINWEIS: erwartet wird Raspberry Pi OS Trixie (Debian 13), hier: ${VERSION_CODENAME:-?}"
[ "$(id -u)" != 0 ] || { echo "  Bitte als normaler Benutzer starten, nicht als root."; exit 1; }
sudo -n true 2>/dev/null || { echo "  sudo braucht hier ein Passwort, bitte einmal eingeben:"; sudo true || exit 1; }
getent group input >/dev/null || sudo groupadd input

if [ "$UPGRADE" = 1 ]; then
  step "System aktualisieren (apt update + full-upgrade)"
  sudo apt-get update -qq || fail "apt update (Internet?)"
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq full-upgrade || fail "apt full-upgrade"
fi

step "Grundpakete, Python-Umgebung, Gruppen (setup_phase2.sh)"
scripts/setup_phase2.sh || fail "setup_phase2.sh"

step "Werkzeuge: git, mpv, yt-dlp, evtest, curl"
sudo apt-get install -y -qq git mpv yt-dlp evtest curl 2>&1 | tail -1 || fail "Werkzeuge"

step "/dev/uinput für das D-Pad (udev-Regel + Modul)"
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' | sudo tee /etc/udev/rules.d/99-uinput.rules >/dev/null
echo uinput | sudo tee /etc/modules-load.d/uinput.conf >/dev/null
sudo modprobe uinput 2>/dev/null; sudo udevadm control --reload-rules; sudo udevadm trigger --name-match=uinput 2>/dev/null
ls -la /dev/uinput 2>/dev/null | sed 's/^/  /'

step "Bluetooth-Audio (A2DP, SBC in hoher Qualität, Profilsperre)"
scripts/setup_bluetooth.sh KITT-Cart || fail "setup_bluetooth.sh"
scripts/bt_a2dp_lock.sh | tail -3

step "Musik vom Handy: Spotify Connect + AirPlay (setup_cast.sh)"
scripts/setup_cast.sh || fail "setup_cast.sh"

step "Stimmen (Piper) und Ansagen"
scripts/setup_phase7.sh || fail "setup_phase7.sh"
[ -x scripts/announce_build.sh ] && { scripts/announce_build.sh 2>&1 | tail -2; }

if [ "$KITT" = 1 ]; then
  step "Sprachassistent: whisper.cpp (setup_phase5.sh)"
  scripts/setup_phase5.sh || fail "setup_phase5.sh"
  step "Sprachassistent: llama.cpp + Modelle (setup_phase6.sh)"
  scripts/setup_phase6.sh || fail "setup_phase6.sh"
fi

if [ "$RETROPIE" = 1 ]; then
  step "RetroPie aus dem Quellcode (setup_phase3.sh, 45-90 min)"
  scripts/setup_phase3.sh || fail "setup_phase3.sh"
fi

if [ "$TAILSCALE" = 1 ] && ! command -v tailscale >/dev/null; then
  step "Tailscale (Paketquelle von pkgs.tailscale.com)"
  curl -fsSL "https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg" | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null \
    && curl -fsSL "https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list" | sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null \
    && sudo apt-get update -qq && sudo apt-get install -y -qq tailscale 2>&1 | tail -1 || fail "Tailscale"
  echo "  Anmelden nach der Installation:  sudo tailscale up"
fi

if [ "$WIFI5" = 1 ]; then
  step "Heim-WLAN fest auf 5 GHz"
  con="$(nmcli -t -f NAME,TYPE,DEVICE connection show --active 2>/dev/null | awk -F: '$2=="802-11-wireless"{print $1; exit}')"
  if [ -n "$con" ]; then sudo nmcli connection modify "$con" 802-11-wireless.band a && echo "  $con: nur noch 5 GHz (wirksam beim nächsten Verbinden)"; else echo "  kein aktives WLAN-Profil gefunden, übersprungen"; fi
fi

step "Klänge und Bild-Cache"
.venv/bin/python scripts/sfx_fetch.py 2>&1 | tail -1
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python scripts/warm_cache.py 2>&1 | tail -1

step "Autostart der Cart-Sitzung (autostart_enable.sh)"
scripts/autostart_enable.sh || fail "autostart_enable.sh"

step "Fertig nach $(( ($(date +%s) - T0) / 60 )) min"
cat <<EOF
  Jetzt noch von Hand (siehe docs/NEUINSTALLATION.md):
   1. Neustart:  sudo reboot   (danach startet der Cart von selbst)
   2. Soundboks koppeln (Box in den Kopplungsmodus):  bluetoothctl  ->  scan on, pair <MAC>, trust <MAC>, connect <MAC>
   3. LED-Controller: Adresse in config/wled.toml prüfen, Test:  scripts/wledctl.py set --col 255,0,0
   4. Spotify-App am Handy: Gerät "KITT-Cart" wählen (Premium nötig). AirPlay: "KITT-Cart".
   5. Kein 2,4-GHz-Hotspot neben dem Cart, solange Bluetooth spielt. Keine Pakete durch den Bot ohne Freigabe.
  Später aktualisieren:  scripts/update.sh
EOF
