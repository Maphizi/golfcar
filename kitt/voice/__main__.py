"""KITT-Sprachpipeline (Phase 7), ohne Oberfläche:

  python -m kitt.voice                       Mikrofon-Betrieb, Zustände und Texte im Terminal
  python -m kitt.voice --say "Text"          nur Sprachausgabe
  python -m kitt.voice --text "Frage"        Frage per Text, Antwort wird gesprochen (ohne Mikrofon)
  python -m kitt.voice --texts-file DATEI    alle Zeilen der Datei nacheinander (Latenztest)
  --seconds N   nach N Sekunden beenden      --beep  Testtöne statt Piper      --no-audio  nichts abspielen
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kitt import config as kcfg  # noqa: E402
from kitt.voice.pipeline import VoicePipeline  # noqa: E402
from launcher import config as lcfg, logsetup  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--say")
    ap.add_argument("--text")
    ap.add_argument("--texts-file")
    ap.add_argument("--seconds", type=float, default=0)
    ap.add_argument("--beep", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    args = ap.parse_args()
    settings = lcfg.load_settings()
    logs_dir = lcfg.logs_dir(settings)
    logsetup.setup("kitt", logs_dir, settings.get("logging", {}).get("level", "INFO"))
    cfg = kcfg.load()
    audio_cfg = lcfg._load("audio.toml")
    if args.no_audio:
        cfg["tts"]["player"] = "none"
    use_mic = not (args.say or args.text or args.texts_file)
    pipe = VoicePipeline(cfg, audio_cfg, logs_dir,
                         on_state=lambda s: print(f"  [{time.strftime('%H:%M:%S')}] STATE {s.upper()}", flush=True),
                         on_text=lambda r, t: print(f"  {'Fahrer' if r == 'user' else 'KITT'}: {t}", flush=True),
                         tts_backend="beep" if args.beep else "piper", use_mic=use_mic)
    try:
        if args.say:
            pipe.tts = __import__("kitt.tts.piper_tts", fromlist=["PiperTTS"]).PiperTTS(
                cfg["tts"], kcfg.path(cfg["tts"]["voices_dir"]), audio_cfg.get("output", {}).get("target", ""),
                "beep" if args.beep else "piper")
            pipe.say(args.say)
            return 0
        pipe.start()
        if args.text:
            pipe.handle_text(args.text)
            return 0
        if args.texts_file:
            for line in open(args.texts_file, encoding="utf-8"):
                q = line.strip()
                if q and not q.startswith("#"):
                    print(f"  Fahrer: {q}", flush=True)
                    pipe.handle_text(q)
                    pipe.kitt.reset()
                    time.sleep(0.5)
            return 0
        print("KITT hört zu. Sprich ins Mikrofon. Strg+C beendet.", flush=True)
        t0 = time.monotonic()
        while not args.seconds or time.monotonic() - t0 < args.seconds:
            time.sleep(0.25)
            if pipe.cap and pipe.cap.active_backend == "none" and time.monotonic() - t0 > 6:
                print("Keine Audioquelle (scripts/audio_check.sh)", flush=True)
                return 3
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        pipe.stop()


if __name__ == "__main__":
    sys.exit(main())
