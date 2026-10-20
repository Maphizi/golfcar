#!/usr/bin/env bash
# Pi aktualisieren: neuesten Stand holen, Ansagen nachrendern, Launcher neu starten.
#   ~/golfcar/scripts/update.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "== git pull ($BRANCH) =="
git pull --no-rebase origin "$BRANCH" 2>&1 | tail -2
if [ -x scripts/announce_build.sh ] && [ -d models/piper ]; then
  echo "== Ansagen =="
  scripts/announce_build.sh 2>&1 | tail -1
fi
echo "== Launcher neu starten =="
systemctl --user restart kitt-launcher.service && echo "ok: $(git log --oneline -1)"
