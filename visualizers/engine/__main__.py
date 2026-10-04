"""Visualizer starten:  python -m visualizers.engine <psychedelic|crt|eye|campfire> [Optionen]

Optionen:
  --test-signal        synthetisches Musiksignal statt Mikrofon
  --seconds N          nach N Sekunden beenden (Tests)
  --screenshot FILE    kurz vor dem Beenden (oder nach 3 s) ein Bild speichern
  --windowed           Fenster statt Vollbild (Entwicklung)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from launcher import config, logsetup  # noqa: E402
from visualizers.engine.analysis import Analyzer  # noqa: E402
from visualizers.engine.audio_capture import AudioCapture  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", choices=["psychedelic", "crt", "eye", "campfire", "kitt"])
    ap.add_argument("--test-signal", action="store_true")
    ap.add_argument("--seconds", type=float, default=0.0)
    ap.add_argument("--screenshot", default="")
    ap.add_argument("--windowed", action="store_true")
    args = ap.parse_args()
    if args.windowed:
        os.environ["KITT_VIZ_WINDOWED"] = "1"

    settings = config.load_settings()
    log = logsetup.setup(f"viz_{args.scene}", config.logs_dir(settings), settings.get("logging", {}).get("level", "INFO"))
    audio_cfg = config._load("audio.toml")
    viz_cfg = config._load("visualizer.toml")
    if args.test_signal:
        audio_cfg.setdefault("capture", {})["backend"] = "test"

    import pygame
    from visualizers.engine import engine as eng

    screen = eng.create_window(settings, viz_cfg, f"KITT VIZ {args.scene}")
    w, h = screen.get_size()
    scene = eng.Scene(args.scene, viz_cfg.get("scenes", {}).get(args.scene, {}), bool(viz_cfg.get("engine", {}).get("hot_reload", True)))
    try:
        scene.load()
    except eng.GLError as exc:
        log.error("%s", exc)
        return 2
    renderer = eng.Renderer(scene, w, h)

    cap = AudioCapture(audio_cfg)
    cap.start()
    analyzer = Analyzer(cap.rate, audio_cfg)

    fps_cap = int(viz_cfg.get("engine", {}).get("fps_cap", 60))
    log_interval = float(viz_cfg.get("engine", {}).get("log_interval", 10))
    clock = pygame.time.Clock()
    t0 = time.monotonic()
    last_log = t0
    frames = 0
    shot_done = False
    under_launcher = bool(os.environ.get("KITT_MODE"))
    rc = 0
    try:
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    raise KeyboardInterrupt
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and not under_launcher:
                    raise KeyboardInterrupt
            now = time.monotonic()
            t = now - t0
            f = analyzer.update(cap.latest(analyzer.n), now)
            scene.maybe_reload(now)
            renderer.upload_audio(f.spectrum, f.wave)
            renderer.draw(t, f)
            if args.screenshot and not shot_done and (t >= (args.seconds - 0.5 if args.seconds else 3.0)):
                renderer.screenshot(args.screenshot)   # vor dem Flip aus dem Back-Buffer
                shot_done = True
            pygame.display.flip()
            frames += 1
            if now - last_log >= log_interval:
                fps = frames / (now - last_log)
                log.info("fps %.1f  audio=%s level=%.4f rms=%.2f bass=%.2f mid=%.2f high=%.2f beat=%.2f%s",
                         fps, cap.active_backend, f.level, f.rms, f.bass, f.mid, f.high, f.beat, "  (Stille)" if f.silent else "")
                last_log, frames = now, 0
            if args.seconds and t >= args.seconds:
                break
            clock.tick(fps_cap)
    except KeyboardInterrupt:
        pass
    except Exception:
        log.exception("Visualizer abgestürzt")
        rc = 1
    finally:
        cap.stop()
        pygame.quit()
    return rc


if __name__ == "__main__":
    sys.exit(main())
