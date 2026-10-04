#!/usr/bin/env bash
# Ansagen aus config/announce.toml mit Piper vorrendern (nach jeder Textänderung erneut ausführen).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec .venv/bin/python -m kitt.announce --build
