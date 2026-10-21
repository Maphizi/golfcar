#version 140
// Der Herzbaum: Baum-Foto (uSceneTex) mit leuchtenden Saftadern. Der Shader erkennt die Adern im Foto (bernstein,
// türkis) und lässt sie glühen: Herzschläge (uPulseA/B = Alter der Impulse) laufen als Lichtwellen von den Wurzeln
// nach oben, uWaveT schiebt ein Flackermuster durch die Adern, uEnergy ist das Grundglühen, uHue färbt sie um.
// Jahreszeit uSeason 0..4 (Frühling, Sommer, Herbst, Winter, fließend): Laubfarbe, fallende Teile aus uSheetTex
// (8x3 à 192: Reihe 0 Frühling, 1 Herbst, 2 Winter), Schnee. Sturm uStormT, Wurzeln uRootsT, großer Herzschlag
// uBigBeat, Drop uFlash, Nahaufnahme uZoom.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uSheetTex;
uniform vec2 uSceneSize, uSheetSize, uTrunk;
uniform float uSeed, uSeason, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uWaveT, uFlash, uHue, uStormT, uStormSeed;
uniform float uRootsT, uBigBeat, uZoom;
uniform vec3 uPulseA, uPulseB;
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
vec4 cell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uSheetTex, lo + (d * 0.5 + 0.5) * 192.0, uSheetSize, lo, lo + 191.0);
}
float pulseAge(int i) { return i < 3 ? uPulseA[i] : uPulseB[i - 3]; }
// Gewicht der Jahreszeit s (0..3) bei fließendem uSeason (zyklisch)
float seasonW(float s) { float d = abs(mod(uSeason - s + 2.0, 4.0) - 2.0); return smoothstep(1.0, 0.0, d); }

