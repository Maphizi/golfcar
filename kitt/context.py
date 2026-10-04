"""Bordbuch: kleine Fakten, die KITT wirklich kennt (zuletzt gespielte Spiele, Uhrzeit, Laufzeit).
Wird je Anfrage als kurzer Block an den System-Prompt gehängt."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from launcher import config as lcfg

GAMES = lcfg.ROOT / "logs" / "games.jsonl"
SYSTEMS = {"snes": "Super Nintendo", "nes": "NES", "megadrive": "Mega Drive", "gb": "Game Boy",
           "gbc": "Game Boy Color", "gba": "Game Boy Advance", "psx": "PlayStation"}


def _title(rom: str) -> str:
    t = re.sub(r"\.[A-Za-z0-9]+$", "", rom)
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", t)          # (Europe) [!] usw.
    return t.strip() or rom


def game_stats() -> dict:
    """Letztes Spiel, Dauer, Anzahl Sessions heute. Leer, wenn nichts protokolliert."""
    if not GAMES.exists():
        return {}
    events = []
    try:
        for line in open(GAMES, encoding="utf-8"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return {}
    starts = [e for e in events if e.get("event") == "start"]
    if not starts:
        return {}
    last = starts[-1]
    end = next((e for e in reversed(events) if e.get("event") == "end" and e.get("rom") == last.get("rom")
                and e.get("ts", 0) >= last.get("ts", 0)), None)
    minutes = int((end["ts"] - last["ts"]) / 60) if end else None
    day0 = time.time() - (time.time() % 86400)
    today = sum(1 for e in starts if e.get("ts", 0) >= day0)
    counts: dict[str, int] = {}
    for e in starts:
        counts[e.get("rom", "?")] = counts.get(e.get("rom", "?"), 0) + 1
    fav = max(counts, key=counts.get)
    return {"title": _title(last.get("rom", "?")), "system": SYSTEMS.get(last.get("system", ""), last.get("system", "")),
            "when": time.strftime("%d.%m. %H:%M", time.localtime(last.get("ts", 0))), "minutes": minutes,
            "running": end is None, "today": today, "favorite": _title(fav), "favorite_count": counts[fav]}


DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def context_block() -> str:
    lt = time.localtime()
    lines = [f"Uhrzeit laut Bordcomputer: {time.strftime('%H:%M', lt)}, {DAYS[lt.tm_wday]}, {lt.tm_mday}. {MONTHS[lt.tm_mon - 1]}."]
    try:
        up = float(open("/proc/uptime").read().split()[0])
        lines.append(f"Bordcomputer läuft seit {int(up // 3600)} h {int(up % 3600 // 60)} min.")
    except OSError:
        pass
    g = game_stats()
    if g:
        s = f"Zuletzt gespielt: {g['title']} ({g['system']}), {g['when']}"
        if g["running"]:
            s += ", läuft gerade"
        elif g["minutes"] is not None:
            s += f", {g['minutes']} Minuten"
        s += f". Heute {g['today']} Spielsitzung(en). Meistgespielt: {g['favorite']} ({g['favorite_count']}x)."
        lines.append(s)
    else:
        lines.append("Bisher wurde kein Spiel gestartet.")
    return "Fakten, die du kennst (nur diese, nichts dazu erfinden):\n" + "\n".join("- " + l for l in lines)
