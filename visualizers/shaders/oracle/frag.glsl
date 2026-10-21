#version 140
// Das Orakel: Serverhallen-Foto (uSceneTex) mit Hologramm-Maske (uMaskTex 8x3 à 192) im Rahmen uFrame (x, y, Breite),
// acht Neontafeln (uPanels: x0, x7, y, Breite) zeigen die Glyphen (uFigTex Reihe 2) als Spektrum (uBands/uPeaks).
// Bass = Maske atmet/flackert, Serverlichter glühen; Beat = Lauflicht durch die Schränke (uStep/uPattern); Mitten =
// Datenregen; Höhen = Funken; Drop = uFlash/uBurstT; Stille = uAwake. Figuren: Samurai (uSam), Katze (uCat), Glitch uGlitch.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uMaskTex, uFigTex;
uniform vec2 uSceneSize, uMaskSize, uFigSize;
uniform vec3 uFrame;
uniform vec4 uPanels, uFig, uSam, uCat, uBands0, uBands1, uPeaks0, uPeaks1;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uStep, uStepPhase, uPattern, uFlash;
uniform float uBurstT, uAwake, uMaskA, uMaskB, uMaskMix, uSpeakT, uGlitch, uZoom;
const float PI = 3.14159265;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
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
vec4 maskCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uMaskTex, lo + (d * 0.5 + 0.5) * 192.0, uMaskSize, lo, lo + 191.0);
}
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
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

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    vec2 fr = uFrame.xy;
    vec2 uv = mix(vUv, fr + (vUv - fr) / 2.4, uZoom);
    uv += vec2(0.0015 * sin(t * 0.27), 0.001 * cos(t * 0.19));
    // Glitch-Modus: Bild zerfällt in Blöcke, Zeilen springen
    if (uGlitch > 0.01) {
        float row = floor(uv.y * 40.0 + floor(t * 8.0));
        float shift = (hash12(vec2(row, floor(t * 6.0))) - 0.5) * 0.08 * step(0.7, hash12(vec2(row, floor(t * 2.0) + 3.0)));
        uv.x += shift * uGlitch;
        vec2 blk = floor(uv * vec2(12.0, 8.0));
        if (hash12(blk + floor(t * 4.0)) > 0.92) uv = (blk + 0.5) / vec2(12.0, 8.0) + (uv - (blk + 0.5) / vec2(12.0, 8.0)) * 0.2;
    }
    vec3 col;
    if (uGlitch > 0.01) {                                                                 // Farbkanäle laufen auseinander
        float sep = 0.006 * uGlitch * (1.0 + 2.0 * uBeatPulse);
        col = vec3(scene(uv + vec2(sep, 0.0)).r, scene(uv).g, scene(uv - vec2(sep, 0.0)).b);
    } else {
        col = scene(uv);
    }
    vec3 plate = col;
    float lum = max(plate.r, max(plate.g, plate.b));
    float sat = lum - min(plate.r, min(plate.g, plate.b));
    // ---- Serverlichter: Lauflicht durch vier Zonen (links außen, links innen, rechts innen, rechts außen) auf den Beat
    float lights = smoothstep(0.3, 0.6, lum) * smoothstep(0.1, 0.3, sat) * step(0.0, abs(uv.x - 0.5) - 0.3);
    float zone = uv.x < 0.5 ? (uv.x < 0.1 ? 0.0 : 1.0) : (uv.x > 0.9 ? 3.0 : 2.0);
    float act = activeZone();
    float run = (zone == act ? 1.0 : 0.0) * (1.0 - 0.7 * uStepPhase);
    vec3 lightCol = hueShift(plate / max(lum, 0.2), uBeatStep * 0.3);
    col += lightCol * lights * (0.15 + 0.5 * uBassS + 1.4 * run + 0.5 * uFlash) * live;
    col = mix(col, col * 0.5, lights * (1.0 - live) * 0.5);
    // ---- Datenregen im Hintergrund (Mitten): fallende Zeichenketten in den dunklen Flächen
    float dark = smoothstep(0.25, 0.05, lum);
    float colX = floor(uv.x * 220.0);
    vec2 rc = vec2(colX, uv.y * 110.0 + t * (3.0 + 8.0 * uMidS) * (0.5 + hash12(vec2(colX, 1.0))));
    float rain = step(0.9, hash12(floor(rc))) * step(0.75, hash12(vec2(colX, 2.0))) * (0.3 + 0.7 * fract(rc.y * 0.1));
    col += vec3(0.2, 0.9, 0.7) * rain * dark * (0.1 + 0.45 * uMidS) * live;
    // ---- Neontafeln: acht Glyphen als Spektrum, Band = Helligkeit, Spitze = Blitz, Farbe aus dem Bogen
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float px = mix(uPanels.x, uPanels.y, fi / 7.0);
        float band = bandAt(i), pk = peakAt(i);
        float hw = uPanels.w * aspect * 0.5;
        vec2 d = (uv - vec2(px, uPanels.z)) * vec2(aspect, 1.0) / hw;
        d.y *= 0.62;                                                                   // Tafel ist hoch, Zelle quadratisch
        vec4 g = figCell(16.0 + fi, d);
        float level = 0.08 + 0.9 * band + 0.4 * uBeatPulse * step(0.6, band);
        float flick = 1.0 - 0.3 * step(0.97, hash12(vec2(fi, floor(t * 20.0)))) * step(0.7, band);
        col = mix(col, g.rgb * (0.3 + 1.2 * level) * flick, g.a * (0.3 + 0.7 * live));
        col += g.rgb * g.a * level * 0.5;
        float glow = smoothstep(1.6, 0.4, length(d)) * (1.0 - g.a);
        col += g.rgb * glow * level * 0.25 * live;
        float pkLine = smoothstep(0.03, 0.0, abs(d.y / 0.62 + 1.0 - 2.0 * pk)) * step(abs(d.x), 1.0) * step(0.05, pk);
        col += vec3(1.0) * pkLine * 0.5 * live;
    }
    // ---- Figuren: Samurai tanzt links vor den Schränken, Katze streift am Boden
    float figMode = uFig.x;
    if (figMode == 1.0 || figMode == 3.0) {
        vec2 sp = vec2(0.17, 0.12);
        sp.y += 0.01 * uBassS + 0.008 * sin(t * 8.0) * uBeatPulse;
        float hw = 0.16 * aspect * 0.5;
        vec2 d = (uv - sp) * vec2(aspect, 1.0) / hw;
        d.y = d.y - 1.0 + 0.04;
        vec4 s = mix(figCell(uSam.x, d), figCell(uSam.y, d), uSam.z);
        s.rgb *= 0.75 + 0.3 * live + 0.3 * uBassS;
        col = mix(col, s.rgb, s.a);
        col += vec3(0.9, 0.2, 0.3) * s.a * uBeatPulse * 0.3;
    }
    if (figMode == 2.0 || figMode == 3.0) {
        vec2 cp = vec2(uCat.x, 0.1 + 0.01 * sin(t * 3.0));
        float hw = 0.11 * aspect * 0.5;
        vec2 d = (uv - cp) * vec2(aspect, 1.0) / hw;
        d.x *= uCat.w;
        d.y = d.y - 1.0 + 0.04;
        vec4 s = mix(figCell(uCat.y, d), figCell(uCat.z, d), 0.6);
        s.rgb *= 0.8 + 0.3 * live;
        col = mix(col, s.rgb, s.a);
        col += vec3(0.6, 0.2, 1.0) * s.a * 0.3 * (0.5 + 0.5 * sin(t * 6.0));
    }
    // ---- Maske im Projektionsrahmen: Hologramm (Scanlines, Flackern), atmet mit dem Bass, Ausdruck überblendet
    {
        float w = uFrame.z * aspect * 0.5 * (1.0 + 0.04 * uBassS * live + 0.02 * uBeatPulse);
        vec2 d = (uv - fr) * vec2(aspect, 1.0) / w;
        d.y += 0.02 * sin(t * 1.1) * uAwake;
        if (uGlitch > 0.01 || uBurstT >= 0.0) {
            float g = uGlitch + (uBurstT >= 0.0 ? exp(-uBurstT * 2.0) : 0.0);
            d.x += (hash12(vec2(floor(d.y * 20.0), floor(t * 10.0))) - 0.5) * 0.15 * g * step(0.6, hash12(vec2(floor(d.y * 20.0), floor(t * 5.0))));
        }
        vec4 m = mix(maskCell(uMaskA, d), maskCell(uMaskB, d), uMaskMix);
        float scan = 0.85 + 0.15 * sin(uv.y * 700.0 + t * 30.0);
        float flick = 1.0 - 0.15 * step(0.93, hash12(vec2(floor(t * 24.0), 1.0))) - 0.3 * uBassS * step(0.9, hash12(vec2(floor(t * 40.0), 2.0)));
        vec3 mc = m.rgb * scan * flick;
        if (uSpeakT >= 0.0) mc += m.rgb * 0.3 * abs(sin(uSpeakT * 14.0));
        float vis = m.a * (0.35 + 0.65 * uAwake) * (0.6 + 0.4 * live);
        col = mix(col, mc, vis * 0.9);
        col += mc * vis * (0.25 + 0.4 * uBassS + 0.6 * uFlash);
        // Lichtkegel des Projektors pulst
        float cone = smoothstep(0.0, 1.0, 1.0 - abs(d.x) / (0.3 + 1.2 * (1.0 - (d.y * 0.5 + 0.5)))) * smoothstep(1.2, -1.0, d.y) * step(-1.3, d.y);
        col += vec3(0.2, 0.6, 1.0) * cone * 0.05 * (0.5 + uBassS) * uAwake;
    }
    // ---- Drop: Datenexplosion aus dem Rahmen
    if (uBurstT >= 0.0) {
        for (int k = 0; k < 40; k++) {
            float fk = float(k);
            float h1 = hash12(vec2(fk, 11.0)), h2 = hash12(vec2(fk, 13.0)), h3 = hash12(vec2(fk, 17.0));
            vec2 dir = vec2(cos(h1 * 6.28), sin(h1 * 6.28));
            vec2 p = fr + dir * uBurstT * (0.15 + 0.35 * h2) / vec2(aspect, 1.0);
            vec2 dd = (uv - p) * vec2(aspect, 1.0);
            float blk = step(max(abs(dd.x), abs(dd.y)), 0.006 + 0.008 * h3);
            col = mix(col, hueShift(vec3(0.3, 0.9, 1.0), h3 * 5.0), blk * exp(-uBurstT * 0.9));
        }
    }
    // ---- Funken an den Kabeln (Höhen)
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 33.0));
        vec2 c = vec2(h1 < 0.5 ? 0.05 + h1 * 0.3 : 0.65 + (h1 - 0.5) * 0.6, 0.05 + h2 * 0.5);
        float on = step(0.85 - 0.4 * uHighS, hash12(vec2(fi, floor(t * 15.0))));
        col += vec3(1.0, 0.8, 0.5) * smoothstep(0.008, 0.0, length((uv - c) * vec2(aspect, 1.0))) * on * live;
    }
    col += (noise(vUv * 250.0 + t * 20.0) - 0.5) * 0.08 * uGlitch;
    col *= 0.7 + 0.3 * live;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
