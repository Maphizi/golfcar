#!/usr/bin/env bash
# Bildmaterial der Themen-Slotmaschinen aus assets/slots/raw/*.png (vom Bot, Prompts in docs/slots_plan.md):
# Rahmen -> assets/slots/<name>.png 1920x1080, Symbolbögen -> assets/slots/<name>.png 768x510 (3x3 à 256x170 wie die
# Space-Bögen). Die drei schon vorhandenen Themenbögen (assets/forestslots/symbols.png, assets/cyber/cyberslots_symbols.png,
# assets/future/almanac_symbols.png, 1152x768) werden ebenfalls nach assets/slots/ auf 768x510 kopiert.
# Nach neuen Rohbildern erneut ausführen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
export PYGAME_HIDE_SUPPORT_PROMPT=1
RAW=assets/slots/raw
OUT=assets/slots
f() { [ -s "$RAW/$1.png" ] && echo "$RAW/$1.png" || { [ -s "$RAW/$1.webp" ] && echo "$RAW/$1.webp"; }; }
# scale_file QUELLE ZIEL BREITE HOEHE
scale_file() { $PY - "$1" "$2" "$3" "$4" <<'PYEOF' 2>/dev/null || echo "  Fehler: $1"
import sys, pygame
pygame.init()
im = pygame.image.load(sys.argv[1]); im = pygame.transform.smoothscale(im, (int(sys.argv[3]), int(sys.argv[4])))
pygame.image.save(im, sys.argv[2]); print(sys.argv[2], im.get_size())
PYEOF
}
scale() { s=$(f "$1"); [ -n "$s" ] && scale_file "$s" "$OUT/$1.png" "$2" "$3" || echo "  fehlt: $RAW/$1.png"; }
for n in forest_frame cyber_frame future_frame space_frame; do scale $n 1920 1080; done
$PY scripts/frame_clean.py "$OUT/future_frame.png"      # Hoverboard aus dem Walzenfeld
for n in forest_animals forest_magic cyber_konzern cyber_netzgeister future_1885 future_2015; do scale $n 768 510; done
# vorhandene Themenbögen (erster Automat je Thema) auf das Space-Format
for pair in assets/forestslots/symbols.png:forest assets/cyber/cyberslots_symbols.png:cyberslots_symbols assets/future/almanac_symbols.png:almanac_symbols; do
    src=${pair%%:*}; dst=${pair##*:}
    [ -s "$src" ] && scale_file "$src" "$OUT/$dst.png" 768 510 || echo "  fehlt: $src"
done
ls -la "$OUT" | grep -v raw
