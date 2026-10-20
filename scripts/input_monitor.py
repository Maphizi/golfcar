#!/usr/bin/env python3
"""Alle Eingabeereignisse der PXN-Geräte (und optional aller Geräte) für N Sekunden mitschneiden und
kompakt zusammenfassen: je Gerät/Typ/Code Anzahl, Werte, Rate und ob die Taste von selbst periodisch
sendet. So sieht man, welche Taste welchen Code hat, welche Achse der Drehknopf ist und ob irgendein
Schalter dauernd Ereignisse schickt.

    scripts/input_monitor.py            10 s, nur PXN-Geräte
    scripts/input_monitor.py 20 --all   20 s, alle Eingabegeräte
Während der Aufnahme nichts anfassen (Dauersender finden) oder gezielt eine Taste/den Knopf bedienen.
"""
from __future__ import annotations

import os
import select
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import evdev
    from evdev import ecodes
except ImportError:
    venv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python")
    if os.path.exists(venv) and sys.executable != venv:
        os.execv(venv, [venv] + sys.argv)
    print("python-evdev fehlt (.venv/bin/pip install evdev)")
    sys.exit(1)


def name_of(t: int, c: int) -> str:
    table = {ecodes.EV_KEY: ecodes.KEY, ecodes.EV_ABS: ecodes.ABS, ecodes.EV_REL: ecodes.REL, ecodes.EV_MSC: ecodes.MSC}.get(t, {})
    n = table.get(c)
    if isinstance(n, (list, tuple)):
        n = n[0]
    if t == ecodes.EV_KEY and n is None:
        n = ecodes.BTN.get(c)
        if isinstance(n, (list, tuple)):
            n = n[0]
    return str(n or "unbenannt")


def main() -> int:
    secs = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else 10.0
    allow_all = "--all" in sys.argv
    devs = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except OSError:
            continue
        if allow_all or "PXN" in d.name or "GolfCar" in d.name or "KITT" in d.name:
            devs.append(d)
        else:
            d.close()
    if not devs:
        print("Kein PXN-Gerät gefunden (mit --all alle Geräte)")
        return 1
    print(f"Mitschnitt {secs:.0f} s von: " + ", ".join(f"{d.name} ({d.path})" for d in devs))
    stats: dict[tuple, dict] = {}
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
        for d in devs:
            if d.fd not in r:
                continue
            try:
                for ev in d.read():
                    if ev.type == ecodes.EV_SYN:
                        continue
                    key = (d.path, ev.type, ev.code)
                    st = stats.setdefault(key, {"n": 0, "values": {}, "times": [], "dev": d.name})
                    st["n"] += 1
                    st["values"][ev.value] = st["values"].get(ev.value, 0) + 1
                    st["times"].append(time.monotonic() - t0)
            except OSError:
                pass
    for d in devs:
        d.close()
    if not stats:
        print("Keine Ereignisse. Gut: nichts sendet von selbst.")
        return 0
    print(f"{'Gerät':<28} {'Typ':<6} {'Code':<22} {'Anzahl':>6} {'/s':>5}  Werte (Anzahl)             Hinweis")
    for (path, t, c), st in sorted(stats.items(), key=lambda kv: -kv[1]["n"]):
        times = st["times"]
        rate = st["n"] / max(0.5, times[-1] - times[0]) if len(times) > 1 else 0.0
        vals = ", ".join(f"{v}×{n}" if n > 1 else f"{v}" for v, n in sorted(st["values"].items(), key=lambda kv: -kv[1])[:6])
        hint = ""
        if len(times) >= 4:
            gaps = [b - a for a, b in zip(times, times[1:])]
            mean = sum(gaps) / len(gaps)
            spread = max(abs(g - mean) for g in gaps)
            if mean > 0.2 and spread < 0.25 * mean:
                hint = f"PERIODISCH alle {mean:.2f} s (sendet von selbst?)"
            elif rate > 20:
                hint = "Dauerstrom (Achse/Encoder)"
        tname = {ecodes.EV_KEY: "KEY", ecodes.EV_ABS: "ABS", ecodes.EV_REL: "REL", ecodes.EV_MSC: "MSC"}.get(t, str(t))
        print(f"{st['dev'][:28]:<28} {tname:<6} {c:>4} {name_of(t, c)[:16]:<17} {st['n']:>6} {rate:>5.1f}  {vals:<28} {hint}")
    print("\nKEY-Code mit value 1 = Taste gedrückt (0 = losgelassen, 2 = gehalten). ABS = Achse (Drehknopf: Werte "
          "ändern sich beim Drehen), REL = Encoder/Joystick (nur Änderungen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
