"""Planeten-Visualizer: Sternenhimmel mit Warp-Flug-Modus.

Steuerung:
  SPACE      (Kippschalter AN)  -> Warp-Flug starten
  BACKSPACE  (Kippschalter AUS) -> Warp-Flug stoppen, zurück zu Drift
  ENTER      (Startknopf)       -> gleiche Funktion wie SPACE (toggle)
  ESC        -> Beenden
"""
from __future__ import annotations
import math, random, sys, time
import pygame

BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
YELLOW = (255, 220,  80)
CYAN   = (100, 220, 255)
RED    = (255,  80,  60)

NUM_STARS   = 300
NUM_PLANETS = 5
WARP_SPEED  = 18.0   # Pixel/Frame im Warp
DRIFT_SPEED = 0.4


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


class Planet:
    COLORS = [RED, (120, 80, 200), (60, 180, 100), CYAN, YELLOW]

    def __init__(self, w, h, idx):
        self.w, self.h = w, h
        self.color = self.COLORS[idx % len(self.COLORS)]
        self.reset()

    def reset(self):
        self.x = random.uniform(0.1 * self.w, 0.9 * self.w)
        self.y = random.uniform(0.1 * self.h, 0.9 * self.h)
        self.r = random.randint(18, 55)
        self.vy = random.uniform(0.2, 0.6)

    def update(self, flying: bool):
        speed = WARP_SPEED * 0.3 if flying else self.vy
        self.y += speed
        if self.y - self.r > self.h:
            self.reset()
            self.y = -self.r

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.r)
        # Glanzpunkt
        pygame.draw.circle(surf, WHITE,
                            (int(self.x) - self.r // 3, int(self.y) - self.r // 3),
                            max(3, self.r // 5))


def main() -> int:
    pygame.init()
    info = pygame.display.Info()
    screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
    pygame.display.set_caption("PLANETEN")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    w, h = screen.get_size()
    stars   = [Star(w, h) for _ in range(NUM_STARS)]
    planets = [Planet(w, h, i) for i in range(NUM_PLANETS)]

    flying = False
    font = pygame.font.SysFont(None, 36)

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return 0
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE,):
                    return 0
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
        for p in planets:
            p.draw(screen)

        # Status-Label
        label = "⚡ WARP" if flying else "· DRIFT"
        txt = font.render(label, True, YELLOW if flying else (80, 80, 80))
        screen.blit(txt, (20, 20))

        pygame.display.flip()
        clock.tick(60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
