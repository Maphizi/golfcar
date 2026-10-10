#version 140
// ERROR – grüner Code überall, der zusammenbricht: Zyklus aus Code-Phase (6 Varianten), Zusammenbruch
// (Glitches, Risse, Rot), Fehlerbild (6 Varianten), Wiederherstellung und Neustart. Reagiert auf Musik:
// Bass = Tempo/Helligkeit/Zittern, Mitten/Höhen = Zeichenflackern und Funken, Beat = Blitze und Risse.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
// Ablauf kommt vom Controller (visualizers/scenes/error.py):
uniform float uSeed;         // Zufall pro Start und Durchlauf
uniform float uPhase;        // 1 Code, 2 Zusammenbruch, 3 Fehler, 4 Wiederherstellung, 5 Neustart,
                             // 6 Eingabe, 7 Virus, 8 Schilde, 9 Stabil, 10 Alarm, 11 Eindringling
uniform float uPhaseT, uPhaseLen;
uniform float uCodeVar, uErrVar;   // Varianten 0..5
uniform float uCodeT, uCodeProg;   // Zeit und Fortschritt der laufenden Code-Szene
uniform float uPrompt;       // 1 oben, 2 unten, 3 links, 4 rechts, 5 Start
uniform float uOutcome;      // 0 offen, 1 gut, 2 schlecht
uniform float uGlitch;       // Stärke des Zusammenbruchs
uniform float uPct;          // Prozentwert (Infektion, Schilde, Ortung)
uniform float uWordA, uWordB;      // Wort-IDs für Banner

const float ROWS = 40.0;     // Textzeilen im Code-Raster
const vec3 GRN = vec3(0.25, 1.0, 0.35);
const vec3 RED = vec3(1.0, 0.12, 0.08);
const vec3 AMB = vec3(1.0, 0.75, 0.2);
float gSeed = 0.0;           // pro Durchlauf anders, damit sich der Code nicht wiederholt

// Zeichen: 0-25 A-Z, 26-35 0-9, 36 Leer, dann .:-[]#%/><_=+*!?{}();"~| und Backslash
const int NGLYPH = 62;
int FONT[62] = int[62](589284910, 521715247, 1007715390, 521717295, 1041284159, 34651199, 1025041470, 588840497, 1044517023, 211034396, 588553521, 1041269793, 588830577, 589092465, 488162862, 34651695, 748340782, 580042287, 520632382, 138547359, 488162865, 145278513, 599442993, 588583249, 138547537, 1041305887, 488232750, 474091716, 1042424366, 520632847, 277849420, 520633407, 488160302, 69345823, 488159790, 487094830, 0, 134217728, 4194432, 31744, 471926862, 478421262, 368389098, 866193779, 1118480, 1118273, 17043728, 1040187392, 1016800, 145536, 703136, 134353028, 134357550, 406980748, 205660294, 272765064, 71438466, 71303296, 330, 283712, 138547332, 17043521);
int WORDS[582] = int[582](4, 17, 17, 14, 17, 18, 24, 18, 19, 4, 12, 5, 4, 7, 11, 4, 17, 10, 4, 17, 13, 4, 11, 36, 15, 0, 13, 8, 2, 25, 20, 6, 17, 8, 5, 5, 36, 21, 4, 17, 22, 4, 8, 6, 4, 17, 19, 5, 0, 19, 0, 11, 2, 14, 17, 4, 36, 3, 20, 12, 15, 13, 4, 20, 18, 19, 0, 17, 19, 18, 8, 6, 13, 0, 11, 36, 21, 4, 17, 11, 14, 17, 4, 13, 18, 15, 4, 8, 2, 7, 4, 17, 5, 4, 7, 11, 4, 17, 20, 13, 1, 4, 10, 0, 13, 13, 19, 4, 17, 36, 1, 4, 5, 4, 7, 11, 0, 1, 1, 17, 20, 2, 7, 10, 4, 17, 13, 36, 8, 13, 18, 19, 0, 1, 8, 11, 3, 0, 19, 4, 13, 36, 10, 14, 17, 17, 20, 15, 19, 22, 0, 17, 13, 20, 13, 6, 18, 2, 7, 8, 11, 3, 4, 36, 26, 43, 18, 19, 0, 2, 10, 36, 14, 21, 4, 17, 5, 11, 14, 22, 18, 4, 6, 12, 4, 13, 19, 0, 19, 8, 14, 13, 36, 5, 0, 20, 11, 19, 15, 17, 20, 4, 5, 18, 20, 12, 12, 4, 36, 5, 0, 11, 18, 2, 7, 1, 20, 18, 36, 4, 17, 17, 14, 17, 0, 2, 7, 19, 20, 13, 6, 5, 4, 7, 11, 4, 17, 2, 14, 3, 4, 15, 0, 13, 8, 2, 19, 14, 19, 0, 11, 0, 20, 18, 5, 0, 11, 11, 13, 8, 2, 7, 19, 36, 1, 4, 7, 4, 1, 1, 0, 17, 40, 36, 14, 10, 36, 41, 40, 22, 0, 17, 13, 41, 40, 5, 0, 8, 11, 41, 26, 23, 4, 17, 17, 36, 22, 8, 4, 3, 4, 17, 7, 4, 17, 18, 19, 4, 11, 11, 20, 13, 6, 18, 24, 18, 19, 4, 12, 4, 8, 13, 6, 0, 1, 4, 36, 4, 17, 5, 14, 17, 3, 4, 17, 11, 8, 2, 7, 3, 17, 20, 4, 2, 10, 4, 14, 1, 4, 13, 20, 13, 19, 4, 13, 11, 8, 13, 10, 18, 17, 4, 2, 7, 19, 18, 18, 19, 0, 17, 19, 25, 20, 6, 17, 8, 5, 5, 36, 6, 4, 22, 0, 4, 7, 17, 19, 5, 0, 11, 18, 2, 7, 4, 36, 4, 8, 13, 6, 0, 1, 4, 10, 4, 8, 13, 4, 36, 0, 13, 19, 22, 14, 17, 19, 18, 24, 18, 19, 4, 12, 36, 20, 4, 1, 4, 17, 13, 8, 12, 12, 19, 21, 8, 17, 20, 18, 36, 4, 13, 19, 3, 4, 2, 10, 19, 16, 20, 0, 17, 0, 13, 19, 0, 4, 13, 4, 18, 2, 7, 8, 11, 3, 4, 36, 0, 20, 18, 6, 4, 18, 4, 19, 25, 19, 18, 2, 7, 8, 11, 3, 4, 36, 22, 8, 4, 3, 4, 17, 36, 14, 1, 4, 13, 4, 8, 13, 3, 17, 8, 13, 6, 11, 8, 13, 6, 36, 8, 12, 36, 18, 24, 18, 19, 4, 12, 14, 17, 19, 20, 13, 6, 8, 18, 14, 11, 8, 4, 17, 19, 18, 24, 18, 19, 4, 12, 36, 18, 19, 0, 1, 8, 11, 0, 11, 0, 17, 12, 18, 15, 4, 17, 17, 4, 36, 0, 10, 19, 8, 21, 5, 4, 7, 11, 0, 11, 0, 17, 12, 8, 13, 5, 8, 25, 8, 4, 17, 19, 25, 4, 8, 19);
// Wörter: 0=ERROR, 1=SYSTEMFEHLER, 2=KERNEL PANIC, 3=ZUGRIFF VERWEIGERT, 4=FATAL, 5=CORE DUMP, 6=NEUSTART, 7=SIGNAL VERLOREN, 8=SPEICHERFEHLER, 9=UNBEKANNTER BEFEHL, 10=ABBRUCH, 11=KERN INSTABIL, 12=DATEN KORRUPT, 13=WARNUNG, 14=SCHILDE 0%, 15=STACK OVERFLOW, 16=SEGMENTATION FAULT, 17=PRUEFSUMME FALSCH, 18=BUS ERROR, 19=ACHTUNG, 20=FEHLERCODE, 21=PANIC, 22=TOTALAUSFALL, 23=NICHT BEHEBBAR, 24=[ OK ], 25=[WARN], 26=[FAIL], 27=0X, 28=ERR , 29=WIEDERHERSTELLUNG, 30=SYSTEM, 31=EINGABE ERFORDERLICH, 32=DRUECKE, 33=OBEN, 34=UNTEN, 35=LINKS, 36=RECHTS, 37=START, 38=ZUGRIFF GEWAEHRT, 39=FALSCHE EINGABE, 40=KEINE ANTWORT, 41=SYSTEM UEBERNIMMT, 42=VIRUS ENTDECKT, 43=QUARANTAENE, 44=SCHILDE AUSGESETZT, 45=SCHILDE WIEDER OBEN, 46=EINDRINGLING IM SYSTEM, 47=ORTUNG, 48=ISOLIERT, 49=SYSTEM STABIL, 50=ALARM, 51=SPERRE AKTIV, 52=FEHLALARM, 53=INFIZIERT, 54=ZEIT
int WSTART[55] = int[55](0, 5, 17, 29, 47, 52, 61, 69, 84, 98, 116, 123, 136, 149, 156, 166, 180, 198, 215, 224, 231, 241, 246, 258, 272, 278, 284, 290, 292, 296, 313, 319, 339, 346, 350, 355, 360, 366, 371, 387, 402, 415, 432, 446, 457, 475, 494, 516, 522, 530, 543, 548, 560, 569, 578);
int WLEN[55] = int[55](5, 12, 12, 18, 5, 9, 8, 15, 14, 18, 7, 13, 13, 7, 10, 14, 18, 17, 9, 7, 10, 5, 12, 14, 6, 6, 6, 2, 4, 17, 6, 20, 7, 4, 5, 5, 6, 5, 16, 15, 13, 17, 14, 11, 18, 19, 22, 6, 8, 13, 5, 12, 9, 9, 4);

