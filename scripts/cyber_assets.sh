#!/usr/bin/env bash
# Bildmaterial des Themas CYBERPUNK aus assets/cyber/raw/*.png (vom Bot erzeugt, Prompts in docs/cyber_plan.md)
# in die Atlanten unter assets/cyber/ schneiden. Nach neuen Rohbildern erneut ausführen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
RAW=assets/cyber/raw
OUT=assets/cyber
T="$PY scripts/trip_assets.py"
f() { [ -s "$RAW/$1.png" ] && echo "$RAW/$1.png" || { [ -s "$RAW/$1.webp" ] && echo "$RAW/$1.webp"; }; }
plate() { s=$(f "$1"); [ -n "$s" ] && $T plate "$OUT/$2" "$s" 2>/dev/null | tail -1 || echo "  fehlt: $1"; }
slice() { s=$(f "$1"); [ -n "$s" ] && $T slice "$OUT/$2" "$s" $3 $4 $5 2>/dev/null | tail -1 || echo "  fehlt: $1"; }
echo "== Neonfahrt =="
plate neonrace_scene neonrace_scene.png
slice neonrace_holo neonrace_holo.png 8 3 160
slice neonrace_traffic neonrace_traffic.png 8 2 192
echo "== Der Kern =="
plate core_scene core_scene.png
slice core_objects core_objects.png 6 4 192
echo "== Das Orakel =="
plate oracle_scene oracle_scene.png
slice oracle_mask oracle_mask.png 8 3 192
slice oracle_figures oracle_figures.png 8 3 192
echo "== Pachinko =="
plate cyberslots_scene cyberslots_scene.png
s=$(f cyberslots_symbols); [ -n "$s" ] && $PY - "$s" "$OUT/cyberslots_symbols.png" <<'PYEOF' 2>/dev/null
import sys, pygame
pygame.init()
im = pygame.image.load(sys.argv[1]); im = pygame.transform.smoothscale(im, (1152, 768)); pygame.image.save(im, sys.argv[2]); print("Symbole", im.get_size())
PYEOF
echo "== Dachterrasse =="
plate rooftop_scene rooftop_scene.png
slice rooftop_particles rooftop_particles.png 8 3 160
echo "== Black Ice =="
plate blackice_scene blackice_scene.png
slice blackice_daemons blackice_daemons.png 4 3 256
echo "== Runde 2 =="
slice neonrace_obstacles neonrace_obstacles.png 8 2 192
slice oracle_heads oracle_heads.png 8 3 192
for i in 1 2 3 4 5 6; do plate rooftop_light_$i rooftop_light_$i.png; done
# Bildschirminhalte: Raster mit dünnen schwarzen Stegen (geliefert 4x4) -> Kacheln erkennen, je 512x288, Atlas 4x4
s=$(f blackice_screens); [ -n "$s" ] && $PY - "$s" "$OUT/blackice_screens.png" <<'PYEOF' 2>/dev/null
import sys, pygame, numpy as np
pygame.init()
im = pygame.image.load(sys.argv[1]).convert(24)
a = pygame.surfarray.array3d(im).transpose(1, 0, 2).max(axis=2)
def bands(prof):
    gaps = [i for i, v in enumerate(prof) if v < 0.01]
    groups = []
    for g in gaps:
        if groups and g - groups[-1][-1] <= 2: groups[-1].append(g)
        else: groups.append([g])
    cuts = [0] + [int(np.mean(g)) for g in groups if len(g) >= 3 and 0 < g[0] < len(prof) - 1] + [len(prof)]
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1) if cuts[i + 1] - cuts[i] > 40]
rows = bands((a > 20).mean(axis=1)); cols = bands((a > 20).mean(axis=0))
TW, TH = 512, 288
out = pygame.Surface((TW * len(cols), TH * len(rows)))
for r, (y0, y1) in enumerate(rows):
    for c, (x0, x1) in enumerate(cols):
        tile = im.subsurface(pygame.Rect(x0 + 4, y0 + 4, x1 - x0 - 8, y1 - y0 - 8))
        out.blit(pygame.transform.smoothscale(tile, (TW, TH)), (c * TW, r * TH))
pygame.image.save(out, sys.argv[2]); print("Bildschirme", len(cols), "x", len(rows), "Kacheln à", TW, "x", TH)
PYEOF
ls -la "$OUT" | grep -v raw
