#version 140
// Black Ice: Hacker-Kammer (uSceneTex, Alpha 0 = Bildschirm) in Wellen (uPhase 0 Einbruch, 1 Trace, 2 Black ICE, 3 Flatline).
// Die Bildschirme uScr0..11 (x0, y0, x1, y1, y von unten) zeigen je einen Inhalt uScrC0..11 = (Typ, Variante, Startzeit, Seed):
//   0 Atlaskachel (uScreenTex 8x4, Zelle = Spalte + 8*Reihe; läuft/pulsiert mit Bass, Wellenform = uAudioTex), 1 digitales Auge (uEyeLook,
//   uEyeBlink, bei Black ICE rot und weit), 2 Countdown aus Blöcken, 3 Warn-Dreieck, 4 Rauschen/Testbild, 5 Fadenkreuz,
//   6 Barcode, 7 Fahndungsfoto (uFaceTex), 8 EKG, 9 aus, 10 Daemon (uCreatureTex 4x3 à 256), 11 Glitch-Maske (uGodTex
//   8x3 à 192), 12 Fixer-Katze (uFigTex, Zellen uOwl), 13 Bootzeilen, 14 Standby (Cursor blinkt), 15 Atlas-Auge (Zellen 0..7).
// Globale Zustände überstimmen den Inhalt: Flatline = EKG überall, Stecker (uEyesT) = alles aus, Augen öffnen sich langsam,
// Reboot (uVomitT) = Bootzeilen überall, Hilfe (uHelpT) = Katze überall, Stille (uLive) = Standby. 80 ms Schwarz beim Wechsel.
// Raum: uPoison = Trace-Grad (Kanaltrennung, Scanlines, Tunnel, Rauschen), Bass = Herzschlag + rote Warnlampen, Beat =
// Bildsprung (uCut) und Negativflackern, Höhen = Kabel funkeln, Drop = uFlash. Gegenmaßnahme uRelief, Jack out uShock.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uScreenTex, uCreatureTex, uFaceTex, uGodTex, uFigTex;
uniform vec2 uSceneSize, uScreenSize, uCreatureSize, uFaceSize, uGodSize, uFigSize, uCut, uEyeLook;
uniform float uScreenOK, uFaceOK, uGodOK, uFigOK, uSeed, uPhase, uPhaseT, uPhaseLen, uWave, uPoison, uRelief, uReliefT;
uniform float uVomitT, uEyes, uEyesT, uHelpT, uShock, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash;
uniform float uEyeBlink, uNScr;
uniform vec4 uOwl, uBands0, uBands1, uEvent;
uniform vec4 uScr0, uScr1, uScr2, uScr3, uScr4, uScr5, uScr6, uScr7, uScr8, uScr9, uScr10, uScr11;
uniform vec4 uScrC0, uScrC1, uScrC2, uScrC3, uScrC4, uScrC5, uScrC6, uScrC7, uScrC8, uScrC9, uScrC10, uScrC11;
const float PI = 3.14159265;

float sq(float x) { return x * x; }
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
vec4 scene(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0); }
vec4 atlasCell(float cell, vec2 q) {                                          // Atlas 8x4 (Zelle = Spalte + 8*Reihe), q 0..1 (y nach oben)
    vec2 cs = uScreenSize / vec2(8.0, 4.0);
    cell = mod(cell, 32.0);
    float ci = mod(cell, 8.0), ri = floor(cell / 8.0);
    vec2 lo = vec2(ci * cs.x, (3.0 - ri) * cs.y);
    return bilin(uScreenTex, lo + clamp(q, 0.0, 1.0) * cs, uScreenSize, lo, lo + cs - 1.0);
}
vec4 creature(float idx, vec2 d) {                                           // 4x3 à 256, d -1..1
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 4.0), ri = floor(idx / 4.0);
    vec2 lo = vec2(ci * 256.0, (2.0 - ri) * 256.0);
    return bilin(uCreatureTex, lo + (d * 0.5 + 0.5) * 256.0, uCreatureSize, lo, lo + 255.0);
}
vec4 figCell(float idx, vec2 d) {                                            // Katze aus dem Orakel (8x3 à 192)
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
}
vec4 godCell(float idx, vec2 d) {                                            // Glitch-Maske (8x3 à 192)
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uGodTex, lo + (d * 0.5 + 0.5) * 192.0, uGodSize, lo, lo + 191.0);
}
vec4 scrAt(int i) {
    if (i == 0) return uScr0; if (i == 1) return uScr1; if (i == 2) return uScr2; if (i == 3) return uScr3;
    if (i == 4) return uScr4; if (i == 5) return uScr5; if (i == 6) return uScr6; if (i == 7) return uScr7;
    if (i == 8) return uScr8; if (i == 9) return uScr9; if (i == 10) return uScr10; return uScr11;
}
vec4 scrCAt(int i) {
    if (i == 0) return uScrC0; if (i == 1) return uScrC1; if (i == 2) return uScrC2; if (i == 3) return uScrC3;
    if (i == 4) return uScrC4; if (i == 5) return uScrC5; if (i == 6) return uScrC6; if (i == 7) return uScrC7;
    if (i == 8) return uScrC8; if (i == 9) return uScrC9; if (i == 10) return uScrC10; return uScrC11;
}
float bandAt(int i) {
    if (i <= 0) return uBands0.x; if (i == 1) return uBands0.y; if (i == 2) return uBands0.z; if (i == 3) return uBands0.w;
    if (i == 4) return uBands1.x; if (i == 5) return uBands1.y; if (i == 6) return uBands1.z; return uBands1.w;
}
float digitCode(int d) {                                                     // 3x5-Blockziffern, Bit 14 = oben links
    if (d == 0) return 31599.0; if (d == 1) return 9362.0; if (d == 2) return 29671.0; if (d == 3) return 29647.0;
    if (d == 4) return 23497.0; if (d == 5) return 31183.0; if (d == 6) return 31215.0; if (d == 7) return 29257.0;
    if (d == 8) return 31727.0; return 31695.0;
}
float digitPx(int d, vec2 p) {                                               // p 0..1 innerhalb der Ziffer (y nach oben)
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    float c = floor(p.x * 3.0), r = floor((1.0 - p.y) * 5.0);
    float b = 14.0 - (r * 3.0 + c);
    float on = mod(floor(digitCode(d) / pow(2.0, b)), 2.0);
    vec2 f = fract(p * vec2(3.0, 5.0));
    float gap = step(0.08, f.x) * step(0.08, f.y);
    return on * gap;
}
float sdTri(vec2 p, float r) {                                               // gleichseitiges Dreieck (iq)
    const float k = 1.7320508;
    p.x = abs(p.x) - r;
    p.y = p.y + r / k;
    if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
    p.x -= clamp(p.x, -2.0 * r, 0.0);
    return -length(p) * sign(p.y);
}

