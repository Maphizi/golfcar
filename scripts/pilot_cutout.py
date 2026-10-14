"""Porträt für den Startbildschirm freistellen: Flutfüllung des Hintergrunds vom Rand her, weiche
Kante, unten als Hologramm-Büste ausblenden. Braucht ein frontales Foto vor ruhigem Hintergrund.
Aufruf: .venv/bin/python scripts/pilot_cutout.py FOTO assets/pilot.png VORSCHAU.png"""
import sys, numpy as np, pygame
from collections import deque
pygame.display.init(); pygame.display.set_mode((8, 8))
src = pygame.image.load(sys.argv[1]).convert_alpha()
w, h = src.get_size()
rgb = pygame.surfarray.array3d(src).transpose(1, 0, 2).astype(np.float32)
border = np.concatenate([rgb[0:20].reshape(-1, 3), rgb[:, 0:20].reshape(-1, 3), rgb[:, -20:].reshape(-1, 3)])
bg = np.median(border, axis=0)
dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
S = 256
H2, W2 = (h // S) * S, (w // S) * S
small = dist[:H2, :W2].reshape(S, H2 // S, S, W2 // S).mean(axis=(1, 3))
bgmask = np.zeros((S, S), dtype=bool)
q = deque([(i, j) for i in range(S) for j in (0, S - 1)] + [(j, i) for i in range(S) for j in (0,)])
thr = 34.0
while q:
    y, x = q.popleft()
    if bgmask[y, x] or small[y, x] > thr: continue
    bgmask[y, x] = True
    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < S and 0 <= nx < S and not bgmask[ny, nx]: q.append((ny, nx))
fg = (~bgmask).astype(np.float32)
for _ in range(2):
    p = np.pad(fg, 1, mode="edge")
    fg = (p[:-2,1:-1]+p[2:,1:-1]+p[1:-1,:-2]+p[1:-1,2:]+p[1:-1,1:-1]*4)/8.0
alpha = np.kron(fg, np.ones((H2 // S, W2 // S), dtype=np.float32))
alpha = np.pad(alpha, ((0, h - H2), (0, w - W2)), mode="edge")
edge = (alpha > 0.05) & (alpha < 0.95)
pix = np.clip((dist - 18.0) / 20.0, 0.0, 1.0)
alpha = np.where(edge, np.clip(alpha * 0.5 + pix * 0.5 + (pix > 0.5) * 0.3, 0, 1), alpha)
# Büste: unterhalb des Kinns weich ausblenden (das Shirt ist dem Hintergrund zu ähnlich)
yy = np.linspace(0, 1, h)[:, None]
alpha *= np.clip((0.90 - yy) / 0.20, 0.0, 1.0)
# Schulterbereich seitlich beschneiden (Streifen am Rand)
xx = np.linspace(0, 1, w)[None, :]
side = np.clip((0.36 - np.abs(xx - 0.5)) / 0.08, 0.0, 1.0)
alpha = np.where(yy > 0.68, alpha * side, alpha)
alpha8 = (alpha * 255).astype(np.uint8)
out = pygame.Surface((w, h), pygame.SRCALPHA)
arr = pygame.surfarray.pixels3d(out); arr[:] = rgb.transpose(1, 0, 2).astype(np.uint8); del arr
aa = pygame.surfarray.pixels_alpha(out); aa[:] = alpha8.T; del aa
out = pygame.transform.smoothscale(out, (512, 512))
pygame.image.save(out, sys.argv[2])
prev = pygame.Surface((512, 512)); prev.fill((10, 20, 40)); prev.blit(out, (0, 0))
pygame.image.save(prev, sys.argv[3])
print("ok")
