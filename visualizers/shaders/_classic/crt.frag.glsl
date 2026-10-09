#version 140
// F3 – Retro CRT / Oscilloscope: Messinstrument aus einem 80er-Science-Fiction-Fahrzeug.
// Oszilloskop-Waveform, Spektrum-Balken, VU-Meter, Zahlen, Scanlines, Verzerrung, Glow, Flimmern.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;

const vec3 PHOS = vec3(0.35, 1.0, 0.55);     // Phosphor grün
const vec3 AMBER = vec3(1.0, 0.65, 0.2);
float wave(float x) { return texture(uAudioTex, vec2(x, 0.75)).r * 2.0 - 1.0; }
float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

// 3x5-Ziffern, Zeilen von oben, Bit 14 = oben links
float digit(int d, vec2 p) {   // p: 0..1 in der Zelle
    int font[10] = int[10](31599, 11415, 29671, 29647, 23497, 31183, 31215, 29257, 31727, 31695);
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    int col = int(p.x * 3.0);
    int row = 4 - int(p.y * 5.0);
    int bit = 14 - (row * 3 + col);
    return float((font[d] >> bit) & 1);
}
// zweistellige Zahl (0..99) an Position pos, Zellgröße sz
float number(int n, vec2 uv, vec2 pos, vec2 sz) {
    vec2 p = (uv - pos) / sz;
    float d1 = digit((n / 10) % 10, p);
    float d2 = digit(n % 10, p - vec2(1.3, 0.0));
    return max(d1, d2);
}
float rect(vec2 uv, vec2 a, vec2 b) {
    vec2 s = step(a, uv) * step(uv, b);
    return s.x * s.y;
}

