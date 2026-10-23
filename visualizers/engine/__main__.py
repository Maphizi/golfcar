"""Visualizer starten:  python -m visualizers.engine <psychedelic|crt|eye|campfire|error|...> [Optionen]

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
    t_main = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", choices=["psychedelic", "crt", "eye", "campfire", "kitt", "hyperspace", "target", "tactical", "navcomputer", "error", "slots", "taxi", "blackhole", "hal", "droid", "newsroom", "trip", "pond", "woodeye", "forestslots", "hearttree", "overdose", "neonrace", "core", "oracle", "cyberslots", "rooftop", "blackice", "timejump", "flux", "clocktower", "almanacslots", "square", "paradox", "splash"])
    ap.add_argument("--test-signal", action="store_true")
    ap.add_argument("--seconds", type=float, default=0.0)
    ap.add_argument("--screenshot", default="")
    ap.add_argument("--windowed", action="store_true")
    ap.add_argument("--source", choices=["mic", "playback"], help="überschreibt [capture].source")
    ap.add_argument("--demo", action="store_true", help="Szenen-Controller läuft automatisch (Tests)")
    ap.add_argument("--uniform", action="append", default=[], metavar="NAME=WERT",
                    help="setzt ein Shader-Uniform fest, z. B. uEventForce=3 oder uPos=0.5,0.2 (mehrfach möglich, Tests)")
    args = ap.parse_args()
    fixed: dict[str, float | tuple] = {}
    for item in args.uniform:
        name, _, val = item.partition("=")
        try:
            parts = tuple(float(v) for v in val.split(","))
            fixed[name.strip()] = parts[0] if len(parts) == 1 else parts
        except ValueError:
            ap.error(f"--uniform erwartet NAME=ZAHL oder NAME=Z1,Z2[,Z3[,Z4]], nicht {item!r}")
    if args.windowed:
        os.environ["KITT_VIZ_WINDOWED"] = "1"

    settings = config.load_settings()
    log = logsetup.setup(f"viz_{args.scene}", config.logs_dir(settings), settings.get("logging", {}).get("level", "INFO"))
    audio_cfg = config._load("audio.toml")
    viz_cfg = config._load("visualizer.toml")
    if args.test_signal:
        audio_cfg.setdefault("capture", {})["backend"] = "test"
    if args.source:
        audio_cfg.setdefault("capture", {})["source"] = args.source

    t_phase = time.monotonic()
    phases = []

    def phase(name):
        nonlocal t_phase
        now_ = time.monotonic()
        phases.append(f"{name} {now_ - t_phase:.1f}s")
        t_phase = now_

    import pygame
    from visualizers.engine import engine as eng
    phase("Imports")

    screen = eng.create_window(settings, viz_cfg, f"KITT VIZ {args.scene}")
    phase("Fenster")
    w, h = screen.get_size()
    scene_cfg = viz_cfg.get("scenes", {}).get(args.scene, {})
    # Optionaler Szenen-Controller (Eingabe, Zustand, Overlays), z. B. der Navigationscomputer
    ctrl = None
    ctrl_name = scene_cfg.get("controller", "")
    if ctrl_name:
        import importlib
        ctrl = importlib.import_module(f"visualizers.scenes.{ctrl_name}").Controller(scene_cfg, demo=args.demo)
        phase("Controller")
    scene = eng.Scene(args.scene, scene_cfg, bool(viz_cfg.get("engine", {}).get("hot_reload", True)),
                      (tuple(ctrl.uniform_names()) if ctrl else ()) + tuple(fixed))
    try:
        scene.load()
    except eng.GLError as exc:
        log.error("%s", exc)
        return 2
    phase("Shader")
    renderer = eng.Renderer(scene, w, h)
    overlays: dict[int, eng.TextOverlay] = {}
    image_versions: dict[str, int] = {}

    def sync_images() -> None:
        # Controller können Bilder liefern (z. B. Sprite-Atlas); hochgeladen wird nur bei neuer Version
        if not ctrl or not hasattr(ctrl, "images"):
            return
        for name, (img, version) in ctrl.images().items():
            if image_versions.get(name) != version:
                renderer.upload_image(name, img, 1 + list(ctrl.images().keys()).index(name))
                image_versions[name] = version

    def overlay(size_frac: float) -> eng.TextOverlay:
        px = max(10, int(h * size_frac))
        if px not in overlays:
            overlays[px] = eng.TextOverlay(px)
        return overlays[px]

    sync_images()
    phase("Bilder")
    cap = AudioCapture(audio_cfg)
    cap.start()
    phase("Audio")
    analyzer = Analyzer(cap.rate, audio_cfg)

    fps_cap = int(viz_cfg.get("engine", {}).get("fps_cap", 60))
    log_interval = float(viz_cfg.get("engine", {}).get("log_interval", 10))
    clock = pygame.time.Clock()
    t0 = time.monotonic()
    last_log = t0
    frames = 0
    shot_done = False
    first_logged = False
    under_launcher = bool(os.environ.get("KITT_MODE"))
    leds = None                                # LED-Board live zur Musik (nur unter dem Launcher oder KITT_LEDS=1)
    led_state_failed = False
    if under_launcher or os.environ.get("KITT_LEDS"):
        try:
            from launcher.ledstream import LedStream
            leds = LedStream(os.environ.get("KITT_MODE", args.scene), args.scene)
        except Exception:
            log.exception("LED-Stream nicht gestartet")
    banner = ""                                # Autopilot-Schalter (F16 AN / F17 AUS vom Launcher): kurze Anzeige
    banner_t0 = -1e9
    try:
        key_on, key_off = pygame.key.key_code("F16"), pygame.key.key_code("F17")
    except Exception:
        key_on, key_off = -1, -1
    rc = 0
    try:
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    raise KeyboardInterrupt
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and not under_launcher:
                    raise KeyboardInterrupt
                if ev.type == pygame.KEYDOWN and ev.key in (key_on, key_off):
                    banner, banner_t0 = ("AUTOPILOT AN" if ev.key == key_on else "AUTOPILOT AUS"), time.monotonic()
                    continue
                if ctrl:
                    ctrl.handle_event(ev)
            now = time.monotonic()
            t = now - t0
            f = analyzer.update(cap.latest(analyzer.n), now)
            scene.maybe_reload(now)
            renderer.upload_audio(f.spectrum, f.wave)
            sync_images()
            renderer.draw(t, f, {**(ctrl.uniforms(t, f) if ctrl else {}), **fixed})   # --uniform überstimmt den Controller
            if leds is not None:
                led_state = None
                if ctrl and callable(getattr(ctrl, "led_state", None)):
                    try:
                        led_state = ctrl.led_state()
                    except Exception:
                        if not led_state_failed:
                            log.exception("led_state der Szene (Stream läuft ohne Szenenzustand weiter)")
                        led_state_failed = True
                try:
                    leds.update(now, f, led_state)
                except Exception:
                    log.exception("LED-Stream")
                    leds = None
            if ctrl:
                for text, size_frac, x_frac, y_frac, color, alpha in ctrl.overlays(t):
                    ov = overlay(size_frac)
                    ov.set_text(text, color)
                    ov.draw(w, h, w * x_frac, h * y_frac, alpha, center=True)
            if now - banner_t0 < 2.5:
                a = min(1.0, (2.5 - (now - banner_t0)) / 0.6)
                ov = overlay(0.06)
                ov.set_text(banner, (120, 255, 200) if banner.endswith("AN") else (255, 120, 90))
                ov.draw(w, h, w * 0.5, h * 0.5, a, center=True)
            if args.screenshot and not shot_done and (t >= (args.seconds - 0.5 if args.seconds else 3.0)):
                renderer.screenshot(args.screenshot)   # vor dem Flip aus dem Back-Buffer
                shot_done = True
            pygame.display.flip()
            frames += 1
            if not first_logged:                       # frames wird je fps-Log zurückgesetzt, daher eigenes Flag
                first_logged = True
                phase("erstes Bild")
                log.info("Start %s: %s (gesamt %.1f s ab main)", args.scene, ", ".join(phases), time.monotonic() - t_main)
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
        if leds is not None:
            leds.stop()
        cap.stop()
        pygame.quit()
    return rc


if __name__ == "__main__":
    sys.exit(main())
