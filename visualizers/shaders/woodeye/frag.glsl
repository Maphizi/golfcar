#version 140
// Das Auge des Waldes: Baum-Foto (uSceneTex) mit riesigem Auge aus dem Augen-Atlas (uEyeTex 8x3 à 224) und acht
// Fröschen aus dem Figuren-Atlas (uFigTex 8x4 à 192; Reihen: sitzend, Kehlsack, Sprung, Fuchs/Eule).
// Bass: Pupille (Linse), Rinde pumpt, Kamera atmet. Beat: Myzel-Lauflicht (uStep/uPattern), Mond pulst.
// Spektrum: Frösche = Bänder (uBands0/1, Kehlsack und Sprung uFrogN.w). Mitten: Kronendach, Pollen. Höhen: Glühwürmchen.
// Drop: uFlash, Sporen (uSporeT), Auge brennt (Zellen über uEyeA/B). Figuren uFig (Fuchs) / uOwl (Eule), uKaleido, uZoom.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uEyeTex, uFigTex;
uniform vec2 uSceneSize, uEyeSize, uFigSize;
uniform vec3 uEyePos;                              // x, y, Breite (Bildanteile)
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uStep, uStepPhase, uPattern, uFlash, uSporeT;
uniform float uZoom, uKaleido, uChorusT, uBlink, uEyeA, uEyeB, uEyeMix, uHueT;
uniform vec4 uFig, uOwl, uBands0, uBands1;
uniform vec4 uFrog0, uFrog1, uFrog2, uFrog3, uFrog4, uFrog5, uFrog6, uFrog7;   // x, y, Größe, Sprungphase (-1 = keiner)
uniform vec4 uFrogPh0, uFrogPh1, uFrogPh2, uFrogPh3, uFrogPh4, uFrogPh5, uFrogPh6, uFrogPh7;   // Phase, Fortschritt/Zeit, Schwimmer
uniform float uHueBurst;
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
// Augenzelle idx (8x3 à 224), d in -1..1
vec4 eyeCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 224.0, (2.0 - ri) * 224.0);
    return bilin(uEyeTex, lo + (d * 0.5 + 0.5) * 224.0, uEyeSize, lo, lo + 223.0);
}
// Figurenzelle idx (8x4 à 192), d in -1..1
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (3.0 - ri) * 192.0);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
}
vec4 frogAt(int i) { return i == 0 ? uFrog0 : (i == 1 ? uFrog1 : (i == 2 ? uFrog2 : (i == 3 ? uFrog3 : (i == 4 ? uFrog4 : (i == 5 ? uFrog5 : (i == 6 ? uFrog6 : uFrog7)))))); }
float bandAt(int i) { return i < 4 ? uBands0[i] : uBands1[i - 4]; }
// aktive Lauflicht-Zone (0..3) je Muster: 0 links->rechts, 1 Pendel, 2 von der Mitte, 3 Zufall
float activeZone() {
    float s = uStep;
    if (uPattern < 0.5) return s;
    if (uPattern < 1.5) return s < 2.0 ? s : (s == 2.0 ? 2.0 : 1.0);
    if (uPattern < 2.5) return s == 0.0 ? 1.0 : (s == 1.0 ? 2.0 : (s == 2.0 ? 0.0 : 3.0));
    return floor(hash12(vec2(s, uSeed)) * 4.0);
}

