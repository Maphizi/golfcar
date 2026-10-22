#version 140
// Fluxkompensator: Werkstatt-Foto (uSceneTex), das Y aus drei Lichtröhren (helle weißblaue Stellen um uCenter, Arme
// uArm0-2 = Richtung, Länge isotrop) pulst mit dem Bass, Beat = Lichtstoß vom Knoten durch die Arme + Ringe (uRing0-5),
// Höhen = Funken an den Kabeln, Mitten = Oszilloskop-Wellen (uAudioTex Zeile 1), Drop = Farbwechsel (uHue), Stille = Glimmen.
// Geworfene Objekte (uThrowN: Fortschritt, Zelle 6x4 à 192, Seite, Seed; uThrowParN: Drehsinn*Dauer, rückwärts, Starthöhe,
// uSpinT beim Wurf; uSpinRate = Drehung je Sekunde)
// fliegen ein, ziehen zwei Feuerspuren, dehnen sich zur Zeitschleife und lösen sich in Blitze auf, die zum Knoten laufen.
// Gewitter uStormT + uBoltN (Alter, x, Seed), Paradoxon uEjectT + Polaroid (uPhotoTex, uPolaroid, uFade),
// 1,21 Gigawatt uOverT, Nahaufnahme uZoom.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uObjTex, uPhotoTex;
uniform vec2 uSceneSize, uObjSize, uPhotoSize, uCenter;
uniform vec4 uArm0, uArm1, uArm2;
uniform float uSeed, uRadius, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash, uHue, uSpinT, uSpinRate, uZoom;
uniform float uStormT, uEjectT, uOverT, uFade, uPolaroid, uRing0, uRing1, uRing2, uRing3, uRing4, uRing5;
uniform float uCharge, uDischargeT;                       // Ladung 0..1 der Röhren, Alter der Entladung (-1 = keine)
uniform vec2 uFlow;                                        // Lauflicht: Richtung (+1 außen / -1 innen), Tempo
uniform vec4 uSpray;                                       // Funken aus einem Röhrenende: Alter, Arm (3 = alle), Seed, Stärke
uniform vec4 uThrow0, uThrow1, uThrow2, uThrowPar0, uThrowPar1, uThrowPar2, uBolt0, uBolt1, uBolt2;
const float PI = 3.14159265;
const int STORM_LEN = 20;

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
vec4 throwAt(int i) { return i == 0 ? uThrow0 : (i == 1 ? uThrow1 : uThrow2); }
vec4 parAt(int i) { return i == 0 ? uThrowPar0 : (i == 1 ? uThrowPar1 : uThrowPar2); }
vec4 armAt(int i) { return i == 0 ? uArm0 : (i == 1 ? uArm1 : uArm2); }
vec4 boltAt(int i) { return i == 0 ? uBolt0 : (i == 1 ? uBolt1 : uBolt2); }

// Abstand Punkt - Strecke und Lage entlang der Strecke (0..1)
float segDist(vec2 p, vec2 a, vec2 b, out float u) {
    vec2 ab = b - a;
    u = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
    return length(p - (a + ab * u));
}
// Kürzester Abstand zu den drei Armen des Y (vom Knoten aus)
float armDist(vec2 q) {
    float d = 9.0, u;
    for (int i = 0; i < 3; i++) { vec4 a = armAt(i); d = min(d, segDist(q, vec2(0.0), a.xy * a.z, u)); }
    return d;
}
// Zackiger Blitz von a nach b: Leuchtkern + Hof, Zacken wechseln mit der Zeit (seed)
float bolt(vec2 p, vec2 a, vec2 b, float seed, float t, float amp) {
    vec2 ab = b - a;
    float len = max(length(ab), 1e-4);
    vec2 dir = ab / len, nrm = vec2(-dir.y, dir.x);
    float u = dot(p - a, dir) / len;
    if (u < -0.02 || u > 1.02) return 0.0;
    float tt = floor(t * 24.0) * 0.37 + seed;
    float off = (noise(vec2(u * 7.0, tt)) - 0.5) * 1.6 + (noise(vec2(u * 23.0, tt + 9.0)) - 0.5) * 0.5;
    off *= amp * sin(clamp(u, 0.0, 1.0) * PI);
    float dd = abs(dot(p - a, nrm) - off);
    return exp(-dd * 220.0) + 0.35 * exp(-dd * 40.0);
}
// Bahn eines geworfenen Objekts: Einflug (0..0.08) von der Seite, dann Zeitschleife (Spirale nach innen);
// spinRel = seit dem Wurf aufgelaufene Drehung (uSpinT - Startwert), läuft nach einem Drop rückwärts
vec2 throwPos(float P, float side, float y0, float swirl, float spinRel, out float pull) {
    float fly = smoothstep(0.0, 0.08, P);
    pull = smoothstep(0.08, 1.0, P);
    float rad = mix(0.6, uRadius * 1.1, pow(pull, 1.6));
    vec2 start = vec2(side * 0.98, y0);
    float a0 = atan(start.y, start.x);
    float ang = a0 + swirl * pull * pull * 8.0 + 0.5 * pull * spinRel;
    return mix(start, vec2(cos(ang), sin(ang)) * rad, fly);
}

