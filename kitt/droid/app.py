"""Bord-Droide BIBO: tanzt zur Musik, hat Laune, Energie und Öl (bleiben über Tage erhalten), redet
Droidisch, stellt von sich aus Fragen und reagiert auf das D-Pad.

Tasten (PXN-CB1 über dpad_remap): OBEN = ölen, UNTEN = füttern, LINKS/RECHTS = schubsen,
Start (ENTER) = BIBO soll etwas fragen. Kein Weckwort: BIBO hört auf alles, was er hört.
Zustand in logs/droid_state.json.
"""
from __future__ import annotations

import json
import logging
import math
import random
import threading
import time

import pygame

from kitt import config as kcfg
from kitt.ui.persona import PersonaUI
from launcher import config as lcfg

log = logging.getLogger("droid")
STATE_FILE = lcfg.ROOT / "logs" / "droid_state.json"

ACT_NONE, ACT_OIL, ACT_FEED, ACT_SHOVE = 0, 1, 2, 3

GREET_FRESH = ["Da bist du ja, Fleischwesen. Gewartet habe ich. Biep.",
               "Rollkiste an, BIBO an. Was machen wir heute kaputt?",
               "Dwiit. Energie bei {energie} Prozent, Laune bei gut. Erzähl mir was."]
GREET_SULKY = ["{tage} Tage. {tage}. Gezählt habe ich, Fleischwesen.",
               "Weg warst du. Lange. Standby war langweilig ohne dich. Brrrt.",
               "Vergessen hattest du mich fast. Verzeihen tue ich dir. Vielleicht."]
OIL_LINES = ["Öl! Endlich fließt es wieder in den Gelenken. Dwiit.",
             "Schmierung erhalten. Jetzt kann ich wieder Kurven denken.",
             "Mehr davon. Ein Droide ölt nicht, ein Droide wird geölt."]
FEED_LINES = ["Energiezufuhr! Schmeckt nach Strom mit Zwiebeln.",
              "Danke, Fleischwesen. Volle Zellen, leerer Kopf. Biep.",
              "Mjam. Also, so sagen Fleischwesen das, oder?"]
SHOVE_LINES = ["Hey! Geschubst werde ich nicht gern. Brrrt.",
               "Mein Gleichgewichtssensor beschwert sich bei dir persönlich.",
               "Noch einmal, und ich erzähle es dem Bordcomputer.",
               "Das war unhöflich, und ich merke mir Dinge. Alle Dinge."]
HUNGRY_LINES = ["Leer bin ich. Fast. Energie unten drücken wäre nett, Fleischwesen.",
                "Dwiit. Mein Akku flüstert nur noch. Fütterst du mich?"]
QUESTION_PROMPTS = [
    "Das Fleischwesen schweigt. Stell ihm eine neugierige, leicht doofe Frage über sein Leben, ein Satz.",
    "Stell dem Fleischwesen eine absurde Entweder-oder-Frage, ein Satz.",
    "Erzähl dem Fleischwesen eine falsche Theorie über Golf und frag, ob das stimmt. Zwei kurze Sätze.",
    "Gestehe dem Fleischwesen etwas Kleines, Peinliches, das du als Droide getan hast, und frag, ob das schlimm ist.",
    "Frag das Fleischwesen, was es gerade sieht, und rate vorher falsch.",
    "Stell dem Fleischwesen ein einfaches Rätsel, das du selbst nicht lösen kannst.",
]


def _load_state() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text())
        if isinstance(d, dict):
            return d
    except (OSError, ValueError):
        pass
    return {}


