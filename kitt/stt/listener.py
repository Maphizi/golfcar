"""Hört den Audiostrom ab und schneidet Äußerungen aus: IDLE -> LISTENING -> Äußerung fertig.

Eingang: 48-kHz-Blöcke vom AudioCapture. Intern 16 kHz, 32-ms-Chunks durch die VAD.
Ausgang: on_utterance(pcm16k: np.ndarray) und on_state("idle" | "listening").
"""
from __future__ import annotations

import logging
import time
from collections import deque

import numpy as np

from kitt.audio_utils import Decimator
from kitt.stt.vad import CHUNK, RATE

log = logging.getLogger("listener")


class Listener:
    def __init__(self, vad_cfg: dict, vad, on_utterance, on_state=None, rate_in: int = 48000, on_level=None):
        self.vad = vad
        self.on_utterance = on_utterance
        self.on_state = on_state or (lambda s: None)
        self.on_level = on_level or (lambda p: None)
        self.start_threshold = float(vad_cfg.get("start_threshold", 0.6))
        self.end_threshold = float(vad_cfg.get("end_threshold", 0.35))
        ms = CHUNK * 1000 / RATE
        self.start_chunks = max(1, int(float(vad_cfg.get("start_ms", 64)) / ms))
        self.end_chunks = max(1, int(float(vad_cfg.get("end_silence_ms", 700)) / ms))
        self.pre_chunks = max(1, int(float(vad_cfg.get("pre_roll_ms", 300)) / ms))
        self.min_chunks = max(1, int(float(vad_cfg.get("min_speech_ms", 300)) / ms))
        self.max_chunks = max(self.min_chunks, int(float(vad_cfg.get("max_speech_ms", 12000)) / ms))
        if rate_in % RATE:
            raise ValueError(f"Eingangsrate {rate_in} ist kein Vielfaches von {RATE}")
        self.decim = Decimator(rate_in // RATE) if rate_in != RATE else None
        self.pending = np.zeros(0, dtype=np.float32)
        self.pre = deque(maxlen=self.pre_chunks)
        self.speaking = False
        self.enabled = True
        self.utter: list[np.ndarray] = []
        self.speech_run = 0
        self.silence_run = 0
        self.started_at = 0.0

    def feed(self, samples: np.ndarray) -> None:
        x = self.decim.process(samples) if self.decim else samples.astype(np.float32)
        self.pending = np.concatenate((self.pending, x))
        while len(self.pending) >= CHUNK:
            chunk, self.pending = self.pending[:CHUNK], self.pending[CHUNK:]
            self._chunk(chunk)

    def pause(self) -> None:
        """Während KITT spricht nicht mithören (sonst hört er sich selbst)."""
        self.enabled = False
        self._abort()

    def resume(self) -> None:
        self.enabled = True
        self.vad.reset()
        self.pre.clear()
        self.pending = self.pending[:0]

    def _abort(self) -> None:
        if self.speaking:
            self.speaking = False
            self.utter = []
            self.on_state("idle")

    def _chunk(self, chunk: np.ndarray) -> None:
        if not self.enabled:
            return
        p = self.vad(chunk)
        self.on_level(p)
        if not self.speaking:
            self.pre.append(chunk)
            if p >= self.start_threshold:
                self.speech_run += 1
                if self.speech_run >= self.start_chunks:
                    self.speaking = True
                    self.utter = list(self.pre)
                    self.silence_run = 0
                    self.started_at = time.monotonic()
                    self.on_state("listening")
            else:
                self.speech_run = 0
            return
        self.utter.append(chunk)
        self.silence_run = self.silence_run + 1 if p < self.end_threshold else 0
        if self.silence_run >= self.end_chunks or len(self.utter) >= self.max_chunks:
            self._finish()

    def _finish(self) -> None:
        self.speaking = False
        self.speech_run = 0
        n_speech = len(self.utter) - self.silence_run
        audio = np.concatenate(self.utter) if self.utter else np.zeros(0, dtype=np.float32)
        self.utter = []
        self.on_state("idle")
        self.vad.reset()
        if n_speech < self.min_chunks + self.pre_chunks:
            log.debug("Zu kurz (%d Chunks), verworfen", n_speech)
            return
        log.info("Äußerung: %.2f s (Ende nach %.0f ms Stille)", len(audio) / RATE, self.silence_run * CHUNK * 1000 / RATE)
        self.on_utterance(audio)