void main() {
    // CRT-Wölbung
    vec2 c = vUv * 2.0 - 1.0;
    float rr = dot(c, c);
    c *= 1.0 + 0.08 * rr;
    vec2 uv = c * 0.5 + 0.5;
    float inside = rect(uv, vec2(0.0), vec2(1.0));
    float aspect = iResolution.x / iResolution.y;
    float px = 1.0 / iResolution.y;

    vec3 col = vec3(0.0);
    float live = 1.0 - uSilent;

    // Rasterlinien
    vec2 grid = abs(fract(uv * vec2(20.0 * aspect / 1.78, 20.0)) - 0.5);
    float gl = smoothstep(0.47, 0.5, max(grid.x, grid.y));
    col += PHOS * gl * 0.05;

    // ---- Oszilloskop (y 0.40..0.78)
    float scopeY = 0.59, scopeH = 0.14 * (0.6 + 0.6 * uBass);
    float sweep = fract(iTime * 0.35);
    {
        float x = uv.x;
        float dx = 1.5 * px / aspect;
        float y0 = scopeY + wave(x) * scopeH;
        float y1 = scopeY + wave(x + dx) * scopeH;
        float slope = (y1 - y0) / dx;
        float d = abs(uv.y - y0) / sqrt(1.0 + slope * slope);
        float beam = exp(-d * 420.0) + 0.35 * exp(-d * 90.0);
        // Strahl zieht von links nach rechts nach (Nachleuchten)
        float trail = 0.55 + 0.45 * smoothstep(0.0, 0.08, fract(sweep - x + 1.0));
        col += PHOS * beam * (0.8 + 0.5 * uRms) * trail;
        // Nulllinie + Skala
        col += PHOS * 0.12 * smoothstep(1.5 * px, 0.0, abs(uv.y - scopeY));
        float tick = step(0.985, fract(uv.x * 20.0)) * step(abs(uv.y - scopeY), 0.012);
        col += PHOS * 0.3 * tick;
    }

    // ---- Spektrum-Balken (y 0.08..0.34), 32 Balken
    {
        float nb = 32.0;
        float bx = uv.x * nb;
        float i = floor(bx);
        float inBar = step(0.12, fract(bx)) * step(fract(bx), 0.88);
        float h = spec((i + 0.5) / nb);
        float barTop = 0.08 + h * 0.26;
        float seg = step(0.25, fract((uv.y - 0.08) / 0.013));   // Segmente
        float on = rect(uv, vec2(0.0, 0.08), vec2(1.0, barTop)) * inBar * seg;
        vec3 bc = mix(PHOS, AMBER, smoothstep(0.55, 0.9, (uv.y - 0.08) / 0.26));
        bc = mix(bc, vec3(1.0, 0.2, 0.15), smoothstep(0.88, 1.0, (uv.y - 0.08) / 0.26));
        col += bc * on * (0.7 + 0.3 * live);
        // Peak-Marke
        col += bc * inBar * smoothstep(2.0 * px, 0.0, abs(uv.y - barTop)) * 0.8 * live;
        col += PHOS * 0.08 * rect(uv, vec2(0.0, 0.08), vec2(1.0, 0.34)) * inBar * seg;  // leere Segmente schwach
    }

    // ---- VU-Meter oben (y 0.84..0.90): links RMS, rechts Höhen
    {
        float nseg = 24.0;
        for (int k = 0; k < 2; k++) {
            float x0 = (k == 0) ? 0.06 : 0.56;
            float lvl = (k == 0) ? uRms : uHigh;
            vec2 p = (uv - vec2(x0, 0.84)) / vec2(0.38, 0.05);
            if (p.x >= 0.0 && p.x < 1.0 && p.y >= 0.0 && p.y < 1.0) {
                float s = floor(p.x * nseg);
                float gap = step(0.15, fract(p.x * nseg)) * step(0.2, p.y) * step(p.y, 0.8);
                float lit = step(s / nseg, lvl);
                vec3 vc = mix(PHOS, AMBER, step(0.65, s / nseg));
                vc = mix(vc, vec3(1.0, 0.2, 0.15), step(0.85, s / nseg));
                col += vc * gap * (lit * 0.9 + 0.08);
            }
        }
    }

    // ---- Zahlen: BASS MID HIGH in Prozent, unten rechts über den Balken; Zeitzähler links oben
    {
        vec2 sz = vec2(0.012, 0.03);
        col += AMBER * number(int(uBass * 99.0), uv, vec2(0.06, 0.93), sz);
        col += AMBER * number(int(uMid * 99.0), uv, vec2(0.12, 0.93), sz);
        col += AMBER * number(int(uHigh * 99.0), uv, vec2(0.18, 0.93), sz);
        col += PHOS * 0.8 * number(int(mod(iTime, 100.0)), uv, vec2(0.90, 0.93), sz);
        col += PHOS * 0.8 * number(int(mod(iTime * 10.0, 100.0)), uv, vec2(0.94, 0.93), sz * vec2(0.8, 0.8));
        // Statusleuchte: rot bei Stille, grün bei Signal
        float led = smoothstep(0.012, 0.008, length((uv - vec2(0.5, 0.945)) * vec2(aspect, 1.0)));
        col += mix(vec3(1.0, 0.15, 0.1) * (0.6 + 0.4 * sin(iTime * 3.0)), PHOS, live) * led;
    }

    // Beat: kurzer Helligkeitsstoß
    col *= 1.0 + 0.35 * uBeat;

    // ---- CRT-Nachbearbeitung
    float scan = 0.82 + 0.18 * sin(vUv.y * iResolution.y * 3.14159);
    col *= scan;
    float flicker = 0.96 + 0.04 * sin(iTime * 73.0) + 0.02 * hash(vec2(iTime, 1.0));
    col *= flicker;
    float roll = smoothstep(0.0, 0.08, abs(fract(vUv.y - iTime * 0.07) - 0.5)) * 0.1 + 0.9;  // wandernder Balken
    col *= roll;
    col += PHOS * 0.03 * hash(vUv * iResolution.xy + iTime);   // Rauschen
    col *= inside;
    col *= 1.0 - 0.5 * smoothstep(0.6, 1.4, rr);               // Vignette
    fragColor = vec4(col, 1.0);
}
