#version 140
// F7 – Lagerfeuer: Pixel-Art-Feuer mit Scheiten, Funken, Lichtschein und Sternenhimmel.
// Zündet in den ersten Sekunden an (iTime startet beim Modusstart bei 0). Reagiert leicht auf Audio.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;

const float CELLS_Y = 90.0;      // Pixelraster: 90 Zeilen, Breite nach Seitenverhältnis
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 11.0; a *= 0.5; }
    return v;
}
// Feuerfarben, auf 6 Stufen quantisiert (Pixel-Look)
vec3 firePal(int k) {           // k = 1..5, Stufen von dunkelrot bis weißgelb
    if (k <= 1) return vec3(0.55, 0.06, 0.0);
    if (k == 2) return vec3(0.90, 0.20, 0.0);
    if (k == 3) return vec3(1.0, 0.48, 0.03);
    if (k == 4) return vec3(1.0, 0.80, 0.18);
    return vec3(1.0, 0.97, 0.72);
}
// Abstand Punkt–Strecke (für die Scheite)
float segDist(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float cellsX = floor(CELLS_Y * aspect);
    // Pixelraster
    vec2 cell = floor(vUv * vec2(cellsX, CELLS_Y));
    vec2 uv = (cell + 0.5) / vec2(cellsX, CELLS_Y);
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y);       // p.x zentriert, p.y 0..1

    // Anzünden: Flammenhöhe wächst in den ersten 5 s, Funke bei 0.5 s
    float ignite = smoothstep(0.8, 5.0, iTime);
    float flameH = mix(0.05, 1.0, ignite) * (1.0 + 0.12 * uRms * (1.0 - uSilent));
    float t = iTime;

    // ---- Himmel und Boden
    vec3 col = mix(vec3(0.01, 0.01, 0.03), vec3(0.03, 0.03, 0.07), uv.y);
    float star = step(0.995, hash(cell)) * (0.5 + 0.5 * sin(t * 2.0 + hash(cell + 7.0) * 6.28)) * step(0.45, uv.y);
    col += vec3(0.8, 0.85, 1.0) * star * 0.7;
    float groundY = 0.22;
    float ground = step(uv.y, groundY);
    col = mix(col, vec3(0.05, 0.035, 0.02) * (0.6 + 0.4 * hash(cell * 0.37)), ground);

    // ---- Lichtschein des Feuers (flackert)
    float flick = 0.85 + 0.15 * noise(vec2(t * 7.0, 3.0)) + 0.1 * uBeat;
    float d = length((p - vec2(0.0, groundY + 0.05)) * vec2(1.0, 1.4));
    col += vec3(1.0, 0.5, 0.15) * exp(-d * 4.5) * 0.35 * flick * ignite;
    col += vec3(1.0, 0.35, 0.1) * exp(-d * 1.8) * 0.08 * flick * ignite;

    // ---- Scheite (zwei gekreuzte Stämme, Streifen in Holzmaserung)
    float logs = 0.0;
    float dl1 = segDist(p, vec2(-0.22, groundY - 0.01), vec2(0.20, groundY + 0.07));
    float dl2 = segDist(p, vec2(0.22, groundY - 0.01), vec2(-0.20, groundY + 0.07));
    float dl = min(dl1, dl2);
    if (dl < 0.035) {
        float stripe = step(0.5, fract((p.x + p.y * 0.3) * 30.0 + hash(vec2(floor(dl * 60.0), 1.0)) * 0.5));
        vec3 wood = mix(vec3(0.30, 0.16, 0.07), vec3(0.18, 0.09, 0.04), stripe);
        // Glut an den Innenseiten
        float glow = smoothstep(0.08, 0.0, abs(p.x)) * ignite * (0.6 + 0.4 * noise(vec2(t * 3.0, p.x * 20.0)));
        wood = mix(wood, vec3(1.0, 0.35, 0.05), glow * 0.7);
        col = wood;
        logs = 1.0;
    }

    // ---- Flammen: Rauschen, das nach oben zieht, mit Form (unten breit, oben spitz)
    float fy = (uv.y - groundY) / (0.55 * flameH);     // 0 am Boden, 1 an der Spitze
    if (fy > -0.05 && fy < 1.3 && logs < 0.5) {
        // Flammenzungen: Rauschen zieht nach oben, die Kontur wackelt mit
        float n = fbm(vec2(p.x * 5.0 + sin(t * 0.7) * 0.3, uv.y * 6.0 - t * 2.4));
        float n2 = noise(vec2(p.x * 12.0 + 3.0, uv.y * 16.0 - t * 4.5));
        float wobble = (n - 0.5) * 0.12 * (0.3 + fy);
        float width = 0.26 * flameH * (1.0 - fy * 0.8) + wobble;
        float shape = 1.0 - clamp(abs(p.x + (n2 - 0.5) * 0.06 * fy) / max(width, 0.001), 0.0, 1.0);
        float v = shape * (0.35 + 1.1 * n + 0.3 * n2) - fy * 0.75;
        v += 0.1 * uMid * (1.0 - uSilent);
        int k = int(clamp(v, 0.0, 0.999) * 6.0);
        if (k >= 1) {
            col = firePal(k);
        }
    }
    // Funke vor dem Anzünden
    if (iTime < 1.2 && abs(p.x) < 0.012 && abs(uv.y - groundY - 0.06) < 0.012 && fract(iTime * 8.0) > 0.5) {
        col = vec3(1.0, 0.9, 0.5);
    }

    // ---- Funken: 14 Partikel, steigen auf, driften, verlöschen
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        float speed = 0.12 + 0.1 * hash(vec2(fi, 2.0));
        float life = fract(t * speed + hash(vec2(fi, 3.0)));         // 0..1 Lebenszeit
        float sx = (hash(vec2(fi, 4.0)) - 0.5) * 0.25 + sin(t * 1.3 + fi) * 0.05 * life + life * (hash(vec2(fi, 5.0)) - 0.5) * 0.2;
        float sy = groundY + 0.08 + life * (0.5 + 0.3 * hash(vec2(fi, 6.0)));
        vec2 sc = floor(vec2(sx / aspect + 0.5, sy) * vec2(cellsX, CELLS_Y));
        float bright = (1.0 - life) * ignite * step(0.3, hash(vec2(fi, floor(t * 6.0))));
        bright *= 1.0 + 1.5 * uBeat;
        if (sc == cell && bright > 0.15) {
            col = mix(vec3(1.0, 0.5, 0.1), vec3(1.0, 0.9, 0.5), bright) ;
        }
    }

    // ---- leichte CRT-Scanlines und Vignette
    col *= 0.9 + 0.1 * sin(vUv.y * iResolution.y * 3.14159 * 0.5);
    col *= 1.0 - 0.35 * smoothstep(0.7, 1.6, length(vUv * 2.0 - 1.0));
    fragColor = vec4(col, 1.0);
}
