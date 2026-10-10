"""Systemfehler-Modus (Taste 8): Ablaufsteuerung für den Shader visualizers/shaders/error/frag.glsl.

Jeder Durchlauf ist anders: Länge und Variante der Code-Phase, Stärke des Zusammenbruchs, Fehlerbild,
und ab und zu ein Sonderereignis statt des normalen Absturzes:
  - Eingabe-Aufforderung: "DRUECKE OBEN/UNTEN/LINKS/RECHTS/START" mit Restzeit. Richtig = Zugriff
    gewährt und der Code läuft stabil weiter, falsch = Alarm und harter Absturz, keine Antwort =
    das System übernimmt. Kommt selten (etwa jeder achte Durchlauf, nie zweimal hintereinander).
  - Virus entdeckt: Infektion breitet sich aus, Start = Quarantäne.
  - Schilde ausgesetzt: Prozent fallen, Segmente fallen aus, manchmal kommen sie zurück.
  - Eindringling im System: Ortung läuft, manchmal isoliert, manchmal Alarm.
  - Fehlalarm: kurzer Riss, dann FEHLALARM und weiter.
Eingabe: Pfeiltasten (D-Pad), ENTER / Leertaste (Startknopf).
"""
from __future__ import annotations

import random
import time

import pygame

CODE, BREAK, ERROR, RECOVERY, REBOOT, PROMPT, VIRUS, SHIELDS, STABLE, ALARM, INTRUDER = range(1, 12)

# Wort-IDs aus dem Shader (Tabelle in frag.glsl)
W_ZUGRIFF, W_FALSCH, W_KEINE_ANTWORT, W_UEBERNIMMT = 38, 39, 40, 41
W_QUARANTAENE, W_SYSTEM_STABIL, W_ALARM, W_SPERRE, W_FEHLALARM, W_ISOLIERT = 43, 49, 50, 51, 52, 48
W_SCHILDE_OBEN, W_EINDRINGLING = 45, 46

