#!/usr/bin/env bash
# Audio-Geräte analysieren und Mikrofon testen (Phase 4). Rein lesend, außer einer 3-s-Aufnahme nach /tmp.
#   scripts/audio_check.sh            Übersicht + Mikrofontest mit der Standardquelle
#   scripts/audio_check.sh <target>   Mikrofontest mit PipeWire-Node-Name/-ID (wpctl status)
set -uo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
target="${1:-}"
sec() { printf '\n== %s ==\n' "$1"; }

sec "Backend"
pactl info 2>/dev/null | grep -E "Server Name|Server Version|Default Sink|Default Source|Sample Spec" || echo "pactl nicht verfügbar"
pw-cli info 0 2>/dev/null | grep -E "clock.rate|clock.quantum\"" | sed 's/^\s*//'

sec "PipeWire-Geräte (wpctl status)"
wpctl status 2>/dev/null | sed -n '/^Audio/,/^Video/p' | grep -vE "^\s*$"

sec "ALSA-Geräte"
echo "-- Aufnahme --"; arecord -l 2>&1 | grep -E "^card|^\*\*" ; echo "-- Wiedergabe --"; aplay -l 2>&1 | grep -E "^card|^\*\*"
echo "-- USB --"; lsusb | grep -viE "hub|keyboard|mouse" || echo "(nur Hub/Tastatur/Maus)"

sec "pipewire-alsa (ALSA default -> PipeWire)"
dpkg-query -W -f='${Status}\n' pipewire-alsa 2>/dev/null | grep -q "install ok installed" && echo "installiert" || echo "FEHLT: sudo apt-get install -y pipewire-alsa"

sec "Mikrofontest (3 s)"
src="$(pactl get-default-source 2>/dev/null || true)"
if [ -z "$src" ] || [ "$src" = "auto_null" ]; then
  echo "Keine Aufnahmequelle in PipeWire. Mikrofon oder USB-Soundkarte anschließen, dann erneut prüfen."
  echo "  (wpctl status zeigt dann unter Sources den neuen Eintrag)"
  exit 2
fi
echo "Quelle: ${target:-$src (Standard)}"
raw=/tmp/kitt_mictest.raw
rm -f "$raw"
cmd=(pw-record --raw --rate 48000 --channels 1 --format s16)
[ -n "$target" ] && cmd+=(--target "$target")
echo "Bitte jetzt ins Mikrofon sprechen oder klatschen ..."
if ! timeout 4 "${cmd[@]}" "$raw" 2>/tmp/kitt_mictest.err; then
  # pw-record ohne --raw (ältere Versionen) oder arecord als Fallback
  if ! timeout 4 arecord -q -D default -f S16_LE -r 48000 -c 1 -t raw -d 3 "$raw" 2>>/tmp/kitt_mictest.err; then
    echo "Aufnahme fehlgeschlagen:"; tail -3 /tmp/kitt_mictest.err; exit 3
  fi
  echo "(arecord-Fallback benutzt; pw-record meldete: $(tail -1 /tmp/kitt_mictest.err))"
fi
python3 - "$raw" <<'PY'
import sys, numpy as np
d = np.fromfile(sys.argv[1], dtype=np.int16).astype(np.float32) / 32768.0
if len(d) < 4800:
    print(f"Zu wenig Daten ({len(d)} Samples)"); sys.exit(3)
rms = float(np.sqrt(np.mean(d*d))); peak = float(np.abs(d).max())
import math
db = 20*math.log10(rms+1e-9)
print(f"Samples: {len(d)}  Dauer: {len(d)/48000:.1f} s  RMS: {rms:.4f} ({db:.1f} dBFS)  Peak: {peak:.3f}")
if rms < 0.001: print("Ergebnis: STILL. Mikrofon stumm, falsches Gerät oder Pegel zu niedrig (wpctl set-volume <id> 1.0).")
elif peak > 0.98: print("Ergebnis: ÜBERSTEUERT. Eingangspegel senken.")
else: print("Ergebnis: OK. Signal vorhanden.")
PY
echo
echo "Config: config/audio.toml  [capture] target = \"${target}\"  (leer = Standardquelle)"
