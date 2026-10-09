#version 140
// F5 – KITT: 80er-Fahrzeugcomputer. Scanner-Balken, Voice-Modulator (drei Säulen), Waveform, Readouts.
// Zustände (uState): 0 idle, 1 listening, 2 thinking, 3 speaking, 4 loading. uStateT = Sekunden im Zustand.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uState, uStateT, uLevel;   // uLevel: VAD-Wahrscheinlichkeit (listening)

const vec3 RED = vec3(1.0, 0.12, 0.06);
const vec3 AMBER = vec3(1.0, 0.62, 0.15);
const vec3 DIM = vec3(0.18, 0.02, 0.01);
float wave(float x) { return texture(uAudioTex, vec2(x, 0.75)).r * 2.0 - 1.0; }
float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }
int font[10] = int[10](31599, 11415, 29671, 29647, 23497, 31183, 31215, 29257, 31727, 31695);
float digit(int d, vec2 p) {
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    int bit = 14 - ((4 - int(p.y * 5.0)) * 3 + int(p.x * 3.0));
    return float((font[d] >> bit) & 1);
}
float number(int n, vec2 uv, vec2 pos, vec2 sz) {
    vec2 p = (uv - pos) / sz;
    return max(digit((n / 10) % 10, p), digit(n % 10, p - vec2(1.3, 0.0)));
}

void main() {
    vec2 c = vUv * 2.0 - 1.0;
    float rr = dot(c, c);
    c *= 1.0 + 0.05 * rr;                       // leichte CRT-Wölbung
    vec2 uv = c * 0.5 + 0.5;
    float inside = rect(uv, vec2(0.0), vec2(1.0));
    float aspect = iResolution.x / iResolution.y;
    float px = 1.0 / iResolution.y;
    int st = int(uState + 0.5);
    float listening = float(st == 1), thinking = float(st == 2), speaking = float(st == 3), loading = float(st == 4);
    float live = 1.0 - uSilent;
    vec3 col = vec3(0.0);

    // Hintergrund: feines Raster
    vec2 g = abs(fract(uv * vec2(32.0 * aspect / 1.78, 32.0)) - 0.5);
    col += RED * 0.035 * smoothstep(0.47, 0.5, max(g.x, g.y));

    // ---- Scanner-Balken (oben, y 0.80..0.86), 32 Segmente
    {
        float n = 32.0;
        float x0 = 0.12, w = 0.76;
        vec2 p = (uv - vec2(x0, 0.80)) / vec2(w, 0.06);
        if (p.x >= 0.0 && p.x < 1.0 && p.y >= 0.0 && p.y < 1.0) {
            float seg = floor(p.x * n);
            float gap = step(0.12, fract(p.x * n)) * step(0.15, p.y) * step(p.y, 0.85);
            float speed = 0.55 + 1.3 * listening + 4.0 * thinking + 0.9 * speaking + 2.0 * loading;
            float pos = (sin(iTime * speed * 2.0) * 0.5 + 0.5) * (n - 1.0);
            float d = abs(seg - pos);
            float b = pow(max(0.0, 1.0 - d / 5.0), 2.0);
            // beim Nachdenken: zusätzliche zufällige Segmente flackern
            b += thinking * step(0.93, hash(vec2(seg, floor(iTime * 25.0)))) * 0.8;
            // beim Sprechen: ganzer Balken pulst mit der Stimme
            b += speaking * uRms * 0.5;
            col += mix(DIM, RED, clamp(b, 0.0, 1.0)) * gap * 1.6;
        }
    }

    // ---- Voice-Modulator: drei Säulen (Mitte y 0.33..0.72)
    {
        float cols[3];
        float amp = speaking * uRms + listening * uLevel * 0.8 + loading * (0.5 + 0.5 * sin(iTime * 3.0)) * 0.3;
        amp = max(amp, 0.04 + 0.03 * sin(iTime * 1.1));        // Ruheatmung
        cols[1] = amp;
        cols[0] = amp * (0.55 + 0.35 * uMid) * (0.8 + 0.2 * sin(iTime * 7.0 + 1.0));
        cols[2] = amp * (0.55 + 0.35 * uHigh) * (0.8 + 0.2 * sin(iTime * 6.3 + 2.0));
        for (int k = 0; k < 3; k++) {
            float cx = 0.5 + float(k - 1) * 0.11;
            vec2 p = (uv - vec2(cx - 0.035, 0.33)) / vec2(0.07, 0.39);
            if (p.x >= 0.0 && p.x < 1.0 && p.y >= 0.0 && p.y < 1.0) {
                float nseg = 20.0;
                float seg = floor(p.y * nseg);
                float gap = step(0.2, fract(p.y * nseg)) * step(0.08, p.x) * step(p.x, 0.92);
                // von der Mitte nach oben und unten
                float dist = abs(seg + 0.5 - nseg * 0.5) / (nseg * 0.5);
                float lit = step(dist, cols[k]);
                vec3 lc = mix(RED, AMBER, step(0.7, dist));
                lc = mix(lc, vec3(0.35, 0.9, 0.5), listening * 0.6);   // beim Zuhören grünlich
                col += lc * gap * (lit * 1.3 + 0.07);
            }
        }
    }

    // ---- Waveform (unten, y 0.17..0.29): Mikrofon oder Stimme
    {
        float y0 = 0.23;
        float h = 0.05 * (0.4 + 1.2 * (speaking + listening));
        float dx = 1.5 * px / aspect;
        float ya = y0 + wave(uv.x) * h, yb = y0 + wave(uv.x + dx) * h;
        float slope = (yb - ya) / dx;
        float d = abs(uv.y - ya) / sqrt(1.0 + slope * slope);
        vec3 wc = mix(RED, AMBER, speaking);
        col += wc * (exp(-d * 500.0) + 0.3 * exp(-d * 90.0)) * (0.5 + 0.6 * live);
        col += RED * 0.1 * smoothstep(1.5 * px, 0.0, abs(uv.y - y0));
    }

    // ---- Readouts: Zustandsnummer links oben, Pegel rechts oben, Zeit im Zustand
    {
        vec2 sz = vec2(0.011, 0.028);
        col += AMBER * number(int(uRms * 99.0), uv, vec2(0.06, 0.92), sz);
        col += AMBER * number(int(uLevel * 99.0), uv, vec2(0.12, 0.92), sz);
        col += RED * 0.9 * number(int(mod(uStateT, 100.0)), uv, vec2(0.89, 0.92), sz);
        // Zustands-LEDs: vier Punkte, der aktive leuchtet
        for (int k = 0; k < 4; k++) {
            float on = float(st == k) * (0.7 + 0.3 * sin(iTime * (2.0 + 6.0 * thinking)));
            float led = smoothstep(0.011, 0.007, length((uv - vec2(0.42 + float(k) * 0.05, 0.935)) * vec2(aspect, 1.0)));
            col += mix(DIM, k == 1 ? vec3(0.35, 0.9, 0.5) : (k == 2 ? AMBER : RED), on) * led;
        }
    }

    // Beat / Sprachimpuls
    col *= 1.0 + 0.25 * uBeat * speaking;

    // ---- CRT
    col *= 0.84 + 0.16 * sin(vUv.y * iResolution.y * 3.14159);
    col *= 0.97 + 0.03 * sin(iTime * 61.0);
    col += RED * 0.02 * hash(vUv * iResolution.xy + iTime);
    col *= inside * (1.0 - 0.5 * smoothstep(0.7, 1.6, rr));
    fragColor = vec4(col, 1.0);
}
