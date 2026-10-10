#version 140
// Space-Slotmaschine: schwebender, atmender Automat vor einem Kaleidoskop-Nebel, drei Walzen mit
// Pixel-Symbolen aus dem Sprite-Atlas (uSpriteTex), Lauflichter, Hebel, Münzregen, Jackpot-Strahlen.
// Zustand und Walzenpositionen kommen vom Controller (visualizers/scenes/slots.py).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSpriteTex;
uniform vec2 uAtlasSize;
uniform float uTheme, uState, uStateT, uWin, uWinMask, uLever, uFade, uStripRow;
uniform vec3 uColA, uColB, uReel, uSpeed;

const float STRIP = 32.0;
const float CELL = 0.146;          // Symbolhöhe in Höheneinheiten
const float REEL_W = 0.34;
const float WIN_H = 0.22;          // halbe Fensterhöhe
const float PI = 3.14159265;

float hash1(float n) { n = fract(n * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.1 + 7.0; a *= 0.5; }
    return v;
}
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdBox(vec2 p, vec2 b, float r) { vec2 d = abs(p) - b + r; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r; }
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
vec3 hueShift(vec3 c, float a) {        // leichte Farbdrift (psychedelisch, aber dezent)
    const vec3 k = vec3(0.57735);
    float cs = cos(a), sn = sin(a);
    return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs);
}

