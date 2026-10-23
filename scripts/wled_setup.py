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
    .venv/bin/python scripts/wled_setup.py --white 0 --apply    Auto-Weiß des RGBW-Ausgangs: 0 aus (Weiß nur, wenn wir es
                                                                schicken; Pflicht für die Farben der Programme), 1 heller,
                                                                2 genau, 3 beides, 4 alt. Steht es nicht auf 0, wird aus
                                                                Gold oder Warmweiß ein weißes Leuchten.
    .venv/bin/python scripts/wled_setup.py --fix rot,weiss,gruen,blau --apply
                                                                rechnet aus dem Ergebnis von --test (gesehene Farbe bei
                                                                Test 1, 2, 3, 4) die passende Farbreihenfolge samt Weiß-Tausch
                                                                aus und setzt sie; danach --test wiederholen.
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


ORDERS = ("GRB", "RGB", "BRG", "RBG", "BGR", "GBR")
SWAPS = {0: "", 1: "B", 2: "G", 3: "R"}            # oberes Nibble: W tauscht mit B / G / R


def _color_key(v: str):
    v = v.strip().lower().replace("ü", "u").replace("ß", "ss")
    for key, names in (("R", ("rot", "red", "r")), ("G", ("gruen", "grun", "green", "g")), ("B", ("blau", "blue", "b")),
                       ("W", ("weiss", "weis", "white", "w"))):
        if v in names:
            return key
    return None


def _positions(order: int) -> dict:
    """Byteposition je logischer Farbe (R, G, B, W) für einen WLED-order-Wert."""
    base = ORDERS[order & 0x0F] if (order & 0x0F) < len(ORDERS) else "GRB"
    pos = {c: base.index(c) for c in "RGB"}
    pos["W"] = 3
    sw = SWAPS.get(order >> 4, "")
    if sw:
        pos[sw], pos["W"] = pos["W"], pos[sw]
    return pos


def _order_name(order: int) -> str:
    base = ORDERS[order & 0x0F] if (order & 0x0F) < len(ORDERS) else "?"
    sw = SWAPS.get(order >> 4, "")
    return base + ("W" if not sw else f"W, W<->{sw}")


def _solve_order(cur: int, seen: list) -> int | None:
    """seen[i] = gesehener Chip bei Test i (logisch R, G, B, W). Gesucht: order, bei dem jede Farbe auf ihrem Chip landet."""
    logical = "RGBW"
    pos_cur = _positions(cur)
    chip_at = {pos_cur[logical[i]]: seen[i] for i in range(4)}       # Byteposition -> physischer Chip
    want = {chip: p for p, chip in chip_at.items()}                   # Chip -> Byteposition, die ihn erreicht
    for o in range(6):
        for sw in range(4):
            cand = o | (sw << 4)
            if all(_positions(cand)[c] == want[c] for c in logical):
                return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leds", type=int, default=0, help="LED-Anzahl des ersten Ausgangs")
    ap.add_argument("--maxpwr", type=int, default=-1, help="Strombegrenzung in mA (0 = aus)")
    ap.add_argument("--order", type=int, default=-1, help="Farbreihenfolge 0 GRB, 1 RGB, 2 BRG, 3 RBG, 4 BGR, 5 GBR")
    ap.add_argument("--type", type=int, default=-1, help="LED-Typ: 22 WS2812 RGB, 30 SK6812 RGBW, 24 WS2811 400k, 31 TM1814")
    ap.add_argument("--white", type=int, default=-1, help="Auto-Weiß je Ausgang: 0 aus, 1 heller, 2 genau, 3 beides, 4 alt")
    ap.add_argument("--fix", default="", help="gesehene Farben bei Test 1-4, z. B. rot,weiss,gruen,blau")
    ap.add_argument("--test", action="store_true", help="Farbtest rot/grün/blau je 4 s")
    ap.add_argument("--apply", action="store_true", help="wirklich senden (sonst nur anzeigen)")
    args = ap.parse_args()
    if args.test:
        import time
        for name, col in (("1 ROT", [255, 0, 0, 0]), ("2 GRÜN", [0, 255, 0, 0]), ("3 BLAU", [0, 0, 255, 0]), ("4 WEISS (nur W-Kanal)", [0, 0, 0, 255])):
            print(f"Test {name}: Jetzt sollte die ganze Kette {name.split(' ', 1)[1]} sein ... (5 s)")
            payload = wled.payload_for({"col": [0, 0, 0], "col2": [0, 0, 0], "fx": 0, "bri": int(120 / max(0.01, wled.dim())), "pal": 2})
            payload["seg"][0]["col"] = [col, [0, 0, 0, 0], [0, 0, 0, 0]]
            wled.send(payload)
            time.sleep(5)
        print("Bitte melden, welche Farbe bei 1, 2, 3 und 4 wirklich zu sehen war (z. B. '1 grün, 2 weiß, 3 blau, 4 rot').")
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
        whites = {0: "aus", 1: "heller", 2: "genau", 3: "beides", 4: "alt"}
        print(f"  Ausgang {i}: start={out.get('start')} len={out.get('len')} pin={out.get('pin')} type={out.get('type')} "
              f"({types.get(out.get('type'), '?')}) order={out.get('order')} ({names.get(out.get('order'), '?')}) "
              f"auto-weiß={out.get('rgbwm')} ({whites.get(out.get('rgbwm'), '?')})")
    print(f"Auto-Weiß global (alte Versionen): {led.get('rgbwm')}")
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
    if args.fix:
        seen = [_color_key(v) for v in args.fix.replace(";", ",").split(",")]
        if len(seen) != 4 or None in seen or len(set(seen)) != 4:
            print("--fix braucht vier verschiedene Farben aus rot, gruen, blau, weiss (gesehen bei Test 1, 2, 3, 4)")
            return 1
        cur = int(ins[0].get("order", 0))
        new = _solve_order(cur, seen)
        if new is None:
            print("Keine Reihenfolge gefunden, die das ergibt; bitte den Test wiederholen")
            return 1
        print(f"Reihenfolge: aktuell {cur} ({_order_name(cur)}) -> neu {new} ({_order_name(new)})")
        args.order = new
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
        if args.type == 30 and args.white < 0:
            args.white = 0                                         # Weißkanal nicht automatisch aus RGB rechnen
    if args.white >= 0:
        new_ins = payload["hw"]["led"].get("ins") or [dict(o) for o in ins]
        for o in new_ins:
            o["rgbwm"] = args.white                                # je Ausgang (WLED >= 0.14)
        payload["hw"]["led"]["ins"] = new_ins
        payload["hw"]["led"]["rgbwm"] = args.white                 # global (ältere Versionen)
    if not payload["hw"]["led"]:
        print("Nichts zu ändern (--leds, --maxpwr, --type, --order oder --white angeben)")
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
