#version 140
// Der Kern: Serverkathedralen-Foto (uSceneTex), der Kern (uCenter, uRadius) pulst mit dem Bass, dreht mit uSpinT
// (Mitten = Tempo), Lichtbögen springen, Höhen = Funken und Datenregen. Jeder Beat = Welle (uRing0-5) aus dem Kern
// durch die Halle: Schränke leuchten auf, wenn die Welle sie erreicht, das Bodengitter hebt sich. Bass-Schläge =
// Druckwelle mit Bildverzerrung (uShock0-2). Lauflicht über die Lichtpunkte (uStep/uStepPhase/uPattern, Zonen
// links/rechts/oben/unten). Farbe uHue (Schritt alle 8 Beats, Sprung beim Drop), uHallT = komplementäre Halle nach
// dem Drop, uHue2 färbt die Datenströme. uVariant = (Variante, vorherige, Überblendung): 0 Plasma, 1 Datenwürfel,
// 2 Blitzkugel. Geworfene Objekte (uThrowN: Fortschritt, Zelle 6x4 à 192, Seite, Seed; uThrowParN: Spirale, rückwärts,
// Starthöhe) fliegen ein, kreisen spiralig nach innen und zerfallen in Pixelblöcke und einen Datenstrom.
// Drohnenschwarm uSwarmT, Überlast uEjectT, EMP uEmpT, Nahaufnahme uZoom. Stille: Kern atmet, Halle dunkel.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uObjTex;
uniform vec2 uSceneSize, uObjSize, uCenter;
uniform float uSeed, uRadius, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uStep, uStepPhase, uPattern;
uniform float uFlash, uHallT, uHue, uHue2, uSpinT, uZoom;
uniform float uSwarmT, uEjectT, uEmpT, uRing0, uRing1, uRing2, uRing3, uRing4, uRing5, uShock0, uShock1, uShock2;
uniform vec3 uVariant;
uniform vec4 uThrow0, uThrow1, uThrow2, uThrowPar0, uThrowPar1, uThrowPar2;
const float PI = 3.14159265;
const float RING_V = 0.42;      // Wellengeschwindigkeit (Kern-Einheiten pro Sekunde)
const float FLOOR_Y = 0.30;     // Oberkante des Hallenbodens (Anteil der Höhe)

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
vec3 scene(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0).rgb; }
vec4 objCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 6.0), ri = floor(idx / 6.0);
    vec2 lo = vec2(ci * 192.0, (3.0 - ri) * 192.0);
    return bilin(uObjTex, lo + (d * 0.5 + 0.5) * 192.0, uObjSize, lo, lo + 191.0);
}
float ringAt(int i) { return i == 0 ? uRing0 : (i == 1 ? uRing1 : (i == 2 ? uRing2 : (i == 3 ? uRing3 : (i == 4 ? uRing4 : uRing5)))); }
float shockAt(int i) { return i == 0 ? uShock0 : (i == 1 ? uShock1 : uShock2); }
vec4 throwAt(int i) { return i == 0 ? uThrow0 : (i == 1 ? uThrow1 : uThrow2); }
vec4 parAt(int i) { return i == 0 ? uThrowPar0 : (i == 1 ? uThrowPar1 : uThrowPar2); }
float variantW(float v) { return (abs(uVariant.x - v) < 0.5 ? uVariant.z : 0.0) + (abs(uVariant.y - v) < 0.5 ? 1.0 - uVariant.z : 0.0); }

// Lauflicht: ist Zone z (0 links, 1 rechts, 2 oben, 3 unten) im Schritt uStep bei Muster uPattern an?
float zoneOn(float z) {
    float s = uStep;
    if (uPattern < 0.5) return z == s ? 1.0 : 0.0;                                        // reihum
    if (uPattern < 1.5) return (mod(s, 2.0) == 0.0 ? (z == 0.0 ? 1.0 : 0.0) : (z == 1.0 ? 1.0 : 0.0));   // links / rechts
    if (uPattern < 2.5) return (mod(s, 2.0) == 0.0 ? (z == 2.0 ? 1.0 : 0.0) : (z == 3.0 ? 1.0 : 0.0));   // oben / unten
    if (uPattern < 3.5) return s == 0.0 ? 1.0 : 0.0;                                     // alle vier Beats alles
    if (uPattern < 4.5) return (mod(s, 2.0) == 0.0 ? (z < 1.5 ? 1.0 : 0.0) : (z > 1.5 ? 1.0 : 0.0));     // Seiten / Mitte
    return step(0.5, hash12(vec2(z, s + floor(uSpinT * 0.1))));                           // zufällig
}

