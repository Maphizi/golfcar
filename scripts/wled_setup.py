#!/usr/bin/env python3
"""LED-Anzahl (und Strombegrenzung) im WLED-Controller setzen, wenn die Kette länger ist als eingestellt: LEDs hinter
der eingestellten Anzahl bekommen nie Daten und bleiben mit Zufallsfarben an.

    .venv/bin/python scripts/wled_setup.py                      zeigt die LED-Konfiguration (hw.led aus /json/cfg)
    .venv/bin/python scripts/wled_setup.py --leds 784 --apply   setzt die Länge des ersten LED-Ausgangs auf 784
    .venv/bin/python scripts/wled_setup.py --maxpwr 0 --apply   Strombegrenzung (ABL) aus (0) oder in mA, z. B. 5000

WLED speichert die Konfiguration und startet die LED-Ausgabe neu. Alternativ im Browser: WLED -> Config ->
LED Preferences -> Length (und "Maximum PSU current")."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launcher import wled  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leds", type=int, default=0, help="LED-Anzahl des ersten Ausgangs")
    ap.add_argument("--maxpwr", type=int, default=-1, help="Strombegrenzung in mA (0 = aus)")
    ap.add_argument("--apply", action="store_true", help="wirklich senden (sonst nur anzeigen)")
    args = ap.parse_args()
    ctrl = wled._controller()
    if ctrl is None:
        print("wled.toml: [controller] enabled = false oder kein host")
        return 1
    host, port, _ = ctrl
    url = f"http://{host}:{port}/json/cfg"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            cfg = json.loads(r.read().decode())
    except Exception as exc:
        print(f"{url}: {exc}")
        return 1
    led = cfg.get("hw", {}).get("led", {})
    ins = led.get("ins", [])
    print(f"Strombegrenzung maxpwr={led.get('maxpwr')} mA, LEDs gesamt {led.get('total')}")
    for i, out in enumerate(ins):
        print(f"  Ausgang {i}: start={out.get('start')} len={out.get('len')} pin={out.get('pin')} type={out.get('type')} "
              f"order={out.get('order')}")
    if not ins:
        print("Keine LED-Ausgänge in der Konfiguration gefunden")
        return 1
    payload: dict = {"hw": {"led": {}}}
    if args.leds > 0:
        new_ins = [dict(o) for o in ins]
        new_ins[0]["start"] = 0
        new_ins[0]["len"] = args.leds
        payload["hw"]["led"]["ins"] = new_ins
        payload["hw"]["led"]["total"] = args.leds + sum(int(o.get("len", 0)) for o in ins[1:])
    if args.maxpwr >= 0:
        payload["hw"]["led"]["maxpwr"] = args.maxpwr
    if not payload["hw"]["led"]:
        print("Nichts zu ändern (--leds N und/oder --maxpwr mA angeben)")
        return 0
    print("Senden:", json.dumps(payload))
    if not args.apply:
        print("(nur Anzeige; mit --apply wirklich setzen)")
        return 0
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print("Antwort:", r.read().decode()[:200])
    except Exception as exc:
        print(f"Senden fehlgeschlagen: {exc}")
        return 1
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/info", timeout=5) as r:
            info = json.loads(r.read().decode())
        print(f"Jetzt: {info.get('leds', {}).get('count')} LEDs")
    except Exception as exc:
        print(f"Info nicht lesbar (Controller startet neu?): {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
