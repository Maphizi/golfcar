"""Audio-Analyse: RMS, Bass/Mitten/Höhen, Spektrum, Waveform, Beat.

Alle Werte sind auf 0..1 normiert und geglättet, mit automatischer Verstärkung,
damit leise Mikrofone trotzdem sichtbare Reaktionen liefern.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Features:
    rms: float = 0.0
    bass: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    beat: float = 0.0          # 1.0 beim Beat, klingt dann ab
    level: float = 0.0         # Roh-RMS (nicht normiert), für Logs
    silent: bool = True
    spectrum: np.ndarray = field(default_factory=lambda: np.zeros(64, dtype=np.float32))
    wave: np.ndarray = field(default_factory=lambda: np.zeros(512, dtype=np.float32))


class Analyzer:
    def __init__(self, rate: int, cfg: dict):
        a = cfg.get("analysis", {})
        self.rate = rate
        self.n = int(a.get("fft_size", 2048))
        self.bins = int(a.get("spectrum_bins", 64))
        self.wave_len = int(a.get("wave_len", 512))
        self.noise_gate = float(a.get("noise_gate", 0.003))
        self.gain_floor = float(a.get("gain_floor", 0.02))
        self.gain_decay = float(a.get("gain_decay", 0.9995))
        self.attack = float(a.get("attack", 0.6))
        self.release = float(a.get("release", 0.12))
        self.beat_threshold = float(a.get("beat_threshold", 1.6))
        self.beat_min_interval = float(a.get("beat_min_interval", 0.22))
        self.beat_decay = float(a.get("beat_decay", 0.88))
        bands = a.get("bands", {})
        self.band_ranges = {
            "bass": tuple(bands.get("bass", [20, 150])),
            "mid": tuple(bands.get("mid", [150, 2000])),
            "high": tuple(bands.get("high", [2000, 12000])),
        }
        self.window = np.hanning(self.n).astype(np.float32)
        self.freqs = np.fft.rfftfreq(self.n, 1.0 / rate)
        # log-verteilte Spektrum-Bins von 30 Hz bis 16 kHz
        edges = np.geomspace(30.0, min(16000.0, rate / 2), self.bins + 1)
        self.bin_idx = [np.where((self.freqs >= lo) & (self.freqs < hi))[0] for lo, hi in zip(edges[:-1], edges[1:])]
        for i, idx in enumerate(self.bin_idx):  # leere Bins (tiefe Frequenzen) auf nächsten Index
            if len(idx) == 0:
                self.bin_idx[i] = np.array([min(int(edges[i] / (rate / self.n)), len(self.freqs) - 1)])
        self.band_idx = {k: np.where((self.freqs >= lo) & (self.freqs < hi))[0] for k, (lo, hi) in self.band_ranges.items()}
        self.peak = self.gain_floor
        self.band_peak = {k: self.gain_floor for k in self.band_ranges}
        self.spec_peak = 1e-3
        self.bass_hist = np.zeros(45, dtype=np.float32)  # ~1 s bei 45 Updates/s
        self.hist_pos = 0
        self.last_beat = 0.0
        self.f = Features(spectrum=np.zeros(self.bins, dtype=np.float32), wave=np.zeros(self.wave_len, dtype=np.float32))

    def _smooth(self, old: float, new: float) -> float:
        k = self.attack if new > old else self.release
        return old + (new - old) * k

    def update(self, samples: np.ndarray, now: float | None = None) -> Features:
        """samples: mindestens fft_size Samples, ältestes zuerst. now: Zeitstempel (Sekunden), für Tests übergebbar."""
        f = self.f
        x = samples[-self.n:]
        if len(x) < self.n:
            x = np.pad(x, (self.n - len(x), 0))
        rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
        f.level = rms
        f.silent = rms < self.noise_gate
        # Auto-Gain: Spitze langsam vergessen, nie unter gain_floor
        self.peak = max(rms, self.peak * self.gain_decay, self.gain_floor)
        rms_n = 0.0 if f.silent else min(1.0, rms / self.peak)
        f.rms = self._smooth(f.rms, rms_n)

        spec = np.abs(np.fft.rfft(x * self.window)) * (2.0 / self.n)
        # Bänder
        for k, idx in self.band_idx.items():
            e = float(np.sqrt(np.mean(spec[idx] ** 2))) if len(idx) else 0.0
            self.band_peak[k] = max(e, self.band_peak[k] * self.gain_decay, self.gain_floor * 0.25)
            v = 0.0 if f.silent else min(1.0, e / self.band_peak[k])
            setattr(f, k, self._smooth(getattr(f, k), v))
        # Spektrum (log-Bins, log-Pegel, normiert)
        raw = np.array([spec[idx].max() for idx in self.bin_idx], dtype=np.float32)
        self.spec_peak = max(float(raw.max()), self.spec_peak * self.gain_decay, self.gain_floor * 0.1)
        s = np.log1p(raw / self.spec_peak * 9.0) / np.log(10.0)
        if f.silent:
            s[:] = 0.0
        k = np.where(s > f.spectrum, self.attack, self.release).astype(np.float32)
        f.spectrum += (s - f.spectrum) * k
        # Waveform, normiert auf Auto-Gain
        w = samples[-self.wave_len:]
        if len(w) < self.wave_len:
            w = np.pad(w, (self.wave_len - len(w), 0))
        f.wave = np.clip(w / (self.peak * 3.0), -1.0, 1.0).astype(np.float32)
        # Beat: Bass-Energie gegen Mittel der letzten Sekunde
        bass_e = float(np.mean(spec[self.band_idx["bass"]] ** 2)) if len(self.band_idx["bass"]) else 0.0
        avg = float(self.bass_hist.mean()) + 1e-12
        self.bass_hist[self.hist_pos] = bass_e
        self.hist_pos = (self.hist_pos + 1) % len(self.bass_hist)
        if now is None:
            now = time.monotonic()
        f.beat *= self.beat_decay
        if not f.silent and bass_e > self.beat_threshold * avg and bass_e > 1e-6 and now - self.last_beat > self.beat_min_interval:
            f.beat = 1.0
            self.last_beat = now
        return f
