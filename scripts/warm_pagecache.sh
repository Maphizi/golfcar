#!/usr/bin/env bash
# Nach dem Start alles einmal von der SD-Karte in den Arbeitsspeicher lesen, was die Szenen beim ersten Start brauchen:
# Python-Bibliotheken (numpy, pygame, OpenGL), Shader-Cache, Bild-Cache (npy/npz), Klänge, Stimmen. Danach ist der erste
# Start jeder Szene so schnell wie der zweite (der Linux-Seitencache hält die Dateien, 8 GB RAM reichen für alles).
# Läuft mit niedrigster Priorität im Hintergrund (ionice idle, nice 19), aus scripts/session_start.sh. Ändert nichts.
#   scripts/warm_pagecache.sh            alles lesen, Log in logs/warm_pagecache.log
#   scripts/warm_pagecache.sh --status   nur zeigen, wie viel davon schon im Speicher liegt (braucht vmtouch, sonst Größe)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs
LOG="$ROOT/logs/warm_pagecache.log"
# Reihenfolge = Reihenfolge des Nutzens: erst, was jede Szene braucht, dann die Szenen, dann der Rest
DIRS=(
  ".venv/lib"            # Python-Pakete (numpy, pygame, PyOpenGL, onnxruntime)
  ".cache/mesa"          # compilierte Shader (V3D)
  ".cache/img"           # Bilder als npy/npz
  "visualizers"          # Shader-Quellen, Szenen-Code
  "launcher" "kitt" "config"
  "assets/sfx"           # Hupe, Effekte
  "assets/splash" "assets/taxi"
  "assets"               # Rest der Bilder (nur nötig, wenn ein npy-Cache fehlt)
  "models/piper"         # Ansagen-Stimmen
)
if [ "${1:-}" = "--status" ]; then
  if command -v vmtouch >/dev/null; then vmtouch "${DIRS[@]}" 2>/dev/null | grep -E 'Files|Resident'; else du -shc "${DIRS[@]}" 2>/dev/null | tail -1; fi
  exit 0
fi
t0=$(date +%s)
echo "[$(date '+%F %T')] warm_pagecache: Start" >> "$LOG"
total=0
for d in "${DIRS[@]}"; do
  [ -e "$d" ] || continue
  t=$(date +%s)
  if command -v vmtouch >/dev/null; then
    vmtouch -t -q "$d" 2>/dev/null
  else
    find "$d" -type f -size +4k -print0 2>/dev/null | xargs -0 -r cat > /dev/null 2>&1
  fi
  sz=$(du -sm "$d" 2>/dev/null | cut -f1); total=$((total + sz))
  echo "[$(date '+%F %T')]   $d: ${sz} MB in $(( $(date +%s) - t )) s" >> "$LOG"
done
echo "[$(date '+%F %T')] warm_pagecache: fertig, ${total} MB in $(( $(date +%s) - t0 )) s" >> "$LOG"
