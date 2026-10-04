#!/usr/bin/env bash
# Phase 5: whisper.cpp bauen, Whisper-Modelle und Silero VAD laden, Test-WAVs erzeugen.
# Idempotent. Dauer auf dem Pi 5: Build ca. 5–10 min, Downloads ca. 350 MB.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WDIR="$ROOT/vendor/whisper.cpp"
MDIR="$ROOT/models"
mkdir -p "$MDIR" vendor logs
say() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

say "apt-Pakete"
sudo apt-get install -y -qq cmake build-essential git espeak-ng curl 2>&1 | tail -1

say "Python-Pakete (onnxruntime für Silero VAD)"
.venv/bin/pip install -q "onnxruntime>=1.17" 2>&1 | grep -v notice || true
.venv/bin/python -c "import onnxruntime as o; print('onnxruntime', o.__version__)" || echo "WARNUNG: onnxruntime fehlt, VAD fällt auf Energie-VAD zurück"

say "whisper.cpp"
if [ -d "$WDIR/.git" ]; then
  git -C "$WDIR" pull --ff-only 2>&1 | tail -1
else
  git clone --depth=1 https://github.com/ggml-org/whisper.cpp.git "$WDIR"
fi
git -C "$WDIR" log -1 --format='Commit: %h %cd' --date=short
if [ ! -x "$WDIR/build/bin/whisper-server" ]; then
  # CPU-Build mit NEON; GGML_NATIVE nutzt die Cortex-A76-Befehle des Pi 5
  cmake -S "$WDIR" -B "$WDIR/build" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DWHISPER_BUILD_TESTS=OFF > logs/whisper_cmake.log 2>&1 \
    && cmake --build "$WDIR/build" -j4 --config Release > logs/whisper_build.log 2>&1 \
    || { echo "Build fehlgeschlagen, siehe logs/whisper_build.log"; tail -20 logs/whisper_build.log; exit 1; }
fi
ls -1 "$WDIR/build/bin/" | grep -E "^whisper-(cli|server|bench)$" | sed 's/^/  /'

say "Modelle"
dl() {  # dl <datei> <url>
  if [ -s "$MDIR/$1" ]; then echo "  $1 vorhanden"; return 0; fi
  echo "  lade $1 ..."
  curl -sS -L -f -C - --retry 3 -o "$MDIR/$1.part" "$2" && mv "$MDIR/$1.part" "$MDIR/$1" && echo "  ok ($(du -h "$MDIR/$1" | cut -f1))" || { echo "  FEHLER beim Laden von $1"; return 1; }
}
HF=https://huggingface.co/ggerganov/whisper.cpp/resolve/main
dl ggml-tiny.bin "$HF/ggml-tiny.bin"
dl ggml-base.bin "$HF/ggml-base.bin"
dl ggml-small-q5_1.bin "$HF/ggml-small-q5_1.bin"
dl silero_vad.onnx https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx

say "Deutsche Test-WAVs (espeak-ng, 22 kHz, werden beim Laden auf 16 kHz gebracht) nach kitt/stt/testdata"
TD="$ROOT/kitt/stt/testdata"
mkdir -p "$TD"
gen() { [ -s "$TD/$1.wav" ] || espeak-ng -v de -s 150 -w "$TD/$1.wav" "$2" 2>/dev/null; }
gen 01_status "KITT, wie sieht es aus?"
gen 02_wo "KITT, wo sind wir gerade?"
gen 03_stimmung "KITT, mach mal ein bisschen Stimmung."
gen 04_lang "KITT, fahr uns bitte zurück zum Clubhaus und sag mir, wie lange wir ungefähr brauchen."
ls -1 "$TD" | sed 's/^/  /'

say "Schnelltest: Transkription der Test-WAVs mit dem konfigurierten Modell"
.venv/bin/python -m kitt.stt --wav "$TD"/*.wav 2>&1 | grep -vE "^\s*$"
say "fertig. Benchmark:  scripts/stt_bench.sh"
