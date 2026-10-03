"""Kleine Audio-Helfer ohne externe Abhängigkeiten: Dezimation 48k->16k, WAV lesen/schreiben."""
from __future__ import annotations

import io
import wave

import numpy as np


class Decimator:
    """Streaming-Tiefpass + Dezimation um einen ganzzahligen Faktor (48000 -> 16000: Faktor 3)."""

    def __init__(self, factor: int, taps: int = 48):
        self.factor = factor
        # Windowed-sinc-Tiefpass bei 0.8 * Nyquist der Zielrate
        cutoff = 0.8 / factor / 2.0
        n = np.arange(taps) - (taps - 1) / 2.0
        h = 2 * cutoff * np.sinc(2 * cutoff * n) * np.hamming(taps)
        self.h = (h / h.sum()).astype(np.float32)
        self.tail = np.zeros(taps - 1, dtype=np.float32)
        self.phase = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        buf = np.concatenate((self.tail, x.astype(np.float32)))
        y = np.convolve(buf, self.h, mode="valid")          # len == len(x)
        out = y[self.phase::self.factor]
        self.phase = (self.phase - len(x)) % self.factor
        self.tail = buf[-(len(self.h) - 1):]
        return out


def resample_linear(x: np.ndarray, rate_in: int, rate_out: int) -> np.ndarray:
    """Einfaches Resampling für Testdateien (nicht für Live-Audio)."""
    if rate_in == rate_out:
        return x.astype(np.float32)
    n_out = int(len(x) * rate_out / rate_in)
    return np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x).astype(np.float32)


def read_wav(path: str, rate: int = 16000) -> np.ndarray:
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        x = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return resample_linear(x, sr, rate)


def wav_bytes(x: np.ndarray, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def write_wav(path: str, x: np.ndarray, rate: int = 16000) -> None:
    with open(path, "wb") as fh:
        fh.write(wav_bytes(x, rate))