// ---------------------------------------------------------------- Bildschirminhalte (q 0..1, s = zentriert, quadratisch)
vec3 atlasContent(float cell, float age, float seed, vec2 q, vec2 s, float horror) {
    float bass = uBassS, bp = uBeatPulse;
    vec2 p = q;
    vec3 col;
    if (cell == 21.0 || cell == 26.0) {                                      // Glyphenregen / Binärblöcke laufen nach unten
        float colx = floor(q.x * 24.0);
        float sp = 0.12 + 0.25 * hash12(vec2(colx, seed * 10.0)) + 0.5 * bass;
        p.y = fract(q.y + age * sp + seed);
        col = atlasCell(cell, p).rgb * (0.7 + 0.7 * bass + 0.3 * bp);
        col *= 0.7 + 0.6 * step(0.6, hash12(vec2(colx, floor(age * 8.0))));
    } else if (cell == 16.0) {                                               // Wellenform = echte Waveform (uAudioTex)
        vec3 base = atlasCell(cell, p).rgb * 0.2;
        float w = (texture(uAudioTex, vec2(fract(q.x + seed), 0.75)).r - 0.5) * (1.2 + 1.5 * bass);
        float line = smoothstep(0.05, 0.0, abs(s.y - w));
        col = base + vec3(0.2, 1.0, 1.0) * line * (0.8 + 0.4 * bp) + vec3(0.1, 0.5, 0.6) * 0.3 * exp(-abs(s.y - w) * 6.0);
        col += vec3(0.2, 0.9, 1.0) * step(abs(s.y), abs(w)) * 0.25;
    } else if (cell == 17.0) {                                               // Herzlinie läuft, Puls mit Bass
        p.x = fract(q.x - age * (0.3 + 0.4 * bass) + seed);
        p.y = 0.5 + (q.y - 0.5) / (0.6 + 0.9 * bass + 0.6 * bp);
        col = atlasCell(cell, p).rgb * (0.7 + 0.5 * bass);
        col += vec3(1.0, 0.2, 0.5) * smoothstep(0.03, 0.0, abs(q.y - 0.5)) * bp * 0.5;
    } else if (cell == 10.0) {                                               // Radar: Sektor dreht, Echos blitzen auf
        col = atlasCell(cell, q).rgb * 0.45;
        float r = length(s), a = atan(s.y, s.x);
        float sweep = fract(a / (2.0 * PI) - age * (0.25 + 0.3 * bass) - seed);
        float wedge = pow(1.0 - sweep, 8.0) * step(r, 0.92);
        col += vec3(0.2, 1.0, 0.4) * wedge * 0.8;
        col += vec3(0.4, 1.0, 0.5) * smoothstep(0.015, 0.0, abs(r - 0.92)) * 0.5;
        for (int i = 0; i < 5; i++) {
            float fi = float(i);
            float ba = hash12(vec2(fi, seed * 5.0 + floor(age * 0.3))) * 2.0 * PI, br = 0.2 + 0.65 * hash12(vec2(fi, seed * 9.0));
            vec2 bpnt = vec2(cos(ba), sin(ba)) * br;
            float phase = fract(ba / (2.0 * PI) - age * (0.25 + 0.3 * bass) - seed);
            float glow = pow(1.0 - fract(-phase), 3.0);
            col += vec3(0.5, 1.0, 0.6) * smoothstep(0.05, 0.0, length(s - bpnt)) * glow;
        }
    } else if (cell == 11.0) {                                               // Fadenkreuz wandert, rastet auf den Beat ein
        vec2 sh = vec2(sin(age * 0.7 + seed * 6.0), cos(age * 0.9 + seed * 3.0)) * 0.12;
        p = 0.5 + (q - 0.5 - sh) * (1.0 - 0.1 * bp);
        if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) col = vec3(0.0);
        else col = atlasCell(cell, p).rgb * (0.7 + 0.5 * bass + 0.8 * bp);
        col += vec3(1.0, 0.2, 0.5) * smoothstep(0.02, 0.0, abs(length(s - sh * 2.0) - 0.9 * fract(age * 0.6))) * (1.0 - fract(age * 0.6)) * 0.5;
    } else if (cell == 12.0 || cell == 28.0) {                               // Scan: Linie fährt durch Fingerabdruck / Hirn
        col = atlasCell(cell, q).rgb * (0.6 + 0.4 * bass);
        float scanY = 0.5 + 0.45 * sin(age * 1.2 + seed * 6.0);
        col += vec3(0.3, 1.0, 1.0) * smoothstep(0.03, 0.0, abs(q.y - scanY)) * 0.9 + vec3(0.1, 0.4, 0.5) * exp(-abs(q.y - scanY) * 12.0) * 0.5;
        col *= 1.0 + 0.8 * bp * step(0.5, fract(age * 10.0));
    } else if (cell == 13.0) {                                               // Schloss wackelt auf den Beat, bei Black ICE rot
        p = q + vec2(0.02 * sin(age * 40.0), 0.0) * bp;
        col = atlasCell(cell, p).rgb * (0.7 + 0.5 * bass + 0.4 * bp);
        col = mix(col, col.gbr * vec3(1.6, 0.4, 0.4), horror * (0.5 + 0.5 * step(0.5, fract(age * 3.0))));
    } else if (cell == 14.0 || cell == 23.0) {                               // Virus / Spirale drehen sich, Tempo = Bass
        float dir = cell == 23.0 ? -1.0 : 1.0;
        vec2 v = rot(dir * (age * (0.3 + 0.8 * bass) + 0.6 * bp)) * ((q - 0.5) * vec2(1.78, 1.0));
        p = v / vec2(1.78, 1.0) * (1.0 - 0.1 * bass) + 0.5;
        if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) col = vec3(0.0);
        else col = atlasCell(cell, p).rgb * (0.7 + 0.6 * bass + 0.5 * bp);
    } else if (cell == 8.0 || cell == 15.0 || cell == 30.0) {                // Schädel / Drahtgesicht / Hand: kommen näher, Glitch
        float grow = 0.75 + 0.25 * min(1.0, age / 8.0) + 0.1 * bp;
        float row = floor(q.y * 36.0);
        p = 0.5 + (q - 0.5) / grow;
        p.x += (hash12(vec2(row, floor(age * 12.0))) - 0.5) * 0.1 * step(0.85, hash12(vec2(row, floor(age * 4.0) + seed))) * (0.5 + horror);
        if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) col = vec3(0.0);
        else col = atlasCell(cell, p).rgb * (0.6 + 0.8 * bass + 0.5 * bp);
        col = mix(col, hueShift(col, 2.5), horror * step(0.5, fract(age * 2.0)));
    } else if (cell == 9.0) {                                                // Warndreieck blinkt
        float blink = 0.35 + 0.65 * step(0.5, fract(age * (2.0 + 2.0 * bass)));
        col = atlasCell(cell, q).rgb * blink * (0.9 + 0.5 * bp);
    } else if (cell == 18.0 || cell == 29.0) {                               // Karten: Kamera fährt, Zielpunkt blinkt
        p = 0.1 + q * 0.8 + 0.08 * vec2(sin(age * 0.11 + seed * 6.0), cos(age * 0.09 + seed * 3.0));
        col = atlasCell(cell, p).rgb * (0.8 + 0.5 * bass);
        vec2 tp = vec2(0.3 + 0.4 * hash12(vec2(seed, 1.0)), 0.3 + 0.4 * hash12(vec2(seed, 2.0)));
        float d = length((q - tp) * vec2(1.78, 1.0));
        float ring = smoothstep(0.012, 0.0, abs(d - 0.06 - 0.05 * fract(age * 0.8)));
        col += vec3(1.0, 0.2, 0.2) * (ring * (1.0 - fract(age * 0.8)) + smoothstep(0.015, 0.0, d) * step(0.5, fract(age * 2.0)));
        col += vec3(1.0, 0.3, 0.8) * step(0.8, hash12(floor(q * vec2(16.0, 9.0)) + floor(age * 2.0 + seed))) * 0.15;
    } else if (cell == 19.0) {                                               // Barcode: Scanner fährt
        p.x = fract(q.x + 0.05 * sin(age * 0.5));
        col = atlasCell(cell, p).rgb * (0.6 + 0.2 * bass);
        float scan = 0.5 + 0.45 * sin(age * 1.5 + seed * 6.0);
        col += vec3(1.0, 0.1, 0.1) * (smoothstep(0.012, 0.0, abs(q.x - scan)) * 1.2 + 0.15 * exp(-abs(q.x - scan) * 20.0));
        col += vec3(1.0, 0.3, 0.3) * bp * 0.3;
    } else if (cell == 22.0) {                                               // Platine: Impulse laufen über die Bahnen
        float pulse = smoothstep(0.55, 0.9, noise(q * vec2(6.0, 3.4) + vec2(age * 1.5, seed * 8.0)));
        col = atlasCell(cell, q).rgb * (0.5 + 1.2 * pulse + 0.4 * bass);
    } else if (cell == 24.0) {                                               // Rauschen lebt
        p = q + vec2(hash12(vec2(floor(age * 15.0), seed)), hash12(vec2(floor(age * 13.0), seed + 1.0))) * 0.3;
        p = fract(p);
        col = atlasCell(cell, p).rgb * (0.6 + 0.6 * uHighS);
        col += (hash12(floor(q * vec2(220.0, 124.0)) + fract(age * 13.0) * 100.0) - 0.5) * 0.4;
    } else if (cell == 25.0) {                                               // Testbild rollt, Rauschen darüber
        p.y = fract(q.y + age * 0.15 * step(0.7, hash12(vec2(floor(age * 2.0), seed))));
        col = atlasCell(cell, p).rgb * (0.7 + 0.3 * bass);
        col += (hash12(q * 300.0 + fract(age * 9.0)) - 0.5) * (0.2 + 0.4 * uHighS);
    } else if (cell == 27.0) {                                               // DNA-Helix wandert
        p.x = fract(q.x - age * (0.15 + 0.3 * bass) + seed);
        col = atlasCell(cell, p).rgb * (0.7 + 0.6 * bass + 0.3 * bp);
    } else if (cell == 31.0) {                                               // rotes Auge: Pupille pulst
        p = 0.5 + (q - 0.5) * (1.0 - 0.12 * bass - 0.08 * bp + 0.05 * sin(age * 0.8));
        col = atlasCell(cell, p).rgb * (0.8 + 0.6 * bass + 0.5 * bp);
    } else {
        col = atlasCell(cell, q).rgb * (0.8 + 0.4 * bass);
    }
    return col;
}

