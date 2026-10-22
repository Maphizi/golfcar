#version 140
// Das Orakel: Serverhallen-Foto (uSceneTex) mit EINEM Hologramm-Kopf in 32 Gesten (uHeadTex 8x4 à 256x288, gleiche Lage in
// jeder Zelle) im Rahmen uFrame (x, y, Breite); Geste uHeadA -> uHeadB mit uHeadMix. Maske uMaskTex (8x2 à 256) über dem
// Gesicht (uMaskP = Index, Einblendung, Alter; uMaskFit = dx, dy, Größe in Kopf-Einheiten), Wackeln/Nicken uWobble (Maske, Beat-
// Nicken, Puls). Übergeben: Schwall aus dem Mund uMouth (Kopf-Einheiten) solange uVomitT >= 0, Datenmüll-Teile uGarb0..15
// (x, y in Kopf-Einheiten, Zelle aus uGarbTex 8x2 à 128, Drehung). Acht Neontafeln (uPanels: x0, x7, y, Breite) zeigen
// die Glyphen (uFigTex Reihe 2) und gehen hart auf den Beat an/aus (uPanelOn0/1 mit Nachglühen); innerhalb einer an-Tafel
// ist das Band (uBands/uPeaks) die Füllhöhe. Serverlichter blinken je Zone (uZoneOn). Bass = Kopf atmet, Mitten = Kopf
// dreht (Parallaxe), Höhen = Funkenregen im Rahmen; Kopfwechsel uHeadA/uHeadB/uHeadMix mit prozeduralem Glitch
// (uHeadGlitch: Streifen reißen, Blöcke springen, Zeilen fallen aus, Farbkanäle trennen, Rauschblöcke), Farbton uHue; Stille = Drahtgitter/Scanlinien-Schemen (uAwake); Drop = uFlash/uBurstT; Scanner-Welle
// uScanT; Glitch-Modus uGlitch; Automatik schnell uFast; Sprechen uSpeakT.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uHeadTex, uFigTex, uMaskTex, uGarbTex;
uniform vec2 uSceneSize, uHeadSize, uFigSize, uMaskSize, uGarbSize, uMouth;
uniform vec3 uFrame, uMaskFit, uWobble;
uniform vec4 uMaskP, uGarb0, uGarb1, uGarb2, uGarb3, uGarb4, uGarb5, uGarb6, uGarb7, uGarb8, uGarb9, uGarb10, uGarb11, uGarb12, uGarb13, uGarb14, uGarb15;
uniform float uVomitT, uNGarb;
uniform vec4 uPanels, uBands0, uBands1, uPeaks0, uPeaks1, uPanelOn0, uPanelOn1, uZoneOn;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uStep, uStepPhase, uPattern, uFlash;
uniform float uBurstT, uAwake, uHeadA, uHeadB, uHeadMix, uHeadGlitch, uHue, uSpeakT, uScanT, uFast, uGlitch, uZoom;
const float PI = 3.14159265;
const float CELL = 192.0;
const vec2 HCELL = vec2(256.0, 288.0);   // Gesten-Zelle (Kopf)

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
// Gesten-Zelle: d in -1..1 über die Zelle (256x288), 8x4 (Bild steht im Speicher auf dem Kopf)
vec4 headCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float rows = max(1.0, floor(uHeadSize.y / HCELL.y + 0.5));
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * HCELL.x, (rows - 1.0 - ri) * HCELL.y);
    return bilin(uHeadTex, lo + (d * 0.5 + 0.5) * HCELL, uHeadSize, lo, lo + HCELL - 1.0);
}
vec4 maskCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 256.0, (1.0 - ri) * 256.0);
    return bilin(uMaskTex, lo + (d * 0.5 + 0.5) * 256.0, uMaskSize, lo, lo + 255.0);
}
vec4 garbCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 128.0, (1.0 - ri) * 128.0);
    return bilin(uGarbTex, lo + (d * 0.5 + 0.5) * 128.0, uGarbSize, lo, lo + 127.0);
}
vec4 garbAt(int i) {
    if (i == 0) return uGarb0; if (i == 1) return uGarb1; if (i == 2) return uGarb2; if (i == 3) return uGarb3;
    if (i == 4) return uGarb4; if (i == 5) return uGarb5; if (i == 6) return uGarb6; if (i == 7) return uGarb7;
    if (i == 8) return uGarb8; if (i == 9) return uGarb9; if (i == 10) return uGarb10; if (i == 11) return uGarb11;
    if (i == 12) return uGarb12; if (i == 13) return uGarb13; if (i == 14) return uGarb14; return uGarb15;
}
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * CELL, (2.0 - ri) * CELL);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * CELL, uFigSize, lo, lo + CELL - 1.0);
}
float bandAt(int i) { return i < 4 ? uBands0[i] : uBands1[i - 4]; }
float peakAt(int i) { return i < 4 ? uPeaks0[i] : uPeaks1[i - 4]; }
float panelOn(int i) { return i < 4 ? uPanelOn0[i] : uPanelOn1[i - 4]; }
// Kopf: Mischung A->B (der Glitch dazwischen ist prozedural, siehe main)
vec4 headPair(float a, float b, vec2 d) { return mix(headCell(a, d), headCell(b, d), uHeadMix); }

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
    // ---- Serverlichter: vier Zonen (links außen, links innen, rechts innen, rechts außen) blinken hart mit den Tafeln,
    //      dazu das Lauflicht des Beat-Schritts und ein Flackern einzelner Lichtpunkte
    float lights = smoothstep(0.3, 0.6, lum) * smoothstep(0.1, 0.3, sat) * step(0.0, abs(uv.x - 0.5) - 0.3);
    int zone = uv.x < 0.5 ? (uv.x < 0.1 ? 0 : 1) : (uv.x > 0.9 ? 3 : 2);
    float zoneOn = uZoneOn[zone];
    float run = (float(zone) == mod(uStep, 4.0) ? 1.0 : 0.0) * (1.0 - 0.7 * uStepPhase);
    float cellFlick = step(0.6, hash12(vec2(floor(uv.x * 60.0), floor(uv.y * 30.0) + floor(t * 12.0) * step(0.3, uBeatPulse))));
    vec3 lightCol = hueShift(plate / max(lum, 0.2), uBeatStep * 0.4 + uHue * 0.5);
    float lightLvl = 0.1 + 0.4 * uBassS + 1.3 * zoneOn * (0.6 + 0.4 * cellFlick) + 0.8 * run + 0.5 * uFlash;
    col += lightCol * lights * lightLvl * live;
    col = mix(col, col * (0.35 + 0.65 * zoneOn), lights * live * 0.6);                    // aus-Zone wirklich dunkler
    col = mix(col, col * 0.5, lights * (1.0 - live) * 0.5);
    // ---- Datenregen im Hintergrund (Mitten): fallende Zeichenketten in den dunklen Flächen
    float dark = smoothstep(0.25, 0.05, lum);
    float colX = floor(uv.x * 220.0);
    vec2 rc = vec2(colX, uv.y * 110.0 + t * (3.0 + 8.0 * uMidS) * (0.5 + hash12(vec2(colX, 1.0))));
    float rain = step(0.9, hash12(floor(rc))) * step(0.75, hash12(vec2(colX, 2.0))) * (0.3 + 0.7 * fract(rc.y * 0.1));
    col += vec3(0.2, 0.9, 0.7) * rain * dark * (0.1 + 0.45 * uMidS) * live;
    // ---- Neontafeln: hart an/aus nach Beat-Muster (uPanelOn, Nachglühen), Band = Füllhöhe in der an-Tafel, Spitze = Linie
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float px = mix(uPanels.x, uPanels.y, fi / 7.0);
        float band = bandAt(i), pk = peakAt(i), on = panelOn(i);
        float hw = uPanels.w * aspect * 0.5;
        vec2 d = (uv - vec2(px, uPanels.z)) * vec2(aspect, 1.0) / hw;
        d.y *= 0.62;                                                                   // Tafel ist hoch, Zelle quadratisch
        vec4 g = figCell(16.0 + fi, d);
        float h = d.y / 0.62 * 0.5 + 0.5;                                              // 0 unten .. 1 oben
        float fill = smoothstep(band + 0.03, band - 0.03, h);                          // bis zur Bandhöhe gefüllt
        float level = on * (0.35 + 0.9 * fill + 0.45 * band + 0.3 * uBeatPulse * step(0.5, band));
        float flick = 1.0 - 0.3 * step(0.97, hash12(vec2(fi, floor(t * 20.0)))) * on;
        vec3 pc = g.rgb * (0.05 + 1.5 * level) * flick;                                // aus = wirklich dunkel
        col = mix(col, pc, g.a * (0.4 + 0.6 * live));
        col += g.rgb * g.a * level * 0.4;
        float glow = smoothstep(1.6, 0.4, length(d)) * (1.0 - g.a);
        col += g.rgb * glow * level * 0.45 * live;
        float pkLine = smoothstep(0.03, 0.0, abs(h - pk)) * step(abs(d.x), 1.0) * step(0.05, pk) * on;
        col += vec3(1.0) * pkLine * 0.6 * live;
    }
    // ---- Kopf im Projektionsrahmen: Hologramm (Scanlinien, Flackern), atmet mit dem Bass, dreht mit den Mitten,
    //      Gestenwechsel mit kurzem Glitch, Maske beim Drop (wackelt im Takt), bei Stille Drahtgitter-Schemen
    vec2 dHead;
    float wHead;
    {
        float breathe = 1.0 + 0.05 * uBassS * live + 0.025 * uBeatPulse;
        float w = uFrame.z * aspect * 0.5 * 1.0 * breathe;                             // Kopf füllt den Rahmen
        vec2 wh = vec2(w, w * HCELL.y / HCELL.x);
        vec2 d = (uv - (fr - vec2(0.0, 0.035))) * vec2(aspect, 1.0) / wh;
        d.y += 0.02 * sin(t * 1.1) * uAwake;
        // Beat-Nicken (uWobble.y) und Masken-Wackeln (uWobble.x): Versatz + Drehung, im Takt
        d.y += 0.05 * uWobble.y * uAwake;
        float wob = uWobble.x;
        if (wob > 0.001) {
            d += vec2(0.07 * sin(t * 31.0), 0.045 * cos(t * 23.0)) * wob;
            d = rot(0.14 * wob * sin(t * 19.0)) * d;
        }
        dHead = d;
        wHead = w;
        // Mitten: leichte Drehung = horizontale Stauchung + Parallaxe (Schichten verschieben sich gegen die Tiefe)
        float turn = sin(t * 0.9 + uSeed) * (0.15 + 0.5 * uMidS) * uAwake;
        d.x = d.x / (1.0 - 0.12 * abs(turn)) + turn * 0.08 * (d.y + 0.3);
        d.x += 0.02 * turn * sin(d.y * 6.0 + t * 2.0);
        float g = clamp(uHeadGlitch, 0.0, 1.0) + uGlitch * 0.5 + (uBurstT >= 0.0 ? exp(-uBurstT * 2.0) : 0.0) * 0.6;
        vec2 dg = d;
        float dropRow = 0.0, nz = 0.0;
        if (g > 0.01) {                                                               // prozeduraler Glitch
            float row = floor(d.y * 24.0);
            float tear = step(1.0 - 0.6 * g, hash12(vec2(row, floor(t * 14.0))));     // Streifen reißen seitlich
            dg.x += (hash12(vec2(row, floor(t * 9.0) + 7.0)) - 0.5) * 0.5 * g * tear;
            vec2 blk = floor(d * vec2(5.0, 7.0));
            float jump = step(1.0 - 0.3 * g, hash12(blk + floor(t * 6.0)));           // Blöcke springen
            dg += (vec2(hash12(blk + 1.0), hash12(blk + 2.0)) - 0.5) * 0.25 * jump;
            float band = floor(d.y * 9.0 + floor(t * 11.0));
            float slide = step(1.0 - 0.35 * g, hash12(vec2(band, floor(t * 7.0) + 2.0)));  // ganze Bänder gleiten durch
            dg.x += (hash12(vec2(band, 5.0)) - 0.5) * 0.8 * g * slide;
            dropRow = step(1.0 - 0.25 * g, hash12(vec2(floor(d.y * 60.0), floor(t * 20.0))));   // Zeilen fallen aus
            nz = step(1.0 - 0.07 * g, hash12(floor(d * vec2(16.0, 24.0)) + floor(t * 12.0)));   // Rauschblöcke
        }
        vec4 hm = headPair(uHeadA, uHeadB, dg);
        if (g > 0.2) {                                                                // Farbkanäle laufen auseinander
            float sep = 0.04 * g;
            hm.r = headPair(uHeadA, uHeadB, dg + vec2(sep, 0.004)).r;
            hm.b = headPair(uHeadA, uHeadB, dg - vec2(sep, 0.004)).b;
            hm.a = max(hm.a, max(headPair(uHeadA, uHeadB, dg + vec2(sep, 0.0)).a, headPair(uHeadA, uHeadB, dg - vec2(sep, 0.0)).a) * 0.7);
        }
        hm.rgb *= 1.0 - dropRow * 0.9;                                                // ausgefallene Zeilen dunkel
        hm.rgb = mix(hm.rgb, mix(vec3(0.2, 0.9, 1.0), vec3(1.0, 0.2, 0.8), hash12(dg * 90.0 + t)) * (0.5 + 0.5 * hash12(dg * 70.0 - t)), nz * step(0.05, hm.a));
        hm.rgb += vec3(0.3, 1.0, 0.9) * dropRow * 0.15 * step(1.0 - 0.2 * g, hash12(vec2(floor(d.y * 60.0), 3.0)));
        // Maske über dem Gesicht (eigene Zelle, zusätzliches Zittern beim Aufsetzen)
        if (uMaskP.y > 0.01) {
            float k = uMaskP.y;
            vec2 md = (dg - uMaskFit.xy) / uMaskFit.z;
            md += vec2(0.03 * sin(t * 47.0), 0.02 * cos(t * 37.0)) * (1.0 - k) * 2.0;
            vec4 mk = maskCell(uMaskP.x, md);
            float on = mk.a * smoothstep(0.0, 1.0, k);
            float settle = exp(max(-uMaskP.z * 2.0, -60.0));                                 // beim Aufsetzen hell aufblitzen
            mk.rgb *= 1.0 + 0.8 * settle + 0.25 * uBeatPulse;
            hm.rgb = mix(hm.rgb, mk.rgb, on);
            hm.a = max(hm.a, on);
        }
        hm.a *= smoothstep(-0.8, -0.42, dg.y + 0.03 * sin(dg.x * 40.0 + t * 6.0));          // Schultern lösen sich unten auf (Hologramm)
        vec4 m = hm;
        hm.rgb = hueShift(hm.rgb, uHue);
        float scan = 0.85 + 0.15 * sin(uv.y * 700.0 + t * 30.0);
        float flick = 1.0 - 0.15 * step(0.93, hash12(vec2(floor(t * 24.0), 1.0))) - 0.3 * uBassS * step(0.9, hash12(vec2(floor(t * 40.0), 2.0)));
        vec3 mc = hm.rgb * scan * flick;
        if (uSpeakT >= 0.0) mc += hm.rgb * 0.3 * abs(sin(uSpeakT * 14.0));
        // Drahtgitter-Schemen: Kanten des Kopfes als cyanfarbene Linien plus Rasterlinien, sichtbar wenn nicht wach
        vec2 e = vec2(0.02, 0.0);
        float la = m.a, lx = headPair(uHeadA, uHeadB, d + e).a - headPair(uHeadA, uHeadB, d - e).a;
        float ly = headPair(uHeadA, uHeadB, d + e.yx).a - headPair(uHeadA, uHeadB, d - e.yx).a;
        float lumH = dot(m.rgb, vec3(0.33));
        float lumX = dot(headPair(uHeadA, uHeadB, d + e).rgb - headPair(uHeadA, uHeadB, d - e).rgb, vec3(0.33));
        float edge = clamp(abs(lx) * 2.0 + abs(ly) * 2.0 + abs(lumX) * 4.0, 0.0, 1.0);
        float grid = max(step(0.94, fract(d.x * 10.0)), step(0.94, fract(d.y * 10.0))) * la * 0.35;
        float wireFlick = 0.6 + 0.4 * step(0.5, hash12(vec2(floor(t * 3.0), floor(d.y * 30.0))));
        vec3 wire = vec3(0.2, 0.8, 1.0) * (edge * 0.8 + grid + lumH * la * 0.15) * wireFlick;
        float wireScan = 0.5 + 0.5 * step(0.5, fract(d.y * 18.0 - t * 1.5));
        wire *= wireScan;
        float vis = hm.a * (0.6 + 0.4 * live);
        vec3 holo = mix(wire * 0.9, mc, uAwake);
        float holoA = mix(max(edge, grid) * 0.9, vis * 0.92, uAwake);
        col = mix(col, holo, holoA);
        col += mc * vis * uAwake * (0.2 + 0.4 * uBassS + 0.6 * uFlash);
        // Funkenregen im Rahmen (Höhen): kleine Funken fallen durch das Hologramm
        for (int k = 0; k < 24; k++) {
            float fk = float(k);
            float h1 = hash12(vec2(fk, 41.0)), h2 = hash12(vec2(fk, 43.0)), h3 = hash12(vec2(fk, 47.0));
            float life = fract(t * (0.5 + 0.7 * h2) + h3);
            vec2 sp = vec2(-0.9 + 1.8 * h1 + 0.1 * sin(t * 3.0 + fk), 1.0 - 2.2 * life);
            float spark = smoothstep(0.035, 0.0, length(d - sp)) * (1.0 - life) * step(0.55 - 0.5 * uHighS, h3 + 0.3 * sin(fk + t));
            col += vec3(1.0, 0.9, 0.6) * spark * (0.3 + 1.5 * uHighS) * live * uAwake;
        }
        // Lichtkegel des Projektors pulst
        float cone = smoothstep(0.0, 1.0, 1.0 - abs(d.x) / (0.3 + 1.2 * (1.0 - (d.y * 0.5 + 0.5)))) * smoothstep(1.2, -1.0, d.y) * step(-1.3, d.y);
        col += vec3(0.2, 0.6, 1.0) * cone * 0.05 * (0.5 + uBassS + 0.5 * uFast) * uAwake;
        col += vec3(0.3, 0.7, 1.0) * cone * 0.04 * uAwake * uBeatPulse * uFast;
    }
    // ---- Übergeben: Schwall aus dem Mund (Bogen nach vorn/unten, cyan/magenta, Pixelblöcke) und Datenmüll-Teile
    if (uVomitT >= 0.0) {
        float len = min(1.5, uVomitT * 1.6);
        float fade = 1.0 - smoothstep(2.6, 3.2, uVomitT);
        float best = 9.0, bs = 0.0;
        for (int i = 0; i <= 24; i++) {
            float ss = float(i) / 24.0 * len;
            vec2 p = uMouth + vec2(0.22 * ss + 0.04 * sin(t * 9.0 + ss * 7.0), -0.3 * ss - 1.1 * ss * ss);
            float dd = length((dHead - p) * vec2(1.0, 0.9));
            if (dd < best) { best = dd; bs = ss; }
        }
        float thick = 0.05 + 0.06 * bs;
        float jet = smoothstep(thick, thick * 0.3, best) * fade;
        float blocks = step(0.45, hash12(floor((dHead + vec2(0.0, t * 2.5)) * 22.0)));
        vec3 jc = mix(vec3(0.2, 1.0, 0.9), vec3(1.0, 0.3, 0.9), blocks);
        col = mix(col, jc, jet * (0.6 + 0.4 * blocks));
        col += jc * smoothstep(thick * 3.0, 0.0, best) * 0.25 * fade;
    }
    for (int i = 0; i < 16; i++) {
        if (float(i) >= uNGarb) break;
        vec4 g = garbAt(i);
        if (g.y < -50.0) continue;
        vec2 dd = rot(-g.w) * (dHead - g.xy) / 0.2;
        vec4 gc = garbCell(g.z, dd);
        if (gc.a > 0.01) {
            col = mix(col, gc.rgb * (1.0 + 0.3 * uBeatPulse), gc.a * 0.95);
            col += gc.rgb * gc.a * 0.3;
        }
    }
    // ---- Scanner-Welle durch die Halle: helle Linie läuft von links nach rechts, hebt Kanten des Fotos hervor
    if (uScanT >= 0.0) {
        float sx = -0.1 + 1.2 * uScanT / 2.4;
        float dx = (uv.x - sx);
        float line = smoothstep(0.012, 0.0, abs(dx)) + 0.5 * smoothstep(0.1, 0.0, -dx) * step(dx, 0.0);
        float edge = abs(lum - max(scene(uv + vec2(0.003, 0.0)).g, scene(uv + vec2(0.0, 0.004)).g));
        col += vec3(0.3, 1.0, 0.8) * line * (0.35 + 2.5 * edge);
        col += vec3(0.3, 1.0, 0.8) * step(0.97, hash12(vec2(floor(uv.y * 80.0), floor(uScanT * 30.0)))) * step(abs(dx), 0.04) * 0.5;
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
            col = mix(col, hueShift(vec3(0.3, 0.9, 1.0), h3 * 5.0 + uHue), blk * exp(-uBurstT * 0.9));
        }
        float ring = smoothstep(0.02, 0.0, abs(length((uv - fr) * vec2(aspect, 1.0)) - uBurstT * 0.35));
        col += vec3(0.6, 0.9, 1.0) * ring * exp(-uBurstT * 1.5) * 0.8;
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
    col += vec3(0.5, 0.8, 1.0) * uFlash * 0.15;
    col *= 0.7 + 0.3 * live;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
