"""whisper.cpp als dauerhaft laufender Server (Modell bleibt geladen) plus HTTP-Client."""
from __future__ import annotations

import http.client
import json
import logging
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path

import numpy as np

from kitt.audio_utils import wav_bytes

log = logging.getLogger("stt")


class WhisperServer:
    def __init__(self, whisper_dir: Path, model_path: Path, port: int, language: str = "de", threads: int = 4,
                 audio_ctx: int = 0, beam_size: int = 1, best_of: int = 1, log_path: Path | None = None):
        self.binary = whisper_dir / "build" / "bin" / "whisper-server"
        self.model_path = model_path
        self.port = port
        self.args = ["-m", str(model_path), "-l", language, "-t", str(threads), "--host", "127.0.0.1",
                     "--port", str(port), "-nt", "-bs", str(beam_size), "-bo", str(best_of)]
        if audio_ctx:
            self.args += ["-ac", str(audio_ctx)]
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None
        self._logfh = None

    def start(self, timeout: float = 60.0) -> float:
        """Startet den Server und wartet, bis er antwortet. Gibt die Ladezeit in Sekunden zurück."""
        if not self.binary.exists():
            raise FileNotFoundError(f"whisper-server fehlt: {self.binary} (scripts/setup_phase5.sh)")
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modell fehlt: {self.model_path}")
        if self._port_open():
            raise RuntimeError(f"Port {self.port} ist belegt (läuft schon ein whisper-server?)")
        self._logfh = open(self.log_path, "ab") if self.log_path else subprocess.DEVNULL
        t0 = time.monotonic()
        self.proc = subprocess.Popen([str(self.binary)] + self.args, stdout=self._logfh, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=False)
        while time.monotonic() - t0 < timeout:
            proc = self.proc
            if proc is None:
                raise RuntimeError("Start abgebrochen (stop() wurde aufgerufen)")
            if proc.poll() is not None:
                raise RuntimeError(f"whisper-server beendet (exit {proc.returncode}), siehe {self.log_path}")
            if self._port_open():
                dt = time.monotonic() - t0
                log.info("whisper-server bereit nach %.1fs (%s)", dt, self.model_path.name)
                return dt
            time.sleep(0.1)
        self.stop()
        raise TimeoutError("whisper-server antwortet nicht")

    def _port_open(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                return True
        except OSError:
            return False

    def rss_mb(self) -> float:
        if not self.proc:
            return 0.0
        try:
            with open(f"/proc/{self.proc.pid}/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024.0
        except OSError:
            pass
        return 0.0

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        if self._logfh not in (None, subprocess.DEVNULL):
            self._logfh.close()
        self._logfh = None


def transcribe(pcm16k: np.ndarray, port: int, prompt: str = "", temperature: float = 0.0, timeout: float = 60.0) -> tuple[str, float]:
    """Schickt Audio an den Server, gibt (Text, Sekunden) zurück."""
    boundary = "----kitt" + uuid.uuid4().hex
    fields = {"temperature": f"{temperature}", "temperature_inc": "0.0", "response_format": "json"}
    if prompt:
        fields["prompt"] = prompt
    body = b""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"u.wav\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode() + wav_bytes(pcm16k) + f"\r\n--{boundary}--\r\n".encode()
    t0 = time.monotonic()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("POST", "/inference", body, {"Content-Type": f"multipart/form-data; boundary={boundary}",
                                               "Content-Length": str(len(body))})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    dt = time.monotonic() - t0
    if resp.status != 200:
        raise RuntimeError(f"whisper-server HTTP {resp.status}: {data[:200]!r}")
    text = json.loads(data).get("text", "").strip()
    return text, dt
