#!/usr/bin/env python3
"""Schalter und Knöpfe des PXN-CB1 anlernen, ohne Ton und ohne Takt: nach dem Start hast du 60 s Zeit und bedienst in
Ruhe der Reihe nach (zwischen den Schritten je 2-3 s Pause lassen):

  1. Hupen-Schalter auf die zweite Seite drücken (die Seite, die noch keinen Ton macht)
  2. Kippschalter A nach unten, kurz warten, wieder nach oben
  3. Kippschalter B nach unten, kurz warten, wieder nach oben
  4. Drehknopf 1 ein paar Raster hin und zurück drehen
  5. Drehknopf 2 ein paar Raster hin und zurück drehen

Davor 5 s Ruhephase (nichts anfassen): zeigt, was das Board von selbst schickt. Danach ein Zeitverlauf aller Ereignisse
und unter "Ergebnis" die Einträge für settings.toml / keymap.toml. Die Ausgabe bitte komplett posten.

    .venv/bin/python scripts/board_learn.py        (auf dem Pi, der Launcher darf laufen)
    .venv/bin/python scripts/board_learn.py 90     90 s statt 60 s"""
from __future__ import annotations

import os
import select
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import evdev
    from evdev import ecodes
except ImportError:
    venv = os.path.join(ROOT, ".venv", "bin", "python")
    if os.path.exists(venv) and sys.executable != venv:
        os.execv(venv, [venv] + sys.argv)
    print("python-evdev fehlt (.venv/bin/pip install evdev)")
    sys.exit(1)

KNOWN = {266: "Startknopf", 267: "Kippschalter Navigation", 269: "Hupe Seite 1", 275: "Autopilot",
         ecodes.KEY_VOLUMEUP: "Lauter", ecodes.KEY_VOLUMEDOWN: "Leiser"}


def kname(t: int, c: int) -> str:
    n = ecodes.bytype.get(t, {}).get(c, c)
    if isinstance(n, list):
        n = n[0]
    return f"{c} {n}" if t == ecodes.EV_KEY else str(n)


