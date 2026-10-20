#!/usr/bin/env python3
"""LED-Buttonboard (WLED) von Hand steuern, zum Ausprobieren von Farben und Effekten.

    scripts/wledctl.py list                         alle Profile aus config/wled.toml
    scripts/wledctl.py mode hal                     Profil eines Modus/Ereignisses senden
    scripts/wledctl.py set --col 0,255,0 --fx 2 --bri 200 [--sx 80] [--ix 128] [--col2 R,G,B] [--pal N]
                                                    direkt senden, nichts wird gespeichert
Gefällt eine Kombination, die Werte in config/wled.toml beim passenden [modes.<name>] eintragen.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launcher import wled  # noqa: E402


def rgb(s: str) -> list[int]:
    parts = [int(v) for v in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Farbe als R,G,B (0-255)")
    return parts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    m = sub.add_parser("mode")
    m.add_argument("name")
    s = sub.add_parser("set")
    s.add_argument("--col", type=rgb, default=[255, 255, 255])
    s.add_argument("--col2", type=rgb, default=None)
    s.add_argument("--col3", type=rgb, default=None)
    s.add_argument("--fx", type=int, default=0)
    s.add_argument("--bri", type=int, default=150)
    s.add_argument("--sx", type=int, default=128)
    s.add_argument("--ix", type=int, default=128)
    s.add_argument("--pal", type=int, default=None)
    args = ap.parse_args()
    if args.cmd == "list":
        for name, prof in wled.profiles().items():
            print(f"{name:<20} fx={prof.get('fx', 0):<4} bri={prof.get('bri', 128):<4} col={prof.get('col')}"
                  f"{'  col2=' + str(prof['col2']) if 'col2' in prof else ''}{'  pal=' + str(prof['pal']) if 'pal' in prof else ''}")
        return 0
    if args.cmd == "mode":
        ok = wled.apply_mode(args.name)
        print("gesendet" if ok else f"nicht gesendet (Profil '{args.name}' fehlt oder Controller nicht erreichbar)")
        return 0 if ok else 1
    prof = {"col": args.col, "fx": args.fx, "bri": args.bri, "sx": args.sx, "ix": args.ix}
    if args.col2:
        prof["col2"] = args.col2
    if args.col3:
        prof["col3"] = args.col3
    if args.pal is not None:
        prof["pal"] = args.pal
    ok = wled.send(wled.payload_for(prof), f"Test fx={args.fx} col={args.col}")
    print("gesendet" if ok else "nicht gesendet (Controller nicht erreichbar)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
