"""Taxistand (Taste 1): Startbildschirm und Themenwahl für das ganze Programm.

Links groß das Plakat des Themas (eigenes Bild aus assets/themes/<name>.png, sonst ein vom Shader
gezeichnetes Plakat), rechts daneben der Pilot als "Space Taxi Driver"-Plakat im gleichen
Duotone-Stil, darunter Titel, Zeile und Taxilizenz. D-Pad LINKS/RECHTS blättert durch die Themen,
Start (ENTER) bestätigt. Die Wahl steht in logs/theme.txt und geht als KITT_THEME an alle Modi.

Jeder Start würfelt neu: Accessoire (Sonnenbrille, Taximütze), Lizenznummer, Taxinummer, Sprüche,
Zahlen. Reagiert auf Musik: Sterne, Schachbrettband und Neon laufen mit Bass und Beat.
"""
from __future__ import annotations

import logging
import random
import time

import numpy as np
import pygame

from launcher import config as lcfg, theme as ltheme, wled

log = logging.getLogger("taxi")
PHOTO = lcfg.ROOT / "assets" / "pilot.png"
DRIVER = lcfg.ROOT / "assets" / "taxi" / "driver.png"

GOLD = (255, 214, 10)
DIM = (150, 140, 90)
WHITE = (240, 240, 245)
GREY = (120, 120, 130)

SLOGANS = [
    "WIR FAHREN ÜBERALL HIN. AUSSER ZURÜCK.", "KEIN TRINKGELD, KEIN NACHBRENNER.",
    "SCHNELLER ALS DEIN CADDIE. MEISTENS.", "TARIF 3: HYPERRAUM, OHNE GEWÄHR.",
    "EINSTEIGEN, ANSCHNALLEN, NICHT FRAGEN.", "DER FAHRER HAT IMMER RECHT. DER TAXAMETER AUCH.",
    "WIR KENNEN JEDE ABKÜRZUNG. AUCH DIE SCHLECHTEN.", "LOCH 19 IST UNSER ZWEITES ZUHAUSE.",
    "DIE FAHRT ENDET, WENN DER FAHRER ES SAGT.", "ÜBERLICHT NUR GEGEN AUFPREIS UND GUTE LAUNE.",
]
RADIO = [
    "FUNK: FAHRGAST AN LOCH 4 WARTET SEIT DREI LICHTJAHREN.",
    "FUNK: ZENTRALE SUCHT TAXI MIT FUNKTIONIERENDER KLIMAANLAGE. NIEMAND MELDET SICH.",
    "FUNK: STAU AUF DER HYPERSPUR NORD. FAHRER EMPFIEHLT DEN BUNKER.",
    "FUNK: TAXI 1337, DEIN FAHRGAST HAT DIE RECHNUNG NICHT BEZAHLT. WIEDER.",
    "FUNK: WETTER IM SEKTOR: EGAL, WIR HABEN EIN DACH.",
    "FUNK: NEUE VORSCHRIFT: BLINKEN AUCH IM WELTRAUM.",
    "FUNK: DER CLUBHAUS-PARKPLATZ IST VOLL. LANDE AUF DEM GRÜN.",
    "FUNK: BORDCOMPUTER MELDET: FAHRER WIRKT MÜDE. FAHRER WIDERSPRICHT.",
]
PASSENGERS = ["FAHRGAST MIT FELL", "ZWEI DROIDEN, EINER KAPUTT", "EIN SCHMUGGLER, SEHR EILIG", "VIER GOLFER, EIN BALL",
              "EINE PRINZESSIN, INKOGNITO", "NIEMAND, ABER DER TAXAMETER LIEF", "EIN ALIEN MIT KOFFER"]


def _license(rng: random.Random) -> str:
    return f"{rng.choice('ABCDEFGHKLMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHKLMNPRSTUVWXYZ')}-{rng.randint(100, 999)}-{rng.randint(10, 99)}"


