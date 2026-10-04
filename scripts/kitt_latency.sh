#!/usr/bin/env bash
# Phase 10: Latenztest der KITT-Pipeline ohne Mikrofon. Stellt die Benchmark-Fragen in einer
# Server-Sitzung und protokolliert je Runde TTFT, erste Sprache, Gesamtzeit nach logs/kitt.log.
#   scripts/kitt_latency.sh [--no-audio]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
.venv/bin/python -m kitt.voice --texts-file kitt/personality/bench_prompts.txt "$@" 2>&1 | grep -E "Fahrer:|KITT:|Runde|STATE LOADING|STATE IDLE|Error|fehlt"
