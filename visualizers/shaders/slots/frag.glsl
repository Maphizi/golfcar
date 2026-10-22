#version 140
// Slotmaschinen aller Themen: Nahaufnahme von 3 bis 5 Walzen (uNReels), die die Walzenfläche uArea füllen. Gedruckte
// Symbole auf gewölbten Trommeln, Licht von oben, dunkle Trennstege (Lauflicht auf den Beat), Themenrahmen uFrameTex
// darüber (Alpha aus dem Luma-Key: Mitte Schwarz = Walzen sichtbar; helle gesättigte Stellen pulsen zum Bass, Höhen
// funkeln, Drop = uFlash). Ohne Rahmen (uFrameOK 0) eine dunkle Blende. Beim Drehen verschwimmt das Bild wie im Traum
// (Unschärfe je Walze), beim Stehenbleiben wird es wieder scharf. Symbole aus dem Atlas uSpriteTex (Zeile uTheme,
// Streifen ab uStripRow), Zustand vom Controller (visualizers/scenes/slots.py).
// uStyle: 0 Space (Goldregen), 1 Natur (Glühwürmchen, Blätter, Fuchs, Lichthirsch, Sporen), 2 Cyber (Chips, Hologramm-
// Feuerwerk, Samurai, Glitch), 3 Zukunft (Dollarregen, Feuerspuren, Professor, Zeitmaschine, Blitz, Schwarzweiß).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSpriteTex, uFrameTex, uFigTex;
uniform vec2 uAtlasSize, uTile, uFrameSize, uFigSize;
uniform vec4 uArea;                                   // Walzenfläche x0, y0, x1, y1 (Bildanteile, von unten)
uniform float uTheme, uState, uStateT, uWin, uWinMask, uWinLine, uFade, uStripRow, uNReels, uStyle, uKeyed, uFrameOK;
uniform vec3 uColA, uColB;
uniform vec4 uReel0, uReel1, uReel2, uReel3, uReel4;  // je Walze: Position, Drehzahl, Unschärfe, Sekunden seit Stopp
uniform vec4 uFig;                                    // Figur: Zelle A, Zelle B, Mischung, Bogen vorhanden
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uFlash, uDropT, uStep, uStepPhase, uPattern;
uniform float uStake, uStakeT, uSepia;

const float STRIP = 32.0;
const float PI = 3.14159265;
const vec3 GOLD = vec3(1.0, 0.78, 0.3);
const vec3 BOLT = vec3(0.75, 0.85, 1.0);

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
float sq(float x) { return x * x; }
float ex(float x) { return exp(max(x, -60.0)); }     // exp mit sehr großem negativem Argument liefert auf llvmpipe Müll
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
vec3 hueShift(vec3 c, float a) {
    const vec3 k = vec3(0.57735);
    float cs = cos(a), sn = sin(a);
    return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs);
}
vec4 bilin(sampler2D tex, vec2 px, vec2 size, vec2 lo, vec2 hi) {
    vec2 p = clamp(px - 0.5, lo, hi);
    vec2 i = floor(p), f = fract(p);
    vec2 i1 = min(i + 1.0, hi);
    vec4 a = texture(tex, (i + 0.5) / size), b = texture(tex, (vec2(i1.x, i.y) + 0.5) / size);
    vec4 c = texture(tex, (vec2(i.x, i1.y) + 0.5) / size), d = texture(tex, (i1 + 0.5) / size);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
vec4 reelData(float i) { return i < 0.5 ? uReel0 : (i < 1.5 ? uReel1 : (i < 2.5 ? uReel2 : (i < 3.5 ? uReel3 : uReel4))); }
float maskBit(float i) { return mod(floor(uWinMask / pow(2.0, i) + 0.001), 2.0); }
float firstBit() { for (int i = 0; i < 5; i++) if (maskBit(float(i)) > 0.5) return float(i); return 0.0; }
// Zeile der Gewinnlinie auf Walze i (-1 unter, 0 Mitte, +1 über der Mitte)
float rowOff(float i) {
    if (uWinLine < 0.5 || uWinLine > 2.5) return 0.0;
    float d = i - firstBit() - 1.0;
    return uWinLine < 1.5 ? d : -d;
}
float stripSymbol(float reel, float k) {
    float kk = mod(k, STRIP);
    return floor(texture(uSpriteTex, vec2((kk + 0.5) / uAtlasSize.x, (uStripRow + reel + 0.5) / uAtlasSize.y)).r * 255.0 + 0.5);
}
// Symbol idx (Kachel idx der Zeile uTheme), Position l in 0..1 über die Kachel: bilinear aus dem Bildbogen
vec4 sprite(float idx, vec2 l) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return vec4(0.0);
    vec2 base = vec2(idx * uTile.x, uTheme * uTile.y);
    vec4 s = bilin(uSpriteTex, base + l * uTile, uAtlasSize, base, base + uTile - 1.0);
    if (uKeyed < 0.5) {                                     // gedrucktes Etikett mit runden Ecken
        vec2 c = abs(l - 0.5) - vec2(0.44, 0.42);
        float d = length(max(c, 0.0)) - 0.06;
        s.a *= smoothstep(0.012, -0.012, d);
    }
    return s;
}
// Figuren-Atlas (Zellen 192 px, Zeile 0 oben), d in -1..1 über die Zelle
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0 || uFig.w < 0.5) return vec4(0.0);
    float cols = floor(uFigSize.x / 192.0 + 0.5), rows = floor(uFigSize.y / 192.0 + 0.5);
    float ci = mod(idx, cols), ri = floor(idx / cols);
    vec2 lo = vec2(ci * 192.0, (rows - 1.0 - ri) * 192.0);
    vec4 s = bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
    s.a = min(s.a, smoothstep(0.04, 0.16, max(s.r, max(s.g, s.b))));
    return s;
}
// Figur mit Fußpunkt foot (isotrope Bildkoordinaten p), halbe Breite hw
vec4 figAt(float idx, vec2 p, vec2 foot, float hw) {
    vec2 d = (p - foot) / hw;
    d.y = d.y - 1.0 + 0.04;
    return figCell(idx, d);
}
vec4 figMix(vec2 p, vec2 foot, float hw) { return mix(figAt(uFig.x, p, foot, hw), figAt(uFig.y, p, foot, hw), uFig.z); }
// Rahmen: Bild über die ganze Fläche (uv), Alpha = Luma-Key (im Controller berechnet)
vec4 frameAt(vec2 uv) { return bilin(uFrameTex, clamp(uv, 0.0, 1.0) * uFrameSize, uFrameSize, vec2(0.0), uFrameSize - 1.0); }
float lightsOf(vec3 c) {                                   // helle, gesättigte Stellen = Lampen, Neon, Pilze
    float lum = max(c.r, max(c.g, c.b));
    float sat = lum - min(c.r, min(c.g, c.b));
    return smoothstep(0.42, 0.75, lum) * smoothstep(0.15, 0.4, sat);
}
// Lauflicht: Zone z von nz Zonen (Stege 0..n, Rahmen nach x-Position), Muster uPattern, Beat-Zähler uStep
float lit(float z, float nz) {
    float ph = 1.0 - 0.6 * uStepPhase;
    float s = uStep;
    if (uPattern < 0.5) return abs(z - mod(s, nz)) < 0.5 ? ph : 0.0;                            // Lauf links -> rechts
    if (uPattern < 1.5) { float m = mod(s, 2.0 * (nz - 1.0)); float zz = m < nz - 0.5 ? m : 2.0 * (nz - 1.0) - m;
                          return abs(z - zz) < 0.5 ? ph : 0.0; }                                 // Pendel
    if (uPattern < 2.5) return mod(z + s, 2.0) < 0.5 ? ph : 0.0;                                 // gerade / ungerade
    float c = (nz - 1.0) * 0.5, k = mod(s, floor(c) + 1.0);                                      // von außen nach innen
    return abs(abs(z - c) - (c - k)) < 0.6 ? ph : 0.0;
}