// Geworfenes Objekt: q = Koordinaten um den Kern (isotrop). Flug (0..0.08), Kreisen und Einziehen (0.08..1):
// Objekt zerfällt mit dem Fortschritt in Blöcke (Pixelraster, Blöcke fallen weg) und zieht einen Datenstrom hinter sich her.
vec3 throwFx(vec3 col, vec2 q, float t, int i) {
    vec4 th = throwAt(i), par = parAt(i);
    float P = th.x;
    if (P <= 0.0) return col;
    float side = th.z, seed = th.w, swirl = par.x, rev = par.y;
    float fly = smoothstep(0.0, 0.08, P);
    float pull = smoothstep(0.08, 1.0, P);
    float r0 = 0.62, rad = mix(r0, uRadius * 0.5, pow(pull, 1.4));
    vec2 start = vec2(side * 0.95, par.z);
    float a0 = atan(start.y, start.x);
    float ang = a0 + swirl * (pull * pull * 9.0 + 0.3 * pull * uSpinT);
    vec2 c = mix(start, vec2(cos(ang), sin(ang)) * rad, fly);
    float sz = 0.16 * (1.0 - 0.6 * pull) * (1.0 + 0.05 * uBassS);
    vec2 d = (q - c) / sz;
    d = rot(pull * swirl * 2.0 + 0.2 * sin(t + seed)) * d;
    if (side > 0.0) d.x = -d.x;
    // Pixelzerfall: Blöcke verschwinden mit dem Fortschritt, Rest wird verschoben (Glitch)
    float blocks = 6.0 + 18.0 * (1.0 - pull);
    vec2 cellId = floor((d * 0.5 + 0.5) * blocks);
    float h = hash12(cellId + seed);
    float gone = step(h, pull * 1.1 - 0.1);
    vec2 glitch = vec2((hash12(cellId + 3.0 + floor(t * 6.0)) - 0.5) * 0.3, 0.0) * pull * step(0.6, hash12(cellId + 9.0 + floor(t * 3.0)));
    vec4 s = objCell(th.y, d + glitch);
    s.rgb = hueShift(s.rgb, pull * 2.5 * (0.5 + 0.5 * sin(uSpinT + seed)) + uHue * pull);
    s.rgb = mix(s.rgb, hueShift(vec3(0.2, 0.9, 1.0), uHue2), pull * 0.4 * step(0.5, hash12(cellId + 7.0)));
    col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * (1.0 - gone) * fly);
    // Datenstrom: Blöcke laufen von der Bahn in den Kern (entlang der Spirale), pulsieren im Takt, Farbe uHue2
    float r = length(q), a = atan(q.y, q.x);
    float rel = mod((a - ang) * swirl + PI, 2.0 * PI) - PI;
    if (rel > 0.0 && rel < 2.5 && pull > 0.02) {
        float u = rel / 2.5;
        float rb = mix(rad, uRadius * 0.4, u);
        float v = (r - rb) / (0.03 + 0.03 * pull);
        if (abs(v) < 1.0) {
            float cellA = floor(rel * 14.0 + uSpinT * 6.0), cellB = floor(v * 3.0);
            float on = step(0.45, hash12(vec2(cellA, cellB) + seed));
            vec3 dc = hueShift(vec3(0.2, 1.0, 0.9), u * 2.0 + uHue2 + seed);
            col += dc * on * (0.35 + 0.5 * uBeatPulse) * pull * (1.0 - u) * (1.0 - rev * 0.5);
        }
    }
    return col;
}