// Frosch i: sitzend <-> Kehlsack je Band, Sprung (Zelle 16+i), Tauchspiel (uFrogPh: Phase 1 springt ins Wasser,
// 2 unter Wasser als wabernder Schatten, 3 taucht wieder auf), Spiegelung im Wasser. Position = Fußpunkt.
vec4 frogPhAt(int i) { return i == 0 ? uFrogPh0 : (i == 1 ? uFrogPh1 : (i == 2 ? uFrogPh2 : (i == 3 ? uFrogPh3 : (i == 4 ? uFrogPh4 : (i == 5 ? uFrogPh5 : (i == 6 ? uFrogPh6 : uFrogPh7)))))); }
vec4 frogSprite(float cellA, float cellB, float infl, vec2 l, float hop) {
    if (abs(l.x) >= 1.0 || abs(l.y) >= 1.0) return vec4(0.0);
    return hop >= 0.0 ? figCell(cellA, l) : mix(figCell(cellA, l), figCell(cellB, l), infl);
}
vec3 frog(vec3 col, vec2 uv, float aspect, int i, bool mirror) {
    vec4 fr = frogAt(i);
    vec4 ph = frogPhAt(i);
    float band = bandAt(i);
    float fi = float(i);
    float phase = ph.x, pt = ph.y, swim = ph.z;
    float infl = smoothstep(0.12, 0.75, band);
    float hop = fr.w;
    float hw = fr.z * aspect * 0.5 * (1.0 + 0.1 * infl) * (0.9 + 0.1 * uLive);
    float H = hw * 2.0;                                                      // Spritehöhe (Zelle quadratisch)
    float wl = fr.y - (swim > 0.5 ? 0.0 : 0.012);                            // Wasserlinie
    float ang = 0.0, yOff = swim > 0.5 ? -0.35 * H + 0.01 * sin(iTime * 1.3 + fi) : 0.0;
    float cellA = fi, cellB = 8.0 + fi;
    bool under = phase == 2.0;
    float splash = 0.0, hueK = 0.0, alpha = 1.0;
    if (phase == 1.0) {                                                      // springt ins Wasser
        cellA = 16.0 + fi; hop = 0.5;
        yOff += H * (0.6 * sin(pt * PI) - 1.3 * pt * pt);
        ang = (fi < 4.0 ? 1.0 : -1.0) * 0.6 * pt;
        splash = smoothstep(0.55, 0.8, pt) * (1.0 - smoothstep(0.8, 1.0, pt) * 0.5);
        hueK = pt;
    } else if (phase == 3.0) {                                               // taucht auf
        yOff += -1.25 * H * (1.0 - pt) * (1.0 - pt) + 0.08 * H * sin(pt * PI);
        splash = smoothstep(0.0, 0.25, pt) * smoothstep(0.7, 0.35, pt);
        infl = max(infl, 0.6 * sin(pt * PI));
        hueK = 1.0 - pt;
    } else if (hop >= 0.0) {
        cellA = 16.0 + fi;
        yOff += fr.z * 1.1 * sin(hop * PI);
        ang = (fi < 4.0 ? 1.0 : -1.0) * 0.4 * sin(hop * PI);
    }
    if (under) {                                                             // Schatten unter der Oberfläche
        float wob = 0.5 + 0.5 * sin(pt * 1.7 + fi);
        yOff = -0.55 * H - 0.08 * H * wob;
        vec2 wuv = uv + vec2(0.006 * sin(uv.y * 70.0 + iTime * 3.0 + fi), 0.0);
        if (mirror || wuv.y > wl) return col;
        vec2 d = (wuv - vec2(fr.x + 0.01 * sin(pt * 0.9 + fi), fr.y + yOff)) * vec2(aspect, 1.0) / hw;
        vec2 l = vec2(d.x, d.y - 1.0 + 0.02);
        vec4 s = frogSprite(fi, 8.0 + fi, infl, l, -1.0);
        vec3 tint = hueShift(vec3(0.3, 0.9, 0.8), uHueT * 3.0 + fi) * (0.7 + 0.5 * band);
        s.rgb = mix(s.rgb, tint, 0.6) * 1.4;
        // weicher Schein des Schattens unter der Oberfläche
        float gl = smoothstep(0.08, 0.0, length((wuv - vec2(fr.x, fr.y + yOff + 0.5 * H)) * vec2(aspect, 1.0)));
        col += tint * gl * 0.25 * (0.6 + 0.4 * sin(pt * 2.0 + fi));
        // Luftblasen steigen auf
        for (int k = 0; k < 4; k++) {
            float hk = hash12(vec2(float(k), fi + 50.0));
            float age = mod(pt * 0.7 + hk * 3.0, 3.0);
            vec2 bp = vec2(fr.x + (hk - 0.5) * 0.03, fr.y - 0.6 * H + age * 0.025);
            if (bp.y < wl) col += vec3(0.6, 0.9, 1.0) * smoothstep(0.004, 0.0, length((uv - bp) * vec2(aspect, 1.0))) * 0.6;
        }
        return mix(col, s.rgb, s.a * 0.65);
    }
    // oberhalb der Wasserlinie das Tier, unterhalb die Spiegelung
    if (!mirror && uv.y < wl) return col;
    if (mirror && uv.y >= wl) return col;
    vec2 l;
    if (mirror) {
        vec2 wuv = uv + vec2(0.004 * sin(uv.y * 90.0 + iTime * 2.0 + fi), 0.0);
        vec2 d = (wuv - vec2(fr.x, wl)) * vec2(aspect, 1.0) / hw;
        l = vec2(d.x, -d.y - 1.0 - (fr.y + yOff - wl) / hw);
    } else {
        vec2 d = (uv - vec2(fr.x, fr.y + yOff)) * vec2(aspect, 1.0) / hw;
        l = vec2(d.x, d.y - 1.0 + 0.02);
    }
    l = rot(ang) * (l + vec2(0.0, 0.5)) - vec2(0.0, 0.5);
    vec4 s = frogSprite(cellA, cellB, infl, l, hop);
    s.rgb *= 0.55 + 0.45 * uLive + 0.5 * band;                            // schläft dunkler, leuchtet mit dem Band
    s.rgb = hueShift(s.rgb, uKaleido * (uHueT * 6.0 + fi) + hueK * 1.5 * sin(uHueT * 20.0 + fi) + uHueBurst * 2.0 * sin(uHueT * 30.0 + fi * 2.0));
    if (mirror) { s.rgb *= 0.35; s.a *= 0.55; }
    col = mix(col, s.rgb, s.a);
    // Psychedelische Nachbilder beim Abtauchen und Auftauchen
    if ((phase == 1.0 || phase == 3.0) && !mirror) {
        for (int k = 1; k <= 3; k++) {
            float pk = clamp(pt - 0.09 * float(k), 0.0, 1.0);
            float yk = swim > 0.5 ? -0.35 * H : 0.0;
            if (phase == 1.0) yk += H * (0.6 * sin(pk * PI) - 1.3 * pk * pk);
            else yk += -1.25 * H * (1.0 - pk) * (1.0 - pk) + 0.08 * H * sin(pk * PI);
            vec2 d = (uv - vec2(fr.x, fr.y + yk)) * vec2(aspect, 1.0) / hw;
            vec2 lk = rot(ang * pk / max(pt, 0.01)) * (vec2(d.x, d.y - 1.0 + 0.02) + vec2(0.0, 0.5)) - vec2(0.0, 0.5);
            vec4 g = frogSprite(cellA, cellB, infl, lk, hop);
            vec3 gc = hueShift(vec3(0.5, 1.0, 0.8), float(k) * 1.4 + uHueT * 10.0 + fi);
            col = mix(col, mix(g.rgb, gc, 0.6), g.a * 0.35 * (1.0 - float(k) * 0.22) * (1.0 - s.a));
        }
    }
    // Spritzer und Ringe an der Wasserlinie
    if (splash > 0.0 && !mirror) {
        vec2 c = vec2(fr.x, wl);
        float rr = length((uv - c) * vec2(aspect, 2.5));
        float ring = exp(-pow((rr - 0.02 - 0.06 * (phase == 1.0 ? pt - 0.55 : pt)) * 60.0, 2.0));
        col += vec3(0.7, 0.9, 1.0) * ring * splash * 0.8 * smoothstep(0.0, 0.01, wl - uv.y + 0.015);
        for (int k = 0; k < 8; k++) {
            float hk = hash12(vec2(float(k), fi + 70.0));
            float a = pt * 1.4 - 0.1;
            vec2 dp = c + vec2((hk - 0.5) * 0.12 * a, 0.09 * a - 0.12 * a * a + hk * 0.01);
            col += vec3(0.8, 0.95, 1.0) * smoothstep(0.004, 0.0, length((uv - dp) * vec2(aspect, 1.0))) * splash;
        }
    }
    return col;
}

