#!/usr/bin/env bash
# Phase 2: Abhängigkeiten für den Launcher installieren und venv anlegen.
# Idempotent, kann mehrfach laufen. Installiert nur kleine Pakete.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== apt-Pakete =="
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3-venv python3-dev build-essential \
  libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 libsdl2-mixer-2.0-0 \
  fonts-dejavu-core mesa-utils

echo "== venv =="
if [ ! -x .venv/bin/python ]; then
  # --system-site-packages: pygame/numpy aus Debian bleiben nutzbar, pip ergänzt nur Fehlendes
  python3 -m venv --system-site-packages .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "== Gruppen =="
for g in input video render audio; do
  id -nG "$USER" | grep -qw "$g" || { echo "Füge $USER zu Gruppe $g hinzu (Neuanmeldung nötig)"; sudo usermod -aG "$g" "$USER"; }
done

mkdir -p logs
echo "== fertig =="
.venv/bin/python -c "import pygame, evdev; print('pygame', pygame.version.ver, '/ evdev ok')"