// fallendes Teil: Zelle idx an Position p (Bild-uv), Größe sz, Winkel
vec3 particle(vec3 col, vec2 uv, float aspect, float idx, vec2 p, float sz, float ang, float bright) {
    vec2 d = rot(ang) * ((uv - p) * vec2(aspect, 1.0)) / sz;
    vec4 s = cell(idx, d);
    return mix(col, s.rgb * bright, s.a);
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float wSpring = seasonW(0.0), wSummer = seasonW(1.0), wAutumn = seasonW(2.0), wWinter = seasonW(3.0);
    // Kamera: Nahaufnahme an die Rinde, Stamm atmet mit dem Bass (weitet sich um die Stammmitte)
    vec2 uv = mix(vUv, uTrunk + (vUv - uTrunk) / 2.4, uZoom);
    float breathe = 0.012 * uBassS + 0.02 * (uBigBeat >= 0.0 ? exp(-uBigBeat * 3.0) : 0.0);
    uv = uTrunk + (uv - uTrunk) * (1.0 - breathe);
    uv += vec2(0.002 * sin(t * 0.17), 0.0015 * cos(t * 0.21));
    // Blätterdach wiegt sich mit den Mitten (oberer Bildteil, außerhalb der Stammmitte)
    vec2 suv = uv;
    float canopy = smoothstep(0.45, 0.8, uv.y) * smoothstep(0.08, 0.2, abs(uv.x - uTrunk.x) + (uv.y - 0.5) * 0.6);
    suv.x += canopy * (0.004 * sin(uv.y * 16.0 + t * 1.2) + 0.006 * sin(uv.x * 8.0 - t * 0.9)) * (0.3 + 1.5 * uMidS);
    suv.y += canopy * 0.003 * sin(uv.x * 12.0 + t * 1.1) * (0.5 + uMidS);
    vec3 plate = scene(suv);
    vec3 col = plate;
    // ---- Adern erkennen: Bernstein (r > g > b, hell) und Türkis (g, b > r)
    float lum = max(plate.r, max(plate.g, plate.b));
    float amber = clamp((plate.r - plate.b * 1.6 - 0.12) * 4.0, 0.0, 1.0) * smoothstep(0.3, 0.6, lum) * smoothstep(0.1, 0.3, plate.g);
    float teal = clamp((min(plate.g, plate.b) - plate.r * 1.4 - 0.05) * 5.0, 0.0, 1.0) * smoothstep(0.3, 0.55, lum);
    float vein = max(amber, teal);
    vec3 veinCol = mix(vec3(1.0, 0.7, 0.25), vec3(0.2, 1.0, 0.85), teal / max(vein, 1e-3) * step(amber, teal));
    // Jahreszeitenfarbe der Adern: Frühling gold-grün, Herbst orange-rot, Winter eisblau; Drop färbt um
    veinCol = hueShift(veinCol, uHue - 0.5 * wAutumn + 0.3 * wSpring);
    veinCol = mix(veinCol, vec3(0.45, 0.7, 1.0), wWinter);                 // Winter: Eisblau
    // Herzschläge: Lichtwellen von unten nach oben durch den Stamm (Alter 0..3 s), je nach Höhe verzögert
    float beatGlow = 0.0;
    for (int i = 0; i < 6; i++) {
        float age = pulseAge(i);
        if (age > 3.0) continue;
        float front = age * 0.55 - 0.05;                                   // Höhe der Welle (uv.y)
        float dy = uv.y - front;
        beatGlow += exp(-dy * dy * 60.0) * exp(-age * 0.9) * (1.0 - 0.5 * smoothstep(0.0, 0.5, abs(uv.x - uTrunk.x) - 0.1 * uv.y));
    }
    // Flackermuster, das durch die Adern wandert (Richtung wechselt beim Drop)
    float flicker = 0.5 + 0.5 * sin(uv.y * 40.0 + uv.x * 18.0 - uWaveT * 6.0 + fbm(uv * 8.0) * 6.0);
    float base = 0.1 + 0.4 * uEnergy + 0.2 * uBassS;
    float rest = (1.0 - uLive) * (0.25 + 0.2 * sin(t * 1.3));            // Ruhepuls in der Stille
    float glow = base * uLive + rest + 0.45 * flicker * (0.3 + uEnergy) * uLive + 1.3 * beatGlow + 0.3 * uBeatPulse * uLive;
    if (uRootsT >= 0.0) glow += 1.5 * exp(-uRootsT * 0.3) * smoothstep(0.45, 0.2, uv.y);
    if (uBigBeat >= 0.0) glow += 1.5 * exp(-uBigBeat * 2.0);
    glow += 1.2 * uFlash * smoothstep(0.5, 0.1, uv.y);
    glow *= 1.0 - 0.6 * wWinter;
    // Adern im Foto selbst umfärben: Winter eisblau, Herbst rötlich, Drop-Farbe
    col = mix(col, vec3(lum) * vec3(0.5, 0.75, 1.1), vein * wWinter);
    col = mix(col, hueShift(col, -0.5), vein * wAutumn);
    col = mix(col, hueShift(col, uHue), vein * min(1.0, abs(uHue)));
    col += veinCol * vein * glow;
    // Umgebungslicht der Adern auf Rinde und Moos (weicher Schein)
    col += veinCol * vein * 0.0 + plate * vein * glow * 0.2;
    // ---- Laubfarbe je Jahreszeit (grüne Stellen im Foto)
    float leaf = clamp((plate.g - max(plate.r, plate.b) * 0.95) * 8.0, 0.0, 1.0) * smoothstep(0.06, 0.2, lum);
    vec3 leafCol = plate;
    leafCol = mix(leafCol, hueShift(plate, 0.35) * vec3(1.15, 1.1, 0.95) + vec3(0.1, 0.03, 0.06) * smoothstep(0.3, 0.6, lum), wSpring);
    leafCol = mix(leafCol, hueShift(plate, -1.7) * vec3(1.5, 0.95, 0.5) + vec3(0.06, 0.02, 0.0), wAutumn);
    vec3 frost = vec3(0.75, 0.82, 0.95) * (0.5 + 0.5 * noise(uv * 300.0)) * smoothstep(0.25, 0.6, lum);
    leafCol = mix(leafCol, mix(plate * vec3(0.5, 0.6, 0.8), frost, 0.7), wWinter);
    col = mix(col, leafCol, leaf);
    // Winter: Schnee auf Wurzeln und Moos, kühle Luft
    float snow = wWinter * smoothstep(0.3, 0.7, lum) * smoothstep(0.45, 0.2, uv.y) * (0.4 + 0.6 * noise(uv * 150.0));
    col = mix(col, vec3(0.85, 0.9, 1.0), snow * 0.6);
    col = mix(col, col * vec3(0.85, 0.92, 1.1), wWinter * 0.5);
    // ---- Fallende Teile: ruhiger Dauerfall je Jahreszeit, Sturm = viel mehr und wirbelnd
    {
        float storm = uStormT >= 0.0 ? (smoothstep(0.0, 0.8, uStormT) * smoothstep(7.0, 4.0, uStormT)) : 0.0;
        int n = 14 + int(storm * 34.0);
        float sw = wSpring, aw = wAutumn, ww = wWinter;
        for (int i = 0; i < 48; i++) {
            if (i >= n) break;
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0 + uStormSeed * storm)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
            // Jahreszeit des Teils: nach Gewichten würfeln (Sommer: nur wenige grüne Blätter)
            float r = h3;
            float row;
            if (r < sw) row = 0.0; else if (r < sw + aw) row = 1.0; else if (r < sw + aw + ww) row = 2.0; else { if (h2 > 0.25) continue; row = 0.0; }
            float idx = row * 8.0 + floor(h1 * 8.0);
            if (row == 0.0 && sw < r) idx = 4.0;                               // Sommer: grünes Blatt
            float fall = 0.05 + 0.08 * h2 + storm * 0.12;
            float cycle = 1.0 / fall;
            float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
            float sway = (0.04 + 0.1 * storm) * sin(t * (1.0 + h2) + fi) + 0.03 * uMidS * sin(t * 3.0 + fi);
            vec2 p = vec2(0.1 + h1 * 0.8 + sway + storm * 0.25 * sin(t * 1.5 + fi), 0.98 - ph * 0.95);
            if (row == 2.0) p.x += 0.05 * sin(t * 0.8 + fi);
            float sz = (0.02 + 0.02 * h3) * (row == 2.0 ? 0.7 : 1.0);
            float ang = t * (0.5 + h2 * 2.0 + storm * 3.0) * (h1 > 0.5 ? 1.0 : -1.0);
            col = particle(col, uv, aspect, idx, p, sz, ang, 0.6 + 0.4 * uLive + 0.3 * uHighS);
        }
    }
    // ---- Wurzeln: Myzel breitet sich als Ring vom Stamm aus
    if (uRootsT >= 0.0) {
        float rr = length((uv - vec2(uTrunk.x, 0.18)) * vec2(aspect, 1.6));
        float ring = exp(-pow((rr - uRootsT * 0.12) * 12.0, 2.0)) * exp(-uRootsT * 0.25);
        col += vec3(0.3, 1.0, 0.7) * ring * (0.5 + 0.5 * noise(uv * 60.0 + t)) * smoothstep(0.5, 0.2, uv.y);
    }
    // ---- Drop / großer Herzschlag: Lichtblitz aus den Wurzeln, Ring
    float bb = uBigBeat >= 0.0 ? exp(-uBigBeat * 2.5) : 0.0;
    col += vec3(1.0, 0.85, 0.5) * (uFlash * 0.25 + bb * 0.35) * smoothstep(0.6, 0.1, uv.y) * (0.5 + 0.5 * fbm(uv * 5.0 + t));
    if (uBigBeat >= 0.0) {
        float rr = length((uv - uTrunk) * vec2(aspect, 1.0));
        col += vec3(1.0, 0.8, 0.4) * exp(-pow((rr - uBigBeat * 0.6) * 10.0, 2.0)) * exp(-uBigBeat * 1.5) * 0.6;
    }
    // ---- Pollen (Frühling/Sommer, Mitten), Glühwürmchen (Sommer stark, sonst wenige, Höhen), Tautropfen
    float pollenW = wSpring + wSummer;
    for (int i = 0; i < 20; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 21.0)), h2 = hash12(vec2(fi, 23.0));
        vec2 p = vec2(0.1 + h1 * 0.8 + 0.03 * sin(t * 0.5 + fi), mod(h2 + t * (0.01 + 0.03 * uMidS), 1.0) * 0.6 + 0.15);
        float g = smoothstep(0.004, 0.0, length((uv - p) * vec2(aspect, 1.0)));
        col += vec3(0.95, 0.9, 0.6) * g * (0.1 + 0.6 * uMidS) * pollenW;
    }
    int nf = 6 + int(wSummer * 14.0);
    for (int i = 0; i < 20; i++) {
        if (i >= nf) break;
        float fi = float(i);
        float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 33.0));
        vec2 c = vec2(h1 + 0.03 * sin(t * (0.3 + h2) + fi), 0.15 + h2 * 0.6 + 0.03 * sin(t * 0.7 + fi * 2.0));
        float g = smoothstep(0.006, 0.0, length((uv - c) * vec2(aspect, 1.0))) * (0.3 + 0.7 * pow(0.5 + 0.5 * sin(t * (2.0 + h1 * 3.0) + fi * 5.0), 2.0));
        col += vec3(1.0, 0.9, 0.5) * g * (0.3 + 1.0 * uHighS);
    }
    col += plate * smoothstep(0.5, 0.85, lum) * (1.0 - vein) * uHighS * 0.5 * (0.5 + 0.5 * sin(t * 9.0 + uv.x * 300.0 + uv.y * 200.0));
    // Nebel am Boden atmet mit dem Bass
    float mist = fbm(vec2(uv.x * 3.0 + t * 0.03, uv.y * 6.0) + uSeed) * smoothstep(0.0, 0.25, uv.y) * smoothstep(0.5, 0.25, uv.y);
    col = mix(col, col * 0.8 + vec3(0.5, 0.58, 0.7), smoothstep(0.4, 0.8, mist) * (0.15 + 0.1 * uBassS));
    // Stille: kälter und dunkler, der Baum schläft
    col *= 0.7 + 0.3 * uLive;
    col = mix(col, col * vec3(0.8, 0.9, 1.1), (1.0 - uLive) * 0.6);
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
