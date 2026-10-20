"""Generische Vollbildoberfläche für sprechende Figuren (Bord-Droide, Nachrichtensprecher):
GL-Szene mit eigenem Shader, Sprachpipeline in Threads, Overlays und Tasten je Figur.

Unterklassen setzen scene_name und uniform_names und überschreiben prepare_cfg (Persönlichkeit,
Stimme), extra_uniforms, draw_overlays, handle_key, tick und run_demo.
"""
from __future__ import annotations

import copy
import logging
import os
import signal
import threading
import time

import numpy as np

from kitt import config as kcfg
from kitt.ui.app import LABELS, STATES, TtsRing
from launcher import config as lcfg
from visualizers.engine.analysis import Analyzer

log = logging.getLogger("kitt.persona")


class PersonaUI:
    scene_name = "kitt"
    uniform_names: tuple[str, ...] = ("uState", "uStateT", "uLevel")
    window_title = "KITT"
    log_name = "persona"

    def __init__(self, demo: bool = False, tts_backend: str = "piper", no_audio: bool = False):
        self.settings = lcfg.load_settings()
        self.logs_dir = lcfg.logs_dir(self.settings)
        self.cfg = copy.deepcopy(kcfg.load())
        self.audio_cfg = lcfg._load("audio.toml")
        self.viz_cfg = lcfg._load("visualizer.toml")
        if no_audio:
            self.cfg["tts"]["player"] = "none"
        self.demo = demo
        self.tts_backend = tts_backend
        self.state = "loading"
        self.state_since = time.monotonic()
        self.level = 0.0
        self.last_user = ""
        self.last_kitt = ""
        self.text_until = 0.0
        self.lock = threading.Lock()
        self.rate = int(self.audio_cfg["capture"]["sample_rate"])
        self.tts_ring = TtsRing(self.rate)
        self.pipe = None
        self.running = True
        self.overlays: dict[int, object] = {}
        self.voice_rms = 0.0
        self.last_f = None
        self.music_cap = None
        self.w = self.h = 0
        self.prepare_cfg(self.cfg)

    # -- Hooks für Unterklassen -------------------------------------------
    def prepare_cfg(self, cfg: dict) -> None:
        """Persönlichkeit, Stimme und Hörverhalten dieser Figur in die Kopie der kitt.toml eintragen."""

    def extra_uniforms(self, now: float, state: str, since: float) -> dict:
        return {}

    def draw_overlays(self, now: float, state: str, lu: str, lk: str) -> None:
        pass

    def handle_key(self, key: int) -> None:
        pass

    def tick(self, now: float) -> None:
        pass

    def on_pipeline_ready(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def context_block(self) -> str:
        return ""

    # -- Callbacks aus der Pipeline (fremde Threads) ----------------------
    def on_state(self, s: str) -> None:
        with self.lock:
            self.state = s
            self.state_since = time.monotonic()
        if s == "idle":
            self.text_until = time.monotonic() + float(self.cfg.get("ui", {}).get("text_hold_s", 8))

    def on_text(self, role: str, text: str) -> None:
        with self.lock:
            if role == "user":
                self.last_user, self.last_kitt = text, ""
            else:
                self.last_kitt = (self.last_kitt + " " + text).strip()
            self.text_until = time.monotonic() + 60

    def on_level(self, p: float) -> None:
        self.level = p

    def on_audio(self, pcm: np.ndarray, rate: int) -> None:
        self.tts_ring.push(pcm, rate)

    # -- Pipeline ----------------------------------------------------------
    def start_pipeline(self) -> None:
        from kitt.voice.pipeline import VoicePipeline
        self.pipe = VoicePipeline(self.cfg, self.audio_cfg, self.logs_dir, on_state=self.on_state,
                                  on_text=self.on_text, on_level=self.on_level, on_audio=self.on_audio,
                                  tts_backend=self.tts_backend, use_mic=self.use_mic())
        try:
            self.pipe.start()
            if self.pipe.kitt is not None:
                prev = self.pipe.kitt.context_provider

                def provider() -> str:
                    parts = [prev() if prev else "", self.context_block()]
                    return "\n\n".join(p for p in parts if p)

                self.pipe.kitt.context_provider = provider
            self.on_pipeline_ready()
        except Exception:
            log.exception("Pipeline-Start fehlgeschlagen")
            self.on_state("stopped")

    def use_mic(self) -> bool:
        return True

    def music_source(self) -> str | None:
        """Eigene Musikquelle für die Szene ("playback" oder "mic"); None = Mikrofon/TTS wie bisher.
        Mit Musikquelle liefert uRms/uBass/... die Musik und uVoice den Pegel der eigenen Stimme."""
        return None

    def say(self, text: str) -> None:
        """Text sprechen (im Hintergrund), wenn die Pipeline bereit ist; sonst nur anzeigen."""
        self.on_text("kitt", text)
        if self.pipe and self.pipe.state not in ("init", "loading", "stopped") and not self.pipe.busy.is_set():
            threading.Thread(target=self.pipe.say, args=(text,), daemon=True).start()

    def ask_hidden(self, instruction: str, placeholder: str = "(schweigt)") -> bool:
        """Figur spricht von sich aus: Regieanweisung an das Sprachmodell, Antwort wird gesprochen."""
        if not (self.pipe and self.pipe.state == "idle" and not self.pipe.busy.is_set()):
            return False

        def run() -> None:
            self.pipe.busy.set()
            if self.pipe.listener:
                self.pipe.listener.pause()
            try:
                self.pipe.handle_text(instruction, hidden=placeholder)
            except Exception:
                log.exception("Eigeninitiative fehlgeschlagen")
                self.on_state("idle")
            finally:
                self.pipe._resume()

        threading.Thread(target=run, daemon=True).start()
        return True

    def run_demo(self) -> None:
        seq = [("loading", 2), ("idle", 4), ("listening", 3), ("thinking", 2), ("speaking", 4), ("idle", 3)]
        while self.running:
            for s, dur in seq:
                self.on_state(s)
                t0 = time.monotonic()
                while self.running and time.monotonic() - t0 < dur:
                    if s == "speaking":
                        t = np.arange(self.rate // 20) / self.rate
                        env = 0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * (time.monotonic() + t))
                        self.on_audio((0.4 * env * np.sin(2 * np.pi * 180 * t)).astype(np.float32), self.rate)
                    elif s == "listening":
                        self.level = 0.5 + 0.5 * np.sin(time.monotonic() * 5.0)
                    time.sleep(0.05)
                if not self.running:
                    break

    # -- Zeichnen ------------------------------------------------------------
    def overlay(self, size_frac: float):
        from visualizers.engine import engine as eng
        px = max(10, int(self.h * size_frac))
        if px not in self.overlays:
            self.overlays[px] = eng.TextOverlay(px)
        return self.overlays[px]

    def text(self, s: str, size_frac: float, x_frac: float, y_frac: float, color=(230, 230, 230), alpha: float = 1.0,
             center: bool = True) -> None:
        if not s:
            return
        ov = self.overlay(size_frac)
        ov.set_text(s, color)
        ov.draw(self.w, self.h, self.w * x_frac, self.h * y_frac, alpha, center=center)

    def wrap(self, s: str, max_chars: int) -> list[str]:
        words, lines, cur = s.split(), [], ""
        for wd in words:
            if len(cur) + len(wd) + 1 > max_chars and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = (cur + " " + wd).strip()
        if cur:
            lines.append(cur)
        return lines

    # -- Hauptschleife -----------------------------------------------------
    def run(self, seconds: float = 0.0, screenshot: str = "") -> int:
        import pygame
        from visualizers.engine import engine as eng
        screen = eng.create_window(self.settings, self.viz_cfg, self.window_title)
        self.w, self.h = screen.get_size()
        w, h = self.w, self.h
        scene_cfg = self.viz_cfg.get("scenes", {}).get(self.scene_name, {"shader": self.scene_name, "render_scale": 1.0})
        scene = eng.Scene(self.scene_name, scene_cfg, bool(self.viz_cfg.get("engine", {}).get("hot_reload", True)),
                          tuple(self.uniform_names))
        scene.load()
        renderer = eng.Renderer(scene, w, h)
        analyzer = Analyzer(self.rate, self.audio_cfg)
        voice_analyzer = Analyzer(self.rate, self.audio_cfg)
        self.music_cap = None
        src = self.music_source()
        if src and not self.demo:
            try:
                from visualizers.engine.audio_capture import AudioCapture
                self.music_cap = AudioCapture(self.audio_cfg, source=src)
                self.music_cap.start()
            except Exception:
                log.exception("Musikquelle nicht gestartet")
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        worker = threading.Thread(target=self.run_demo if self.demo else self.start_pipeline, daemon=True)
        worker.start()
        clock = pygame.time.Clock()
        fps_cap = int(self.viz_cfg.get("engine", {}).get("fps_cap", 60))
        t0 = time.monotonic()
        last_log = t0
        frames = 0
        shot_done = False
        under_launcher = bool(os.environ.get("KITT_MODE"))
        rc = 0
        try:
            while self.running:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and not under_launcher):
                        self.running = False
                    elif ev.type == pygame.KEYDOWN:
                        self.handle_key(ev.key)
                now = time.monotonic()
                t = now - t0
                self.tick(now)
                with self.lock:
                    state, since, lu, lk = self.state, self.state_since, self.last_user, self.last_kitt
                voice_rms = 0.0
                if self.music_cap is not None or (self.demo and src):
                    samples = self.music_cap.latest(analyzer.n) if self.music_cap else np.zeros(analyzer.n, dtype=np.float32)
                    fv = voice_analyzer.update(self.tts_ring.latest(voice_analyzer.n) if state == "speaking"
                                               else np.zeros(voice_analyzer.n, dtype=np.float32), now)
                    voice_rms = float(fv.rms)
                elif state == "speaking":
                    samples = self.tts_ring.latest(analyzer.n)
                elif self.pipe and self.pipe.cap:
                    samples = self.pipe.cap.latest(analyzer.n)
                else:
                    samples = np.zeros(analyzer.n, dtype=np.float32)
                f = analyzer.update(samples, now)
                self.voice_rms = voice_rms
                self.last_f = f
                scene.maybe_reload(now)
                renderer.upload_audio(f.spectrum, f.wave)
                uniforms = {"uState": STATES.get(state, 0), "uStateT": now - since, "uLevel": self.level}
                uniforms.update(self.extra_uniforms(now, state, since))
                renderer.draw(t, f, uniforms)
                self.draw_overlays(now, state, lu, lk)
                if screenshot and not shot_done and t >= (seconds - 0.5 if seconds else 3.0):
                    renderer.screenshot(screenshot)
                    shot_done = True
                pygame.display.flip()
                frames += 1
                if now - last_log >= 10:
                    log.info("fps %.1f state=%s rms=%.2f", frames / (now - last_log), state, f.rms)
                    last_log, frames = now, 0
                if seconds and t >= seconds:
                    break
                clock.tick(fps_cap)
        except Exception:
            log.exception("UI abgestürzt")
            rc = 1
        finally:
            self.running = False
            try:
                self.shutdown()
            except Exception:
                log.exception("Shutdown")
            if self.pipe:
                self.pipe.stop()
            if getattr(self, "music_cap", None):
                self.music_cap.stop()
            pygame.quit()
        return rc
