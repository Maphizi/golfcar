"""llama.cpp als dauerhafter Server (OpenAI-kompatible API) plus Streaming-Client für KITT."""
from __future__ import annotations

import http.client
import json
import logging
import re
import socket
import subprocess
import time
from pathlib import Path

log = logging.getLogger("llm")
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def is_thinking_model(name: str) -> bool:
    n = name.lower()
    return "qwen3" in n or "deepseek-r1" in n or "thinking" in n


class LlamaServer:
    def __init__(self, llama_dir: Path, model_path: Path, port: int, threads: int = 4, ctx: int = 2048,
                 log_path: Path | None = None):
        self.binary = llama_dir / "build" / "bin" / "llama-server"
        self.model_path = model_path
        self.port = port
        self.args = ["-m", str(model_path), "--host", "127.0.0.1", "--port", str(port), "-t", str(threads),
                     "-c", str(ctx), "-np", "1", "--jinja", "--no-webui"]
        if is_thinking_model(model_path.name):
            self.args += ["--reasoning-budget", "0", "--reasoning-format", "none"]
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None
        self._logfh = None

    def start(self, timeout: float = 180.0) -> float:
        if not self.binary.exists():
            raise FileNotFoundError(f"llama-server fehlt: {self.binary} (scripts/setup_phase6.sh)")
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modell fehlt: {self.model_path}")
        if self._port_open():
            raise RuntimeError(f"Port {self.port} belegt (läuft schon ein llama-server?)")
        self._logfh = open(self.log_path, "ab") if self.log_path else subprocess.DEVNULL
        t0 = time.monotonic()
        self.proc = subprocess.Popen([str(self.binary)] + self.args, stdout=self._logfh, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=False)
        while time.monotonic() - t0 < timeout:
            proc = self.proc
            if proc is None:
                raise RuntimeError("Start abgebrochen (stop() wurde aufgerufen)")
            if proc.poll() is not None:
                raise RuntimeError(f"llama-server beendet (exit {proc.returncode}), siehe {self.log_path}")
            if self._healthy():
                dt = time.monotonic() - t0
                log.info("llama-server bereit nach %.1fs (%s)", dt, self.model_path.name)
                return dt
            time.sleep(0.2)
        self.stop()
        raise TimeoutError("llama-server antwortet nicht")

    def _port_open(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                return True
        except OSError:
            return False

    def _healthy(self) -> bool:
        try:
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=1)
            c.request("GET", "/health")
            r = c.getresponse()
            ok = r.status == 200
            c.close()
            return ok
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
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        if self._logfh not in (None, subprocess.DEVNULL):
            self._logfh.close()
        self._logfh = None


class StopGeneration(Exception):
    """Aus on_token werfen, um die Generierung abzubrechen (Verbindung wird geschlossen, Slot frei)."""


class Result:
    def __init__(self):
        self.text = ""
        self.ttft = 0.0          # Sekunden bis zum ersten Token
        self.total = 0.0         # Sekunden gesamt
        self.tokens = 0          # generierte Tokens (Chunks)
        self.tps = 0.0           # Tokens/s laut Server (oder berechnet)
        self.prompt_tokens = 0
        self.prompt_ms = 0.0
        self.stopped = False


def chat(port: int, messages: list[dict], max_tokens: int = 80, temperature: float = 0.7, top_p: float = 0.8,
         repeat_penalty: float = 1.05, on_token=None, timeout: float = 120.0) -> Result:
    """Streaming-Chat. on_token(text) wird pro Token aufgerufen (für UI/TTS-Satzweise)."""
    body = json.dumps({
        "messages": messages, "stream": True, "max_tokens": max_tokens, "temperature": temperature,
        "top_p": top_p, "repeat_penalty": repeat_penalty, "timings_per_token": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "cache_prompt": True,
    }).encode()
    res = Result()
    t0 = time.monotonic()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("POST", "/v1/chat/completions", body, {"Content-Type": "application/json"})
    resp = conn.getresponse()
    if resp.status != 200:
        data = resp.read()
        conn.close()
        raise RuntimeError(f"llama-server HTTP {resp.status}: {data[:300]!r}")
    buf = b""
    while True:
        chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(4096)
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if "timings" in obj:
                t = obj["timings"]
                res.tps = float(t.get("predicted_per_second", 0.0)) or res.tps
                res.prompt_tokens = int(t.get("prompt_n", 0))
                res.prompt_ms = float(t.get("prompt_ms", 0.0))
            for ch in obj.get("choices", []):
                delta = ch.get("delta", {}).get("content")
                if delta:
                    if res.tokens == 0:
                        res.ttft = time.monotonic() - t0
                    res.tokens += 1
                    res.text += delta
                    if on_token:
                        try:
                            on_token(delta)
                        except StopGeneration:
                            res.stopped = True
                            buf = b""
                            chunk = b""
                            break
            if getattr(res, "stopped", False):
                break
        if getattr(res, "stopped", False):
            break
    conn.close()
    res.total = time.monotonic() - t0
    res.text = THINK_RE.sub("", res.text).strip()
    if not res.tps and res.tokens > 1 and res.total > res.ttft:
        res.tps = (res.tokens - 1) / (res.total - res.ttft)
    return res


class Kitt:
    """Dialogzustand: System-Prompt + begrenzte Historie."""

    def __init__(self, port: int, system_prompt: str, cfg: dict):
        self.port = port
        self.system = system_prompt
        self.max_tokens = int(cfg.get("max_tokens", 80))
        self.temperature = float(cfg.get("temperature", 0.7))
        self.top_p = float(cfg.get("top_p", 0.8))
        self.repeat_penalty = float(cfg.get("repeat_penalty", 1.05))
        self.history_turns = int(cfg.get("history_turns", 4))
        self.history: list[dict] = []

    def ask(self, user_text: str, on_token=None) -> Result:
        msgs = [{"role": "system", "content": self.system}] + self.history[-2 * self.history_turns:] + \
               [{"role": "user", "content": user_text}]
        res = chat(self.port, msgs, self.max_tokens, self.temperature, self.top_p, self.repeat_penalty, on_token)
        self.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": res.text}]
        return res

    def reset(self) -> None:
        self.history.clear()
