#!/usr/bin/env python3
"""LED-Board (WLED) prüfen, wenn es nicht tut, was der Launcher schickt: Erreichbarkeit, Version, LED-Anzahl,
Segmente, Playlist, Live-Status; dann drei Tests nacheinander (je 4 s): rot gedimmt per HTTP, rot voll per
HTTP, rot per UDP-Echtzeit (Stream wie aus den Szenen). Danach wird das Profil "home" gesetzt.

    .venv/bin/python scripts/wled_check.py            (auf dem Pi)

Erwartung: Test 1 dunkelrot, Test 2 hellrot, Test 3 hellrot mit einem laufenden dunklen Punkt. Bleibt das Board
bunt oder bewegt sich anders, steht in der Ausgabe davor, woran es liegt (Segmente, Playlist, lor, Live aus)."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launcher import wled  # noqa: E402


def get(host: str, port: int, path: str) -> dict:
    with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=4) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ctrl = wled._controller()
    if ctrl is None:
        print("wled.toml: [controller] enabled = false oder kein host")
        return 1
    host, port, _ = ctrl
    cfg = wled._load_cfg().get("controller", {})
    udp_port = int(cfg.get("udp_port", 21324))
    print(f"Controller {host}:{port}, UDP {udp_port}, dim {wled.dim()}")
    try:
        info = get(host, port, "/json/info")
    except Exception as exc:
        print(f"NICHT ERREICHBAR: {exc}")
        return 1
    n = int(info.get("leds", {}).get("count", 0))
    print(f"WLED {info.get('ver')} '{info.get('name')}', {n} LEDs, live={info.get('live')} ({info.get('lip', '')}), "
          f"fps={info.get('leds', {}).get('fps', '?')}")
    print(f"  -> LEDs 1-{n} werden angesteuert; hat die Kette mehr (Verpackung), bleiben die übrigen mit Zufallsfarben an:"
          f" scripts/wled_setup.py --leds <Anzahl> --apply")
    st = get(host, port, "/json/state")
    print(f"Zustand: on={st.get('on')} bri={st.get('bri')} Playlist={st.get('pl')} Preset={st.get('ps')} "
          f"lor={st.get('lor')} nl={st.get('nl', {}).get('on')}")
    for sg in st.get("seg", []):
        print(f"  Segment {sg.get('id')}: {sg.get('start')}-{sg.get('stop')} fx={sg.get('fx')} pal={sg.get('pal')} "
              f"col={sg.get('col')} bri={sg.get('bri')} on={sg.get('on')} frz={sg.get('frz')}")
    if len(st.get("seg", [])) > 1:
        print("  -> mehrere Segmente: der Launcher steuert nur Segment 0 und löscht die anderen beim nächsten Senden")
    if st.get("lor"):
        print("  -> lor (Live-Override) ist gesetzt: UDP-Echtzeit wird ignoriert, wird beim Senden auf 0 gesetzt")
    if st.get("pl", -1) not in (-1, None):
        print("  -> Playlist läuft: wird gestoppt")
    red = {"col": [255, 0, 0], "col2": [0, 0, 0], "fx": 0, "bri": 60, "pal": 2}
    print("Test 1: rot, Helligkeit 60 (HTTP) ...")
    wled.send(wled.payload_for({**red, "bri": int(60 / max(0.01, wled.dim()))}))
    time.sleep(4)
    print("Test 2: rot, Helligkeit 255 (HTTP) ...")
    wled.send(wled.payload_for({**red, "bri": int(255 / max(0.01, wled.dim()))}))
    time.sleep(4)
    if n > 0:
        print(f"Test 3: rot per UDP-Echtzeit, {n} LEDs, dunkler Punkt läuft (4 s) ...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4.0:
            k = int(((time.monotonic() - t0) * 8) % n)
            pixels = b"".join(bytes([0, 0, 0] if i == k else [255, 0, 0]) for i in range(n))
            if n <= 490:
                sock.sendto(bytes([2, 2]) + pixels, (host, udp_port))
            else:
                for start in range(0, n, 489):                          # DNRGB mit Startindex
                    sock.sendto(bytes([4, 2, (start >> 8) & 0xFF, start & 0xFF]) + pixels[start * 3:(start + 489) * 3], (host, udp_port))
            time.sleep(0.04)
        sock.close()
        try:
            live = get(host, port, "/json/info").get("live")
            print(f"  live={live} ({'WLED zeigt den Stream' if live else 'KEIN Live: in WLED Sync -> UDP-Echtzeit empfangen einschalten'})")
        except Exception as exc:
            print(f"  Status nicht lesbar: {exc}")
    print("Profil home ...")
    wled.apply_mode("home")
    return 0


if __name__ == "__main__":
    sys.exit(main())
