#!/usr/bin/env bash
# Musik über mpv mit Steuer-Socket, damit der Drehknopf die Musiklautstärke regeln kann.
#   scripts/music.sh [Ordner-oder-Datei-oder-URL]   (Standard: ~/Music, Zufall, Endlosschleife)
# Lautstärke-Startwert: config/settings.toml [music].start_percent (Standard 70).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$HOME/Music}"
SOCK="/tmp/mpv.sock"
START="$(python3 -c "import tomllib;print(tomllib.load(open('$ROOT/config/settings.toml','rb')).get('music',{}).get('start_percent',70))" 2>/dev/null || echo 70)"
pkill -x mpv 2>/dev/null
rm -f "$SOCK"
exec mpv --no-video --really-quiet --loop-playlist=inf --shuffle \
  --volume="$START" --input-ipc-server="$SOCK" "$SRC"
