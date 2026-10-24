"""Vorgerenderte Ansagen: Piper einmal, danach nur noch WAV abspielen (keine Ladezeit im Launcher).

  python -m kitt.announce --build           alle Sätze aus config/announce.toml rendern (alle Themen, alle Stimmen)
  python -m kitt.announce --play boot       einen Satz der Gruppe abspielen (Test, Stimme des gewählten Themas)
  python -m kitt.announce --play boot green einen Satz der Gruppe im Thema green abspielen

Themen (config/themes.toml) können in announce.toml eine eigene Stimme und eigene Sätze haben:
  [themes.green]  voice = "de_DE-pavoque-low"  tts = { pitch_factor = 0.9, ... }
  [themes.green.lines]  boot = [...]  home = [...]  ...
Fehlt eine Gruppe im Thema, werden die Standardsätze genommen, aber mit der Themenstimme gesprochen.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import shutil
import subprocess
import sys
from pathlib import Path

from launcher import config as lcfg

log = logging.getLogger("announce")
OUT = lcfg.ROOT / "models" / "announce"
RECENT_FILE = lcfg.ROOT / "logs" / "announce_recent.json"   # zuletzt gespielte Sätze je Gruppe (über Neustarts hinweg)
_current: subprocess.Popen | None = None


def _replaced_modes(theme: str) -> set:
    """Modi, die das Thema durch eigene ersetzt (themes.toml modes): deren Standardsätze spielt das Thema nie."""
    try:
        for t in lcfg._load("themes.toml").get("themes", []):
            if t.get("name") == theme:
                return set((t.get("modes") or {}).keys())
    except Exception:
        pass
    return set()


def _pick(group_key: str, candidates: list) -> Path:
    """Zufällige Ansage, aber keine der zuletzt gespielten: gemerkt wird gut die Hälfte der Auswahl, damit sich derselbe
    Satz erst nach einigen anderen wiederholt."""
    try:
        recent = json.loads(RECENT_FILE.read_text())
    except (OSError, ValueError):
        recent = {}
    hist = [h for h in recent.get(group_key, []) if any(c.name == h for c in candidates)]
    keep = max(0, min(len(candidates) - 1, (len(candidates) + 1) // 2))
    fresh = [c for c in candidates if c.name not in hist[-keep:]] if keep else candidates
    path = random.choice(fresh or candidates)
    hist = (hist + [path.name])[-max(1, keep):]
    recent[group_key] = hist
    try:
        RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        RECENT_FILE.write_text(json.dumps(recent))
    except OSError:
        pass
    return path


def _cfg() -> dict:
    try:
        return lcfg._load("announce.toml")
    except Exception as exc:
        log.warning("announce.toml nicht lesbar: %s", exc)
        return {"enabled": False, "lines": {}}


def _theme_sets(cfg: dict) -> dict:
    """{themenname: {"voice": str, "tts": dict, "lines": dict}} aus announce.toml [themes.<name>]."""
    out = {}
    for name, sec in (cfg.get("themes") or {}).items():
        if not isinstance(sec, dict):
            continue
        out[name] = {"voice": str(sec.get("voice", "") or ""), "tts": dict(sec.get("tts", {}) or {}),
                     "lines": dict(sec.get("lines", {}) or {})}
    return out


def _wav_name(group: str, text: str, theme: str = "") -> Path:
    prefix = f"{theme}__" if theme else ""
    return OUT / f"{prefix}{group}_{hashlib.sha1(text.encode()).hexdigest()[:10]}.wav"


def _lines_for(cfg: dict, group: str, theme: str) -> tuple[list[str], str]:
    """(Sätze, Themenpräfix) für Gruppe und Thema: Themensätze, sonst Standardsätze in der Themenstimme."""
    base = cfg.get("lines", {}).get(group) or []
    sets = _theme_sets(cfg)
    if theme and theme in sets:
        ts = sets[theme]
        if group in ts["lines"]:
            return ts["lines"][group], theme
        if ts["voice"] or ts["tts"]:                                        # eigene Stimme: Standardsätze damit gesprochen
            return base, theme
    return base, ""


def _ensure_voice(voice: str, voices_dir: Path) -> bool:
    """Piper-Stimme nachladen, wenn sie fehlt (huggingface.co/rhasspy/piper-voices)."""
    if (voices_dir / f"{voice}.onnx").exists() and (voices_dir / f"{voice}.onnx.json").exists():
        return True
    print(f"  Stimme {voice} fehlt, lade nach ...")
    try:
        r = subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir", str(voices_dir), voice],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print(f"  FEHLER beim Laden von {voice}: {(r.stderr or r.stdout).strip()[-200:]}")
    except Exception as exc:
        print(f"  FEHLER beim Laden von {voice}: {exc}")
    return (voices_dir / f"{voice}.onnx").exists()


def build() -> int:
    from kitt import config as kcfg
    from kitt.audio_utils import write_wav
    from kitt.tts.piper_tts import PiperTTS
    cfg = _cfg()
    k = kcfg.load()
    voices_dir = kcfg.path(k["tts"]["voices_dir"])
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = set()
    n = 0
    jobs = [("", dict(k["tts"]), cfg.get("lines", {}))]                    # Standard: KITT-Stimme, Standardsätze
    for name, ts in _theme_sets(cfg).items():
        tcfg = {**k["tts"], **ts["tts"]}
        if ts["voice"]:
            tcfg["voice"] = ts["voice"]
        if ts["voice"] or ts["tts"]:                                       # eigene Stimme: alle Gruppen damit rendern
            skip = _replaced_modes(name) - set(ts["lines"])                # ersetzte Modi spielt das Thema nie
            groups = {g: (ts["lines"].get(g) or lines) for g, lines in cfg.get("lines", {}).items() if g not in skip}
            groups.update({g: l for g, l in ts["lines"].items() if g not in groups})
        else:                                                               # nur eigene Sätze, Rest kommt vom Standard
            groups = dict(ts["lines"])
        jobs.append((name, tcfg, groups))
    for theme, tcfg, groups in jobs:
        voice = tcfg.get("voice", "")
        if voice and not _ensure_voice(voice, voices_dir):
            print(f"  Thema {theme or 'standard'}: Stimme {voice} nicht verfügbar, nehme {k['tts'].get('voice')}")
            tcfg["voice"] = k["tts"].get("voice")
        tts = None
        for group, lines in groups.items():
            for text in lines:
                path = _wav_name(group, text, theme)
                wanted.add(path.name)
                if path.exists():
                    continue
                if tts is None:
                    tts = PiperTTS(tcfg, voices_dir)
                write_wav(str(path), tts.synth(text), tts.rate)
                n += 1
                print(f"  {theme + ': ' if theme else ''}{group}: {text!r} -> {path.name}")
    for old in OUT.glob("*.wav"):            # verwaiste Dateien (geänderte Texte) entfernen
        if old.name not in wanted:
            old.unlink()
    print(f"{n} neue Ansagen gerendert, {len(wanted)} gesamt in {OUT}")
    return 0


def play(group: str, target: str = "", theme: str | None = None) -> bool:
    """Spielt eine zufällige Ansage der Gruppe nicht-blockierend ab (Stimme und Sätze des Themas). False, wenn keine da ist."""
    global _current
    cfg = _cfg()
    if not cfg.get("enabled", True):
        return False
    if theme is None:
        try:
            from launcher import theme as ltheme
            theme = ltheme.current_name() or ""
        except Exception:
            theme = ""
    lines, prefix = _lines_for(cfg, group, theme or "")
    candidates = [c for c in (_wav_name(group, t, prefix) for t in lines) if c.exists()]
    if not candidates and prefix:                                           # Thema noch nicht gerendert: Standard
        base = cfg.get("lines", {}).get(group) or []
        candidates = [c for c in (_wav_name(group, t) for t in base) if c.exists()]
    if not candidates:
        return False
    path = _pick(f"{prefix or 'standard'}:{group}", candidates)
    if _current and _current.poll() is None:
        _current.kill()                      # laufende Ansage abbrechen
    vol = float(cfg.get("volume", 1.0))
    try:                                                                    # Grundlautstärke aller Sprecher + Drehknopf
        from kitt.tts.piper_tts import voice_volume
        vol *= voice_volume()
    except Exception:
        pass
    if shutil.which("pw-play"):
        vol_props = ["-P", f"media.volume={vol}"]
        cmd = ["pw-play"] + vol_props + (["--target", target] if target else []) + [str(path)]
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
        ok = play(argv[1], theme=argv[2] if len(argv) > 2 else None)
        print("abgespielt" if ok else "keine Ansage vorhanden (erst --build)")
        if _current:
            _current.wait()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
