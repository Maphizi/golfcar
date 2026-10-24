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

from kitt.hal import figures as figures_mod
from kitt.hal.figures import Figures
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



def _key_code(name: str) -> int:
    """SDL-Keycode für F16/F17 (pygame hat dafür keine Konstante)."""
    try:
        return pygame.key.key_code(name)
    except Exception:
        return -1

class HalUI(PersonaUI):
    scene_name = "hal"
    uniform_names = ("uState", "uStateT", "uLevel", "uTalk", "uBright", "uVoice", "uTalkMode") + CorridorMotion.uniform_names + Figures.uniform_names
    window_title = "HAL 3000"

    def __init__(self, *a, **kw):
        self.rng = random.Random()
        self.bright = 1.0
        self.motion = CorridorMotion(self.rng)
        self.figures = Figures(self.rng)
        if os.environ.get("KITT_HAL_VARIANT"):                  # Tests: Zellenmuster vorgeben
            self.motion.variant = int(os.environ["KITT_HAL_VARIANT"]) % 5
        if os.environ.get("KITT_HAL_FIGURE"):                   # Tests: Figur vorgeben (0 HAL, 1, 2, 3 beide)
            self.figures.set_mode(int(os.environ["KITT_HAL_FIGURE"]) % 4)
        self.next_prompt_at = time.monotonic() + 40.0
        self._turns_seen = 0
        self.talk_mode = False          # Sprechmodus: Musik leise, Mikrofon an
        self.banner = ""                # Autopilot-Schalter (F16/F17): kurze Anzeige
        self.banner_t0 = -1e9
        # vor super().__init__ (prepare_cfg läuft dort): ohne Mikrofon keine Spracherkennung laden
        self.mic = bool(lcfg.load_settings().get("hal", {}).get("mic", False))
        self.base_volume: float | None = None
        self._ducked = False
        super().__init__(*a, **kw)
        self.duck_percent = int(self.settings.get("volume", {}).get("duck_percent", 25))
        hal_cfg = self.settings.get("hal", {})
        self.kipp_talk = bool(hal_cfg.get("kipp_talk", False))          # Kippschalter schaltet Sprechmodus (alt)
        self.talk_timeout = float(hal_cfg.get("talk_timeout", 150))      # s ohne Gespräch -> Sprechmodus aus
        self.talk_last_activity = time.monotonic()
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
        if not self.mic:
            cfg["stt"]["enabled"] = False
        cfg["voice"]["require_name"] = False
        cfg["voice"]["max_sentences"] = 3
        cfg["voice"]["mood"] = False
        tts = cfg["tts"]                    # dieselben Werte stehen in config/announce.toml [themes.spacetaxi] (Ansagen)
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

    def use_mic(self) -> bool:
        return self.mic

    def set_talk_mode(self, on: bool) -> None:
        if not self.mic:
            if on:
                log.info("Sprechtaste ignoriert: HAL läuft ohne Mikrofon ([hal].mic = false), Musik bleibt normal")
            return
        if on == self.talk_mode:
            return
        self.talk_mode = on
        self.talk_last_activity = time.monotonic()
        log.info("Sprechmodus %s (Musik %s, Mikrofon %s)", "AN" if on else "AUS", "leise" if on else "normal", "an" if on else "aus")
        if self.pipe and self.pipe.cap:
            (self.pipe.cap.resume if on else self.pipe.cap.suspend)()
        if self.pipe and self.pipe.listener:
            (self.pipe.listener.resume if on else self.pipe.listener.pause)()
        threading.Thread(target=self._update_duck, args=(self.state == "speaking",), daemon=True).start()

    def on_state(self, s: str) -> None:
        super().on_state(s)
        if self.talk_mode:
            threading.Thread(target=self._update_duck, args=(s == "speaking",), daemon=True).start()

    def on_pipeline_ready(self) -> None:
        # Mikrofon bleibt aus (Stream geschlossen), bis die Sprechtaste gedrückt wird
        if not self.talk_mode:
            if self.pipe.listener:
                self.pipe.listener.pause()
            if self.pipe.cap:
                self.pipe.cap.suspend()
        line = self.rng.choice(GREETINGS)
        self.pipe.say(line)
        self.on_text("kitt", line)
        self.next_prompt_at = time.monotonic() + self.rng.uniform(40.0, 70.0)

    def handle_key(self, key: int) -> None:
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.next_prompt_at = 0.0
        elif key == pygame.K_F15:                       # Sprechtaste (Launcher-Action "talk"): umschalten
            self.set_talk_mode(not self.talk_mode)
        elif key in (_key_code("F16"), _key_code("F17")):      # Autopilot-Schalter: nur anzeigen
            self.banner = "AUTOPILOT AN" if key == _key_code("F16") else "AUTOPILOT AUS"
            self.banner_t0 = time.monotonic()
        elif key == pygame.K_SPACE and self.kipp_talk:
            self.set_talk_mode(True)
        elif key == pygame.K_BACKSPACE and self.kipp_talk:
            self.set_talk_mode(False)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.figures.set_mode(figures_mod.MODE_ASTRO)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.figures.set_mode(figures_mod.MODE_ALIEN)
        elif key in (pygame.K_UP, pygame.K_w):
            self.figures.set_mode(figures_mod.MODE_BOTH)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.figures.set_mode(figures_mod.MODE_HAL)

    def tick(self, now: float) -> None:
        if self.demo or not self.pipe:
            if self.demo and not getattr(self, "_demo_kicked", False):
                self._demo_kicked = True
                self.motion.demo_kick()
            return
        # Die Pipeline gibt das Mikrofon nach jeder Runde wieder frei; ohne Sprechmodus wieder schließen,
        # und zwar den Stream selbst (ein offenes Bluetooth-Mikrofon würde die Musik ins Headset-Profil zwingen)
        if not self.talk_mode and not self.pipe.busy.is_set():
            if self.pipe.listener and self.pipe.listener.enabled:
                self.pipe.listener.pause()
            if self.pipe.cap and not self.pipe.cap.suspended:
                self.pipe.cap.suspend()
        if self.pipe.stats.get("turns", 0) != self._turns_seen:
            self._turns_seen = self.pipe.stats["turns"]
            self.next_prompt_at = now + self.rng.uniform(45.0, 90.0)
            self.talk_last_activity = now
        if self.pipe.state != "idle":
            self.talk_last_activity = now
        # Sicherheitsnetz: Sprechmodus vergessen -> nach talk_timeout s ohne Gespräch wieder Musik normal
        if self.talk_mode and self.talk_timeout > 0 and now - self.talk_last_activity > self.talk_timeout:
            log.info("Sprechmodus nach %.0f s ohne Gespräch beendet", self.talk_timeout)
            self.set_talk_mode(False)
        if now >= self.next_prompt_at and self.pipe.state == "idle":
            self.ask_hidden(self.rng.choice(PROMPTS))
            self.next_prompt_at = now + self.rng.uniform(50.0, 100.0)

    def images(self) -> dict:
        return self.figures.images()

    def led_state(self) -> dict:
        """Für launcher/ledstream.py: ruhiges HAL-Programm (Atmen, wanderndes Feld)."""
        return {"program": "hal", "talk": self.talk_mode}

    def extra_uniforms(self, now: float, state: str, since: float) -> dict:
        out = self.motion.update(now, self.last_f)
        out.update(self.figures.update(now, self.last_f))
        out.update({"uTalk": 1.0 if state == "speaking" else 0.0, "uBright": self.bright,
                    "uVoice": self.voice_rms, "uTalkMode": 1.0 if self.talk_mode else 0.0})
        return out

    def draw_overlays(self, now: float, state: str, lu: str, lk: str) -> None:
        if now - self.banner_t0 < 2.5:
            a = min(1.0, (2.5 - (now - self.banner_t0)) / 0.6)
            self.text(self.banner, 0.06, 0.5, 0.5, (120, 255, 200) if self.banner.endswith("AN") else (255, 120, 90), a)
        if self.figures.mix < 0.5:
            self.text("HAL", 0.032, 0.479, 0.713, (40, 160, 255), 1.0 - 2.0 * self.figures.mix)
            self.text("3000", 0.032, 0.526, 0.713, (240, 240, 245), 1.0 - 2.0 * self.figures.mix)
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
        talk = "SPRECHTASTE  MUSIK WIEDER LAUT, MIKRO AUS" if self.talk_mode else "SPRECHTASTE  MUSIK LEISE, MIKRO AN"
        if not self.mic:
            talk = "OHNE MIKROFON"
        elif self.kipp_talk:
            talk = "KIPPSCHALTER  SPRECHEN (MUSIK LEISE)"
        self.text(f"{talk}      START  HAL FRAGEN      KNÜPPEL  LINKS ASTRONAUT  RECHTS ALIEN  OBEN BEIDE  UNTEN HAL", 0.015, 0.5, 0.03, (110, 60, 60), 0.5 + 0.2 * math.sin(now * 2.0))
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
