#!/usr/bin/env bash
# Zustand des Appliance-Betriebs anzeigen.
echo "== lightdm =="; grep -E '^(autologin-user|autologin-session|user-session)=' /etc/lightdm/lightdm.conf 2>/dev/null | sed 's/^/  /'
echo "== Session-Prozesse =="; pgrep -a -x labwc | sed 's/^/  /'; pgrep -a -f 'wf-panel|pcmanfm' | sed 's/^/  (Desktop) /'
echo "== Launcher-Dienst =="; systemctl --user --no-pager status kitt-launcher.service 2>/dev/null | sed -n '1,6p' | sed 's/^/  /'
echo "== Launcher-Zustand =="; "$(dirname "$0")/kittctl" state 2>/dev/null | sed 's/^/  /'