// ---- Hashes ohne sin(): auf jeder GPU gleich
float hash1(float n) { n = fract((n + gSeed) * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx + gSeed) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p) { p = fract((p + gSeed) * vec3(0.1031, 0.1030, 0.0973)); p += dot(p, p.yxz + 33.33); return fract((p.x + p.y) * p.z); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
float wave(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.75)).r * 2.0 - 1.0; }

// ---- Zeichen: Zelle 6x8 Einheiten, Glyphe 5x6, l = lokale Koordinate 0..1 (y nach oben)
float glyphBit(int code, vec2 l) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return 0.0;
    int cx = int(l.x * 6.0);
    int ry = int((1.0 - l.y) * 8.0) - 1;
    if (cx > 4 || ry < 0 || ry > 5) return 0.0;
    return float((FONT[code] >> (ry * 5 + cx)) & 1);
}
int randCode(float seed) { return int(hash1(seed) * 36.0); }                        // A-Z, 0-9
int hexCode(float seed) { int v = int(hash1(seed) * 16.0); return v < 10 ? 26 + v : v - 10; }
// Wort id an Pixelposition. org = linke untere Ecke (oder Mitte unten bei center), cs = Zellhöhe in Pixeln
float word(int id, vec2 fc, vec2 org, float cs, float center, int maxn) {
    float cw = cs * 0.75;
    int n = min(WLEN[id], maxn);
    if (center > 0.5) org.x -= float(WLEN[id]) * cw * 0.5;
    vec2 q = (fc - org) / vec2(cw, cs);
    if (q.y < 0.0 || q.y >= 1.0 || q.x < 0.0) return 0.0;
    int i = int(q.x);
    if (i >= n) return 0.0;
    return glyphBit(WORDS[WSTART[id] + i], vec2(fract(q.x), q.y));
}
float wordAll(int id, vec2 fc, vec2 org, float cs, float center) { return word(id, fc, org, cs, center, 99); }
// n Hex-Ziffern (zufällig per seed) ab org
float hexRun(vec2 fc, vec2 org, float cs, float seed, int n) {
    float cw = cs * 0.75;
    vec2 q = (fc - org) / vec2(cw, cs);
    if (q.y < 0.0 || q.y >= 1.0 || q.x < 0.0) return 0.0;
    int i = int(q.x);
    if (i >= n) return 0.0;
    return glyphBit(hexCode(seed + float(i) * 7.7), vec2(fract(q.x), q.y));
}
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }

