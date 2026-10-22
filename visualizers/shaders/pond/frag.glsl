#version 140
// Moorsee: Waldsee-Foto (uLakeTex) mit Strudel. Wasser wird in Bildkoordinaten verzerrt (Wellen, Strudel),
// Nebel treibt darüber, Mondspiegelung und Glühwürmchen atmen mit der Musik. Beats werfen Ringe (uRing0-5),
// Drops lassen das Wasser aufleuchten (uFlash). Geworfene Wesen (uThrow0/1) treiben, werden spiralig
// eingezogen und zu einem Band entlang der Spirale gestreckt, das zur Musik wogt. Blätterregen (uLeaf),
// Stein (uStone), Umkehrung (uEjectT: Fontäne, Wellen, Seegrund uBottomTex scheint durch). uZoom = Nahaufnahme.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uLakeTex, uBottomTex, uCreatureTex, uBeingsTex;
uniform vec2 uLakeSize, uCreatureSize, uBeingsSize, uVortex;
uniform vec4 uWater;                            // y unten, y oben, x links, x rechts (Bildanteile)
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uSwirlT, uSnakeT, uZoom, uFlash, uLeaf, uLeafSeed, uEjectT, uStone, uStoneSide;
uniform float uBeatPulse, uBeatStep, uQuakeT;            // Beat: Puls (klingt ab), Zähler 0..7, Sekunden seit dem letzten Beben
uniform sampler2D uShoreTex;                              // Uferleben 4x6 à 192 (Spalte = Stufe, Reihe = Art)
uniform vec2 uShoreSize;
uniform float uSporeT;                                    // Sekunden seit dem letzten Sporenstoß (Beat)
uniform vec4 uPlant0, uPlant1, uPlant2, uPlant3, uPlant4, uPlant5, uPlant6, uPlant7, uPlant8, uPlant9;       // x, Fußlinie, Größe, Art
uniform vec4 uPlantS0, uPlantS1, uPlantS2, uPlantS3, uPlantS4, uPlantS5, uPlantS6, uPlantS7, uPlantS8, uPlantS9; // Stufe 0..3 (-1 leer), Seite (+-1 Ufer, +-2 im Wasser), Seed, Alter s
uniform vec4 uRing0, uRing1, uRing2, uRing3, uRing4, uRing5;   // x, y, Alter, aktiv
uniform vec4 uThrow0, uThrow1;                  // Fortschritt, Zelle, Seite, Seed
uniform vec4 uThrowPar0, uThrowPar1;            // Spirale, rückwärts
uniform vec4 uLeafCells, uBubbleCells, uFountain0, uFountain1, uFountain2, uFountain3;
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
    px -= 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 a = clamp(i, lo, hi), b = clamp(i + 1.0, lo, hi);
    vec4 s00 = texture(tex, (vec2(a.x, a.y) + 0.5) / size), s10 = texture(tex, (vec2(b.x, a.y) + 0.5) / size);
    vec4 s01 = texture(tex, (vec2(a.x, b.y) + 0.5) / size), s11 = texture(tex, (vec2(b.x, b.y) + 0.5) / size);
    return mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
}
vec3 lake(vec2 uv) { return bilin(uLakeTex, clamp(uv, 0.0, 1.0) * uLakeSize, uLakeSize, vec2(0.0), uLakeSize - 1.0).rgb; }
vec3 bottomTex(vec2 uv) { return bilin(uBottomTex, clamp(uv, 0.0, 1.0) * uLakeSize, uLakeSize, vec2(0.0), uLakeSize - 1.0).rgb; }
// Wesen (Atlas 5x4 à 256), l 0..1
vec4 being(float cell, vec2 l) {
    if (l.x <= 0.0 || l.x >= 1.0 || l.y <= 0.0 || l.y >= 1.0) return vec4(0.0);
    float c = mod(cell, 5.0), r = floor(cell / 5.0);
    vec2 lo = vec2(c * 256.0, (3.0 - r) * 256.0);
    return bilin(uBeingsTex, lo + l * 256.0, uBeingsSize, lo, lo + 255.0);
}
// Wasserwesen (Atlas 6x4 à 160), p Bildkoordinaten (x in Höheneinheiten), c Mitte, sz halbe Größe, ang
vec4 creature(float idx, vec2 p, vec2 c, float sz, float ang) {
    vec2 d = rot(ang) * (p - c) / sz;
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 6.0), ri = floor(idx / 6.0);
    vec2 lo = vec2(ci * 160.0, (3.0 - ri) * 160.0);
    return bilin(uCreatureTex, lo + (d * 0.5 + 0.5) * 160.0, uCreatureSize, lo, lo + 159.0);
}
vec4 plantAt(int i) { return i == 0 ? uPlant0 : (i == 1 ? uPlant1 : (i == 2 ? uPlant2 : (i == 3 ? uPlant3 : (i == 4 ? uPlant4 : (i == 5 ? uPlant5 : (i == 6 ? uPlant6 : (i == 7 ? uPlant7 : (i == 8 ? uPlant8 : uPlant9)))))))); }
vec4 plantSAt(int i) { return i == 0 ? uPlantS0 : (i == 1 ? uPlantS1 : (i == 2 ? uPlantS2 : (i == 3 ? uPlantS3 : (i == 4 ? uPlantS4 : (i == 5 ? uPlantS5 : (i == 6 ? uPlantS6 : (i == 7 ? uPlantS7 : (i == 8 ? uPlantS8 : uPlantS9)))))))); }
vec4 shoreCell(float species, float stage, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    vec2 lo = vec2(stage * 192.0, (5.0 - species) * 192.0);
    return bilin(uShoreTex, lo + (d * 0.5 + 0.5) * 192.0, uShoreSize, lo, lo + 191.0);
}
// Pflanze i am Ufer: Stufe fließend (Keim -> jung -> voll -> verwelkt) als Überblendung mit Wachstumsskalierung,
// voll = pulst mit dem Bass und leuchtet, Beat = Sporen/Pollen steigen auf, Wind mit den Mitten
vec3 plant(vec3 col, vec2 uv, float aspect, float t, int i, float live) {
    vec4 p = plantAt(i), st = plantSAt(i);
    float stage = st.x;
    if (stage < 0.0) return col;
    float hw = p.z * aspect * 0.5;
    if (abs(uv.x - p.x) * aspect > hw * 1.2 || uv.y < p.y - hw * 0.3 || uv.y > p.y + hw * 2.3) return col;
    float fi = float(i), seed = st.z;
    float full = smoothstep(1.6, 2.0, stage) * (1.0 - smoothstep(2.0, 2.6, stage));
    float wither = smoothstep(2.0, 3.0, stage);
    // Größe wächst mit der Stufe (Keim klein), verwelkt sackt zusammen
    float grow = 0.45 + 0.55 * smoothstep(0.0, 2.0, stage);
    grow *= 1.0 - 0.25 * wither;
    grow *= 1.0 + 0.06 * uBassS * full * live + 0.02 * sin(t * 1.7 + fi);
    vec2 d = (uv - vec2(p.x, p.y)) * vec2(aspect, 1.0) / (hw * grow);
    d.x *= sign(st.y);                                                      // rechtes Ufer gespiegelt
    d.x += 0.04 * sin(d.y * 3.0 + t * 1.1 + fi) * (0.3 + 1.2 * uMidS * live) * smoothstep(-0.9, 0.5, d.y);   // Wind
    vec2 l = vec2(d.x, d.y - 1.0 + 0.04);
    float sa = clamp(stage, 0.0, 3.0);
    float ca = floor(min(sa, 2.999)), cb = min(ca + 1.0, 3.0);
    float mixv = smoothstep(0.25, 0.75, sa - ca);
    vec4 s = mix(shoreCell(p.w, ca, l), shoreCell(p.w, cb, l), mixv);
    if (s.a < 0.01) return col;
    // Leuchten: voll entwickelt glüht mit dem Bass, Drop-Flash, Leuchtpilze und Lotus stärker
    float glowy = (p.w == 2.0 || p.w == 3.0 || p.w == 5.0) ? 1.0 : 0.5;
    s.rgb *= 0.7 + 0.3 * live + full * (0.35 * uBassS + 0.3 * uBeatPulse + 0.6 * uFlash) * glowy;
    s.rgb = mix(s.rgb, s.rgb * vec3(0.7, 0.6, 0.5), wither * 0.5);
    col = mix(col, s.rgb, s.a);
    col += s.rgb * s.a * full * glowy * 0.25 * uBassS * live;
    // Sprießen: in den ersten Sekunden glüht der Fußpunkt und Funken steigen auf (sichtbar, wenn der Knüppel es ruft)
    float age = st.w;
    if (age < 3.0) {
        float born = 1.0 - age / 3.0;
        vec2 foot = (uv - vec2(p.x, p.y + hw * 0.3)) * vec2(aspect, 1.0) / hw;
        col += vec3(0.5, 1.0, 0.6) * exp(-dot(foot, foot) * 3.0) * born * born * 0.6;
        for (int k = 0; k < 8; k++) {
            float hk = hash12(vec2(float(k) + 7.0, seed * 70.0 + fi));
            float ak = age * (0.6 + 0.6 * hk);
            vec2 sp = vec2(p.x + (hk - 0.5) * p.z * 0.9 * sin(ak * 3.0 + float(k)), p.y + hw * (0.2 + 2.0 * fract(ak * 0.5 + hk)));
            float g = smoothstep(0.005, 0.0, length((uv - sp) * vec2(aspect, 1.0)));
            col += vec3(0.6, 1.0, 0.7) * g * born * 1.5;
        }
    }
    // Sporen / Pollen steigen von vollen Pflanzen auf (Beat), Libelle flattert über dem Schilf
    if (full > 0.0 && uSporeT < 2.5) {
        for (int k = 0; k < 6; k++) {
            float hk = hash12(vec2(float(k), seed * 90.0 + fi));
            float age = uSporeT + hk * 0.4;
            vec2 sp = vec2(p.x + (hk - 0.5) * p.z * 0.8, p.y + p.z * 0.7 + age * (0.03 + 0.05 * hk));
            sp.x += 0.01 * sin(age * 6.0 + fi + float(k));
            float g = smoothstep(0.004, 0.0, length((uv - sp) * vec2(aspect, 1.0))) * (1.0 - age / 2.9);
            col += (p.w == 2.0 ? vec3(0.4, 1.0, 0.9) : (p.w == 5.0 ? vec3(1.0, 0.4, 0.6) : vec3(1.0, 0.9, 0.5))) * g * full * 1.2;
        }
    }
    return col;
}
vec4 ringAt(int i) { return i == 0 ? uRing0 : (i == 1 ? uRing1 : (i == 2 ? uRing2 : (i == 3 ? uRing3 : (i == 4 ? uRing4 : uRing5)))); }
float fountainCell(int i) { int g = i / 4, k = i - g * 4; vec4 v = g == 0 ? uFountain0 : (g == 1 ? uFountain1 : (g == 2 ? uFountain2 : uFountain3)); return v[k]; }

