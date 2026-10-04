#!/usr/bin/env bash
# Phase 10: Dauertest. Schaltet die Modi im Kreis durch (oder bleibt in einem Modus) und protokolliert
# alle 30 s Temperatur, Throttling, Takt, RAM, Last, Modus und Launcher-PID nach logs/soak.csv.
# Läuft gegen den laufenden Launcher (Desktop oder Appliance), beendet ihn nicht.
#
#   scripts/soak_test.sh                 2 Stunden, Modi im Kreis (je 5 min, KITT 8 min)
#   scripts/soak_test.sh --hours 6       längere Laufzeit
#   scripts/soak_test.sh --stay kitt     nur einen Modus halten
#   scripts/soak_test.sh --hours 0.1     Kurztest (6 min)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
hours=2; stay=""
while [ $# -gt 0 ]; do case "$1" in --hours) hours="$2"; shift 2;; --stay) stay="$2"; shift 2;; *) shift;; esac; done
CSV="$ROOT/logs/soak.csv"
mkdir -p logs
end=$(( $(date +%s) + $(python3 -c "print(int($hours*3600))") ))
seq_modes=(home gaming home viz_psychedelic viz_crt viz_eye kitt home)
seq_secs=(60 300 30 300 300 300 480 60)

sample() {  # eine CSV-Zeile
  local t thr clk mem load mode pid
  t=$(vcgencmd measure_temp 2>/dev/null | tr -d "temp='C"); thr=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
  clk=$(vcgencmd measure_clock arm 2>/dev/null | cut -d= -f2); clk=$(( ${clk:-0} / 1000000 ))
  mem=$(free -m | awk 'NR==2{print $3}'); load=$(cut -d' ' -f1 /proc/loadavg)
  mode=$(scripts/kittctl state 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('mode'))" 2>/dev/null || echo none)
  pid=$(pgrep -f "python -m launcher$" | head -1)
  echo "$(date +%FT%T),${t:-},${thr:-},${clk:-},${mem},${load},${mode},${pid:-}" >> "$CSV"
}
if ! scripts/kittctl state >/dev/null 2>&1; then echo "Launcher läuft nicht (scripts/run_launcher.sh oder Appliance-Session)"; exit 1; fi
[ -f "$CSV" ] || echo "zeit,temp_c,throttled,arm_mhz,ram_used_mb,load1,mode,launcher_pid" > "$CSV"
echo "Dauertest bis $(date -d @$end '+%H:%M'), CSV: $CSV"
[ -n "$stay" ] && scripts/kittctl "$stay" >/dev/null
i=0; next_switch=$(date +%s)
while [ "$(date +%s)" -lt "$end" ]; do
  if [ -z "$stay" ] && [ "$(date +%s)" -ge "$next_switch" ]; then
    m=${seq_modes[$((i % ${#seq_modes[@]}))]}; d=${seq_secs[$((i % ${#seq_secs[@]}))]}
    scripts/kittctl "$m" >/dev/null 2>&1; echo "[$(date +%T)] -> $m für ${d}s"
    next_switch=$(( $(date +%s) + d )); i=$((i+1))
  fi
  sample
  sleep 30
done
[ -z "$stay" ] && scripts/kittctl home >/dev/null 2>&1
echo "Dauertest beendet. Auswertung:  scripts/perf_report.py"
