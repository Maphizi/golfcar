"""Planeten-Visualizer: Sternenhimmel mit Warp-Flug und Planeten-Auswahl.

Steuerung:
  LEFT / RIGHT   (Hebel)         -> Ziel-Planeten durchschalten
  SPACE          (Kippschalter AN)  -> Warp-Flug zum Zielplaneten starten
  BACKSPACE      (Kippschalter AUS) -> Warp stoppen, zurück zu Drift
  ENTER          (Startknopf)    -> gleiche Funktion wie SPACE (toggle)
  ESC            -> Beenden
"""
from __future__ import annotations
import math, random, sys, time
import pygame

BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
YELLOW = (255, 220,  80)
CYAN   = (100, 220, 255)
RED    = (255,  80,  60)
GREY   = (80,  80,  80)
GREEN  = (80,  220, 100)

NUM_STARS   = 300
WARP_SPEED  = 18.0
DRIFT_SPEED = 0.4

PLANET_DEFS = [
    {"name": "MARS",       "color": RED,              "r": 38, "ring": False},
    {"name": "NEPTUN",     "color": (60,  100, 220),  "r": 45, "ring": False},
    {"name": "KEPLER-22b", "color": (60,  180, 100),  "r": 50, "ring": False},
    {"name": "SATURN",     "color": YELLOW,           "r": 55, "ring": True},
    {"name": "PROXIMA b",  "color": CYAN,             "r": 35, "ring": False},
    {"name": "GLIESE 667C","color": (180, 80,  200),  "r": 42, "ring": False},
]


class Star:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.reset(random.random())

    def reset(self, progress=0.0):
        self.x = random.uniform(0, self.w)
        self.y = random.uniform(0, self.h)
        self.z = random.uniform(progress, 1.0)
        self.size = random.uniform(0.5, 2.0)

    def update(self, speed):
        self.z -= speed * 0.01
        if self.z <= 0:
            self.reset()

    def draw(self, surf):
        scale = 1 - self.z
        x = int(self.w / 2 + (self.x - self.w / 2) * scale / max(self.z, 0.01))
        y = int(self.h / 2 + (self.y - self.h / 2) * scale / max(self.z, 0.01))
        size = max(1, int(self.size * (1 - self.z) * 3))
        bright = int(255 * (1 - self.z))
        if 0 <= x < self.w and 0 <= y < self.h:
            pygame.draw.circle(surf, (bright, bright, bright), (x, y), size)


class PlanetObj:
    def __init__(self, w, h, defn):
        self.w, self.h = w, h
        self.defn = defn
        self.x = w // 2
        self.y = -defn["r"]
        self.vy = random.uniform(0.3, 0.7)

    def reset(self):
        self.x = random.randint(int(self.w * 0.15), int(self.w * 0.85))
        self.y = -self.defn["r"]
        self.vy = random.uniform(0.3, 0.7)

    def update(self, flying: bool):
        speed = WARP_SPEED * 0.35 if flying else self.vy
        self.y += speed
        if self.y - self.defn["r"] > self.h:
            self.reset()

    def draw(self, surf, highlight: bool):
        r = self.defn["r"]
        col = self.defn["color"]
        cx, cy = int(self.x), int(self.y)
        pygame.draw.circle(surf, col, (cx, cy), r)
        # Glanzpunkt
        pygame.draw.circle(surf, WHITE,
                            (cx - r // 3, cy - r // 3),
                            max(3, r // 5))
        # Ring (Saturn)
        if self.defn.get("ring"):
            rx = int(r * 1.7)
            ry = int(r * 0.35)
            ring_surf = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
            pygame.draw.ellipse(ring_surf, (*YELLOW, 140), (0, 0, rx * 2, ry * 2), 5)
            surf.blit(ring_surf, (cx - rx, cy - ry))
        # Auswahl-Rahmen
        if highlight:
            pygame.draw.circle(surf, GREEN, (cx, cy), r + 6, 3)


def main() -> int:
    pygame.init()
    info = pygame.display.Info()
    screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
    pygame.display.set_caption("PLANETEN")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    w, h = screen.get_size()
    stars   = [Star(w, h) for _ in range(NUM_STARS)]
    planets = [PlanetObj(w, h, d) for d in PLANET_DEFS]
    # Planeten auf dem Bildschirm verteilen
    for i, p in enumerate(planets):
        p.x = int(w * (i + 1) / (len(planets) + 1))
        p.y = random.randint(int(h * 0.15), int(h * 0.6))

    selected = 0          # aktuell ausgewählter Planet (Hebel)
    flying   = False

    font_big  = pygame.font.SysFont(None, 52)
    font_small = pygame.font.SysFont(None, 32)

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return 0
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return 0
                # Hebel → Planeten-Auswahl
                if ev.key == pygame.K_LEFT:
                    selected = (selected - 1) % len(planets)
                if ev.key == pygame.K_RIGHT:
                    selected = (selected + 1) % len(planets)
                # Kippschalter / Startknopf → Warp-Toggle
                if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    flying = True
                if ev.key == pygame.K_BACKSPACE:
                    flying = False

        speed = WARP_SPEED if flying else DRIFT_SPEED
        for s in stars:
            s.update(speed)
        for p in planets:
            p.update(flying)

        screen.fill(BLACK)
        for s in stars:
            s.draw(screen)
        for i, p in enumerate(planets):
            p.draw(screen, highlight=(i == selected))

        # Planetenname
        sel = planets[selected]
        name_txt = font_big.render(PLANET_DEFS[selected]["name"], True, GREEN)
        screen.blit(name_txt, (w // 2 - name_txt.get_width() // 2, h - 90))

        # Status
        label = "⚡ WARP → " + PLANET_DEFS[selected]["name"] if flying else "[ HEBEL: Planet wählen ]"
        status_txt = font_small.render(label, True, YELLOW if flying else GREY)
        screen.blit(status_txt, (w // 2 - status_txt.get_width() // 2, h - 46))

        pygame.display.flip()
        clock.tick(60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
