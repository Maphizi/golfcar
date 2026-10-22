#!/usr/bin/env bash
# Pi aktualisieren: neuesten Stand holen, Ansagen nachrendern, Launcher neu starten.
#   ~/golfcar/scripts/update.sh
# Bricht ab, wenn der Stand nicht geholt werden konnte (dann läuft sonst unbemerkt die alte Version).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "== vorher: $(git log --oneline -1)"
if ! git fetch origin "$BRANCH" 2>&1 | tail -1; then
  echo "FEHLER: git fetch fehlgeschlagen (Netz?)"; exit 1
fi
if ! git merge --ff-only "origin/$BRANCH" >/dev/null 2>&1; then
  echo "Schnelles Vorspulen nicht möglich, versuche Merge ..."
  if ! git pull --no-rebase origin "$BRANCH" 2>&1 | tail -3; then
    echo "FEHLER: Update nicht übernommen. Lokale Änderungen:"; git status --short | head; exit 1
  fi
fi
echo "== jetzt:  $(git log --oneline -1)"
if [ -x scripts/announce_build.sh ] && [ -d models/piper ]; then
  echo "== Ansagen =="
  scripts/announce_build.sh 2>&1 | tail -1
fi
if [ -x .venv/bin/python ]; then
  echo "== Bild-Cache =="
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python scripts/warm_cache.py 2>&1 | tail -1
fi
echo "== Launcher neu starten =="
systemctl --user restart kitt-launcher.service && echo "ok"
