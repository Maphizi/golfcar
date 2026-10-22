#!/usr/bin/env bash
# Bildmaterial der Themen-Slotmaschinen aus assets/slots/raw/*.png (vom Bot, Prompts in docs/slots_plan.md):
# Rahmen -> assets/slots/<name>.png 1920x1080, Symbolbögen -> assets/slots/<name>.png 768x510 (3x3 à 256x170 wie die
# Space-Bögen). Nach neuen Rohbildern erneut ausführen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
RAW=assets/slots/raw
OUT=assets/slots
f() { [ -s "$RAW/$1.png" ] && echo "$RAW/$1.png" || { [ -s "$RAW/$1.webp" ] && echo "$RAW/$1.webp"; }; }
scale() { s=$(f "$1"); [ -n "$s" ] && $PY - "$s" "$OUT/$1.png" "$2" "$3" <<'PYEOF' 2>/dev/null || echo "  fehlt: $1"
import sys, pygame
pygame.init()
im = pygame.image.load(sys.argv[1]); im = pygame.transform.smoothscale(im, (int(sys.argv[3]), int(sys.argv[4])))
pygame.image.save(im, sys.argv[2]); print(sys.argv[2], im.get_size())
PYEOF
}
for n in forest_frame cyber_frame future_frame space_frame; do scale $n 1920 1080; done
for n in forest_animals forest_magic cyber_konzern cyber_netzgeister future_1885 future_2015; do scale $n 768 510; done
ls -la "$OUT" | grep -v raw
