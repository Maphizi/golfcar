#!/usr/bin/env bash
# Phase 7: Piper (pip) und deutsche Stimme(n) installieren, Sprachausgabe testen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VDIR="$ROOT/models/piper"
mkdir -p "$VDIR" logs
say() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

say "piper-tts (pip)"
.venv/bin/pip install -q "piper-tts>=1.3" 2>&1 | grep -v notice || true
.venv/bin/python -c "import piper, onnxruntime; print('piper-tts ok, onnxruntime', onnxruntime.__version__)" || { echo "piper-tts fehlt"; exit 1; }

say "Stimmen laut config/kitt.toml [tts].bench_voices (huggingface.co/rhasspy/piper-voices)"
voices=$(python3 -c "import tomllib; c=tomllib.load(open('config/kitt.toml','rb'))['tts']; print(' '.join(dict.fromkeys([c['voice']]+c.get('bench_voices',[]))))")
for v in $voices; do
  if [ -s "$VDIR/$v.onnx" ] && [ -s "$VDIR/$v.onnx.json" ]; then echo "  $v vorhanden"; continue; fi
  echo "  lade $v ..."
  .venv/bin/python -m piper.download_voices --download-dir "$VDIR" "$v" 2>&1 | tail -1 || echo "  FEHLER bei $v"
done
ls -la "$VDIR" | grep -E "\.onnx(\.json)?$" | awk '{print "  "$5"  "$9}'

say "Sprachtest (WAV nach docs/, zusätzlich Wiedergabe über Lautsprecher, falls vorhanden)"
mkdir -p docs
for v in $voices; do
  [ -s "$VDIR/$v.onnx" ] || continue
  echo "Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab." \
    | .venv/bin/python -m piper -m "$VDIR/$v.onnx" -f "docs/tts_sample_$v.wav" 2>/dev/null \
    && echo "  docs/tts_sample_$v.wav geschrieben" || echo "  Synthese mit $v fehlgeschlagen"
done
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
.venv/bin/python -m kitt.voice --say "KITT online. Alle Systeme nominal. Fahrer leider auch." 2>&1 | grep -E "Piper|TTS|Wiedergabe|STATE|Error|fehlt" || true
say "fertig. Ganze Pipeline:  scripts/kitt_voice.sh --text \"KITT, wie sieht's aus?\""
