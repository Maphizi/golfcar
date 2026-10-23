#!/usr/bin/env python3
"""LED-Anzahl (und Strombegrenzung) im WLED-Controller setzen, wenn die Kette länger ist als eingestellt: LEDs hinter
der eingestellten Anzahl bekommen nie Daten und bleiben mit Zufallsfarben an.

    .venv/bin/python scripts/wled_setup.py                      zeigt die LED-Konfiguration (hw.led aus /json/cfg)
    .venv/bin/python scripts/wled_setup.py --leds 784 --apply   setzt die Länge des ersten LED-Ausgangs auf 784
    .venv/bin/python scripts/wled_setup.py --maxpwr 0 --apply   Strombegrenzung (ABL) aus (0) oder in mA, z. B. 5000
    .venv/bin/python scripts/wled_setup.py --test               Farbtest: 4 s ROT, 4 s GRÜN, 4 s BLAU auf der ganzen Kette
    .venv/bin/python scripts/wled_setup.py --type 30 --apply    LED-Typ: 22 WS2812/WS2815 (3 Kanäle RGB), 30 SK6812 RGBW
                                                                (4 Kanäle, "5PIN"-Streifen), 24 WS2811 400 kHz, 31 TM1814.
                                                                Zeigt die Kette bei reinem Rot ein Muster Rot/Weiß/Blau/Grün,
                                                                hat sie 4 Kanäle und WLED steht auf 3: --type 30.
    .venv/bin/python scripts/wled_setup.py --order 1 --apply    Farbreihenfolge: 0 GRB (WS2812), 1 RGB (viele 24-V-Ketten),
                                                                2 BRG, 3 RBG, 4 BGR, 5 GBR. Zeigt der Test statt ROT ein GRÜN,
                                                                ist die Reihenfolge falsch (GRB <-> RGB).

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
    ap.add_argument("--order", type=int, default=-1, help="Farbreihenfolge 0 GRB, 1 RGB, 2 BRG, 3 RBG, 4 BGR, 5 GBR")
    ap.add_argument("--type", type=int, default=-1, help="LED-Typ: 22 WS2812 RGB, 30 SK6812 RGBW, 24 WS2811 400k, 31 TM1814")
    ap.add_argument("--test", action="store_true", help="Farbtest rot/grün/blau je 4 s")
    ap.add_argument("--apply", action="store_true", help="wirklich senden (sonst nur anzeigen)")
    args = ap.parse_args()
    if args.test:
        import time
        for name, col in (("ROT", [255, 0, 0]), ("GRÜN", [0, 255, 0]), ("BLAU", [0, 0, 255])):
            print(f"Jetzt sollte die ganze Kette {name} sein ...")
            wled.send(wled.payload_for({"col": col, "col2": [0, 0, 0], "fx": 0, "bri": int(120 / max(0.01, wled.dim())), "pal": 2}))
            time.sleep(4)
        wled.apply_mode("home")
        print("Stimmt die Farbe nicht (z. B. GRÜN statt ROT): --order 1 --apply (RGB) bzw. --order 0 --apply (GRB)")
        return 0
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
        names = {0: "GRB", 1: "RGB", 2: "BRG", 3: "RBG", 4: "BGR", 5: "GBR"}
        types = {22: "WS2812 RGB", 30: "SK6812 RGBW", 24: "WS2811 400k", 31: "TM1814", 26: "UCS8903", 29: "UCS8904"}
        print(f"  Ausgang {i}: start={out.get('start')} len={out.get('len')} pin={out.get('pin')} type={out.get('type')} "
              f"({types.get(out.get('type'), '?')}) order={out.get('order')} ({names.get(out.get('order'), '?')})")
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
    if args.order >= 0:
        new_ins = payload["hw"]["led"].get("ins") or [dict(o) for o in ins]
        for o in new_ins:
            o["order"] = args.order
        payload["hw"]["led"]["ins"] = new_ins
    if args.type >= 0:
        new_ins = payload["hw"]["led"].get("ins") or [dict(o) for o in ins]
        for o in new_ins:
            o["type"] = args.type
        payload["hw"]["led"]["ins"] = new_ins
        if args.type == 30:
            payload["hw"]["led"]["rgbwm"] = 0                      # Weißkanal nicht automatisch aus RGB rechnen
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
    import time
    time.sleep(2.0)
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/info", timeout=5) as r:
            info = json.loads(r.read().decode())
        n = int(info.get("leds", {}).get("count", 0))
        print(f"Jetzt: {n} LEDs")
        if n > 0:                                                  # Segment 0 sofort über die ganze Kette, sonst endet es beim alten Wert
            wled.send({"seg": [{"id": 0, "start": 0, "stop": n, "grp": 1, "spc": 0}]}, f"Segment 0 = 0-{n}")
            print(f"Segment 0 auf 0-{n} gesetzt. Launcher neu starten: systemctl --user restart kitt-launcher.service")
    except Exception as exc:
        print(f"Info nicht lesbar (Controller startet neu?): {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