// Geworfenes Objekt mit zwei Feuerspuren, Dehnung zur Zeitschleife, Auflösung in Blitze zum Knoten
vec3 throwFx(vec3 col, vec2 q, float t, int i) {
    vec4 th = throwAt(i), par = parAt(i);
    float P = th.x;
    if (P <= 0.0) return col;
    float side = th.z, seed = th.w, swirl = sign(par.x), dur = max(abs(par.x), 1.0), rev = par.y, y0 = par.z;
    float spinRel = uSpinT - par.w;
    float dPdt = (rev > 0.5 ? -4.0 : 1.0) / dur;        // Fortschritt je Sekunde (rückwärts beim Paradoxon)
    float pull;
    vec2 c = throwPos(P, side, y0, swirl, spinRel, pull);
    float dissolve = smoothstep(0.84, 0.97, pull);
    // Feuerspuren: zwei parallele Spuren entlang der Bahn der letzten 2 s, flackernd, hinten verglühend
    vec2 prev = c;
    float pl;
    vec3 fire = vec3(0.0);
    for (int k = 1; k <= 8; k++) {
        float back = float(k) * 0.25;
        float Pk = P - back * dPdt;
        if (Pk < 0.0 || Pk > 1.0) break;
        vec2 pk = throwPos(Pk, side, y0, swirl, spinRel - back * uSpinRate, pl);
        vec2 seg = prev - pk;
        vec2 nrm = normalize(vec2(-seg.y, seg.x) + 1e-5);
        float w = 0.014 * (1.0 - 0.45 * pull);
        float u;
        float d1 = segDist(q, pk + nrm * w, prev + nrm * w, u), d2 = segDist(q, pk - nrm * w, prev - nrm * w, u);
        float d = min(d1, d2);
        float age = (float(k) - u) / 8.0;
        float flick = 0.6 + 0.6 * noise(vec2(age * 30.0 + seed, t * 22.0));
        float g = exp(-d * 240.0) * 1.6 + exp(-d * 50.0) * 0.5;
        fire += mix(vec3(1.0, 0.85, 0.3), vec3(1.0, 0.3, 0.05), age) * g * flick * (1.0 - age * 0.85);
        prev = pk;
    }
    col += fire * (1.0 - dissolve) * (0.8 + 0.4 * uBassS) * (1.0 - 0.4 * rev);
    // Das Objekt: wird entlang der Bahn gedehnt (Zeitschleife), elektrisch blau überzogen, löst sich auf
    float sz = 0.12 * (1.0 - 0.25 * pull) * (1.0 + 0.04 * uBassS);
    vec2 d = (q - c) / sz;
    float tang = atan(c.y, c.x) + PI * 0.5;
    d = rot(-tang * smoothstep(0.0, 0.35, pull)) * d;
    d.x /= 1.0 + 2.2 * pull;
    d = rot(0.15 * sin(t * 1.3 + seed)) * d;
    if (side > 0.0) d.x = -d.x;
    vec4 s = objCell(th.y, d);
    s.rgb = mix(s.rgb, hueShift(vec3(0.6, 0.85, 1.0), uHue) * 1.3, pull * 0.45);
    float crack = step(0.55, noise(d * 6.0 + vec2(seed, floor(t * 12.0)))) * dissolve;
    col = mix(col, s.rgb * (1.0 + 0.5 * uBeatPulse * pull), s.a * (1.0 - dissolve) * (1.0 - crack * 0.7));
    col += hueShift(vec3(0.5, 0.8, 1.0), uHue) * s.a * dissolve * (1.0 - dissolve) * 2.0;
    // Auflösung: Blitze vom Objekt zum Knoten, ein zweiter zum nächsten Arm
    if (dissolve > 0.0 && dissolve < 1.0) {
        float e = dissolve * (1.0 - dissolve) * 4.0;
        float on = step(0.15, hash12(vec2(floor(t * 20.0), seed)));
        float b = bolt(q, c, vec2(0.0), seed, t, 0.2);
        vec4 arm = armAt(int(mod(seed, 3.0)));
        b += bolt(q, c, arm.xy * arm.z * 0.8, seed + 5.0, t + 3.0, 0.1) * 0.7;
        col += mix(hueShift(vec3(0.6, 0.85, 1.0), uHue), vec3(1.0), 0.5) * b * e * on * 2.5;
    }
    return col;
}