// Band der Trommel (zwischen und unter den Symbolen) je Stil
vec3 bandColor(float reel, vec2 q, float yc, float grain) {
    float flow = noise(vec2(yc * 1.6 + iTime * 0.04, q.x * 1.2 + reel * 3.0));
    vec3 toneA = hueShift(uColA, 0.4 * sin(iTime * 0.05 + reel)) * 0.30 + 0.05;
    vec3 toneB = hueShift(uColB, 0.4 * sin(iTime * 0.04 + 2.0)) * 0.34 + 0.06;
    vec3 band = mix(toneA, toneB, smoothstep(0.3, 0.7, flow)) * (0.94 + grain);
    if (uStyle < 0.5) return band;
    if (uStyle < 1.5) {                                                       // feuchtes Holz mit Maserung
        float g = fbm(vec2(q.x * 3.0 + reel, yc * 14.0 + uSeed));
        vec3 wood = mix(vec3(0.10, 0.06, 0.03), vec3(0.22, 0.14, 0.07), g) * (0.8 + 0.4 * noise(vec2(q.x * 200.0, yc * 300.0)));
        return mix(wood, band * 0.6, 0.25);
    }
    if (uStyle < 2.5) {                                                       // dunkles Glas mit Leiterbahnen
        float trace = smoothstep(0.02, 0.0, abs(fract(q.x * 6.0 + yc * 2.0) - 0.5) - 0.02) + smoothstep(0.02, 0.0, abs(fract(yc * 9.0) - 0.5) - 0.01);
        vec3 glass = vec3(0.03, 0.02, 0.06) + vec3(0.1, 0.0, 0.2) * noise(vec2(q.x * 20.0, yc * 40.0));
        return glass + mix(uColB, uColA, 0.3) * trace * (0.06 + 0.3 * uBeatPulse) + band * 0.15;
    }
    float lines = smoothstep(0.02, 0.0, abs(fract(yc * 14.0) - 0.5) - 0.02);  // Samt mit Goldlinien
    vec3 velvet = vec3(0.08, 0.02, 0.03) + vec3(0.12, 0.03, 0.03) * noise(vec2(q.x * 24.0, yc * 48.0));
    return velvet + GOLD * lines * (0.05 + 0.2 * uBeatPulse) + band * 0.1;
}

