#!/usr/bin/env bash
# Musik vom Handy an den Pi schicken: Spotify Connect (librespot aus dem raspotify-Paket) und AirPlay
# (shairport-sync). Der Pi erscheint in der Spotify-App als Gerät "KITT-Cart" (Spotify Premium nötig) und
# auf iPhone/iPad/Mac als AirPlay-Lautsprecher "KITT-Cart" (SoundCloud, YouTube, alles was AirPlay kann).
# Android ohne AirPlay: Bluetooth-Senke über scripts/setup_bluetooth.sh (dann "KITT-Cart" als
# Bluetooth-Lautsprecher wählen). Einen echten Chromecast-Empfänger gibt es für den Pi nicht (Google-Protokoll).
#
# Beide laufen als systemd --user-Dienste über PipeWire (Standard-Sink = Bose-Headset oder Klinke), damit die
# Visualizer mit [capture].source = "playback" die Musik sehen. Der Musik-Drehknopf regelt nur mpv; Spotify- und
# AirPlay-Lautstärke kommen vom Handy.
#
#   scripts/setup_cast.sh                 einrichten (Spotify + AirPlay), idempotent
#   scripts/setup_cast.sh --name NAME     anderer Gerätename (Standard KITT-Cart)
#   scripts/setup_cast.sh --no-airplay | --no-spotify
#   scripts/setup_cast.sh --status        Dienste und Audio prüfen
#   scripts/setup_cast.sh --undo          Dienste entfernen (Pakete bleiben)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
NAME="KITT-Cart"
DO_SPOTIFY=1
DO_AIRPLAY=1
MODE="setup"
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift ;;
    --no-airplay) DO_AIRPLAY=0 ;;
    --no-spotify) DO_SPOTIFY=0 ;;
    --status) MODE="status" ;;
    --undo) MODE="undo" ;;
    *) echo "unbekannte Option: $1"; exit 2 ;;
  esac
  shift
done
UNIT_DIR="$HOME/.config/systemd/user"
SPOT_UNIT="$UNIT_DIR/kitt-spotify.service"
AIR_UNIT="$UNIT_DIR/kitt-airplay.service"
AIR_CONF="$HOME/.config/shairport-sync.conf"
mkdir -p "$UNIT_DIR" "$ROOT/logs"

status() {
  echo "== Dienste =="
  for u in kitt-spotify kitt-airplay; do
    if [ -f "$UNIT_DIR/$u.service" ]; then
      printf "  %-14s %s\n" "$u" "$(systemctl --user is-active "$u.service" 2>/dev/null)"
    else
      printf "  %-14s nicht eingerichtet\n" "$u"
    fi
  done
  echo "== Programme =="
  printf "  librespot:      %s\n" "$(command -v librespot || echo fehlt)"
  printf "  shairport-sync: %s\n" "$(command -v shairport-sync || echo fehlt)"
  echo "== Standard-Sink (dort landet die Musik) =="
  wpctl status 2>/dev/null | sed -n '/Sinks:/,/Sources:/p' | grep -E "^\s*│?\s*\*" | sed 's/^/  /' || echo "  (wpctl nicht verfügbar)"
  echo "== Laufende Streams =="
  wpctl status 2>/dev/null | sed -n '/Streams:/,/Video/p' | grep -iE "librespot|shairport|spotify|airplay" | sed 's/^/  /' || true
  echo "== Letzte Zeilen =="
  journalctl --user -u kitt-spotify -u kitt-airplay -n 8 --no-pager 2>/dev/null | sed 's/^/  /'
  [ -f "$ROOT/logs/now_playing.txt" ] && echo "== Spotify spielt ==" && sed 's/^/  /' "$ROOT/logs/now_playing.txt"
}

if [ "$MODE" = "status" ]; then status; exit 0; fi

if [ "$MODE" = "undo" ]; then
  systemctl --user disable --now kitt-spotify.service kitt-airplay.service 2>/dev/null
  rm -f "$SPOT_UNIT" "$AIR_UNIT" "$AIR_CONF"
  systemctl --user daemon-reload
  echo "Dienste entfernt. Pakete bleiben (sudo apt-get remove raspotify shairport-sync zum Löschen)."
  exit 0
fi

echo "== Grundpakete (PipeWire-Brücken, Avahi für die Gerätesuche) =="
sudo apt-get install -y -qq pipewire-alsa pipewire-pulse avahi-daemon curl 2>&1 | tail -1
sudo systemctl enable --now avahi-daemon >/dev/null 2>&1

