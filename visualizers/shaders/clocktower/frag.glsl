#version 140
// Der Uhrturm: Rathaus-Foto im Gewitter (uSceneTex), Zifferblatt uClock (x, y, Radius) ohne Zeiger – die Zeiger zeichnet
// der Shader aus uHands (Stunde, Minute, Sekunde in Umdrehungen). Acht Schaufenster (uWindows: x0, x7, y, Breite) sind
// die acht Spektrumbänder (uBands/uPeaks), Lauflicht uStep/uPattern. Bass = Wolken leuchten von innen + Turm bebt,
// Mitten = Wetterleuchten (uSheet), Höhen = Regen + Funken am Kabel (uCable), Drop/22:04 = Blitz in den Turm (uStrikeT,
// uBoltSeed), Kabel glüht (uCableGlow), Weißblitz (uFlash). Figuren aus uFigTex (8x3): Professor (uDoc), Zeitmaschine
// (uCar/uCarPar), Tanzpaar + Girlanden (uDance/uDancer). uZoom = Nahaufnahme aufs Zifferblatt.
// Ablauf der Nacht: uStorm (Gewitter: Regen, Wolken, ferne Blitze uFarBolt = Alter, x, Seed, Stärke), uFinal (Countdown:
// Kabel knistert, Rand dunkelt), uDocPos (x, y, Sichtbarkeit: Professor am Zeiger oder kletternd), Schaufenster in acht
// Neonfarben mit Paar im Fenster uWinCouple (Fenster, Sichtbarkeit), Pfützen unter uGround spiegeln die Fenster.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uFigTex;
uniform vec2 uSceneSize, uFigSize;
uniform vec3 uClock, uHands;
uniform vec4 uWindows, uCable, uSheet, uFig, uDoc, uDocFitA, uDocFitB, uCar, uCarPar, uCarFit, uDancer, uDancerFitA, uDancerFitB;
uniform vec4 uBands0, uBands1, uPeaks0, uPeaks1;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uStep, uStepPhase, uPattern, uFlash;
uniform float uClockT, uStrikeT, uBoltSeed, uCableGlow, uDance, uZoom;
uniform float uStorm, uFinal, uGround;
uniform vec4 uDocPos, uWinCouple, uFarBolt;
const float PI = 3.14159265;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
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
// Zelle idx (0 = oben links, 8 Spalten, 3 Reihen) des Figurenbogens, d = -1..1 innerhalb der Zelle
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    vec2 cell = uFigSize / vec2(8.0, 3.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * cell.x, (2.0 - ri) * cell.y);
    vec4 s = bilin(uFigTex, lo + (d * 0.5 + 0.5) * cell, uFigSize, lo, lo + cell - 1.0);
    s.a *= smoothstep(0.03, 0.1, max(s.r, max(s.g, s.b)));                                 // Schwarz = frei
    return s;
}
// Zelle mit Passmaß fit = (Mitte x, Fuß y, halbe Breite, halbe Höhe in Zellkoordinaten) zeichnen: der Hauptkörper wird
// `width` breit (aspektkorrigierte Einheiten) und steht mit dem Fuß (top = 0) bzw. hängt mit dem Kopf (top = 1) an pos.
vec4 figFit(float idx, vec2 p, vec2 pos, float width, vec4 fit, float top) {
    float S = width / (2.0 * max(fit.z, 0.05));
    vec2 d = (p - pos) / S + vec2(fit.x, fit.y + 2.0 * fit.w * top);
    return figCell(idx, d);
}
float bandAt(int i) { return i < 4 ? uBands0[i] : uBands1[i - 4]; }
float peakAt(int i) { return i < 4 ? uPeaks0[i] : uPeaks1[i - 4]; }
float activeZone() {
    float s = uStep;
    if (uPattern < 0.5) return s;
    if (uPattern < 1.5) return s < 2.0 ? s : (s == 2.0 ? 2.0 : 1.0);
    if (uPattern < 2.5) return s == 0.0 ? 1.0 : (s == 1.0 ? 2.0 : (s == 2.0 ? 0.0 : 3.0));
    return floor(hash12(vec2(s, uSeed)) * 4.0);
}
float segDist(vec2 p, vec2 a, vec2 b) {
    vec2 ab = b - a;
    float h = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
    return length(p - a - ab * h);
}
// Uhrzeiger: Balken vom Mittelpunkt in Richtung turns (0 = 12 Uhr, im Uhrzeigersinn), d in Radien
float hand(vec2 d, float turns, float len, float wid, float back) {
    float a = turns * 2.0 * PI;
    vec2 dir = vec2(sin(a), cos(a));
    return segDist(d, -dir * back, dir * len) - wid;
}
// Gezackter Blitz zwischen a und b (aspektkorrigierte Koordinaten), amp = Zackenweite
float bolt(vec2 p, vec2 a, vec2 b, float seed, float amp, int n) {
    float dmin = 1e3;
    vec2 prev = a;
    vec2 dir = normalize(b - a + 1e-5), nrm = vec2(-dir.y, dir.x);
    for (int i = 1; i <= 12; i++) {
        if (i > n) break;
        float f = float(i) / float(n);
        vec2 q = mix(a, b, f) + nrm * (hash12(vec2(float(i), seed)) - 0.5) * amp * sin(f * PI) * 1.3;
        dmin = min(dmin, segDist(p, prev, q));
        prev = q;
    }
    return dmin;
}
// Acht Neonfarben der Schaufenster (Tanzabend 1955)
vec3 winCol(int i) {
    if (i == 0) return vec3(1.0, 0.42, 0.68);                                              // Rosa
    if (i == 1) return vec3(0.25, 0.95, 0.88);                                             // Türkis
    if (i == 2) return vec3(1.0, 0.76, 0.28);                                              // Gold
    if (i == 3) return vec3(0.68, 0.52, 1.0);                                              // Lavendel
    if (i == 4) return vec3(0.45, 1.0, 0.58);                                              // Mint
    if (i == 5) return vec3(1.0, 0.5, 0.32);                                               // Koralle
    if (i == 6) return vec3(0.42, 0.68, 1.0);                                              // Himmelblau
    return vec3(1.0, 0.62, 0.42);                                                          // Apricot
}
// Schaufenster an uv: rgb = Licht, a = Deckung (Scheibe 0.95, Rahmen 0.5); col = col * (1 - 0.65 a) + rgb.
// Pegel = Band i, Spitze als Linie, Lauflicht je Fensterpaar, im Fenster uWinCouple.x tanzt ein Paar vor dem Neon.
vec4 windowsAt(vec2 uv, float aspect, float t, float act, float strikeK) {
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float wx = mix(uWindows.x, uWindows.y, fi / 7.0);
        float hw = uWindows.w * 0.5;
        float hh = hw * aspect * 1.3;
        vec2 d = (uv - vec2(wx, uWindows.z)) / vec2(hw, hh);
        if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) continue;
        float band = bandAt(i), pk = peakAt(i);
        float yy = d.y * 0.5 + 0.5;
        float fill = smoothstep(0.08, -0.08, yy - band);
        float pane = smoothstep(1.0, 0.92, abs(d.x)) * smoothstep(1.0, 0.92, abs(d.y));
        float wrun = (floor(fi / 2.0) == act ? 1.0 : 0.0) * (1.0 - 0.6 * uStepPhase);
        float flick = 1.0 - 0.25 * step(0.96, hash12(vec2(fi, floor(t * 18.0)))) * step(0.7, band);
        vec3 neon = mix(hueShift(winCol(i), uBeatStep * 0.05), vec3(0.95, 0.97, 1.0), strikeK);
        float level = min(1.2, 0.08 + 1.1 * band + 0.4 * uBeatPulse * step(0.6, band)) * flick;
        float grad = 0.7 + 0.3 * (1.0 - yy);                                               // unten heller
        vec3 wcol = neon * (fill * level * 1.15 * grad + (1.0 - fill) * (0.06 + 0.14 * band)) + neon * wrun * (0.5 + 0.6 * band);
        wcol += vec3(1.0, 0.97, 0.9) * smoothstep(0.06, 0.0, abs(yy - pk)) * step(0.05, pk) * 0.6;
        if (uWinCouple.y > 0.01 && abs(fi - uWinCouple.x) < 0.5) {
            vec2 p = uv * vec2(aspect, 1.0);
            vec2 fp = vec2(wx * aspect, uWindows.z - hh * 0.92);
            float w = hw * aspect * 1.5;
            vec4 sA = figFit(uDancer.x, p, fp, w, uDancerFitA, 0.0), sB = figFit(uDancer.y, p, fp, w, uDancerFitB, 0.0);
            vec4 fs = mix(sA, sB, uDancer.z);
            wcol += neon * (0.45 + 0.35 * uBeatPulse) * uWinCouple.y;                      // das Fenster leuchtet hinter dem Paar
            wcol = mix(wcol, fs.rgb * 0.45 + neon * 0.15, fs.a * uWinCouple.y);
        }
        float frame = 1.0 - pane;
        return vec4(wcol * pane + neon * frame * (0.25 * level + 0.7 * wrun), pane * 0.95 + frame * 0.5);
    }
    return vec4(0.0);
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    vec2 cc = uClock.xy;
    float cr = uClock.z;
    float strike = uStrikeT >= 0.0 ? uStrikeT : 1e3;
    float boltK = strike < 1.3 ? exp(-strike * 2.5) * (0.6 + 0.4 * step(0.4, hash12(vec2(floor(t * 45.0), 7.0)))) : 0.0;
    // ---- Kamera: Nahaufnahme aufs Zifferblatt, der Turm bebt mit dem Bass und beim Blitz
    vec2 uv = mix(vUv, cc + (vUv - vec2(0.5, 0.52)) / 3.2, uZoom);                        // Nahaufnahme: Zifferblatt in die Mitte
    float quake = (0.0025 * uBassS * uBassS + 0.004 * uBeatPulse * uBassS) * live + 0.012 * boltK;
    uv += vec2(hash12(vec2(floor(t * 50.0), 1.0)) - 0.5, hash12(vec2(floor(t * 50.0), 2.0)) - 0.5) * quake;
    uv += vec2(0.0012 * sin(t * 0.27), 0.0008 * cos(t * 0.19));
    vec3 col = scene(uv);
    vec3 plate = col;
    float lum = max(plate.r, max(plate.g, plate.b));
    float sat = lum - min(plate.r, min(plate.g, plate.b));
    float dark = smoothstep(0.3, 0.06, lum);
    // ---- Wolken (Bass): ziehen immer, leuchten von innen mit dem Bass; Wetterleuchten (Mitten) dahinter
    float sky = smoothstep(0.5, 0.75, uv.y) * dark;
    vec2 cp = vec2(uv.x * 2.2 + t * 0.012, uv.y * 3.0 - t * 0.004) + uSeed;
    float cloud = fbm(cp);
    float cloudHi = smoothstep(0.35, 0.75, cloud);
    float sheet = 0.0;
    if (uSheet.x < 0.9) {
        float flick = 0.7 + 0.3 * step(0.35, hash12(vec2(floor(t * 30.0), 3.0)));
        sheet = uSheet.z * exp(-uSheet.x * 5.0) * flick * smoothstep(0.7, 0.0, abs(uv.x - uSheet.y)) * smoothstep(0.4, 0.95, uv.y);
    }
    vec3 cloudCol = mix(vec3(0.35, 0.3, 0.6), vec3(0.9, 0.6, 1.0), uBassS);
    col += cloudCol * cloudHi * sky * (0.08 + 0.55 * uBassS * uBassS + 0.12 * uStorm) * (0.4 + 0.6 * live);
    col = mix(col, col * vec3(0.8, 0.85, 1.05), sky * uStorm * 0.4);                         // Gewitter: Himmel kälter
    col += vec3(0.75, 0.8, 1.0) * sky * (0.5 + 0.5 * cloud) * (sheet * 0.9 + boltK * 0.6);
    col += vec3(0.6, 0.65, 0.9) * dark * sheet * 0.12;                                     // Wetterleuchten hellt die Nacht auf
    // ---- Ferne Blitze hinter den Häusern (Gewitter, ab und zu auch in der ruhigen Nacht)
    float farK = 0.0;
    if (uFarBolt.x < 0.6) {
        farK = uFarBolt.w * exp(-uFarBolt.x * 7.0) * (0.55 + 0.45 * step(0.4, hash12(vec2(floor(t * 40.0), 11.0))));
        vec2 p = uv * vec2(aspect, 1.0);
        vec2 a = vec2(uFarBolt.y * aspect, 1.05);
        vec2 b = vec2((uFarBolt.y + (hash12(vec2(uFarBolt.z, 3.0)) - 0.5) * 0.12) * aspect, 0.55 + 0.06 * hash12(vec2(uFarBolt.z, 4.0)));
        float d = bolt(p, a, b, uFarBolt.z, 0.09, 10);
        float behind = smoothstep(0.6, 0.3, lum) * smoothstep(0.58, 0.66, uv.y);           // nur am Himmel, nicht vor dem Turm
        col += vec3(0.8, 0.85, 1.0) * (smoothstep(0.003, 0.0, d) * 1.6 + smoothstep(0.05, 0.0, d) * 0.4) * farK * behind;
        col += vec3(0.5, 0.55, 0.85) * sky * farK * 0.35 * smoothstep(0.6, 0.0, abs(uv.x - uFarBolt.y));
    }
    // ---- Regen (Höhen): schräge Streifen, Stille = kein Regen
    {
        vec2 rp = vec2(uv.x * aspect + uv.y * (0.18 + 0.3 * uStorm), uv.y);
        float colX = floor(rp.x * 160.0);
        float speed = 2.2 + 1.4 * hash12(vec2(colX, 5.0));
        float ry = fract(rp.y * 2.5 + t * speed + hash12(vec2(colX, 6.0)));
        float streak = smoothstep(0.0, 0.08, ry) * smoothstep(0.3, 0.09, ry) * step(0.55 - 0.25 * uStorm, hash12(vec2(colX, floor(rp.y * 2.5 + t * speed) + 9.0)));
        float rain = streak * smoothstep(0.5, 0.0, abs(fract(rp.x * 160.0) - 0.5));
        col += vec3(0.6, 0.7, 0.9) * rain * (0.05 + 0.28 * uHighS + 0.3 * uStorm) * max(live, uStorm);
    }
    // ---- Beleuchtete Stellen des Fotos: warmes Licht pulst mit dem Bass, Lauflicht in vier Zonen auf den Beat
    float lights = smoothstep(0.45, 0.7, lum) * smoothstep(0.08, 0.25, sat) * step(plate.b, plate.r + 0.05) * smoothstep(0.6, 0.3, uv.y);
    float zone = floor(clamp(uv.x, 0.0, 0.999) * 4.0);
    float act = activeZone();
    float run = (zone == act ? 1.0 : 0.0) * (1.0 - 0.7 * uStepPhase);
    col += plate / max(lum, 0.2) * lights * (0.1 + 0.4 * uBassS + 0.9 * run + 0.4 * uFlash) * live;
    col = mix(col, col * 0.6, lights * (1.0 - live) * 0.5);
    // ---- Acht Schaufenster in Neon (Tanzabend), darunter spiegeln die Pfützen sie
    float strikeK = strike < 10.0 ? 0.5 * exp(-strike * 0.4) : 0.0;
    vec4 win = windowsAt(uv, aspect, t, act, strikeK);
    col = col * (1.0 - 0.65 * win.a * live) + win.rgb * live;
    if (uv.y < uGround) {
        float depth = uGround - uv.y;
        float gmask = smoothstep(0.0, 0.015, depth);
        vec2 rp = vec2(uv.x + 0.0035 * sin(uv.y * 190.0 + t * 2.6) * (0.6 + uBassS) + 0.002 * sin(uv.x * 70.0 - t * 1.3), uGround + depth);
        vec4 wr = windowsAt(rp, aspect, t, act, strikeK);
        float fadeR = exp(-depth * 9.0);
        col += wr.rgb * gmask * fadeR * (0.35 + 0.35 * uBassS) * live;
        float wet = smoothstep(0.35, 0.75, lum) * gmask;                                      // nasse Lichter pulsen mit dem Bass
        col += plate * wet * (0.25 * uBassS + 0.3 * uBeatPulse * uBassS) * live;
        col += vec3(0.7, 0.8, 1.0) * gmask * fadeR * (boltK * 0.5 + farK * 0.25 + sheet * 0.15);
    }
    {                                                                                      // neuntes Fenster unter dem Turm: Bass + Beat
        float wx = uWindows.y + (uWindows.y - uWindows.x) / 7.0;
        float hw = uWindows.w * 0.5, hh = hw * aspect * 1.3;
        vec2 d = (uv - vec2(wx, uWindows.z)) / vec2(hw, hh);
        if (abs(d.x) < 1.0 && abs(d.y) < 1.0) {
            float pane = smoothstep(1.0, 0.92, abs(d.x)) * smoothstep(1.0, 0.92, abs(d.y));
            float level = 0.08 + 0.4 * uBassS + 0.35 * uBeatPulse + 0.5 * uFlash;
            vec3 wcol = mix(vec3(1.0, 0.8, 0.45), vec3(0.8, 0.85, 1.0), 0.5 * uBeatPulse) * level * (0.6 + 0.4 * (1.0 - (d.y * 0.5 + 0.5)));
            col = mix(col, col * 0.35 + wcol, pane * live * 0.95);
        }
    }
    // ---- Kabel vom Turm zur Laterne: hängt durch, Funken (Höhen), glüht nach dem Blitz
    {
        vec2 a = uCable.xy * vec2(aspect, 1.0), b = uCable.zw * vec2(aspect, 1.0);
        vec2 p = uv * vec2(aspect, 1.0);
        float dmin = 1e3, sPar = 0.0;
        vec2 prev = a;
        float sag = 0.28 * length(b - a);                                                   // tiefer Durchhang wie im Foto
        for (int i = 1; i <= 16; i++) {
            float f = float(i) / 16.0;
            vec2 q = mix(a, b, f) - vec2(0.0, sag * 4.0 * f * (1.0 - f));
            float dd = segDist(p, prev, q);
            if (dd < dmin) { dmin = dd; sPar = f; }
            prev = q;
        }
        float glow = uCableGlow * (0.7 + 0.3 * sin(t * 30.0 + sPar * 20.0));
        float core = smoothstep(0.005, 0.0, dmin);
        float halo = smoothstep(0.04, 0.0, dmin);
        col = mix(col, vec3(0.05, 0.04, 0.03), core * 0.6);                                   // das Kabel selbst, dunkel
        float crackle = uFinal * (0.4 + 0.6 * step(0.5, hash12(vec2(floor(t * 25.0), floor(sPar * 12.0)))));
        col += vec3(1.0, 0.75, 0.4) * core * (0.12 + 0.25 * live + 1.3 * glow + 0.8 * boltK + 1.1 * crackle);
        col += vec3(0.6, 0.8, 1.0) * halo * crackle * 0.35;
        col += vec3(1.0, 0.55, 0.2) * halo * (0.5 * glow + 0.3 * boltK);
        // Funken: hüpfen vom Kabel, mit den Höhen häufiger; Strom läuft beim Blitz zur Laterne
        for (int k = 0; k < 10; k++) {
            float fk = float(k);
            float slot = floor(t * 12.0 + fk * 3.7);
            float h1 = hash12(vec2(slot, fk + 41.0)), h2 = hash12(vec2(slot, fk + 43.0)), h3 = hash12(vec2(slot, fk + 47.0));
            float on = step(1.0 - (0.08 + 0.5 * uHighS * live + 0.6 * uCableGlow + 0.5 * uFinal), h3);
            float f = h1;
            vec2 q = mix(a, b, f) - vec2(0.0, sag * 4.0 * f * (1.0 - f));
            float age = fract(t * 12.0 + fk * 3.7) / 12.0;
            q += vec2(h2 - 0.5, 0.3) * age * 1.5 - vec2(0.0, 25.0 * age * age);
            col += vec3(1.0, 0.85, 0.5) * smoothstep(0.006, 0.0, length(p - q)) * on;
        }
        if (uCableGlow > 0.01) {
            float pulse = fract((1.0 - uCableGlow) * 6.0);
            col += vec3(0.7, 0.9, 1.0) * halo * smoothstep(0.08, 0.0, abs(sPar - pulse)) * uCableGlow * 1.2;
        }
    }
    // ---- Blitz (Drop / 22:04): gezackter Hauptstrang vom Himmel in die Turmspitze, zwei Äste, Flackern
    if (boltK > 0.0) {
        vec2 p = uv * vec2(aspect, 1.0);
        vec2 top = vec2(cc.x + (hash12(vec2(uBoltSeed, 1.0)) - 0.5) * 0.5, 1.08) * vec2(aspect, 1.0);
        vec2 hit = vec2(cc.x, cc.y + cr * 2.6) * vec2(aspect, 1.0);
        float d1 = bolt(p, top, hit, uBoltSeed, 0.15, 12);
        vec2 mid1 = mix(top, hit, 0.4) + vec2(0.07, -0.02);
        float d2 = bolt(p, mid1, mid1 + vec2(0.22 * (hash12(vec2(uBoltSeed, 2.0)) - 0.5) * 2.0, -0.25), uBoltSeed + 3.0, 0.12, 7);
        vec2 mid2 = mix(top, hit, 0.65) - vec2(0.05, 0.0);
        float d3 = bolt(p, mid2, mid2 + vec2(0.16 * (hash12(vec2(uBoltSeed, 4.0)) - 0.5) * 2.0, -0.18), uBoltSeed + 5.0, 0.1, 6);
        float dm = min(d1, min(d2 + 0.001, d3 + 0.0015));
        float core = smoothstep(0.0045, 0.0, dm);
        float glow = smoothstep(0.08, 0.0, dm) * 0.5 + smoothstep(0.25, 0.0, dm) * 0.15;
        col += vec3(0.85, 0.9, 1.0) * (core * 2.0 + glow) * boltK;
        col += vec3(0.6, 0.7, 1.0) * boltK * 0.35;                                             // der Himmel leuchtet
        float impact = smoothstep(0.1, 0.0, length(p - hit) - 0.01) * boltK;
        col += vec3(1.0) * impact * 1.5;
    }
    // ---- Zeitmaschine rast über den Platz, hinter ihr zwei Feuerspuren, die liegen bleiben und flackern
    if (uCar.w > 0.5) {
        float y = uCarPar.x, speed = max(uCarPar.y, 0.01);
        float hw = uCar.z * aspect * 0.5;
        if (uv.x > uCarPar.z - 0.02 && uv.x < uCar.x && abs(uv.y - y) < 0.06) {
            float ageX = (uCar.x - uv.x) / speed;
            if (ageX < uCarPar.w) {
                float k = 1.0 - ageX / uCarPar.w;
                float fade = k * k * (0.4 + 0.6 * exp(-ageX * 0.5));
                float flick = 0.5 + 0.5 * noise(vec2(uv.x * 90.0 - t * 12.0, t * 7.0));
                float fy = min(abs(uv.y - (y - 0.018)), abs(uv.y - (y + 0.004)));
                float line = smoothstep(0.012, 0.0, fy + 0.3 * fy * sin(uv.x * 120.0 + t * 20.0));
                float flames = smoothstep(0.55, 1.0, noise(vec2(uv.x * 60.0, (uv.y - y) * 60.0 - t * 10.0))) * smoothstep(0.05, 0.0, abs(uv.y - y + 0.004));
                vec3 fire = mix(vec3(1.0, 0.25, 0.03), vec3(1.0, 0.85, 0.35), flick);
                float scorch = smoothstep(0.035, 0.0, abs(uv.y - y + 0.007));
                col = mix(col, col * 0.25, scorch * k);                                        // verbrannter Boden
                col += fire * (line * 2.2 + flames * 1.2) * fade * (0.6 + 0.4 * flick);
                col += vec3(0.6, 0.2, 0.0) * scorch * fade * 0.5;
            }
        }
        vec2 p = uv * vec2(aspect, 1.0), pos = vec2(uCar.x * aspect, y - 0.005);
        vec4 s = figFit(uCar.y, p, pos, hw * 2.0, uCarFit, 0.0);
        s.rgb *= 0.85 + 0.3 * live + 0.5 * uFlash;
        col = mix(col, s.rgb, s.a);
        col += vec3(0.3, 0.6, 1.0) * s.a * 0.25 * (0.5 + 0.5 * sin(t * 25.0));                 // Zeitkreise flackern blau
        float under = smoothstep(0.03, 0.0, abs(uv.y - y + 0.01)) * step(abs(p.x - pos.x), hw);
        col += vec3(1.0, 0.5, 0.2) * under * 0.25 * step(uCarPar.z, uCar.x);
    }
    // ---- Tanzball: Girlanden mit bunten Lichtern über dem Platz blinken auf den Beat, das Paar tanzt unten
    if (uDance > 0.01) {
        vec2 p = uv * vec2(aspect, 1.0);
        for (int g = 0; g < 3; g++) {
            float fg = float(g);
            float y0 = 0.46 + fg * 0.07, x0 = (0.08 - fg * 0.02) * aspect, x1 = (0.92 + fg * 0.02) * aspect;
            float f = clamp((p.x - x0) / (x1 - x0), 0.0, 1.0);
            float yc = y0 - 0.1 * 4.0 * f * (1.0 - f) + 0.004 * sin(t * 1.3 + fg) * (1.0 + uBassS);
            float dLine = abs(p.y - yc) * step(x0, p.x) * step(p.x, x1) + 10.0 * (1.0 - step(x0, p.x) * step(p.x, x1));
            col += vec3(0.25, 0.2, 0.15) * smoothstep(0.0025, 0.0, dLine) * uDance;
            float n = 22.0 + fg * 4.0;
            float k = floor(f * n), fk = fract(f * n);
            vec2 bulb = vec2(x0 + (k + 0.5) / n * (x1 - x0), 0.0);
            float fb = (k + 0.5) / n;
            bulb.y = y0 - 0.1 * 4.0 * fb * (1.0 - fb) + 0.004 * sin(t * 1.3 + fg) * (1.0 + uBassS) - 0.012;
            float db = length(p - bulb);
            float phase = mod(k + fg, 4.0);
            float on = 0.35 + 0.65 * (phase == mod(uBeatStep, 4.0) ? 1.0 : 0.0) * (0.4 + 0.6 * uBeatPulse);
            on = mix(0.5 + 0.5 * sin(t * 2.0 + k), on, live);
            vec3 bc = hueShift(vec3(1.0, 0.3, 0.3), (k * 0.9 + fg * 2.1));
            col += bc * (smoothstep(0.009, 0.003, db) * 1.6 + smoothstep(0.05, 0.0, db) * 0.3) * on * uDance;
        }
        vec2 dp = vec2(0.5 * aspect, 0.07 + 0.006 * uBeatPulse);
        vec4 s = mix(figFit(uDancer.x, p, dp, 0.2, uDancerFitA, 0.0), figFit(uDancer.y, p, dp, 0.2, uDancerFitB, 0.0), uDancer.z);
        vec2 d = (p - dp) / 0.1;
        s.rgb *= 0.8 + 0.3 * live + 0.2 * uBeatPulse;
        s.rgb = mix(s.rgb, hueShift(s.rgb, uBeatStep * 0.4) , 0.25);
        col = mix(col, s.rgb, s.a * uDance);
        col += vec3(1.0, 0.6, 0.8) * smoothstep(1.4, 0.3, length(d - vec2(0.0, 0.6))) * (1.0 - s.a) * 0.08 * uDance * (0.5 + uBassS);
    }
    // ---- Zifferblatt: leuchtet mit dem Bass, Zeiger als Balken mit Glow, Sekundenzeiger tickt, 22:04 = weiß
    {
        vec2 d = (uv - cc) * vec2(aspect, 1.0) / cr;
        float r = length(d);
        float struck = strike < 10.0 ? 1.0 : 0.0;
        vec3 warm = mix(vec3(1.0, 0.8, 0.45), vec3(0.95, 0.97, 1.0), struck * 0.8);
        float face = smoothstep(1.0, 0.95, r);
        col += warm * face * (0.05 + 0.25 * uBassS * live + 0.6 * uFlash + 0.25 * struck * (0.5 + 0.5 * sin(t * 2.0)));
        float ring = smoothstep(0.05, 0.0, abs(r - 0.98)) ;
        col += warm * ring * (0.15 + 0.3 * uBeatPulse * live + 0.5 * struck);
        float ticks = 0.0;                                                                     // zwölf Stundenmarken
        {
            float ang = atan(d.x, d.y);
            float sector = abs(fract(ang / (2.0 * PI) * 12.0 + 0.5) - 0.5) * 2.0;
            ticks = smoothstep(0.1, 0.0, sector * r) * smoothstep(0.78, 0.82, r) * smoothstep(0.93, 0.9, r);
        }
        col += warm * ticks * (0.2 + 0.2 * uBassS);
        float dh = hand(d, uHands.x, 0.55, 0.075, 0.12);
        float dm = hand(d, uHands.y, 0.84, 0.05, 0.14);
        float ds = hand(d, uHands.z, 0.9, 0.018, 0.22);
        float hands = max(smoothstep(0.03, 0.0, dh), smoothstep(0.03, 0.0, dm));
        float secH = smoothstep(0.025, 0.0, ds);
        float hglow = max(smoothstep(0.35, 0.0, dh), smoothstep(0.35, 0.0, dm)) * 0.35 + smoothstep(0.2, 0.0, ds) * 0.2;
        vec3 handCol = mix(vec3(0.12, 0.08, 0.03), vec3(1.0), struck * 0.9 + uFlash);
        vec3 secCol = mix(vec3(1.0, 0.35, 0.15), vec3(1.0), struck * 0.5);
        float inFace = step(r, 1.02);
        col = mix(col, handCol + warm * 0.3 * uBassS * live, hands * inFace);
        col += warm * hglow * inFace * (0.3 + 0.6 * uBassS * live + 0.8 * struck + uBeatPulse * 0.4);
        col = mix(col, secCol * (1.2 + uBeatPulse), secH * inFace);
        col += warm * smoothstep(0.1, 0.0, r) * 0.6;                                           // Achse
        // kurz vor 22:04 wird das Blatt unruhig
        float near = smoothstep(0.85, 1.0, uClockT) * (1.0 - struck);
        col += vec3(0.6, 0.7, 1.0) * face * near * 0.25 * step(0.6, hash12(vec2(floor(t * 20.0), 8.0)));
    }
    // ---- Professor hängt am Zifferblatt (Pose je Beat, baumelt), beim Blitz in Weiß
    if (uDocPos.z > 0.01) {
        vec2 p = uv * vec2(aspect, 1.0);
        vec2 pos = vec2(uDocPos.x * aspect + uDoc.w * cr, uDocPos.y + 0.02 * cr * sin(t * 2.2));
        float sway = (0.05 * sin(t * 1.7) + 0.03 * uBeatPulse) * cr;
        p.x += sway * (pos.y - p.y) / cr;                                                      // baumelt um den Griff
        vec4 s = mix(figFit(uDoc.x, p, pos, cr * 1.6, uDocFitA, 1.0), figFit(uDoc.y, p, pos, cr * 1.6, uDocFitB, 1.0), uDoc.z);
        s.rgb *= 0.8 + 0.3 * live + 0.8 * boltK;
        s.rgb = mix(s.rgb, vec3(1.0), uFlash * 0.6);
        col = mix(col, s.rgb, s.a * uDocPos.z);
        col += vec3(1.0, 0.8, 0.4) * s.a * uDocPos.z * uBeatPulse * 0.15;
    }
    // ---- Weißblitz, Vignette, Stille
    col += vec3(1.0, 1.0, 1.0) * uFlash * uFlash * 0.9;
    col *= 0.78 + 0.22 * live;
    col *= 1.0 - 0.2 * uFinal * smoothstep(0.25, 0.75, length(vUv - 0.5));                   // Countdown: der Rand dunkelt
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.12);
    fragColor = vec4(col, 1.0);
}
