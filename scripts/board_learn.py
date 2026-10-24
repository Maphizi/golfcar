#!/usr/bin/env python3
"""Schalter und Knöpfe des PXN-CB1 anlernen: fragt Schritt für Schritt ab (je Schritt ein Piepton, dann 6 s Zeit),
zeigt je Schritt die Rohereignisse und am Ende die fertigen Einträge für settings.toml / keymap.toml.

    .venv/bin/python scripts/board_learn.py            (auf dem Pi, der Launcher darf laufen; Lautsprecher an)
    .venv/bin/python scripts/board_learn.py --no-beep  ohne Piepton (dann nach der Uhr: alle 6 s der nächste Schritt)

Ablauf (nach jedem Piep genau EINE Sache tun):
  1. Hupen-Schalter auf die zweite Seite drücken (die, die noch keinen Ton macht)
  2. Kippschalter A nach unten legen
  3. Kippschalter A wieder nach oben
  4. Kippschalter B nach unten
  5. Kippschalter B wieder nach oben
  6. Drehknopf 1 ein paar Raster drehen (hin und zurück)
  7. Drehknopf 2 ein paar Raster drehen
Die Ausgabe bitte komplett posten (nicht zusammenfassen)."""
from __future__ import annotations

import math
import os
import select
import shutil
import struct
import subprocess
import sys
import time
import wave

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

STEPS = [
    ("horn2", "Hupen-Schalter auf die ZWEITE Seite drücken"),
    ("a_down", "Kippschalter A nach UNTEN"),
    ("a_up", "Kippschalter A wieder nach OBEN"),
    ("b_down", "Kippschalter B nach UNTEN"),
    ("b_up", "Kippschalter B wieder nach OBEN"),
    ("knob1", "Drehknopf 1 ein paar Raster drehen"),
    ("knob2", "Drehknopf 2 ein paar Raster drehen"),
]
STEP_S = 6.0
KNOWN = {266: "Startknopf", 267: "Kippschalter (Navigation)", 269: "Hupe Seite 1", 275: "Autopilot"}


def beep_file() -> str:
    p = "/tmp/board_learn_beep.wav"
    if not os.path.exists(p):
        sr, dur = 22050, 0.25
        with wave.open(p, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 880 * i / sr) * min(1.0, (dur * sr - i) / 2000)))
                              for i in range(int(sr * dur)))
            w.writeframes(frames)
    return p


def beep(times: int) -> None:
    p = beep_file()
    player = ["pw-play", p] if shutil.which("pw-play") else (["aplay", "-q", p] if shutil.which("aplay") else None)
    if not player:
        return
    for _ in range(times):
        subprocess.run(player, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.15)