vec3 atlasEyeContent(float hueVar, float age, float seed, vec2 q, float horror, float openMax) {
    // Augen aus dem Atlas (Reihe 0): 0 geradeaus, 1 links, 2 rechts, 3 halb, 4 zu, 5 rot zornig, 6 Glitch, 7 zerfällt
    // Blinzeln = 0 -> 3 -> 4 -> 3 -> 0, Blick = 1/2 (uEyeLook), Black ICE = 5/6/7
    vec2 look = uEyeLook + 0.3 * vec2(sin(age * 1.3 + seed * 9.0), cos(age * 1.1 + seed * 5.0)) * (1.0 - horror);
    float b = fract((age + seed * 7.0) / (3.0 + 3.0 * seed));
    float blink = max(uEyeBlink, sin(min(1.0, b / 0.08) * PI));
    float closed = max(blink, 1.0 - openMax);
    float openCell = look.x < -0.35 ? 1.0 : (look.x > 0.35 ? 2.0 : 0.0);
    if (horror > 0.5) {
        float h = hash12(vec2(floor(age * 3.0 + uBeatStep), seed));
        openCell = h < 0.6 ? 5.0 : (h < 0.85 ? 6.0 : 7.0);
    } else if (step(0.9, hash12(vec2(floor(age * 8.0), seed))) * (0.5 + 0.5 * uBeatPulse) > 0.6) openCell = 6.0;
    float cellA, cellB, mixv;
    if (closed < 0.5) { cellA = openCell; cellB = 3.0; mixv = smoothstep(0.1, 0.5, closed); }
    else { cellA = 3.0; cellB = 4.0; mixv = smoothstep(0.5, 0.85, closed); }
    vec2 p = 0.5 + (q - 0.5) * (1.0 - 0.05 * uBassS - 0.04 * horror);
    vec3 col = mix(atlasCell(cellA, p).rgb, atlasCell(cellB, p).rgb, mixv);
    col = hueShift(col, (hueVar - 0.5) * 1.5 * (1.0 - horror));
    col *= 0.8 + 0.5 * uBassS + 0.3 * uBeatPulse;
    col = mix(col, col * vec3(1.6, 0.4, 0.4), horror * 0.5);
    return col;
}

