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
uniform float uCodeForce;    // Test: >0 erzwingt Code-Variante (Wert-1, 0..5)
uniform float uErrorForce;   // Test: >0 erzwingt Fehler-Variante (Wert-1, 0..5)
uniform float uPhaseForce;   // Test: 1 Code, 2 Zusammenbruch, 3 Fehler, 4 Wiederherstellung, 5 Neustart

const float CYCLE = 24.0;    // Sekunden pro Durchlauf
const float ROWS = 40.0;     // Textzeilen im Code-Raster
const vec3 GRN = vec3(0.25, 1.0, 0.35);
const vec3 RED = vec3(1.0, 0.12, 0.08);
const vec3 AMB = vec3(1.0, 0.75, 0.2);
float gSeed = 0.0;           // pro Durchlauf anders, damit sich der Code nicht wiederholt

// Zeichen: 0-25 A-Z, 26-35 0-9, 36 Leer, dann .:-[]#%/><_=+*!?{}();"~| und Backslash
const int NGLYPH = 62;
int FONT[62] = int[62](589284910, 521715247, 1007715390, 521717295, 1041284159, 34651199, 1025041470, 588840497, 1044517023, 211034396, 588553521, 1041269793, 588830577, 589092465, 488162862, 34651695, 748340782, 580042287, 520632382, 138547359, 488162865, 145278513, 599442993, 588583249, 138547537, 1041305887, 488232750, 474091716, 1042424366, 520632847, 277849420, 520633407, 488160302, 69345823, 488159790, 487094830, 0, 134217728, 4194432, 31744, 471926862, 478421262, 368389098, 866193779, 1118480, 1118273, 17043728, 1040187392, 1016800, 145536, 703136, 134353028, 134357550, 406980748, 205660294, 272765064, 71438466, 71303296, 330, 283712, 138547332, 17043521);
int WORDS[319] = int[319](4, 17, 17, 14, 17, 18, 24, 18, 19, 4, 12, 5, 4, 7, 11, 4, 17, 10, 4, 17, 13, 4, 11, 36, 15, 0, 13, 8, 2, 25, 20, 6, 17, 8, 5, 5, 36, 21, 4, 17, 22, 4, 8, 6, 4, 17, 19, 5, 0, 19, 0, 11, 2, 14, 17, 4, 36, 3, 20, 12, 15, 13, 4, 20, 18, 19, 0, 17, 19, 18, 8, 6, 13, 0, 11, 36, 21, 4, 17, 11, 14, 17, 4, 13, 18, 15, 4, 8, 2, 7, 4, 17, 5, 4, 7, 11, 4, 17, 20, 13, 1, 4, 10, 0, 13, 13, 19, 4, 17, 36, 1, 4, 5, 4, 7, 11, 0, 1, 1, 17, 20, 2, 7, 10, 4, 17, 13, 36, 8, 13, 18, 19, 0, 1, 8, 11, 3, 0, 19, 4, 13, 36, 10, 14, 17, 17, 20, 15, 19, 22, 0, 17, 13, 20, 13, 6, 18, 2, 7, 8, 11, 3, 4, 36, 26, 43, 18, 19, 0, 2, 10, 36, 14, 21, 4, 17, 5, 11, 14, 22, 18, 4, 6, 12, 4, 13, 19, 0, 19, 8, 14, 13, 36, 5, 0, 20, 11, 19, 15, 17, 20, 4, 5, 18, 20, 12, 12, 4, 36, 5, 0, 11, 18, 2, 7, 1, 20, 18, 36, 4, 17, 17, 14, 17, 0, 2, 7, 19, 20, 13, 6, 5, 4, 7, 11, 4, 17, 2, 14, 3, 4, 15, 0, 13, 8, 2, 19, 14, 19, 0, 11, 0, 20, 18, 5, 0, 11, 11, 13, 8, 2, 7, 19, 36, 1, 4, 7, 4, 1, 1, 0, 17, 40, 36, 14, 10, 36, 41, 40, 22, 0, 17, 13, 41, 40, 5, 0, 8, 11, 41, 26, 23, 4, 17, 17, 36, 22, 8, 4, 3, 4, 17, 7, 4, 17, 18, 19, 4, 11, 11, 20, 13, 6, 18, 24, 18, 19, 4, 12);
// Wörter: 0=ERROR, 1=SYSTEMFEHLER, 2=KERNEL PANIC, 3=ZUGRIFF VERWEIGERT, 4=FATAL, 5=CORE DUMP, 6=NEUSTART, 7=SIGNAL VERLOREN, 8=SPEICHERFEHLER, 9=UNBEKANNTER BEFEHL, 10=ABBRUCH, 11=KERN INSTABIL, 12=DATEN KORRUPT, 13=WARNUNG, 14=SCHILDE 0%, 15=STACK OVERFLOW, 16=SEGMENTATION FAULT, 17=PRUEFSUMME FALSCH, 18=BUS ERROR, 19=ACHTUNG, 20=FEHLERCODE, 21=PANIC, 22=TOTALAUSFALL, 23=NICHT BEHEBBAR, 24=[ OK ], 25=[WARN], 26=[FAIL], 27=0X, 28=ERR , 29=WIEDERHERSTELLUNG, 30=SYSTEM
int WSTART[31] = int[31](0, 5, 17, 29, 47, 52, 61, 69, 84, 98, 116, 123, 136, 149, 156, 166, 180, 198, 215, 224, 231, 241, 246, 258, 272, 278, 284, 290, 292, 296, 313);
int WLEN[31] = int[31](5, 12, 12, 18, 5, 9, 8, 15, 14, 18, 7, 13, 13, 7, 10, 14, 18, 17, 9, 7, 10, 5, 12, 14, 6, 6, 6, 2, 4, 17, 6);

