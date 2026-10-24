#!/usr/bin/env python3
"""Stimmen-Drehknopf prüfen, wenn er nichts bewirkt. Zeigt die PXN-Geräte mit Dreh-Ereignissen (REL) und Achsen (ABS),
nimmt dann 10 s lang auf, was beim Drehen ankommt, zeigt den Faktor in logs/voice_volume.txt (Datei, Alter) und die
Grundlautstärke [volume].voice_gain, und spielt zum Schluss eine Ansage mit dem aktuellen Faktor.

    .venv/bin/python scripts/voice_knob_check.py          (auf dem Pi; der Launcher darf dabei laufen)
    .venv/bin/python scripts/voice_knob_check.py 0.3      zusätzlich: Faktor 0.3 in voice_volume.txt schreiben und ansagen

Erwartung: beim Drehen kommen Zeilen "EV_REL REL_MISC 32 / 224" (oder eine ABS-Achse); im Launcher-Log stehen dann
"Stimme NN% -> voice_volume.txt". Kommt beim Drehen gar nichts, sitzt der Knopf an einem anderen Interface (dann
scripts/input_monitor.py 10 --all). Kommt eine ABS-Achse, in settings.toml [volume] rel = false und axis = "ABS_..." setzen."""
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

from launcher import config as lcfg  # noqa: E402

VOICE_FILE = os.path.join(ROOT, "logs", "voice_volume.txt")


def main() -> int:
    cfg = lcfg.load_settings().get("volume", {})
    print(f"settings.toml [volume]: enabled={cfg.get('enabled', True)} rel={cfg.get('rel', False)} axis='{cfg.get('axis', '')}' "
          f"target={cfg.get('target', 'voice')} step={cfg.get('step', 5)} voice_gain={cfg.get('voice_gain', 1.0)}")
    devs = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except Exception:
            continue
        caps = d.capabilities()
        rel = [ecodes.REL.get(c, c) for c in caps.get(ecodes.EV_REL, [])]
        abs_ = [ecodes.ABS.get(c, c) for c, _ in caps.get(ecodes.EV_ABS, [])]
        mark = "PXN" if "PXN" in d.name else "   "
        print(f"{mark} {path}: {d.name}  REL={rel}  ABS={abs_}")
        if "PXN" in d.name:
            devs.append(d)
        else:
            d.close()
    if not devs:
        print("Kein PXN-Gerät gefunden: USB prüfen, Rechte (Gruppe input)")
        return 1
    print("\nJetzt 10 s lang den Stimmen-Knopf drehen ...")
    t0 = time.monotonic()
    seen: dict = {}
    while time.monotonic() - t0 < 10.0:
        r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
        for d in devs:
            if d.fd not in r:
                continue
            try:
                for ev in d.read():
                    if ev.type in (ecodes.EV_SYN, ecodes.EV_MSC):
                        continue
                    key = (d.path, ev.type, ev.code)
                    if key not in seen:
                        seen[key] = [0, set()]
                        names = ecodes.bytype.get(ev.type, {}).get(ev.code, ev.code)
                        print(f"  {d.path} {ecodes.EV.get(ev.type, ev.type)} {names} Wert {ev.value}")
                    seen[key][0] += 1
                    seen[key][1].add(ev.value)
            except OSError:
                pass
    if not seen:
        print("  nichts angekommen: Knopf an einem anderen Interface? -> scripts/input_monitor.py 10 --all")
    for (path, t, c), (n, vals) in seen.items():
        names = ecodes.bytype.get(t, {}).get(c, c)
        print(f"  {path} {ecodes.EV.get(t, t)} {names}: {n} Ereignisse, Werte {sorted(vals)[:8]}")
    print()
    if len(sys.argv) > 1:
        try:
            os.makedirs(os.path.dirname(VOICE_FILE), exist_ok=True)
            with open(VOICE_FILE, "w") as fh:
                fh.write(f"{float(sys.argv[1]):.2f}")
            print(f"voice_volume.txt auf {float(sys.argv[1]):.2f} gesetzt")
        except (OSError, ValueError) as exc:
            print(f"voice_volume.txt: {exc}")
    try:
        age = time.time() - os.stat(VOICE_FILE).st_mtime
        with open(VOICE_FILE) as fh:
            print(f"logs/voice_volume.txt = {fh.read().strip()} (vor {age:.0f} s geschrieben)")
    except OSError:
        print("logs/voice_volume.txt fehlt: der Knopf hat noch nie geschrieben (Launcher-Log: 'Lautstärkeknopf')")
    try:
        from kitt.tts.piper_tts import voice_volume
        print(f"Stimmenfaktor gesamt (Knopf x voice_gain): {voice_volume():.2f}")
        from kitt import announce
        if announce.play("home"):
            print("Ansage 'home' gespielt (mit diesem Faktor)")
            if announce._current:
                announce._current.wait()
        else:
            print("keine Ansage vorhanden (erst scripts/announce_build.sh)")
    except Exception as exc:
        print(f"Ansage: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