vec3 eyeContent(float hueVar, float age, float seed, vec2 s, float horror, float openMax) {
    vec2 look = uEyeLook + 0.2 * vec2(sin(age * 1.3 + seed * 9.0), cos(age * 1.1 + seed * 5.0)) * (1.0 - horror);
    look = clamp(look, -1.0, 1.0);
    float b = fract((age + seed * 7.0) / (3.0 + 3.0 * seed));
    float localBlink = sin(min(1.0, b / 0.08) * PI);
    float blink = max(uEyeBlink, localBlink);
    float open = (1.0 - blink) * openMax * (1.0 + 0.15 * horror);
    float lid = 0.78 * open * max(0.0, 1.0 - s.x * s.x / 2.2);
    float inside = smoothstep(0.03, 0.0, abs(s.y) - lid);
    vec2 ic = look * vec2(0.5, 0.3);
    float r = length(s - ic);
    float a = atan(s.y - ic.y, s.x - ic.x);
    float irisR = 0.42 + 0.08 * horror, pupilR = 0.15 + 0.08 * uBassS + 0.14 * horror + 0.05 * uBeatPulse;
    vec3 irisCol = hueShift(vec3(0.1, 0.9, 0.6), hueVar * 6.28 + 0.3 * sin(age * 0.5));
    irisCol = mix(irisCol, vec3(1.0, 0.08, 0.08), horror);
    float rings = 0.5 + 0.5 * sin(r * 70.0 - age * 2.0) * sin(a * 18.0 + age * (0.5 + uBassS));
    rings = mix(rings, noise(vec2(a * 6.0, r * 25.0 - age * 0.5)), 0.5);
    float iris = smoothstep(irisR, irisR - 0.03, r) * smoothstep(pupilR - 0.02, pupilR + 0.02, r);
    vec3 col = vec3(0.02, 0.03, 0.04) + vec3(0.02, 0.05, 0.04) * step(0.92, fract(s.x * 8.0)) + vec3(0.02, 0.05, 0.04) * step(0.92, fract(s.y * 8.0));
    col += irisCol * iris * (0.35 + 0.6 * rings) * (0.8 + 0.4 * uBassS);
    col += irisCol * smoothstep(0.02, 0.0, abs(r - irisR)) * 1.2;                       // Irisring
    col += irisCol * smoothstep(0.015, 0.0, abs(r - irisR - 0.08)) * 0.5 * step(0.5, fract(a * 4.0 / PI + age * 0.3));  // Datenticks
    col = mix(col, vec3(0.0), smoothstep(pupilR + 0.02, pupilR - 0.02, r));
    col += vec3(1.0) * smoothstep(0.06, 0.0, length(s - ic - vec2(-0.12, 0.14))) * 0.5 * (1.0 - 0.6 * horror);
    col += irisCol * 0.08 * exp(-r * 2.0);
    col += irisCol * 0.35 * smoothstep(0.01, 0.0, abs(r - irisR - 0.18)) * step(0.5, fract(a * 12.0 / PI - age * 0.2));
    col *= inside;
    col += irisCol * 0.25 * smoothstep(0.03, 0.0, abs(abs(s.y) - lid)) * step(abs(s.x), 1.5);   // Lidkante
    return col;
}

vec3 countdownContent(float start, float age, float seed, vec2 s, float var2) {
    float n = max(0.0, floor(start - age));
    float frac = fract(start - age);
    int d1 = int(mod(floor(n / 10.0), 10.0)), d0 = int(mod(n, 10.0));
    float bw = 0.24;                                                          // Blockgröße: Ziffer 3x5 Blöcke
    vec2 p0 = (s - vec2(0.12, -0.6)) / vec2(bw * 3.0, bw * 5.0);
    vec2 p1 = (s - vec2(-0.96, -0.6)) / vec2(bw * 3.0, bw * 5.0);
    float px = digitPx(d0, p0) + (n >= 10.0 ? digitPx(d1, p1) : 0.0);
    float urgent = smoothstep(10.0, 0.0, n);
    vec3 c = mix(vec3(1.0, 0.75, 0.2), vec3(1.0, 0.15, 0.1), urgent);
    float blinkf = n <= 0.0 ? step(0.5, fract(age * 6.0)) : (0.7 + 0.3 * step(0.5, frac + 0.5 * urgent));
    vec3 col = vec3(0.03, 0.01, 0.0) + c * px * blinkf * (0.9 + 0.3 * uBeatPulse);
    float bar = step(s.y, -0.75) * step(-0.9, s.y) * step(abs(s.x), 1.6 * clamp(n / max(start, 1.0), 0.0, 1.0));
    col += c * bar * 0.7;
    col += c * step(0.9, abs(s.y) - 0.02) * 0.15 * step(0.5, fract(s.x * 20.0));
    if (n <= 0.0) col = mix(col, vec3(1.0, 0.1, 0.1), 0.6 * step(0.5, fract(age * 8.0)));
    return col;
}

vec3 warnContent(float var, float age, float seed, vec2 s) {
    vec3 c = var < 2.0 ? vec3(1.0, 0.8, 0.1) : vec3(1.0, 0.15, 0.1);
    float blink = step(0.5, fract(age * (2.0 + 2.0 * uBassS)));
    float stripes = step(0.5, fract((s.x + s.y) * 4.0 + age * 0.5));
    vec3 col = c * stripes * 0.12 * step(0.82, abs(s.y));
    float d = sdTri(s * vec2(1.0, 1.0) - vec2(0.0, -0.1), 0.6);
    float tri = smoothstep(0.03, 0.0, abs(d)) + smoothstep(0.0, -0.03, d) * 0.15;
    col += c * tri * (0.4 + 0.6 * blink);
    float bang = step(abs(s.x), 0.06) * (step(abs(s.y + 0.0), 0.28) * step(-0.25, s.y) + step(abs(s.y + 0.42), 0.06));
    col += c * bang * (0.5 + 0.5 * blink) * 1.2;
    col += c * 0.5 * step(0.5, fract(s.x * 16.0)) * step(0.9, -s.y) * step(0.5, fract(age * 4.0 + floor(s.x * 16.0) * 0.1));
    return col;
}

