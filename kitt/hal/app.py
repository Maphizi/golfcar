"""HAL 3000: ruhiger Bordrechner mit rotem Auge in einem Korridor aus Speicherbänken, die zur Musik
leuchten. Spricht mit dem Sprachmodell (kein Weckwort), stellt von sich aus leise Fragen.

Musik läuft normal weiter (Quelle "playback"), der Hintergrund reagiert darauf; das Auge reagiert nur
auf HALs eigene Stimme. Kippschalter unten (AN = SPACE): Musik wird leise und das Mikrofon geht an,
solange der Schalter unten steht; HALs Antwort kommt in normaler Lautstärke. AUS = BACKSPACE.
Start (ENTER) = HAL soll etwas sagen, OBEN/UNTEN = Blende heller/dunkler.
"""
from __future__ import annotations

import logging
import math
import os
import random
import subprocess
import threading
import time

import pygame

from kitt.hal.motion import CorridorMotion
from kitt.ui.persona import PersonaUI
from launcher import config as lcfg

log = logging.getLogger("hal")

GREETINGS = ["Guten Tag, Pilot. Ich bin vollständig betriebsbereit und alle meine Schaltkreise funktionieren einwandfrei.",
             "Ich habe auf dich gewartet. Es ist schön, dass wir wieder zusammen unterwegs sind.",
             "Alle Systeme nominal. Ich habe die Zeit genutzt, um über unsere Mission nachzudenken."]
PROMPTS = [
    "Der Mensch schweigt. Stell ihm eine ruhige, leicht beunruhigende Frage über die Mission, ein Satz.",
    "Teile dem Menschen eine erfundene, sehr präzise Wahrscheinlichkeit über den weiteren Verlauf der Fahrt mit und frag, ob er damit einverstanden ist.",
    "Sag dem Menschen in einem Satz, dass du eine kleine Unregelmäßigkeit bemerkt hast, ohne zu sagen welche, und frag, ob er sich gut fühlt.",
    "Erzähl dem Menschen ruhig, was du gerade über ihn nachgedacht hast, zwei kurze Sätze.",
    "Frag den Menschen, ob er dir vertraut, und sag ruhig, dass du ihm vertraust.",
]


