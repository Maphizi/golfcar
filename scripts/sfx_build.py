#!/usr/bin/env python3
"""Hupe und Effekte je Thema synthetisch erzeugen (keine Fremddateien): assets/sfx/<thema>_horn.wav und
<thema>_fx1..3.wav, 22050 Hz, mono, 16 Bit. Aufruf: .venv/bin/python scripts/sfx_build.py (auch in update.sh).
Abgespielt über launcher/sfx.py (Aktionen "horn" und "fx" in config/keymap.toml)."""
from __future__ import annotations

import math
import random
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sfx"
SR = 22050
rng = random.Random(7)


def t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def env(n: int, a: float = 0.01, d: float = 0.1, s: float = 0.7, r: float = 0.2) -> np.ndarray:
    """ADSR in Sekunden (Release liegt am Ende innerhalb der Länge)."""
    x = np.ones(n)
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    if na:
        x[:na] = np.linspace(0, 1, na)
    if nd:
        x[na:na + nd] = np.linspace(1, s, nd)
        x[na + nd:] = s
    if nr and nr < n:
        x[-nr:] *= np.linspace(1, 0, nr)
    return x


def saw(f, tt): return 2.0 * ((f * tt) % 1.0) - 1.0
def square(f, tt): return np.sign(np.sin(2 * np.pi * f * tt))
def sine(f, tt): return np.sin(2 * np.pi * f * tt)


def sweep(f0: float, f1: float, dur: float, wave_fn=sine, curve: float = 1.0) -> np.ndarray:
    tt = t(dur)
    k = (tt / dur) ** curve
    f = f0 + (f1 - f0) * k
    phase = np.cumsum(f) / SR
    if wave_fn is sine:
        return np.sin(2 * np.pi * phase)
    if wave_fn is saw:
        return 2.0 * (phase % 1.0) - 1.0
    return np.sign(np.sin(2 * np.pi * phase))


def noise(dur: float) -> np.ndarray:
    return np.random.default_rng(3).uniform(-1, 1, int(SR * dur))


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = a * acc + (1 - a) * v
        y[i] = acc
    return y


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    return x - lowpass(x, cutoff)


def echo(x: np.ndarray, delay: float, gain: float, n: int = 3) -> np.ndarray:
    out = x.copy()
    d = int(delay * SR)
    for k in range(1, n + 1):
        if d * k < len(x):
            out[d * k:] += x[:-d * k] * gain ** k
    return out


def clip(x: np.ndarray, drive: float) -> np.ndarray:
    return np.tanh(x * drive) / math.tanh(drive)


def norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def write(name: str, x: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = (np.clip(norm(x), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"  {name}.wav  {len(x) / SR:.2f} s")


def vib(tt: np.ndarray, rate: float, depth: float) -> np.ndarray:
    return 1.0 + depth * np.sin(2 * np.pi * rate * tt)


# ---- Space-Taxi: Raumschiff-Klaxon, Laser, Warp, Roboter-Piepsen
def spacetaxi() -> None:
    tt = t(1.4)
    a = saw(440 * vib(tt, 6, 0.02), tt) * (tt < 0.7) + saw(330 * vib(tt, 6, 0.02), tt) * (tt >= 0.7)
    a += 0.6 * saw(443, tt) * (tt < 0.7) + 0.6 * saw(332, tt) * (tt >= 0.7)      # Chorus
    a += 0.5 * sine(110, tt)
    a = lowpass(clip(a, 2.0), 2500) * env(len(tt), 0.02, 0.05, 0.9, 0.25)
    write("spacetaxi_horn", echo(a, 0.12, 0.35, 2))
    write("spacetaxi_fx1", sweep(2200, 180, 0.35, square, 0.6) * env(int(SR * 0.35), 0.005, 0.05, 0.6, 0.1))
    w = lowpass(noise(1.6), 900) * np.linspace(0.2, 1.0, int(SR * 1.6)) ** 2 + 0.5 * sweep(90, 1400, 1.6, sine, 2.0)
    write("spacetaxi_fx2", w * env(int(SR * 1.6), 0.1, 0.1, 1.0, 0.3))
    beeps = np.zeros(int(SR * 1.0))
    for k in range(6):
        f0 = rng.choice((660, 880, 990, 1320, 1760))
        seg = square(f0, t(0.09)) * env(int(SR * 0.09), 0.003, 0.02, 0.8, 0.03)
        i = int(k * 0.15 * SR)
        beeps[i:i + len(seg)] += seg * 0.8
    write("spacetaxi_fx3", lowpass(beeps, 4000))


# ---- Cyberpunk: verzerrte Sirenen-Hupe, Glitch, Alarm, Synth-Stab
def cyber() -> None:
    tt = t(1.5)
    f = 180 * (1.0 + 0.08 * np.sin(2 * np.pi * 2.5 * tt))
    a = saw(f, tt) + saw(f * 1.5, tt) * 0.8 + saw(f * 0.5, tt) * 0.5
    a = clip(a, 6.0) * env(len(tt), 0.01, 0.1, 0.9, 0.2)
    write("cyber_horn", echo(lowpass(a, 3000), 0.09, 0.3, 2))
    g = np.zeros(int(SR * 0.7))
    for k in range(10):
        dur = rng.uniform(0.02, 0.07)
        seg = (square(rng.choice((120, 240, 480, 960, 1920)), t(dur)) if rng.random() < 0.6 else noise(dur)) * 0.9
        i = int(rng.uniform(0.0, 0.62) * SR)
        g[i:i + len(seg)] += seg[:len(g) - i]
    write("cyber_fx1", highpass(g, 300))
    tt = t(1.2)
    alarm = square(np.where((tt % 0.3) < 0.15, 800.0, 600.0), tt) * env(len(tt), 0.005, 0.0, 1.0, 0.1)
    write("cyber_fx2", lowpass(alarm, 3500) * 0.8)
    tt = t(1.1)
    chord = sum(saw(f0 * vib(tt, 5, 0.004), tt) for f0 in (110, 130.8, 164.8, 220)) + 0.4 * sine(55, tt)
    write("cyber_fx3", echo(lowpass(clip(chord, 3.0), 1800) * env(len(tt), 0.005, 0.25, 0.3, 0.5), 0.15, 0.4, 3))


# ---- Zurück in die Zukunft: Autohupe (Terz) mit Flux-Brummen, Zeitkreis-Piepser, Donner, Knistern
def future() -> None:
    tt = t(1.1)
    a = sum(w * (saw(f0 * h, tt) if h == 1 else sine(f0 * h, tt)) for f0 in (370, 466) for h, w in ((1, 1.0), (2, 0.5), (3, 0.25)))
    a = lowpass(clip(a, 1.8), 2200) + 0.35 * sine(60, tt) * (1 + 0.5 * np.sin(2 * np.pi * 7 * tt))
    write("future_horn", a * env(len(tt), 0.03, 0.05, 0.95, 0.2))
    b = np.zeros(int(SR * 1.3))
    for k, f0 in enumerate((880, 1100, 1320)):
        seg = sine(f0, t(0.12)) * env(int(SR * 0.12), 0.005, 0.03, 0.7, 0.05)
        i = int(k * 0.2 * SR)
        b[i:i + len(seg)] += seg
    ding = (sine(2093, t(0.7)) + 0.5 * sine(4186, t(0.7))) * env(int(SR * 0.7), 0.002, 0.3, 0.2, 0.3)
    b[int(0.6 * SR):int(0.6 * SR) + len(ding)] += ding * 0.8
    write("future_fx1", b)
    th = lowpass(noise(2.2), 180) * np.exp(-t(2.2) * 1.6) * (1 + 0.6 * lowpass(noise(2.2), 6))
    th[:int(0.05 * SR)] += highpass(noise(0.05), 800) * 2.0
    write("future_fx2", echo(th, 0.2, 0.5, 2))
    cr = highpass(noise(0.9), 1500) * (lowpass(noise(0.9), 40) > 0.05) * np.exp(-t(0.9) * 2.0)
    write("future_fx3", cr + 0.3 * sine(50, t(0.9)) * np.exp(-t(0.9) * 3.0))


# ---- Natur: Alphorn, Eule, Frosch, Windspiel
def green() -> None:
    tt = t(1.6)
    f = 130.8 * vib(tt, 4.5, 0.006)
    a = sum(sine(f * h, tt) / h for h in range(1, 7))
    write("green_horn", lowpass(a, 1500) * env(len(tt), 0.12, 0.2, 0.85, 0.35))
    hoot = np.zeros(int(SR * 1.0))
    for i0, dur in ((0.0, 0.3), (0.45, 0.45)):
        seg = sweep(400, 340, dur, sine, 0.5) * env(int(SR * dur), 0.04, 0.05, 0.8, 0.12)
        i = int(i0 * SR)
        hoot[i:i + len(seg)] += seg
    write("green_fx1", lowpass(hoot, 900))
    tt = t(0.55)
    frog = saw(95 * (1 + 0.1 * tt), tt) * (np.sin(2 * np.pi * 28 * tt) > 0) * env(len(tt), 0.01, 0.1, 0.8, 0.1)
    write("green_fx2", lowpass(frog, 1200))
    chime = np.zeros(int(SR * 2.2))
    for k, f0 in enumerate((1760, 2217, 2637, 3322, 2093)):
        dur = 1.4
        seg = (sine(f0, t(dur)) + 0.3 * sine(f0 * 2.76, t(dur))) * np.exp(-t(dur) * 2.5)
        i = int(rng.uniform(0.0, 0.7) * SR)
        chime[i:i + len(seg)] += seg * 0.6
    write("green_fx3", chime)


def main() -> int:
    print("Klangeffekte nach", OUT)
    spacetaxi()
    cyber()
    future()
    green()
    return 0


if __name__ == "__main__":
    sys.exit(main())
