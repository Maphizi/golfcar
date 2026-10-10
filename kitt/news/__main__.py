"""Galaktische Nachrichten (Taste 3):  python -m kitt.news [--demo] [--beep] [--no-audio] [--seconds N] [--screenshot DATEI]
--demo: feste Meldungen ohne Server (Optik prüfen)."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from launcher import config as lcfg, logsetup  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--beep", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--seconds", type=float, default=0)
    ap.add_argument("--screenshot", default="")
    args = ap.parse_args()
    settings = lcfg.load_settings()
    logsetup.setup("news", lcfg.logs_dir(settings), settings.get("logging", {}).get("level", "INFO"))
    from kitt.news.app import NewsUI
    return NewsUI(demo=args.demo, tts_backend="beep" if args.beep else "piper", no_audio=args.no_audio).run(args.seconds, args.screenshot)


if __name__ == "__main__":
    sys.exit(main())