// =====================================================================
// Code-Varianten (fc in Pixeln, t Sekunden in der Phase, prog 0..1 Fortschritt der Phase)
// =====================================================================
// 0: Zeichenregen – fallende Spuren, Kopf hell, Bass verlängert die Spuren, Beat blitzt Spalten
vec3 codeRain(vec2 fc, float t, float prog) {
    vec3 col = vec3(0.0);
    float cs = iResolution.y / ROWS;
    for (int layer = 0; layer < 2; layer++) {
        float sc = layer == 0 ? 1.0 : 1.7;
        vec2 csz = vec2(cs * 0.75, cs) * sc;
        vec2 cell = floor(fc / csz);
        vec2 l = fract(fc / csz);
        float rows = iResolution.y / csz.y;
        float cseed = cell.x + float(layer) * 777.0;
        float speed = (4.0 + 10.0 * hash1(cseed + 0.3)) / sc;
        float trail = 6.0 + 10.0 * hash1(cseed + 0.7) + 12.0 * uBass;
        float period = rows + 24.0;
        float head = mod(t * speed + hash1(cseed + 0.9) * period, period) - 24.0 + trail;
        float r = rows - 1.0 - cell.y;
        float d = head - r;
        if (d < 0.0 || d > trail) continue;
        float bright = pow(1.0 - d / trail, 1.6);
        float flick = floor(t * (2.0 + 8.0 * uMid) * (0.5 + hash1(cseed + 0.5)));
        int code = randCode(hash13(vec3(cell, flick)) * 100.0);
        float g = glyphBit(code, l);
        vec3 cc = mix(GRN, vec3(0.85, 1.0, 0.9), step(d, 1.0) * 0.9);
        col += cc * g * bright * (layer == 0 ? 1.0 : 0.3);
        // Beat: einzelne Spalten blitzen weiß
        float flash = step(0.92, hash12(vec2(cell.x, floor(t * 8.0)))) * uBeat;
        col += vec3(0.9, 1.0, 0.9) * g * flash * 0.8;
    }
    return col;
}
// 1: Hexdump – Adressen, Bytes, Klartext; scrollt hoch, Spektrum steuert die Helligkeit der Spalten
vec3 codeHex(vec2 fc, float t, float prog) {
    float cs = iResolution.y / ROWS, cw = cs * 0.75;
    float scroll = t * 3.0;
    float fy = ROWS - fc.y / cs + scroll;               // Zeilennummer wächst nach unten, scrollt nach oben
    float line = floor(fy);
    float c = floor(fc.x / cw);
    vec2 l = vec2(fract(fc.x / cw), 1.0 - fract(fy));
    int code = 36;
    int ic = int(c);
    if (ic < 2) code = ic == 0 ? 26 : 23;                         // "0X"
    else if (ic < 6) { int addr = int(line) * 16; int v = (addr >> (4 * (5 - ic))) & 15; code = v < 10 ? 26 + v : v - 10; }
    else if (ic >= 8 && ic < 56) { int sub = (ic - 8) - ((ic - 8) / 3) * 3; if (sub < 2) code = hexCode(hash12(vec2(line, c))); }
    else if (ic >= 57 && ic < 73) code = randCode(hash12(vec2(line, c + 0.5)));
    float g = glyphBit(code, l);
    float cols = iResolution.x / cw;
    float b = 0.45 + 0.55 * step(0.85, hash1(line + 0.33));       // einzelne Zeilen hell
    b *= 0.6 + 1.2 * spec(c / cols);                               // Spektrum über die Spalten
    float cur = step(abs(line - (floor(scroll) + ROWS - 2.0)), 0.5);   // "aktuelle" Zeile unten
    vec3 cc = mix(GRN, vec3(0.9, 1.0, 0.9), cur);
    float beatRow = step(abs(line - (floor(scroll) + floor(hash1(floor(t * 6.0)) * ROWS))), 0.5) * uBeat;
    cc = mix(cc, vec3(1.0), beatRow);
    return cc * g * b * (0.7 + 0.5 * uRms);
}
// 2: Boot-Protokoll – [ OK ] / [WARN] / [FAIL], Balken, gegen Ende immer mehr FAIL
vec3 codeLog(vec2 fc, float t, float prog) {
    float cs = iResolution.y / ROWS, cw = cs * 0.75;
    vec2 cell = floor(fc / vec2(cw, cs));
    vec2 l = fract(fc / vec2(cw, cs));
    float n = floor(t * 4.5) + 1.0;                               // bisher ausgegebene Zeilen
    float r = ROWS - 1.0 - cell.y;
    float line = n - (ROWS - r);
    if (line < 0.0) return vec3(0.0);
    float kind = hash1(line + 0.5);
    float pfail = 0.03 + 0.55 * prog;
    float isFail = step(kind, pfail), isWarn = step(kind, pfail + 0.15) * (1.0 - isFail);
    int ic = int(cell.x);
    int code = 36;
    vec3 cc = GRN * 0.75;
    if (ic < 6) {
        int w = isFail > 0.5 ? 26 : (isWarn > 0.5 ? 25 : 24);
        code = WORDS[WSTART[w] + ic];
        cc = isFail > 0.5 ? RED : (isWarn > 0.5 ? AMB : GRN);
    } else if (ic >= 7) {
        float hasBar = step(0.72, hash1(line + 0.8));
        if (hasBar > 0.5) {
            // [##########        ] 52%
            float live = step(line, n - 1.0) * step(n - 3.0, line);   // die jüngsten Zeilen laufen live mit
            float fill = mix(hash1(line + 0.9), 0.2 + 0.8 * uBass, live);
            int k = ic - 7;
            if (k == 0) code = 40; else if (k == 21) code = 41;
            else if (k < 21) code = step(float(k - 1), fill * 20.0 - 1.0) > 0.5 ? 42 : 36;
            else if (k == 23 || k == 24) { int pc = int(fill * 99.0); code = 26 + (k == 23 ? pc / 10 : pc - (pc / 10) * 10); }
            else if (k == 25) code = 43;
            cc = mix(GRN * 0.8, vec3(0.9, 1.0, 0.9), live);
        } else {
            float len = 14.0 + hash1(line + 0.6) * 44.0;
            if (cell.x - 7.0 < len) {
                float sp = step(hash12(vec2(line, floor((cell.x - 7.0) * 0.37))), 0.18);
                code = sp > 0.5 ? 36 : randCode(hash12(vec2(line, cell.x)));
                cc = mix(GRN * 0.6, RED * 0.8, isFail);
            }
        }
    }
    float g = glyphBit(code, l);
    // Cursor auf der nächsten Zeile
    float curRow = step(abs(line - n), 0.5) * step(cell.x, 0.5) * step(0.5, fract(t * 2.5));
    return cc * g * (0.8 + 0.4 * uRms) + GRN * curRow * 0.8;
}
// 3: Bitraster – 0/1 kippen, Spektrum als Ringe aus der Mitte, Beat schickt eine Welle
vec3 codeBits(vec2 fc, float t, float prog) {
    float cs = iResolution.y / ROWS * 0.8, cw = cs * 0.75;
    vec2 cell = floor(fc / vec2(cw, cs));
    vec2 l = fract(fc / vec2(cw, cs));
    float rate = 1.0 + 7.0 * hash12(cell + 0.5);
    float bit = step(0.5, hash13(vec3(cell, floor(t * rate))));
    float g = glyphBit(bit > 0.5 ? 27 : 26, l);
    vec2 p = (fc - iResolution * 0.5) / iResolution.y;
    float rr = length(p);
    float s = spec(rr * 1.3);
    float ring = exp(-abs(rr - fract(t * 0.7) * 0.9) * 25.0) * uBeat;
    float bright = (0.18 + 1.6 * s + ring) * (0.6 + 0.5 * bit);
    vec3 cc = GRN;
    float corrupt = step(hash13(vec3(cell, floor(t))), prog * 0.12);
    cc = mix(cc, RED, corrupt);
    return cc * g * bright;
}
// 4: Quelltext – eingerückte Blöcke, Schlüsselwörter, Strings, Kommentare; Fehlerzeilen nehmen zu
vec3 codeSource(vec2 fc, float t, float prog) {
    float cs = iResolution.y / ROWS, cw = cs * 0.75;
    float scroll = t * 2.2;
    float fy = ROWS - fc.y / cs + scroll;
    float line = floor(fy);
    float c = floor(fc.x / cw) - 2.0;
    vec2 l = vec2(fract(fc.x / cw), 1.0 - fract(fy));
    float depth = floor(hash1(floor(line / 4.0) + 0.2) * 3.0) * 4.0;
    float len = 6.0 + hash1(line + 0.7) * 34.0;
    float isErr = step(hash1(line + 0.9), prog * 0.35);
    float g = 0.0;
    vec3 cc = GRN * 0.6;
    if (isErr > 0.5) {
        // ">> FEHLERCODE 0XA1B2C3D4"
        vec2 org = vec2((2.0 + depth) * cw, (ROWS - 1.0 - (line - scroll)) * cs);
        g = wordAll(20, fc, org + vec2(3.0 * cw, 0.0), cs, 0.0);
        g += hexRun(fc, org + vec2(14.0 * cw, 0.0), cs, line * 3.1, 8);
        g += glyphBit(45, (fc - org) / vec2(cw, cs)) + glyphBit(45, (fc - org - vec2(cw, 0.0)) / vec2(cw, cs));
        cc = RED;
    } else if (c >= depth && c - depth < len) {
        float k = c - depth;
        float braceLine = step(hash1(line + 0.4), 0.12);
        if (braceLine > 0.5) { if (k < 1.0) g = glyphBit(50, l); }      // "}" bzw. "{"
        else {
            float sp = step(hash12(vec2(line, floor(k * 0.73))), 0.18);
            int code = sp > 0.5 ? 36 : randCode(hash12(vec2(line, k)));
            float seg = floor(k / 7.0 + hash1(line));
            float kind = hash12(vec2(line, seg + 50.0));
            cc = kind < 0.3 ? GRN : (kind < 0.6 ? GRN * 0.6 : (kind < 0.8 ? AMB * 0.8 : GRN * 0.35));
            g = glyphBit(code, l);
        }
    }
    // Funken bei Höhen: zufällige Zellen leuchten kurz auf
    vec2 scell = floor(fc / vec2(cw, cs));
    float spark = step(0.996 - uHigh * 0.01, hash13(vec3(scell, floor(t * 15.0)))) * glyphBit(49, fract(fc / vec2(cw, cs)));
    return cc * g * (0.8 + 0.4 * uBass) + vec3(0.8, 1.0, 0.85) * spark;
}
// 5: Analysator als Code – Spektrumsäulen aus Zeichen, Wellenform als Tilde-Zeile
vec3 codeSpectrum(vec2 fc, float t, float prog) {
    float cols = 64.0;
    float cwid = iResolution.x / cols, cs = iResolution.y / ROWS;
    float k = floor(fc.x / cwid);
    float row = floor(fc.y / cs);
    vec2 l = vec2(fract(fc.x / cwid), fract(fc.y / cs));
    float h = spec((k + 0.5) / cols) * ROWS * 1.1;
    vec3 col = vec3(0.0);
    if (row < h) {
        float top = step(h - 1.5, row);
        int code = top > 0.5 ? 42 : randCode(hash13(vec3(k, row, floor(t * 6.0))));
        float g = glyphBit(code, l);
        float fr = row / ROWS;
        vec3 cc = mix(GRN, AMB, smoothstep(0.3, 0.6, fr));
        cc = mix(cc, RED, smoothstep(0.65, 0.85, fr));
        col += cc * g * (0.6 + 0.6 * top);
    }
    // Wellenform
    float wrow = floor((0.5 + wave((k + 0.5) / cols) * 0.3) * ROWS);
    if (abs(row - wrow) < 0.5) col += vec3(0.85, 1.0, 0.9) * glyphBit(48, l) * 0.9;   // "="
    // Kopfzeile: WARNUNG blinkt bei hohem Pegel
    float loud = step(0.55, uRms) * step(0.5, fract(t * 3.0));
    col += AMB * wordAll(13, fc, vec2(iResolution.x * 0.5, iResolution.y * 0.9), cs * 1.6, 1.0) * loud;
    return col;
}
vec3 codeScene(vec2 fc, int v, float t, float prog) {
    if (v == 0) return codeRain(fc, t, prog);
    if (v == 1) return codeHex(fc, t, prog);
    if (v == 2) return codeLog(fc, t, prog);
    if (v == 3) return codeBits(fc, t, prog);
    if (v == 4) return codeSource(fc, t, prog);
    return codeSpectrum(fc, t, prog);
}