// Variante 1: Datenwürfel – isometrisches Würfelgitter auf der Kugel (Sechseck = Würfel: Deckel hell, links mittel,
// rechts dunkel), Würfel blinken im Takt, Kanten leuchten, Farbe uHue
vec3 cubes(vec2 p, float t, float live) {
    float rr = min(length(p), 0.999);
    p *= 1.0 / sqrt(1.0 - rr * rr * 0.8);                                  // Kugelwölbung
    p = rot(0.15 * sin(t * 0.3)) * p;
    vec2 hp = p * 3.2;
    const vec2 S = vec2(1.0, 1.7320508);
    vec2 a = mod(hp, S) - S * 0.5, b = mod(hp - S * 0.5, S) - S * 0.5;
    vec2 d = dot(a, a) < dot(b, b) ? a : b;                                  // Abstand zur nächsten Würfelmitte
    vec2 id = floor((hp - d) * 2.0 + 0.5);
    float ang = atan(d.y, d.x);
    float face = (ang > 0.5236 && ang < 2.618) ? 0.0 : ((ang >= 2.618 || ang < -1.5708) ? 1.0 : 2.0);
    float hexD = max(abs(d.x), dot(abs(d), vec2(0.5, 0.866)));
    vec2 u0 = vec2(0.866, 0.5), u1 = vec2(-0.866, 0.5), u2 = vec2(0.0, -1.0);
    float sp = 1.0;
    if (dot(d, u0) > 0.0) sp = min(sp, abs(d.x * u0.y - d.y * u0.x));
    if (dot(d, u1) > 0.0) sp = min(sp, abs(d.x * u1.y - d.y * u1.x));
    if (dot(d, u2) > 0.0) sp = min(sp, abs(d.x * u2.y - d.y * u2.x));
    float edge = smoothstep(0.06, 0.0, 0.5 - hexD) + smoothstep(0.05, 0.0, sp);
    float h = hash12(id + floor(t * (1.0 + 4.0 * uBassS)) * 0.37 + uSeed);
    float blink = step(0.62 - 0.35 * uBeatPulse, hash12(id + floor(uBeatStep) + uSeed));
    float shade = face == 0.0 ? 1.0 : (face == 1.0 ? 0.6 : 0.32);
    vec3 base = hueShift(vec3(0.05, 0.45, 0.85), uHue) * shade * (0.55 + 0.45 * live);
    vec3 glow = hueShift(vec3(0.5, 1.0, 1.1), uHue + h * 0.8) * blink * (0.5 + 0.7 * uBeatPulse + 0.5 * uBassS) * shade;
    return base + glow + hueShift(vec3(0.6, 1.0, 1.0), uHue) * min(edge, 1.0) * (0.3 + 0.5 * uBassS + 0.4 * uBeatPulse);
}