vec3 noiseContent(float var, float age, float seed, vec2 q, vec2 s) {
    float n = hash12(floor(q * vec2(220.0, 124.0)) + fract(age * 13.0 + seed) * 100.0);
    float band = smoothstep(0.1, 0.0, abs(fract(q.y - age * 0.3) - 0.5)) ;
    vec3 col = vec3(n) * (0.35 + 0.5 * band + 0.4 * uHighS);
    if (var == 1.0) col *= vec3(0.3, 1.0, 0.4);
    else if (var == 2.0) col *= vec3(1.0, 0.25, 0.2);
    else if (var == 3.0) {                                                   // Testbild: Farbbalken unter dem Rauschen
        float k = floor(q.x * 7.0);
        vec3 bar = k < 1.0 ? vec3(0.8) : (k < 2.0 ? vec3(0.8, 0.8, 0.0) : (k < 3.0 ? vec3(0.0, 0.8, 0.8) : (k < 4.0 ? vec3(0.0, 0.8, 0.0) :
                   (k < 5.0 ? vec3(0.8, 0.0, 0.8) : (k < 6.0 ? vec3(0.8, 0.0, 0.0) : vec3(0.0, 0.0, 0.8))))));
        col = mix(bar * step(0.25, q.y), vec3(n), 0.35 + 0.3 * uHighS);
    }
    col *= 0.85 + 0.15 * sin(q.y * 300.0 + age * 30.0);
    return col;
}

vec3 crossContent(float var, float age, float seed, vec2 s) {
    vec3 c = var < 2.0 ? vec3(0.3, 1.0, 0.4) : vec3(1.0, 0.2, 0.15);
    vec2 pos = vec2(sin(age * 0.7 + seed * 6.0) * 0.9, cos(age * 0.9 + seed * 3.0) * 0.5);
    pos += vec2(sin(age * 5.0), cos(age * 4.0)) * 0.03;
    vec3 col = c * 0.06 * (step(0.95, fract(s.x * 4.0)) + step(0.95, fract(s.y * 4.0)));
    vec2 d = s - pos;
    float lines = smoothstep(0.012, 0.0, abs(d.x)) + smoothstep(0.012, 0.0, abs(d.y));
    float r = length(d);
    float ring = smoothstep(0.015, 0.0, abs(r - 0.3 - 0.08 * uBassS)) + smoothstep(0.012, 0.0, abs(r - 0.55)) * step(0.5, fract(atan(d.y, d.x) * 3.0 / PI + age * 0.5));
    float lock = uBeatPulse * smoothstep(0.02, 0.0, abs(r - 0.2));
    col += c * (lines * 0.5 * step(r, 0.9) + ring + lock * 1.5);
    col += c * smoothstep(0.04, 0.0, r) * (0.5 + 0.5 * step(0.5, fract(age * 3.0)));
    col += c * 0.4 * step(0.5, fract(s.x * 12.0)) * step(0.88, s.y) * step(abs(s.x), 0.6 + 0.3 * sin(age));   // Datenzeile
    return col;
}

vec3 barcodeContent(float var, float age, float seed, vec2 q, vec2 s) {
    float col1 = floor(q.x * 64.0);
    float bar = step(0.45, hash12(vec2(col1, seed * 20.0))) * step(abs(s.y), 0.5);
    float w = step(0.15, fract(q.x * 64.0));
    vec3 col = vec3(0.9, 0.95, 1.0) * bar * w * (0.6 + 0.2 * uBassS);
    float scan = 0.5 + 0.45 * sin(age * 1.5 + seed * 6.0);
    col += vec3(1.0, 0.1, 0.1) * smoothstep(0.012, 0.0, abs(q.x - scan)) * step(abs(s.y), 0.6) * 1.2;
    col += vec3(1.0, 0.1, 0.1) * 0.15 * exp(-abs(q.x - scan) * 20.0) * step(abs(s.y), 0.6);
    col += vec3(0.9) * 0.4 * step(0.5, fract(q.x * 20.0)) * step(0.62, abs(s.y)) * step(abs(s.y), 0.68);
    col += vec3(1.0, 0.2, 0.2) * uBeatPulse * bar * 0.5;
    return col;
}

vec3 faceContent(float var, float age, float seed, vec2 q, vec2 s) {
    float fh = 1.8, fw = fh * uFaceSize.x / uFaceSize.y;
    vec2 fq = s / vec2(fw, fh) + 0.5;
    vec3 col = vec3(0.03, 0.0, 0.0);
    col += vec3(0.3, 0.05, 0.05) * (step(0.95, fract(q.x * 8.0)) + step(0.95, fract(q.y * 6.0))) * 0.3;
    if (uFaceOK > 0.5 && fq.x > 0.0 && fq.x < 1.0 && fq.y > 0.0 && fq.y < 1.0) {
        float row = floor(fq.y * 40.0);
        fq.x += (hash12(vec2(row, floor(age * 10.0))) - 0.5) * 0.1 * step(0.8, hash12(vec2(row, floor(age * 5.0)))) * uBeatPulse;
        vec4 f = bilin(uFaceTex, fq * uFaceSize, uFaceSize, vec2(0.0), uFaceSize - 1.0);
        float gl = dot(f.rgb, vec3(0.33));
        col = mix(col, vec3(gl) * vec3(1.0, 0.35, 0.3) * 1.1, max(f.a, 0.3));
    }
    float scanY = fract(age * 0.35 + seed);
    col += vec3(1.0, 0.3, 0.3) * smoothstep(0.02, 0.0, abs(q.y - scanY)) * 0.8;
    col += vec3(1.0, 0.2, 0.2) * (smoothstep(0.006, 0.0, abs(s.x)) + smoothstep(0.006, 0.0, abs(s.y))) * step(length(s), 0.45) * (0.5 + 0.5 * sin(age * 6.0));
    col += vec3(1.0, 0.2, 0.2) * smoothstep(0.01, 0.0, abs(length(s) - 0.5 - 0.05 * uBassS)) * 0.6;
    float bars = step(0.5, hash12(vec2(floor(q.x * 60.0), seed))) * step(q.y, 0.1) * step(0.03, q.y);
    col = mix(col, vec3(1.0, 0.9, 0.9), bars * 0.8);
    col += vec3(1.0, 0.1, 0.1) * step(0.9, q.y) * step(abs(q.x - 0.5), 0.3) * step(0.5, fract(age * 2.0)) * 0.4 * step(0.5, fract(q.x * 24.0));
    return col;
}

