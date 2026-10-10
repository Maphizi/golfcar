"""Live-Audio vom Mikrofon in einen Ringpuffer.

Liest rohe S16-Mono-Samples aus einem Subprozess (pw-record oder arecord), damit
keine kompilierten Audio-Bindings nötig sind. Backend "test" erzeugt ein
synthetisches Musiksignal mit Kick, Melodie und Hi-Hats, um die Szenen ohne
Mikrofon prüfen zu können.
"""
from __future__ import annotations

import logging
import math
import shutil
import subprocess
import threading
import time

import numpy as np

log = logging.getLogger("audio.capture")


class AudioCapture(threading.Thread):
    def __init__(self, cfg: dict, ring_seconds: float = 2.0, source: str | None = None):
        super().__init__(name="audio-capture", daemon=True)
        cap = cfg.get("capture", {})
        self.backend = cap.get("backend", "auto")
        self.source = source or cap.get("source", "mic")
        self.target = cap.get("target", "") or ""
        if self.source == "playback":
            self.target = cfg.get("output", {}).get("target", "") or ""
        self.rate = int(cap.get("sample_rate", 48000))
        self.block = int(cap.get("block_size", 1024))
        self.ring = np.zeros(int(self.rate * ring_seconds), dtype=np.float32)
        self.pos = 0
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.active_backend = "none"
        self.blocks = 0
        self.subscribers: list = []     # Callbacks, die jeden Block (float32, 48 kHz) bekommen
        self._stop_event = threading.Event()

    # -- Öffentlich ------------------------------------------------------
    def latest(self, n: int) -> np.ndarray:
        """Die letzten n Samples (ältestes zuerst)."""
        with self.lock:
            if n >= len(self.ring):
                n = len(self.ring)
            idx = (self.pos - n) % len(self.ring)
            if idx + n <= len(self.ring):
                return self.ring[idx:idx + n].copy()
            return np.concatenate((self.ring[idx:], self.ring[:(idx + n) % len(self.ring)]))

    def stop(self) -> None:
        self._stop_event.set()
        self._kill()

    # -- Intern ----------------------------------------------------------
    def _push(self, samples: np.ndarray) -> None:
        with self.lock:
            n = len(samples)
            end = self.pos + n
            if end <= len(self.ring):
                self.ring[self.pos:end] = samples
            else:
                k = len(self.ring) - self.pos
                self.ring[self.pos:] = samples[:k]
                self.ring[:n - k] = samples[k:]
            self.pos = end % len(self.ring)
            self.blocks += 1
        for cb in self.subscribers:
            try:
                cb(samples)
            except Exception:
                log.exception("Audio-Subscriber")

    def _commands(self) -> list[tuple[str, list[str]]]:
        cmds = []
        if self.backend in ("auto", "pipewire") and shutil.which("pw-record"):
            c = ["pw-record", "--raw", "--rate", str(self.rate), "--channels", "1", "--format", "s16",
                 "--latency", f"{max(1, int(1000 * self.block / self.rate))}ms"]   # PipeWire 1.4 lehnt "1024/48000" ab
            if self.source == "playback":
                c += ["-P", "{ stream.capture.sink = true }"]      # Monitor des Sinks statt Mikrofon
            if self.target:
                c += ["--target", self.target]
            cmds.append(("pipewire", c + ["-"]))
        if self.backend in ("auto", "alsa") and shutil.which("arecord") and self.source != "playback":
            dev = self.target if (self.backend == "alsa" and self.target) else "default"
            cmds.append(("alsa", ["arecord", "-q", "-D", dev, "-f", "S16_LE", "-r", str(self.rate),
                                   "-c", "1", "-t", "raw", "--buffer-size", str(self.block * 4), "-"]))
        return cmds

    def _kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None

    def run(self) -> None:
        if self.backend == "test":
            self._run_test_signal()
            return
        backoff = 1.0
        while not self._stop_event.is_set():
            ok = False
            for name, cmd in self._commands():
                if self._stop_event.is_set():
                    return
                ok = self._run_process(name, cmd)
                if ok:
                    backoff = 1.0
                    break
            if not ok:
                log.warning("Keine Audioquelle verfügbar, neuer Versuch in %.0fs", backoff)
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2, 15.0)

    def _run_process(self, name: str, cmd: list[str]) -> bool:
        """Liest, bis der Prozess endet. True, wenn er länger als 2 s Daten geliefert hat."""
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        except OSError as exc:
            log.warning("%s: Start fehlgeschlagen: %s", name, exc)
            return False
        log.info("Audio-Capture gestartet: %s (%s)", name, " ".join(cmd))
        self.active_backend = name
        nbytes = self.block * 2
        started = time.monotonic()
        got = 0
        try:
            while not self._stop_event.is_set():
                buf = self.proc.stdout.read(nbytes)
                if not buf:
                    break
                got += len(buf)
                samples = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
                self._push(samples)
        finally:
            err = b""
            try:
                err = self.proc.stderr.read(2000) if self.proc.stderr else b""
            except Exception:
                pass
            self._kill()
        ran = time.monotonic() - started
        if ran < 2.0 or got < nbytes * 10:
            log.warning("%s endete nach %.1fs (%d Bytes): %s", name, ran, got, err.decode(errors="ignore").strip()[-300:])
            self.active_backend = "none"
            return False
        log.warning("%s beendet nach %.0fs, starte neu", name, ran)
        return True

    def _run_test_signal(self) -> None:
        """Synthetisches Signal in Echtzeit: Kick 120 BPM, Melodie, Hi-Hats, alle 24 s eine Pause."""
        self.active_backend = "test"
        log.info("Audio-Capture: Testsignal")
        n = self.block
        t0 = time.monotonic()
        i = 0
        while not self._stop_event.is_set():
            t = (np.arange(n) + i * n) / self.rate
            beat_t = np.mod(t, 0.5)
            kick = np.exp(-beat_t * 18.0) * np.sin(2 * math.pi * (50 + 40 * np.exp(-beat_t * 30)) * t)
            mel_f = 330.0 * 2 ** (np.floor(np.mod(t * 2, 8)) / 12 * 2)
            mel = 0.25 * np.sign(np.sin(2 * math.pi * mel_f * t)) * (0.6 + 0.4 * np.sin(2 * math.pi * 0.5 * t))
            hat_t = np.mod(t + 0.25, 0.25)
            hat = 0.18 * np.exp(-hat_t * 60.0) * np.random.uniform(-1, 1, n)
            pause = (np.mod(t, 24.0) > 20.0)
            sig = (0.8 * kick + mel + hat) * 0.6
            sig[pause] *= 0.0
            self._push(np.clip(sig, -1, 1).astype(np.float32))
            i += 1
            # Echtzeit halten
            due = t0 + (i * n) / self.rate
            delay = due - time.monotonic()
            if delay > 0:
                self._stop_event.wait(delay)
