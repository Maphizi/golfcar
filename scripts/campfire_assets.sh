#!/usr/bin/env bash
# Bildmaterial des Lagerfeuers aus assets/campfire/raw/*.png (vom Bot, Prompts in docs/campfire_plan.md) in die
# Atlanten unter assets/campfire/ schneiden. Nach neuen Rohbildern erneut ausführen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
RAW=assets/campfire/raw
OUT=assets/campfire
T="$PY scripts/trip_assets.py"
f() { [ -s "$RAW/$1.png" ] && echo "$RAW/$1.png" || { [ -s "$RAW/$1.webp" ] && echo "$RAW/$1.webp"; }; }
plate() { s=$(f "$1"); [ -n "$s" ] && $T plate "$OUT/$2" "$s" 2>/dev/null | tail -1 || echo "  fehlt: $1"; }
cut() { s=$(f "$1"); [ -n "$s" ] && $T cut "$OUT/$2" "$s" $3 $4 $5 $6 $7 $8 2>/dev/null | tail -1 || echo "  fehlt: $1"; }
plate campfire_scene scene.png
# Flammenbögen: ganzer Zellenausschnitt (128x256, Fußpunkt unten), Alpha aus der Helligkeit
for n in small mid big blue; do cut campfire_flames_$n flames_$n.png 8 4 128 256 0 glow; done
cut campfire_sparks sparks.png 8 2 128 128 1 glow
cut campfire_items items.png 8 2 192 192 1 fill