PROMPT_KEYS = {
    1: (pygame.K_UP,), 2: (pygame.K_DOWN,), 3: (pygame.K_LEFT, pygame.K_a), 4: (pygame.K_RIGHT, pygame.K_d),
    5: (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE),
}
ALL_PROMPT_KEYS = {k for keys in PROMPT_KEYS.values() for k in keys}


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.demo = demo
        self.seed = self.rng.uniform(1.0, 900.0)
        self.cycle = 0
        self.code_var = -1
        self.err_var = -1
        self.last_event = ""
        self.cycles_since_prompt = 99
        self.queue: list[tuple[int, float, dict]] = []   # (Phase, Länge, Extras)
        self.phase = CODE
        self.phase_t0 = time.monotonic()
        self.phase_len = 1.0
        self.extra: dict = {}
        self.code_t0 = self.phase_t0
        self.code_len = 12.0
        self.glitch = 1.0
        self.prompt = 0
        self.outcome = 0.0
        self.pct = 0.0
        self.word_a = 0
        self.word_b = -1
        self.demo_answer_at = 0.0
        self._new_cycle()

    # -- Planung -----------------------------------------------------------
    def _pick(self, n: int, avoid: int) -> int:
        choices = [i for i in range(n) if i != avoid]
        return self.rng.choice(choices)

    def _new_cycle(self) -> None:
        self.cycle += 1
        self.seed = self.rng.uniform(1.0, 900.0)
        self.code_var = 0 if self.cycle == 1 else self._pick(6, self.code_var)
        self.err_var = self._pick(6, self.err_var)
        self.glitch = self.rng.uniform(0.6, 1.4)
        self.code_len = self.rng.uniform(9.0, 18.0)
        self.cycles_since_prompt += 1
        r = self.rng.random()
        plan: list[tuple[int, float, dict]] = []
        err = [(ERROR, self.rng.uniform(3.5, 6.0), {}), (RECOVERY, self.rng.uniform(1.5, 4.0), {}), (REBOOT, 0.8, {})]
        crash = [(BREAK, self.rng.uniform(1.8, 3.5), {})] + err
        if r < 0.11 and self.cycles_since_prompt >= 3 and self.last_event != "prompt":
            plan = [(PROMPT, self.rng.uniform(6.0, 8.0), {"prompt": self.rng.randint(1, 5)})]
            self.last_event = "prompt"
            self.cycles_since_prompt = 0
        elif r < 0.23 and self.last_event != "virus":
            good = self.rng.random() < 0.4
            plan = [(VIRUS, self.rng.uniform(6.0, 8.0), {"good": good})]
            plan += [(RECOVERY, 2.5, {}), (REBOOT, 0.8, {})] if good else crash
            self.last_event = "virus"
        elif r < 0.33 and self.last_event != "shields":
            good = self.rng.random() < 0.5
            plan = [(SHIELDS, self.rng.uniform(5.0, 7.0), {"good": good})]
            plan += [] if good else crash
            self.last_event = "shields"
        elif r < 0.43 and self.last_event != "intruder":
            good = self.rng.random() < 0.5
            plan = [(INTRUDER, self.rng.uniform(6.0, 9.0), {"good": good})]
            plan += [(STABLE, 2.5, {"wa": W_SYSTEM_STABIL, "wb": W_ISOLIERT})] if good else \
                    [(ALARM, 3.0, {"wa": W_ALARM, "wb": W_EINDRINGLING})] + err
            self.last_event = "intruder"
        elif r < 0.50:
            plan = [(BREAK, 0.7, {}), (STABLE, 2.5, {"wa": W_FEHLALARM, "wb": -1})]
            self.last_event = "false"
        else:
            plan = crash
            self.last_event = "crash"
        self.queue = [(CODE, self.code_len, {})] + plan
        self._next()

    def _next(self) -> None:
        if not self.queue:
            self._new_cycle()
            return
        phase, length, extra = self.queue.pop(0)
        self.phase, self.phase_len, self.extra = phase, length, extra
        self.phase_t0 = time.monotonic()
        self.outcome = 0.0
        self.pct = 0.0
        self.prompt = int(extra.get("prompt", 0))
        self.word_a = int(extra.get("wa", 0))
        self.word_b = int(extra.get("wb", -1))
        if phase == CODE:
            self.code_t0 = self.phase_t0
        if phase == PROMPT and self.demo:
            self.demo_answer_at = self.phase_t0 + self.rng.uniform(1.5, 9.0)

    # -- Eingabe -------------------------------------------------------------
    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN or ev.key not in ALL_PROMPT_KEYS:
            return
        self._key(ev.key)

    def _key(self, key: int) -> None:
        now = time.monotonic()
        if self.phase == PROMPT and self.outcome < 0.5:
            if key in PROMPT_KEYS[self.prompt]:
                self.queue = [(STABLE, 3.0, {"wa": W_ZUGRIFF, "wb": W_SYSTEM_STABIL}), (CODE, self.rng.uniform(8.0, 14.0), {})]
            else:
                self.queue = [(ALARM, 3.5, {"wa": W_FALSCH, "wb": W_SPERRE}), (BREAK, 2.5, {}),
                              (ERROR, 5.0, {}), (RECOVERY, 2.0, {}), (REBOOT, 0.8, {})]
            self._next()
        elif self.phase == VIRUS and self.outcome < 0.5 and key in PROMPT_KEYS[5]:
            # Quarantäne per Startknopf: Infektion geht zurück, dann Wiederherstellung
            self.outcome = 1.0
            self.extra["good"] = True
            self.extra["quarantine_t"] = now - self.phase_t0
            self.extra["quarantine_pct"] = self.pct
            self.queue = [(RECOVERY, 2.5, {}), (REBOOT, 0.8, {})]
            self.phase_len = (now - self.phase_t0) + 2.5

    # -- Zustand -------------------------------------------------------------
    def _advance(self) -> None:
        now = time.monotonic()
        pt = now - self.phase_t0
        if self.phase == VIRUS:
            if self.outcome < 0.5:
                self.pct = min(1.0, pt / (self.phase_len * 0.85))
                if self.extra.get("good") and pt >= self.phase_len * 0.7:
                    self.outcome = 1.0
                    self.extra["quarantine_t"] = pt
                    self.extra["quarantine_pct"] = self.pct
            else:
                qt = pt - self.extra.get("quarantine_t", 0.0)
                self.pct = max(0.0, self.extra.get("quarantine_pct", 1.0) * (1.0 - qt / 2.0))
        elif self.phase == SHIELDS:
            if self.extra.get("good"):
                half = self.phase_len * 0.55
                if pt < half:
                    self.pct = max(0.0, 1.0 - pt / half)
                else:
                    self.outcome = 1.0
                    self.pct = min(1.0, (pt - half) / (self.phase_len - half))
            else:
                self.pct = max(0.0, 1.0 - pt / (self.phase_len * 0.9))
        elif self.phase == INTRUDER:
            self.pct = min(1.0, pt / (self.phase_len * 0.8))
            if self.extra.get("good") and self.pct >= 1.0:
                self.outcome = 1.0
        elif self.phase == PROMPT and self.demo and now >= self.demo_answer_at and self.outcome < 0.5:
            self.demo_answer_at = now + 99.0
            self._key(self.rng.choice((PROMPT_KEYS[self.prompt][0], pygame.K_UP)))
        if pt >= self.phase_len:
            if self.phase == PROMPT:          # keine Antwort: das System übernimmt
                self.queue = [(ALARM, 3.5, {"wa": W_KEINE_ANTWORT, "wb": W_UEBERNIMMT}), (ERROR, 5.0, {}),
                              (RECOVERY, 3.0, {}), (REBOOT, 0.8, {})]
            self._next()

    # -- Schnittstelle zur Engine ----------------------------------------------
    def uniform_names(self):
        return ("uSeed", "uPhase", "uPhaseT", "uPhaseLen", "uCodeVar", "uErrVar", "uCodeT", "uCodeProg",
                "uPrompt", "uOutcome", "uGlitch", "uPct", "uWordA", "uWordB")

    def uniforms(self, t: float, f) -> dict:
        self._advance()
        now = time.monotonic()
        code_t = now - self.code_t0
        return {
            "uSeed": self.seed,
            "uPhase": float(self.phase),
            "uPhaseT": now - self.phase_t0,
            "uPhaseLen": self.phase_len,
            "uCodeVar": float(self.code_var),
            "uErrVar": float(self.err_var),
            "uCodeT": code_t,
            "uCodeProg": min(1.0, code_t / max(self.code_len, 1.0)),
            "uPrompt": float(self.prompt),
            "uOutcome": self.outcome,
            "uGlitch": self.glitch,
            "uPct": self.pct,
            "uWordA": float(self.word_a),
            "uWordB": float(self.word_b),
        }

    def overlays(self, t: float):
        return []