// ---- Hashes ohne sin(): auf jeder GPU gleich
float hash1(float n) { n = fract((n + gSeed) * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx + gSeed) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p) { p = fract((p + gSeed) * vec3(0.1031, 0.1030, 0.0973)); p += dot(p, p.yxz + 33.33); return fract((p.x + p.y) * p.z); }
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

void main() {
    vec2 res = iResolution;
    vec2 fc = vUv * res;
    float t = iTime;
    float c = floor(t / CYCLE);
    float tc = t - c * CYCLE;
    gSeed = c * 37.0;
    float codeLen = 12.0 + 4.0 * hash1(0.11);
    float breakLen = 2.5, errLen = 4.5, bootLen = 0.8;
    float recLen = CYCLE - codeLen - breakLen - errLen - bootLen;
    int vc = c < 0.5 ? 0 : int(hash1(7.3) * 6.0);
    int ve = int(hash1(19.1) * 6.0);
    if (uCodeForce > 0.5) vc = int(uCodeForce) - 1;
    if (uErrorForce > 0.5) ve = int(uErrorForce) - 1;
    vec3 col;
    int phase; float pt; float pp;
    if (uPhaseForce > 0.5) {
        phase = int(uPhaseForce);
        float len = phase == 1 ? 14.0 : (phase == 2 ? breakLen : (phase == 3 ? errLen : (phase == 4 ? 3.0 : bootLen)));
        pt = mod(t, len); pp = pt / len;
    } else if (tc < codeLen) { phase = 1; pt = tc; pp = tc / codeLen; }
    else if (tc < codeLen + breakLen) { phase = 2; pt = tc - codeLen; pp = pt / breakLen; }
    else if (tc < codeLen + breakLen + errLen) { phase = 3; pt = tc - codeLen - breakLen; pp = pt / errLen; }
    else if (tc < CYCLE - bootLen) { phase = 4; pt = tc - codeLen - breakLen - errLen; pp = pt / recLen; }
    else { phase = 5; pt = tc - (CYCLE - bootLen); pp = pt / bootLen; }

    if (phase == 1) {
        col = codeScene(fc, vc, pt, pp);
        // kleine Beat-Glitches schon in der Code-Phase: kurz verschobene Streifen
        float g = uBeat * step(0.75, pp * 0.5 + hash1(floor(t * 10.0)));
        if (g > 0.3) {
            float band = floor(fc.y / (res.y / 16.0));
            float sh = (hash12(vec2(band, floor(t * 10.0))) - 0.5) * res.x * 0.05 * step(0.6, hash12(vec2(band, 1.0 + floor(t * 10.0))));
            col = mix(col, codeScene(vec2(mod(fc.x + sh, res.x), fc.y), vc, pt, pp), step(0.001, abs(sh)));
            col += RED * 0.08 * g;
        }
    } else if (phase == 2) col = breakdown(fc, pp, vc, codeLen + pt, 1.0);
    else if (phase == 3) {
        col = errorScene(fc, ve, pt, pp);
        // am Anfang kurzer Weißblitz, zum Ende Rauschen
        col += vec3(1.0, 0.6, 0.5) * exp(-pt * 10.0);
        float fade = smoothstep(0.85, 1.0, pp);
        col = mix(col, vec3(hash13(vec3(floor(fc / 2.0), floor(t * 30.0)))) * 0.5, fade * step(0.5, hash1(floor(t * 20.0))));
    } else if (phase == 4) col = recovery(fc, pt, pp);
    else col = reboot(fc, pt, pp);

    // Monitor-Look: Scanlines, Vignette
    vec2 uv = fc / res;
    col *= 0.86 + 0.14 * step(0.5, fract(fc.y / 3.0));
    col *= 1.0 - 0.4 * pow(length(uv - 0.5) * 1.35, 2.0);
    fragColor = vec4(col, 1.0);
}