// Ein Punkt auf der Trommel: q.x -0.5..0.5 über die Walzenbreite, q.y Bildhöheneinheiten um die Walzenmitte,
// H = Höhe der Walzenfläche, reelW = Walzenbreite (isotrop); Symbole 3:2 auf der abgerollten Trommel (Zelle = reelW / 1.5)
vec3 drumPixel(float reel, vec2 q, float pos, float H, float reelW, float speed) {
    float yn = clamp(q.y / (0.5 * H), -0.999, 0.999);
    float ang = asin(yn);                                   // Winkel auf dem Zylinder
    float yc = ang * H * 0.5;                               // abgerollte Position (Bildhöheneinheiten, 1:1 in der Mitte)
    float cell = reelW / 1.5;
    float k = floor(pos + yc / cell + 0.5);
    float ly = (yc - (k - pos) * cell) / cell + 0.5;
    float lx = q.x + 0.5;
    float grain = noise(vec2(q.x * 420.0, yc * 420.0)) * 0.05 + noise(vec2(q.x * 90.0, yc * 90.0)) * 0.03;
    vec3 band = bandColor(reel, q, yc, grain);
    vec2 cellP = vec2(lx, ly) - 0.5;
    if (uKeyed < 0.5) {                                     // je Symbol ein etwas helleres, abgerundetes Feld (Etikett)
        float label = smoothstep(0.0, 0.02, 0.40 - max(abs(cellP.x) * 1.15, abs(cellP.y)));
        band = mix(band, band * 1.35 + 0.04, label * 0.8);
    }
    float idx = stripSymbol(reel, k);
    float fill = uKeyed < 0.5 ? 0.88 : 0.94;
    vec2 l = cellP / fill + 0.5;
    vec4 s = sprite(idx, l);
    vec3 ink = s.rgb * (0.97 + grain * 0.6);                // gedrucktes Foto mit feinem Korn
    vec3 col = mix(band, ink, s.a);
    if (uKeyed > 0.5) {                                     // freigestellte Symbole glühen im Dunkeln, Jackpot stärker
        float onLine = smoothstep(0.35, 0.0, abs(q.y) / max(H, 0.01));
        float glow = (idx > 7.5 ? 0.45 : 0.2) + 0.35 * uBeatPulse * onLine;
        col += s.rgb * s.a * glow * uLive;
        if (uStyle > 2.5 && idx > 7.5) col += BOLT * s.a * 0.25 * (0.5 + 0.5 * sin(iTime * 9.0 + reel));
    }
    float sep = smoothstep(0.03, 0.0, min(ly, 1.0 - ly));
    col *= 1.0 - 0.25 * sep;
    if (uStyle > 2.5) col = mix(col, GOLD * 0.8, sep * 0.4);
    if (uStyle > 1.5 && uStyle < 2.5) col = mix(col, vec3(0.2, 0.8, 1.0), sep * 0.35);
    // Beleuchtung: Licht von schräg oben, Glanzband, Zylinderabschattung
    float diffuse = 0.30 + 0.70 * pow(max(cos(ang), 0.0), 0.7);
    float spec = 0.14 * pow(max(cos(ang - 0.32), 0.0), 30.0);
    col = col * diffuse + spec;
    col *= 1.0 - 0.45 * smoothstep(0.36, 0.5, abs(q.x));   // Walzenenden dunkler (Zylinder läuft in den Steg)
    float spin = clamp(speed / 8.0, 0.0, 1.0);
    col += uColA * 0.06 * spin * (0.6 + 0.4 * sin(iTime * 20.0 + reel));
    return col;
}

