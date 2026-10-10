#version 140
// Space-Slotmaschine: Nahaufnahme von drei Walzen, die das ganze Bild füllen. Gedruckte Symbole auf
// gewölbten Trommeln mit Papierkorn, Licht von oben, dunkle Trennstege und Blende, Glasreflex.
// Die Maschine selbst steht still; beim Drehen verschwimmt das Bild wie im Traum (uDream) und wird
// beim Stehenbleiben wieder scharf. Symbole aus dem Sprite-Atlas uSpriteTex, Zustand vom Controller.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSpriteTex;
uniform vec2 uAtlasSize;
uniform float uTheme, uState, uStateT, uWin, uWinMask, uDream, uFade, uStripRow;
uniform vec3 uColA, uColB, uReel, uSpeed;

const float STRIP = 32.0;
const float CELL = 0.30;           // Symbolhöhe auf der abgerollten Trommel (Höheneinheiten)
const float PI = 3.14159265;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float stripSymbol(float reel, float k) {
    float kk = mod(k, STRIP);
    return floor(texture(uSpriteTex, vec2((kk + 0.5) / uAtlasSize.x, (uStripRow + reel + 0.5) / uAtlasSize.y)).r * 255.0 + 0.5);
}
// Symbol idx, Position l in 0..1: Pixelgrafik mit weich gezeichneten Kanten (wirkt gedruckt, nicht klotzig)
vec4 sprite(float idx, vec2 l, float soft) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return vec4(0.0);
    vec2 px = vec2(idx * 16.0 + l.x * 16.0, uTheme * 16.0 + l.y * 16.0) - 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 w = smoothstep(0.5 - soft, 0.5 + soft, f);          // weiche Kante zwischen Texeln
    vec2 base = vec2(idx * 16.0, uTheme * 16.0);
    vec2 lo = base, hi = base + 15.0;
    vec2 a = clamp(i, lo, hi), b = clamp(i + 1.0, lo, hi);
    vec4 s00 = texture(uSpriteTex, (vec2(a.x, a.y) + 0.5) / uAtlasSize);
    vec4 s10 = texture(uSpriteTex, (vec2(b.x, a.y) + 0.5) / uAtlasSize);
    vec4 s01 = texture(uSpriteTex, (vec2(a.x, b.y) + 0.5) / uAtlasSize);
    vec4 s11 = texture(uSpriteTex, (vec2(b.x, b.y) + 0.5) / uAtlasSize);
    return mix(mix(s00, s10, w.x), mix(s01, s11, w.x), w.y);
}
// Ein Punkt auf der Trommel: q.x -0.5..0.5 über die Walzenbreite, q.y -0.5..0.5 Bildhöhe
vec3 drumPixel(float reel, vec2 q, float pos, float soft) {
    float yn = clamp(q.y / 0.5, -0.999, 0.999);
    float ang = asin(yn);                                   // Winkel auf dem Zylinder
    float yc = ang / (PI * 0.5) * 0.5 * 1.45;               // abgerollte Position
    float k = floor(pos + yc / CELL + 0.5);
    float ly = (yc - (k - pos) * CELL) / CELL + 0.5;
    float lx = q.x + 0.5;
    // Papier mit Korn, Druckfarbe, feine Trennlinie zwischen den Feldern
    float grain = noise(vec2(q.x * 420.0, yc * 420.0)) * 0.05 + noise(vec2(q.x * 90.0, yc * 90.0)) * 0.03;
    vec3 paper = vec3(0.90, 0.89, 0.85) * (0.96 + grain);
    paper = mix(paper, uColB * 0.9 + 0.1, 0.06);
    float idx = stripSymbol(reel, k);
    vec2 l = (vec2(lx, ly) - vec2(0.17, 0.12)) / vec2(0.66, 0.76);
    vec4 s = sprite(idx, l, soft);
    vec3 ink = s.rgb * 0.92 * (0.92 + grain);
    vec3 col = mix(paper, ink, s.a * 0.96);
    float sep = smoothstep(0.03, 0.0, min(ly, 1.0 - ly));
    col *= 1.0 - 0.18 * sep;
    // Beleuchtung: Licht von schräg oben, Glanzband, Zylinderabschattung
    float diffuse = 0.22 + 0.78 * pow(max(cos(ang), 0.0), 0.7);
    float spec = 0.22 * pow(max(cos(ang - 0.32), 0.0), 30.0);
    col = col * diffuse + spec;
    // Walzenenden dunkler (Zylinder läuft in den Steg)
    col *= 1.0 - 0.45 * smoothstep(0.36, 0.5, abs(q.x));
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = vUv;
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);
    float t = iTime;
    float live = 1.0 - uSilent;
    bool result = uState > 1.5 && uState < 2.5;
    float winPulse = result && uWin > 0.5 ? 0.5 + 0.5 * sin(t * 4.0) : 0.0;
    float dream = clamp(uDream, 0.0, 1.0);

    float reelW = aspect * 0.30;
    float x0 = -aspect * 0.45;
    float ri = floor((p.x - x0) / reelW);
    vec3 col = vec3(0.025, 0.025, 0.03) + uColB * 0.03;       // Blende
    if (ri >= 0.0 && ri <= 2.0 && abs(p.y) < 0.49) {
        float cx = x0 + (ri + 0.5) * reelW;
        vec2 q = vec2((p.x - cx) / reelW, p.y);
        float pos = ri < 0.5 ? uReel.x : (ri < 1.5 ? uReel.y : uReel.z);
        float sp = ri < 0.5 ? uSpeed.x : (ri < 1.5 ? uSpeed.y : uSpeed.z);
        // Traum: weiche Unschärfe in der Fläche plus Bewegungsunschärfe entlang der Walze
        float blurR = 0.016 * dream * (1.0 + 0.3 * sin(t * 0.7));
        float mblur = sp * 0.018;
        float soft = 0.08 + 0.3 * dream;
        vec3 acc = vec3(0.0);
        if (dream < 0.02 && sp < 1.5) {
            acc = drumPixel(ri, q, pos, soft);
        } else {
            for (int i = 0; i < 6; i++) {
                float fi = float(i);
                float a = fi * 2.399 + t * 0.3;
                float rr = blurR * sqrt((fi + 0.5) / 6.0);
                vec2 off = vec2(cos(a) * rr / reelW, sin(a) * rr);
                float dp = (fi - 2.5) / 2.5 * mblur;
                acc += drumPixel(ri, q + off, pos + dp, soft);
            }
            acc /= 6.0;
            // Doppelbild, das langsam wandert
            vec2 ghost = vec2(0.0, 0.03 * sin(t * 0.5)) * dream;
            acc = mix(acc, drumPixel(ri, q + ghost, pos, soft), 0.25 * dream);
        }
        col = acc;
        // Gewinnlinie: nur bei Ergebnis, dezentes Leuchten auf dem Band der Mittelsymbole
        float band = smoothstep(CELL * 0.62, CELL * 0.5, abs(p.y));
        float maskBit = mod(floor(uWinMask / pow(2.0, ri)), 2.0);
        if (result && maskBit > 0.5) {
            vec3 glow = uWin > 2.5 ? vec3(1.0, 0.85, 0.4) : uColA;
            col += glow * band * winPulse * 0.18;
            float sweep = smoothstep(0.08, 0.0, abs(fract(uStateT * 0.35) * (aspect + 0.4) - aspect * 0.5 - 0.2 - p.x));
            col += glow * band * sweep * 0.25;
        }
        if (result && uWin < 0.5) col *= 0.82 + 0.18 * smoothstep(0.0, 1.2, uStateT);
        // Blendenschatten oben/unten
        col *= 1.0 - 0.55 * smoothstep(0.36, 0.49, abs(p.y));
    }
    // Trennstege zwischen und neben den Walzen
    for (int i = 0; i < 4; i++) {
        float ex = x0 + float(i) * reelW;
        float d = abs(p.x - ex);
        float bar = smoothstep(0.012, 0.009, d);
        float hi = smoothstep(0.004, 0.0, abs(d - 0.006)) * 0.35;
        col = mix(col, vec3(0.07, 0.07, 0.08) + vec3(hi), bar);
    }
    // Markierung der Gewinnlinie in den Stegen
    float mark = smoothstep(0.006, 0.0, abs(p.y)) * step(abs(p.x - (x0 + 1.5 * reelW)), aspect * 0.46) * (1.0 - step(0.012, abs(p.x - x0))) ;
    for (int i = 0; i < 4; i++) {
        float ex = x0 + float(i) * reelW;
        float m = smoothstep(0.012, 0.0, abs(p.x - ex)) * smoothstep(0.02, 0.0, abs(p.y));
        col += uColA * m * (0.6 + 0.3 * sin(t * 2.0) + winPulse);
    }
    // Glas: weicher Reflex und etwas Staub
    col += vec3(0.045) * smoothstep(0.0, 0.8, p.y * 0.8 - p.x * 0.25 + 0.3) * (1.0 - smoothstep(0.42, 0.49, abs(p.y)));
    col += vec3(0.02) * noise(p * 40.0 + 3.0);
    // Traum: Farben werden weicher und heller, leichte Farbdrift
    vec3 soft = col * vec3(1.03, 1.0, 1.06) + uColA * 0.04 + 0.03;
    col = mix(col, soft, dream * 0.8);
    // Beat: kaum merkliches Atmen des Lichts
    col *= 1.0 + 0.04 * uBeat * live;
    // Themenwechsel: Abblenden
    col *= 1.0 - uFade;
    col *= 1.0 - 0.3 * pow(length(uv - 0.5) * 1.25, 2.0);
    fragColor = vec4(col, 1.0);
}
