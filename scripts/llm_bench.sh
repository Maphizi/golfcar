#!/usr/bin/env bash
# Phase 6: Qwen-Kandidaten vergleichen (Ladezeit, RAM, TTFT, tok/s, Persona-Regeln). -> docs/llm_bench_phase6.md
#   scripts/llm_bench.sh [--quick] [--bench-models datei.gguf ...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec .venv/bin/python -m kitt.llm --bench "$@"
