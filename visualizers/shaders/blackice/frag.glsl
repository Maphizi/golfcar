#version 140
// Black Ice: Hacker-Kammer (uSceneTex) in Wellen (uPhase 0 Einbruch, 1 Trace, 2 Black ICE, 3 Flatline). uPoison 0..1 =
// Trace-Grad (Kanaltrennung, Scanlines, Tunnel, Rauschen). Bass = Herzschlag, Beat = Glitch/Bildsprung (uCut), Höhen =
// Rauschen, Drop = uFlash. Daemonen uCre0..4 / uCreP (4x3 à 256). Black ICE: Daemon-Maske (uGodTex = Orakel-Maske 8x3 à 192,
// Glitch-Zelle uGodCell), Fahndungsbild (uFaceTex) mit Barcode. Gegenmaßnahme uRelief, Neustart uVomitT, Stecker uEyes,
// Fixer-Katze uHelpT (uFigTex Reihe 1, Zellen uOwl), Jack out uShock.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uCreatureTex, uFaceTex, uGodTex, uFigTex;
uniform vec2 uSceneSize, uCreatureSize, uFaceSize, uGodSize, uFigSize, uCut;
uniform float uFaceOK, uGodOK, uFigOK, uSeed, uPhase, uPhaseT, uPhaseLen, uWave, uPoison, uRelief, uVomitT, uEyes, uHelpT, uShock;
uniform float uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash, uGodCell;
uniform vec4 uOwl;
uniform vec4 uCre0, uCre1, uCre2, uCre3, uCre4, uCreP0, uCreP1, uCreP2, uCreP3, uCreP4;
const float PI = 3.14159265;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
vec3 hueShift(vec3 c, float a) { const vec3 k = vec3(0.57735); float cs = cos(a), sn = sin(a); return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs); }
vec4 bilin(sampler2D tex, vec2 px, vec2 size, vec2 lo, vec2 hi) {
    vec2 p = clamp(px - 0.5, lo, hi);
    vec2 i = floor(p), f = fract(p);
    vec2 i1 = min(i + 1.0, hi);
    vec4 a = texture(tex, (i + 0.5) / size), b = texture(tex, (vec2(i1.x, i.y) + 0.5) / size);
    vec4 c = texture(tex, (vec2(i.x, i1.y) + 0.5) / size), d = texture(tex, (i1 + 0.5) / size);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
vec3 scene(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0).rgb; }
vec4 creature(float idx, vec2 d) {                                           // 4x3 à 256, d -1..1
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 4.0), ri = floor(idx / 4.0);
    vec2 lo = vec2(ci * 256.0, (2.0 - ri) * 256.0);
    return bilin(uCreatureTex, lo + (d * 0.5 + 0.5) * 256.0, uCreatureSize, lo, lo + 255.0);
}
vec4 figCell(float idx, vec2 d) {                                            // Eule aus dem Auge des Waldes (8x4 à 192)
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
}
vec4 creAt(int i) { return i == 0 ? uCre0 : (i == 1 ? uCre1 : (i == 2 ? uCre2 : (i == 3 ? uCre3 : uCre4))); }
vec4 crePAt(int i) { return i == 0 ? uCreP0 : (i == 1 ? uCreP1 : (i == 2 ? uCreP2 : (i == 3 ? uCreP3 : uCreP4))); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    int phase = int(uPhase + 0.5);
    float k = clamp(uPhaseT / max(uPhaseLen, 0.1), 0.0, 1.0);
    float poison = clamp(uPoison * (1.0 - 0.7 * uRelief) * (1.0 - 0.8 * uShock), 0.0, 1.0);
    float horror = phase == 2 ? smoothstep(0.0, 0.15, k) : 0.0;
    float live = uLive;
    // ---- Kamera: Atmen, Herzschlag-Zoom, Bildsprünge auf den Beat, Erbrechen kippt das Bild
    vec2 uv = vUv;
    float heart = uBassS * live;
    uv = 0.5 + (uv - 0.5) * (1.0 - 0.05 * heart * poison - 0.02 * sin(t * 0.9) * poison);
    uv += uCut * uBeatPulse * (0.3 + horror);
    if (uVomitT >= 0.0) {
        float v = sin(min(1.0, uVomitT / 3.0) * PI);
        uv.y = fract(uv.y + v * uVomitT * 0.8);
    }
    // Ränder verbiegen sich mit den Mitten, die Vergiftung lässt alles wabern
    float edge = smoothstep(0.2, 0.5, length(vUv - 0.5));
    uv += vec2(sin(uv.y * 12.0 + t * 1.3), cos(uv.x * 10.0 - t * 1.1)) * 0.012 * (uMidS * 0.6 + 0.4 * poison) * edge;
    uv += (vec2(fbm(uv * 3.0 + t * 0.2), fbm(uv * 3.0 - t * 0.17 + 5.0)) - 0.5) * 0.03 * poison;
    vec3 col = scene(uv);
    // ---- Doppelbild: zweites, verschobenes und umgefärbtes Bild
    float dbl = poison * (0.6 + 0.4 * sin(t * 0.7));
    vec2 off = vec2(0.012 + 0.02 * uMidS, 0.006) * dbl;
    vec3 ghost = vec3(scene(uv + off).r, scene(uv).g, scene(uv - off).b);
    col = mix(col, ghost, 0.7 * dbl);
    col *= 1.0 - 0.12 * poison * step(0.5, fract(vUv.y * 300.0));
    // ---- Giftfarben: Grün/Violett kippt mit der Vergiftung, Drop = Rot-Schwarz-Negativ
    float lum = dot(col, vec3(0.3, 0.55, 0.15));
    vec3 toxic = mix(vec3(1.0, 0.15, 0.2), vec3(0.2, 0.8, 1.0), 0.5 + 0.5 * sin(t * 0.4 + uv.y * 3.0 + uBeatStep * 0.4));
    col = mix(col, mix(col, toxic * lum * 1.6, 0.5), poison * 0.7);
    col = mix(col, vec3(lum), poison * 0.2);
    // Negativflackern auf den Beat (Horror: hart, Vergiftung: kurz)
    float neg = uBeatPulse * uBeatPulse * (0.25 * poison + 0.9 * horror) * live;
    col = mix(col, 1.0 - col, neg * step(0.5, fract(t * 25.0 + uBeatStep)));
    col = mix(col, vec3(1.0, 0.1, 0.05) * (1.0 - lum) + vec3(0.0), uFlash * 0.8);
    // ---- Wesen lauern an den Rändern, rücken näher, springen auf den Beat
    for (int i = 0; i < 5; i++) {
        vec4 c = creAt(i), p = crePAt(i);
        if (c.w < 0.0) continue;
        float age = p.x;
        float fade = smoothstep(0.0, 1.2, age) * (1.0 - smoothstep(0.0, 0.3, -1.0));
        float lunge = p.y;
        float sz = c.z * (1.0 + 1.2 * lunge + 0.08 * uBassS) * aspect * 0.5;
        vec2 pos = vec2(c.x, c.y);
        pos = mix(pos, vec2(0.5, 0.5), 0.35 * lunge);                        // Sprung Richtung Kamera
        pos += vec2(0.004 * sin(t * 9.0 + age), 0.003 * cos(t * 7.0)) * (poison + horror);
        vec2 d = (uv - pos) * vec2(aspect, 1.0) / sz;
        if (mod(p.w, 2.0) >= 1.0) d.x = -d.x;
        d += vec2(0.02 * sin(d.y * 8.0 + t * 3.0), 0.0) * poison;             // wabert
        vec4 s = creature(c.w, d);
        vec3 sc = hueShift(s.rgb, p.z * poison * 0.6 + 0.4 * sin(t * 2.0 + age));
        sc = mix(sc, 1.0 - sc, horror * uBeatPulse * 0.6);
        sc *= 0.6 + 0.6 * uBassS + 0.5 * lunge;
        col = mix(col, sc, s.a * fade * (0.75 + 0.25 * lunge));
        // Spiegelkopie bei Horror (Kaleidoskop der Angst)
        if (horror > 0.0) {
            vec2 dm = (vec2(1.0 - uv.x, uv.y) - pos) * vec2(aspect, 1.0) / sz;
            vec4 sm = creature(c.w, dm);
            col = mix(col, 1.0 - sm.rgb * 0.8, sm.a * horror * 0.5 * fade);
        }
    }
    // ---- Horror: Waldgott mit hohlen Augen aus der Mitte, dein Gesicht mit Pilzen
    if (horror > 0.0 && uGodOK > 0.5) {
        float g = uGodCell;
        vec2 lo = vec2(mod(g, 8.0) * 192.0, (2.0 - floor(g / 8.0)) * 192.0);
        float sc = 0.85 + 0.1 * sin(t * 1.3) + 0.08 * uBassS;
        vec2 d = (uv - vec2(0.5, 0.55)) * vec2(aspect, 1.0) / sc;
        d += vec2(0.01 * sin(t * 30.0), 0.01 * cos(t * 27.0)) * uBeatPulse;
        float row = floor(d.y * 30.0);
        d.x += (hash12(vec2(row, floor(t * 12.0))) - 0.5) * 0.08 * step(0.75, hash12(vec2(row, floor(t * 4.0))));
        vec2 q = d * 0.5 + 0.5;
        if (q.x > 0.0 && q.x < 1.0 && q.y > 0.0 && q.y < 1.0) {
            vec4 s = bilin(uGodTex, lo + q * 192.0, uGodSize, lo, lo + 191.0);
            float gl = dot(s.rgb, vec3(0.33));
            vec3 fc = mix(s.rgb, vec3(1.0, 0.1, 0.15) * gl * 1.8, 0.6);
            fc = mix(fc, 1.0 - s.rgb, 0.3 * uBeatPulse);
            fc += vec3(1.0, 0.3, 0.3) * smoothstep(0.6, 0.95, gl) * (0.4 + 0.6 * uBassS);
            float laugh = 0.5 + 0.5 * sin(t * 8.0 + uBeatStep);
            fc *= 0.8 + 0.5 * laugh * uBassS;
            fc *= 0.85 + 0.15 * sin(uv.y * 600.0 + t * 20.0);
            float ghostly = 0.85 * horror * (0.75 + 0.25 * sin(t * 2.0)) * (1.0 - smoothstep(0.75, 1.0, k));
            col = mix(col, fc, s.a * ghostly);
        }
    }
    if (horror > 0.0 && uFaceOK > 0.5 && k > 0.45) {
        float fk = smoothstep(0.45, 0.6, k) * (1.0 - smoothstep(0.9, 1.0, k));
        vec2 fp = vec2(0.5 + 0.2 * sin(t * 0.5), 0.45);
        vec2 d = (uv - fp) * vec2(aspect, 1.0) / vec2(0.3 * uFaceSize.x / uFaceSize.y, 0.3);
        d.x += 0.04 * sin(d.y * 6.0 + t * 2.0);
        vec2 q = d * 0.5 + 0.5;
        if (q.x > 0.0 && q.x < 1.0 && q.y > 0.0 && q.y < 1.0) {
            vec4 s = bilin(uFaceTex, q * uFaceSize, uFaceSize, vec2(0.0), uFaceSize - 1.0);
            float gl = dot(s.rgb, vec3(0.33));
            vec3 fc = vec3(gl) * vec3(1.0, 0.35, 0.3) * (0.7 + 0.3 * uBassS) * (0.85 + 0.15 * sin(uv.y * 500.0 + t * 15.0));
            col = mix(col, fc, max(s.a, 0.5) * fk * 0.9);
            float ex = max(abs(q.x - 0.5) * 2.0, abs(q.y - 0.5) * 2.0);
            col += vec3(1.0, 0.2, 0.2) * smoothstep(0.93, 0.97, ex) * fk;
            float bars = step(0.5, hash12(vec2(floor(q.x * 60.0), 1.0))) * step(q.y, 0.12) * step(0.03, q.y);
            col = mix(col, vec3(1.0, 0.9, 0.9), bars * fk);
            float cross = (smoothstep(0.004, 0.0, abs(d.x)) + smoothstep(0.004, 0.0, abs(d.y))) * step(length(d), 0.25);
            col += vec3(1.0, 0.2, 0.2) * cross * fk * (0.5 + 0.5 * sin(t * 6.0));
        }
    }
    // ---- Hilferuf: die Eule fliegt ein und bringt kurz klares Bild
    if (uHelpT >= 0.0 && uFigOK > 0.5) {
        float h = uHelpT / 5.0;
        float clear = sin(h * PI);
        col = mix(col, scene(vUv), clear * 0.7);
        vec2 op = vec2(mix(1.2, -0.2, h), 0.1 + 0.02 * sin(uHelpT * 6.0));
        vec2 d = (uv - op) * vec2(aspect, 1.0) / (0.16 * aspect * 0.5);
        d.y = d.y - 1.0 + 0.04;
        vec4 s = mix(figCell(uOwl.x, vec2(-d.x, d.y)), figCell(uOwl.y, vec2(-d.x, d.y)), 0.5);
        col = mix(col, s.rgb * 1.1, s.a);
        col += vec3(0.7, 0.3, 1.0) * exp(-length((uv - op) * vec2(aspect, 1.0)) * 6.0) * 0.3 * clear;
    }
    // ---- Fliegen und Rauschen mit den Höhen, Motten im Horror
    int nf = 10 + int(poison * 20.0);
    for (int i = 0; i < 30; i++) {
        if (i >= nf) break;
        float fi = float(i);
        float h1 = hash12(vec2(fi, 41.0)), h2 = hash12(vec2(fi, 43.0));
        vec2 c = vec2(0.5, 0.5) + vec2(cos(t * (1.5 + h1 * 3.0) + fi * 7.0), sin(t * (1.1 + h2 * 2.0) + fi * 3.0)) * vec2(0.3 + 0.2 * h1, 0.25 + 0.2 * h2);
        c += vec2(0.02 * sin(t * 17.0 + fi), 0.02 * cos(t * 19.0 + fi));
        float g = smoothstep(0.004 + 0.004 * horror, 0.0, length((uv - c) * vec2(aspect, 1.0)));
        col = mix(col, vec3(0.05, 0.03, 0.06), g * (0.3 + 0.7 * uHighS) * poison);
    }
    col += (noise(vUv * 300.0 + t * 50.0) - 0.5) * (0.06 * poison + 0.15 * uHighS * poison);
    // ---- Ranken kriechen von den Rändern herein (prozedural, wachsen mit der Vergiftung), Tunnelblick auf den Bass
    float rr = length((vUv - 0.5) * vec2(1.0, 1.2));
    float tendril = fbm(vec2(atan(vUv.y - 0.5, vUv.x - 0.5) * 3.0, rr * 6.0 - t * 0.1) + uSeed) ;
    float vines = smoothstep(0.52 - 0.22 * poison, 0.62, rr + (tendril - 0.5) * 0.25);
    col = mix(col, vec3(0.01, 0.0, 0.02), vines * (0.5 + 0.5 * poison) * 0.7);
    float tunnel = smoothstep(0.25 + 0.3 * (1.0 - heart) - 0.15 * poison, 0.75, rr) * (0.3 + 0.7 * poison) * (0.5 + 0.5 * heart);
    col *= 1.0 - tunnel;
    // ---- Erbrechen: grüne Welle läuft von oben nach unten
    if (uVomitT >= 0.0) {
        float rowY = floor((1.0 - vUv.y) * 70.0);
        float shown = step(rowY, uVomitT * 30.0) * step(rowY, 60.0);
        float cellX = floor(vUv.x * 220.0);
        float inLine = step(0.5, fract(vUv.y * 70.0 + 0.25)) * step(0.2, fract(vUv.x * 220.0));   // Zeilen- und Zeichenlücken
        float txt = step(0.5, hash12(vec2(cellX, rowY + uSeed))) * step(cellX, 12.0 + 90.0 * hash12(vec2(rowY, 3.0))) * step(4.0, cellX) * inLine;
        float blink = step(0.5, fract(t * 3.0)) * step(abs(rowY - floor(uVomitT * 30.0)), 0.5);
        col = mix(col, vec3(0.2, 0.95, 0.4) * (0.7 + 0.3 * blink), txt * shown * 0.7 * smoothstep(3.0, 2.2, uVomitT));
    }
    // ---- Kaltwasserschock: klares, kaltes Bild
    col = mix(col, scene(vUv) * vec3(0.8, 0.9, 1.15), uShock * 0.8);
    // ---- Blackout: Schwarz mit Nachbildern (Wesen als Negativ-Schemen), Puls glimmt
    if (phase == 3) {
        float dark = smoothstep(0.0, 0.15, k) * (1.0 - smoothstep(0.75, 1.0, k));
        vec3 after = vec3(0.0);
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            vec2 ap = vec2(0.3 + 0.2 * fi + 0.05 * sin(t * 0.3 + fi), 0.5 + 0.1 * cos(t * 0.4 + fi * 2.0));
            vec2 d = (uv - ap) * vec2(aspect, 1.0) / 0.25;
            vec4 s = creature(mod(uWave * 3.0 + fi * 5.0, 12.0), d);
            after += (1.0 - s.rgb) * s.a * 0.15 * (0.5 + 0.5 * sin(t * 0.8 + fi));
        }
        float ekgx = fract(vUv.x - k * 2.0);
        float blip = (k < 0.7 ? 1.0 : 0.0) * exp(-pow((fract(k * 6.0) - 0.5) * 8.0, 2.0));
        float ekgy = 0.5 + 0.12 * blip * sin(ekgx * 40.0) * exp(-pow((ekgx - 0.5) * 12.0, 2.0));
        float line = smoothstep(0.004, 0.0, abs(vUv.y - ekgy)) * smoothstep(0.0, 0.3, fract(vUv.x - t * 0.5));
        vec3 black = after * 0.5 + vec3(0.9, 0.1, 0.15) * line * (k < 0.7 ? 1.0 : 0.3) + vec3(0.2, 0.02, 0.05) * heart * exp(-rr * 3.0);
        col = mix(col, black, dark);
    }
    // ---- Augen zu: Dunkelheit, farbige Nachbilder atmen mit der Musik
    if (uEyes > 0.0) {
        vec3 inner = vec3(0.0);
        for (int i = 0; i < 4; i++) {
            float fi = float(i);
            vec2 bp = vec2(0.5, 0.5) + vec2(sin(t * 0.4 + fi * 1.6), cos(t * 0.3 + fi * 2.1)) * 0.25;
            float g = exp(-length((vUv - bp) * vec2(aspect, 1.0)) * (4.0 - 2.0 * uBassS));
            inner += hueShift(vec3(0.1, 0.3, 0.6), fi * 1.5 + t * 0.5) * g * (0.3 + 0.7 * uBassS + 0.5 * uBeatPulse);
        }
        col = mix(col, inner, uEyes * 0.95);
    }
    // ---- Stille: schweres Atmen, Dunkelheit kriecht
    float breath = 0.5 + 0.5 * sin(t * 0.6);
    col *= mix(0.35 + 0.25 * breath, 1.0, live);
    col *= 1.0 - 0.25 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
