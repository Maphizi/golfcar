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
uniform sampler2D uSceneTex, uEyeTex, uFigTex, uFrogTex, uDiveTex, uGnomeTex;
uniform vec2 uSceneSize, uEyeSize, uFigSize, uFrogSize, uDiveSize, uGnomeSize;
uniform vec3 uEyePos;                              // x, y, Breite (Bildanteile)
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uStep, uStepPhase, uPattern, uFlash, uSporeT;
uniform float uZoom, uKaleido, uChorusT, uBlink, uEyeA, uEyeB, uEyeMix, uHueT;
uniform vec4 uFig, uOwl, uBands0, uBands1;
uniform vec4 uFrog0, uFrog1, uFrog2, uFrog3, uFrog4, uFrog5, uFrog6, uFrog7;   // x, y, Größe, Art (Reihe in frogs.png)
uniform vec4 uFrogPh0, uFrogPh1, uFrogPh2, uFrogPh3, uFrogPh4, uFrogPh5, uFrogPh6, uFrogPh7;   // Phase 0 leer 1 taucht auf 2 sitzt 3 hüpft 4 springt 5 unten, Fortschritt, rechts (spiegeln)
uniform vec4 uGnome0, uGnome1, uGnome2, uGnome3, uGnome4, uGnome5, uGnome6, uGnome7, uGnome8, uGnome9, uGnome10, uGnome11;       // x, y, Größe, Zelle
uniform vec4 uGnomeS0, uGnomeS1, uGnomeS2, uGnomeS3, uGnomeS4, uGnomeS5, uGnomeS6, uGnomeS7, uGnomeS8, uGnomeS9, uGnomeS10, uGnomeS11; // Pose A, Pose B, Mischung, aufgetaucht
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

vec4 frogPhAt(int i) { return i == 0 ? uFrogPh0 : (i == 1 ? uFrogPh1 : (i == 2 ? uFrogPh2 : (i == 3 ? uFrogPh3 : (i == 4 ? uFrogPh4 : (i == 5 ? uFrogPh5 : (i == 6 ? uFrogPh6 : uFrogPh7)))))); }
vec4 gnomeAt(int i) { return i == 0 ? uGnome0 : (i == 1 ? uGnome1 : (i == 2 ? uGnome2 : (i == 3 ? uGnome3 : (i == 4 ? uGnome4 : (i == 5 ? uGnome5 : (i == 6 ? uGnome6 : (i == 7 ? uGnome7 : (i == 8 ? uGnome8 : (i == 9 ? uGnome9 : (i == 10 ? uGnome10 : uGnome11)))))))))); }
vec4 gnomeSAt(int i) { return i == 0 ? uGnomeS0 : (i == 1 ? uGnomeS1 : (i == 2 ? uGnomeS2 : (i == 3 ? uGnomeS3 : (i == 4 ? uGnomeS4 : (i == 5 ? uGnomeS5 : (i == 6 ? uGnomeS6 : (i == 7 ? uGnomeS7 : (i == 8 ? uGnomeS8 : (i == 9 ? uGnomeS9 : (i == 10 ? uGnomeS10 : uGnomeS11)))))))))); }
// Sprungbild: frogs.png 8x4 à 160 (Reihe = Art, Spalte = Bild), d -1..1
vec4 frogCell(float species, float frame, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    vec2 lo = vec2(frame * 160.0, (3.0 - species) * 160.0);
    return bilin(uFrogTex, lo + (d * 0.5 + 0.5) * 160.0, uFrogSize, lo, lo + 159.0);
}
// Tauchbild: dive.png 8x2 à 192 (Reihe 0 springt ins Wasser, 1 taucht auf)
vec4 diveCell(float row, float frame, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    vec2 lo = vec2(frame * 192.0, (1.0 - row) * 192.0);
    return bilin(uDiveTex, lo + (d * 0.5 + 0.5) * 192.0, uDiveSize, lo, lo + 191.0);
}
// Zwerg: gnomes.png 8x3 à 160 (Reihe 0 gucken, 1 ducken, 2 winken)
vec4 gnomeCell(float pose, float cell, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    vec2 lo = vec2(cell * 160.0, (2.0 - pose) * 160.0);
    return bilin(uGnomeTex, lo + (d * 0.5 + 0.5) * 160.0, uGnomeSize, lo, lo + 159.0);
}
// Bildfolge weich: Bild f und f+1 überblenden
vec4 frogAnim(float species, float prog, int nmax, vec2 d) {
    float f = clamp(prog * float(nmax), 0.0, float(nmax) - 0.001);
    float fa = floor(f), fb = min(fa + 1.0, float(nmax) - 1.0);
    return mix(frogCell(species, fa, d), frogCell(species, fb, d), smoothstep(0.2, 0.8, fract(f)));
}
vec4 diveAnim(float row, float prog, vec2 d) {
    float f = clamp(prog * 8.0, 0.0, 7.999);
    float fa = floor(f), fb = min(fa + 1.0, 7.0);
    return mix(diveCell(row, fa, d), diveCell(row, fb, d), smoothstep(0.2, 0.8, fract(f)));
}
// Artfarbe für die (grünen) Tauchbilder: 0 Laubfrosch, 1 Rotaugen, 2 orange, 3 blau
float speciesHue(float sp) { return sp < 0.5 ? 0.0 : (sp < 1.5 ? 0.15 : (sp < 2.5 ? -1.7 : 1.9)); }