// =====================================================================
// Zusammenbruch: Code bleibt, wird aber zerrissen, verschoben, invertiert, rot
// =====================================================================
vec3 breakdown(vec2 fc, float b, int v, float t, float prog) {
    vec2 uv = fc / iResolution;
    float tt = floor(t * 12.0);
    float bb = b * b;
    // Bildrollen
    uv.y = fract(uv.y + bb * 0.6 * fract(tt * 0.37) * step(0.6, hash1(tt + 0.1)));
    // Zeilenstreifen verschieben
    float band = floor(uv.y * (10.0 + 30.0 * b));
    float sh = (hash12(vec2(band, tt)) - 0.5) * b * 0.4 * step(1.0 - b * 0.8, hash12(vec2(band, tt + 7.0)));
    uv.x = fract(uv.x + sh);
    // Blöcke springen
    vec2 blk = floor(uv * vec2(8.0, 6.0));
    if (hash12(blk + tt * 0.1) > 1.0 - 0.3 * b) uv = fract(uv + (hash12(blk + tt) - 0.5) * 0.3);
    vec3 col = codeScene(uv * iResolution, v, t, prog);
    // Farbspaltung: roter Geist des Codes
    vec3 c2 = codeScene(fract(uv + vec2(0.012 + 0.02 * b + 0.01 * uBass, 0.0)) * iResolution, v, t, prog);
    col = vec3(max(col.r, c2.g * 0.9), col.g, col.b);
    // invertierte Blöcke
    float inv = step(1.0 - 0.25 * b, hash12(blk * 1.7 + tt));
    col = mix(col, vec3(0.9, 0.2, 0.15) * (1.0 - col.g), inv);
    // Rauschen
    float n = hash13(vec3(floor(fc / 2.0), tt));
    col += vec3(n) * step(1.0 - 0.35 * bb, n) * b;
    // nach Rot kippen
    col = mix(col, vec3(col.g * 1.1, col.g * 0.12, col.g * 0.1), bb);
    // ERROR-Stempel tauchen auf
    vec2 sblk = floor(fc / vec2(iResolution.x / 5.0, iResolution.y / 4.0));
    float st = step(1.0 - 0.9 * bb, hash12(sblk * 3.1 + floor(t * 6.0)));
    vec2 sorg = (sblk + vec2(0.1, 0.35)) * vec2(iResolution.x / 5.0, iResolution.y / 4.0);
    col += RED * wordAll(0, fc, sorg, iResolution.y * 0.06, 0.0) * st;
    col += vec3(1.0, 0.2, 0.2) * uBeat * 0.25 * b;
    return col;
}

