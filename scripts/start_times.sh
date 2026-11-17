#!/usr/bin/env bash
# Startzeiten der Szenen auswerten: je Szene die letzten "Start <szene>: Imports, Fenster, Controller, Shader, Bilder, Audio,
# erstes Bild"-Zeilen aus logs/viz_*.log, dazu Zustand von Shader- und Bild-Cache, Datenträger-Tempo und Launcher-Wechselzeiten.
# Ergebnis in diag/start_times_<zeit>.txt und (ohne --no-push) als eigener Commit auf origin/diag. Ändert nichts am System.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p diag
OUT="$ROOT/diag/start_times_$(date '+%Y%m%d_%H%M%S').txt"
PUSH=1; [ "${1:-}" = "--no-push" ] && PUSH=0
S() { printf '\n===== %s =====\n' "$1"; }
{
S "Allgemein"
date; uname -r; echo "Projekt $(git log --oneline -1 2>/dev/null)"
vcgencmd get_throttled 2>/dev/null; vcgencmd measure_clock arm 2>/dev/null; vcgencmd measure_temp 2>/dev/null
S "Startzeiten je Szene (letzte 4 Starts; Phasen in s: Imports, Fenster, Controller, Shader, Bilder, Audio, erstes Bild)"
for f in logs/viz_*.log; do
  [ -f "$f" ] || continue
  n="$(grep -c 'Start ' "$f")"; [ "$n" = 0 ] && continue
  echo "-- $(basename "$f" .log) ($n Starts im Log)"
  grep -a 'Start ' "$f" | grep -a 'erstes Bild' | tail -n 4 | sed -E 's/^.*INFO[^:]*: ?//; s/^[0-9-]+ [0-9:,]+ //' | sed 's/^/   /'
done
S "Langsamste Starts insgesamt (Top 15, Sekunden ab main)"
grep -ah 'Start .*gesamt' logs/viz_*.log 2>/dev/null | sed -E 's/.*Start ([a-z_]+): (.*) \(gesamt ([0-9.]+) s.*/\3 \1 | \2/' | sort -rn | head -n 15 | sed 's/^/   /'
S "Launcher: Moduswechsel (Start, Vorgänger geht / erstes Bild, Beende, Modus beendet) der letzten 60 Zeilen"
grep -aE 'Modus gestartet|Vorgänger|Beende Modus|Modus beendet|bleibt stehen' logs/launcher.log 2>/dev/null | tail -n 60 | sed 's/^/   /'
S "Shader-Cache (Mesa) unter .cache/mesa"
ls -la .cache/ 2>/dev/null | sed 's/^/   /'
du -sh .cache/mesa 2>/dev/null; find .cache/mesa -type f 2>/dev/null | wc -l | sed 's/^/   Dateien: /'
echo "   beschreibbar: $( [ -w .cache/mesa ] && echo ja || echo NEIN )"
echo "   neueste Einträge:"; find .cache/mesa -type f -printf '%TY-%Tm-%Td %TH:%TM %s %p\n' 2>/dev/null | sort | tail -n 5 | sed 's/^/     /'
echo "   Umgebung des laufenden Modus:"; for p in $(pgrep -f 'visualizers.engine|kitt.hal|kitt.ui' | head -2); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -E 'MESA|XDG_CACHE|KITT_MODE' | sed 's/^/     /'; done
S "Bild-Cache .cache/img (npy) und abgeleitete Daten"
du -sh .cache/img 2>/dev/null; find .cache/img -type f 2>/dev/null | wc -l | sed 's/^/   Dateien: /'
find .cache/img -type f -size +20M -printf '%s %p\n' 2>/dev/null | sort -rn | head -n 10 | sed 's/^/   groß: /'
S "Datenträger"
findmnt -no SOURCE,FSTYPE / ; df -h / | tail -1
big="$(find .cache/img -type f -size +5M 2>/dev/null | head -1)"
if [ -n "$big" ]; then
  sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || true
  dd if="$big" of=/dev/null bs=1M 2>&1 | tail -1 | sed 's/^/   Lesetest (kalt): /'
  dd if="$big" of=/dev/null bs=1M 2>&1 | tail -1 | sed 's/^/   Lesetest (warm): /'
fi
S "Python-Importzeit (numpy, pygame, OpenGL) ohne Fenster"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -X importtime -c "import numpy, pygame, OpenGL.GL" 2>&1 | sort -t'|' -k2 -rn | head -n 8 | sed 's/^/   /'
S "Last"
uptime; ps -eo pid,pcpu,pmem,cmd --sort=-pcpu | head -n 8 | sed 's/^/   /'
} > "$OUT" 2>&1
echo "geschrieben: $OUT ($(wc -l < "$OUT") Zeilen)"
if [ "$PUSH" = 1 ]; then
  if blob="$(git hash-object -w "$OUT")" && tree="$(printf '100644 blob %s\t%s\n' "$blob" "$(basename "$OUT")" | git mktree)" \
     && commit="$(git commit-tree "$tree" -m "Startzeiten $(date '+%F %T') von $(hostname)")" && git push -q -f origin "$commit:refs/heads/diag" 2>/dev/null; then
    echo "Gepusht nach origin/diag. Fertig."
  else
    echo "Push fehlgeschlagen, bitte den Inhalt weitergeben:  cat $OUT"
  fi
else
  cat "$OUT"
fi