def record(devs: list, seconds: float) -> list:
    """[(t, path, type, code, value)] für seconds Sekunden."""
    out = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
        for d in devs:
            if d.fd not in r:
                continue
            try:
                for ev in d.read():
                    if ev.type in (ecodes.EV_SYN, ecodes.EV_MSC):
                        continue
                    if ev.type == ecodes.EV_ABS and ev.code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                        continue
                    out.append((time.monotonic() - t0, d.path, ev.type, ev.code, ev.value))
            except OSError:
                pass
    return out


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 60.0
    devs = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except Exception:
            continue
        if "PXN" in d.name:
            devs.append(d)
            print(f"Gerät {path}: {d.name}")
        else:
            d.close()
    if not devs:
        print("Kein PXN-Gerät gefunden")
        return 1

    print("\nRuhephase: 5 s nichts anfassen ...", flush=True)
    idle: dict = {}
    for _, path, t, c, v in record(devs, 5.0):
        idle.setdefault((path, t, c), []).append(v)
    for (path, t, c), vals in sorted(idle.items()):
        uniq = sorted(set(vals))
        print(f"  von selbst: {path} {ecodes.EV.get(t, t)} {kname(t, c)}: {len(vals)} Ereignisse, Werte {uniq[:10]}"
              + ("  <- Stellungsgeber (Knopf), harmlos" if t == ecodes.EV_REL and len(uniq) == 1 else "")
              + ("  <- TASTE SENDET VON SELBST" if t == ecodes.EV_KEY else ""))
    if not idle:
        print("  nichts: das Board ist in Ruhe still")
    rest_rel = {c: vals[-1] for (_, t, c), vals in idle.items() if t == ecodes.EV_REL}

    print(f"\nJetzt {seconds:.0f} s Zeit: Hupe Seite 2, Schalter A runter/rauf, Schalter B runter/rauf, Knopf 1, Knopf 2 ...", flush=True)
    evs = record(devs, seconds)
    print("\n==== Zeitverlauf ====")
    last_rel: dict = dict(rest_rel)
    rel_runs: dict = {}
    for ts, path, t, c, v in evs:
        if t == ecodes.EV_REL:
            if last_rel.get(c) == v:
                continue                                       # Stellung unverändert
            last_rel[c] = v
            rel_runs.setdefault(c, []).append((ts, v))
            print(f"{ts:6.1f}s  {ecodes.EV.get(t, t)} {kname(t, c)} -> {v}")
        elif t == ecodes.EV_KEY:
            tag = KNOWN.get(c, "")
            print(f"{ts:6.1f}s  Taste {kname(t, c)} {'gedrückt' if v == 1 else 'losgelassen' if v == 0 else v}{'  (' + tag + ')' if tag else ''}")
        else:
            print(f"{ts:6.1f}s  {ecodes.EV.get(t, t)} {kname(t, c)} = {v}")
    if not evs:
        print("  nichts angekommen")

    print("\n==== Ergebnis ====")
    presses = [(ts, c) for ts, _, t, c, v in evs if t == ecodes.EV_KEY and v == 1 and c not in KNOWN]
    releases = {c: ts for ts, _, t, c, v in evs if t == ecodes.EV_KEY and v == 0}
    order: list = []
    for ts, c in presses:
        if c not in [o for o, _ in order]:
            order.append((c, ts))
    labels = ["Hupe Seite 2", "Kippschalter A unten", "Kippschalter A oben", "Kippschalter B unten", "Kippschalter B oben"]
    if not order:
        print("keine neuen Tastencodes gesehen")
    for i, (c, ts) in enumerate(order):
        rel_at = releases.get(c)
        held = rel_at is not None and rel_at - ts > 0.8
        kind = ("Schalter, bleibt gedrückt (unten = 1, oben = 0)" if held else
                "Taster (kurz)" if rel_at is not None else "nur gedrückt, nie losgelassen")
        label = labels[i] if i < len(labels) else "?"
        print(f"{i + 1}. Code {c} bei {ts:.1f}s: {kind}  -> vermutlich {label}")
    if order:
        c0 = order[0][0]
        print(f"\nsettings.toml [buttons]:  horn2_code = {c0}")
        rest = [c for c, _ in order[1:]]
        if len(rest) >= 2:
            print("keymap.toml:")
            for name, codes in (("A", rest[0:2]), ("B", rest[2:4])):
                if not codes:
                    continue
                if len(codes) == 2 and codes[0] != codes[1]:
                    print(f"  Kippschalter {name}: code = {codes[0]} (unten) und code = {codes[1]} (oben), je action = ...")
                else:
                    print(f"  Kippschalter {name}: code = {codes[0]} action = ... (unten) und code = {codes[0]} on = \"up\" action = ... (oben)")
    for c, runs in rel_runs.items():
        vals = [v for _, v in runs]
        print(f"Knopf {ecodes.REL.get(c, c)}: Stellung geändert {len(runs)}x, Verlauf {vals[:24]}{' ...' if len(vals) > 24 else ''}"
              f"  -> Stimmenknopf (volume_knob, REL)")
    vol = [(ts, c) for ts, _, t, c, v in evs if t == ecodes.EV_KEY and v == 1 and c in (ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN)]
    if vol:
        print(f"Lauter/Leiser-Tasten: {len(vol)}x ({vol[0][0]:.1f}s .. {vol[-1][0]:.1f}s)  -> Musikknopf (music_knob)")
    abs_codes = sorted({c for _, _, t, c, _ in evs if t == ecodes.EV_ABS})
    for c in abs_codes:
        vals = [v for _, _, t, cc, v in evs if t == ecodes.EV_ABS and cc == c]
        print(f"ABS-Achse {ecodes.ABS.get(c, c)}: {min(vals)}..{max(vals)}  -> settings.toml [volume] rel = false, axis = \"{ecodes.ABS.get(c, c)}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
