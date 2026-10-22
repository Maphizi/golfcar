#version 140
// Paradoxon: Erfinderwerkstatt (uSceneTex) in Wellen (uPhase 0 Störung, 1 Paradoxon, 2 1,21 Gigawatt, 3 Auslöschung).
// uPoison 0..1 = Bruch der Zeitlinie (Doppelbild, Sepia/Blitzblau, Filmkorn, Ränder verbiegen, Hand wird durchsichtig).
// Bass = Herzschlag, Beat = Bildsprung (uCut) + Negativflackern, Höhen = Korn und Staubfäden, Drop = uFlash + Blitz.
// Anachronismen uCre0..4 / uCreP (4x3 à 256). Fahrerfoto (uPhotoTex) als Polaroid auf dem Tisch (uPhoto = Mitte x, y, Breite),
// verblasst mit uFade 0..1 von den Rändern her (fbm-Maske). Blitze uBolt (Alter, x, Seed, Stärke). Gegenmaßnahme uRelief,
// Zeitkreise neu starten uRebootT, Foto ansehen uPhotoView, Professor + Zeitmaschine uHelpT (uFigTex 8x3 à 192: uCar =
// Zelle A, B, Mischung, Zeit; uProf = Zelle A, B, Mischung, Sichtbarkeit), zurück in 1985 uShock.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uCreatureTex, uPhotoTex, uFigTex;
uniform vec2 uSceneSize, uCreatureSize, uPhotoSize, uFigSize, uCut;
uniform vec3 uPhoto, uHand;
uniform float uPhotoOK, uFigOK, uSeed, uPhase, uPhaseT, uPhaseLen, uWave, uPoison, uFade, uRelief, uRebootT, uPhotoView, uHelpT, uShock;
uniform float uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash;
uniform vec4 uBolt, uCar, uProf;
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
float cross2(vec2 a, vec2 b) { return a.x * b.y - a.y * b.x; }
vec3 hueShift(vec3 c, float a) { const vec3 k = vec3(0.57735); float cs = cos(a), sn = sin(a); return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs); }
vec3 sepia(vec3 c) { float l = dot(c, vec3(0.3, 0.55, 0.15)); return vec3(l) * vec3(1.12, 0.9, 0.62); }
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
    vec4 s = bilin(uCreatureTex, lo + (d * 0.5 + 0.5) * 256.0, uCreatureSize, lo, lo + 255.0);
    s.a *= smoothstep(0.02, 0.12, dot(s.rgb, vec3(0.33)) + s.a * 0.5);         // Schwarz = frei
    return s;
}
vec4 figCell(float idx, vec2 d) {                                            // Professor / Zeitmaschine (8x3 à 192)
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    vec4 s = bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
    s.a *= smoothstep(0.03, 0.12, dot(s.rgb, vec3(0.33)));                     // Schwarz = frei (einige Zellen ohne Alpha)
    return s;
}
vec4 creAt(int i) { return i == 0 ? uCre0 : (i == 1 ? uCre1 : (i == 2 ? uCre2 : (i == 3 ? uCre3 : uCre4))); }
vec4 crePAt(int i) { return i == 0 ? uCreP0 : (i == 1 ? uCreP1 : (i == 2 ? uCreP2 : (i == 3 ? uCreP3 : uCreP4))); }

