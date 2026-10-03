"""Voice Activity Detection: Silero VAD (ONNX) mit energiebasiertem Fallback.

Beide liefern pro 512-Sample-Chunk bei 16 kHz (32 ms) eine Sprachwahrscheinlichkeit 0..1.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger("vad")
CHUNK = 512          # Samples bei 16 kHz
RATE = 16000


class SileroVAD:
    """Silero VAD v5 (silero_vad.onnx, MIT-Lizenz) über onnxruntime, einspurig."""

    def __init__(self, model_path: Path):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        names = {i.name for i in self.sess.get_inputs()}
        if "state" not in names:
            raise RuntimeError("Unerwartetes Silero-Modell (v5 mit 'state'-Eingang erwartet)")
        self.context_size = 64
        self.reset()

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros(self.context_size, dtype=np.float32)

    def __call__(self, chunk: np.ndarray) -> float:
        x = np.concatenate((self.context, chunk.astype(np.float32)))[None, :]
        out, self.state = self.sess.run(None, {"input": x, "state": self.state, "sr": np.array(RATE, dtype=np.int64)})
        self.context = chunk[-self.context_size:].astype(np.float32)
        return float(out[0, 0])

    name = "silero"


class EnergyVAD:
    """Fallback: RMS gegen adaptiven Grundrauschpegel. Kein Modell nötig, aber ungenauer."""

    name = "energy"

    def __init__(self, ratio: float = 3.0):
        self.noise = 0.002
        self.ratio = ratio

    def reset(self) -> None:
        pass

    def __call__(self, chunk: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(chunk * chunk)) + 1e-9)
        if rms < self.noise * 2.0:
            self.noise = 0.98 * self.noise + 0.02 * rms       # Rauschpegel langsam nachführen
        x = rms / (self.noise * self.ratio)
        return float(np.clip((x - 0.5), 0.0, 1.0))


def load_vad(cfg: dict, model_path: Path):
    backend = cfg.get("backend", "auto")
    if backend in ("auto", "silero"):
        try:
            v = SileroVAD(model_path)
            log.info("VAD: Silero (%s)", model_path)
            return v
        except Exception as exc:
            if backend == "silero":
                raise
            log.warning("Silero VAD nicht verfügbar (%s), nutze Energie-VAD", exc)
    log.info("VAD: energiebasiert")
    return EnergyVAD()