vec3 ekgContent(float var, float age, float seed, vec2 q, vec2 s, float flatK) {
    vec3 c = uPhase > 1.5 ? vec3(1.0, 0.2, 0.2) : vec3(0.25, 1.0, 0.4);
    vec3 col = c * 0.07 * (step(0.93, fract(q.x * 16.0)) + step(0.93, fract(q.y * 9.0)));
    float sp = 0.3 + 0.3 * uBassS;
    float u = fract(q.x * 2.0 + age * sp + seed);
    float amp = (0.6 + 0.8 * uBassS + 0.4 * uBeatPulse) * (1.0 - flatK);
    float y = amp * (0.08 * exp(-sq((u - 0.12) * 30.0)) + 0.75 * exp(-sq((u - 0.25) * 55.0)) - 0.2 * exp(-sq((u - 0.31) * 60.0)) + 0.15 * exp(-sq((u - 0.5) * 20.0)));
    y -= 0.1;
    float line = smoothstep(0.04, 0.0, abs(s.y - y));
    float head = fract(q.x - age * sp * 0.5);
    col += c * line * (0.5 + 0.5 * (1.0 - head)) * 1.2;
    col += c * 0.15 * exp(-abs(s.y - y) * 8.0) * (1.0 - head);
    col += c * smoothstep(0.05, 0.0, length(s - vec2(1.4, 0.75))) * step(0.5, fract(age * (1.0 + uBassS))) * (1.0 - flatK);
    if (flatK > 0.5) col += c * 0.5 * step(0.5, fract(age * 1.5)) * step(0.5, fract(q.x * 10.0)) * step(0.85, q.y) * step(abs(s.x), 0.9);
    return col;
}

vec3 daemonContent(float cell, float age, float seed, vec2 s, float horror) {
    float grow = 0.65 + 0.35 * min(1.0, age / 6.0) + 0.2 * uBeatPulse;
    vec2 d = s / (1.25 * grow);
    d.y += 0.1;
    if (hash12(vec2(seed, 3.0)) < 0.5) d.x = -d.x;
    float row = floor(s.y * 25.0);
    d.x += (hash12(vec2(row, floor(age * 12.0))) - 0.5) * 0.12 * step(0.8, hash12(vec2(row, floor(age * 4.0) + seed))) * (0.3 + horror);
    vec4 f = creature(cell, d);
    vec3 col = vec3(0.0, 0.03, 0.06) + vec3(0.0, 0.1, 0.15) * (step(0.93, fract(s.x * 5.0)) + step(0.93, fract(s.y * 5.0))) * 0.4;
    vec3 fc = hueShift(f.rgb, seed * 2.0 + 0.3 * sin(age)) * (0.7 + 0.6 * uBassS + 0.5 * uBeatPulse);
    fc = mix(fc, 1.0 - fc, horror * uBeatPulse * 0.5);
    col = mix(col, fc, f.a);
    col *= 0.8 + 0.2 * sin(s.y * 200.0 + age * 15.0);
    return col;
}

vec3 godContent(float cell, float age, float seed, vec2 s) {
    vec2 d = s / (0.95 + 0.06 * sin(age * 1.3) + 0.06 * uBassS);
    float row = floor(d.y * 30.0);
    d.x += (hash12(vec2(row, floor(age * 12.0))) - 0.5) * 0.08 * step(0.75, hash12(vec2(row, floor(age * 4.0))));
    vec4 f = godCell(cell, d);
    float gl = dot(f.rgb, vec3(0.33));
    vec3 fc = mix(f.rgb, vec3(1.0, 0.1, 0.15) * gl * 1.8, 0.6);
    fc = mix(fc, 1.0 - f.rgb, 0.3 * uBeatPulse);
    fc += vec3(1.0, 0.3, 0.3) * smoothstep(0.6, 0.95, gl) * (0.4 + 0.6 * uBassS);
    fc *= 0.8 + 0.5 * (0.5 + 0.5 * sin(age * 8.0 + uBeatStep)) * uBassS;
    vec3 col = vec3(0.05, 0.0, 0.01) + vec3(0.3, 0.02, 0.02) * hash12(floor(s * 20.0) + floor(age * 6.0)) * 0.3;
    col = mix(col, fc, f.a);
    col *= 0.85 + 0.15 * sin(s.y * 300.0 + age * 20.0);
    return col;
}

vec3 catContent(float age, float seed, vec2 s) {
    float h = age / 5.0;
    vec2 d = s / 0.95;
    d.y -= 0.05;
    vec4 f = mix(figCell(uOwl.x, d), figCell(uOwl.y, d), uOwl.z);
    vec3 col = vec3(0.04, 0.0, 0.08) + vec3(0.7, 0.3, 1.0) * exp(-length(s) * 2.0) * 0.25 * sin(h * PI);
    col += vec3(0.5, 0.2, 0.8) * 0.15 * (step(0.93, fract(s.x * 6.0 + age * 0.5)) + step(0.93, fract(s.y * 6.0)));
    col = mix(col, f.rgb * 1.1, f.a * (uFigOK > 0.5 ? 1.0 : 0.0));
    return col;
}

vec3 bootContent(float age, float seed, vec2 q) {
    float rowY = floor((1.0 - q.y) * 24.0);
    float shown = step(rowY, age * 10.0) * step(rowY, 22.0);
    float cellX = floor(q.x * 60.0);
    float inLine = step(0.5, fract(q.y * 24.0 + 0.25)) * step(0.2, fract(q.x * 60.0));
    float txt = step(0.5, hash12(vec2(cellX, rowY + seed * 50.0))) * step(cellX, 4.0 + 30.0 * hash12(vec2(rowY, seed))) * step(1.0, cellX) * inLine;
    float cur = step(abs(rowY - floor(age * 10.0)), 0.5) * step(cellX, 5.0 + 30.0 * hash12(vec2(rowY, seed))) * step(4.0 + 30.0 * hash12(vec2(rowY, seed)), cellX) * step(0.5, fract(age * 4.0));
    vec3 col = vec3(0.0, 0.03, 0.0) + vec3(0.2, 0.95, 0.4) * (txt * shown * 0.8 + cur);
    col += vec3(1.0, 0.7, 0.2) * txt * shown * step(0.9, hash12(vec2(rowY, seed * 3.0)));   // einzelne Warnzeilen gelb
    return col;
}

vec3 standbyContent(float age, float seed, vec2 q) {
    vec3 col = vec3(0.0, 0.01, 0.01);
    col += vec3(0.0, 0.06, 0.05) * (step(0.97, fract(q.x * 10.0)) + step(0.97, fract(q.y * 6.0))) * 0.3;
    vec2 cp = vec2(0.08, 0.82);
    float cur = step(abs(q.x - cp.x), 0.012) * step(abs(q.y - cp.y), 0.04) * step(0.5, fract(age * 1.2 + seed));
    col += vec3(0.4, 0.9, 0.6) * cur;
    float dot1 = smoothstep(0.012, 0.0, length((q - vec2(0.94, 0.9)) * vec2(1.78, 1.0))) * step(0.9, fract(age * 0.25 + seed));
    col += vec3(0.9, 0.3, 0.2) * dot1;
    return col;
}

