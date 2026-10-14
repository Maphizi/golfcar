"""Startbildschirm "Space-Taxi": der Pilot als Hologramm auf seiner Taxilizenz, Neon-TAXI-Schild,
Taxameter, Funksprüche, Sprüche und Statistik. Jeder Start würfelt neu: Hintergrund, Hologrammfarbe,
Accessoire (Sonnenbrille, Taximütze), Lizenznummer, Sprüche, Zahlen. Keine Modusliste.

Foto: assets/pilot.png (RGBA, freigestellt, siehe scripts/pilot_cutout.py). Fehlt es, bleibt die
Lizenz ohne Bild. Name aus config/settings.toml [launcher].pilot_name.
"""
from __future__ import annotations

import logging
import random
import time

import numpy as np

from launcher import config as lcfg

log = logging.getLogger("taxi")
PHOTO = lcfg.ROOT / "assets" / "pilot.png"

GOLD = (255, 214, 10)
NEON = (255, 240, 120)
DIM = (150, 140, 90)
WHITE = (240, 240, 245)

SLOGANS = [
    "WIR FAHREN ÜBERALL HIN. AUSSER ZURÜCK.",
    "KEIN TRINKGELD, KEIN NACHBRENNER.",
    "SCHNELLER ALS DEIN CADDIE. MEISTENS.",
    "TARIF 3: HYPERRAUM, OHNE GEWÄHR.",
    "EINSTEIGEN, ANSCHNALLEN, NICHT FRAGEN.",
    "DER FAHRER HAT IMMER RECHT. DER TAXAMETER AUCH.",
    "WIR KENNEN JEDE ABKÜRZUNG. AUCH DIE SCHLECHTEN.",
    "LOCH 19 IST UNSER ZWEITES ZUHAUSE.",
    "DIE FAHRT ENDET, WENN DER FAHRER ES SAGT.",
    "ERSTE KLASSE GIBT ES NICHT. NUR VORNE UND HINTEN.",
    "BITTE NICHT MIT DEM FAHRER DISKUTIEREN. ER GEWINNT.",
    "ÜBERLICHT NUR GEGEN AUFPREIS UND GUTE LAUNE.",
]
RADIO = [
    "FUNK: FAHRGAST AN LOCH 4 WARTET SEIT DREI LICHTJAHREN.",
    "FUNK: ZENTRALE SUCHT TAXI MIT FUNKTIONIERENDER KLIMAANLAGE. NIEMAND MELDET SICH.",
    "FUNK: STAU AUF DER HYPERSPUR NORD. FAHRER EMPFIEHLT DEN BUNKER.",
    "FUNK: BITTE KEINE FAHRGÄSTE MIT FELL AUF DEM BEIFAHRERSITZ.",
    "FUNK: TAXI 1337, DEIN FAHRGAST HAT DIE RECHNUNG NICHT BEZAHLT. WIEDER.",
    "FUNK: WETTER IM SEKTOR: EGAL, WIR HABEN EIN DACH.",
    "FUNK: NEUE VORSCHRIFT: BLINKEN AUCH IM WELTRAUM.",
    "FUNK: DER CLUBHAUS-PARKPLATZ IST VOLL. LANDE AUF DEM GRÜN.",
    "FUNK: BORDCOMPUTER MELDET: FAHRER WIRKT MÜDE. FAHRER WIDERSPRICHT.",
    "FUNK: PREISERHÖHUNG AB SOFORT. BEGRÜNDUNG: WEIL.",
]
PASSENGERS = ["FAHRGAST MIT FELL", "ZWEI DROIDEN, EINER KAPUTT", "EIN SCHMUGGLER, SEHR EILIG", "VIER GOLFER, EIN BALL",
              "EINE PRINZESSIN, INKOGNITO", "NIEMAND, ABER DER TAXAMETER LIEF", "EIN ALIEN MIT KOFFER", "DER BORDCOMPUTER PERSÖNLICH"]
ACCESSORIES = ["", "SONNENBRILLE", "TAXIMÜTZE", "MÜTZE UND BRILLE"]


def _license(rng: random.Random) -> str:
    return f"{rng.choice('ABCDEFGHKLMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHKLMNPRSTUVWXYZ')}-{rng.randint(100, 999)}-{rng.randint(10, 99)}"