def _load_rgba(path) -> np.ndarray | None:
    """Bild als RGBA (Zeile 0 unten, für GL). None wenn nicht ladbar."""
    try:
        surf = pygame.image.load(str(path))
        w, h = surf.get_size()
        rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
        try:
            alpha = pygame.surfarray.array_alpha(surf).T
        except ValueError:
            alpha = np.full((h, w), 255, dtype=np.uint8)
        return np.ascontiguousarray(np.dstack((rgb, alpha)).astype(np.uint8)[::-1])
    except Exception as exc:
        log.warning("Bild %s nicht ladbar: %s", path, exc)
        return None


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.settings = lcfg.load_settings()
        self.name = str(self.settings.get("launcher", {}).get("pilot_name", "PILOT")).upper()
        self.themes = ltheme.themes() or [ltheme.current()]
        cur = ltheme.current().get("name")
        self.idx = next((i for i, t in enumerate(self.themes) if t.get("name") == cur), 0)
        self.chosen = self.idx
        self.slide = 0.0
        self.slide_t0 = 0.0
        self.confirm_t0 = -10.0
        self.accessory = self.rng.choice([0, 1, 2, 3, 0, 1, 2])
        self.taxi_no = self.rng.choice([1337, 42, 7, 1138, 404, 2187, 9000])
        self.license = _license(self.rng)
        self.slogan = self.rng.choice(SLOGANS)
        self.rides = self.rng.randint(0, 23)
        self.complaints = self.rides + self.rng.randint(1, 9)
        self.last_passenger = self.rng.choice(PASSENGERS)
        self.meter = self.rng.uniform(80.0, 900.0)
        self.radio = self.rng.choice(RADIO)
        self.radio_at = time.monotonic() + self.rng.uniform(10.0, 20.0)
        self.t_last = time.monotonic()
        self.blank = np.zeros((4, 4, 4), dtype=np.uint8)
        self.photo = _load_rgba(PHOTO) if PHOTO.exists() else None
        if self.photo is None:
            log.warning("Kein Pilotenfoto unter %s", PHOTO)
        # Digitale Lizenz: neues Fahrerfoto (assets/taxi/driver.png); fehlt es, bleibt das Duotone-Porträt
        self.driver = _load_rgba(DRIVER) if DRIVER.exists() else None
        self.eyes = [tuple(float(v) for v in e) for e in scene_cfg.get("eyes", [[0.425, 0.655], [0.573, 0.655]])]
        self.eye_r = float(scene_cfg.get("eye_r", 0.03))
        self.beat_zoom = 0.0
        self.bass_s = 0.0
        self.energy = 0.0
        self.glitch = 0.0
        self.spin_t = 0.0
        self.last_beat = 0.0
        self.covers: dict[int, np.ndarray] = {}
        for i, t in enumerate(self.themes):
            p = lcfg.ROOT / str(t.get("cover", "")) if t.get("cover") else None
            if p and p.exists():
                img = _load_rgba(p)
                if img is not None:
                    self.covers[i] = img
        self.cover_version = 0
        self.demo = demo
        self.demo_next = time.monotonic() + 4.0
        log.info("Taxistand: Thema %s, %d Themen, %d eigene Plakate, Accessoire %d",
                 self.themes[self.idx].get("name"), len(self.themes), len(self.covers), self.accessory)

    # -- Eingabe -------------------------------------------------------------
    def handle_event(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.select(+1)
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self.select(-1)
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.confirm()

    def select(self, d: int) -> None:
        self.idx = (self.idx + d) % len(self.themes)
        self.slide = float(d)
        self.slide_t0 = time.monotonic()
        self.cover_version += 1

    def confirm(self) -> None:
        self.chosen = self.idx
        ltheme.set_current(self.themes[self.idx].get("name", ""))
        self.confirm_t0 = time.monotonic()
        log.info("Thema gewählt: %s", self.themes[self.idx].get("name"))
        wled.apply_mode_async("home", [int(c * 255) for c in self.themes[self.idx].get("color_a", [0.95, 0.8, 0.25])])

    # -- Schnittstelle zur Engine --------------------------------------------
    def images(self) -> dict:
        cover = self.covers.get(self.idx, self.blank)
        return {"uPhotoTex": (self.photo if self.photo is not None else self.blank, 1),
                "uCoverTex": (cover, self.cover_version),
                "uDriverTex": (self.driver if self.driver is not None else self.blank, 1)}

    def uniform_names(self):
        return ("uPhotoTex", "uCoverTex", "uDriverTex", "uPhotoOK", "uCoverOK", "uCoverStyle", "uAccessory", "uColA", "uColB",
                "uTint", "uSlide", "uConfirm", "uChosen", "uSeed",
                "uDriverOK", "uDriverSize", "uBeatZoom", "uBassS", "uEnergy", "uGlitch", "uSpinT", "uEyes", "uEyeR")

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.t_last)
        self.t_last = now
        self.meter += dt * (0.35 + 3.0 * getattr(f, "bass", 0.0))
        # Digitale Lizenz: Beat zoomt ins Gesicht (klingt über ~1.5 s ab), Bass und Energie geglättet,
        # kräftige Beats lösen manchmal einen kurzen Glitch aus, die Spiralen drehen mit der Musik schneller
        silent = bool(getattr(f, "silent", True))
        live = 0.0 if silent else 1.0
        beat = float(getattr(f, "beat", 0.0)) * live
        self.bass_s += (float(getattr(f, "bass", 0.0)) * live - self.bass_s) * min(1.0, dt / 0.2)
        self.energy += (float(getattr(f, "rms", 0.0)) * live - self.energy) * min(1.0, dt / 2.0)
        if beat > 0.5 and now - self.last_beat > 0.25:
            self.last_beat = now
            self.beat_zoom = min(1.0, self.beat_zoom + 0.35 + 0.4 * beat)
            if beat > 0.8 and self.rng.random() < 0.5:
                self.glitch = 1.0
        self.beat_zoom = max(0.0, self.beat_zoom - dt / 1.5)
        self.glitch = max(0.0, self.glitch - dt / 0.25)
        self.spin_t += dt * (0.6 + 2.5 * self.bass_s + 2.0 * self.beat_zoom)
        if now >= self.radio_at:
            self.radio = self.rng.choice([r for r in RADIO if r != self.radio])
            self.radio_at = now + self.rng.uniform(12.0, 25.0)
        if self.demo and now >= self.demo_next:
            self.select(+1) if self.rng.random() < 0.7 else self.confirm()
            self.demo_next = now + 3.0
        th = self.themes[self.idx]
        slide = self.slide * max(0.0, 1.0 - (now - self.slide_t0) / 0.5)
        return {
            "uPhotoOK": 1.0 if self.photo is not None else 0.0,
            "uDriverOK": 1.0 if self.driver is not None else 0.0,
            "uDriverSize": (float(self.driver.shape[1]), float(self.driver.shape[0])) if self.driver is not None else (1.0, 1.0),
            "uBeatZoom": self.beat_zoom, "uBassS": self.bass_s, "uEnergy": self.energy, "uGlitch": self.glitch,
            "uSpinT": self.spin_t % 1000.0,
            "uEyes": (self.eyes[0][0], self.eyes[0][1], self.eyes[1][0], self.eyes[1][1]), "uEyeR": self.eye_r,
            "uCoverOK": 1.0 if self.idx in self.covers else 0.0,
            "uCoverStyle": float(th.get("cover_style", 0)),
            "uAccessory": float(self.accessory),
            "uColA": tuple(th.get("color_a", [0.95, 0.8, 0.25])),
            "uColB": tuple(th.get("color_b", [0.15, 0.45, 0.85])),
            "uTint": tuple(th.get("tint", [0.95, 0.75, 0.25])),
            "uSlide": slide,
            "uConfirm": max(0.0, 1.0 - (now - self.confirm_t0) / 1.2),
            "uChosen": 1.0 if self.idx == self.chosen else 0.0,
            "uSeed": float(self.idx) * 7.0 + 3.0,
        }

    def overlays(self, t: float):
        now = time.monotonic()
        th = self.themes[self.idx]
        n = len(self.themes)
        col_a = tuple(int(c * 255) for c in th.get("color_a", [0.95, 0.8, 0.25]))
        chosen = self.idx == self.chosen
        out = [
            # Plakat links: Titel und Zeile unter dem Bild
            (th.get("title", "").upper(), 0.05, 0.30, 0.16, col_a, 1.0),
            (th.get("tagline", "").upper(), 0.02, 0.30, 0.115, WHITE, 0.85),
            (f"THEMA  {self.idx + 1} / {n}" + ("     AKTIV" if chosen else "     START = WÄHLEN"), 0.019, 0.30, 0.082,
             col_a if chosen else GREY, 0.9 if chosen else 0.6 + 0.3 * abs(((now * 1.5) % 2.0) - 1.0)),
            # Fahrerplakat rechts
            ("SPACE TAXI DRIVER", 0.034, 0.775, 0.24, col_a, 1.0),
            (self.name, 0.044, 0.775, 0.188, WHITE, 1.0),
            (f"TAXI NR. {self.taxi_no}   LIZENZ {self.license}", 0.018, 0.775, 0.143, WHITE, 0.8),
            (f"FAHRTEN {self.rides}   BESCHWERDEN {self.complaints}   TAXAMETER {self.meter:07.2f} CR", 0.017, 0.775, 0.112, DIM, 0.85),
            (f"LETZTER FAHRGAST: {self.last_passenger}", 0.016, 0.775, 0.083, DIM, 0.75),
            # Fußzeile
            (self.slogan, 0.02, 0.30, 0.018, col_a, 0.9),
            ("<  THEMA  >      START  WÄHLEN", 0.016, 0.775, 0.018, GREY, 0.5 + 0.2 * abs(((now * 1.5) % 2.0) - 1.0)),
        ]
        if self.photo is None and self.driver is None:
            out.append(("KEIN FOTO: assets/taxi/driver.png", 0.02, 0.775, 0.55, (255, 90, 70), 0.9))
        if self.driver is not None:
            out.append(("● LIVE", 0.016, 0.905, 0.978, (255, 60, 50), 0.5 + 0.5 * abs(((now * 2.0) % 2.0) - 1.0)))
            out.append(("DIGITALE LIZENZ  ·  SPACE TAXI DRIVER", 0.014, 0.72, 0.978, (200, 200, 210), 0.7))
        if now - self.confirm_t0 < 1.5:
            out.append((f"THEMA {th.get('title', '').upper()} AKTIV", 0.04, 0.5, 0.5, WHITE, 1.0 - (now - self.confirm_t0) / 1.5))
        return out
