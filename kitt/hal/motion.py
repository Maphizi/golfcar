"""Langsame Bewegung des HAL-Korridors aus der Musik.

Alles hier ist bewusst träge: der Korridor treibt langsam nach vorn oder hinten (uDrift, uDir), die
Helligkeit folgt einer über Sekunden geglätteten Energie (uEnergy), ein Drop (Beat nach einer leisen
Stelle) kann die Fahrtrichtung umkehren und lässt den Gang kurz anschwellen (uDrop). Dazu seltene
Ereignisse: eine einzelne andersfarbige Zelle hüpft durch die Wand (uAccent), eine langsame Farbwelle
läuft durch den Gang (uWash). uVariant würfelt pro Start das Zellenmuster.
"""
from __future__ import annotations

import logging
import random
import time

log = logging.getLogger("hal.motion")

ACCENT_HUES = 5          # 0 cyan, 1 grün, 2 weiß, 3 violett, 4 gelb (Tabelle im Shader)
VARIANTS = 5
CELLS = {0: (14, 7), 1: (28, 3), 2: (7, 4), 3: (18, 9), 4: (14, 7)}   # Spalten je Gangeinheit, Reihen (wie im Shader)


class CorridorMotion:
    uniform_names = ("uDrift", "uDir", "uEnergy", "uBassS", "uDrop", "uVariant", "uAccent", "uWash")

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        now = time.monotonic()
        self.last = now
        self.drift = self.rng.uniform(0.0, 6.0)
        self.dir_target = self.rng.choice((-1.0, 1.0))
        self.dir = self.dir_target
        self.energy = 0.0        # langsam (≈2.5 s)
        self.e_fast = 0.0        # schnell (≈0.3 s)
        self.bass_s = 0.0
        self.drop = 0.0
        self.quiet_since: float | None = None
        self.armed = False
        self.last_drop_at = now
        self.next_flip_at = now + self.rng.uniform(70.0, 140.0)
        self.variant = self.rng.randrange(VARIANTS)
        # Akzentzelle: (Zellenindex entlang des Gangs, Farbe, Reihe, Seite); aktiv solange hops < hops_max
        self.accent_on = False
        self.accent_cell = 0.0
        self.accent_hue = 0
        self.accent_row = 0
        self.accent_side = 1.0
        self.accent_hops = 0
        self.accent_hops_max = 0
        self.accent_last_hop = now
        self.next_accent_at = now + self.rng.uniform(8.0, 20.0)
        # Farbwelle: Fortschritt 0..1 über ~10 s
        self.wash_t0: float | None = None
        self.wash_hue = 0
        self.wash_dur = 10.0
        self.next_wash_at = now + self.rng.uniform(40.0, 90.0)
        log.info("HAL-Korridor: Variante %d, Richtung %+.0f", self.variant, self.dir)

    def update(self, now: float, f) -> dict:
        dt = min(0.1, max(0.0, now - self.last))
        self.last = now
        rms = float(getattr(f, "rms", 0.0)) if f is not None else 0.0
        bass = float(getattr(f, "bass", 0.0)) if f is not None else 0.0
        beat = float(getattr(f, "beat", 0.0)) if f is not None else 0.0
        silent = bool(getattr(f, "silent", True)) if f is not None else True
        live = 0.0 if silent else 1.0
        self.e_fast += (rms * live - self.e_fast) * min(1.0, dt / 0.3)
        self.energy += (rms * live - self.energy) * min(1.0, dt / 2.5)
        self.bass_s += (bass * live - self.bass_s) * min(1.0, dt / 0.6)
        # Drop: nach einer leisen Stelle (≥ 0.4 s deutlich unter dem Mittel) kommt ein Beat mit Energie
        if live and self.energy > 0.03 and self.e_fast < 0.5 * self.energy:
            if self.quiet_since is None:
                self.quiet_since = now
            elif now - self.quiet_since > 0.4:
                self.armed = True
        else:
            self.quiet_since = None
        if self.armed and beat > 0.5 and self.e_fast > 1.05 * self.energy and now - self.last_drop_at > 12.0:
            self.armed = False
            self.last_drop_at = now
            self.drop = 1.0
            if self.rng.random() < 0.7:
                self.dir_target = -self.dir_target
                log.info("Drop: Korridor wechselt die Richtung (%+.0f)", self.dir_target)
            self.next_flip_at = now + self.rng.uniform(70.0, 140.0)
        if now >= self.next_flip_at:                      # ohne Drops: ab und zu trotzdem umkehren
            self.dir_target = -self.dir_target
            self.next_flip_at = now + self.rng.uniform(70.0, 140.0)
        self.drop = max(0.0, self.drop - dt / 3.5)
        # Richtung weich wechseln (der Gang bremst ab und fährt rückwärts an), Tempo sehr niedrig
        self.dir += (self.dir_target - self.dir) * min(1.0, dt / 2.5)
        speed = 0.05 + 0.14 * self.energy + 0.06 * self.bass_s + 0.12 * self.drop
        self.drift = (self.drift + dt * speed * self.dir) % 1000.0
        self._update_accent(now, beat, live)
        self._update_wash(now)
        if self.wash_t0 is None:
            wash = (0.0, 0.0, 0.0, 0.0)
        else:
            prog = (now - self.wash_t0) / self.wash_dur
            wash = (prog, float(self.wash_hue), 1.0, 0.0)
        return {"uDrift": self.drift, "uDir": self.dir, "uEnergy": self.energy, "uBassS": self.bass_s,
                "uDrop": self.drop, "uVariant": float(self.variant),
                "uAccent": (self.accent_cell, float(self.accent_hue), float(self.accent_row), self.accent_side)
                if self.accent_on else (0.0, 0.0, 0.0, 0.0),
                "uWash": wash}

    def _update_accent(self, now: float, beat: float, live: float) -> None:
        if not self.accent_on:
            if now >= self.next_accent_at:
                self.accent_on = True
                self.accent_hue = self.rng.randrange(ACCENT_HUES)
                self.accent_side = self.rng.choice((-1.0, 1.0, 3.0, 5.0))
                # Zellenindex entlang des Gangs: der Shader rechnet cell.x = floor((Tiefe*6 - uDrift) * Spalten)
                # Start hinten oder vorn, je nach Fahrtrichtung; dann hüpft die Zelle entgegen
                cols, rows = CELLS[self.variant]
                self.accent_row = self.rng.randrange(-rows + 1, rows - 1)
                far, near = (6.0 - self.drift) * cols, -self.drift * cols
                self.accent_from_far = self.dir > 0
                self.accent_cell = float(int(far if self.accent_from_far else near))
                self.accent_hops = 0
                self.accent_hops_max = self.rng.randint(40, 80)
                self.accent_last_hop = now
            return
        hop = (beat > 0.45 and live and now - self.accent_last_hop > 0.25) or now - self.accent_last_hop > 0.8
        if hop:
            self.accent_last_hop = now
            self.accent_hops += 1
            self.accent_cell += -1.0 if self.accent_from_far else 1.0
            if self.rng.random() < 0.15:                    # ab und zu eine Reihe höher oder tiefer
                rows = CELLS[self.variant][1]
                self.accent_row = max(-rows, min(rows - 1, self.accent_row + self.rng.choice((-1, 1))))
        if self.accent_hops >= self.accent_hops_max:
            self.accent_on = False
            self.next_accent_at = now + self.rng.uniform(15.0, 45.0)

    def _update_wash(self, now: float) -> None:
        if self.wash_t0 is None:
            if now >= self.next_wash_at:
                self.wash_t0 = now
                self.wash_hue = self.rng.randrange(ACCENT_HUES)
                self.wash_dur = self.rng.uniform(8.0, 14.0)
        elif now - self.wash_t0 > self.wash_dur:
            self.wash_t0 = None
            self.next_wash_at = now + self.rng.uniform(40.0, 100.0)

    def demo_kick(self) -> None:
        """Tests: Akzent und Welle sofort starten."""
        self.next_accent_at = 0.0
        self.next_wash_at = 0.0
