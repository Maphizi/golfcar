#!/usr/bin/env bash
# Momentaufnahme: Temperatur, Throttling, Takt, RAM, Launcher, Dienste, Audio. Rein lesend.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
t=$(vcgencmd measure_temp 2>/dev/null | tr -d "temp='C")
thr=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
clk=$(vcgencmd measure_clock arm 2>/dev/null | cut -d= -f2); clk=$(( ${clk:-0} / 1000000 ))
echo "Temperatur: ${t:-?} °C   ARM-Takt: ${clk:-?} MHz   Throttled: ${thr:-?}"
case "$thr" in
  0x0) echo "  kein Throttling, keine Unterspannung";;
  *) echo "  Bits: 0x1 Unterspannung jetzt, 0x2 Takt begrenzt jetzt, 0x4 gedrosselt jetzt, 0x8 Temperaturlimit jetzt; 0x10000..0x80000 = dasselbe seit Boot";;
esac
free -m | awk 'NR==2{printf "RAM: %d/%d MB belegt, %d MB verfügbar\n",$3,$2,$7}'
uptime | sed 's/^ */Last: /'
echo "Launcher: $("$ROOT/scripts/kittctl" state 2>/dev/null | tr -d '\n ' || echo 'läuft nicht')"
systemctl --user is-active kitt-launcher.service 2>/dev/null | sed 's/^/Dienst kitt-launcher: /'
for p in llama-server whisper-server emulationstation retroarch; do pgrep -f "^[^ ]*/?$p( |$)" >/dev/null && echo "Prozess: $p läuft"; done
echo "Audio: Sink $(pactl get-default-sink 2>/dev/null || echo '?'), Source $(pactl get-default-source 2>/dev/null || echo 'keine')"