// Symbol idx des Themas an lokaler Position l (0..1): RGBA aus dem Atlas
vec4 sprite(float idx, vec2 l) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return vec4(0.0);
    vec2 px = vec2(idx * 16.0 + l.x * 16.0, uTheme * 16.0 + l.y * 16.0);
    return texture(uSpriteTex, (floor(px) + 0.5) / uAtlasSize);
}
float stripSymbol(float reel, float k) {
    float kk = mod(k, STRIP);
    return floor(texture(uSpriteTex, vec2((kk + 0.5) / uAtlasSize.x, (uStripRow + reel + 0.5) / uAtlasSize.y)).r * 255.0 + 0.5);
}
// Eine Walze: q lokale Koordinate (x ±REEL_W/2, y ±WIN_H), pos Walzenposition in Symbolen
vec4 reelPixel(float reel, vec2 q, float pos) {
    // Zylinderwölbung: Zeilen am Rand gestaucht
    float yn = clamp(q.y / (WIN_H * 1.05), -1.0, 1.0);
    float yc = asin(yn) / (PI * 0.5) * WIN_H * 1.05;
    float k = floor(pos + yc / CELL + 0.5);
    float ly = (yc - (k - pos) * CELL) / CELL + 0.5;      // 0..1 in der Zelle
    float lx = q.x / REEL_W + 0.5;
    vec2 l = (vec2(lx, ly) - 0.1) / 0.8;
    float idx = stripSymbol(reel, k);
    vec4 s = sprite(idx, l);
    float shade = 0.55 + 0.45 * cos(yn * 1.35);
    s.rgb *= shade;
    return s;
}
vec4 reelBlurred(float reel, vec2 q, float pos, float speed) {
    if (speed < 2.5) return reelPixel(reel, q, pos);
    float d = speed * 0.012;
    vec4 a = reelPixel(reel, q, pos - d), b = reelPixel(reel, q, pos), c = reelPixel(reel, q, pos + d);
    vec4 m = (a + b + c) / 3.0;
    m.a = min(1.0, m.a * 1.1);
    m.rgb *= 0.9;
    return m;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = vUv;
    vec2 p0 = (uv - 0.5) * vec2(aspect, 1.0);
    float t = iTime;
    float live = 1.0 - uSilent;
    float beat = uBeat * live;
    float bass = uBass * live;
    bool result = uState > 1.5 && uState < 2.5;
    bool spinning = uState > 0.5 && uState < 1.5;
    float winPulse = result && uWin > 0.5 ? 0.5 + 0.5 * sin(t * 10.0) : 0.0;
    float jackpot = result && uWin > 2.5 ? 1.0 : 0.0;

    // ---- Traum: alles schwebt, atmet, dreht sich leicht
    float wob = 1.0 + 0.025 * sin(t * 0.6) + 0.03 * bass + 0.08 * uFade;
    float ang = 0.035 * sin(t * 0.45) + 0.012 * sin(t * 6.0) * bass + 0.02 * jackpot * sin(t * 15.0);
    vec2 p = rot(ang) * p0 / wob;
    p.x += 0.008 * sin(p.y * 9.0 + t * 1.7);
    p.y += 0.006 * sin(p.x * 7.0 + t * 1.3) + 0.01 * sin(t * 0.8);

    // ---- Hintergrund: Kaleidoskop-Nebel in Themenfarben
    vec2 kq = rot(t * 0.05) * p0;
    float a = atan(kq.y, kq.x);
    float seg = PI / 3.0;
    a = abs(mod(a, seg * 2.0) - seg);                       // sechsfach gespiegelt
    float r = length(kq) * (1.0 - 0.12 * bass);
    float n = fbm(vec2(a * 2.5 + t * 0.07, r * 3.5 - t * 0.25 - uFade * 3.0));
    float n2 = fbm(vec2(r * 6.0 + t * 0.1, a * 4.0));
    vec3 colA = hueShift(uColA, 0.25 * sin(t * 0.21));
    vec3 colB = hueShift(uColB, 0.25 * sin(t * 0.17 + 2.0));
    vec3 bg = mix(colB * 0.25, colA * 0.45, smoothstep(0.35, 0.7, n)) * (0.6 + 0.8 * n2);
    bg += colA * 0.5 * smoothstep(0.55, 0.9, n) * (0.4 + 0.6 * spec(r));   // Spektrum färbt Ringe
    bg *= 0.55 + 0.45 * smoothstep(1.2, 0.2, r);
    // Sterne, die mit dem Beat funkeln
    vec2 sc = floor(p0 * 60.0);
    float star = step(0.985, hash12(sc)) * (0.5 + 0.5 * sin(t * 3.0 + hash12(sc + 1.0) * 6.28)) * (1.0 + beat);
    bg += vec3(star) * smoothstep(0.6, 0.0, length(fract(p0 * 60.0) - 0.5) * 2.0);
    // Jackpot: rotierende Strahlen
    float rays = step(0.5, fract(atan(p0.y, p0.x) * 6.0 / PI + t * 0.6)) * jackpot;
    bg += colA * rays * 0.25;
    vec3 col = bg;

    // ---- Automat
    vec2 body = vec2(0.64, 0.43);
    float dBody = sdBox(p, body, 0.06);
    float dWin = sdBox(p, vec2(0.545, WIN_H + 0.015), 0.02);
    float dMarq = sdBox(p - vec2(0.0, 0.345), vec2(0.56, 0.055), 0.02);
    float dMsg = sdBox(p + vec2(0.0, 0.315), vec2(0.56, 0.06), 0.02);
    vec3 metal = mix(colB * 0.45, colB * 0.95, smoothstep(-0.45, 0.45, p.y + 0.15 * sin(p.x * 6.0 + t)));
    metal += 0.08 * sin(p.y * 90.0 + t * 2.0);
    metal = mix(metal, colA, 0.25 * winPulse + 0.2 * jackpot);
    if (dBody < 0.0) {
        col = metal * (0.7 + 0.3 * smoothstep(0.0, -0.04, dBody));
        col += colA * 0.5 * smoothstep(0.012, 0.0, abs(dBody + 0.02));   // Zierleiste
    }
    // Lauflichter am Rand
    for (int i = 0; i < 36; i++) {
        float fi = float(i);
        vec2 bp;
        if (i < 14) bp = vec2(-0.585 + fi * 0.09, 0.405);
        else if (i < 28) bp = vec2(0.585 - (fi - 14.0) * 0.09, -0.405);
        else if (i < 32) bp = vec2(-0.605, 0.27 - (fi - 28.0) * 0.18);
        else bp = vec2(0.605, -0.27 + (fi - 32.0) * 0.18);
        float on = step(fract(fi / 36.0 * 3.0 - t * (0.6 + 1.6 * uMid * live)), 0.35);
        on = max(on, winPulse * step(0.5, fract(fi * 0.5 + t * 8.0)));
        on = max(on, jackpot);
        vec3 bc = jackpot > 0.5 ? hueShift(colA, fi * 0.4 + t * 3.0) : mix(colA, vec3(1.0, 0.95, 0.8), 0.5);
        float dd = length(p - bp);
        col += bc * on * (smoothstep(0.014, 0.008, dd) + 0.4 * smoothstep(0.035, 0.0, dd));
        col += bc * 0.08 * smoothstep(0.014, 0.008, dd);
    }
    // Laufschrift-Panel oben und Meldungspanel unten (Text zeichnet der Controller)
    if (dMarq < 0.0) {
        float stripe = step(0.5, fract((p.x - t * 0.15) * 8.0));
        col = mix(vec3(0.03, 0.02, 0.05), colA * 0.18, stripe) + colA * 0.1 * bass;
    }
    if (dMsg < 0.0) col = vec3(0.02, 0.02, 0.04) + colB * 0.08;
    // Walzenfenster
    if (dWin < 0.0) {
        col = vec3(0.04, 0.04, 0.06);
        float gapGlow = 0.0;
        for (int rI = 0; rI < 3; rI++) {
            float fr = float(rI);
            float cx = (fr - 1.0) * 0.36;
            vec2 q = p - vec2(cx, 0.0);
            if (abs(q.x) < REEL_W * 0.5 && abs(q.y) < WIN_H) {
                float pos = rI == 0 ? uReel.x : (rI == 1 ? uReel.y : uReel.z);
                float sp = rI == 0 ? uSpeed.x : (rI == 1 ? uSpeed.y : uSpeed.z);
                // Walzenhintergrund: heller Zylinder mit Wölbung
                float yn = q.y / WIN_H;
                vec3 drum = mix(vec3(0.82, 0.84, 0.9), vec3(0.95, 0.96, 1.0), 0.5 + 0.5 * cos(yn * 1.4));
                drum *= 0.75 + 0.25 * cos(yn * 1.6);
                drum = mix(drum, colB, 0.12);
                // Streifen bei hoher Drehzahl
                drum *= 1.0 - 0.25 * step(2.5, sp) * step(0.5, fract(q.y * 40.0 + pos * 7.0));
                vec4 s = reelBlurred(fr, q, pos, sp);
                col = mix(drum, s.rgb, s.a);
                // Gewinnlinie markieren
                float onLine = step(abs(q.y), CELL * 0.5);
                float maskBit = mod(floor(uWinMask / pow(2.0, fr)), 2.0);
                if (result && maskBit > 0.5) {
                    float glow = winPulse * onLine;
                    col += colA * glow * 0.45 * (1.0 - s.a) + vec3(1.0, 0.9, 0.6) * glow * 0.25 * s.a;
                    col += colA * smoothstep(0.012, 0.0, abs(abs(q.y) - CELL * 0.5)) * winPulse;
                }
                // verlorene Runde: kurz abdunkeln
                if (result && uWin < 0.5) col *= 0.75 + 0.25 * smoothstep(0.0, 0.8, uStateT);
                // Rand der Walze
                col *= 0.6 + 0.4 * smoothstep(0.0, 0.02, REEL_W * 0.5 - abs(q.x));
            }
        }
        // Gewinnlinien-Pfeile in den Lücken
        float arrowL = smoothstep(0.012, 0.0, abs(p.y) - (0.545 - abs(p.x)) * 0.5) * step(0.525, abs(p.x));
        col += colA * arrowL * (0.6 + 0.4 * sin(t * 4.0));
        col += colA * 0.3 * smoothstep(0.004, 0.0, abs(p.y)) * step(REEL_W * 0.5, abs(abs(p.x) - 0.36) - 0.0) * step(abs(p.x), 0.56);
        // Glasreflex
        col += vec3(0.08) * smoothstep(0.0, 0.3, p.y - p.x * 0.4);
    }
    // Hebel rechts: Stange mit Kugel, kippt beim Start
    {
        vec2 piv = vec2(0.70, -0.05);
        vec2 h = rot(-uLever * 1.3) * (p - piv);
        float stick = smoothstep(0.012, 0.004, abs(h.x)) * step(0.0, h.y) * step(h.y, 0.32);
        float ball = smoothstep(0.045, 0.035, length(h - vec2(0.0, 0.33)));
        float base = smoothstep(0.03, 0.02, length(p - piv));
        col = mix(col, vec3(0.75, 0.77, 0.85), stick + base);
        col = mix(col, vec3(0.9, 0.2, 0.2) + colA * 0.3, ball);
    }
    // Münzregen bei Gewinn
    if (result && uWin > 0.5) {
        float cols = 14.0;
        float cxI = floor(p0.x * cols / aspect + cols * 0.5);
        float h0 = hash1(cxI + 3.0 + uTheme);
        float fall = fract(h0 - uStateT * (0.35 + 0.4 * h0) * (uWin > 1.5 ? 1.3 : 0.8));
        float yC = 0.55 - fall * 1.15;
        float xC = (cxI - cols * 0.5 + 0.5) * aspect / cols + 0.02 * sin(t * 3.0 + h0 * 7.0);
        vec2 d = p0 - vec2(xC, yC);
        float wobble = abs(cos(t * 7.0 + h0 * 9.0)) * 0.7 + 0.3;
        float coin = smoothstep(0.026, 0.02, length(d / vec2(wobble, 1.0)));
        float ring = smoothstep(0.004, 0.0, abs(length(d / vec2(wobble, 1.0)) - 0.014));
        float density = uWin > 2.5 ? 1.0 : (uWin > 1.5 ? step(0.3, hash1(cxI + 9.0)) : step(0.65, hash1(cxI + 9.0)));
        col = mix(col, vec3(1.0, 0.85, 0.3), coin * density * step(0.3, uStateT));
        col += vec3(0.5, 0.4, 0.1) * ring * density * step(0.3, uStateT);
    }
    // Themenwechsel: Weißblitz mit Farbsaum
    col = mix(col, vec3(1.0, 0.97, 0.9), uFade * uFade);
    col += colA * uFade * (1.0 - uFade) * 0.6;
    // Beat: kurzer Blitz, Vignette
    col += colA * beat * 0.06;
    col *= 1.0 - 0.35 * pow(length(uv - 0.5) * 1.3, 2.0);
    fragColor = vec4(col, 1.0);
}
