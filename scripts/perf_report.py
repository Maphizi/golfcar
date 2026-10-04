#!/usr/bin/env python3
"""Phase 10: Logs auswerten -> docs/perf_phase10.md
Quellen: logs/soak.csv (Dauertest), logs/launcher.log* (Status, Neustarts, Abstürze),
logs/viz_*.log* (FPS), logs/kitt.log* (Runden-Latenzen), logs/*.log (Fehler)."""
from __future__ import annotations

import csv
import glob
import re
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
out = []


def lines(pattern: str):
    for f in sorted(glob.glob(str(LOGS / pattern))):
        try:
            yield from open(f, errors="ignore")
        except OSError:
            pass


def section(title: str):
    out.append(f"\n## {title}\n")


out.append(f"# Performance-Report KITT-Cart ({time.strftime('%Y-%m-%d %H:%M')})\n")

# -- Dauertest
soak = LOGS / "soak.csv"
if soak.exists():
    rows = list(csv.DictReader(open(soak)))
    if rows:
        temps = [float(r["temp_c"]) for r in rows if r["temp_c"]]
        rams = [int(r["ram_used_mb"]) for r in rows if r["ram_used_mb"]]
        clks = [int(r["arm_mhz"]) for r in rows if r["arm_mhz"]]
        thr = {r["throttled"] for r in rows if r["throttled"]}
        pids = [r["launcher_pid"] for r in rows if r["launcher_pid"]]
        restarts = sum(1 for a, b in zip(pids, pids[1:]) if a != b)
        dur = len(rows) * 0.5 / 60
        section("Dauertest")
        out.append(f"{len(rows)} Messpunkte über {dur:.1f} h ({rows[0]['zeit']} bis {rows[-1]['zeit']})\n")
        out.append("| Messwert | min | Ø | max |\n|---|---|---|---|")
        if temps: out.append(f"| Temperatur °C | {min(temps):.1f} | {st.mean(temps):.1f} | {max(temps):.1f} |")
        if clks: out.append(f"| ARM-Takt MHz | {min(clks)} | {st.mean(clks):.0f} | {max(clks)} |")
        if rams: out.append(f"| RAM belegt MB | {min(rams)} | {st.mean(rams):.0f} | {max(rams)} |")
        out.append(f"\nThrottling-Flags gesehen: {', '.join(sorted(thr)) or 'keine'} (0x0 = nie gedrosselt, keine Unterspannung)")
        out.append(f"\nLauncher-Neustarts (PID-Wechsel): {restarts}")
        by_mode = {}
        for r in rows:
            if r["temp_c"]:
                by_mode.setdefault(r["mode"], []).append(float(r["temp_c"]))
        out.append("\n| Modus | Messpunkte | Ø Temp | max Temp |\n|---|---|---|---|")
        for m, ts in sorted(by_mode.items()):
            out.append(f"| {m} | {len(ts)} | {st.mean(ts):.1f} | {max(ts):.1f} |")

# -- FPS der Szenen
section("Visualizer FPS")
fps = {}
for f in sorted(glob.glob(str(LOGS / "viz_*.log*"))) + sorted(glob.glob(str(LOGS / "kitt.log*"))):
    name = Path(f).name.split(".")[0]
    for line in open(f, errors="ignore"):
        m = re.search(r"fps ([\d.]+)", line)
        if m:
            fps.setdefault(name, []).append(float(m.group(1)))
if fps:
    out.append("| Szene | Messungen | Ø fps | min fps |\n|---|---|---|---|")
    for n, v in sorted(fps.items()):
        out.append(f"| {n} | {len(v)} | {st.mean(v):.1f} | {min(v):.1f} |")
else:
    out.append("keine FPS-Zeilen gefunden")

# -- KITT-Runden
section("KITT-Latenz")
rounds = []
for line in lines("kitt.log*"):
    m = re.search(r"Runde: LLM TTFT ([\d.]+)s, ([\d.]+) tok/s, erste Sprache nach ([\d.]+)s, gesamt ([\d.]+)s", line)
    if m:
        rounds.append(tuple(float(x) for x in m.groups()))
stt = [float(m.group(1)) for line in lines("kitt.log*") for m in [re.search(r"STT ([\d.]+)s", line)] if m]
loads = [float(m.group(1)) for line in lines("kitt.log*") for m in [re.search(r"llama-server bereit nach ([\d.]+)s", line)] if m]
if rounds:
    ttft, tps, first, total = zip(*rounds)
    out.append(f"{len(rounds)} Runden\n")
    out.append("| Messwert | Ø | min | max |\n|---|---|---|---|")
    if stt: out.append(f"| STT (whisper) s | {st.mean(stt):.2f} | {min(stt):.2f} | {max(stt):.2f} |")
    out.append(f"| LLM Time-to-first-token s | {st.mean(ttft):.2f} | {min(ttft):.2f} | {max(ttft):.2f} |")
    out.append(f"| LLM tok/s | {st.mean(tps):.1f} | {min(tps):.1f} | {max(tps):.1f} |")
    out.append(f"| Erste Sprache nach s (ab LLM-Start) | {st.mean(first):.2f} | {min(first):.2f} | {max(first):.2f} |")
    out.append(f"| Runde gesamt s | {st.mean(total):.2f} | {min(total):.2f} | {max(total):.2f} |")
    if loads: out.append(f"| llama-server Ladezeit s | {st.mean(loads):.1f} | {min(loads):.1f} | {max(loads):.1f} |")
else:
    out.append("keine Runden im Log")

# -- Fehler und Abstürze
section("Fehler, Abstürze, Neustarts")
crash = [l.strip() for l in lines("launcher.log*") if re.search(r"exit -?\d+|stürzt|Fallback|lässt sich nicht", l) and "exit 0" not in l]
errs = [l.strip() for l in lines("*.log*") if re.search(r"ERROR|Traceback|abgestürzt", l)]
out.append(f"Launcher-Meldungen zu Abbrüchen: {len(crash)}")
for l in crash[-10:]:
    out.append(f"- `{l[:160]}`")
out.append(f"\nERROR/Traceback-Zeilen in allen Logs: {len(errs)}")
for l in errs[-10:]:
    out.append(f"- `{l[:160]}`")

dst = ROOT / "docs" / "perf_phase10.md"
dst.write_text("\n".join(out) + "\n")
print("\n".join(out))
print(f"\n-> {dst}")
