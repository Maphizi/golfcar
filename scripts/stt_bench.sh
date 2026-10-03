#!/usr/bin/env bash
# Phase 5: Whisper-Modelle vergleichen (Latenz, RTF, RAM, Text). Ergebnis in docs/stt_bench_phase5.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
exec .venv/bin/python -m kitt.stt --bench "$@"
