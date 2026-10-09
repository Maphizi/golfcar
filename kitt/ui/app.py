"""KITT-Vollbildoberfläche (F5): GL-Szene 'kitt' + Sprachpipeline in Threads.

Kein Chatfenster, keine Eingabe. Eine Readout-Zeile zeigt das letzte Transkript bzw. den
gesprochenen Satz (abschaltbar: [ui].show_text). Während KITT spricht, treibt das TTS-Signal
die Visualisierung, sonst das Mikrofon.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time

import numpy as np

from kitt import config as kcfg
from launcher import config as lcfg
from visualizers.engine.analysis import Analyzer

log = logging.getLogger("kitt.ui")
STATES = {"idle": 0, "listening": 1, "thinking": 2, "speaking": 3, "loading": 4, "init": 4, "stopped": 0}
LABELS = {"idle": "BEREIT", "listening": "EMPFANG", "thinking": "DROIDENKERN RECHNET", "speaking": "SENDE",
          "loading": "SYSTEME LADEN", "init": "SYSTEME LADEN", "stopped": "AUS"}


class TtsRing:
    """48-kHz-Ringpuffer für das TTS-Audio (Analyzer erwartet die Capture-Rate)."""

    def __init__(self, rate: int, seconds: float = 2.0):
        self.rate = rate
        self.buf = np.zeros(int(rate * seconds), dtype=np.float32)
        self.pos = 0
        self.lock = threading.Lock()

    def push(self, pcm: np.ndarray, src_rate: int) -> None:
        if src_rate != self.rate:
            n = int(len(pcm) * self.rate / src_rate)
            pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
        with self.lock:
            n = len(pcm)
            idx = np.arange(self.pos, self.pos + n) % len(self.buf)
            self.buf[idx] = pcm
            self.pos = (self.pos + n) % len(self.buf)

    def latest(self, n: int) -> np.ndarray:
        with self.lock:
            idx = np.arange(self.pos - n, self.pos) % len(self.buf)
            return self.buf[idx].copy()


class KittUI:
    def __init__(self, demo: bool = False, tts_backend: str = "piper", no_audio: bool = False):
        self.settings = lcfg.load_settings()
        self.logs_dir = lcfg.logs_dir(self.settings)
        self.cfg = kcfg.load()
        self.ui_cfg = self.cfg.get("ui", {})
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

    # -- Callbacks aus der Pipeline (fremde Threads) ----------------------
    def on_state(self, s: str) -> None:
        with self.lock:
            self.state = s
            self.state_since = time.monotonic()
        if s in ("idle",):
            self.text_until = time.monotonic() + float(self.ui_cfg.get("text_hold_s", 6))

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

    # -- Pipeline-Thread ---------------------------------------------------
    def start_pipeline(self) -> None:
        from kitt.voice.pipeline import VoicePipeline
        self.pipe = VoicePipeline(self.cfg, self.audio_cfg, self.logs_dir, on_state=self.on_state,
                                  on_text=self.on_text, on_level=self.on_level, on_audio=self.on_audio,
                                  tts_backend=self.tts_backend, use_mic=True)
        try:
            self.pipe.start()
            greeting = self.ui_cfg.get("greeting", "")
            if greeting:
                self.pipe.say(greeting)
        except Exception:
            log.exception("Pipeline-Start fehlgeschlagen")
            self.on_state("stopped")

    def run_demo(self) -> None:
        """Ohne Server: Zustände durchlaufen, damit die Optik ohne Hardware prüfbar ist."""
        seq = [("loading", 3), ("idle", 4), ("listening", 3), ("thinking", 2), ("speaking", 4), ("idle", 3)]
        self.on_text("user", "KITT, wie sieht's aus?")
        while self.running:
            for s, dur in seq:
                self.on_state(s)
                if s == "speaking":
                    self.on_text("kitt", "Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab.")
                t0 = time.monotonic()
                while self.running and time.monotonic() - t0 < dur:
                    if s == "speaking":       # synthetische Stimme: moduliertes Rauschen
                        t = np.arange(self.rate // 20) / self.rate
                        env = 0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * (time.monotonic() + t))
                        self.on_audio((0.4 * env * np.sin(2 * np.pi * 140 * t) * (1 + 0.5 * np.random.uniform(-1, 1, len(t)))).astype(np.float32), self.rate)
                    elif s == "listening":
                        self.level = 0.5 + 0.5 * np.sin(time.monotonic() * 5.0)
                    time.sleep(0.05)
                if not self.running:
                    break

    # -- Hauptschleife -----------------------------------------------------
    def run(self, seconds: float = 0.0, screenshot: str = "") -> int:
        import pygame
        from visualizers.engine import engine as eng
        screen = eng.create_window(self.settings, self.viz_cfg, "KITT")
        w, h = screen.get_size()
        scene = eng.Scene("kitt", self.viz_cfg.get("scenes", {}).get("kitt", {"shader": "kitt", "render_scale": 1.0}),
                          bool(self.viz_cfg.get("engine", {}).get("hot_reload", True)), ("uState", "uStateT", "uLevel"))
        scene.load()
        renderer = eng.Renderer(scene, w, h)
        show_text = bool(self.ui_cfg.get("show_text", True))
        overlay = eng.TextOverlay(int(h * 0.026)) if show_text else None
        label = eng.TextOverlay(int(h * 0.034))
        analyzer = Analyzer(self.rate, self.audio_cfg)
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
                now = time.monotonic()
                t = now - t0
                with self.lock:
                    state, since, lu, lk = self.state, self.state_since, self.last_user, self.last_kitt
                if state == "speaking":
                    samples = self.tts_ring.latest(analyzer.n)
                elif self.pipe and self.pipe.cap:
                    samples = self.pipe.cap.latest(analyzer.n)
                else:
                    samples = np.zeros(analyzer.n, dtype=np.float32)
                f = analyzer.update(samples, now)
                scene.maybe_reload(now)
                renderer.upload_audio(f.spectrum, f.wave)
                renderer.draw(t, f, {"uState": STATES.get(state, 0), "uStateT": now - since, "uLevel": self.level})
                # Zustandslabel und Readout-Zeile
                label.set_text(LABELS.get(state, state.upper()), (255, 214, 10))
                label.draw(w, h, w * 0.36, h * 0.66, 0.95, center=True)
                if overlay and now < self.text_until and (lu or lk):
                    line = (("> " + lu) if state in ("listening", "thinking") or not lk else ("KITT: " + lk))[-110:]
                    overlay.set_text(line, (255, 236, 120))
                    overlay.draw(w, h, w * 0.5, h * 0.025, 0.9, center=True)
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
            if self.pipe:
                self.pipe.stop()
            pygame.quit()
        return rc
