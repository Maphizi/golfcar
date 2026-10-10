"""GNN, Galaktisches Nachrichten-Netz: Holo-Studio, ein Droiden-Sprecher liest absurde Meldungen vor,
die das lokale Sprachmodell erfindet (Schlagzeile plus ein bis zwei Sätze), dazu Laufband und
Wetter für drei Planeten.

Tasten: Start (ENTER) = nächste Meldung, LINKS/RECHTS = Ressort wechseln,
Kippschalter (SPACE/BACKSPACE) = Pause / weiter.
"""
from __future__ import annotations

import logging
import math
import random
import threading
import time

import pygame

from kitt.ui.persona import PersonaUI
from launcher import config as lcfg

log = logging.getLogger("news")

CATEGORIES = ["GALAXIS", "GOLFPLATZ", "SPORT", "WIRTSCHAFT", "PROMI", "TECHNIK", "VERKEHR"]
CANNED = [
    ("GALAXIS", "Imperiale Behörde verlegt Loch sieben um vierzig Lichtjahre",
     "Die Spieler wurden gebeten, Proviant für drei Wochen mitzuführen. Ein Sprecher nannte die Maßnahme eine Verbesserung des Spielflusses."),
    ("TECHNIK", "Droide gewinnt Wettbewerb im Stillstehen, Jury schläft ein",
     "Der Sieger erklärte, er habe lediglich auf ein Software-Update gewartet. Die Trophäe wurde ihm per Funk überreicht."),
    ("GOLFPLATZ", "Unbekannter Gleiter auf dem Fairway gesichtet, trägt Getränkehalter",
     "Die Besatzung gab an, nur kurz nach dem Weg zu fragen. Das Clubhaus hat vorsorglich die Schilde hochgefahren."),
    ("WIRTSCHAFT", "Preis für Kühlflüssigkeit erreicht neues Rekordhoch an Loch neunzehn",
     "Analysten führen den Anstieg auf starke Nachfrage nach der Rückneun zurück. Die Zentralbank verweist auf saisonale Effekte."),
    ("SPORT", "Pilot schlägt weißen Kleinplaneten in Umlaufbahn, Par nicht anerkannt",
     "Der Ball umrundet den Planeten seit Dienstag. Die Spielleitung wartet mit der Wertung, bis er landet."),
    ("PROMI", "Bekannter Astromech ändert Namen in eine Reihe von Pieptönen",
     "Fans zeigten sich gespalten, die Hälfte konnte den neuen Namen nicht aussprechen. Der Droide selbst nannte das Problem lösbar."),
    ("VERKEHR", "Stau im Hyperraum: Zwölf Lichtjahre Rückstau vor der Sprungspur Nord",
     "Grund ist ein liegengebliebener Frachter mit Vorfahrt. Die Verkehrsleitstelle empfiehlt, den Umweg über den Nebel zu nehmen."),
]
PLANETS = ["HOTH", "TATOOINE", "ENDOR", "BESPIN", "KAMINO", "MUSTAFAR", "NABOO", "DAGOBAH", "JAKKU", "CORUSCANT"]
WEATHER_WORDS = ["Eisnebel", "Sandsturm", "heiter", "Ascheregen", "Dauerregen", "Lavaböen", "windstill", "Sumpfdunst", "Smog", "Sternenklar"]


class Item:
    def __init__(self, category: str, headline: str, body: str, breaking: bool = False):
        self.category, self.headline, self.body, self.breaking = category, headline, body, breaking