class Controller:
    def __init__(self, scene_cfg: dict, demo: bool = False):
        self.rng = random.Random()
        self.settings = lcfg.load_settings()
        self.name = str(self.settings.get("launcher", {}).get("pilot_name", "PILOT")).upper()
        self.bg = self.rng.randrange(3)
        self.accessory = self.rng.choice([0, 1, 2, 3, 0, 1, 2])
        self.holo = self.rng.randrange(3)             # 0 blau, 1 bernstein, 2 grün
        self.seed = self.rng.uniform(1.0, 500.0)
        self.taxi_no = self.rng.choice([1337, 42, 7, 1138, 404, 666, 2187, 9000])
        self.license = _license(self.rng)
        self.slogan = self.rng.choice(SLOGANS)
        self.rides = self.rng.randint(0, 23)
        self.complaints = self.rides + self.rng.randint(1, 9)
        self.rating = self.rng.choice(["1,5", "2,0", "2,5", "3,0", "4,9"])
        self.tip = self.rng.choice([0, 0, 0, 3, 12, 1])
        self.last_passenger = self.rng.choice(PASSENGERS)
        self.meter = self.rng.uniform(80.0, 900.0)
        self.radio = self.rng.choice(RADIO)
        self.radio_at = time.monotonic() + self.rng.uniform(10.0, 20.0)
        self.free = True
        self.free_at = time.monotonic() + self.rng.uniform(8.0, 25.0)
        self.t_last = time.monotonic()
        self.image = None
        self.photo_ok = 0.0
        self._load_photo()
        log.info("Taxistand: Hintergrund %d, Hologramm %d, Accessoire %s, Lizenz %s", self.bg, self.holo,
                 ACCESSORIES[self.accessory] or "keins", self.license)

    def _load_photo(self) -> None:
        if not PHOTO.exists():
            log.warning("Kein Pilotenfoto unter %s, Lizenz bleibt ohne Bild", PHOTO)
            self.image = np.zeros((4, 4, 4), dtype=np.uint8)
            return
        try:
            import pygame
            surf = pygame.image.load(str(PHOTO))
            w, h = surf.get_size()
            rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
            try:
                alpha = pygame.surfarray.array_alpha(surf).T
            except ValueError:
                alpha = np.full((h, w), 255, dtype=np.uint8)
            img = np.dstack((rgb, alpha)).astype(np.uint8)
            self.image = np.ascontiguousarray(img[::-1])        # Zeile 0 = unten (GL)
            self.photo_ok = 1.0
        except Exception as exc:
            log.warning("Pilotenfoto nicht ladbar: %s", exc)
            self.image = np.zeros((4, 4, 4), dtype=np.uint8)

    # -- Schnittstelle zur Engine --------------------------------------------
    def handle_event(self, ev) -> None:
        pass

    def images(self) -> dict:
        return {"uPhotoTex": (self.image, 1)}

    def uniform_names(self):
        return ("uPhotoTex", "uPhotoOK", "uBg", "uAccessory", "uHolo", "uSeed", "uFree")

    def uniforms(self, t: float, f) -> dict:
        now = time.monotonic()
        dt = min(0.1, now - self.t_last)
        self.t_last = now
        self.meter += dt * (0.35 + 3.0 * getattr(f, "bass", 0.0))
        if now >= self.radio_at:
            self.radio = self.rng.choice([r for r in RADIO if r != self.radio])
            self.radio_at = now + self.rng.uniform(12.0, 25.0)
        if now >= self.free_at:
            self.free = not self.free
            self.free_at = now + self.rng.uniform(6.0, 30.0)
        return {"uPhotoOK": self.photo_ok, "uBg": float(self.bg), "uAccessory": float(self.accessory),
                "uHolo": float(self.holo), "uSeed": self.seed, "uFree": 1.0 if self.free else 0.0}

    def overlays(self, t: float):
        now = time.monotonic()
        blink = 0.6 + 0.4 * (1.0 if int(now * 2) % 2 == 0 else 0.3)
        out = [
            (f"SPACE-TAXI  NR. {self.taxi_no}", 0.04, 0.5, 0.925, GOLD, 0.95),
            ("FREI" if self.free else "BESETZT", 0.03, 0.885, 0.925, (90, 255, 120) if self.free else (255, 90, 70), blink),
            # Lizenz links unter dem Hologramm
            ("TAXILIZENZ", 0.02, 0.245, 0.24, DIM, 0.85),
            (self.name, 0.046, 0.245, 0.19, NEON, 1.0),
            (f"NR. {self.license}   KLASSE: ALLES MIT ANTRIEB", 0.019, 0.245, 0.148, WHITE, 0.85),
            ("GÜLTIG BIS: STERNTOD   PUNKTE IN FLENSBURG-7: ALLE", 0.019, 0.245, 0.12, WHITE, 0.75),
            # Taxameter und Statistik rechts
            ("TAXAMETER", 0.02, 0.73, 0.70, DIM, 0.85),
            (f"{self.meter:09.2f} CR", 0.052, 0.73, 0.645, (255, 80, 60), 1.0),
            (f"FAHRTEN HEUTE {self.rides:2d}      BESCHWERDEN {self.complaints:2d}", 0.02, 0.73, 0.56, WHITE, 0.85),
            (f"BEWERTUNG {self.rating} / 5      TRINKGELD {self.tip} CR", 0.02, 0.73, 0.525, WHITE, 0.85),
            (f"LETZTER FAHRGAST: {self.last_passenger}", 0.019, 0.73, 0.49, DIM, 0.85),
            # Spruch und Funk
            (self.slogan, 0.03, 0.5, 0.06, NEON, 0.95),
            (self.radio, 0.018, 0.5, 0.022, (160, 200, 255), 0.5 + 0.4 * abs(((now * 0.7) % 2.0) - 1.0)),
        ]
        if self.photo_ok < 0.5:
            out.append(("KEIN FOTO: assets/pilot.png", 0.02, 0.245, 0.55, (255, 90, 70), 0.9))
        return out