// =====================================================================
// Fehlerbilder
// =====================================================================
int panicWord(int k) {
    if (k == 0) return 2; if (k == 1) return 4; if (k == 2) return 5; if (k == 3) return 8;
    if (k == 4) return 7; if (k == 5) return 11; if (k == 6) return 12; if (k == 7) return 15;
    if (k == 8) return 16; if (k == 9) return 17; if (k == 10) return 18; return 23;
}
// 0: riesiges ERROR, zitternd, zerrissen, Fehlercode darunter
vec3 errBig(vec2 fc, float te, float e) {
    vec2 res = iResolution;
    float cs = res.y * 0.28;
    float k = floor(te * 20.0);
    vec2 j = (vec2(hash1(k + 0.3), hash1(k + 0.7)) - 0.5) * cs * 0.1 * (0.3 + uBass * 1.5 + uBeat);
    float band = floor(fc.y / (res.y / 24.0));
    float tear = (hash12(vec2(band, floor(te * 10.0))) - 0.5) * res.x * 0.08 * step(0.8, hash12(vec2(band, floor(te * 10.0) + 3.0)));
    vec2 f2 = fc + j + vec2(tear, 0.0);
    float w = wordAll(0, f2, vec2(res.x * 0.5, res.y * 0.42), cs, 1.0);
    float flick = 0.75 + 0.25 * step(0.3, hash1(floor(te * 30.0)));
    vec3 col = RED * w * flick;
    // FEHLERCODE 0X........
    float cs2 = res.y * 0.045;
    vec2 org = vec2(res.x * 0.5 - 11.0 * cs2 * 0.75, res.y * 0.3);
    col += vec3(1.0, 0.5, 0.4) * wordAll(20, fc, org, cs2, 0.0) * 0.9;
    col += vec3(1.0, 0.5, 0.4) * wordAll(27, fc, org + vec2(11.0 * cs2 * 0.75, 0.0), cs2, 0.0) * 0.9;
    col += vec3(1.0, 0.5, 0.4) * hexRun(fc, org + vec2(13.0 * cs2 * 0.75, 0.0), cs2, floor(te * 5.0), 8) * 0.9;
    vec2 uv = fc / res;
    col += vec3(0.3, 0.0, 0.0) * (1.0 - length(uv - 0.5) * 1.3) * (0.3 + uBass);
    col += vec3(0.6, 0.06, 0.0) * step(0.985, hash12(vec2(floor(fc.y / 3.0), floor(te * 15.0))));
    return col;
}
// 1: Alarmkacheln – rot blinkende Fläche, SYSTEMFEHLER als Muster, Warnband mit ERROR
vec3 errTiles(vec2 fc, float te, float e) {
    vec2 res = iResolution;
    float flash = step(0.5, fract(te * 3.0));
    vec3 bg = RED * (0.3 + 0.4 * flash + 0.25 * uBass);
    float cs = res.y / 14.0;
    float row = floor(fc.y / cs);
    float dir = mod(row, 2.0) < 1.0 ? 1.0 : -1.0;
    float tileW = 13.0 * cs * 0.75;
    float xx = mod(fc.x + dir * te * cs * 0.8 + row * cs * 2.0, tileW);
    float w = word(1, vec2(xx, fc.y), vec2(0.0, row * cs), cs, 0.0, 99);
    vec3 col = mix(bg, vec3(0.04, 0.0, 0.0), w);
    vec2 uv = fc / res;
    if (abs(uv.y - 0.5) < 0.13) {
        col = vec3(0.03, 0.0, 0.0);
        float big = wordAll(0, fc, vec2(res.x * 0.5, res.y * 0.42), res.y * 0.16, 1.0);
        col += mix(AMB, vec3(1.0), flash) * big * (0.8 + 0.4 * uBeat);
    }
    float edge = step(abs(abs(uv.y - 0.5) - 0.13), 0.012);
    float stripe = step(0.5, fract((fc.x + fc.y) / 40.0 - te * 2.0));
    col = mix(col, mix(vec3(0.05), AMB, stripe), edge);
    return col;
}
// 2: Kaskade – ERROR ERROR ERROR füllt das Bild zeilenweise, dann bebt alles
vec3 errCascade(vec2 fc, float te, float e) {
    vec2 res = iResolution;
    float cs = res.y / ROWS, cw = cs * 0.75;
    float shake = max(0.0, e - 0.6) * 3.0;
    float k = floor(te * 25.0);
    fc += (vec2(hash1(k + 0.3), hash1(k + 0.7)) - 0.5) * cs * 1.5 * shake * (0.5 + uBass);
    vec2 cell = floor(fc / vec2(cw, cs));
    vec2 l = fract(fc / vec2(cw, cs));
    float cols = floor(res.x / cw);
    float r = ROWS - 1.0 - cell.y;
    float idx = r * cols + cell.x;
    float total = cols * ROWS;
    float lim = e * 1.35 * total;
    if (idx > lim) return vec3(0.0);
    float kk = mod(cell.x + r * 2.0, 6.0);
    int code = kk < 5.0 ? WORDS[int(kk)] : 36;
    float g = glyphBit(code, l);
    float fresh = step(lim - cols * 2.0, idx);
    float b = 0.5 + 0.5 * hash12(cell);
    float rowFlash = step(0.9, hash12(vec2(r, floor(te * 8.0)))) * uBeat;
    vec3 cc = mix(RED, vec3(1.0, 0.8, 0.7), max(fresh, rowFlash));
    return cc * g * b * (0.8 + 0.4 * uBass);
}
// 3: Kernel-Panic – weiße Protokollzeilen, rote Meldungen, blinkender ERROR-Kasten
vec3 errPanic(vec2 fc, float te, float e) {
    vec2 res = iResolution;
    float cs = res.y / ROWS, cw = cs * 0.75;
    vec2 cell = floor(fc / vec2(cw, cs));
    vec2 l = fract(fc / vec2(cw, cs));
    float r = ROWS - 1.0 - cell.y;
    float n = floor(te * 7.0);
    vec3 col = vec3(0.0);
    if (r < n && r > 0.0) {
        float line = r;
        float kind = hash1(line + 0.2);
        vec2 org = vec2(cw, cell.y * cs);
        float g = 0.0;
        vec3 cc = vec3(0.8);
        // Präfix: 0X + 8 Hex + ": "
        g += wordAll(27, fc, org, cs, 0.0);
        g += hexRun(fc, org + vec2(2.0 * cw, 0.0), cs, line * 5.3, 8);
        g += glyphBit(38, (fc - org - vec2(10.0 * cw, 0.0)) / vec2(cw, cs));
        if (kind < 0.4) {
            g += wordAll(panicWord(int(hash1(line + 0.6) * 12.0)), fc, org + vec2(12.0 * cw, 0.0), cs, 0.0);
            cc = mix(vec3(0.8), RED, step(12.0, cell.x));
        } else {
            int ic = int(cell.x) - 12;
            if (ic >= 0 && ic < 48) { int sub = ic - (ic / 3) * 3; if (sub < 2) g += glyphBit(hexCode(hash12(vec2(line, cell.x))), l); }
        }
        float fresh = step(n - 2.0, line);
        col = cc * min(g, 1.0) * mix(0.55, 1.0, fresh);
    }
    vec2 uv = fc / res;
    float box = rect(uv, vec2(0.70, 0.06), vec2(0.95, 0.17));
    float on = step(0.5, fract(te * 2.0 + uBeat));
    col = mix(col, RED * (0.6 + 0.4 * uBass), box * on);
    col = mix(col, vec3(0.0), box * on * wordAll(0, fc, vec2(res.x * 0.825, res.y * 0.085), res.y * 0.06, 1.0));
    return col;
}
// 4: Countdown – WARNUNG, große Ziffer, KERN INSTABIL, Warnstreifen, am Ende Weißblitz
vec3 errCountdown(vec2 fc, float te, float e) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    vec3 col = vec3(0.12, 0.0, 0.0) * (0.5 + uBass);
    float n = max(0.0, 9.0 - floor(te * 2.2));
    float k = floor(te * 25.0);
    float shake = (9.0 - n) / 9.0;
    vec2 j = (vec2(hash1(k + 0.3), hash1(k + 0.7)) - 0.5) * res.y * 0.03 * shake * (0.5 + uBass);
    float blink = step(0.5, fract(te * 2.0));
    col += AMB * wordAll(13, fc, vec2(res.x * 0.5, res.y * 0.78), res.y * 0.09, 1.0) * blink;
    float dcs = res.y * 0.42;
    vec2 q = (fc + j - vec2(res.x * 0.5 - dcs * 0.375, res.y * 0.3)) / vec2(dcs * 0.75, dcs);
    col += RED * glyphBit(26 + int(n), q) * (0.8 + 0.4 * uBeat);
    col += RED * wordAll(11, fc, vec2(res.x * 0.5, res.y * 0.14), res.y * 0.055, 1.0) * 0.9;
    float bars = step(0.92, uv.y) + step(uv.y, 0.06);
    float stripe = step(0.5, fract((fc.x + fc.y) / 50.0 + te * 1.5));
    col = mix(col, mix(vec3(0.05), AMB, stripe), bars);
    float t0 = 9.0 / 2.2;
    if (te > t0) col += vec3(1.0) * exp(-(te - t0) * 6.0);
    return col;
}
// 5: Rauschen – kein Signal, ERROR als rotes Loch im Schnee, SIGNAL VERLOREN
vec3 errStatic(vec2 fc, float te, float e) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    float n = hash13(vec3(floor(fc / 2.0), floor(te * 30.0)));
    float band = 0.6 + 0.4 * step(0.5, fract(uv.y * 3.0 - te * 0.7));
    vec3 col = vec3(n) * 0.55 * band * (0.6 + 0.7 * uRms);
    float w = wordAll(0, fc, vec2(res.x * 0.5, res.y * 0.42), res.y * 0.25, 1.0);
    col = mix(col, RED * (0.6 + 0.5 * n) * (0.8 + 0.4 * uBass), w);
    float blink = step(0.5, fract(te * 1.5));
    col += vec3(0.9) * wordAll(7, fc, vec2(res.x * 0.5, res.y * 0.12), res.y * 0.05, 1.0) * blink;
    return col;
}
vec3 errorScene(vec2 fc, int v, float te, float e) {
    if (v == 0) return errBig(fc, te, e);
    if (v == 1) return errTiles(fc, te, e);
    if (v == 2) return errCascade(fc, te, e);
    if (v == 3) return errPanic(fc, te, e);
    if (v == 4) return errCountdown(fc, te, e);
    return errStatic(fc, te, e);
}
// Wiederherstellung: Balken, der stottert, Prozentzahl, darunter rauschende Reste
vec3 recovery(vec2 fc, float tr, float r) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    float cs = res.y * 0.05;
    vec3 col = vec3(0.0);
    col += GRN * wordAll(29, fc, vec2(res.x * 0.5, res.y * 0.58), cs, 1.0) * 0.9;
    float fill = clamp(r * 1.1 - 0.08 * step(0.7, hash1(floor(tr * 6.0))), 0.0, 1.0);   // Balken stottert
    float barL = res.x * 0.25, barR = res.x * 0.75;
    float frame = rect(uv, vec2(0.25, 0.46), vec2(0.75, 0.52)) - rect(uv, vec2(0.253, 0.466), vec2(0.747, 0.514));
    col += GRN * frame * 0.8;
    float inside = rect(uv, vec2(0.26, 0.472), vec2(0.26 + 0.48 * fill, 0.508));
    float seg = step(0.15, fract(fc.x / (res.x * 0.012)));
    col += GRN * inside * seg * (0.7 + 0.4 * uBass);
    // Prozent
    int pc = int(fill * 99.0);
    vec2 org = vec2(res.x * 0.5 - 1.5 * cs * 0.75, res.y * 0.38);
    col += GRN * glyphBit(26 + pc / 10, (fc - org) / vec2(cs * 0.75, cs));
    col += GRN * glyphBit(26 + pc - (pc / 10) * 10, (fc - org - vec2(cs * 0.75, 0.0)) / vec2(cs * 0.75, cs));
    col += GRN * glyphBit(43, (fc - org - vec2(1.5 * cs, 0.0)) / vec2(cs * 0.75, cs));
    // Reste: Zeilen aus Rauschen am unteren Rand, die verschwinden
    float noise = hash13(vec3(floor(fc / 3.0), floor(tr * 20.0)));
    col += vec3(0.4, 0.1, 0.1) * step(1.0 - 0.3 * (1.0 - r), noise) * step(uv.y, 0.25);
    return col;
}
// Neustart: NEUSTART wird getippt, Cursor blinkt
vec3 reboot(vec2 fc, float tb, float r) {
    vec2 res = iResolution;
    float cs = res.y * 0.06;
    int shown = int(r * 12.0);
    vec2 org = vec2(res.x * 0.5 - 4.0 * cs * 0.75, res.y * 0.47);
    vec3 col = GRN * word(6, fc, org, cs, 0.0, shown);
    float cx = org.x + float(min(shown, 8)) * cs * 0.75;
    float cur = rect(fc, vec2(cx, org.y), vec2(cx + cs * 0.6, org.y + cs * 0.85)) * step(0.5, fract(tb * 4.0));
    return col + GRN * cur;
}