vec3 figure(vec3 col, vec2 uv, float aspect, float cellA, float cellB, float mixv, vec2 pos, float sz, float flip) {
    vec2 d = (uv - pos) * vec2(aspect, 1.0) / (sz * aspect * 0.5);
    d.x *= flip;
    d.y = d.y - 1.0 + 0.02;
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return col;
    vec4 s = mix(figCell(cellA, d), figCell(cellB, d), mixv);
    s.rgb *= 0.7 + 0.3 * uLive + 0.3 * uBassS;
    return mix(col, s.rgb, s.a);
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    vec2 eye = uEyePos.xy;
    // Kamera: Nahaufnahme ins Auge, Atmen mit dem Bass
    vec2 uv = mix(vUv, eye + (vUv - eye) / 2.6, uZoom);
    uv = eye + (uv - eye) * (1.0 - 0.025 * uBassS);
    uv += vec2(0.002 * sin(t * 0.19), 0.0015 * cos(t * 0.23));
    // Kronendach wiegt sich mit den Mitten (oberer Bildteil), Nebel treibt
    vec2 suv = uv;
    float canopy = smoothstep(0.5, 0.85, uv.y);
    suv.x += canopy * (0.004 * sin(uv.y * 18.0 + t * 1.3) + 0.006 * sin(uv.x * 9.0 - t * 0.8)) * (0.3 + 1.5 * uMidS);
    suv.y += canopy * 0.003 * sin(uv.x * 14.0 + t * 1.1) * uMidS;
    vec3 col = scene(suv);
    vec3 plate = col;
    // ---- Myzel: türkise Stellen im Foto leuchten, Lauflicht 1-2-3-4 je Zone, Drop = Farbwelle
    float teal = clamp((min(plate.g, plate.b) - plate.r * 1.4 - 0.05) * 5.0, 0.0, 1.0) * smoothstep(0.62, 0.45, uv.y);
    float zone = floor(clamp((uv.x - 0.04) / 0.92, 0.0, 0.999) * 4.0);
    float act = activeZone();
    float pulse = (zone == act ? 1.0 : 0.0) * (1.0 - 0.8 * uStepPhase) + 0.35 * uBeatPulse;
    float base = 0.25 + 0.45 * uLive + 0.4 * uBassS;
    vec3 glowCol = vec3(0.2, 1.0, 0.8);
    if (uFlash > 0.0) {
        float wave = exp(-pow((uv.x - (1.0 - uFlash) * 1.6 + 0.3) * 6.0, 2.0));
        glowCol = mix(glowCol, hueShift(glowCol, uv.x * 4.0 + t), wave * uFlash);
        pulse += wave * uFlash * 1.5;
    }
    glowCol = hueShift(glowCol, uKaleido * (uHueT * 4.0 + uv.x * 3.0));
    col += glowCol * teal * (base + 3.0 * pulse * uLive);
    // Bodenlicht der aktiven Zone (weicher Schein auf Wurzeln und Moos)
    float zc = (act + 0.5) * 0.23 + 0.04;
    float ground = exp(-pow((uv.x - zc) * 3.5, 2.0)) * smoothstep(0.55, 0.3, uv.y) * smoothstep(0.08, 0.25, uv.y);
    col += glowCol * ground * (0.12 + 0.4 * (1.0 - uStepPhase)) * uLive * (0.6 + 0.6 * uBassS);
    // Drop: der ganze Boden leuchtet kurz auf
    col += glowCol * uFlash * 0.25 * smoothstep(0.6, 0.2, uv.y) * (0.5 + 0.5 * fbm(uv * 6.0 + t * 0.5));
    // ---- Mond pulst mit dem Beat
    vec2 moon = vec2(0.706, 0.91);
    float md = length((uv - moon) * vec2(aspect, 1.0));
    col += vec3(0.8, 0.85, 1.0) * exp(-md * 25.0) * (0.15 * uBeatPulse + 0.05 * uBassS);
    // ---- Frösche: Spiegelungen zuerst, dann die Tiere
    for (int i = 0; i < 8; i++) col = frog(col, uv, aspect, i, true);
    for (int i = 0; i < 8; i++) col = frog(col, uv, aspect, i, false);
    // ---- Figuren: Fuchs tanzt am linken Wurzelstock, Eule kreist um den Baum
    float figMode = uFig.x;
    if (figMode == 1.0 || figMode == 3.0) {
        vec2 fp = vec2(0.215, 0.40);
        fp.y += 0.012 * uBassS + 0.006 * sin(t * 6.0) * uBeatPulse;
        col = figure(col, uv, aspect, uFig.y, uFig.z, uFig.w, fp, 0.14 * (1.0 + 0.06 * uBassS), 1.0);
    }
    if (figMode == 2.0 || figMode == 3.0) {
        float a = uOwl.x * 2.0 * PI;
        vec2 op = vec2(0.5 + 0.34 * cos(a), 0.66 + 0.1 * sin(a) + 0.02 * sin(t * 2.0));
        float depth = 0.5 + 0.5 * sin(a);                                      // vor dem Baum = größer
        col = figure(col, uv, aspect, uOwl.y, uOwl.z, uOwl.w, op, 0.07 + 0.07 * depth, cos(a) > 0.0 ? 1.0 : -1.0);
    }
    // ---- Auge: Öffnen über Reihe 0, Blick/Farbe/Feuer über Zellen A/B, Pupille als Linse mit dem Bass
    {
        float sz = uEyePos.z * aspect * (1.0 + 0.05 * uBassS + 0.03 * uBeatPulse);   // Breite, isotrop
        vec2 d = (uv - eye) * vec2(aspect, 1.0) / (sz * 0.5);
        if (abs(d.x) < 1.0 && abs(d.y) < 1.0) {
            // Linse: Pupille weitet sich (Mitte vergrößert), Kaleidoskop dreht die Iris
            float r = length(d - vec2(0.0, 0.02));
            float lens = (0.25 + 0.45 * uBassS) * exp(-r * r * 9.0);
            vec2 dl = d * (1.0 - lens);
            dl = rot(uKaleido * (sin(t * 1.5) * 0.5 + uHueT * 2.0) * smoothstep(0.45, 0.0, r)) * dl;
            vec4 s;
            if (uBlink < 0.999) {
                float fr = uBlink * 7.0;
                float fa = floor(fr), fb = min(fa + 1.0, 7.0);
                s = mix(eyeCell(fa, dl), eyeCell(fb, dl), fr - fa);
                if (uBlink > 0.9) {                                            // fast offen: Blickzelle einblenden
                    vec4 look = mix(eyeCell(uEyeA, dl), eyeCell(uEyeB, dl), uEyeMix);
                    s = mix(s, look, (uBlink - 0.9) * 10.0);
                }
            } else {
                s = mix(eyeCell(uEyeA, dl), eyeCell(uEyeB, dl), uEyeMix);
            }
            // Iris glüht mit dem Bass, brennt beim Drop
            float irisMask = smoothstep(0.42, 0.25, r) * uBlink;
            s.rgb *= 1.0 + irisMask * (0.3 * uBassS + 0.8 * uFlash);
            s.rgb = hueShift(s.rgb, uKaleido * irisMask * uHueT * 8.0);
            // Rinde um das Auge: Mondlicht, Drop-Schein
            s.rgb *= 0.85 + 0.15 * uLive;
            col = mix(col, s.rgb, s.a);
            col += vec3(1.0, 0.6, 0.2) * uFlash * irisMask * 0.5;
        }
        // Schein des Auges auf die Rinde
        float ed = length((uv - eye) * vec2(aspect, 1.0)) / (sz * 0.5);
        col += vec3(0.9, 0.7, 0.4) * exp(-ed * ed * 3.0) * uBlink * (0.05 + 0.1 * uBassS + 0.6 * uFlash) * smoothstep(0.5, 0.8, ed);
    }
    // ---- Sporenwolke beim Drop: leuchtende Partikel steigen vom Wurzelstock auf
    if (uSporeT >= 0.0) {
        for (int i = 0; i < 40; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 11.0)), h2 = hash12(vec2(fi, 13.0)), h3 = hash12(vec2(fi, 17.0));
            float age = uSporeT - h1 * 0.5;
            if (age < 0.0) continue;
            vec2 p = vec2(0.5 + (h2 - 0.5) * 0.25, 0.32) + vec2((h2 - 0.5) * 0.9 * age, age * (0.12 + 0.18 * h3) - 0.02 * age * age);
            p.x += 0.02 * sin(age * 3.0 + fi);
            float g = smoothstep(0.012 + 0.004 * h3, 0.0, length((uv - p) * vec2(aspect, 1.0))) * (1.0 - age / 4.0);
            col += hueShift(vec3(0.4, 1.0, 0.7), h3 * 1.5) * g * 1.2;
        }
    }
    // ---- Pollen steigen mit den Mitten, Glühwürmchen mit den Höhen
    for (int i = 0; i < 18; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 21.0)), h2 = hash12(vec2(fi, 23.0));
        vec2 p = vec2(0.1 + h1 * 0.8 + 0.03 * sin(t * 0.5 + fi), mod(h2 + t * (0.01 + 0.03 * uMidS), 1.0) * 0.5 + 0.2);
        float g = smoothstep(0.004, 0.0, length((uv - p) * vec2(aspect, 1.0)));
        col += vec3(0.9, 0.95, 0.6) * g * (0.1 + 0.6 * uMidS);
    }
    for (int i = 0; i < 16; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 33.0));
        vec2 c = vec2(h1 + 0.03 * sin(t * (0.3 + h2) + fi), 0.25 + h2 * 0.45 + 0.03 * sin(t * 0.7 + fi * 2.0));
        float g = smoothstep(0.006, 0.0, length((uv - c) * vec2(aspect, 1.0))) * (0.3 + 0.7 * pow(0.5 + 0.5 * sin(t * (2.0 + h1 * 3.0) + fi * 5.0), 2.0));
        col += vec3(1.0, 0.95, 0.5) * g * (0.3 + 1.0 * uHighS);
    }
    // Tautropfen funkeln: helle Bildstellen glitzern mit den Höhen
    float lum = dot(plate, vec3(0.33));
    col += plate * smoothstep(0.55, 0.9, lum) * uHighS * 0.5 * (0.5 + 0.5 * sin(t * 9.0 + uv.x * 300.0 + uv.y * 200.0));
    // ---- Kaleidoskop: Farben kreisen durchs ganze Bild
    col = mix(col, hueShift(col, uHueT * 5.0 + uv.y * 2.0), uKaleido * 0.6);
    // Stille: kälter und dunkler
    col *= 0.7 + 0.3 * uLive;
    col = mix(col, col * vec3(0.8, 0.9, 1.1), 1.0 - uLive);
    // Abschluss
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
