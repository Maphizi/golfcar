#!/usr/bin/env bash
# systemd-User-Service installieren und aktivieren (Phase 9 schaltet ihn scharf).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p ~/.config/systemd/user
sed "s|__ROOT__|$ROOT|g" "$ROOT/systemd/kitt-launcher.service" > ~/.config/systemd/user/kitt-launcher.service
systemctl --user daemon-reload
systemctl --user enable kitt-launcher.service
echo "Aktiviert. Jetzt starten mit:  systemctl --user start kitt-launcher"