def main() -> int:
    use_beep = "--no-beep" not in sys.argv
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
    # Ruhephase: 5 s NICHTS anfassen; alles, was trotzdem kommt, schickt das Board von selbst
    print("\nRuhephase: 5 s nichts anfassen ...", flush=True)
    idle: dict = {}
    t0 = time.monotonic()
    while time.monotonic() - t0 < 5.0:
        r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
        for d in devs:
            if d.fd in r:
                try:
                    for ev in d.read():
                        if ev.type in (ecodes.EV_SYN, ecodes.EV_MSC):
                            continue
                        idle.setdefault((d.path, ev.type, ev.code), []).append(ev.value)
                except OSError:
                    pass
    for (path, t, c), vals in sorted(idle.items()):
        name = ecodes.bytype.get(t, {}).get(c, c)
        uniq = sorted(set(vals))
        print(f"  von selbst: {path} {ecodes.EV.get(t, t)} {name}: {len(vals)} Ereignisse, Werte {uniq[:10]}"
              + ("  <- Stellungsgeber (Knopf), harmlos" if t == ecodes.EV_REL and len(uniq) == 1 else "")
              + ("  <- TASTE SENDET VON SELBST" if t == ecodes.EV_KEY else ""))
    if not idle:
        print("  nichts: das Board ist in Ruhe still")
    results: dict = {}
    for i, (key, text) in enumerate(STEPS, 1):
        print(f"\nSchritt {i}/{len(STEPS)}: {text}  ({STEP_S:.0f} s)", flush=True)
        if use_beep:
            beep(1 if i < len(STEPS) else 2)
        keys: list = []
        rel: dict = {}
        abs_: dict = {}
        t0 = time.monotonic()
        while time.monotonic() - t0 < STEP_S:
            r, _, _ = select.select([d.fd for d in devs], [], [], 0.2)
            for d in devs:
                if d.fd not in r:
                    continue
                try:
                    for ev in d.read():
                        if ev.type == ecodes.EV_KEY:
                            keys.append((ev.code, ev.value))
                        elif ev.type == ecodes.EV_REL:
                            rel.setdefault(ev.code, []).append(ev.value)
                        elif ev.type == ecodes.EV_ABS and ev.code not in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                            abs_.setdefault(ev.code, []).append(ev.value)
                except OSError:
                    pass
        results[key] = (keys, rel, abs_)
        if keys:
            seq = ", ".join(f"{c}{'(' + KNOWN[c] + ')' if c in KNOWN else ''}={v}" for c, v in keys[:12])
            print(f"  Tasten: {seq}")
        for c, vals in rel.items():
            uniq = []
            for v in vals:
                if not uniq or uniq[-1] != v:
                    uniq.append(v)
            print(f"  {ecodes.REL.get(c, c)}: {len(vals)} Ereignisse, Werteverlauf {uniq[:20]}{' ...' if len(uniq) > 20 else ''}")
        for c, vals in abs_.items():
            print(f"  {ecodes.ABS.get(c, c)}: {len(vals)} Ereignisse, {min(vals)}..{max(vals)}")
        if not keys and not rel and not abs_:
            print("  nichts angekommen")
    # Auswertung
    print("\n==== Ergebnis ====")

    def pressed(key: str) -> list:
        return [c for c, v in results[key][0] if v == 1 and c not in KNOWN]

    def released(key: str) -> list:
        return [c for c, v in results[key][0] if v == 0 and c not in KNOWN]

    h2 = pressed("horn2")
    if h2:
        print(f"settings.toml [buttons]:  horn2_code = {h2[0]}")
    else:
        print("Hupe Seite 2: kein neuer Code gesehen (vielleicht Code 269 selbst mit Wert 0/1?)")
    for name in ("a", "b"):
        down, up = pressed(f"{name}_down"), pressed(f"{name}_up")
        rel_down = released(f"{name}_up")
        if down and up and down[0] != up[0]:
            print(f"Kippschalter {name.upper()}: zwei Codes -> keymap.toml: code = {down[0]} (unten), code = {up[0]} (oben), je action = ...")
        elif down and (rel_down or not up):
            print(f"Kippschalter {name.upper()}: ein Code {down[0]} (unten = 1, oben = 0) -> keymap.toml: code = {down[0]} action = ... "
                  f"und code = {down[0]} on = \"up\" action = ...")
        else:
            print(f"Kippschalter {name.upper()}: unklar (unten {down}, oben {up}, losgelassen {rel_down})")
    for k in ("knob1", "knob2"):
        keys, rel, abs_ = results[k]
        kinds = []
        if any(c in (ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN) for c, _ in keys):
            kinds.append("KEY_VOLUMEUP/DOWN -> Musikknopf (music_knob.py)")
        for c, vals in rel.items():
            changed = len(set(vals)) > 1
            kinds.append(f"{ecodes.REL.get(c, c)} {'mit Änderung -> Stellungsgeber, taugt als Knopf' if changed else 'ohne Änderung -> war nicht dieser Knopf'}")
        for c in abs_:
            kinds.append(f"ABS-Achse {ecodes.ABS.get(c, c)} -> settings.toml axis = \"{ecodes.ABS.get(c, c)}\"")
        other = sorted({c for c, v in keys if v == 1 and c not in (ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN)})
        if other:
            kinds.append(f"Tastencodes {other} -> keymap voice_up/voice_down bzw. music_up/music_down")
        print(f"{k}: " + ("; ".join(kinds) if kinds else "nichts"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
