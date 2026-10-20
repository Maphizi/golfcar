#!/usr/bin/env bash
# Kompakte Diagnose für HAL 3000 und die Musikanalyse (eine Ausgabe, ca. 25 Zeilen):
# Standard-Sink/-Quelle, Bluetooth-Profil, ob der Monitor des Sinks (Musik) und das Mikrofon Daten
# liefern, und die letzten Audio-Zeilen aus den Logs.
#   scripts/hal_audio_check.sh
set -uo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sec() { printf '\n== %s ==\n' "$1"; }
name_of() { wpctl inspect "$1" 2>/dev/null | grep -m1 "node.name" | sed 's/.*= *"\(.*\)"/\1/'; }
sec "Standardgeräte"
echo "Sink:   $(name_of @DEFAULT_AUDIO_SINK@)"
echo "Quelle: $(name_of @DEFAULT_AUDIO_SOURCE@)"
sec "Bluetooth (Profil)"
for id in $(wpctl status 2>/dev/null | sed -n '/Devices:/,/^$/p' | grep -iE "bluez|bose|headset" | grep -oE "^[ │]*[0-9]+" | tr -d ' │'); do
  wpctl inspect "$id" 2>/dev/null | grep -E "device.description|device.profile.name|api.bluez5.profile" | sed 's/^\s*//'
done
wpctl status 2>/dev/null | sed -n '/Sources:/,/^$/p' | grep -iE "bluez" | sed 's/^/Quelle: /'
sec "WirePlumber: A2DP-Sperre"
ls "$HOME/.config/wireplumber/wireplumber.conf.d/"50-kitt-bluez-no-autoswitch.conf 2>/dev/null && echo "aktiv" || echo "nicht eingerichtet (scripts/bt_a2dp_lock.sh)"
sec "Monitor des Sinks (Musik, 3 s)"
sink="$(name_of @DEFAULT_AUDIO_SINK@)"
err=/tmp/kitt_moncheck.err
n=$(timeout 3 pw-record --raw --rate 48000 --channels 1 --format s16 -P '{ stream.capture.sink = true }' ${sink:+--target "$sink"} - 2>"$err" | wc -c)
echo "Bytes: $n (erwartet ca. 288000 bei 3 s)"; [ "$n" -lt 100000 ] && { echo "Fehler:"; tail -3 "$err"; }
sec "Mikrofon (3 s, Standardquelle)"
n=$(timeout 3 pw-record --raw --rate 48000 --channels 1 --format s16 - 2>"$err" | wc -c)
echo "Bytes: $n"; [ "$n" -lt 100000 ] && { echo "Fehler:"; tail -3 "$err"; }
sec "Logs (Audio-Capture, Sprechmodus)"
for f in "$ROOT/logs/hal.log" "$ROOT/logs/viz_hal.log"; do
  [ -f "$f" ] && { echo "-- $(basename "$f")"; grep -aE "Audio-Capture|endete nach|Sprechmodus|Bluetooth|Standardquelle" "$f" | tail -6; }
done
echo
echo "Modus laut Launcher: $(python3 -c "import json;print(json.load(open('$XDG_RUNTIME_DIR/kitt-launcher.state')).get('mode'))" 2>/dev/null || echo '?')"