// Frosch auf Blatt i: Besetzung, Hüpfen, Tauchen, Auftauchen; Spiegelung im Wasser. Fußpunkt = Blattmitte.
vec3 frog(vec3 col, vec2 uv, float aspect, int i, bool mirror) {
    vec4 fr = frogAt(i);
    vec4 ph = frogPhAt(i);
    float phase = ph.x, prog = ph.y, flip = ph.z > 0.5 ? -1.0 : 1.0;
    if (phase < 0.5) return col;                                             // leer
    if (abs(uv.x - fr.x) * aspect > fr.z * aspect * 1.2 || abs(uv.y - fr.y) > fr.z * aspect * 1.6) return col;   // weit weg: nichts zu tun
    float band = bandAt(i);
    float fi = float(i);
    float sp = fr.w;
    float infl = smoothstep(0.12, 0.75, band);
    if (uChorusT >= 0.0) {
        float cph = clamp(uChorusT * 2.0 - fi * 0.35, 0.0, 6.0);
        infl = max(infl, 0.5 + 0.5 * sin(cph * PI - PI * 0.5));
    }
    float hw = fr.z * aspect * 0.5 * (0.95 + 0.1 * uLive);
    float wl = fr.y - 0.012;                                                  // Wasserlinie
    bool diveSeq = phase == 1.0 || phase == 4.0;                             // Tauchbilder (größer, mit Blatt)
    float scale = diveSeq ? 1.45 : 1.0;
    float yOff = diveSeq ? -0.02 * hw : 0.0;
    vec4 s;
    if (phase == 5.0) {                                                      // unter Wasser: wabernder Schatten, Blasen
        vec2 wuv = uv + vec2(0.006 * sin(uv.y * 70.0 + iTime * 3.0 + fi), 0.0);
        if (mirror || wuv.y > wl) return col;
        float wob = 0.5 + 0.5 * sin(prog * 1.7 + fi);
        vec2 d = (wuv - vec2(fr.x + 0.01 * sin(prog * 0.9 + fi), fr.y - 1.1 * hw - 0.15 * hw * wob)) * vec2(aspect, 1.0) / hw;
        d.x *= flip;
        vec4 sh = frogCell(sp, 0.0, vec2(d.x, d.y - 1.0 + 0.02));
        vec3 tint = hueShift(vec3(0.3, 0.9, 0.8), uHueT * 3.0 + fi) * (0.7 + 0.5 * band);
        for (int k = 0; k < 4; k++) {
            float hk = hash12(vec2(float(k), fi + 50.0));
            float age = mod(prog * 0.7 + hk * 3.0, 3.0);
            vec2 bp = vec2(fr.x + (hk - 0.5) * 0.03, fr.y - 1.2 * hw + age * 0.025);
            if (bp.y < wl) col += vec3(0.6, 0.9, 1.0) * smoothstep(0.004, 0.0, length((uv - bp) * vec2(aspect, 1.0))) * 0.6;
        }
        return mix(col, mix(sh.rgb, tint, 0.6) * 1.3, sh.a * 0.6);
    }
    if (!mirror && uv.y < wl - 0.002 && !diveSeq) return col;
    if (mirror && (uv.y >= wl || diveSeq)) return col;
    vec2 l;
    if (mirror) {
        vec2 wuv = uv + vec2(0.004 * sin(uv.y * 90.0 + iTime * 2.0 + fi), 0.0);
        vec2 d = (wuv - vec2(fr.x, wl)) * vec2(aspect, 1.0) / (hw * scale);
        l = vec2(d.x * flip, -d.y - 1.0 - (fr.y + yOff - wl) / (hw * scale));
    } else {
        vec2 d = (uv - vec2(fr.x, fr.y + yOff)) * vec2(aspect, 1.0) / (hw * scale);
        l = vec2(d.x * flip, d.y - 1.0 + 0.02);
    }
    if (phase == 2.0) {                                                      // sitzt: Kehlsack mit dem Band
        s = mix(frogCell(sp, 0.0, l), frogCell(sp, 7.0, l), infl);
    } else if (phase == 3.0) {                                               // hüpft: 8 Bilder
        s = frogAnim(sp, prog, 8, l);
    } else if (phase == 4.0) {                                               // springt ins Wasser
        s = diveAnim(0.0, prog, l);
        s.rgb = hueShift(s.rgb, speciesHue(sp));
    } else {                                                                 // taucht auf
        s = diveAnim(1.0, prog, l);
        s.rgb = hueShift(s.rgb, speciesHue(sp));
        if (prog > 0.85) s = mix(s, frogCell(sp, 0.0, l), (prog - 0.85) / 0.15);   // Übergang auf das Sprungbild der Art
    }
    s.rgb *= 0.55 + 0.45 * uLive + 0.5 * band;
    s.rgb = hueShift(s.rgb, uKaleido * (uHueT * 6.0 + fi) + uHueBurst * 2.0 * sin(uHueT * 30.0 + fi * 2.0));
    if (mirror) { s.rgb *= 0.35; s.a *= 0.55; }
    col = mix(col, s.rgb, s.a);
    // Nachbilder beim Hüpfen und Tauchen (psychedelisch, mit der Musik)
    if (!mirror && (phase == 3.0 || phase == 4.0 || phase == 1.0) && uLive > 0.3) {
        for (int k = 1; k <= 2; k++) {
            float pk = max(0.0, prog - 0.08 * float(k));
            vec4 g = phase == 3.0 ? frogAnim(sp, pk, 8, l) : diveAnim(phase == 4.0 ? 0.0 : 1.0, pk, l);
            vec3 gc = hueShift(vec3(0.5, 1.0, 0.8), float(k) * 1.4 + uHueT * 10.0 + fi);
            col = mix(col, mix(g.rgb, gc, 0.6), g.a * 0.3 * (1.0 - float(k) * 0.3) * (1.0 - s.a) * (0.5 + 0.5 * uBassS));
        }
    }
    // Ringe an der Wasserlinie beim Eintauchen und Auftauchen
    if (!mirror && (phase == 4.0 && prog > 0.5 || phase == 1.0 && prog < 0.5)) {
        float sp2 = phase == 4.0 ? (prog - 0.5) * 2.0 : prog * 2.0;
        vec2 c = vec2(fr.x, wl);
        float rr = length((uv - c) * vec2(aspect, 2.5));
        float ring = exp(-pow((rr - 0.02 - 0.08 * sp2) * 60.0, 2.0)) * (1.0 - sp2);
        col += vec3(0.7, 0.9, 1.0) * ring * 0.8 * smoothstep(0.0, 0.01, wl - uv.y + 0.015);
    }
    return col;
}

