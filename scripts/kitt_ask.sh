#!/usr/bin/env bash
# Eine Frage an KITT (Text, ohne Sprache):  scripts/kitt_ask.sh "KITT, wie sieht's aus?"
# Ohne Argument: interaktiver Dialog.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ $# -gt 0 ]; then exec .venv/bin/python -m kitt.llm --ask "$*"; else exec .venv/bin/python -m kitt.llm --chat; fi