class NewsUI(PersonaUI):
    scene_name = "newsroom"
    uniform_names = ("uState", "uStateT", "uLevel", "uBreaking", "uPanel", "uTalk")
    window_title = "GNN"

    def __init__(self, *a, **kw):
        self.rng = random.Random()
        self.items: list[Item] = []
        self.history: list[str] = []
        self.current: Item | None = None
        self.current_since = 0.0
        self.item_no = 0
        self.category_next = ""
        self.paused = False
        self.skip = threading.Event()
        self.weather: list[tuple[str, int, str]] = []
        self.generating = False
        self.ready = threading.Event()
        self.ticker_x = 1.0
        super().__init__(*a, **kw)
        self._new_weather()

    def prepare_cfg(self, cfg: dict) -> None:
        cfg["llm"]["system_prompt"] = str(lcfg.ROOT / "kitt" / "personality" / "news_prompt.txt")
        cfg["llm"]["history_turns"] = 0
        cfg["llm"]["max_tokens"] = 110
        cfg["llm"]["ctx"] = 3072
        cfg["llm"]["temperature"] = 0.95
        cfg["stt"]["enabled"] = False
        cfg["voice"]["mood"] = False
        tts = cfg["tts"]
        tts["pitch_factor"] = 0.92
        tts["robot"] = True
        tts["robot_mix"] = 0.4
        cfg["ui"]["greeting"] = ""

    def use_mic(self) -> bool:
        return False

    # -- Inhalte ---------------------------------------------------------------
    def _new_weather(self) -> None:
        picks = self.rng.sample(PLANETS, 3)
        self.weather = [(p, self.rng.randint(-120, 95), self.rng.choice(WEATHER_WORDS)) for p in picks]

    def _generate(self, category: str) -> Item | None:
        """Eine Meldung vom Sprachmodell holen (blockiert, läuft im Hintergrund)."""
        if not (self.pipe and self.pipe.kitt):
            return None
        from kitt.context import context_block
        facts = context_block() if category == "GOLFPLATZ" else ""
        avoid = ("Bereits gemeldet (nicht wiederholen): " + " | ".join(self.history[-4:])) if self.history else ""
        msg = f"Ressort: {category}. Nächste Meldung.\n{facts}\n{avoid}".strip()
        try:
            self.pipe.kitt.reset()
            res = self.pipe.kitt.ask(msg)
        except Exception as exc:
            log.warning("Generierung fehlgeschlagen: %s", exc)
            return None
        head, body = "", ""
        for line in res.text.splitlines():
            low = line.strip().lower()
            if low.startswith("schlagzeile:"):
                head = line.split(":", 1)[1].strip().strip('"')
            elif low.startswith("meldung:"):
                body = line.split(":", 1)[1].strip()
        if not head:
            parts = [ln.strip() for ln in res.text.splitlines() if ln.strip()]
            if parts:
                head, body = parts[0][:90], " ".join(parts[1:])[:220]
        if not head:
            return None
        return Item(category, head.rstrip("."), body, breaking=self.rng.random() < 0.2)

    def _producer(self) -> None:
        """Hintergrund: hält ein bis zwei Meldungen vorrätig."""
        while self.running:
            if len(self.items) < 2 and not self.generating:
                self.generating = True
                cat = self.category_next or self.rng.choice(CATEGORIES)
                self.category_next = ""
                item = self._generate(cat) if not self.demo else None
                if item is None:
                    c = self.rng.choice(CANNED)
                    item = Item(c[0], c[1], c[2], breaking=self.rng.random() < 0.2)
                self.items.append(item)
                self.generating = False
            time.sleep(0.3)

    def _anchor(self) -> None:
        """Vordergrund-Ablauf: Meldung zeigen, vorlesen, kurz halten, nächste."""
        self.ready.wait()
        while self.running:
            if self.paused or not self.items:
                time.sleep(0.2)
                continue
            self.skip.clear()
            self.item_no += 1
            item = self.items.pop(0)
            self.current, self.current_since = item, time.monotonic()
            self.history.append(item.headline)
            self.on_text("kitt", "")
            text = item.headline + ". " + item.body
            if self.pipe and not self.demo:
                try:
                    self.pipe.say(text)
                except Exception:
                    log.exception("Sprechen fehlgeschlagen")
            else:
                self.on_state("speaking")
                time.sleep(4.0)
                self.on_state("idle")
            hold = 3.5 if not self.demo else 2.0
            t0 = time.monotonic()
            while self.running and time.monotonic() - t0 < hold and not self.skip.is_set():
                time.sleep(0.1)
            if self.item_no % 4 == 0:
                self._new_weather()

    def on_pipeline_ready(self) -> None:
        self.ready.set()

    def start_pipeline(self) -> None:
        threading.Thread(target=self._producer, daemon=True).start()
        threading.Thread(target=self._anchor, daemon=True).start()
        super().start_pipeline()

    def run_demo(self) -> None:
        self.on_state("idle")
        self.ready.set()
        threading.Thread(target=self._producer, daemon=True).start()
        self._anchor()

    # -- Eingabe -----------------------------------------------------------------
    def handle_key(self, key: int) -> None:
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.skip.set()
        elif key == pygame.K_SPACE:
            self.paused = True
        elif key == pygame.K_BACKSPACE:
            self.paused = False
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            cur = CATEGORIES.index(self.category_next) if self.category_next in CATEGORIES else 0
            self.category_next = CATEGORIES[(cur + (1 if key in (pygame.K_RIGHT, pygame.K_d) else -1)) % len(CATEGORIES)]
            self.items.clear()

    # -- Darstellung -------------------------------------------------------------
    def extra_uniforms(self, now: float, state: str, since: float) -> dict:
        item = self.current
        return {"uBreaking": 1.0 if item and item.breaking and now - self.current_since < 6.0 else 0.0,
                "uPanel": 1.0 if self.item_no % 4 == 3 else 0.0,
                "uTalk": 1.0 if state == "speaking" else 0.0}

    def draw_overlays(self, now: float, state: str, lu: str, lk: str) -> None:
        self.text("GNN  GALAKTISCHES NACHRICHTEN-NETZ", 0.024, 0.03, 0.955, (255, 214, 10), 0.9, center=False)
        self.text(time.strftime("%H:%M") + "  STANDARDZEIT", 0.02, 0.97 - 0.19, 0.955, (200, 200, 210), 0.7, center=False)
        if state in ("loading", "init"):
            self.text("SENDER WIRD AUFGEBAUT", 0.04, 0.5, 0.5, (255, 214, 10), 0.6 + 0.4 * math.sin(now * 4.0))
            return
        item = self.current
        if item:
            cat = item.category + ("   +++ EILMELDUNG +++" if item.breaking and now - self.current_since < 6.0 else "")
            self.text(cat, 0.022, 0.06, 0.335, (255, 80, 60) if item.breaking else (120, 200, 255), 0.95, center=False)
            for i, ln in enumerate(self.wrap(item.headline.upper(), 44)[:2]):
                self.text(ln, 0.042, 0.06, 0.28 - i * 0.055, (245, 245, 250), 1.0, center=False)
            for i, ln in enumerate(self.wrap(item.body, 78)[:3]):
                self.text(ln, 0.022, 0.06, 0.165 - i * 0.033, (210, 215, 225), 0.9, center=False)
        if self.paused:
            self.text("PAUSE", 0.03, 0.5, 0.6, (255, 214, 10), 0.6 + 0.4 * math.sin(now * 3.0))
        if self.item_no % 4 == 3 and self.weather:
            self.text("AUSSENKLIMA", 0.022, 0.86, 0.76, (255, 214, 10), 0.9)
            for i, (pl, temp, word) in enumerate(self.weather):
                self.text(f"{pl:<10} {temp:+4d}°", 0.02, 0.86, 0.71 - i * 0.075, (230, 230, 240), 0.95)
                self.text(word, 0.016, 0.86, 0.68 - i * 0.075, (170, 180, 200), 0.8)
        # Laufband: letzte Schlagzeilen
        if self.history:
            band = "   +++   ".join(h.upper() for h in self.history[-5:]) + "   +++   "
            self.ticker_x -= 0.0016
            if self.ticker_x < -0.02 * len(band) * 0.6:
                self.ticker_x = 1.0
            self.text(band, 0.022, self.ticker_x, 0.04, (240, 240, 240), 0.95, center=False)
        if self.category_next:
            self.text("NÄCHSTES RESSORT: " + self.category_next, 0.018, 0.5, 0.42, (120, 200, 255), 0.8)