// Zwerg i lugt über die Wurzeln: steigt hinter der Fußlinie auf (darunter abgeschnitten), wippt mit dem Bass, duckt
// sich auf den Beat, winkt ab und zu
vec3 gnome(vec3 col, vec2 uv, float aspect, int i) {
    vec4 g = gnomeAt(i), st = gnomeSAt(i);
    float rise = st.w;
    if (rise < 0.01) return col;
    if (abs(uv.x - g.x) * aspect > g.z * aspect * 0.6 || uv.y - g.y > g.z * aspect * 1.2) return col;
    float fi = float(i);
    float hw = g.z * aspect * 0.5;
    float H = hw * 2.0;
    if (uv.y < g.y) return col;                                              // hinter der Wurzel
    float bob = 0.04 * H * uBassS * sin(iTime * 8.0 + fi) + 0.02 * H * sin(iTime * 1.3 + fi * 2.0);
    float yOff = -(1.0 - rise) * 1.1 * H + bob;
    vec2 d = (uv - vec2(g.x, g.y + yOff)) * vec2(aspect, 1.0) / hw;
    vec2 l = vec2(d.x * (mod(fi, 2.0) < 1.0 ? 1.0 : -1.0), d.y - 1.0 + 0.1);   // Sockel des Bildes (unten 10 %) wegschneiden
    if (l.y < -0.8) return col;
    vec4 s = mix(gnomeCell(st.x, g.w, l), gnomeCell(st.y, g.w, l), st.z);
    s.rgb *= 0.7 + 0.3 * uLive + 0.3 * uBassS;
    s.rgb = hueShift(s.rgb, uKaleido * (uHueT * 4.0 + fi));
    return mix(col, s.rgb, s.a * smoothstep(0.0, 0.2, rise));
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
    // ---- Figuren: Zwerge lugen über die Wurzeln (rechts), Eule kreist um den Baum (links)
    float figMode = uFig.x;
    for (int i = 0; i < 12; i++) col = gnome(col, uv, aspect, i);
    if (figMode == 1.0 || figMode == 3.0) {
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
