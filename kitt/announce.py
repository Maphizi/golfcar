"""Vorgerenderte Ansagen: Piper einmal, danach nur noch WAV abspielen (keine Ladezeit im Launcher).

  python -m kitt.announce --build      alle Sätze aus config/announce.toml rendern
  python -m kitt.announce --play boot  einen Satz der Gruppe abspielen (Test)
"""
from __future__ import annotations

import hashlib
import logging
import random
import shutil
import subprocess
import sys
from pathlib import Path

from launcher import config as lcfg

log = logging.getLogger("announce")
OUT = lcfg.ROOT / "models" / "announce"
_current: subprocess.Popen | None = None


def _cfg() -> dict:
    try:
        return lcfg._load("announce.toml")
    except Exception as exc:
        log.warning("announce.toml nicht lesbar: %s", exc)
        return {"enabled": False, "lines": {}}


def _wav_name(group: str, text: str) -> Path:
    return OUT / f"{group}_{hashlib.sha1(text.encode()).hexdigest()[:10]}.wav"


def build() -> int:
    from kitt import config as kcfg
    from kitt.audio_utils import write_wav
    from kitt.tts.piper_tts import PiperTTS
    cfg = _cfg()
    k = kcfg.load()
    tts = PiperTTS(k["tts"], kcfg.path(k["tts"]["voices_dir"]))
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = set()
    n = 0
    for group, lines in cfg.get("lines", {}).items():
        for text in lines:
            path = _wav_name(group, text)
            wanted.add(path.name)
            if path.exists():
                continue
            write_wav(str(path), tts.synth(text), tts.rate)
            n += 1
            print(f"  {group}: {text!r} -> {path.name}")
    for old in OUT.glob("*.wav"):            # verwaiste Dateien (geänderte Texte) entfernen
        if old.name not in wanted:
            old.unlink()
    print(f"{n} neue Ansagen gerendert, {len(wanted)} gesamt in {OUT}")
    return 0


def play(group: str, target: str = "") -> bool:
    """Spielt eine zufällige Ansage der Gruppe nicht-blockierend ab. False, wenn keine da ist."""
    global _current
    cfg = _cfg()
    if not cfg.get("enabled", True):
        return False
    lines = cfg.get("lines", {}).get(group) or []
    candidates = [_wav_name(group, t) for t in lines]
    candidates = [c for c in candidates if c.exists()]
    if not candidates:
        return False
    path = random.choice(candidates)
    if _current and _current.poll() is None:
        _current.kill()                      # laufende Ansage abbrechen
    if shutil.which("pw-play"):
        cmd = ["pw-play"] + (["--target", target] if target else []) + [str(path)]
    elif shutil.which("aplay"):
        cmd = ["aplay", "-q", str(path)]
    else:
        return False
    try:
        _current = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError as exc:
        log.warning("Ansage: %s", exc)
        return False


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    if argv[:1] == ["--build"]:
        return build()
    if argv[:1] == ["--play"] and len(argv) > 1:
        ok = play(argv[1])
        print("abgespielt" if ok else "keine Ansage vorhanden (erst --build)")
        if _current:
            _current.wait()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
