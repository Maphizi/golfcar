"""Sprachausgabe mit Piper (piper-tts, Python-API) und Streaming-Wiedergabe über PipeWire/ALSA.

Die Stimme bleibt geladen. Sätze werden einzeln synthetisiert und sofort abgespielt; jeder
Audio-Block geht zusätzlich an on_audio(float32, rate) für die Visualisierung.
Backend "beep" erzeugt statt Sprache Töne (Tests ohne Stimme).
"""
from __future__ import annotations

import logging
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("tts")


class Player:
    """Ein Wiedergabeprozess pro Antwort: rohe S16-Samples auf stdin."""

    def __init__(self, rate: int, player: str = "auto", target: str = ""):
        self.rate = rate
        self.proc: subprocess.Popen | None = None
        self.kind = "none"
        if player in ("auto", "pw-play") and shutil.which("pw-play"):
            cmd = ["pw-play", "--raw", "--rate", str(rate), "--channels", "1", "--format", "s16"]
            if target:
                cmd += ["--target", target]
            self.cmd, self.kind = cmd + ["-"], "pw-play"
        elif player in ("auto", "aplay") and shutil.which("aplay"):
            dev = target if (player == "aplay" and target) else "default"
            self.cmd, self.kind = ["aplay", "-q", "-D", dev, "-t", "raw", "-f", "S16_LE", "-r", str(rate), "-c", "1", "-"], "aplay"
        else:
            self.cmd = None

    def start(self) -> None:
        if self.cmd:
            self.proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def write(self, pcm: np.ndarray) -> None:
        if self.proc and self.proc.stdin:
            try:
                self.proc.stdin.write((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
            except (BrokenPipeError, OSError):
                log.warning("Wiedergabe abgebrochen (%s)", self.kind)
                self.proc = None

    def finish(self) -> None:
        """stdin schließen und warten, bis alles abgespielt ist."""
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=30)
            except Exception:
                self.proc.kill()
            self.proc = None

    def abort(self) -> None:
        if self.proc:
            self.proc.kill()
            self.proc = None


class PiperTTS:
    def __init__(self, cfg: dict, voices_dir: Path, output_target: str = "", backend: str = "piper"):
        self.cfg = cfg
        self.backend = backend
        self.voices_dir = voices_dir
        self.voice_name = cfg.get("voice", "de_DE-thorsten-medium")
        self.length_scale = float(cfg.get("length_scale", 1.0))
        self.pitch_factor = float(cfg.get("pitch_factor", 1.0))
        self.sentence_silence = float(cfg.get("sentence_silence", 0.15))
        self.volume = float(cfg.get("volume", 1.0))
        self.player_kind = cfg.get("player", "auto")
        self.output_target = output_target
        self.voice = None
        self.rate = 22050
        if backend == "piper":
            self._load()
        else:
            log.warning("TTS-Backend '%s': nur Testtöne", backend)

    def _load(self) -> None:
        from piper import PiperVoice
        model = self.voices_dir / f"{self.voice_name}.onnx"
        if not model.exists():
            raise FileNotFoundError(f"Piper-Stimme fehlt: {model} (scripts/setup_phase7.sh)")
        t0 = time.monotonic()
        self.voice = PiperVoice.load(model, model.with_suffix(".onnx.json"))
        self.rate = int(self.voice.config.sample_rate)
        log.info("Piper-Stimme %s geladen in %.1fs (%d Hz)", self.voice_name, time.monotonic() - t0, self.rate)

    # -- Synthese -------------------------------------------------------
    def synth(self, text: str) -> np.ndarray:
        """Ein Satz -> float32-PCM mit self.rate (nach Pitch-Anpassung)."""
        if self.backend != "piper" or self.voice is None:
            return self._beep(text)
        from piper import SynthesisConfig
        cfg = SynthesisConfig(length_scale=self.length_scale, volume=self.volume)
        parts = [np.asarray(ch.audio_float_array, dtype=np.float32) for ch in self.voice.synthesize(text, cfg)]
        pcm = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
        if self.pitch_factor != 1.0 and len(pcm):
            # langsamer abspielen = tiefer: Samples strecken, Rate bleibt
            n = int(len(pcm) / self.pitch_factor)
            pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
        if self.sentence_silence > 0:
            pcm = np.concatenate((pcm, np.zeros(int(self.rate * self.sentence_silence), dtype=np.float32)))
        return pcm

    def _beep(self, text: str) -> np.ndarray:
        dur = 0.25 + 0.04 * len(text)
        t = np.arange(int(self.rate * dur)) / self.rate
        f = 180.0 + 20.0 * (hash(text) % 7)
        env = np.minimum(1.0, t * 20) * np.minimum(1.0, (dur - t) * 20)
        return (0.3 * env * np.sin(2 * np.pi * f * t) * (1 + 0.3 * np.sin(2 * np.pi * 6 * t))).astype(np.float32)

    # -- Sprecher: Queue von Sätzen, Synthese + Wiedergabe in einem Thread ---
    def speaker(self, on_audio=None, on_done=None) -> "Speaker":
        return Speaker(self, on_audio, on_done)


class Speaker:
    """Nimmt Sätze entgegen (feed), synthetisiert und spielt sie der Reihe nach. end() schließt ab."""

    def __init__(self, tts: PiperTTS, on_audio=None, on_done=None):
        self.tts = tts
        self.on_audio = on_audio or (lambda pcm, rate: None)
        self.on_done = on_done or (lambda: None)
        self.q: queue.Queue = queue.Queue()
        self.player = Player(tts.rate, tts.player_kind, tts.output_target)
        self.aborted = False
        self.first_audio_at = 0.0
        self.started = time.monotonic()
        self.thread = threading.Thread(target=self._run, name="tts-speaker", daemon=True)
        self.thread.start()

    def feed(self, sentence: str) -> None:
        self.q.put(sentence)

    def end(self) -> None:
        self.q.put(None)

    def abort(self) -> None:
        self.aborted = True
        self.q.put(None)
        self.player.abort()

    def _run(self) -> None:
        self.player.start()
        try:
            while True:
                s = self.q.get()
                if s is None or self.aborted:
                    break
                t0 = time.monotonic()
                pcm = self.tts.synth(s)
                if not self.first_audio_at:
                    self.first_audio_at = time.monotonic()
                log.info("TTS %.2fs für %.1fs Audio: %r", time.monotonic() - t0, len(pcm) / self.tts.rate, s)
                # in Blöcken schreiben, damit die Visualisierung mitläuft
                step = self.tts.rate // 20
                for i in range(0, len(pcm), step):
                    if self.aborted:
                        break
                    blk = pcm[i:i + step]
                    self.player.write(blk)
                    self.on_audio(blk, self.tts.rate)
            if not self.aborted:
                self.player.finish()
        except Exception:
            log.exception("Sprecher-Thread")
        finally:
            self.on_done()