// Umkehrung der bilinearen Abbildung: p im Viereck a (unten links), b (unten rechts), c (oben rechts), d (oben links) -> (u, v)
vec2 invBilinear(vec2 p, vec2 a, vec2 b, vec2 c, vec2 d) {
    vec2 e = b - a, f = d - a, g = a - b + c - d, h = p - a;
    float k2 = cross2(g, f), k1 = cross2(e, f) + cross2(h, g), k0 = cross2(h, e);
    if (abs(k2) < 1e-4) return vec2((h.x * k1 + f.x * k0) / (e.x * k1 - g.x * k0), -k0 / k1);
    float w = k1 * k1 - 4.0 * k0 * k2;
    if (w < 0.0) return vec2(-1.0);
    w = sqrt(w);
    float ik2 = 0.5 / k2;
    float v = (-k1 - w) * ik2;
    float u = (h.x - f.x * v) / (e.x + g.x * v);
    if (u < 0.0 || u > 1.0 || v < 0.0 || v > 1.0) { v = (-k1 + w) * ik2; u = (h.x - f.x * v) / (e.x + g.x * v); }
    return vec2(u, v);
}
// Fahrerfoto an Stelle q (0..1 im Bild), verblasst mit fade von den Rändern und über eine fbm-Maske (nicht gleichmäßig)
vec4 photoAt(vec2 q, float fade, float t) {
    vec2 tq = vec2(q.x, 0.2 + q.y * 0.75);                                     // quadratisches Foto auf 4:3 beschnitten
    vec2 fw = min(fwidth(tq), vec2(0.02)) * 0.25;                               // 2x2 Überabtastung gegen Flimmern (Foto ist klein)
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) return vec4(0.0);
    vec3 pc = vec3(0.0);
    for (int i = 0; i < 4; i++) {
        vec2 o = vec2(i == 1 || i == 3 ? 1.0 : -1.0, i >= 2 ? 1.0 : -1.0) * fw;
        pc += bilin(uPhotoTex, (tq + o) * uPhotoSize, uPhotoSize, vec2(0.0), uPhotoSize - 1.0).rgb * 0.25;
    }
    float inner = min(min(q.x, 1.0 - q.x), min(q.y, 1.0 - q.y)) * 2.0;        // 0 am Rand, 1 in der Mitte
    float m = inner * 0.55 + fbm(q * vec2(4.0, 3.0) + uSeed * 0.1) * 0.6 + 0.08 * sin(t * 0.7 + q.y * 5.0);
    float vis = smoothstep(fade * 1.35 - 0.3, fade * 1.35 + 0.05, m);
    vis *= 1.0 - fade * 0.25;                                                  // das Ganze wird blasser
    vec3 washed = mix(pc, vec3(0.92, 0.9, 0.84), 0.6 * fade);                  // Reste werden milchig
    return vec4(washed, vis);
}
// Durchsichtige Hand (prozedural): Handfläche + fünf Finger, liegt unten rechts auf dem Tisch
float capsule(vec2 p, vec2 a, vec2 b, float r) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h) - r; }
float smin(float a, float b, float k) { float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }
float handSdf(vec2 p) {                                                        // p relativ zur Handmitte, Einheit = Handgröße
    p = rot(-0.35) * p;
    vec2 q = p; q.y = max(q.y, 0.0) * 0.9 + min(q.y, 0.0);
    float palm = length(max(abs(q) - vec2(0.42, 0.45) + 0.3, 0.0)) - 0.3;
    float d = palm;
    for (int i = 0; i < 4; i++) {
        float fi = float(i);
        float x = -0.33 + fi * 0.22;
        float len = 0.55 + 0.25 * sin(fi * 2.0 + 1.0);
        vec2 tip = vec2(x + 0.08 * (fi - 1.5), 0.4 + len);
        d = smin(d, capsule(p, vec2(x, 0.3), tip, 0.1), 0.08);
    }
    d = smin(d, capsule(p, vec2(-0.42, -0.05), vec2(-0.8, 0.35), 0.11), 0.1); // Daumen
    return d;
}
// Blitz: gezackte Linie von oben nach unten um x0, Helligkeit 0..1
float bolt(vec2 uv, float x0, float seed, float t, float aspect) {
    float y = 1.0 - uv.y;
    float x = x0 + (fbm(vec2(y * 7.0 + seed, floor(t * 20.0) * 0.37)) - 0.5) * 0.3 * (0.2 + y);
    float branch = x + (noise(vec2(y * 11.0 + seed * 3.0, 2.0)) - 0.5) * 0.25 * y;
    float dx = abs(uv.x - x) * aspect, db = abs(uv.x - branch) * aspect;
    float core = exp(-dx * 220.0) + 0.35 * exp(-dx * 40.0);
    float side = (exp(-db * 220.0) + 0.3 * exp(-db * 40.0)) * step(0.3, y) * 0.7;
    return (core + side) * smoothstep(0.0, 0.1, y);
}
// Werkstatt + Polaroid + Hand = das eigentliche Bild (für klare Varianten mit eigenem fade / handAlpha)
vec3 compose(vec2 uv, float fade, float handAlpha, float t, float aspect) {
    vec3 col = scene(uv);
    if (uPhotoOK > 0.5) {
        float s = uPhoto.z / 0.12;
        vec2 c = uPhoto.xy;
        vec2 a = c + s * vec2(-0.0499, -0.0531), b = c + s * vec2(0.0673, -0.0299);
        vec2 cc = c + s * vec2(0.0423, 0.0479), d = c + s * vec2(-0.0593, 0.0340);
        vec2 q = invBilinear(uv, a, b, cc, d);
        vec4 ph = photoAt(q, fade, t);
        vec3 lit = ph.rgb * vec3(1.0, 0.93, 0.82) * (0.85 + 0.1 * q.y);        // warmes Lampenlicht auf dem Tisch
        col = mix(col, lit, ph.a);
    }
    if (handAlpha > 0.001) {
        vec2 p = (uv - uHand.xy) * vec2(aspect, 1.0) / uHand.z;
        p += vec2(0.015 * sin(t * 9.0), 0.01 * cos(t * 7.5)) * (0.3 + uBassS);   // zittert
        float d = handSdf(p);
        float body = smoothstep(0.02, -0.02, d);
        float shade = smoothstep(-0.3, 0.05, d);
        vec3 skin = mix(vec3(0.38, 0.22, 0.15), vec3(0.85, 0.6, 0.45), 1.0 - shade * 0.7) * (0.5 + 0.4 * smoothstep(-0.3, 0.9, p.y));
        skin *= 0.85 + 0.15 * noise(p * 14.0);                                 // Haut
        skin *= 0.75 + 0.25 * smoothstep(0.1, -0.2, abs(p.x + 0.1));             // Rundung der Handfläche
        float rim = smoothstep(0.05, 0.0, abs(d)) * 0.5;
        col = mix(col, col * vec3(0.55, 0.45, 0.4), smoothstep(0.3, -0.05, d - 0.12) * 0.5 * handAlpha);   // Schatten auf dem Tisch
        col = mix(col, skin, body * handAlpha);
        col += vec3(0.5, 0.7, 1.0) * rim * (1.0 - handAlpha) * 0.5;              // Geisterkante, wenn sie schwindet
    }
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    int phase = int(uPhase + 0.5);
    float k = clamp(uPhaseT / max(uPhaseLen, 0.1), 0.0, 1.0);
    float poison = clamp(uPoison * (1.0 - 0.7 * uRelief) * (1.0 - 0.8 * uShock), 0.0, 1.0);
    float horror = phase == 2 ? smoothstep(0.0, 0.15, k) : 0.0;
    float live = uLive;
    float heart = uBassS * live;
    float handA = (1.0 - 0.85 * poison) * (1.0 - 0.5 * uFade);
    handA *= 1.0 - 0.5 * horror * step(0.5, fract(t * 13.0 + uBeatStep));         // flackert in der Gigawatt-Phase
    // ---- Kamera: Herzschlag pumpt das Bild, Bildsprünge auf den Beat, Neustart rollt das Bild
    vec2 uv = vUv;
    uv = 0.5 + (uv - 0.5) * (1.0 - 0.05 * heart * (0.4 + poison) - 0.02 * sin(t * 0.9) * poison);
    uv += uCut * uBeatPulse * (0.3 + horror);
    if (uRebootT >= 0.0) {
        float v = sin(min(1.0, uRebootT / 3.0) * PI);
        uv.y = fract(uv.y + v * uRebootT * 0.8);
        float band = step(0.9, hash12(vec2(floor(vUv.y * 40.0), floor(t * 15.0))));
        uv.x += band * 0.03 * v;                                               // Synchronrisse
    }
    // Ränder verbiegen sich mit den Mitten, der Bruch lässt alles wabern
    float edge = smoothstep(0.2, 0.5, length(vUv - 0.5));
    uv += vec2(sin(uv.y * 12.0 + t * 1.3), cos(uv.x * 10.0 - t * 1.1)) * 0.012 * (uMidS * 0.6 + 0.4 * poison) * edge;
    uv += (vec2(fbm(uv * 3.0 + t * 0.2), fbm(uv * 3.0 - t * 0.17 + 5.0)) - 0.5) * 0.03 * poison;
    vec3 col = compose(uv, uFade, handA, t, aspect);
    // ---- Doppelbild: Zeitlinien überlagern sich (Kanaltrennung, zweites Bild in Blitzblau)
    float dbl = poison * (0.6 + 0.4 * sin(t * 0.7));
    vec2 off = vec2(0.012 + 0.02 * uMidS, 0.006) * dbl;
    vec3 ghost = vec3(scene(uv + off).r, col.g, scene(uv - off).b);
    col = mix(col, ghost, 0.6 * dbl);
    vec2 off2 = vec2(0.02 * sin(t * 0.5), 0.03) * dbl;
    col = mix(col, max(col, scene(uv + off2) * vec3(0.6, 0.8, 1.3)), 0.35 * dbl * (0.5 + 0.5 * uBeatPulse));
    // ---- Farben kippen: Sepia (alte Fotos) gegen Blitzblau, mit dem Beat-Schritt wandernd
    float lum = dot(col, vec3(0.3, 0.55, 0.15));
    vec3 sep = sepia(col) * 1.15;
    vec3 blue = vec3(lum) * vec3(0.55, 0.75, 1.3);
    float swing = 0.5 + 0.5 * sin(t * 0.4 + uv.y * 3.0 + uBeatStep * 0.6);
    vec3 shifted = mix(sep, blue, swing * (0.4 + 0.6 * horror));
    col = mix(col, shifted, poison * 0.75);
    col *= 1.0 - 0.1 * poison * step(0.5, fract(vUv.y * 300.0));
    // Negativflackern auf den Beat (Gigawatt: hart, Paradoxon: kurz)
    float neg = uBeatPulse * uBeatPulse * (0.25 * poison + 0.9 * horror) * live;
    col = mix(col, 1.0 - col, neg * step(0.5, fract(t * 25.0 + uBeatStep)));
    // ---- Blitze: Fenster leuchtet, gezackte Entladungen im Bild (Gigawatt: überall)
    if (uBolt.x >= 0.0) {
        float age = uBolt.x;
        float env = exp(-age * 5.0) * (0.6 + 0.4 * step(0.5, fract(t * 40.0))) * uBolt.w;
        float b = bolt(uv, uBolt.y, uBolt.z, t, aspect);
        int nb = 1 + int(min(2.0, uBolt.w * 1.5));
        for (int i = 1; i < 3; i++) {
            if (i >= nb) break;
            float fi = float(i);
            b += bolt(uv, fract(uBolt.y + 0.37 * fi + uBolt.z * 0.01), uBolt.z + fi * 17.0, t, aspect) * 0.8;
        }
        col += vec3(0.75, 0.85, 1.0) * b * env * 1.4;
        col += vec3(0.4, 0.5, 0.8) * env * 0.25 * smoothstep(0.3, 1.0, uv.y);   // Himmel/Fenster hellt auf
    }
    col = mix(col, vec3(1.0, 0.97, 0.9) * (0.4 + 0.6 * (1.0 - lum)), uFlash * 0.8);   // Drop: weißer Blitz als Negativ
    // ---- Anachronismen lauern an den Rändern, rücken näher, springen auf den Beat
    for (int i = 0; i < 5; i++) {
        vec4 c = creAt(i), p = crePAt(i);
        if (c.w < 0.0) continue;
        float age = p.x;
        float fade = smoothstep(0.0, 1.2, age);
        float lunge = p.y;
        float sz = c.z * (1.0 + 1.2 * lunge + 0.08 * uBassS) * aspect * 0.5;
        vec2 pos = vec2(c.x, c.y);
        pos = mix(pos, vec2(0.5, 0.5), 0.35 * lunge);                        // Sprung Richtung Kamera
        pos += vec2(0.004 * sin(t * 9.0 + age), 0.003 * cos(t * 7.0)) * (poison + horror);
        vec2 d = (uv - pos) * vec2(aspect, 1.0) / sz;
        if (mod(p.w, 2.0) >= 1.0) d.x = -d.x;
        d += vec2(0.02 * sin(d.y * 8.0 + t * 3.0), 0.0) * poison;             // wabert
        vec4 s = creature(c.w, d);
        vec3 sc = mix(s.rgb, sepia(s.rgb) * 1.1, 0.5 * poison);
        sc = hueShift(sc, 0.3 * sin(p.z + t * 2.0) * poison);
        sc = mix(sc, 1.0 - sc, horror * uBeatPulse * 0.6);
        sc *= 0.7 + 0.5 * uBassS + 0.5 * lunge;
        float flick = 0.8 + 0.2 * step(0.3, hash12(vec2(floor(t * 24.0), p.z)));   // alte Filmrolle
        col = mix(col, sc * flick, s.a * fade * (0.75 + 0.25 * lunge));
        // zweite Zeitlinie: blasse, blaue Kopie leicht versetzt
        vec4 s2 = creature(c.w, d + vec2(0.1, 0.05) * (0.5 + 0.5 * sin(t * 1.3 + age)));
        col = mix(col, max(col, vec3(0.5, 0.7, 1.2) * dot(s2.rgb, vec3(0.33))), s2.a * fade * (0.25 * poison + 0.35 * horror));
    }
    // ---- Hilfe: die Zeitmaschine fährt mit Feuerspuren herein, der Professor winkt, klares Bild
    if (uHelpT >= 0.0) {
        float h = uHelpT / 5.0;
        float clear = smoothstep(0.0, 0.25, h) * (1.0 - smoothstep(0.8, 1.0, h));
        col = mix(col, compose(vUv, max(0.0, uFade - 0.3), 1.0, t, aspect), clear * 0.8);
        float drive = 1.0 - pow(1.0 - clamp(uHelpT / 3.0, 0.0, 1.0), 3.0);
        float carX = mix(-0.25, 0.6, drive), carY = 0.3;
        float carW = 0.3;
        // Feuerspuren hinter den Rädern
        for (int i = 0; i < 2; i++) {
            float fy = carY - 0.085 + 0.025 * float(i);
            float along = uv.x - (carX - carW * 0.3);
            float trail = smoothstep(-1.0, 0.0, along) * step(along, 0.0);
            float dy = abs(uv.y - fy - 0.005 * sin(uv.x * 60.0 + t * 20.0) - 0.01 * noise(vec2(uv.x * 25.0 - t * 12.0, float(i) + 5.0)));
            float fire = (exp(-dy * 200.0) + 0.5 * exp(-dy * 500.0)) * trail * (0.6 + 0.4 * noise(vec2(uv.x * 40.0 - t * 15.0, float(i))));
            float dying = 1.0 - smoothstep(3.0, 4.6, uHelpT);
            col += vec3(1.0, 0.6, 0.2) * fire * 1.8 * dying + vec3(1.0, 0.35, 0.05) * exp(-dy * 40.0) * trail * 0.35 * dying;
        }
        if (uFigOK > 0.5) {
            vec2 d = (uv - vec2(carX, carY)) * vec2(aspect, 1.0) / (carW * 0.5);
            d.y = d.y - 1.0 + 0.1;
            vec4 s = mix(figCell(uCar.x, d), figCell(uCar.y, d), uCar.z);
            col = mix(col, s.rgb * 1.1, s.a);
            vec2 dp = (uv - vec2(0.8, 0.24)) * vec2(aspect, 1.0) / 0.19;
            dp.y = dp.y - 1.0 + 0.1;
            vec4 sp = mix(figCell(uProf.x, dp), figCell(uProf.y, dp), uProf.z);
            col = mix(col, sp.rgb * 1.05, sp.a * uProf.w);
        }
        col += vec3(1.0, 0.8, 0.5) * exp(-length((uv - vec2(carX, carY)) * vec2(aspect, 1.0)) * 5.0) * 0.25 * clear;
    }
    // ---- Filmkorn, Staubfäden und Kratzer mit den Höhen
    float grain = noise(vUv * 420.0 + t * 60.0) - 0.5;
    col += grain * (0.05 * poison + 0.18 * uHighS * (0.3 + poison));
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        float slot = floor(t * 6.0 + fi * 0.37);
        float on = step(0.72 - 0.25 * uHighS - 0.1 * poison, hash12(vec2(slot, fi)));
        float hx = hash12(vec2(slot, fi + 10.0));
        float hair = abs(vUv.x - hx - 0.015 * sin(vUv.y * 40.0 + fi * 3.0 + slot)) * aspect;
        float seg = step(hash12(vec2(slot, fi + 20.0)), vUv.y) * step(vUv.y, hash12(vec2(slot, fi + 20.0)) + 0.4);
        col *= 1.0 - smoothstep(0.0025, 0.0, hair) * on * seg * 0.8 * (0.4 + 0.6 * poison);
        float sx = hash12(vec2(slot * 3.0, fi + 30.0));
        float scratch = smoothstep(0.0012, 0.0, abs(vUv.x - sx) * aspect) * step(0.9 - 0.1 * uHighS, hash12(vec2(slot, fi + 40.0)));
        col += vec3(0.9, 0.85, 0.7) * scratch * 0.5 * poison;
    }
    // ---- Vignette kriecht herein (Sepia-Ränder), Tunnelblick auf den Bass
    float rr = length((vUv - 0.5) * vec2(1.0, 1.2));
    float tend = fbm(vec2(atan(vUv.y - 0.5, vUv.x - 0.5) * 3.0, rr * 6.0 - t * 0.1) + uSeed);
    float burn = smoothstep(0.52 - 0.16 * poison, 0.66, rr + (tend - 0.5) * 0.25);
    col = mix(col, vec3(0.08, 0.05, 0.02), burn * (0.4 + 0.5 * poison) * 0.6);
    float tunnel = smoothstep(0.25 + 0.3 * (1.0 - heart) - 0.15 * poison, 0.75, rr) * (0.3 + 0.7 * poison) * (0.5 + 0.5 * heart);
    col *= 1.0 - tunnel;
    // ---- Neustart: Zeitkreis-Ziffern laufen von oben herab (rot / grün / gelb)
    if (uRebootT >= 0.0) {
        float rowY = floor((1.0 - vUv.y) * 48.0);
        float shown = step(rowY, uRebootT * 22.0) * step(rowY, 40.0);
        float cellX = floor(vUv.x * 140.0);
        float inLine = step(0.5, fract(vUv.y * 48.0 + 0.25)) * step(0.2, fract(vUv.x * 140.0));
        float txt = step(0.5, hash12(vec2(cellX, rowY + uSeed + floor(t * 12.0)))) * step(cellX, 10.0 + 60.0 * hash12(vec2(rowY, 3.0))) * step(4.0, cellX) * inLine;
        float which = mod(rowY, 3.0);
        vec3 dc = which < 0.5 ? vec3(1.0, 0.3, 0.2) : (which < 1.5 ? vec3(0.3, 1.0, 0.4) : vec3(1.0, 0.85, 0.25));
        col = mix(col, dc, txt * shown * 0.7 * smoothstep(3.0, 2.2, uRebootT));
    }
    // ---- Zurück in 1985: klares, kaltes Bild, Sepia weg, das Foto da
    if (uShock > 0.001) col = mix(col, compose(vUv, uFade, 1.0, t, aspect) * vec3(0.82, 0.92, 1.15), uShock * 0.85);
    // ---- Auslöschung: Schwarz mit Filmriss (Streifen, Brandloch), Sepia-Nachbilder
    if (phase == 3) {
        float dark = smoothstep(0.0, 0.15, k) * (1.0 - smoothstep(0.75, 1.0, k));
        vec3 after = sepia(scene(vUv)) * 0.3 * (0.6 + 0.4 * sin(t * 0.8)) * (1.0 - smoothstep(0.0, 0.5, k) * 0.6);
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            vec2 ap = vec2(0.3 + 0.2 * fi + 0.05 * sin(t * 0.3 + fi), 0.45 + 0.1 * cos(t * 0.4 + fi * 2.0));
            vec2 d = (vUv - ap) * vec2(aspect, 1.0) / 0.3;
            vec4 s = creature(mod(uWave * 3.0 + fi * 5.0, 12.0), d);
            after += sepia(s.rgb) * s.a * 0.2 * (0.5 + 0.5 * sin(t * 0.8 + fi));
        }
        float streak = step(0.985, hash12(vec2(floor(vUv.x * 160.0), floor(t * 18.0)))) * step(0.5, hash12(vec2(floor(vUv.x * 160.0), floor(t * 4.0))));
        after += vec3(0.9, 0.8, 0.6) * streak * 0.5;
        float r = length((vUv - vec2(0.55, 0.5)) * vec2(aspect, 1.0)) + 0.18 * (fbm(vUv * 6.0 + uSeed) - 0.5);
        float holeR = smoothstep(0.0, 0.7, k) * 1.3;
        float hole = smoothstep(0.006, 0.0, r - holeR);
        float rim = exp(-max(r - holeR, 0.0) * 30.0) * (1.0 - hole);
        float ember = 0.5 + 0.5 * noise(vUv * 40.0 + t * 6.0);
        vec3 black = after * (1.0 - hole) * (1.0 - 0.6 * rim) + vec3(1.0, 0.4, 0.08) * rim * ember * 0.9
                   + vec3(0.5, 0.35, 0.2) * smoothstep(0.03, 0.0, abs(r - holeR)) * ember * 0.4 + vec3(0.2, 0.1, 0.02) * heart * exp(-rr * 3.0);
        col = mix(col, black, dark);
    }
    // ---- Foto ansehen: Dunkel, nur das Polaroid groß in der Mitte, atmet und verblasst
    if (uPhotoView > 0.001) {
        float breathe = 1.0 + 0.04 * sin(t * 1.2) + 0.05 * uBassS;
        vec2 d = (vUv - vec2(0.5, 0.5)) * vec2(aspect, 1.0) / (0.36 * breathe);
        d += vec2(0.004 * sin(t * 20.0), 0.003 * cos(t * 17.0)) * uBeatPulse;
        vec2 q = d * vec2(1.0, 1.333) * 0.5 + 0.5;
        vec2 frame = abs(d) - vec2(1.1, 0.95);
        float inFrame = step(max(frame.x, frame.y + 0.25 * step(d.y, 0.0)), 0.0);   // breiter Rand unten (Polaroid)
        vec3 dark = vec3(0.02, 0.015, 0.01) + vec3(0.05, 0.08, 0.15) * uBeatPulse * horror;
        vec3 paper = vec3(0.9, 0.88, 0.82) * (0.94 + 0.06 * fbm(d * 9.0 + uSeed));
        vec4 ph = uPhotoOK > 0.5 ? photoAt(q, uFade, t) : vec4(0.0);
        vec3 pv = mix(dark, paper, inFrame);
        pv = mix(pv, ph.rgb * (0.9 + 0.1 * sin(t * 0.5)), ph.a);
        pv += vec3(0.75, 0.85, 1.0) * uFlash * 0.4;
        col = mix(col, pv, uPhotoView * 0.97);
    }
    // ---- Stille: schweres Atmen, Sepia kriecht
    float breath = 0.5 + 0.5 * sin(t * 0.6);
    col = mix(col, sepia(col), (1.0 - live) * (0.4 + 0.3 * breath));
    col *= mix(0.35 + 0.25 * breath, 1.0, live);
    col *= 1.0 - 0.25 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