void main() {
    float aspect = uSceneSize.x / max(uSceneSize.y, 1.0);
    float t = iTime;
    float live = uLive;
    vec2 cen = uCenter;
    float stormT = uStormT;
    float stormA = stormT >= 0.0 ? min(1.0, stormT / 1.5) * min(1.0, (float(STORM_LEN) - stormT) / 2.0) : 0.0;
    float ejectT = uEjectT;
    float surge = ejectT >= 0.0 ? (ejectT < 1.2 ? ejectT / 1.2 : exp(-(ejectT - 1.2) * 0.6)) : 0.0;
    float overE = uOverT >= 0.0 ? exp(-uOverT * 1.8) : 0.0;
    // Blitzschläge (Gewitter): jüngstes Alter für Flash und Flackern
    float boltFlash = 0.0;
    for (int i = 0; i < 3; i++) { float age = boltAt(i).x; if (age < 1.0) boltFlash = max(boltFlash, exp(-age * 7.0)); }
    // ---- Bildlage: Nahaufnahme, leichtes Atmen, Bass-Beben, Zittern bei Überladung / Paradoxon / Donner
    vec2 uv = mix(vUv, cen + (vUv - cen) / 2.3, uZoom);
    uv += vec2(0.0015 * sin(t * 0.3), 0.001 * cos(t * 0.23));
    uv += vec2(0.0018 * sin(t * 47.0), 0.0014 * cos(t * 53.0)) * uBassS * live;
    uv += vec2(0.006 * sin(t * 50.0), 0.005 * cos(t * 37.0)) * surge;
    uv += vec2(0.012 * sin(t * 73.0), 0.009 * cos(t * 61.0)) * overE;
    uv += vec2(0.004 * sin(t * 31.0), 0.003 * cos(t * 29.0)) * boltFlash;
    vec2 q = (uv - cen) * vec2(aspect, 1.0);
    float r = length(q);
    float R = uRadius;
    vec3 plate = scene(uv);
    vec3 col = plate;
    float lum = max(col.r, max(col.g, col.b));
    float minc = min(col.r, min(col.g, col.b));
    // ---- Röhren des Y erkennen: hell und weißblau, nahe am Knoten; blaues Streulicht im Kasten weicher
    float near = smoothstep(R * 2.6, R * 1.4, r);
    float tube = smoothstep(0.62, 0.86, minc) * smoothstep(-0.03, 0.06, col.b - col.r) * near;
    float glow = smoothstep(0.1, 0.4, col.b - col.r) * smoothstep(0.1, 0.5, col.b) * smoothstep(R * 3.0, R * 1.2, r) * (1.0 - tube);
    float aDist = armDist(q);
    float halo = exp(-aDist * 22.0);
    // Lichtstoß vom Knoten durch die Arme (Beat) + Ringe nach außen; Lichtstöße addieren sich
    float pulse = 0.0, rings = 0.0;
    for (int i = 0; i < 6; i++) {
        float age = ringAt(i);
        if (age > 3.0) continue;
        pulse += exp(-pow((r - age * 0.5) * 28.0, 2.0)) * exp(-age * 2.5);
        rings += exp(-pow((r - R * 1.5 - age * 0.35) * 40.0, 2.0)) * exp(-age * 1.5);
    }
    float flick = mix(1.0, 0.35 + 0.65 * step(0.3, hash12(vec2(floor(t * 26.0), 3.0))), stormA * 0.8 + boltFlash * 0.5);
    float glimmer = 0.42 + 0.08 * sin(t * 1.7 + 2.0 * noise(vec2(t * 0.5, 1.0)));
    float disE = uDischargeT >= 0.0 ? exp(-uDischargeT * 2.2) : 0.0;
    // Ladung: Röhren füllen sich vom Knoten aus bis uCharge (heller Kopf), Lauflicht fließt entlang der Arme (uFlow)
    float fillGlow = 0.0, headGlow = 0.0, flowGlow = 0.0, nearFilled = 1.0, nearD = 9.0;
    for (int i = 0; i < 3; i++) {
        vec4 a = armAt(i);
        float u;
        float d = segDist(q, vec2(0.0), a.xy * a.z, u);
        float w = exp(-d * 28.0);
        float filled = smoothstep(uCharge + 0.04, uCharge - 0.04, u);
        fillGlow += w * filled;
        if (d < nearD) { nearD = d; nearFilled = filled; }
        headGlow += w * exp(-pow((u - uCharge) * 10.0, 2.0)) * step(0.02, uCharge) * (1.0 - step(0.999, uCharge) * 0.5);
        float stripes = 0.5 + 0.5 * sin(u * 36.0 - t * uFlow.y * uFlow.x + float(i) * 2.0);
        flowGlow += w * smoothstep(0.55, 0.95, stripes) * filled;
    }
    // ungeladener Teil der Röhren bleibt dunkel (Glimmen), geladener Teil leuchtet voll
    float lit = mix(0.3, 1.0, nearFilled);
    float power = min(2.4, mix(glimmer, (0.7 + 0.5 * uBassS + 0.35 * uBeatPulse) * lit, live) * flick + 0.8 * pulse + 1.5 * overE + 0.8 * surge + 1.2 * disE);
    vec3 tubeCol = hueShift(vec3(0.62, 0.82, 1.0), uHue);
    // Röhren: Grundlicht dimmen (Stille), färben (Drop), aufhellen (Bass, Beat, Stöße)
    col = mix(col, hueShift(col, uHue), max(tube, glow * 0.9));
    col *= mix(1.0, power, tube);
    col *= mix(1.0, 0.45 + 0.55 * power, glow);
    col += tubeCol * halo * (0.06 + 0.35 * uBassS * live + 0.9 * pulse + 0.6 * overE) * (0.3 + 0.7 * live + overE);
    col += tubeCol * exp(-r * 12.0) * (0.15 * uBassS * live + 0.5 * pulse + overE);
    col += tubeCol * rings * 0.3 * (1.0 - near);
    col += tubeCol * fillGlow * (0.05 + 0.2 * uCharge) * live * (1.0 - tube);
    col += vec3(1.0, 0.95, 0.85) * headGlow * (0.4 + 0.6 * uBassS + 0.3 * uBeatPulse) * live;
    col += tubeCol * flowGlow * (0.15 + 0.25 * uBassS) * live * tube;
    if (disE > 0.0) {                                                        // Entladung: weißer Stoß nach innen, Knoten blitzt
        col += tubeCol * halo * disE * 1.6 + vec3(1.0) * exp(-r * 9.0) * disE * 1.2;
        col += vec3(1.0, 0.98, 0.9) * exp(max(-uDischargeT * 7.0, -60.0)) * 0.35;
    }
    // Funken sprühen aus einem Röhrenende (oder allen bei der Entladung), nach außen und fallend
    if (uSpray.x >= 0.0) {
        for (int k = 0; k < 36; k++) {
            float fk = float(k);
            int ai = uSpray.y >= 2.5 ? int(mod(fk, 3.0)) : int(uSpray.y + 0.5);
            vec4 a = armAt(ai);
            float h1 = hash12(vec2(fk, uSpray.z)), h2 = hash12(vec2(fk, uSpray.z + 1.0)), h3 = hash12(vec2(fk, uSpray.z + 2.0));
            float age = uSpray.x * (0.7 + 0.6 * h2) - 0.3 * h3;
            if (age < 0.0 || age > 1.4) continue;
            vec2 dir = normalize(a.xy);
            vec2 nrm = vec2(-dir.y, dir.x);
            vec2 vel = dir * (0.25 + 0.45 * h1) + nrm * (h2 - 0.5) * 0.5;
            vec2 sp = dir * a.z + vel * age * 0.6 + vec2(0.0, -0.5 * age * age);
            float g = smoothstep(0.005 + 0.003 * h3, 0.0, length(q - sp));
            col += mix(vec3(1.0, 0.9, 0.6), tubeCol * 1.3, step(0.5, h3)) * g * (1.0 - age / 1.4) * 2.2 * uSpray.w;
        }
    }
    // ---- Lichter im Foto: rote Kontrolllampe blinkt auf Beats, warme Lampen flackern mit den Mitten
    float redLamp = smoothstep(0.5, 0.8, col.r) * smoothstep(0.35, 0.1, col.g) * (1.0 - tube);
    col += plate * redLamp * (1.5 * uBeatPulse + 0.3 * uBassS) * live;
    float warm = smoothstep(0.75, 0.95, col.r) * smoothstep(0.7, 0.45, col.b) * smoothstep(0.4, 0.7, col.g) * (1.0 - tube);
    col += plate * warm * (0.25 * uMidS + 0.1 * sin(t * 40.0 + uv.x * 50.0) * uMidS) * live;
    // ---- Oszilloskope: grüne Schirme pulsen mit den Mitten, zeichnen die Wellenform (uAudioTex Zeile 1)
    float screen = smoothstep(0.1, 0.3, col.g) * smoothstep(0.04, 0.15, col.g - col.r) * smoothstep(-0.06, 0.03, col.g - col.b) * (1.0 - tube) * (1.0 - glow);
    if (screen > 0.001) {
        float lx = fract((uv.x + 0.002) / 0.09), ly = clamp((uv.y - 0.45) / 0.15, 0.0, 1.0);
        float wave = texture(uAudioTex, vec2(lx, 0.75)).r * 2.0 - 1.0;
        float amp = mix(0.03, 0.3, clamp(uMidS * 1.5, 0.0, 1.0)) * live + 0.02;
        float line = exp(-abs(ly - 0.55 - wave * amp) * 60.0);
        float sweep = exp(-abs(fract(lx - t * 0.7) - 0.5) * 4.0);
        col += vec3(0.4, 1.0, 0.5) * screen * (line * 0.9 + sweep * 0.1 + 0.2 * uMidS * live + 0.05 * sin(t * 90.0));
        col *= 1.0 + screen * (0.3 * uMidS * live - 0.3 * (1.0 - live) * (0.5 + 0.5 * sin(t * 2.0)));
    }
    // ---- Funken an den Kabeln (Höhen): drei Quellen über und neben dem Kasten
    for (int k = 0; k < 24; k++) {
        float fk = float(k);
        float h1 = hash12(vec2(fk, 21.0)), h2 = hash12(vec2(fk, 23.0)), h3 = hash12(vec2(fk, 25.0));
        vec2 src = fk < 8.0 ? vec2(0.0, R * 2.3) : (fk < 16.0 ? vec2(R * 2.2, R * 1.6) : vec2(-R * 1.9, R * 1.5));
        float age = mod(t * (0.7 + h2) + h1 * 4.0, 1.6);
        vec2 sp = src + vec2((h1 - 0.5) * 0.5, 0.1 + 0.2 * h3) * age + vec2(0.0, -0.6 * age * age);
        float sparkOn = step(0.35 - 0.3 * uHighS, h3);
        col += vec3(1.0, 0.85, 0.5) * smoothstep(0.0045, 0.0, length(q - sp)) * (1.0 - age / 1.6) * (0.2 + 1.5 * uHighS) * live * sparkOn;
    }
    // ---- Geworfene Objekte
    for (int i = 0; i < 3; i++) col = throwFx(col, q, t, i);
    // ---- Gewitter: Szene kühler und dunkler, Regen am Fenster, Blitze schlagen von oben in die Kabel ein
    if (stormA > 0.0) {
        col = mix(col, col * vec3(0.7, 0.8, 1.0) * 0.75, stormA * (1.0 - tube));
        float win = smoothstep(0.08, 0.25, plate.b - plate.r) * smoothstep(0.45, 0.3, uv.x) * smoothstep(0.45, 0.6, uv.y);
        float rx = floor(uv.x * 160.0 + uv.y * 25.0);
        float ry = fract(uv.y * 2.5 + t * 2.2 + hash12(vec2(rx, 1.0)));
        float drop = smoothstep(0.12, 0.0, ry) * step(0.55, hash12(vec2(rx, floor(t * 0.4 + hash12(vec2(rx, 2.0))))));
        col += vec3(0.6, 0.75, 1.0) * drop * win * stormA * 0.5;
        col += vec3(0.5, 0.6, 0.9) * win * stormA * 0.08 * noise(uv * 30.0 + t);
        for (int i = 0; i < 3; i++) {
            vec4 b = boltAt(i);
            if (b.x > 0.7) continue;
            float e = exp(-b.x * 6.0) * step(0.2, hash12(vec2(floor(t * 30.0), b.z)) + step(b.x, 0.12));
            vec2 top = (vec2(b.y, 1.08) - cen) * vec2(aspect, 1.0);
            vec2 hit = vec2(0.0, R * 2.3) + vec2((hash12(vec2(b.z, 1.0)) - 0.5) * 0.15, 0.0);
            float bb = bolt(q, top, hit, b.z, t, 0.35);
            vec2 mid = mix(top, hit, 0.45);
            bb += bolt(q, mid, mid + vec2((hash12(vec2(b.z, 2.0)) - 0.5) * 0.5, -0.25), b.z + 7.0, t, 0.3) * 0.5;
            col += vec3(0.8, 0.9, 1.0) * bb * e * 1.5;
        }
        col += vec3(0.7, 0.8, 1.0) * boltFlash * 0.35;
    }
    // ---- Paradoxon: Anschwellen, Blitz, Druckwelle, Objekte aus allen Epochen fliegen rückwärts heraus, Sepia-Flimmern
    if (ejectT >= 0.0) {
        float ej = min(1.0, ejectT / 1.2) * min(1.0, (8.0 - ejectT) / 1.5);
        if (ejectT < 1.2) {
            col += tubeCol * (halo + exp(-r * 8.0)) * surge * 1.2;
        } else {
            float bt = ejectT - 1.2;
            col += vec3(1.0, 0.95, 0.85) * exp(-bt * 4.0) * exp(-r * 2.0) * 2.0;
            col += vec3(1.0, 0.8, 0.5) * exp(-pow((r - bt * 0.9) * 12.0, 2.0)) * exp(-bt * 0.8);
            for (int k = 0; k < 14; k++) {
                float fk = float(k);
                float h1 = hash12(vec2(fk, 3.0) + uSeed), h2 = hash12(vec2(fk, 5.0) + uSeed), h3 = hash12(vec2(fk, 7.0) + uSeed);
                vec2 dir = vec2(cos(h1 * 6.28), sin(h1 * 6.28));
                vec2 p = dir * (R * 0.6 + bt * (0.12 + 0.3 * h2)) + vec2(0.0, -0.08 * bt * bt);
                float sz = 0.05 + 0.04 * h3;
                vec2 d = rot(bt * (h3 - 0.5) * 6.0) * (q - p) / sz;
                vec4 s = objCell(floor(h2 * 24.0), d);
                float sep = dot(s.rgb, vec3(0.33));
                vec3 sc = mix(s.rgb, vec3(sep) * vec3(1.1, 0.95, 0.7), 0.7);
                col = mix(col, sc * (0.8 + 0.4 * sin(t * 20.0 + fk)), s.a * exp(-bt * 0.45) * ej);
            }
        }
        float sepia = dot(col, vec3(0.3, 0.5, 0.2));
        col = mix(col, vec3(sepia) * vec3(1.05, 0.9, 0.7), 0.45 * ej);
        col *= 1.0 - 0.15 * ej * step(0.8, hash12(vec2(floor(t * 18.0), 5.0)));
        col += vec3(0.6) * ej * step(0.997, hash12(vec2(floor(uv.x * 300.0), floor(t * 10.0)))) * 0.25;
    }
    // ---- Polaroid in der Ecke: das Fahrerfoto, verblasst von unten nach oben (uFade), Beats holen es zurück
    if (uPolaroid > 0.01) {
        vec2 fc = vec2(0.885, 0.23) - vec2(0.0, 0.3) * (1.0 - uPolaroid);
        vec2 fp = rot(-0.09) * ((vUv - fc) * vec2(aspect, 1.0));
        vec2 frameHalf = vec2(0.15, 0.185);
        float inFrame = step(abs(fp.x), frameHalf.x) * step(abs(fp.y), frameHalf.y);
        if (inFrame > 0.0) {
            vec2 ph = vec2(0.13);
            vec2 pc = fp - vec2(0.0, 0.035);
            vec2 puv = clamp(pc / ph * 0.5 + 0.5, 0.0, 1.0);
            float inPhoto = step(abs(pc.x), ph.x) * step(abs(pc.y), ph.y);
            vec3 photo = bilin(uPhotoTex, puv * uPhotoSize, uPhotoSize, vec2(0.0), uPhotoSize - 1.0).rgb;
            float ly = puv.y;
            float vanish = smoothstep(ly - 0.45, ly + 0.05, uFade * 1.2 + 0.08 * noise(puv * 12.0 + t * 0.5) - 0.08);
            float gray = dot(photo, vec3(0.33));
            vec3 faded = mix(photo, vec3(gray), 0.6) * 0.8 + 0.25;
            vec3 paper = vec3(0.93, 0.9, 0.82);
            vec3 pcol = mix(mix(photo, faded, smoothstep(0.0, 1.0, vanish * 2.0)), paper, smoothstep(0.5, 1.0, vanish));
            pcol += vec3(0.9, 0.95, 1.0) * exp(-abs(ly - uFade * 1.1 + 0.03) * 40.0) * 0.3 * step(0.02, uFade);
            vec3 frame = vec3(0.96, 0.95, 0.9) * (0.9 + 0.1 * noise(fp * 80.0));
            vec3 pol = mix(frame, pcol, inPhoto);
            pol *= 0.75 + 0.25 * live + 0.3 * uBeatPulse;
            col = mix(col, pol, uPolaroid);
        }
        col *= 1.0 - 0.25 * uPolaroid * exp(-max(0.0, max(abs(fp.x) - frameHalf.x, abs(fp.y) - frameHalf.y)) * 40.0) * (1.0 - inFrame);
    }
    // ---- 1,21 Gigawatt: Weißblitz, Lichtbögen über alle Kabel, kurz Negativ
    if (uOverT >= 0.0) {
        float e = overE;
        for (int k = 0; k < 8; k++) {
            float fk = float(k);
            float h1 = hash12(vec2(fk, 31.0)), h2 = hash12(vec2(fk, 33.0)), h3 = hash12(vec2(fk, 35.0));
            vec2 a = vec2(cos(h1 * 6.28), sin(h1 * 6.28)) * (R * 1.6 + 0.45 * h2);
            vec2 b = vec2(cos(h3 * 6.28), sin(h3 * 6.28)) * (R * 1.4 + 0.4 * h1);
            float on = step(0.45, hash12(vec2(floor(t * 30.0), fk)));
            col += vec3(0.75, 0.88, 1.0) * bolt(q, a, b, fk * 3.0, t, 0.3) * e * on * 1.6;
        }
        col += vec3(1.0) * exp(-uOverT * 5.0) * 1.3;
        col += tubeCol * (tube + halo) * e * 1.5;
        if (uOverT > 0.1 && uOverT < 0.26) col = max(vec3(0.0), 1.15 - col);
    }
    // ---- Drop: Blitz, Stille: Werkstatt im Dunkeln
    col += tubeCol * uFlash * 0.4 * exp(-r * 1.8);
    col *= 0.72 + 0.28 * live;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
