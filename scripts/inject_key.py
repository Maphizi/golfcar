#!/usr/bin/env python3
"""Entwicklung: Tastendruck über ein virtuelles Eingabegerät einspeisen.

Testet die evdev-Erkennung des Launchers ohne physische Tastatur, z. B. per SSH:
    .venv/bin/python scripts/inject_key.py KEY_F3
    .venv/bin/python scripts/inject_key.py KEY_F6 KEY_F2 --delay 5

Braucht Schreibrecht auf /dev/uinput (sudo oder udev-Regel). Das virtuelle Gerät
heißt "KITT Test Buttonbox" und erscheint im Launcher-Log wie eine echte Buttonbox.
"""
import argparse
import time

from evdev import UInput, ecodes as e

p = argparse.ArgumentParser()
p.add_argument("keys", nargs="+", help="evdev-Keycodes, z. B. KEY_F1")
p.add_argument("--delay", type=float, default=4.0, help="Sekunden warten, bis der Launcher das Gerät erkannt hat")
p.add_argument("--gap", type=float, default=3.0, help="Sekunden zwischen mehreren Tasten")
a = p.parse_args()

codes = [e.ecodes[k] for k in a.keys]
ui = UInput({e.EV_KEY: list(set(codes + [e.KEY_F1, e.KEY_F2, e.KEY_F3, e.KEY_F4, e.KEY_F5, e.KEY_F6, e.KEY_ESC]))},
            name="KITT Test Buttonbox")
time.sleep(max(a.delay, 1.0))   # mindestens 1 s, damit der Compositor das neue Gerät kennt, sonst geht die erste Taste verloren
for i, c in enumerate(codes):
    ui.write(e.EV_KEY, c, 1); ui.syn(); time.sleep(0.05)
    ui.write(e.EV_KEY, c, 0); ui.syn()
    print("gesendet:", a.keys[i])
    if i < len(codes) - 1:
        time.sleep(a.gap)
time.sleep(0.5)
ui.close()
