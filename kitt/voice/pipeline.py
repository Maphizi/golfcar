"""KITT-Sprachpipeline: Mikrofon -> VAD -> whisper.cpp -> llama.cpp -> Piper -> Lautsprecher.

Zustände: idle -> listening -> thinking -> speaking -> idle
Callbacks für die UI (Phase 8): on_state(name), on_text(role, text), on_level(p), on_audio(pcm, rate).
Alles läuft in Threads; die Pipeline blockiert den Aufrufer nicht.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import numpy as np

from kitt import config as kcfg
from kitt.llm.llama_client import Kitt, LlamaServer, StopGeneration
from kitt.stt.listener import Listener
from kitt.stt.vad import RATE as STT_RATE, load_vad
from kitt.stt.whisper_client import WhisperServer, transcribe
from kitt.tts.piper_tts import PiperTTS
from kitt.voice.sentences import SentenceSplitter
from launcher import config as lcfg

log = logging.getLogger("voice")


def clean_sentence(s: str, openers: list[str]) -> str:
    """Floskeln am Satzanfang entfernen ("Natürlich!", "Gerne,"), Markdown-Reste und Emojis streichen."""
    import re
    s = re.sub(r"[*_#`]+", "", s).strip()
    s = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", s)
    low = s.lower()
    for o in openers:
        if low.startswith(o.lower()):
            rest = s[len(o):].lstrip(" ,.!:;-")
            if len(rest) < 3:
                return ""           # Satz bestand nur aus der Floskel
            return rest[0].upper() + rest[1:]
    return s


class VoicePipeline:
    def __init__(self, cfg: dict, audio_cfg: dict, logs_dir: Path, on_state=None, on_text=None, on_level=None,
                 on_audio=None, tts_backend: str = "piper", use_mic: bool = True):
        self.cfg = cfg
        self.audio_cfg = audio_cfg
        self.logs_dir = logs_dir
        self.on_state = on_state or (lambda s: None)
        self.on_text = on_text or (lambda role, text: None)
        self.on_level = on_level or (lambda p: None)
        self.on_audio = on_audio or (lambda pcm, rate: None)
        self.state = "init"
        self.lock = threading.Lock()
        self.use_mic = use_mic
        self.tts_backend = tts_backend
        self.stt_cfg, self.llm_cfg, self.tts_cfg, self.vcfg = cfg["stt"], cfg["llm"], cfg["tts"], cfg.get("voice", {})
        self.whisper: WhisperServer | None = None
        self.gate: WhisperServer | None = None
        self.llama: LlamaServer | None = None
        self.kitt: Kitt | None = None
        self.tts: PiperTTS | None = None
        self.listener: Listener | None = None
        self.cap = None
        self.busy = threading.Event()
        self.stats = {"turns": 0}

    # -- Lebenszyklus ----------------------------------------------------
    def _set(self, state: str) -> None:
        if state != self.state:
            self.state = state
            log.info("STATE %s", state.upper())
            self.on_state(state)

    def start(self) -> None:
        self._set("loading")
        stt = self.stt_cfg
        self.whisper = WhisperServer(kcfg.path(stt["whisper_dir"]), kcfg.path(stt["models_dir"]) / stt["model"],
                                     int(stt["port"]), stt.get("language", "de"), int(stt.get("threads", 4)),
                                     int(stt.get("audio_ctx", 0)), int(stt.get("beam_size", 1)), int(stt.get("best_of", 1)),
                                     self.logs_dir / "whisper-server.log")
        llm = self.llm_cfg
        self.llama = LlamaServer(kcfg.path(llm["llama_dir"]), kcfg.path(llm["models_dir"]) / llm["model"], int(llm["port"]),
                                 int(llm.get("threads", 4)), int(llm.get("ctx", 2048)), self.logs_dir / "llama-server.log")
        gate_model = kcfg.path(stt["models_dir"]) / stt.get("gate_model", "")
        if self.vcfg.get("require_name", False) and stt.get("gate_model") and gate_model.exists():
            self.gate = WhisperServer(kcfg.path(stt["whisper_dir"]), gate_model, int(stt.get("gate_port", 8177)),
                                      stt.get("language", "de"), 2, 512, 1, 1, self.logs_dir / "whisper-gate.log")
        # Server parallel starten (alle laden nur, CPU-Last entsteht erst bei Anfragen)
        t_w = threading.Thread(target=self.whisper.start, daemon=True)
        t_l = threading.Thread(target=self.llama.start, daemon=True)
        t_g = threading.Thread(target=self.gate.start, daemon=True) if self.gate else None
        t_w.start(); t_l.start()
        if t_g:
            t_g.start()
        self.tts = PiperTTS(self.tts_cfg, kcfg.path(self.tts_cfg["voices_dir"]),
                            self.audio_cfg.get("output", {}).get("target", ""), self.tts_backend)
        t_w.join(); t_l.join()
        if t_g:
            t_g.join()
            if not self.gate.proc:
                log.warning("Anrede-Vorfilter nicht gestartet, prüfe Anrede mit dem Hauptmodell")
                self.gate = None
        if not (self.whisper.proc and self.llama.proc):
            raise RuntimeError("whisper-server oder llama-server nicht gestartet, siehe logs/")
        self.kitt = Kitt(self.llama.port, kcfg.path(llm["system_prompt"]).read_text().strip(), llm)
        if self.vcfg.get("context", True):
            from kitt.context import context_block
            self.kitt.context_provider = context_block
        # Prompt-Cache füllen, damit die erste echte Antwort schnell kommt
        try:
            self.kitt.ask("Systemcheck.")
            self.kitt.reset()
        except Exception as exc:
            log.warning("Warm-up fehlgeschlagen: %s", exc)
        if self.use_mic:
            from visualizers.engine.audio_capture import AudioCapture
            vad = load_vad(self.cfg["vad"], kcfg.path(self.cfg["vad"]["model"]))
            self.listener = Listener(self.cfg["vad"], vad, self._on_utterance, self._on_listen_state,
                                     rate_in=int(self.audio_cfg["capture"]["sample_rate"]), on_level=self.on_level)
            self.cap = AudioCapture(self.audio_cfg, source="mic")
            self.cap.subscribers.append(self.listener.feed)
            self.cap.start()
        self._set("idle")
        log.info("Pipeline bereit: STT %s, LLM %s, TTS %s", stt["model"], llm["model"], self.tts.voice_name)

    def stop(self) -> None:
        if self.cap:
            self.cap.stop()
        if self.whisper:
            self.whisper.stop()
        if self.gate:
            self.gate.stop()
        if self.llama:
            self.llama.stop()
        self._set("stopped")

    # -- Ablauf einer Runde ----------------------------------------------
    def _on_listen_state(self, s: str) -> None:
        if s == "listening" and not self.busy.is_set():
            self._set("listening")
        elif s == "idle" and self.state == "listening":
            self._set("idle")

    def _on_utterance(self, pcm16k: np.ndarray) -> None:
        if self.busy.is_set():
            return
        threading.Thread(target=self.handle_audio, args=(pcm16k,), daemon=True).start()

    def _accept(self, text: str) -> bool:
        t = text.lower().strip()
        if len(t.split()) < int(self.vcfg.get("min_words", 2)):
            log.info("Ignoriert (zu kurz): %r", text)
            return False
        if any(p in t for p in self.vcfg.get("ignore_phrases", [])):
            log.info("Ignoriert (Halluzinationsfilter): %r", text)
            return False
        if self.vcfg.get("require_name", False) and not self._has_name(t):
            log.info("Ignoriert (keine Anrede): %r", text)
            return False
        return True

    def _has_name(self, t: str) -> bool:
        t = " " + t.lower() + " "
        return any(v in t for v in self.vcfg.get("name_variants", ["kitt"]))

    def handle_audio(self, pcm16k: np.ndarray) -> None:
        """Äußerung -> Text -> Antwort -> Sprache. Läuft im eigenen Thread."""
        with self.lock:
            if self.busy.is_set():
                return
            self.busy.set()
        if self.listener:
            self.listener.pause()
        try:
            self._set("thinking")
            t0 = time.monotonic()
            if self.gate:
                gtext, gdt = transcribe(pcm16k, self.gate.port, "KITT.")
                if not self._has_name(gtext):
                    log.info("Vorfilter %.2fs: keine Anrede: %r", gdt, gtext)
                    self._set("idle")
                    return
                log.info("Vorfilter %.2fs: Anrede erkannt: %r", gdt, gtext)
            text, dt = transcribe(pcm16k, self.whisper.port, self.stt_cfg.get("prompt", ""))
            log.info("STT %.2fs (%.1fs Audio): %r", dt, len(pcm16k) / STT_RATE, text)
            if not self._accept(text):
                self._set("idle")
                return
            self.on_text("user", text)
            self.handle_text(text, t_start=t0)
        except Exception:
            log.exception("Runde fehlgeschlagen")
            self._set("idle")
        finally:
            self._resume()

    def handle_text(self, text: str, t_start: float | None = None) -> str:
        """Textfrage -> Antwort sprechen. Gibt den Antworttext zurück."""
        t_start = t_start or time.monotonic()
        self._set("thinking")
        splitter = SentenceSplitter()
        done = threading.Event()
        speaker = self.tts.speaker(on_audio=self.on_audio, on_done=done.set)
        spoken = []
        max_sentences = int(self.vcfg.get("max_sentences", 3))

        def emit(s: str) -> None:
            s = clean_sentence(s, self.vcfg.get("strip_openers", []))
            if not s:
                return
            if len(spoken) >= max_sentences:
                raise StopGeneration()
            if not spoken:
                self._set("speaking")
            spoken.append(s)
            self.on_text("kitt", s)
            speaker.feed(s)

        def on_token(tok: str) -> None:
            for s in splitter.feed(tok):
                emit(s)

        try:
            res = self.kitt.ask(text, on_token=on_token)
            if not res.stopped:
                for s in splitter.flush():
                    try:
                        emit(s)
                    except StopGeneration:
                        break
            if res.stopped:
                # Historie auf das Gesprochene kürzen, sonst "erinnert" KITT sich an ungesagte Sätze
                self.kitt.history[-1]["content"] = " ".join(spoken)
            if not spoken:
                log.warning("Leere Antwort")
        finally:
            speaker.end()
        done.wait(timeout=120)
        first = (speaker.first_audio_at - t_start) if speaker.first_audio_at else 0.0
        log.info("Runde: LLM TTFT %.2fs, %.1f tok/s, erste Sprache nach %.2fs, gesamt %.2fs: %r",
                 res.ttft, res.tps, first, time.monotonic() - t_start, " ".join(spoken))
        self.stats["turns"] += 1
        self._set("idle")
        return " ".join(spoken)

    def say(self, text: str) -> None:
        """Nur sprechen (Test / Ansagen)."""
        self.busy.set()
        if self.listener:
            self.listener.pause()
        try:
            self._set("speaking")
            done = threading.Event()
            sp = self.tts.speaker(on_audio=self.on_audio, on_done=done.set)
            spl = SentenceSplitter(min_chars=1)
            for s in spl.feed(text + " ") + spl.flush():
                sp.feed(s)
            sp.end()
            done.wait(timeout=120)
            self._set("idle")
        finally:
            self._resume()

    def _resume(self) -> None:
        time.sleep(float(self.vcfg.get("resume_delay_ms", 400)) / 1000.0)
        if self.listener:
            self.listener.resume()
        self.busy.clear()