// Variante 2: Blitzkugel – dunkle Kugel, Blitzfäden vom Zentrum zur Hülle, zucken mit Bass und Beat
vec3 ball(vec2 p, float t, float live) {
    float r = length(p), a = atan(p.y, p.x);
    vec3 col = hueShift(vec3(0.08, 0.04, 0.22), uHue) * (1.0 - 0.5 * r) + hueShift(vec3(0.2, 0.1, 0.5), uHue) * fbm(p * 3.0 + t * 0.2) * 0.5;
    float glow = 0.0, line = 0.0;
    for (int k = 0; k < 11; k++) {
        float fk = float(k);
        float ak = fk * 0.571 + uSpinT * 0.25 + hash12(vec2(fk, floor(t * 6.0))) * 0.6;
        float off = (noise(vec2(r * 7.0 + fk * 3.1, t * 3.0 + fk)) - 0.5) * 2.0 * r + (noise(vec2(r * 25.0 + fk, t * 9.0)) - 0.5) * 0.5 * r;
        float da = mod(a - ak - off + PI, 2.0 * PI) - PI;
        float dist = abs(da) * max(r, 0.04);
        float on = step(0.3 - 0.3 * uBassS - 0.3 * uBeatPulse, hash12(vec2(fk, floor(t * 10.0))));
        glow += smoothstep(0.09, 0.0, dist) * on * smoothstep(1.05, 0.9, r);
        line += smoothstep(0.018, 0.0, dist) * on;
    }
    col += hueShift(vec3(0.5, 0.3, 1.0), uHue) * glow * 0.7 * (0.6 + 0.4 * live);
    col += hueShift(vec3(0.85, 0.9, 1.0), uHue) * min(line, 1.5) * (0.9 + 0.5 * uBassS) * (0.6 + 0.4 * live);
    col += hueShift(vec3(0.9, 0.95, 1.0), uHue) * smoothstep(0.3, 0.0, r) * (1.0 + 1.0 * uBassS + 0.6 * uBeatPulse);
    col += hueShift(vec3(0.5, 0.4, 1.0), uHue) * smoothstep(0.8, 1.0, r) * smoothstep(1.1, 1.0, r) * (0.8 + 0.6 * uBeatPulse);
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    vec2 cen = uCenter;
    vec2 uv = mix(vUv, cen + (vUv - cen) / 2.2, uZoom);
    uv += vec2(0.002 * sin(t * 0.3), 0.0015 * cos(t * 0.23));
    float ejectT = uEjectT;
    float surge = ejectT >= 0.0 ? (ejectT < 1.2 ? ejectT / 1.2 : exp(max(-(ejectT - 1.2) * 0.6, -60.0))) : 0.0;
    uv += vec2(0.006 * sin(t * 50.0), 0.005 * cos(t * 37.0)) * surge;
    vec2 q = (uv - cen) * vec2(aspect, 1.0);
    float r = length(q), a = atan(q.y, q.x);
    float breath = 1.0 + 0.06 * sin(t * 0.7) * (1.0 - live);
    float R = uRadius * breath * (1.0 + 0.14 * uBassS * live + 0.05 * uBeatPulse + 0.25 * surge);
    // ---- Druckwellen (uShock): das Bild wird radial gestaucht, wo die Welle gerade ist
    float shock = 0.0, shockEnv = 0.0;
    for (int i = 0; i < 3; i++) {
        float s = shockAt(i);
        if (s > 1.6) continue;
        float env = exp(max(-sq((r - R - s * 0.95) * 9.0), -60.0)) * exp(-s * 1.6);
        shock += env;
        shockEnv += env * (r - R - s * 0.95 < 0.0 ? 1.0 : -1.0);
    }
    vec2 dir = r > 0.001 ? q / r : vec2(1.0, 0.0);
    // ---- Beat-Wellen: Umhüllende an diesem Pixel, Bodengitter hebt sich darunter
    float wave = 0.0, edgeW = 0.0;
    for (int i = 0; i < 6; i++) {
        float age = ringAt(i);
        if (age > 3.0) continue;
        float d = r - R - age * RING_V;
        wave += exp(max(-sq(d * 22.0), -60.0)) * exp(-age * 1.1);
        edgeW += exp(max(-sq(d * 70.0), -60.0)) * exp(-age * 0.9);
    }
    wave = min(wave, 1.5);
    float floorM = smoothstep(FLOOR_Y + 0.04, FLOOR_Y - 0.06, uv.y) * (1.0 - smoothstep(0.9, 1.5, r)) * (1.0 - uZoom);
    vec2 suv = uv - dir * (0.06 * shockEnv) / vec2(aspect, 1.0);
    suv.y += 0.03 * wave * floorM;
    vec2 sq2 = (suv - cen) * vec2(aspect, 1.0);
    float sr = length(sq2);
    // ---- Kern: das Foto um den Kern wird gedreht und verzerrt (Energie wirbelt), Farbe mit uHue
    float inside = smoothstep(R * 1.15, R * 0.6, sr);
    vec2 qq = rot(uSpinT * 0.6 * inside) * sq2;
    qq += (vec2(fbm(sq2 * 6.0 + uSpinT * 0.3), fbm(sq2 * 6.0 - uSpinT * 0.2 + 5.0)) - 0.5) * 0.06 * inside * (1.0 + uBassS);
    vec2 duv = cen + qq / vec2(aspect, 1.0);
    vec3 col = scene(mix(suv, duv, inside));
    vec3 plate = col;
    float lum = max(col.r, max(col.g, col.b));
    // Halle: komplementär nach dem Drop, dunkel in der Stille
    vec3 hall = hueShift(col, PI * uHallT) * (0.5 + 0.5 * live);
    col = mix(hall, hueShift(col, uHue) * (0.75 + 0.25 * live), inside);
    col += col * inside * (0.3 * uBassS + 0.5 * uBeatPulse + 0.8 * uFlash) * live;
    // Varianten 1 und 2 ersetzen das Plasma im Kern
    float Rv = R * 1.9;                                                      // die ganze Kugel des Fotos
    vec2 pc = rot(uSpinT * 0.3) * (sq2 / Rv);
    float sphere = smoothstep(Rv * 1.02, Rv * 0.9, sr);
    float limb = 1.0 - 0.55 * sq(min(sr / Rv, 1.0));
    float w1 = variantW(1.0), w2 = variantW(2.0);
    if (w1 > 0.001) col = mix(col, cubes(pc, t, live) * limb, sphere * w1);
    if (w2 > 0.001) col = mix(col, ball(pc, t, live) * limb, sphere * w2);
    // Lichtbögen springen aus dem Kern (Bass), Funken (Höhen)
    for (int k = 0; k < 5; k++) {
        float fk = float(k);
        float an = fk * 1.26 + uSpinT * 0.5 + sin(t * 3.0 + fk) * 0.4;
        float on = step(0.6 - 0.4 * uBassS, hash12(vec2(fk, floor(t * 14.0))));
        vec2 ad = vec2(cos(an), sin(an));
        float along = dot(q, ad), across = abs(dot(q, vec2(-ad.y, ad.x)) + 0.02 * sin(along * 60.0 + t * 30.0));
        float arc = smoothstep(0.006, 0.0, across) * smoothstep(R * 0.9, R * 1.1, along) * smoothstep(R * 2.2, R * 1.3, along);
        col += hueShift(vec3(0.5, 0.9, 1.0), uHue) * arc * on * (0.8 + 0.5 * uBassS) * live;
    }
    for (int k = 0; k < 24; k++) {
        float fk = float(k);
        float h1 = hash12(vec2(fk, 21.0)), h2 = hash12(vec2(fk, 23.0));
        float age = mod(t * (0.5 + h2 + uHighS) + h1 * 4.0, 2.0);
        vec2 sp = vec2(cos(h1 * 6.28), sin(h1 * 6.28)) * (R + age * 0.3) + vec2(0.0, -age * age * 0.1);
        col += vec3(1.0, 0.9, 0.6) * smoothstep(0.004, 0.0, length(q - sp)) * (1.0 - age / 2.0) * (0.3 + 1.4 * uHighS) * live;
    }
    // ---- Beat-Wellen: Ring über die ganze Halle, Lichtpunkte der Schränke leuchten, wenn die Welle sie erreicht
    float orb = smoothstep(Rv * 1.15, Rv * 0.95, sr);                       // die Kugel des Fotos bleibt frei
    float lights = smoothstep(0.4, 0.8, lum) * (1.0 - orb);
    vec3 ringCol = hueShift(vec3(0.4, 0.9, 1.0), uHue);
    col += ringCol * (wave * 0.3 + edgeW * 0.5) * (1.0 - orb);
    col += plate * lights * wave * 2.4;
    col += plate * wave * 0.4 * (1.0 - orb);
    // Bodengitter: perspektivische Linien, leuchten mit der Welle und dem Bass
    if (floorM > 0.001) {
        float depth = max(FLOOR_Y - uv.y, 0.0) + 0.03;
        float gx = (uv.x - cen.x) / depth, gy = 0.06 / depth;
        float gl = smoothstep(0.08, 0.0, abs(fract(gx * 0.9) - 0.5)) + smoothstep(0.1, 0.0, abs(fract(gy - t * 0.1) - 0.5));
        col += ringCol * gl * floorM * (0.04 + 0.1 * uBassS * live + 0.5 * wave) * smoothstep(0.0, 0.1, depth - 0.03);
    }
    // Lauflicht: Zonen links/rechts/oben/unten blitzen nach dem Muster
    float zone = uv.x < 0.36 ? 0.0 : (uv.x > 0.64 ? 1.0 : (uv.y > cen.y ? 2.0 : 3.0));
    float run = zoneOn(zone) * (1.0 - 0.7 * uStepPhase);
    col += plate * lights * (0.4 * uBassS + 1.4 * run) * live;
    // Datenregen in den Schrankreihen (Höhen)
    float rack = smoothstep(0.2, 0.3, abs(uv.x - 0.5)) * (1.0 - orb) * (1.0 - floorM);
    if (rack > 0.001) {
        float cx = floor(uv.x * 180.0);
        float hc = hash12(vec2(cx, 5.0));
        float yy = fract(uv.y * 1.3 + t * (0.25 + 0.5 * hc) + hc * 7.0);
        float head = step(0.965 - 0.08 * uHighS, hash12(vec2(cx, floor(yy * 50.0) + floor(t * 0.5 + hc) * 3.0)));
        float trail = smoothstep(0.0, 0.6, fract(yy * 50.0)) * smoothstep(0.0, 0.3, abs(fract(uv.x * 180.0) - 0.5) * -1.0 + 0.5);
        col += hueShift(vec3(0.3, 1.0, 0.8), uHue2) * head * trail * rack * (0.2 + 0.9 * uHighS) * live;
    }
    // ---- Druckwelle sichtbar: heller Saum, Chroma-Riss
    col += hueShift(vec3(1.0, 0.7, 0.9), uHue) * shock * 0.5 * (1.0 - orb);
    col += plate * shock * 0.8 * (1.0 - orb);
    col.r += shock * 0.2 * sin(a * 30.0 + t * 20.0);
    // ---- Geworfene Objekte
    for (int i = 0; i < 3; i++) col = throwFx(col, q, t, i);
    // ---- Drohnenschwarm: Perlenkette aus Drohnen auf einer Spirale
    if (uSwarmT >= 0.0) {
        float sp = uSwarmT / 30.0;
        for (int k = 0; k < 14; k++) {
            float fk = float(k);
            float p = clamp(sp * 1.6 - fk * 0.05, 0.0, 1.0);
            float rad = mix(0.75, uRadius * 0.4, p);
            float an = 2.0 + p * p * 10.0 + 0.35 * uSpinT + fk * 0.12;
            vec2 c = vec2(cos(an), sin(an)) * rad;
            float sz = 0.05 * (1.0 - 0.7 * p);
            vec2 d = (q - c) / sz;
            d = rot(an + PI * 0.5) * d;
            vec4 s = objCell(0.0, d);
            float gone = step(hash12(floor((d * 0.5 + 0.5) * 8.0) + fk), p * 1.3 - 0.3);
            col = mix(col, hueShift(s.rgb, p * 2.0) + vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 4.0 + fk * 0.3)) * 0.3, s.a * (1.0 - gone) * step(0.001, p) * (1.0 - smoothstep(0.95, 1.0, p)));
        }
    }
    // ---- Überlast: Anschwellen, Blitz, Druckwelle, Trümmerblöcke fliegen aus dem Kern
    if (ejectT >= 0.0) {
        if (ejectT < 1.2) {
            col += hueShift(vec3(0.8, 0.9, 1.0), uHue) * inside * surge * 1.5;
        } else {
            float bt = ejectT - 1.2;
            col += vec3(1.0) * exp(-bt * 4.0) * exp(-r * 2.0) * 2.0;
            col += vec3(0.6, 0.9, 1.0) * exp(max(-sq((r - bt * 0.9) * 12.0), -60.0)) * exp(-bt * 0.8);
            for (int k = 0; k < 30; k++) {
                float fk = float(k);
                float h1 = hash12(vec2(fk, 3.0)), h2 = hash12(vec2(fk, 5.0)), h3 = hash12(vec2(fk, 7.0));
                vec2 dd = vec2(cos(h1 * 6.28), sin(h1 * 6.28));
                vec2 p = dd * (R + bt * (0.3 + 0.6 * h2)) + vec2(0.0, -0.15 * bt * bt);
                vec2 d = rot(bt * (h3 - 0.5) * 8.0) * (q - p) / (0.02 + 0.02 * h3);
                float blk = step(max(abs(d.x), abs(d.y)), 1.0);
                col = mix(col, hueShift(vec3(0.2, 0.9, 1.0), h3 * 4.0) * (0.6 + 0.4 * sin(t * 20.0 + fk)), blk * exp(-bt * 0.5));
            }
        }
    }
    // ---- EMP: weißer Ring, Bild kurz schwarzweiß und ohne Lichter
    if (uEmpT >= 0.0) {
        float e = exp(-uEmpT * 1.2);
        col += vec3(0.9, 0.95, 1.0) * exp(max(-sq((r - uEmpT * 1.2) * 15.0), -60.0)) * e;
        float gray = dot(col, vec3(0.33));
        col = mix(col, vec3(gray) * 0.6, smoothstep(0.0, 0.2, uEmpT) * e);
        col += (noise(vUv * 200.0 + t * 30.0) - 0.5) * 0.2 * e;
    }
    // ---- Drop: Blitz, Stille: Kern schläft
    col += hueShift(vec3(0.5, 0.9, 1.0), uHue) * uFlash * 0.3 * exp(-r * 2.0);
    col *= 0.75 + 0.25 * live;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