// ---- Zahl mit führenden Nullen
float number(vec2 fc, vec2 org, float cs, int value, int digits) {
    float cw = cs * 0.75;
    vec2 q = (fc - org) / vec2(cw, cs);
    if (q.y < 0.0 || q.y >= 1.0 || q.x < 0.0) return 0.0;
    int i = int(q.x);
    if (i >= digits) return 0.0;
    int div = 1;
    for (int k = 0; k < 6; k++) if (k < digits - 1 - i) div *= 10;
    int d = (value / div) - ((value / div) / 10) * 10;
    return glyphBit(26 + d, vec2(fract(q.x), q.y));
}
// Pfeil in Richtung dir (1 oben, 2 unten, 3 links, 4 rechts), Mitte c, Größe sz
float arrow(vec2 fc, vec2 c, float sz, int dir) {
    vec2 d = (fc - c) / sz;
    if (dir == 2) d.y = -d.y;
    if (dir == 3) d = vec2(d.y, -d.x);
    if (dir == 4) d = vec2(-d.y, d.x);
    float shaft = step(abs(d.x), 0.16) * step(-0.9, d.y) * step(d.y, 0.1);
    float head = step(0.0, d.y) * step(d.y, 0.9) * step(abs(d.x), (0.9 - d.y) * 0.75);
    return max(shaft, head);
}
vec3 promptScene(vec2 fc, vec3 code, float pt, float len, int dir) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    vec3 col = code * 0.3;
    vec2 pc = res * 0.5;
    vec2 hsz = vec2(res.x * 0.28, res.y * 0.24);
    float box = rect(fc, pc - hsz, pc + hsz);
    float border = box - rect(fc, pc - hsz + 4.0, pc + hsz - 4.0);
    float urgency = smoothstep(0.5, 1.0, pt / len);
    vec3 frame = mix(AMB, RED, urgency) * (0.7 + 0.3 * sin(pt * (6.0 + 10.0 * urgency)));
    col = mix(col, vec3(0.02, 0.02, 0.03), box);
    col += frame * border;
    col += AMB * wordAll(31, fc, vec2(pc.x, pc.y + hsz.y - res.y * 0.075), res.y * 0.035, 1.0);
    // Pfeil oder START-Kreis
    vec2 ac = vec2(pc.x, pc.y + res.y * 0.02);
    if (dir <= 4) col += vec3(1.0) * arrow(fc, ac, res.y * 0.09, dir) * (0.85 + 0.15 * sin(pt * 8.0));
    else {
        float ring = smoothstep(0.0, 2.0, abs(length(fc - ac) - res.y * 0.075) - 3.0);
        col += vec3(1.0) * (1.0 - ring) * (0.85 + 0.15 * sin(pt * 8.0));
        col += vec3(1.0) * wordAll(37, fc, ac - vec2(0.0, res.y * 0.02), res.y * 0.04, 1.0);
    }
    float cs = res.y * 0.05;
    vec2 org = vec2(pc.x - (7.0 + 1.0 + float(WLEN[32 + dir])) * cs * 0.75 * 0.5, pc.y - res.y * 0.14);
    col += vec3(1.0, 0.9, 0.6) * wordAll(32, fc, org, cs, 0.0);
    col += vec3(1.0) * wordAll(32 + dir, fc, org + vec2(8.0 * cs * 0.75, 0.0), cs, 0.0);
    // Restzeit-Balken
    float remain = 1.0 - pt / len;
    float bar = rect(fc, vec2(pc.x - hsz.x + 12.0, pc.y - hsz.y + 10.0), vec2(pc.x - hsz.x + 12.0 + (hsz.x * 2.0 - 24.0) * remain, pc.y - hsz.y + 18.0));
    col += frame * bar;
    // Sekundentakt
    col += vec3(1.0, 0.8, 0.5) * 0.06 * step(0.92, fract(pt)) * box;
    return col;
}
vec3 bannerScene(vec2 fc, vec3 code, float pt, float len, int wa, int wb, vec3 tint, float alarm) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    vec3 col = mix(code, vec3(dot(code, vec3(0.33))) * tint * 1.6, alarm * 0.8);
    if (alarm < 0.5) col = code * 1.1 + tint * 0.03;
    float strobe = step(0.5, fract(pt * 3.0)) * alarm;
    float edge = 1.0 - rect(uv, vec2(0.03, 0.05), vec2(0.97, 0.95));
    col += tint * edge * strobe * 0.8;
    float stripe = step(0.5, fract((fc.x - fc.y) / 50.0 + pt * 1.5));
    float bars = step(0.93, uv.y) + step(uv.y, 0.07);
    col = mix(col, mix(vec3(0.05), tint, stripe), bars * alarm);
    float k = floor(pt * 25.0);
    vec2 j = (vec2(hash1(k + 0.3 + uSeed), hash1(k + 0.7 + uSeed)) - 0.5) * res.y * 0.015 * alarm;
    float fadeIn = smoothstep(0.0, 0.3, pt);
    vec2 pc = res * 0.5;
    float bw = float(WLEN[wa]) * res.y * 0.07 * 0.75 + res.y * 0.08;
    float panel = rect(fc, pc - vec2(bw * 0.5, res.y * 0.11), pc + vec2(bw * 0.5, res.y * 0.11));
    col = mix(col, vec3(0.02), panel * 0.85 * fadeIn);
    col += tint * (panel - rect(fc, pc - vec2(bw * 0.5 - 4.0, res.y * 0.11 - 4.0), pc + vec2(bw * 0.5 - 4.0, res.y * 0.11 - 4.0))) * fadeIn;
    col += tint * wordAll(wa, fc + j, vec2(pc.x, pc.y + res.y * 0.005), res.y * 0.07, 1.0) * fadeIn * (0.8 + 0.2 * sin(pt * 6.0));
    if (wb >= 0) col += vec3(0.9) * wordAll(wb, fc + j, vec2(pc.x, pc.y - res.y * 0.075), res.y * 0.032, 1.0) * fadeIn;
    if (alarm < 0.5) {   // Funken bei gutem Ausgang
        float spark = step(0.995, hash13(vec3(floor(fc / 6.0), floor(pt * 12.0))));
        col += GRN * spark;
    }
    return col;
}
vec3 virusScene(vec2 fc, vec3 code, float pt, float len, float pct, float outcome) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    float cs = res.y / ROWS, cw = cs * 0.75;
    vec2 cell = floor(fc / vec2(cw, cs));
    vec2 center = vec2(0.25 + 0.5 * hash1(uSeed + 0.5), 0.3 + 0.4 * hash1(uSeed + 0.9));
    float d = length((uv - center) * vec2(res.x / res.y, 1.0));
    float edgeN = vnoise(cell * 0.35 + uSeed) * 0.25;
    float infected = step(d + edgeN, pct * 1.3);
    vec3 col = code;
    float g = step(0.5, hash12(cell + floor(pt * 4.0)));
    vec3 sick = mix(RED * 0.5, vec3(1.0, 0.3, 0.2), g) * (0.4 + 0.6 * dot(code, vec3(1.0)));
    sick += RED * 0.25 * glyphBit(42, fract(fc / vec2(cw, cs))) * g;         // '#'-Zellen
    col = mix(col, sick, infected);
    col += RED * 0.3 * smoothstep(0.06, 0.0, abs(d + edgeN - pct * 1.3));     // Infektionsfront
    // Scanzeile
    float sy = 1.0 - fract(pt * 0.45);
    col += vec3(0.4, 1.0, 0.5) * smoothstep(0.03, 0.0, abs(uv.y - sy)) * 0.5 * (1.0 - outcome);
    // Kopfzeile
    float blink = step(0.5, fract(pt * 2.5));
    float top = rect(uv, vec2(0.0, 0.9), vec2(1.0, 1.0));
    col = mix(col, vec3(0.08, 0.0, 0.0), top * 0.85);
    if (outcome < 0.5) {
        col += RED * wordAll(42, fc, vec2(res.x * 0.5, res.y * 0.93), res.y * 0.05, 1.0) * (0.6 + 0.4 * blink);
        float cs2 = res.y * 0.03;
        vec2 org = vec2(res.x * 0.5 - 7.0 * cs2 * 0.75, res.y * 0.015);
        col += vec3(1.0, 0.6, 0.5) * wordAll(53, fc, org, cs2, 0.0);
        col += vec3(1.0, 0.6, 0.5) * number(fc, org + vec2(10.0 * cs2 * 0.75, 0.0), cs2, int(pct * 100.0), 3);
        col += vec3(1.0, 0.6, 0.5) * glyphBit(43, (fc - org - vec2(13.0 * cs2 * 0.75, 0.0)) / vec2(cs2 * 0.75, cs2));
        col += vec3(0.8) * wordAll(37, fc, vec2(res.x * 0.5 - 10.0 * cs2 * 0.75, res.y * 0.055), cs2 * 0.9, 0.0) * 0.6;
        col += vec3(0.8) * glyphBit(48, (fc - vec2(res.x * 0.5 - 4.0 * cs2 * 0.75, res.y * 0.055)) / vec2(cs2 * 0.75 * 0.9, cs2 * 0.9)) * 0.6;
        col += vec3(0.8) * wordAll(43, fc, vec2(res.x * 0.5 - 2.0 * cs2 * 0.75, res.y * 0.055), cs2 * 0.9, 0.0) * 0.6;
    } else {
        col = mix(col, col * vec3(0.6, 1.0, 0.7), 0.5);
        col += GRN * wordAll(43, fc, vec2(res.x * 0.5, res.y * 0.93), res.y * 0.05, 1.0);
        float ring = smoothstep(4.0, 0.0, abs(d - pct * 1.3) * res.y - 2.0);
        col += GRN * ring * 0.8;
    }
    return col;
}
vec3 shieldScene(vec2 fc, vec3 code, float pt, float len, float pct, float outcome) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    float flick = mix(1.0, step(0.3, hash1(floor(pt * 20.0) + uSeed)), (1.0 - pct) * 0.6 * (1.0 - outcome));
    vec3 col = code * 0.5 * flick;
    // Sechseck-Schild in der Mitte
    vec2 p = (fc - res * 0.5) / res.y;
    float a = atan(p.y, p.x);
    float r6 = length(p) * cos(mod(a + 0.5235988, 1.0471976) - 0.5235988);
    float R = 0.26;
    float outline = smoothstep(0.006, 0.0, abs(r6 - R));
    float fill = step(r6, R);
    vec3 sc = outcome > 0.5 ? GRN : mix(RED, vec3(0.3, 0.8, 1.0), pct);
    float segs = step(0.5, fract((a / (2.0 * 3.1415927) + 0.5) * 12.0 + 0.5));
    float alive = step(fract((a / (2.0 * 3.1415927) + 0.5)), pct);        // Segmente fallen aus
    col += sc * outline * mix(0.3, 1.0, max(alive, outcome)) * flick;
    col += sc * fill * 0.08 * max(alive, outcome) * (0.7 + 0.3 * segs);
    // Prozent in der Mitte
    float cs = res.y * 0.09;
    col += sc * number(fc, vec2(res.x * 0.5 - 1.5 * cs * 0.75, res.y * 0.5 - cs * 0.5), cs, int(pct * 100.0), 3);
    col += sc * glyphBit(43, (fc - vec2(res.x * 0.5 + 1.6 * cs * 0.75, res.y * 0.5 - cs * 0.5)) / vec2(cs * 0.75, cs));
    float blink = step(0.5, fract(pt * 2.0));
    if (outcome < 0.5) col += AMB * wordAll(44, fc, vec2(res.x * 0.5, res.y * 0.9), res.y * 0.05, 1.0) * (0.6 + 0.4 * blink);
    else col += GRN * wordAll(45, fc, vec2(res.x * 0.5, res.y * 0.9), res.y * 0.05, 1.0);
    // Einschläge: kurze helle Treffer auf dem Schild
    float hit = step(0.9, hash1(floor(pt * 3.0) + uSeed + 7.0)) * step(0.5, fract(pt * 3.0) * 2.0) * (1.0 - outcome);
    vec2 hp = vec2(hash1(floor(pt * 3.0) + 1.0 + uSeed), hash1(floor(pt * 3.0) + 2.0 + uSeed)) - 0.5;
    col += vec3(1.0) * hit * smoothstep(0.08, 0.0, length(p - hp * 0.4)) * fill;
    col += vec3(1.0) * hit * 0.08;
    return col;
}
vec3 intruderScene(vec2 fc, vec3 code, float pt, float len, float pct, float outcome) {
    vec2 res = iResolution;
    vec2 uv = fc / res;
    float cs = res.y / ROWS, cw = cs * 0.75;
    vec2 cell = floor(fc / vec2(cw, cs));
    float cols = floor(res.x / cw);
    vec3 col = code * 0.8;
    // Cursor wandert in Sprüngen (Zufallspfad), Spur bleibt kurz sichtbar
    float stepT = 6.0;
    float n = floor(pt * stepT);
    vec2 cur = vec2(cols * 0.5, ROWS * 0.5);
    for (int i = 0; i < 48; i++) {
        float fi = float(i);
        if (fi > n) break;
        float h = hash1(fi * 3.1 + uSeed + 11.0);
        vec2 stp = h < 0.25 ? vec2(1, 0) : (h < 0.5 ? vec2(-1, 0) : (h < 0.75 ? vec2(0, 1) : vec2(0, -1)));
        cur = clamp(cur + stp * (2.0 + floor(hash1(fi + uSeed + 5.0) * 4.0)), vec2(2.0), vec2(cols - 3.0, ROWS - 3.0));
        float age = n - fi;
        if (all(equal(cell, cur))) col += vec3(1.0, 0.3, 0.2) * exp(-age * 0.25) * 1.2;
    }
    if (outcome < 0.5 && all(equal(cell, cur))) col = vec3(1.0, 0.9, 0.8) * (0.6 + 0.4 * sin(pt * 20.0));
    if (outcome > 0.5) {
        // isoliert: grüner Rahmen um den Cursor
        vec2 cc = (cur + 0.5) * vec2(cw, cs);
        float box = rect(fc, cc - vec2(cw, cs) * 2.5, cc + vec2(cw, cs) * 2.5) - rect(fc, cc - vec2(cw, cs) * 2.2, cc + vec2(cw, cs) * 2.2);
        col += GRN * box;
        col += GRN * wordAll(48, fc, vec2(res.x * 0.5, res.y * 0.9), res.y * 0.05, 1.0);
    } else {
        float blink = step(0.5, fract(pt * 2.0));
        col += RED * wordAll(46, fc, vec2(res.x * 0.5, res.y * 0.9), res.y * 0.045, 1.0) * (0.6 + 0.4 * blink);
    }
    // Ortungsbalken unten
    float cs2 = res.y * 0.03;
    vec2 org = vec2(res.x * 0.5 - 12.0 * cs2 * 0.75, res.y * 0.03);
    col += AMB * wordAll(47, fc, org, cs2, 0.0);
    col += AMB * number(fc, org + vec2(7.0 * cs2 * 0.75, 0.0), cs2, int(pct * 100.0), 3);
    col += AMB * glyphBit(43, (fc - org - vec2(10.0 * cs2 * 0.75, 0.0)) / vec2(cs2 * 0.75, cs2));
    float bar = rect(uv, vec2(0.6, 0.032), vec2(0.6 + 0.3 * pct, 0.052));
    float frameB = rect(uv, vec2(0.598, 0.03), vec2(0.902, 0.054)) - rect(uv, vec2(0.6, 0.032), vec2(0.9, 0.052));
    col += AMB * (bar + frameB * 0.6);
    return col;
}

