#!/usr/bin/env python3
"""Echte Hupen und Effekte aus der Scratch-Soundbibliothek (CC BY-SA 2.0, scratch.mit.edu) holen und je Thema aufbereiten.

Lädt die Originale nach assets/sfx/raw/ (nur fehlende) und baut daraus assets/sfx/real/<thema>_horn.wav, <thema>_horn2.wav und
<thema>_fx1..3.wav (22050 Hz, mono, 16 Bit). launcher/sfx.py nimmt die Dateien aus real/ vor den synthetischen aus
assets/sfx/ (scripts/sfx_build.py). Beide Ordner liegen nicht im Repo; update.sh ruft das Skript auf dem Pi auf.
Aufruf: .venv/bin/python scripts/sfx_fetch.py [--rebuild]"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "sfx" / "raw"
OUT = ROOT / "assets" / "sfx" / "real"
SR = 22050
HOSTS = ("https://assets.scratch.mit.edu", "https://cdn.assets.scratch.mit.edu")

# Name in der Scratch-Bibliothek -> Datei (src/lib/libraries/sounds.json in scratch-gui)
SOUNDS = {
    "car_horn": "7c887f6a2ecd1cdb85d5527898d7f7a0.wav",
    "train_whistle": "50f29d0e028ec5c11210d0e2f91f83dd.wav",
    "police_siren": "b10dcd209865fbd392534633307dafad.wav",
    "goose": "16a3b9d516e125cdb2ad74cd8d205d71.wav",
    "space_flyby": "49c2e36b7258338fb3a8576e646c6738.wav",
    "teleport2": "7e5019890a930f3535604cf9cad63ba4.wav",
    "alien_creak2": "21f82b7f1a83c501539c5031aea4fa8c.wav",
    "alert": "f62e3bfccab9c23eee781473c94a009c.wav",
    "buzz_whir": "d4f76ded6bccd765958d15b63804de55.wav",
    "computer_beep2": "1da43f6d52d0615da8a250e28100a80d.wav",
    "clock_ticking": "a634fcb87894520edbd7a534d1479ec4.wav",
    "thunder_storm": "11f13be7e53b2e9116d59344c5efc66a.wav",
    "whiz": "d790e1887515deb4097f0946fbf597ad.wav",
    "owl": "e8b6d605f5a1bb36c29e4e21ef754209.wav",
    "wolf_howl": "5e36d74bb16aa5085b901362788b0fbf.wav",
    "crickets": "cae6206eb3c57bb8c4b3e2ca362dfa6d.wav",
}


# ---- Laden --------------------------------------------------------------------------------------------------------
def fetch(name: str) -> Path | None:
    p = RAW / f"{name}.wav"
    if p.exists() and p.stat().st_size > 1000:
        return p
    RAW.mkdir(parents=True, exist_ok=True)
    md5ext = SOUNDS[name]
    for host in HOSTS:
        url = f"{host}/internalapi/asset/{md5ext}/get/"
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data = r.read()
            if len(data) > 1000:
                p.write_bytes(data)
                print(f"  geladen: {name} ({len(data) // 1024} kB)")
                return p
        except Exception as exc:  # Netz, 404, Timeout -> nächster Host
            print(f"  {name}: {url}: {exc}")
    return None


def _decode_ffmpeg(p: Path) -> np.ndarray | None:
    if not shutil.which("ffmpeg"):
        return None
    try:
        raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(p), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                             capture_output=True, check=True).stdout
    except Exception:
        return None
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0


def load(name: str) -> np.ndarray | None:
    """Mono-Float bei SR; Originale sind PCM-WAV (sonst ffmpeg)."""
    p = fetch(name)
    if p is None:
        return None
    try:
        with wave.open(str(p), "rb") as w:
            ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            data = w.readframes(n)
        if sw == 2:
            x = np.frombuffer(data, dtype=np.int16).astype(np.float64) / 32768.0
        elif sw == 1:
            x = (np.frombuffer(data, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
        else:
            raise ValueError(f"{sw * 8} Bit")
        if ch > 1:
            x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        if rate != SR:
            x = resample(x, SR / rate)
    except Exception as exc:
        x = _decode_ffmpeg(p)
        if x is None:
            print(f"  {name}: nicht lesbar ({exc})")
            return None
    return trim(x)


# ---- Werkzeuge ---------------------------------------------------------------------------------------------------
def resample(x: np.ndarray, factor: float) -> np.ndarray:
    """Länge * factor (factor < 1 = schneller/höher, > 1 = langsamer/tiefer), linear."""
    n = max(1, int(len(x) * factor))
    return np.interp(np.linspace(0.0, len(x) - 1, n), np.arange(len(x)), x)


def pitch(x: np.ndarray, semitones: float) -> np.ndarray:
    return resample(x, 2.0 ** (-semitones / 12.0))


def trim(x: np.ndarray, thr: float = 0.01) -> np.ndarray:
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - int(0.01 * SR)): min(len(x), idx[-1] + int(0.05 * SR))]


def cut(x: np.ndarray, seconds: float, fade: float = 0.3) -> np.ndarray:
    x = x[: int(seconds * SR)].copy()
    n = min(len(x), int(fade * SR))
    if n > 0:
        x[-n:] *= np.linspace(1.0, 0.0, n)
    return x


def fade_in(x: np.ndarray, seconds: float) -> np.ndarray:
    x = x.copy()
    n = min(len(x), int(seconds * SR))
    if n > 0:
        x[:n] *= np.linspace(0.0, 1.0, n)
    return x


def echo(x: np.ndarray, delay: float, gain: float, n: int = 3) -> np.ndarray:
    d = int(delay * SR)
    out = np.concatenate([x, np.zeros(d * n)])
    for k in range(1, n + 1):
        out[d * k: d * k + len(x)] += x * gain ** k
    return out


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = a * acc + (1 - a) * v
        y[i] = acc
    return y


def clip(x: np.ndarray, drive: float) -> np.ndarray:
    return np.tanh(x * drive) / math.tanh(drive)


def repeat(x: np.ndarray, times: int, gap: float) -> np.ndarray:
    g = np.zeros(int(gap * SR))
    parts = []
    for i in range(times):
        parts.append(x)
        if i < times - 1:
            parts.append(g)
    return np.concatenate(parts)


def mix(*parts: tuple[np.ndarray, float, float]) -> np.ndarray:
    """(signal, start s, gain) übereinander."""
    n = max(int(s * SR) + len(x) for x, s, _ in parts)
    out = np.zeros(n)
    for x, s, g in parts:
        i = int(s * SR)
        out[i: i + len(x)] += x * g
    return out


def write(name: str, x: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    m = np.max(np.abs(x)) or 1.0
    data = (np.clip(x / m * 0.9, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"  {name}.wav  {len(x) / SR:.2f} s")


# ---- Rezepte je Thema --------------------------------------------------------------------------------------------
def build(name: str, recipe) -> bool:
    """recipe() liefert das Signal oder None (Quelle fehlt)."""
    try:
        x = recipe()
    except Exception as exc:
        print(f"  {name}: {exc}")
        return False
    if x is None or len(x) < SR // 10:
        print(f"  {name}: Quelle fehlt, bleibt synthetisch")
        return False
    write(name, x)
    return True


def recipes() -> dict:
    def horn_space():
        h = load("car_horn")
        return None if h is None else echo(lowpass(pitch(h, -3), 3000), 0.16, 0.35, 2)

    def horn_cyber():
        h, s = load("car_horn"), load("police_siren")
        if h is None:
            return None
        deep = echo(clip(lowpass(pitch(h, -7), 1800), 5.0), 0.09, 0.3, 2)
        return deep if s is None else mix((deep, 0.0, 1.0), (repeat(s, 2, 0.02), 0.05, 0.35))

    def horn_future():
        h = load("car_horn")
        return None if h is None else cut(h, 1.3, 0.15)

    def horn_green():
        g = load("goose")
        return None if g is None else repeat(g, 2, 0.12)

    def horn2_space():                                               # Zugpfeife tief mit Hall = Schiffshorn
        w = load("train_whistle")
        return None if w is None else echo(lowpass(pitch(w, -5), 2500), 0.18, 0.35, 2)

    def horn2_cyber():
        s = load("police_siren")
        return None if s is None else clip(repeat(s, 2, 0.0), 2.0)

    def horn2_future():                                              # kurzes Doppelhupen
        h = load("car_horn")
        return None if h is None else repeat(cut(h, 0.3, 0.08), 2, 0.12)

    def horn2_green():                                               # Wolfsgeheul
        w = load("wolf_howl")
        return None if w is None else cut(w, 3.0, 0.6)

    def simple(src, seconds=None, fade=0.3, semis=0.0):
        def f():
            x = load(src)
            if x is None:
                return None
            if semis:
                x = pitch(x, semis)
            return cut(x, seconds, fade) if seconds else x
        return f

    def siren():
        s = load("police_siren")
        return None if s is None else repeat(s, 3, 0.0)

    def thunder():
        x = load("thunder_storm")
        return None if x is None else cut(fade_in(x, 0.05), 3.5, 0.8)

    return {
        "spacetaxi_horn": horn_space, "spacetaxi_horn2": horn2_space, "cyber_horn2": horn2_cyber, "future_horn2": horn2_future,
        "green_horn2": horn2_green, "spacetaxi_fx1": simple("space_flyby"), "spacetaxi_fx2": simple("teleport2"),
        "spacetaxi_fx3": simple("alien_creak2"),
        "cyber_horn": horn_cyber, "cyber_fx1": simple("alert"), "cyber_fx2": siren, "cyber_fx3": simple("buzz_whir"),
        "future_horn": horn_future, "future_fx1": simple("clock_ticking", 2.5, 0.4), "future_fx2": thunder,
        "future_fx3": simple("whiz"),
        "green_horn": horn_green, "green_fx1": simple("owl"), "green_fx2": simple("wolf_howl", 3.5, 0.5),
        "green_fx3": simple("crickets", 2.5, 0.6),
    }


def main() -> int:
    rebuild = "--rebuild" in sys.argv
    todo = recipes()
    if not rebuild:
        todo = {n: r for n, r in todo.items() if not (OUT / f"{n}.wav").exists()}
    if not todo:
        print("Echte Klänge vorhanden:", OUT)
        return 0
    print("Echte Klänge nach", OUT)
    ok = sum(build(n, r) for n, r in todo.items())
    print(f"{ok} von {len(todo)} gebaut")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
