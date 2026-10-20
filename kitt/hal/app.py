"""HAL 3000: ruhiger Bordrechner mit rotem Auge in einem Korridor aus Speicherbänken, die zur Musik
leuchten. Spricht mit dem Sprachmodell (kein Weckwort), stellt von sich aus leise Fragen.

Tasten: Start (ENTER) = HAL soll etwas sagen, OBEN/UNTEN = Blende heller/dunkler.
"""
from __future__ import annotations

import logging
import math
import random
import time

import pygame

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
    uniform_names = ("uState", "uStateT", "uLevel", "uTalk", "uBright")
    window_title = "HAL 3000"

    def __init__(self, *a, **kw):
        self.rng = random.Random()
        self.bright = 1.0
        self.next_prompt_at = time.monotonic() + 40.0
        self._turns_seen = 0
        super().__init__(*a, **kw)
        self.name = str(self.settings.get("launcher", {}).get("pilot_name", "")).strip().title()

    def prepare_cfg(self, cfg: dict) -> None:
        cfg["llm"]["system_prompt"] = str(lcfg.ROOT / "kitt" / "personality" / "hal_prompt.txt")
        cfg["llm"]["history_turns"] = 6
        cfg["llm"]["max_tokens"] = 70
        cfg["llm"]["temperature"] = 0.75
        cfg["llm"]["ctx"] = 3072
        cfg["voice"]["require_name"] = False
        cfg["voice"]["max_sentences"] = 2
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

    def on_pipeline_ready(self) -> None:
        line = self.rng.choice(GREETINGS)
        self.pipe.say(line)
        self.on_text("kitt", line)
        self.next_prompt_at = time.monotonic() + self.rng.uniform(40.0, 70.0)

    def handle_key(self, key: int) -> None:
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.next_prompt_at = 0.0
        elif key == pygame.K_UP:
            self.bright = min(1.4, self.bright + 0.1)
        elif key == pygame.K_DOWN:
            self.bright = max(0.4, self.bright - 0.1)

    def tick(self, now: float) -> None:
        if self.demo or not self.pipe:
            return
        if self.pipe.stats.get("turns", 0) != self._turns_seen:
            self._turns_seen = self.pipe.stats["turns"]
            self.next_prompt_at = now + self.rng.uniform(45.0, 90.0)
        if now >= self.next_prompt_at and self.pipe.state == "idle":
            self.ask_hidden(self.rng.choice(PROMPTS))
            self.next_prompt_at = now + self.rng.uniform(50.0, 100.0)

    def extra_uniforms(self, now: float, state: str, since: float) -> dict:
        return {"uTalk": 1.0 if state == "speaking" else 0.0, "uBright": self.bright}

    def draw_overlays(self, now: float, state: str, lu: str, lk: str) -> None:
        self.text("HAL", 0.032, 0.479, 0.713, (40, 160, 255), 1.0)
        self.text("3000", 0.032, 0.526, 0.713, (240, 240, 245), 1.0)
        label = {"idle": "BEREIT", "listening": "ICH HÖRE", "thinking": "ICH DENKE NACH", "speaking": "",
                 "loading": "SYSTEME WERDEN GELADEN", "init": "SYSTEME WERDEN GELADEN", "stopped": "ABGESCHALTET"}.get(state, "")
        if label:
            self.text(label, 0.022, 0.5, 0.17, (255, 90, 60), 0.6 + 0.3 * math.sin(now * 2.0))
        if now < self.text_until and (lu or lk):
            if state in ("listening", "thinking") or not lk:
                self.text(("> " + lu)[-100:], 0.022, 0.5, 0.12, (200, 200, 210), 0.85)
            else:
                for i, ln in enumerate(self.wrap("HAL: " + lk, 78)[:2]):
                    self.text(ln, 0.023, 0.5, 0.125 - i * 0.034, (255, 220, 200), 0.95)
        self.text("START  HAL FRAGEN      OBEN/UNTEN  LICHT", 0.015, 0.5, 0.03, (110, 60, 60), 0.5 + 0.2 * math.sin(now * 2.0))

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
                    elif s == "listening":
                        self.level = 0.5 + 0.5 * np.sin(time.monotonic() * 5.0)
                    time.sleep(0.05)
                if not self.running:
                    break
