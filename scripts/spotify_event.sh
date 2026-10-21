#!/usr/bin/env bash
# Wird von librespot (--onevent) bei jedem Ereignis aufgerufen: schreibt den laufenden Titel nach
# logs/now_playing.txt und ein Protokoll nach logs/spotify.log. Umgebungsvariablen je nach librespot-Version:
# PLAYER_EVENT (track_changed, playing, paused, stopped, session_connected, ...), NAME, ARTISTS, ALBUM, TRACK_ID.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/logs"
EV="${PLAYER_EVENT:-}"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"
case "$EV" in
  track_changed|playing|preloading)
    if [ -n "${NAME:-}" ]; then
      printf '%s\n%s\n%s\n' "${NAME}" "${ARTISTS:-}" "${ALBUM:-}" > "$ROOT/logs/now_playing.txt"
      [ "$EV" = "track_changed" ] && echo "$NOW  ${ARTISTS:-?} - ${NAME}" >> "$ROOT/logs/spotify.log"
    elif [ -n "${TRACK_ID:-}" ] && [ "$EV" = "track_changed" ]; then
      echo "$NOW  Track $TRACK_ID" >> "$ROOT/logs/spotify.log"
    fi
    ;;
  stopped|session_disconnected)
    rm -f "$ROOT/logs/now_playing.txt"
    echo "$NOW  $EV" >> "$ROOT/logs/spotify.log"
    ;;
  session_connected|session_client_changed)
    echo "$NOW  $EV ${CONNECTION_ID:-} ${USER_NAME:-}" >> "$ROOT/logs/spotify.log"
    ;;
esac
exit 0
