#!/usr/bin/env bash
# KITT-Sprachpipeline ohne Oberfläche:  scripts/kitt_voice.sh [--text "Frage"] [--say "Text"] [--seconds N]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
exec .venv/bin/python -m kitt.voice "$@"