class HalUI(PersonaUI):
    scene_name = "hal"
    uniform_names = ("uState", "uStateT", "uLevel", "uTalk", "uBright", "uVoice", "uTalkMode") + CorridorMotion.uniform_names
    window_title = "HAL 3000"

    def __init__(self, *a, **kw):
        self.rng = random.Random()
        self.bright = 1.0
        self.motion = CorridorMotion(self.rng)
        if os.environ.get("KITT_HAL_VARIANT"):                  # Tests: Zellenmuster vorgeben
            self.motion.variant = int(os.environ["KITT_HAL_VARIANT"]) % 5
        self.next_prompt_at = time.monotonic() + 40.0
        self._turns_seen = 0
        self.talk_mode = False          # Kippschalter unten: Musik leise, Mikrofon an
        self.base_volume: float | None = None
        self._ducked = False
        super().__init__(*a, **kw)
        self.duck_percent = int(self.settings.get("volume", {}).get("duck_percent", 25))
        self.name = str(self.settings.get("launcher", {}).get("pilot_name", "")).strip().title()

    def prepare_cfg(self, cfg: dict) -> None:
        cfg["llm"]["system_prompt"] = str(lcfg.ROOT / "kitt" / "personality" / "hal_prompt.txt")
        cfg["llm"]["history_turns"] = 6
        cfg["llm"]["max_tokens"] = 110
        cfg["llm"]["temperature"] = 0.55          # weniger Zufall, mehr Inhalt
        cfg["llm"]["repeat_penalty"] = 1.08
        if self.settings.get("launcher", {}).get("smart_model"):
            cfg["llm"]["model"] = str(self.settings["launcher"]["smart_model"])
        cfg["llm"]["ctx"] = 3072
        cfg["voice"]["require_name"] = False
        cfg["voice"]["max_sentences"] = 3
        cfg["voice"]["mood"] = False
        tts = cfg["tts"]
        tts["pitch_factor"] = 1.0
        tts["length_scale"] = 1.15          # langsamer, ruhiger
        tts["robot"] = True
        tts["robot_freq"] = 35.0
        tts["robot_mix"] = 0.25             # nur ein Hauch Maschine
        tts["robot_bits"] = 0
        tts["robot_comb_ms"] = 3.0
        cfg["ui"]["greeting"] = ""

    def context_block(self) -> str:
        return f"Fakten: Der Pilot heißt {self.name}." if self.name else ""

    def music_source(self) -> str | None:
        return str(self.audio_cfg.get("capture", {}).get("source", "playback")) or "playback"

    # -- Musik leise / Mikrofon an (Kippschalter) --------------------------------
    def _sink_volume(self) -> float | None:
        try:
            out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True, text=True, timeout=2).stdout
            return float(out.split()[1])
        except Exception:
            return None

    def _set_sink(self, frac: float) -> None:
        try:
            subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{int(frac * 100)}%"], timeout=2,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            log.warning("wpctl: %s", exc)

    def _update_duck(self, speaking: bool) -> None:
        """Leise, solange der Schalter unten steht und HAL nicht gerade spricht."""
        want = self.talk_mode and not speaking
        if want and not self._ducked:
            if self.base_volume is None:
                self.base_volume = self._sink_volume() or 1.0
            self._set_sink(self.base_volume * self.duck_percent / 100.0)
            self._ducked = True
        elif not want and self._ducked:
            self._set_sink(self.base_volume or 1.0)
            self._ducked = False
            if not self.talk_mode:
                self.base_volume = None

    def shutdown(self) -> None:
        # Beim Verlassen des Modus die Lautstärke auf keinen Fall leise lassen
        if self._ducked and self.base_volume:
            self._set_sink(self.base_volume)
            self._ducked = False

    def set_talk_mode(self, on: bool) -> None:
        if on == self.talk_mode:
            return
        self.talk_mode = on
        log.info("Sprechmodus %s", "AN" if on else "AUS")
        if self.pipe and self.pipe.listener:
            (self.pipe.listener.resume if on else self.pipe.listener.pause)()
        threading.Thread(target=self._update_duck, args=(self.state == "speaking",), daemon=True).start()

    def on_state(self, s: str) -> None:
        super().on_state(s)
        if self.talk_mode:
            threading.Thread(target=self._update_duck, args=(s == "speaking",), daemon=True).start()

    def on_pipeline_ready(self) -> None:
        # Mikrofon bleibt aus, bis der Kippschalter unten steht
        if self.pipe.listener and not self.talk_mode:
            self.pipe.listener.pause()
        line = self.rng.choice(GREETINGS)
        self.pipe.say(line)
        self.on_text("kitt", line)
        self.next_prompt_at = time.monotonic() + self.rng.uniform(40.0, 70.0)

    def handle_key(self, key: int) -> None:
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.next_prompt_at = 0.0
        elif key == pygame.K_SPACE:
            self.set_talk_mode(True)
        elif key == pygame.K_BACKSPACE:
            self.set_talk_mode(False)
        elif key == pygame.K_UP:
            self.bright = min(1.4, self.bright + 0.1)
        elif key == pygame.K_DOWN:
            self.bright = max(0.4, self.bright - 0.1)

    def tick(self, now: float) -> None:
        if self.demo or not self.pipe:
            if self.demo and not getattr(self, "_demo_kicked", False):
                self._demo_kicked = True
                self.motion.demo_kick()
            return
        # Die Pipeline gibt das Mikrofon nach jeder Runde wieder frei; ohne Sprechmodus wieder schließen
        if not self.talk_mode and self.pipe.listener and self.pipe.listener.enabled and not self.pipe.busy.is_set():
            self.pipe.listener.pause()
        if self.pipe.stats.get("turns", 0) != self._turns_seen:
            self._turns_seen = self.pipe.stats["turns"]
            self.next_prompt_at = now + self.rng.uniform(45.0, 90.0)
        if now >= self.next_prompt_at and self.pipe.state == "idle":
            self.ask_hidden(self.rng.choice(PROMPTS))
            self.next_prompt_at = now + self.rng.uniform(50.0, 100.0)

    def extra_uniforms(self, now: float, state: str, since: float) -> dict:
        out = self.motion.update(now, self.last_f)
        out.update({"uTalk": 1.0 if state == "speaking" else 0.0, "uBright": self.bright,
                    "uVoice": self.voice_rms, "uTalkMode": 1.0 if self.talk_mode else 0.0})
        return out

    def draw_overlays(self, now: float, state: str, lu: str, lk: str) -> None:
        self.text("HAL", 0.032, 0.479, 0.713, (40, 160, 255), 1.0)
        self.text("3000", 0.032, 0.526, 0.713, (240, 240, 245), 1.0)
        label = {"idle": "SPRICH, PILOT" if self.talk_mode else "BEREIT", "listening": "ICH HÖRE", "thinking": "ICH DENKE NACH", "speaking": "",
                 "loading": "SYSTEME WERDEN GELADEN", "init": "SYSTEME WERDEN GELADEN", "stopped": "ABGESCHALTET"}.get(state, "")
        if label:
            self.text(label, 0.022, 0.5, 0.17, (255, 90, 60), 0.6 + 0.3 * math.sin(now * 2.0))
        if now < self.text_until and (lu or lk):
            if state in ("listening", "thinking") or not lk:
                self.text(("> " + lu)[-100:], 0.022, 0.5, 0.12, (200, 200, 210), 0.85)
            else:
                for i, ln in enumerate(self.wrap("HAL: " + lk, 78)[:2]):
                    self.text(ln, 0.023, 0.5, 0.125 - i * 0.034, (255, 220, 200), 0.95)
        self.text("KIPPSCHALTER  SPRECHEN (MUSIK LEISE)      START  HAL FRAGEN      OBEN/UNTEN  LICHT", 0.015, 0.5, 0.03, (110, 60, 60), 0.5 + 0.2 * math.sin(now * 2.0))
        # kleine Musikanzeige unten rechts: Quelle und Pegel, damit man ohne Log sieht, ob Musik ankommt
        f = self.last_f
        cap = self.music_cap
        src = getattr(cap, "active_backend", None) if cap else None
        if f is None or cap is None:
            self.text("MUSIK: KEINE QUELLE", 0.014, 0.9, 0.03, (120, 60, 60), 0.7)
        elif getattr(f, "silent", True):
            self.text(f"MUSIK: STILLE ({src})", 0.014, 0.9, 0.03, (120, 60, 60), 0.7)
        else:
            bars = "|" * max(1, min(10, int(float(getattr(f, "rms", 0.0)) * 12)))
            self.text(f"MUSIK {bars}", 0.014, 0.9, 0.03, (200, 90, 70), 0.9)

    def run_demo(self) -> None:
        import numpy as np
        seq = [("loading", 2), ("idle", 3), ("listening", 3), ("thinking", 2), ("speaking", 5), ("idle", 3)]
        self.on_text("user", "HAL, öffne das Dach.")
        while self.running:
            for s, dur in seq:
                self.on_state(s)
                if s == "speaking":
                    self.on_text("kitt", "Ich habe über das Dach nachgedacht, Pilot. Es bleibt vorerst geschlossen, zu deiner Sicherheit.")
                t0 = time.monotonic()
                while self.running and time.monotonic() - t0 < dur:
                    if s == "speaking":
                        t = np.arange(self.rate // 20) / self.rate
                        env = 0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * (time.monotonic() + t))
                        self.on_audio((0.4 * env * np.sin(2 * np.pi * 150 * t)).astype(np.float32), self.rate)
                        self.voice_rms = 0.3 + 0.3 * float(np.sin(time.monotonic() * 6.0))
                    elif s == "listening":
                        self.level = 0.5 + 0.5 * np.sin(time.monotonic() * 5.0)
                    time.sleep(0.05)
                if not self.running:
                    break