void main() {
    vec2 res = iResolution;
    vec2 fc = vUv * res;
    float t = iTime;
    gSeed = uSeed;
    int phase = int(uPhase + 0.5);
    float pt = uPhaseT, len = max(uPhaseLen, 0.001), pp = clamp(pt / len, 0.0, 1.0);
    int vc = int(uCodeVar + 0.5), ve = int(uErrVar + 0.5);
    vec3 code = codeScene(fc, vc, uCodeT, uCodeProg);
    vec3 col = code;
    if (phase == 1) {
        // kleine Beat-Glitches schon in der Code-Phase: kurz verschobene Streifen
        float g = uBeat * step(0.75, uCodeProg * 0.5 + hash1(floor(t * 10.0)));
        if (g > 0.3) {
            float band = floor(fc.y / (res.y / 16.0));
            float sh = (hash12(vec2(band, floor(t * 10.0))) - 0.5) * res.x * 0.05 * step(0.6, hash12(vec2(band, 1.0 + floor(t * 10.0))));
            col = mix(col, codeScene(vec2(mod(fc.x + sh, res.x), fc.y), vc, uCodeT, uCodeProg), step(0.001, abs(sh)));
            col += RED * 0.08 * g;
        }
    } else if (phase == 2) col = breakdown(fc, clamp(pp * uGlitch, 0.0, 1.0), vc, uCodeT, uCodeProg);
    else if (phase == 3) {
        col = errorScene(fc, ve, pt, pp);
        col += vec3(1.0, 0.6, 0.5) * exp(-pt * 10.0);
        float fade = smoothstep(0.85, 1.0, pp);
        col = mix(col, vec3(hash13(vec3(floor(fc / 2.0), floor(t * 30.0)))) * 0.5, fade * step(0.5, hash1(floor(t * 20.0))));
    }
    else if (phase == 4) col = recovery(fc, pt, pp);
    else if (phase == 5) col = reboot(fc, pt, pp);
    else if (phase == 6) col = promptScene(fc, code, pt, len, int(uPrompt + 0.5));
    else if (phase == 7) col = virusScene(fc, code, pt, len, uPct, uOutcome);
    else if (phase == 8) col = shieldScene(fc, code, pt, len, uPct, uOutcome);
    else if (phase == 9) col = bannerScene(fc, code, pt, len, int(uWordA + 0.5), int(uWordB + 0.5), GRN, 0.0);
    else if (phase == 10) col = bannerScene(fc, code, pt, len, int(uWordA + 0.5), int(uWordB + 0.5), RED, 1.0);
    else if (phase == 11) col = intruderScene(fc, code, pt, len, uPct, uOutcome);

    // Monitor-Look: Scanlines, Vignette
    vec2 uv = fc / res;
    col *= 0.86 + 0.14 * step(0.5, fract(fc.y / 3.0));
    col *= 1.0 - 0.4 * pow(length(uv - 0.5) * 1.35, 2.0);
    fragColor = vec4(col, 1.0);
}
