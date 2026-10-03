#!/usr/bin/env bash
# Phase 5: Live-Test Mikrofon -> VAD -> whisper. Transkripte erscheinen im Terminal. Strg+C beendet.
#   scripts/stt_mic.sh [--seconds 60] [--model ggml-small-q5_1.bin]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
exec .venv/bin/python -m kitt.stt --mic "$@"
