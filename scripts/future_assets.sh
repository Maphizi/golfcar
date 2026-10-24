#!/usr/bin/env bash
# Bildmaterial des Themas ZURÜCK IN DIE ZUKUNFT aus assets/future/raw/*.png (vom Bot erzeugt, Prompts in
# docs/future_plan.md) in die Szenenbilder und Atlanten unter assets/future/ schneiden. Nach neuen Rohbildern erneut ausführen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
RAW=assets/future/raw
OUT=assets/future
T="$PY scripts/trip_assets.py"
mkdir -p "$OUT"
f() { [ -s "$RAW/$1.png" ] && echo "$RAW/$1.png" || { [ -s "$RAW/$1.webp" ] && echo "$RAW/$1.webp"; }; }
plate() { s=$(f "$1"); [ -n "$s" ] && $T plate "$OUT/$2" "$s" 2>/dev/null | tail -1 || echo "  fehlt: $1"; }
slice() { s=$(f "$1"); [ -n "$s" ] && $T slice "$OUT/$2" "$s" $3 $4 $5 2>/dev/null | tail -1 || echo "  fehlt: $1"; }
echo "== Zeitsprung =="
plate timejump_cockpit timejump_cockpit.png
for e in 1885 1955 1985 2015; do plate timejump_$e timejump_$e.png; done
slice timejump_traffic timejump_traffic.png 8 4 192
echo "== Fluxkompensator =="
plate flux_scene flux_scene.png
slice flux_objects flux_objects.png 6 4 192
echo "== Uhrturm =="
slice clocktower_figures clocktower_figures.png 8 3 192   # Professor/Zeitmaschine für Paradoxon und Almanach
$PY scripts/clocktower_assets.py 2>/dev/null | grep -v "^pygame\|^Hello"   # neuer Uhrturm (Runde 3)
echo "== Almanach =="
plate almanac_scene almanac_scene.png
s=$(f almanac_symbols); [ -n "$s" ] && $PY - "$s" "$OUT/almanac_symbols.png" <<'PYEOF' 2>/dev/null
import sys, pygame
pygame.init()
im = pygame.image.load(sys.argv[1]); im = pygame.transform.smoothscale(im, (1152, 768)); pygame.image.save(im, sys.argv[2]); print("Symbole", im.get_size())
PYEOF
echo "== Marktplatz =="
for e in 1885 1955 1985 2015; do plate square_$e square_$e.png; done
slice square_particles square_particles.png 8 3 160
echo "== Paradoxon =="
plate paradox_scene paradox_scene.png
slice paradox_intruders paradox_intruders.png 4 3 256
ls -la "$OUT" | grep -v raw