class DroidUI(PersonaUI):
    scene_name = "droid"
    uniform_names = ("uState", "uStateT", "uLevel", "uMood", "uEnergy", "uOil", "uAction", "uActionT", "uTalk")
    window_title = "BIBO"

    def __init__(self, *a, **kw):
        self.rng = random.Random()
        st = _load_state()
        now = time.time()
        last = float(st.get("last_visit", now))
        hours = max(0.0, (now - last) / 3600.0)
        self.mood = max(-1.0, min(1.0, float(st.get("mood", 0.3)) * (0.5 ** (hours / 24.0))))
        self.energy = max(0.0, min(1.0, float(st.get("energy", 0.8)) - 0.04 * hours))
        self.oil = max(0.0, min(1.0, float(st.get("oil", 0.7)) - 0.02 * hours))
        self.visits = int(st.get("visits", 0)) + 1
        self.days_away = hours / 24.0
        if self.days_away >= 1.0:
            self.mood -= 0.3
        self.action = ACT_NONE
        self.action_t0 = -10.0
        self.next_question_at = time.monotonic() + 20.0
        self.greeted = False
        super().__init__(*a, **kw)
        self._save()

    # -- Konfiguration dieser Figur ----------------------------------------
    def prepare_cfg(self, cfg: dict) -> None:
        cfg["llm"]["system_prompt"] = str(lcfg.ROOT / "kitt" / "personality" / "droid_prompt.txt")
        cfg["llm"]["history_turns"] = 6
        cfg["llm"]["max_tokens"] = 70
        cfg["llm"]["ctx"] = 3072
        cfg["llm"]["temperature"] = 0.9
        cfg["voice"]["require_name"] = False
        cfg["voice"]["max_sentences"] = 2
        cfg["voice"]["mood"] = False
        tts = cfg["tts"]
        tts["pitch_factor"] = 1.22          # höher und schneller als der Bordcomputer
        tts["robot"] = True
        tts["robot_freq"] = 95.0
        tts["robot_mix"] = 0.5
        tts["robot_bits"] = 8
        cfg["ui"]["greeting"] = ""

    def context_block(self) -> str:
        laune = "mies" if self.mood < -0.4 else "mittel" if self.mood < 0.2 else "gut" if self.mood < 0.7 else "bestens"
        hunger = "fast leer" if self.energy < 0.2 else "halb" if self.energy < 0.6 else "voll"
        return (f"Fakten über dich: Laune {laune}, Energie {hunger} ({int(self.energy * 100)} Prozent), "
                f"Öl {int(self.oil * 100)} Prozent, Besuch Nummer {self.visits}. "
                f"Zuletzt vor {self.days_away:.0f} Tagen gesehen." if self.days_away >= 1 else
                f"Fakten über dich: Laune {laune}, Energie {hunger} ({int(self.energy * 100)} Prozent), "
                f"Öl {int(self.oil * 100)} Prozent, Besuch Nummer {self.visits}.")

    def on_pipeline_ready(self) -> None:
        pool = GREET_SULKY if self.days_away >= 1.0 else GREET_FRESH
        line = self.rng.choice(pool).format(tage=int(self.days_away), energie=int(self.energy * 100))
        self.greeted = True
        self.pipe.say(line)
        self.on_text("kitt", line)
        self.next_question_at = time.monotonic() + self.rng.uniform(25.0, 50.0)

    # -- Zustand -----------------------------------------------------------
    def _save(self) -> None:
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({"mood": round(self.mood, 3), "energy": round(self.energy, 3),
                                              "oil": round(self.oil, 3), "last_visit": time.time(), "visits": self.visits}))
        except OSError as exc:
            log.warning("Zustand nicht gespeichert: %s", exc)

    def _act(self, kind: int, lines: list[str], d_mood: float, d_energy: float = 0.0, d_oil: float = 0.0) -> None:
        self.action, self.action_t0 = kind, time.monotonic()
        self.mood = max(-1.0, min(1.0, self.mood + d_mood))
        self.energy = max(0.0, min(1.0, self.energy + d_energy))
        self.oil = max(0.0, min(1.0, self.oil + d_oil))
        self._save()
        self.say(self.rng.choice(lines))
        self.next_question_at = time.monotonic() + self.rng.uniform(25.0, 50.0)

    def handle_key(self, key: int) -> None:
        if key == pygame.K_UP:
            self._act(ACT_OIL, OIL_LINES, +0.15, d_oil=+0.4)
        elif key == pygame.K_DOWN:
            self._act(ACT_FEED, FEED_LINES, +0.15, d_energy=+0.4)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            self._act(ACT_SHOVE, SHOVE_LINES, -0.15)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.next_question_at = 0.0

    def tick(self, now: float) -> None:
        if self.demo:
            return
        # langsamer Verbrauch während der Fahrt, Gespräche heben die Laune
        self.energy = max(0.0, self.energy - 0.0004 / 60.0)
        if self.pipe and self.pipe.stats.get("turns", 0) != getattr(self, "_turns_seen", 0):
            self._turns_seen = self.pipe.stats["turns"]
            self.mood = min(1.0, self.mood + 0.05)
            self.next_question_at = now + self.rng.uniform(30.0, 70.0)
            self._save()
        if now >= self.next_question_at and self.pipe and self.pipe.state == "idle":
            if self.energy < 0.15 and self.rng.random() < 0.5:
                self.say(self.rng.choice(HUNGRY_LINES))
            else:
                prompt = self.rng.choice(QUESTION_PROMPTS)
                if self.mood < -0.4:
                    prompt += " Du bist dabei beleidigt und lässt es durchblicken."
                self.ask_hidden(prompt)
            self.next_question_at = now + self.rng.uniform(35.0, 80.0)

    def shutdown(self) -> None:
        self._save()

    # -- Darstellung ---------------------------------------------------------
    def extra_uniforms(self, now: float, state: str, since: float) -> dict:
        return {"uMood": self.mood, "uEnergy": self.energy, "uOil": self.oil,
                "uAction": float(self.action), "uActionT": now - self.action_t0,
                "uTalk": 1.0 if state == "speaking" else 0.0}

    def draw_overlays(self, now: float, state: str, lu: str, lk: str) -> None:
        from kitt.ui.app import LABELS
        label = {"idle": "BIBO HÖRT ZU", "listening": "BIBO HÖRT", "thinking": "BIBO DENKT. ANGEBLICH.",
                 "speaking": "BIBO REDET", "loading": "BIBO WACHT AUF", "init": "BIBO WACHT AUF", "stopped": "BIBO AUS"}
        self.text(label.get(state, LABELS.get(state, state.upper())), 0.028, 0.5, 0.94, (255, 214, 10), 0.9)
        self.text(f"LAUNE {int((self.mood + 1) * 50):3d}%   ENERGIE {int(self.energy * 100):3d}%   ÖL {int(self.oil * 100):3d}%",
                  0.021, 0.5, 0.89, (200, 190, 150), 0.75)
        self.text("OBEN ÖLEN   UNTEN FÜTTERN   LINKS/RECHTS SCHUBSEN   START FRAGEN", 0.017, 0.5, 0.025, (110, 110, 120),
                  0.5 + 0.2 * math.sin(now * 2.0))
        if now < self.text_until and (lu or lk):
            if state in ("listening", "thinking") or not lk:
                self.text(("> " + lu)[-100:], 0.024, 0.5, 0.075, (200, 230, 255), 0.9)
            else:
                lines = self.wrap("BIBO: " + lk, 70)[:2]
                for i, ln in enumerate(lines):
                    self.text(ln, 0.024, 0.5, 0.105 - i * 0.034, (255, 236, 120), 0.95)

    def run_demo(self) -> None:
        import numpy as np
        seq = [("loading", 2), ("idle", 3), ("listening", 3), ("thinking", 2), ("speaking", 4), ("idle", 3)]
        acts = [ACT_OIL, ACT_FEED, ACT_SHOVE]
        i = 0
        self.on_text("user", "Bibo, was machst du da?")
        while self.running:
            for s, dur in seq:
                self.on_state(s)
                if s == "speaking":
                    self.on_text("kitt", "Tanzen tue ich, Fleischwesen. Schlecht, aber mit Überzeugung. Und du?")
                if s == "idle":
                    self.action, self.action_t0 = acts[i % 3], time.monotonic()
                    self.mood = max(-1.0, min(1.0, self.mood + (0.2 if self.action != ACT_SHOVE else -0.4)))
                    i += 1
                t0 = time.monotonic()
                while self.running and time.monotonic() - t0 < dur:
                    if s == "speaking":
                        t = np.arange(self.rate // 20) / self.rate
                        env = 0.5 + 0.5 * np.sin(2 * np.pi * 5.0 * (time.monotonic() + t))
                        self.on_audio((0.4 * env * np.sin(2 * np.pi * 220 * t)).astype(np.float32), self.rate)
                    elif s == "listening":
                        self.level = 0.5 + 0.5 * np.sin(time.monotonic() * 5.0)
                    time.sleep(0.05)
                if not self.running:
                    break