# -- Spotify Connect ------------------------------------------------------------------------------------------
if [ "$DO_SPOTIFY" = 1 ]; then
  echo "== Spotify Connect (librespot aus dem raspotify-Paket) =="
  if ! command -v librespot >/dev/null; then
    KEY=/usr/share/keyrings/raspotify-archive-keyring.asc
    if [ ! -s "$KEY" ]; then
      curl -fsSL https://dtcooper.github.io/raspotify/key.asc | sudo tee "$KEY" >/dev/null || echo "FEHLER: Schlüssel nicht geladen (Netz?)"
    fi
    echo "deb [signed-by=$KEY] https://dtcooper.github.io/raspotify raspotify main" | sudo tee /etc/apt/sources.list.d/raspotify.list >/dev/null
    sudo apt-get update -qq 2>&1 | tail -1
    sudo apt-get install -y -qq raspotify 2>&1 | tail -1
  fi
  if command -v librespot >/dev/null; then
    # Das Paket bringt einen Systemdienst (Benutzer raspotify, reines ALSA) mit, der nicht an unser PipeWire kommt:
    # aus, stattdessen unser Benutzerdienst.
    sudo systemctl disable --now raspotify.service >/dev/null 2>&1
    BACKEND="alsa"
    if librespot --backend ? 2>&1 | grep -qi pulseaudio; then BACKEND="pulseaudio"; fi
    cat > "$SPOT_UNIT" <<UNIT
[Unit]
Description=KITT Spotify Connect (librespot) "$NAME"
After=pipewire.service pipewire-pulse.service wireplumber.service network-online.target
Wants=pipewire.service pipewire-pulse.service

[Service]
ExecStart=/usr/bin/librespot --name "$NAME" --backend $BACKEND --bitrate 320 --initial-volume 75 \\
  --enable-volume-normalisation --device-type speaker --cache %h/.cache/librespot \\
  --onevent $ROOT/scripts/spotify_event.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
    chmod +x "$ROOT/scripts/spotify_event.sh" 2>/dev/null
    systemctl --user daemon-reload
    systemctl --user enable --now kitt-spotify.service && echo "  kitt-spotify läuft (Backend $BACKEND)"
  else
    echo "  librespot fehlt, Spotify Connect übersprungen."
  fi
fi

# -- AirPlay ----------------------------------------------------------------------------------------------------
if [ "$DO_AIRPLAY" = 1 ]; then
  echo "== AirPlay (shairport-sync) =="
  command -v shairport-sync >/dev/null || sudo apt-get install -y -qq shairport-sync 2>&1 | tail -1
  if command -v shairport-sync >/dev/null; then
    sudo systemctl disable --now shairport-sync.service >/dev/null 2>&1   # Systemdienst (ALSA, ohne PipeWire-Zugriff) aus
    OUT="alsa"
    if shairport-sync -V 2>/dev/null | grep -qE "(^|-)pa(-|$)"; then OUT="pa"; fi
    cat > "$AIR_CONF" <<CONF
// KITT-Cart AirPlay-Empfänger (scripts/setup_cast.sh). Ausgabe über PipeWire (PulseAudio-Brücke).
general = {
  name = "$NAME";
  output_backend = "$OUT";
  volume_range_db = 50;
  ignore_volume_control = "no";
};
sessioncontrol = {
  allow_session_interruption = "yes";
  session_timeout = 20;
};
CONF
    cat > "$AIR_UNIT" <<UNIT
[Unit]
Description=KITT AirPlay-Empfänger (shairport-sync) "$NAME"
After=pipewire.service pipewire-pulse.service wireplumber.service avahi-daemon.service network-online.target
Wants=pipewire.service pipewire-pulse.service

[Service]
ExecStart=/usr/bin/shairport-sync -c $AIR_CONF
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable --now kitt-airplay.service && echo "  kitt-airplay läuft (Ausgabe $OUT)"
  else
    echo "  shairport-sync fehlt, AirPlay übersprungen."
  fi
fi

# Benutzerdienste auch ohne Anmeldung starten (Pi bootet ohne Login in den Launcher)
loginctl enable-linger "$(whoami)" 2>/dev/null
sleep 2
status
cat <<TXT

Fertig. Handy ins selbe WLAN wie der Pi:
  Spotify:  Wiedergabe starten, "Geräte" (Lautsprecher-Symbol) -> "$NAME". Braucht Spotify Premium.
  AirPlay:  iPhone/iPad/Mac: Kontrollzentrum oder AirPlay-Symbol in der App -> "$NAME" (SoundCloud, YouTube, alles).
  Android:  SoundCloud kann kein AirPlay. Bluetooth: scripts/setup_bluetooth.sh, dann "$NAME" als Lautsprecher wählen.
Die Visualizer sehen die Musik über [capture].source = "playback" (config/audio.toml). Spotify-Titel: logs/now_playing.txt.
TXT