// Wassermaske (weich): Bereich des Sees im Bild
const float FLAT = 0.5;   // Wasserfläche perspektivisch: Kreise um den Strudel sind Ellipsen (y gestaucht)
float waterMask(vec2 uv) {
    float m = smoothstep(uWater.x - 0.02, uWater.x + 0.05, uv.y) * smoothstep(uWater.y + 0.01, uWater.y - 0.03, uv.y);
    m *= smoothstep(uWater.z - 0.03, uWater.z + 0.08, uv.x) * smoothstep(uWater.w + 0.03, uWater.w - 0.08, uv.x);
    return m;
}
// Geworfenes Wesen: treibt, dann Spirale, dann Band. p in Höheneinheiten um den Strudel (x gestaucht), rv = Strudelradius
vec3 throwFx(vec3 col, vec2 q, float aspect, vec4 th, vec4 par, float live) {
    float P = th.x;
    if (P <= 0.0) return col;
    float side = th.z, seed = th.w, swirl = par.x;
    vec2 qs = q;                      // Bildkoordinaten (für Sprites)
    q = vec2(q.x, q.y / FLAT);        // Ebenenkoordinaten (Bahn liegt flach auf dem Wasser)
    float wob = 0.3 + 0.9 * uBassS * live + 0.4 * uMidS * live;
    // Start am Rand (Seite), Flug ins Wasser (0..0.06), Treiben (0.06..0.2), Einziehen (0.2..1)
    vec2 start = vec2(side * 0.3, 0.06);
    float fly = smoothstep(0.0, 0.06, P);
    float drift = smoothstep(0.06, 0.2, P);
    float pull = smoothstep(0.2, 1.0, P);
    float r0 = 0.3;
    float rad = mix(r0, 0.02, pow(pull, 1.3));
    float a0 = atan(start.y, start.x);
    float ang = a0 + swirl * (pull * pull * 10.0 + drift * 0.6 * sin(uSwirlT * 0.3 + seed)) + uSwirlT * 0.15 * pull * swirl;
    // Band: Winkelspanne wächst mit dem Einziehen (Spaghettisierung), Breite schrumpft
    float span = 0.35 + pull * pull * 7.0;
    float width = 0.09 * (1.0 - 0.75 * pull) * (1.0 + 0.1 * uBassS);
    vec2 c = vec2(cos(ang), sin(ang)) * rad;
    vec2 d = q - c;
    // vor dem Einziehen: Wesen fliegt von der Seite ein (Bogen) und treibt
    if (pull < 0.02) {
        vec2 pos = mix(vec2(side * 0.9, 0.5), start, fly);
        pos.y += (1.0 - fly) * 0.2 * sin(fly * PI);
        pos += vec2(0.015 * sin(uSwirlT * 0.7 + seed), 0.01 * sin(uSwirlT * 1.1)) * drift;
        float sz = 0.13 * (1.0 + 0.05 * uBassS);
        vec2 l = (qs - pos * vec2(1.0, FLAT)) / sz * 0.5 + 0.5;
        vec4 s = being(th.y, l);
        float dip = drift * 0.35;                                  // teilweise im Wasser: unten dunkler
        s.rgb *= 1.0 - dip * smoothstep(0.5, 0.0, l.y);
        return mix(col, s.rgb, s.a * fly);
    }
    // Spirale: Polarkoordinaten um den Strudel, Band liegt auf Radius rad(sa) entlang eines Winkelbogens
    float r = length(q), a = atan(q.y, q.x);
    float rel = (a - ang) * swirl;                                 // Winkel hinter dem Kopf (positiv = Schwanzrichtung)
    rel = mod(rel + PI, 2.0 * PI) - PI;
    float turns = floor((span - rel) / (2.0 * PI) + 0.5);          // welche Windung
    float sa = rel + turns * 2.0 * PI;                             // Bogenposition 0 (Kopf) .. span (Schwanz)
    if (sa < -0.2 || sa > span + 0.2) return col;
    float u = clamp(sa / span, 0.0, 1.0);
    float rb = rad + u * (r0 * 0.9 - rad) * (1.0 - pull * 0.5) + 0.03 * u;   // Schwanz weiter außen
    rb += width * 0.8 * sin(sa * 3.0 - uSnakeT * 1.5 + seed) * wob * pull;  // Schlangenwellen
    float v = (r - rb) / width;
    if (abs(v) > 1.3) return col;
    vec2 l = vec2(1.0 - u, v * 0.5 + 0.5);
    vec4 s = being(th.y, l);
    float nz = sqrt(max(0.0, 1.0 - v * v));
    // Farben laufen in Fäden auseinander: Hue wandert mit der Bogenposition, Bild wird zum Band
    s.rgb = hueShift(s.rgb, u * 2.0 * pull + uSnakeT * 0.2 * pull);
    s.rgb *= 0.5 + 0.6 * nz;
    s.rgb = mix(s.rgb, s.rgb * vec3(0.5, 0.8, 1.0), 0.4 * pull);     // unter Wasser kühler
    float fade = smoothstep(0.0, 0.04, rad - 0.02) * (1.0 - smoothstep(0.85, 1.0, P));
    col = mix(col, s.rgb, s.a * smoothstep(1.3, 0.9, abs(v)) * fade);
    // Luftblasen steigen vom Band auf
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float h = hash12(vec2(fi, seed));
        float life = 2.0 + h * 2.0;
        float age = mod(uSwirlT * 0.8 + h * life, life);
        vec2 bp = c * vec2(1.0, FLAT) + vec2((h - 0.5) * 0.1, age * 0.08);
        float b = smoothstep(0.006, 0.0, length(qs - bp) - 0.003 * age) * (1.0 - age / life) * pull;
        col += vec3(0.6, 0.8, 0.9) * b * 0.8;
    }
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = 1.0 - uSilent;
    // Kamera: Nahaufnahme zieht in den Strudel
    vec2 uv = mix(vUv, uVortex + (vUv - uVortex) / 1.6, uZoom);
    uv += vec2(0.003 * sin(t * 0.21), 0.002 * cos(t * 0.17));
    // Beben: jeder Beat rüttelt die Kamera kurz, das Wasser zittert (nur die Wasserfläche)
    float quake = uBeatPulse * uBeatPulse * live * smoothstep(1.6, 0.0, uQuakeT);   // nur bei der Druckwelle
    uv += vec2(0.0015 * sin(t * 60.0), 0.001 * cos(t * 47.0)) * quake;
    vec2 q = vec2((uv.x - uVortex.x) * aspect, uv.y - uVortex.y);   // um den Strudel, isotrop
    float wm = waterMask(uv);
    float r = length(q), a = atan(q.y, q.x);
    vec2 qp = vec2(q.x, q.y / FLAT);                                      // Ebenenkoordinaten
    float rp = length(qp), ap = atan(qp.y, qp.x);
    // ---- Wasser: Wellen, Strudelverzerrung, Beat-Ringe
    vec2 wuv = uv;
    float swirlStrength = (0.8 + 2.2 * uBassS * live + 0.4 * uBeatPulse * live) * (1.0 + 0.6 * uZoom);
    float reach = 6.0 - 2.5 * uBassS * live;                                 // mit Bass greift der Strudel weiter
    float sw = exp(-rp * reach) * swirlStrength;
    float ejectT = uEjectT;
    float surge = 0.0;
    if (ejectT >= 0.0) surge = ejectT < 1.5 ? ejectT / 1.5 : exp(-(ejectT - 1.5) * 0.6);
    vec2 wq = rot(sw * 2.0) * qp;
    vec2 disp = (wq - qp) * vec2(1.0, FLAT) * 0.5;
    disp += vec2(noise(uv * 40.0 + vec2(t * 0.6, t * 0.3)) - 0.5, noise(uv * 40.0 + vec2(-t * 0.4, t * 0.5)) - 0.5) * 0.004 * (1.0 + 2.0 * uBassS * live);
    disp -= qp / max(rp, 0.01) * vec2(1.0, FLAT) * exp(-rp * 6.0) * 0.02 * (0.5 + 1.5 * uBassS + 0.4 * uBeatPulse);   // Sog zur Mitte
    // Beben: Druckwelle vom Strudel über den ganzen See (verschiebt das Wasserbild), dazu Zittern
    if (uQuakeT < 1.6) {
        float qr = uQuakeT * 0.9;
        float shock = exp(-pow((rp - qr) * 14.0, 2.0)) * (1.0 - uQuakeT / 1.6) * live;
        disp += qp / max(rp, 0.01) * vec2(1.0, FLAT) * shock * 0.012;
        disp += vec2(0.0, 0.002) * quake * sin(uv.x * 60.0 + t * 40.0) * smoothstep(0.0, 0.3, rp);
    }
    for (int i = 0; i < 6; i++) {
        vec4 rg = ringAt(i);
        if (rg.w < 0.5 || rg.z > 4.0) continue;
        vec2 rc = vec2((uv.x - rg.x) * aspect, uv.y - rg.y);
        float rr = length(rc * vec2(1.0, 2.2));
        float wave = exp(-pow((rr - rg.z * 0.18) * 30.0, 2.0)) * exp(-rg.z * 0.8);
        disp += normalize(rc + 1e-5) * wave * 0.004;
    }
    disp += vec2(0.0, 0.03) * surge * sin(uv.x * 30.0 + t * 8.0) * smoothstep(0.0, 0.25, r);
    disp.x /= aspect;
    wuv += disp * wm;
    vec3 col = lake(wuv);
    // Seegrund bei der Umkehrung: scheint um den Strudel durch
    if (ejectT >= 1.5) {
        float reveal = exp(-(ejectT - 1.5) * 0.22) * smoothstep(0.0, 1.0, (ejectT - 1.5) / 0.4);
        float hole = smoothstep(0.5 * reveal + 0.05, 0.1 * reveal, rp) * min(1.0, reveal * 1.6) * wm;
        col = mix(col, bottomTex(uv), hole);
    }
    // Strudel: dunkle Mitte, Schaumspiralen, Glühen mit dem Bass
    // Schaumspiralen: drei Arme, springen auf jeden Beat ein Stück weiter (uBeatStep) und drehen mit uSwirlT
    float armJump = uBeatStep * 0.785 + uBeatPulse * 0.4;
    float foam = pow(0.5 + 0.5 * sin(ap * 3.0 + log(rp + 0.02) * 9.0 - uSwirlT * 3.0 - armJump), 10.0 - 6.0 * uBeatPulse) * exp(-rp * (5.0 - 2.0 * uBassS * live));
    foam *= 1.0 + 0.4 * uBeatPulse;
    col = mix(col, col * 0.25, smoothstep(0.08, 0.0, rp) * wm);
    col += vec3(0.8, 0.9, 0.95) * foam * wm * (0.4 + 0.5 * uBassS);
    col += vec3(0.3, 0.9, 0.7) * exp(-rp * (14.0 - 5.0 * uBassS * live)) * wm * (0.2 + 0.8 * uBassS * live + 0.2 * uBeatPulse * live) * (1.0 + uZoom);
    col += hueShift(vec3(0.4, 0.9, 1.0), uBeatStep * 0.5) * exp(-rp * 8.0) * wm * uBeatPulse * 0.15 * live;   // Beat-Blitz im Trichter
    // Druckwelle als heller Ring über das ganze Wasser
    if (uQuakeT < 1.6) {
        float qr = uQuakeT * 0.9;
        col += vec3(0.6, 0.85, 1.0) * exp(-pow((rp - qr) * 18.0, 2.0)) * (1.0 - uQuakeT / 1.6) * wm * 0.22 * live;
    }
    // Beat-Ringe als helle Linien
    for (int i = 0; i < 6; i++) {
        vec4 rg = ringAt(i);
        if (rg.w < 0.5 || rg.z > 4.0) continue;
        vec2 rc = vec2((uv.x - rg.x) * aspect, uv.y - rg.y);
        float rr = length(rc * vec2(1.0, 2.2));
        col += vec3(0.7, 0.85, 1.0) * exp(-pow((rr - rg.z * 0.18) * 40.0, 2.0)) * exp(-rg.z * 0.9) * 0.2 * wm;
    }
    // Drop: Wasser leuchtet von innen
    col += vec3(0.3, 0.9, 0.6) * uFlash * wm * (0.3 + 0.4 * noise(uv * 12.0 + t));
    // ---- Blätterregen: Blätter fallen, landen, drehen sich im Strudel nach innen
    if (uLeaf > 0.0) {
        float k = uLeaf;
        for (int i = 0; i < 22; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, uLeafSeed * 50.0)), h2 = hash12(vec2(fi + 30.0, uLeafSeed * 50.0)), h3 = hash12(vec2(fi, 77.0));
            float tt = k * 45.0 - h1 * 8.0;                                  // Sekunden seit dem Fall dieses Blatts
            if (tt < 0.0) continue;
            vec2 pos;
            float ang;
            float fallT = 3.0;
            float rad0 = 0.3 + 0.12 * h3, an0 = h2 * 6.28;
            vec2 land = vec2(cos(an0), sin(an0) * FLAT) * rad0;              // Landepunkt = Start der Spirale
            if (tt < fallT) {                                                 // Fall mit Schaukeln
                float ff = tt / fallT;
                pos = vec2(land.x + 0.08 * sin(tt * 2.0 + fi) * (1.0 - ff), mix(0.7, land.y, ff));
                ang = sin(tt * 2.0 + fi) * 0.5;
            } else {                                                          // auf dem Wasser: Spirale nach innen
                float s = (tt - fallT) / 30.0;
                if (s >= 1.0) continue;
                float rad = mix(rad0, 0.02, smoothstep(0.0, 1.0, s));
                float an = an0 + s * s * 14.0 + (tt - fallT) * 0.12;
                pos = vec2(cos(an), sin(an) * FLAT) * rad;
                ang = an + PI * 0.5 + 0.2 * sin(uSwirlT + fi);
            }
            float sz = 0.035 + 0.02 * h3;
            vec4 s = creature(uLeafCells[i % 4], q, pos, sz, ang);
            s.rgb *= 0.9 + 0.4 * uBassS;
            float fadeEnd = smoothstep(0.0, 0.03, length(pos * vec2(1.0, 1.0 / FLAT)) - 0.02);
            col = mix(col, s.rgb, s.a * fadeEnd);
        }
    }
    // ---- Uferleben: Pflanzen wachsen und vergehen zur Musik
    for (int i = 0; i < 10; i++) col = plant(col, uv, aspect, t, i, live);
    // ---- Geworfene Wesen
    col = throwFx(col, q, aspect, uThrow0, uThrowPar0, live);
    col = throwFx(col, q, aspect, uThrow1, uThrowPar1, live);
    // ---- Stein hüpft über das Wasser
    if (uStone >= 0.0) {
        float hop = uStone / 0.6;
        float k = floor(hop), f = fract(hop);
        float x = uStoneSide * (0.4 - k * 0.11 - f * 0.11);
        float y = 0.06 - k * 0.015 + 0.08 * sin(f * PI) * (1.0 - k * 0.2);
        vec4 s = creature(uBubbleCells.w, q, vec2(x, y), 0.045, uStone * 4.0);
        s.rgb = s.rgb * 1.2 + vec3(0.12, 0.14, 0.18);                      // Mondlicht auf dem Stein
        col = mix(col, s.rgb, s.a * (1.0 - smoothstep(3.5, 4.0, hop)));
        // Spritzer beim Aufsetzen: kurzer heller Fächer an der letzten Landestelle
        if (k > 0.0 && f < 0.35) {
            vec2 lp = vec2(uStoneSide * (0.4 - k * 0.11), 0.06 - k * 0.015);
            vec2 dl = q - lp;
            float spray = smoothstep(0.05, 0.0, length(dl - vec2(0.0, f * 0.06))) * smoothstep(0.0, 0.01, dl.y)
                        * (1.0 - f / 0.35) * noise(dl * 120.0 + f * 20.0);
            col += vec3(0.8, 0.9, 1.0) * spray * 2.0;
        }
    }
    // ---- Umkehrung: Fontäne aus Wesen, Wellen, Nebel reißt auf
    if (ejectT >= 1.5) {
        float bt = ejectT - 1.5;
        for (int i = 0; i < 16; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 9.0));
            float age = bt - h1 * 0.8;
            if (age < 0.0 || age > 4.5) continue;
            float vx = (h2 - 0.5) * 0.6, vy = 0.5 + 0.5 * h3;
            vec2 pos = vec2(vx * age, vy * age - 0.25 * age * age);
            float ang = age * (h1 - 0.5) * 6.0;
            vec4 s = creature(fountainCell(i), q, pos, 0.05 + 0.04 * h3, ang);
            col = mix(col, s.rgb, s.a * (1.0 - smoothstep(3.5, 4.5, age)));
        }
        col += vec3(0.7, 0.9, 1.0) * exp(-bt * 3.0) * exp(-r * 2.0) * 1.5;      // Blitz beim Ausbruch
        float column = smoothstep(0.08, 0.0, abs(q.x)) * smoothstep(0.0, 0.1, q.y) * smoothstep(0.9, 0.3, q.y) * exp(-bt * 0.8);
        col += vec3(0.6, 0.8, 0.9) * column * (0.6 + 0.4 * noise(vec2(q.x * 30.0, q.y * 10.0 - bt * 6.0)));
    }
    // ---- Nebel über dem Wasser (reißt bei der Umkehrung auf), atmet mit dem Bass
    float mistBand = smoothstep(uWater.y - 0.2, uWater.y + 0.02, uv.y) * smoothstep(uWater.y + 0.14, uWater.y + 0.02, uv.y);
    float mist = fbm(vec2(uv.x * 4.0 + t * 0.03, uv.y * 8.0 - t * 0.01) + uSeed) * mistBand;
    mist *= 1.0 - 0.8 * surge;
    col = mix(col, col * 0.7 + vec3(0.55, 0.62, 0.75), smoothstep(0.3, 0.75, mist) * (0.35 + 0.15 * uBassS * live));
    // ---- Mondspiegelung pulst, Glühwürmchen und Tautropfen funkeln mit den Höhen
    col += vec3(0.8, 0.85, 1.0) * uBassS * live * 0.12 * wm * smoothstep(0.35, 0.0, abs(uv.x - 0.6)) * smoothstep(0.25, 0.0, abs(uv.y - 0.28));
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 41.0)), h2 = hash12(vec2(fi, 43.0));
        vec2 c = vec2(h1 + 0.03 * sin(t * (0.3 + h2) + fi), 0.1 + h2 * 0.5 + 0.03 * sin(t * 0.7 + fi * 2.0));
        float g = smoothstep(0.006, 0.0, length((uv - c) * vec2(aspect, 1.0))) * (0.3 + 0.7 * pow(0.5 + 0.5 * sin(t * (2.0 + h1 * 3.0) + fi * 5.0), 2.0));
        col += vec3(1.0, 0.9, 0.5) * g * (0.5 + 0.8 * uHighS * live);
    }
    // Abschluss
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
