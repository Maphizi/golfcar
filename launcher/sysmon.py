"""Systemwerte ohne externe Abhängigkeiten: CPU-Last, RAM, Temperatur, Throttling."""
from __future__ import annotations

import os
from pathlib import Path

_THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")
_THROTTLED = Path("/sys/devices/platform/cooling_fan/hwmon")  # nur Marker, vcgencmd ist genauer


def cpu_temp() -> float | None:
    try:
        return int(_THERMAL.read_text().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def load_avg() -> float:
    try:
        return os.getloadavg()[0]
    except OSError:
        return 0.0


def mem_used_mb() -> tuple[int, int]:
    """(benutzt, gesamt) in MB, 'benutzt' = total - available."""
    total = avail = 0
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
    except OSError:
        return 0, 0
    return (total - avail) // 1024, total // 1024


def snapshot() -> dict:
    used, total = mem_used_mb()
    return {
        "temp_c": cpu_temp(),
        "load1": load_avg(),
        "ncpu": os.cpu_count() or 1,
        "mem_used_mb": used,
        "mem_total_mb": total,
    }


def format_line(s: dict | None = None) -> str:
    s = s or snapshot()
    t = f"{s['temp_c']:.1f}°C" if s["temp_c"] is not None else "n/a"
    return f"temp {t}  load {s['load1']:.2f}/{s['ncpu']}  ram {s['mem_used_mb']}/{s['mem_total_mb']} MB"