// Regen (Chips / Dollarscheine / Blätter) über das Bild, Stil-abhängige Form
vec3 rain(vec3 col, vec2 p, float aspect, float resultT, float n, float style) {
    for (int i = 0; i < 50; i++) {
        if (float(i) >= n) break;
        float fi = float(i);
        float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
        float age = resultT * (0.5 + 0.6 * h3) - h2 * 1.5;
        if (age < 0.0) continue;
        vec2 pos = vec2((0.1 + h1 * 0.8 - 0.5) * aspect + 0.03 * sin(age * 2.5 + fi), 0.55 - age * 0.22);
        if (pos.y < -0.55) continue;
        if (style < 1.5) {                                                   // Blätter
            vec2 d = rot(age * 2.0 + fi) * (p - pos);
            float leaf = smoothstep(0.0, -0.004, abs(d.x) * 1.6 + abs(d.y) * 0.9 - 0.014);
            vec3 lc = mix(vec3(0.9, 0.6, 0.2), vec3(0.4, 0.8, 0.3), h3);
            col = mix(col, lc * (0.7 + 0.3 * sin(fi)), leaf * 0.9);
        } else if (style < 2.5) {                                            // Chips
            vec2 d = rot(age * 4.0 + fi) * (p - pos);
            float chip = step(max(abs(d.x) * 1.6, abs(d.y) * 2.5), 0.013);
            col = mix(col, mix(vec3(1.0, 0.85, 0.2), vec3(0.3, 0.9, 1.0), h3) * (0.8 + 0.4 * sin(iTime * 10.0 + fi)), chip * 0.95);
        } else {                                                             // Dollarscheine, flattern
            vec2 d = rot(0.6 * sin(age * 3.0 + fi * 2.0) + h1 * 0.8) * (p - pos);
            float flap = 0.45 + 0.55 * abs(cos(age * 6.0 + fi));
            vec2 e = abs(d) / vec2(0.03, 0.014 * flap);
            float bill = step(max(e.x, e.y), 1.0);
            float border = step(0.78, max(e.x, e.y));
            float oval = smoothstep(0.45, 0.3, length(d / vec2(0.012, 0.01 * flap)));
            vec3 bc = mix(vec3(0.55, 0.68, 0.5), vec3(0.3, 0.45, 0.32), border + oval * 0.6) * (0.75 + 0.25 * flap) * (0.85 + 0.3 * uBeatPulse);
            col = mix(col, bc, bill * 0.95);
        }
    }
    return col;
}
// Blitz: gezackte Linie von from nach to (isotrope Koordinaten)
float bolt(vec2 p, vec2 from, vec2 to, float seed, float width) {
    float v = clamp((p.y - to.y) / (from.y - to.y), 0.0, 1.0);
    if (p.y > from.y + 0.02 || p.y < to.y - 0.03) return 0.0;
    float x = mix(to.x, from.x, v);
    float wob = (noise(vec2(v * 7.0 + seed, seed)) - 0.5) * 0.09 + (noise(vec2(v * 29.0 + seed * 3.0, seed + 5.0)) - 0.5) * 0.03;
    x += wob * smoothstep(0.0, 0.08, v) * smoothstep(1.0, 0.9, v);
    float d = abs(p.x - x);
    return ex(-d / width) + 0.35 * ex(-d / (width * 6.0));
}
// Feuerspur: zwei Glutlinien von x0 bis Kopf x1 auf Höhe y, Flammen darüber; rgb = Farbe, a = Deckung
vec4 fireTrail(vec2 p, float y, float x0, float x1, float t, float flare) {
    float lo = min(x0, x1), hi = max(x0, x1);
    if (p.x < lo - 0.03 || p.x > hi + 0.05) return vec4(0.0);
    float along = clamp((p.x - lo) / max(hi - lo, 0.001), 0.0, 1.0);
    float head = x1 > x0 ? along : 1.0 - along;
    float ends = smoothstep(lo - 0.03, lo + 0.03, p.x) * smoothstep(hi + 0.05, hi - 0.02, p.x);
    float dy = p.y - y;
    float lines = ex(-sq(dy * 200.0)) + ex(-sq((dy - 0.022) * 200.0));
    float flick = 0.6 + 0.4 * noise(vec2(p.x * 60.0 - t * 9.0, t * 4.0));
    float fl = fbm(vec2(p.x * 30.0, dy * 50.0 - t * 5.0));
    float flames = smoothstep(0.035, 0.0, max(dy - 0.012 - fl * 0.03 * (1.0 + flare), 0.0)) * step(-0.01, dy) * fl * 1.5;
    vec3 c = vec3(1.0, 0.55, 0.12) * lines * flick * 1.4 + vec3(1.0, 0.35, 0.05) * flames;
    c += vec3(1.0, 0.9, 0.6) * ex(-sq(dy * 320.0)) * (0.5 + 0.5 * flick) * 0.5;
    float a = clamp(lines * 1.8 + flames * 1.6, 0.0, 1.0) * ends * (0.5 + 0.5 * head);
    return vec4(c * (0.35 + 0.65 * head), a);
}
vec3 blendFire(vec3 col, vec4 f) { col = mix(col, col * 0.3, f.a * 0.8); return mix(col, f.rgb * 1.4, f.a) + f.rgb * f.a * 0.3; }

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = vUv;
    float t = iTime;
    float n = clamp(floor(uNReels + 0.5), 3.0, 5.0);
    bool result = uState > 1.5 && uState < 2.5;
    float resultT = result ? uStateT : -1.0;
    float winPulse = result && uWin > 0.5 ? 0.5 + 0.5 * sin(t * 4.0) : 0.0;
    float winK = (result && uWin > 0.5) ? smoothstep(0.0, 0.25, uStateT) : 0.0;     // Gewinn-Effekte
    float big = (result && uWin > 1.5) ? 1.0 : 0.0, jackpot = (result && uWin > 2.5) ? 1.0 : 0.0;
    vec3 winCol = jackpot > 0.5 ? vec3(1.0, 0.85, 0.4) : (big > 0.5 ? mix(uColA, vec3(1.0, 0.9, 0.6), 0.5) : uColA);
    if (jackpot > 0.5) winCol = hueShift(winCol, t * 2.0) * 0.6 + vec3(0.5, 0.4, 0.2);   // Jackpot: Farben laufen
    // Drop-Glitch (Cyber): Zeilen springen, Kanäle trennen sich
    float gl = (uStyle > 1.5 && uStyle < 2.5 && uDropT >= 0.0) ? ex(-uDropT * 2.5) : 0.0;
    if (gl > 0.01) {
        float row = floor(uv.y * 50.0 + floor(t * 10.0));
        uv.x += (hash12(vec2(row, floor(t * 8.0))) - 0.5) * 0.06 * gl * step(0.6, hash12(vec2(row, 7.0)));
    }
    // Blitz (Zukunft): beim Drop und zum Jackpot schlägt er von oben in die Walzen ein
    float boltAge = -1.0, boltSeed = uSeed;
    if (uStyle > 2.5) {
        if (uDropT >= 0.0 && uDropT < 1.5) boltAge = uDropT;
        if (jackpot > 0.0 && resultT < 1.2) { boltAge = resultT * 0.5; boltSeed = 42.0; }
    }
    float boltK = boltAge >= 0.0 ? ex(-boltAge * 4.0) * (0.6 + 0.4 * step(0.5, hash12(vec2(floor(t * 40.0), 1.0)))) : 0.0;
    uv += vec2(0.004, 0.003) * boltK * sin(t * 50.0);
    uv += vec2(0.003, 0.002) * jackpot * sin(t * 30.0) * ex(-resultT * 0.6);
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);
    // Gewinn: kurzer Stoß nach innen (die Maschine "zuckt")
    p *= 1.0 - 0.035 * ex(-uStateT * 6.0) * winK * (1.0 + big);

    // ---- Walzenfläche
    float ax0 = (uArea.x - 0.5) * aspect, ax1 = (uArea.z - 0.5) * aspect;
    float ay0 = uArea.y - 0.5, ay1 = uArea.w - 0.5;
    float H = ay1 - ay0, ymid = (ay0 + ay1) * 0.5;
    float reelW = (ax1 - ax0) / n;
    float cell = reelW / 1.5;
    float ri = floor((p.x - ax0) / reelW);
    vec3 col = vec3(0.025, 0.025, 0.03) + uColB * 0.03;       // Blende
    float moving = 0.0;
    for (int i = 0; i < 5; i++) if (float(i) < n) moving = max(moving, reelData(float(i)).z);
    bool onReel = ri >= 0.0 && ri <= n - 1.0 && p.y > ay0 && p.y < ay1;
    if (onReel) {
        float cx = ax0 + (ri + 0.5) * reelW;
        vec2 q = vec2((p.x - cx) / reelW, p.y - ymid);
        vec4 rd = reelData(ri);
        float pos = rd.x, sp = rd.y, dream = clamp(rd.z, 0.0, 1.0);
        // Nur in Bewegung: weiche Unschärfe in der Fläche plus Bewegungsunschärfe entlang der Walze
        float blurR = 0.014 * dream * (1.0 + 0.3 * sin(t * 0.7));
        float mblur = sp * 0.018;
        vec3 acc = vec3(0.0);
        if (dream < 0.02 && sp < 0.5) {
            acc = drumPixel(ri, q, pos, H, reelW, sp);
        } else {
            for (int i = 0; i < 6; i++) {
                float fi = float(i);
                float a = fi * 2.399 + t * 0.3;
                float rr = blurR * sqrt((fi + 0.5) / 6.0);
                vec2 off = vec2(cos(a) * rr / reelW, sin(a) * rr);
                float dp = (fi - 2.5) / 2.5 * mblur;
                acc += drumPixel(ri, q + off, pos + dp, H, reelW, sp);
            }
            acc /= 6.0;
            vec2 ghost = vec2(0.0, 0.03 * sin(t * 0.5)) * dream;             // Doppelbild, das langsam wandert
            acc = mix(acc, drumPixel(ri, q + ghost, pos, H, reelW, sp), 0.25 * dream);
        }
        col = acc;
        // Stopp-Blitz: die Walze leuchtet kurz auf, wenn sie einrastet
        float st = rd.w;
        if (st >= 0.0 && st < 0.4) col += (uStyle < 0.5 ? winCol : uColA) * (1.0 - st / 0.4) * 0.18;
        // Gewinnlinie: nur bei Ergebnis, Leuchten auf dem Band der Gewinnsymbole (Zeile je Walze)
        float lineY = rowOff(ri) * cell;
        float band = smoothstep(cell * 0.62, cell * 0.5, abs(q.y - lineY));
        if (result && maskBit(ri) > 0.5 && uWin > 0.5) {
            vec3 glow = winCol;
            col += glow * band * winPulse * (0.14 + 0.1 * big);
            float sweep = smoothstep(0.08, 0.0, abs(fract(uStateT * 0.6) * (ax1 - ax0 + 0.4) + ax0 - 0.2 - p.x));
            col += glow * band * sweep * 0.3;
            col += vec3(1.0, 0.97, 0.9) * band * ex(-uStateT * 5.0) * (0.9 + 0.6 * big);      // Aufblitzen
            vec2 sp2 = vec2(q.x * 30.0, (q.y + 0.5) * 24.0 - uStateT * (3.0 + 2.0 * big));   // Funken steigen auf
            vec2 sc = floor(sp2), sf = fract(sp2) - 0.5;
            float sh = hash12(sc + ri * 7.0);
            float spark = step(0.86 - 0.08 * big, sh) * smoothstep(0.22, 0.0, length(sf)) * (0.6 + 0.4 * sin(t * 9.0 + sh * 20.0));
            col += glow * spark * winK * smoothstep(0.0, 0.3, band + 0.1) * 1.2;
            col *= 1.0 + 0.12 * band * winPulse * (1.0 + big);
        }
        if (result && big > 0.5) {                                             // Lichtstrahlen aus der Gewinnlinie
            vec2 rp = vec2(q.x * 1.6, q.y - lineY);
            float ang = atan(rp.y, rp.x);
            float rays = pow(0.5 + 0.5 * sin(ang * 10.0 + t * 3.0 + ri), 6.0) * ex(-length(rp) * 2.2);
            col += winCol * rays * winK * (0.18 + 0.12 * jackpot);
        }
        if (result && uWin < 0.5) col *= 0.82 + 0.18 * smoothstep(0.0, 1.2, uStateT);
        col *= 1.0 - 0.55 * smoothstep(0.36 * H, 0.49 * H, abs(q.y));        // Blendenschatten oben/unten
        col *= 0.85 + 0.15 * uLive;                                            // Stille: etwas dunkler
    }
    // ---- Trennstege zwischen und neben den Walzen mit Lauflicht (Beat) und Markierung der Gewinnlinie
    float nz = n + 1.0;
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        if (fi > n) break;
        float exx = ax0 + fi * reelW;
        float d = abs(p.x - exx);
        float bar = smoothstep(0.012, 0.009, d) * step(ay0 - 0.02, p.y) * step(p.y, ay1 + 0.02);
        float hi = smoothstep(0.004, 0.0, abs(d - 0.006)) * 0.35;
        float run = lit(fi, nz) * uLive;
        vec3 barCol = vec3(0.07, 0.07, 0.08) + vec3(hi);
        barCol += uColA * (run * 0.9 + 0.15 * uBassS) * (0.6 + 0.4 * smoothstep(0.012, 0.0, abs(d - 0.004)));
        col = mix(col, barCol, bar);
        col += uColA * run * smoothstep(0.03, 0.0, d) * 0.25 * (1.0 - bar);                 // Schein auf die Walzenränder
        float m = smoothstep(0.012, 0.0, d) * smoothstep(0.02, 0.0, abs(p.y - ymid));
        col += uColA * m * (0.6 + 0.3 * sin(t * 2.0) + winPulse);
    }
    // ---- Stil-Effekte über den Walzen (Figuren, Regen, Feuer, Hirsch), bevor der Rahmen darüber liegt
    vec3 reelsOnly = col;
    // Jackpot (Space): Goldregen über das ganze Bild
    if (result && jackpot > 0.5 && uStyle < 0.5) {
        vec2 gp = vec2(p.x * 26.0, (p.y + 0.5) * 16.0 + uStateT * 2.5);
        vec2 gc = floor(gp), gf = fract(gp) - 0.5;
        float gh = hash12(gc + 11.0);
        float drop = step(0.8, gh) * smoothstep(0.18, 0.0, length(gf * vec2(1.0, 0.5))) * (0.7 + 0.3 * sin(t * 6.0 + gh * 30.0));
        col += vec3(1.0, 0.85, 0.35) * drop * winK * 0.9;
    }
    // Natur: Glühwürmchen bei jedem Gewinn, Blätter + Fuchs bei großem, Lichthirsch beim Jackpot, Sporen beim Drop
    if (uStyle > 0.5 && uStyle < 1.5) {
        if (result && uWin > 0.5) {
            int nf = big > 0.5 ? 36 : 16;
            for (int i = 0; i < 36; i++) {
                if (i >= nf) break;
                float fi = float(i);
                float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
                float age = resultT - h3 * 0.8;
                if (age < 0.0) continue;
                vec2 start = vec2(mix(ax0, ax1, h1), ymid + (h2 - 0.5) * cell);
                vec2 fp = start + vec2((h1 - 0.5) * 0.5 * age + 0.03 * sin(age * 3.0 + fi), age * (0.05 + 0.08 * h2) + 0.02 * sin(age * 4.0 + fi * 2.0));
                float g = smoothstep(0.007, 0.0, length(p - fp)) * (0.5 + 0.5 * sin(age * 8.0 + fi)) * smoothstep(6.0, 3.0, age);
                col += vec3(1.0, 0.95, 0.5) * g * 1.5;
            }
        }
        if (big > 0.5) {
            col = rain(col, p, aspect, resultT, 30.0, 1.0);
            float enter = smoothstep(0.0, 0.6, resultT) * smoothstep(5.0, 4.4, resultT);
            if (jackpot > 0.5) enter = 0.0;
            vec4 s = figMix(p, vec2(ax0 + 0.2, ay0 + 0.03 + 0.012 * uBassS + 0.006 * sin(t * 6.0) * uBeatPulse), 0.17);
            col = mix(col, s.rgb * (0.8 + 0.3 * uBassS), s.a * enter);
        }
        if (jackpot > 0.5) {                                                 // der Lichthirsch (Jackpot-Symbol) galoppiert von rechts nach links
            col += reelsOnly * 0.5 * ex(-resultT * 0.4) * (0.6 + 0.4 * sin(t * 10.0));
            float run = resultT / 6.0;
            vec2 hp = vec2(ax1 + 0.3 - run * (ax1 - ax0 + 0.9), ymid + 0.05 * abs(sin(resultT * 6.0)));
            float hs = 0.24;
            vec2 d = (p - hp) / hs;
            d.y *= 1.5;
            if (abs(d.x) < 1.0 && abs(d.y) < 1.0) {
                vec2 l = vec2(1.0 - (d.x * 0.5 + 0.5), d.y * 0.5 + 0.5);    // Hirsch schaut nach links: Kachel spiegeln
                vec4 s = sprite(8.0, l);
                col = mix(col, s.rgb * (1.0 + 0.1 * sin(resultT * 12.0)) + vec3(0.3, 0.2, 0.0) * s.a, s.a);
                col += s.rgb * s.a * 0.8;
            }
            for (int i = 0; i < 24; i++) {                                   // Funkenschweif
                float fi = float(i);
                float h1 = hash12(vec2(fi, 23.0)), h2 = hash12(vec2(fi, 29.0));
                vec2 sp3 = hp + vec2(0.05 + h1 * 0.4, (h2 - 0.5) * 0.2 + 0.02 * sin(t * 5.0 + fi));
                float g = smoothstep(0.006, 0.0, length(p - sp3)) * (0.5 + 0.5 * sin(t * 15.0 + fi * 3.0));
                col += vec3(1.0, 0.8, 0.3) * g * 1.5;
            }
        }
        float sporeT = uDropT;
        if (jackpot > 0.5 && resultT < 4.0) sporeT = max(sporeT, resultT);
        if (sporeT >= 0.0) {                                                 // Sporen steigen von unten auf
            for (int i = 0; i < 30; i++) {
                float fi = float(i);
                float h1 = hash12(vec2(fi, 11.0)), h2 = hash12(vec2(fi, 13.0)), h3 = hash12(vec2(fi, 17.0));
                float age = sporeT - h1 * 0.5;
                if (age < 0.0) continue;
                vec2 sp3 = vec2((h2 - 0.5) * aspect * 0.8, ay0) + vec2((h2 - 0.5) * 0.8 * age, age * (0.12 + 0.18 * h3) - 0.015 * age * age);
                sp3.x += 0.02 * sin(age * 3.0 + fi);
                float g = smoothstep(0.012 + 0.004 * h3, 0.0, length(p - sp3)) * (1.0 - age / 4.0);
                col += hueShift(vec3(0.4, 1.0, 0.7), h3 * 1.5) * g * 1.2;
            }
        }
    }
    // Cyber: Chips regnen bei Gewinn, Hologramm-Feuerwerk + Samurai bei großem, Jackpot = Neon-Explosion
    if (uStyle > 1.5 && uStyle < 2.5) {
        if (result && uWin > 0.5) col = rain(col, p, aspect, resultT, big > 0.5 ? 50.0 : 24.0, 2.0);
        if (big > 0.5) {
            for (int k = 0; k < 6; k++) {
                float fk = float(k);
                float h1 = hash12(vec2(fk, 13.0)), h2 = hash12(vec2(fk, 17.0));
                float age = mod(resultT * 0.8 + h1 * 3.0, 2.0);
                vec2 c = vec2((h1 - 0.5) * aspect * 0.8, 0.05 + h2 * 0.35);
                vec2 d = p - c;
                float r = length(d), a = atan(d.y, d.x);
                float ring = ex(-sq((r - age * 0.15) * 40.0)) * pow(0.5 + 0.5 * sin(a * 14.0 + fk), 3.0) * (1.0 - age / 2.0);
                col += hueShift(vec3(1.0, 0.3, 0.9), fk * 1.1) * ring * 1.2;
            }
            float enter = smoothstep(0.0, 0.6, resultT) * smoothstep(5.0, 4.4, resultT);
            vec4 s = figMix(p, vec2(ax0 + 0.18, ay0 + 0.02 + 0.01 * uBassS + 0.008 * sin(t * 8.0) * uBeatPulse), 0.17);
            col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * enter);
            col += vec3(0.4, 0.9, 1.0) * s.a * enter * 0.25 * uBeatPulse;
        }
        if (jackpot > 0.5) {
            col += reelsOnly * 0.8 * ex(-resultT * 0.4) * (0.6 + 0.4 * sin(t * 12.0));
            col = mix(col, hueShift(col, sin(t * 3.0) * 1.0), 0.4 * ex(-resultT * 0.3));
        }
        col += (noise(vUv * 250.0 + t * 20.0) - 0.5) * 0.15 * gl;
    }
    // Zukunft: Dollarregen bei Gewinn, Feuerspuren + Professor bei großem, Jackpot = Blitz und die Zeitmaschine fährt durch
    if (uStyle > 2.5) {
        if (result && uWin > 0.5) col = rain(col, p, aspect, resultT, big > 0.5 ? 50.0 : 24.0, 3.0);
        if (big > 0.5 && jackpot < 0.5) {
            for (int k = 0; k < 2; k++) {
                float fk = float(k);
                float yk = ay0 + 0.12 + fk * 0.5;
                float head = mod(resultT * 0.45 + fk * 0.37, 1.3) - 0.15;
                float dir = fk < 0.5 ? 1.0 : -1.0;
                float x1 = dir > 0.0 ? mix(ax0, ax1, head) : mix(ax1, ax0, head);
                col = blendFire(col, fireTrail(p, yk, x1 - dir * 0.55, x1, t + fk * 3.0, uBassS));
            }
        }
        if (big > 0.5) {
            float enter = smoothstep(0.0, 0.6, resultT) * smoothstep(5.0, 4.4, resultT);
            if (jackpot > 0.5) enter = smoothstep(4.0, 4.8, resultT) * smoothstep(8.0, 7.4, resultT);   // nach der Zeitmaschine
            vec4 s = figMix(p, vec2(ax0 + 0.18, ay0 + 0.02 + 0.012 * uBassS + 0.01 * sin(t * 8.0) * uBeatPulse), 0.17);
            col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * enter);
            col += GOLD * s.a * enter * 0.25 * uBeatPulse;
        }
        if (jackpot > 0.5) {
            col += reelsOnly * 0.35 * ex(-resultT * 0.5) * (0.6 + 0.4 * sin(t * 12.0));
            float drive = clamp((resultT - 0.9) / 3.0, 0.0, 1.0);
            float cy = ymid - 0.15 + 0.012 * sin(t * 7.0);
            if (resultT >= 0.9 && drive < 1.0) {
                float cx = ax0 - 0.5 + drive * (ax1 - ax0 + 1.0);
                float frame = 14.0 + step(0.5, fract(t * 8.0));                 // Wagen mit Feuerspuren (Zellen 14/15)
                vec4 car = figAt(frame, p, vec2(cx, cy), 0.3);
                col = blendFire(col, fireTrail(p, cy + 0.005, cx - 0.9, cx - 0.12, t, 1.5));
                col += BOLT * car.a * 0.3 * step(0.5, fract(t * 10.0));
                col = mix(col, car.rgb * (1.0 + 0.3 * uBeatPulse), car.a);
                col += BOLT * ex(-abs(p.x - cx) * 6.0) * 0.08 * (0.5 + 0.5 * sin(t * 40.0));
            }
            if (drive >= 1.0) {
                vec4 rest = fireTrail(p, cy + 0.005, ax0 + 0.2, ax1 + 0.5, t, 0.5);
                rest.a *= ex(-(resultT - 3.9) * 1.2);
                col = blendFire(col, rest);
            }
        }
        if (boltK > 0.01) {
            vec2 hit = vec2((hash12(vec2(boltSeed, 2.0)) - 0.5) * aspect * 0.5, ymid + 0.1);
            float b = bolt(p, vec2((hash12(vec2(boltSeed, 1.0)) - 0.5) * aspect * 0.6, 0.55), hit, boltSeed, 0.009);
            b += 0.6 * bolt(p, vec2((hash12(vec2(boltSeed, 3.0)) - 0.5) * aspect * 0.8, 0.55), hit + vec2(0.05, 0.02), boltSeed + 7.0, 0.004);
            col *= 1.0 - 0.55 * boltK;
            col = mix(col, BOLT * 1.7, clamp(b * boltK * 2.5, 0.0, 1.0));
            col += vec3(1.0) * ex(-length(p - hit) * 6.0) * boltK * 0.9;
            col += reelsOnly * boltK * 0.8 * step(0.7, boltK);
        }
    }
    // Gewinn: Blende und Stege leuchten mit
    col += winCol * winK * winPulse * (0.08 + 0.12 * big) * (1.0 - smoothstep(0.0, 0.46, abs(p.y)) * 0.5);

    // ---- Themenrahmen darüber: Lichter pulsen zum Bass, Lauflicht nach x-Position, Höhen funkeln, Drop-Welle
    if (uFrameOK > 0.5) {
        vec4 fr = frameAt(uv);
        float lights = lightsOf(fr.rgb);
        float bloom = 0.0;
        for (int k = 0; k < 4; k++) {
            float a = float(k) * PI * 0.5 + 0.4;
            vec4 nb = frameAt(uv + vec2(cos(a) / aspect, sin(a)) * 0.022);
            bloom += lightsOf(nb.rgb) * nb.a;
        }
        bloom *= 0.25;
        float z = clamp(floor((p.x - ax0) / reelW + 0.5), 0.0, n);
        float run = lit(z, nz) * uLive;
        float lum = max(fr.r, max(fr.g, fr.b));
        vec3 glowCol = fr.rgb / max(lum, 0.2);
        if (uFlash > 0.0) {                                                    // Drop: Farbwelle läuft über den Rahmen
            float wave = ex(-sq((uv.x - (1.0 - uFlash) * 1.6 + 0.3) * 6.0));
            glowCol = mix(glowCol, hueShift(glowCol, 2.0 + uv.x * 3.0), wave * uFlash);
        }
        float breathe = 0.5 + 0.5 * sin(t * 1.2 + uv.x * 4.0 + uv.y * 3.0);
        float twinkle = step(0.7 - 0.5 * uHighS, hash12(vec2(floor(uv.x * 80.0), floor(uv.y * 45.0) + floor(t * 12.0))));
        float drive = 0.15 * breathe + 1.0 * uBassS + 0.4 * uBeatPulse + 1.4 * run + 0.4 * uHighS * twinkle
                    + (0.1 + 0.2 * uStake) * 0.3 + 1.2 * big * (0.5 + 0.5 * sin(t * 6.0 - uv.x * 12.0)) + 0.8 * uFlash;
        vec3 fc = fr.rgb * (0.55 + 0.25 * uLive);                              // Grundhelligkeit, Stille dimmt
        fc = mix(fc, fc * 0.4, lights * uLive * (1.0 - clamp(drive, 0.0, 1.0)));
        fc += glowCol * lights * drive * (0.35 + 0.65 * uLive);
        fc += glowCol * bloom * drive * 0.5 * (0.3 + 0.7 * uLive);
        fc += winCol * winK * winPulse * (0.1 + 0.15 * big) * lights;
        fc = mix(fc, fc * vec3(0.8, 0.9, 1.1), (1.0 - uLive) * 0.3);
        if (jackpot > 0.5) fc += fr.rgb * 0.6 * ex(-resultT * 0.4) * (0.6 + 0.4 * sin(t * 10.0));
        // dunkle Bänder oben und unten, damit Titel und Guthaben über dem Rahmen lesbar bleiben
        fc *= 1.0 - 0.6 * (smoothstep(0.90, 0.955, uv.y) + smoothstep(0.075, 0.015, uv.y));
        col = mix(col, fc, fr.a);
        col += glowCol * bloom * drive * 0.35 * (1.0 - fr.a);                  // Schein der Lampen fällt auf die Walzen
    }
    // Einsatzwechsel: Lichtring
    float stakeFx = ex(-uStakeT * 2.0) * step(0.0, uStakeT);
    col += uColA * stakeFx * ex(-sq((length(p) - uStakeT * 1.2) * 8.0));
    // Glas: weicher Reflex und etwas Staub (nur ohne Rahmen über das ganze Bild)
    col += vec3(0.045) * smoothstep(0.0, 0.8, p.y * 0.8 - p.x * 0.25 + 0.3) * (1.0 - smoothstep(0.42, 0.49, abs(p.y))) * (onReel ? 1.0 : 0.3);
    col += vec3(0.02) * noise(p * 40.0 + 3.0);
    // in Bewegung driften die Farben kaum merklich
    col = mix(col, hueShift(col, 0.25 * sin(t * 0.6)), moving * 0.5);
    col *= 1.0 + 0.04 * uBeat * (1.0 - uSilent);
    // Schwarzweiß wie 1955 (Zukunft, Jackpot): Film mit Korn und Kratzern
    if (uSepia > 0.001) {
        float g = dot(col, vec3(0.3, 0.59, 0.11));
        vec3 film = vec3(pow(max(g, 0.0), 1.15)) * vec3(1.0, 0.96, 0.9);
        film *= 0.9 + 0.2 * (noise(vUv * 400.0 + t * 30.0) - 0.5);
        film += step(0.995, hash12(vec2(floor(vUv.x * 300.0 + floor(t * 7.0) * 13.0), 1.0))) * 0.3;
        film *= 0.85 + 0.15 * hash12(vec2(floor(t * 24.0), 3.0));
        col = mix(col, film, uSepia);
    }
    col *= 1.0 - uFade;                                     // Automatenwechsel: Abblenden
    col *= 1.0 - 0.3 * sq(length(vUv - 0.5) * 1.25);
    col = col / (1.0 + col * 0.12);
    fragColor = vec4(col, 1.0);
}