vec3 screenContent(int idx, vec4 c, vec2 q, vec2 s, float t, float horror, int phase, float k) {
    int kind = int(c.x + 0.5);
    float var = c.y, age = t - c.z, seed = c.w;
    float openMax = 1.0;
    float flatK = 0.0;
    // Globale Zustände überstimmen den Inhalt
    if (phase == 3) { kind = 8; age = uPhaseT; flatK = smoothstep(0.35, 0.5, k); }
    else if (uEyesT >= 0.0) {
        age = uEyesT;
        if (hash12(vec2(seed, 11.0)) < 0.45) { kind = hash12(vec2(seed, 12.0)) < 0.5 ? 1 : 15; openMax = smoothstep(1.0, 4.0 + 3.0 * seed, uEyesT); var = seed; }
        else kind = 9;
    }
    else if (uVomitT >= 0.0) { kind = 13; age = uVomitT; }
    else if (uHelpT >= 0.0) { kind = 12; age = uHelpT; }
    else if (uLive < 0.3) { kind = 14; age = t; }
    if (age < 0.08) {                                                         // 80 ms Schwarz mit Zeilenkollaps
        float n = hash12(q * 300.0 + t) * 0.3;
        return vec3(n) * step(0.03, age) + vec3(0.6, 0.9, 0.8) * smoothstep(0.04, 0.0, abs(s.y)) * (1.0 - age / 0.08);
    }
    vec3 col;
    if (kind == 0) col = uScreenOK > 0.5 ? atlasContent(var, age, seed, q, s, horror) : noiseContent(1.0, age, seed, q, s);
    else if (kind == 15) col = uScreenOK > 0.5 ? atlasEyeContent(var, age, seed, q, horror, openMax) : eyeContent(var, age, seed, s, horror, openMax);
    else if (kind == 1) col = eyeContent(var, age, seed, s, horror, openMax);
    else if (kind == 2) col = countdownContent(var, age, seed, s, 0.0);
    else if (kind == 3) col = warnContent(var, age, seed, s);
    else if (kind == 4) col = noiseContent(var, age, seed, q, s);
    else if (kind == 5) col = crossContent(var, age, seed, s);
    else if (kind == 6) col = barcodeContent(var, age, seed, q, s);
    else if (kind == 7) col = faceContent(var, age, seed, q, s);
    else if (kind == 8) col = ekgContent(var, age, seed, q, s, flatK);
    else if (kind == 10) col = daemonContent(var, age, seed, s, horror);
    else if (kind == 11) col = uGodOK > 0.5 ? godContent(var, age, seed, s) : eyeContent(0.0, age, seed, s, 1.0, 1.0);
    else if (kind == 12) col = catContent(age, seed, s);
    else if (kind == 13) col = bootContent(age, seed, q);
    else if (kind == 14) col = standbyContent(age, seed, q);
    else col = vec3(0.012, 0.016, 0.022);                                      // aus: kalter Restschimmer
    // Schirm-Look: Scanlines, Einschaltblende, Randabfall, Beat-Helligkeit
    col *= 1.0 - 0.18 * step(0.5, fract(q.y * 90.0));
    col *= smoothstep(0.08, 0.25, age) * 0.75 + 0.25;
    float vig = smoothstep(0.0, 0.05, min(q.x, 1.0 - q.x)) * smoothstep(0.0, 0.08, min(q.y, 1.0 - q.y));
    col *= 0.7 + 0.3 * vig;
    col *= 1.15 + 0.2 * uBeatPulse;
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
    int ev = int(uEvent.x + 0.5);
    float evk = ev > 0 ? clamp((t - uEvent.y) / max(uEvent.z, 0.1), 0.0, 1.0) : 1.0;
    // ---- Kamera: Atmen, Herzschlag-Zoom, Bildsprünge auf den Beat, Reboot rollt das Bild
    vec2 uv = vUv;
    float heart = uBassS * live;
    uv = 0.5 + (uv - 0.5) * (1.0 - 0.05 * heart * poison - 0.02 * sin(t * 0.9) * poison);
    uv += uCut * uBeatPulse * (0.3 + horror);
    if (uVomitT >= 0.0) {
        float v = sin(min(1.0, uVomitT / 3.0) * PI);
        uv.y = fract(uv.y + v * uVomitT * 0.25);
    }
    // Ränder verbiegen sich mit den Mitten, die Vergiftung lässt alles wabern
    float edge = smoothstep(0.2, 0.5, length(vUv - 0.5));
    uv += vec2(sin(uv.y * 12.0 + t * 1.3), cos(uv.x * 10.0 - t * 1.1)) * 0.012 * (uMidS * 0.6 + 0.4 * poison) * edge;
    uv += (vec2(fbm(uv * 3.0 + t * 0.2), fbm(uv * 3.0 - t * 0.17 + 5.0)) - 0.5) * 0.03 * poison;
    vec4 sc = scene(uv);
    vec3 col = sc.rgb;
    float screenMask = 1.0 - sc.a;
    // ---- Doppelbild: zweites, verschobenes und umgefärbtes Bild
    float dbl = poison * (0.6 + 0.4 * sin(t * 0.7));
    vec2 off = vec2(0.012 + 0.02 * uMidS, 0.006) * dbl;
    vec3 ghost = vec3(scene(uv + off).r, col.g, scene(uv - off).b);
    col = mix(col, ghost, 0.7 * dbl);
    col *= 1.0 - 0.12 * poison * step(0.5, fract(vUv.y * 300.0));
    // ---- Rote Warnlampen pulsen zum Bass, Kabel (helle feine Stellen) funkeln in den Höhen
    float lum = dot(col, vec3(0.3, 0.55, 0.15));
    float redness = smoothstep(0.15, 0.5, col.r - max(col.g, col.b));
    col += vec3(1.0, 0.1, 0.05) * redness * (0.3 * heart + 0.5 * uBeatPulse * poison + 0.4 * (ev == 2 ? 1.0 - evk : 0.0));
    float wire = smoothstep(0.12, 0.3, lum) * (1.0 - redness) * step(0.75, hash12(floor(vUv * 180.0) + floor(t * 12.0)));
    col += vec3(0.5, 0.9, 1.0) * wire * uHighS * 0.6;
    // ---- Giftfarben: Grün/Violett kippt mit der Vergiftung, Drop = Rot-Schwarz-Negativ
    vec3 toxic = mix(vec3(1.0, 0.15, 0.2), vec3(0.2, 0.8, 1.0), 0.5 + 0.5 * sin(t * 0.4 + uv.y * 3.0 + uBeatStep * 0.4));
    col = mix(col, mix(col, toxic * lum * 1.6, 0.5), poison * 0.7);
    col = mix(col, vec3(lum), poison * 0.2);
    // ---- Flatline: der Raum geht fast aus, Herz glimmt rot
    float rr = length((vUv - 0.5) * vec2(1.0, 1.2));
    if (phase == 3) {
        float dark = smoothstep(0.0, 0.15, k) * (1.0 - smoothstep(0.75, 1.0, k));
        col = mix(col, col * 0.08 + vec3(0.2, 0.02, 0.05) * heart * exp(-rr * 3.0), dark);
    }
    // ---- Stecker gezogen: Dunkelheit, farbige Nachbilder atmen mit der Musik
    if (uEyes > 0.0) {
        vec3 inner = vec3(0.0);
        for (int i = 0; i < 4; i++) {
            float fi = float(i);
            vec2 bp = vec2(0.5, 0.5) + vec2(sin(t * 0.4 + fi * 1.6), cos(t * 0.3 + fi * 2.1)) * 0.25;
            float g = exp(-length((vUv - bp) * vec2(aspect, 1.0)) * (4.0 - 2.0 * uBassS));
            inner += hueShift(vec3(0.1, 0.3, 0.6), fi * 1.5 + t * 0.5) * g * (0.3 + 0.7 * uBassS + 0.5 * uBeatPulse);
        }
        col = mix(col, inner * 0.35, uEyes * 0.95);
    }
    // ---- Bildschirme: Inhalt exakt in der Schirmform (Alpha-Maske), Rechteck liefert die Koordinaten
    if (screenMask > 0.01) {
        int found = -1;
        vec4 rect = vec4(0.0);
        int n = int(min(uNScr, 12.0) + 0.5);
        for (int i = 0; i < 12; i++) {
            if (i >= n) break;
            vec4 r = scrAt(i);
            if (uv.x >= r.x - 0.004 && uv.x <= r.z + 0.004 && uv.y >= r.y - 0.004 && uv.y <= r.w + 0.004) { found = i; rect = r; break; }
        }
        if (found >= 0) {
            vec2 q = (uv - rect.xy) / max(rect.zw - rect.xy, vec2(0.001));
            float ra = (rect.z - rect.x) * aspect / max(rect.w - rect.y, 0.001);
            vec2 s = (q - 0.5) * 2.0 * vec2(ra, 1.0);
            vec3 content = screenContent(found, scrCAt(found), q, s, t, horror, phase, k);
            content = mix(content, 1.0 - content, uBeatPulse * uBeatPulse * horror * step(0.5, fract(t * 25.0 + uBeatStep)) * 0.5);
            col = mix(col, content, screenMask);
        } else {
            col = mix(col, vec3(0.0), screenMask);
        }
    }
    // ---- Negativflackern auf den Beat (Horror: hart, Vergiftung: kurz), Drop = Rot-Schwarz
    float neg = uBeatPulse * uBeatPulse * (0.25 * poison + 0.9 * horror) * live;
    col = mix(col, 1.0 - col, neg * step(0.5, fract(t * 25.0 + uBeatStep)) * (1.0 - 0.7 * screenMask));
    col = mix(col, vec3(1.0, 0.1, 0.05) * (1.0 - lum), uFlash * 0.8 * (1.0 - 0.6 * screenMask));
    // ---- Rauschsturm-Ereignis: der ganze Raum flimmert
    if (ev == 3) col += (hash12(vUv * 400.0 + t) - 0.5) * 0.25 * (1.0 - evk);
    // ---- Fliegen und Rauschen mit den Höhen
    int nf = 6 + int(poison * 14.0);
    for (int i = 0; i < 20; i++) {
        if (i >= nf) break;
        float fi = float(i);
        float h1 = hash12(vec2(fi, 41.0)), h2 = hash12(vec2(fi, 43.0));
        vec2 c = vec2(0.5, 0.5) + vec2(cos(t * (1.5 + h1 * 3.0) + fi * 7.0), sin(t * (1.1 + h2 * 2.0) + fi * 3.0)) * vec2(0.3 + 0.2 * h1, 0.25 + 0.2 * h2);
        c += vec2(0.02 * sin(t * 17.0 + fi), 0.02 * cos(t * 19.0 + fi));
        float g = smoothstep(0.004 + 0.004 * horror, 0.0, length((uv - c) * vec2(aspect, 1.0)));
        col = mix(col, vec3(0.05, 0.03, 0.06), g * (0.3 + 0.7 * uHighS) * poison);
    }
    col += (noise(vUv * 300.0 + t * 50.0) - 0.5) * (0.05 * poison + 0.12 * uHighS * poison);
    // ---- Ranken kriechen von den Rändern herein, Tunnelblick auf den Bass
    float tendril = fbm(vec2(atan(vUv.y - 0.5, vUv.x - 0.5) * 3.0, rr * 6.0 - t * 0.1) + uSeed);
    float vines = smoothstep(0.52 - 0.22 * poison, 0.62, rr + (tendril - 0.5) * 0.25);
    col = mix(col, vec3(0.01, 0.0, 0.02), vines * (0.5 + 0.5 * poison) * 0.7 * (1.0 - 0.5 * screenMask));
    float tunnel = smoothstep(0.25 + 0.3 * (1.0 - heart) - 0.15 * poison, 0.75, rr) * (0.3 + 0.7 * poison) * (0.5 + 0.5 * heart);
    col *= 1.0 - tunnel * (1.0 - 0.5 * screenMask);
    // ---- Gegenmaßnahme: kurz grünes, ruhiges Bild
    if (uReliefT >= 0.0) col = mix(col, col * vec3(0.8, 1.1, 0.9) + vec3(0.0, 0.03, 0.01), uRelief * 0.6);
    // ---- Jack out: klares, kaltes Bild
    col = mix(col, col * vec3(0.8, 0.95, 1.2) + 0.02, uShock * 0.8);
    // ---- Stille: schweres Atmen, Dunkelheit kriecht (Schirme bleiben als Standby sichtbar)
    float breath = 0.5 + 0.5 * sin(t * 0.6);
    col *= mix(mix(0.35 + 0.25 * breath, 0.8, screenMask), 1.0, live);
    col *= 1.0 - 0.25 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
