#version 140
// Der Kern: Serverkathedralen-Foto (uSceneTex), der Kern (uCenter, uRadius) pulst mit dem Bass, dreht mit uSpinT,
// Lichtbögen springen, Beat = Ringe (uRing0-5), Drop = Farbwechsel (uHue). Geworfene Objekte (uThrowN: Fortschritt,
// Zelle 6x4 à 192, Seite, Seed; uThrowParN: Spirale, rückwärts, Starthöhe) fliegen ein, kreisen spiralig nach innen und
// zerfallen in Pixelblöcke und einen Datenstrom. Drohnenschwarm uSwarmT, Überlast uEjectT, EMP uEmpT, Nahaufnahme uZoom.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uObjTex;
uniform vec2 uSceneSize, uObjSize, uCenter;
uniform float uSeed, uRadius, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash, uHue, uSpinT, uZoom;
uniform float uSwarmT, uEjectT, uEmpT, uRing0, uRing1, uRing2, uRing3, uRing4, uRing5;
uniform vec4 uThrow0, uThrow1, uThrow2, uThrowPar0, uThrowPar1, uThrowPar2;
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
vec4 objCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 6.0), ri = floor(idx / 6.0);
    vec2 lo = vec2(ci * 192.0, (3.0 - ri) * 192.0);
    return bilin(uObjTex, lo + (d * 0.5 + 0.5) * 192.0, uObjSize, lo, lo + 191.0);
}
float ringAt(int i) { return i == 0 ? uRing0 : (i == 1 ? uRing1 : (i == 2 ? uRing2 : (i == 3 ? uRing3 : (i == 4 ? uRing4 : uRing5)))); }
vec4 throwAt(int i) { return i == 0 ? uThrow0 : (i == 1 ? uThrow1 : uThrow2); }
vec4 parAt(int i) { return i == 0 ? uThrowPar0 : (i == 1 ? uThrowPar1 : uThrowPar2); }

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
    s.rgb = mix(s.rgb, vec3(0.2, 0.9, 1.0), pull * 0.4 * step(0.5, hash12(cellId + 7.0)));
    col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * (1.0 - gone) * fly);
    // Datenstrom: Blöcke laufen von der Bahn in den Kern (entlang der Spirale), pulsieren im Takt
    float r = length(q), a = atan(q.y, q.x);
    float rel = mod((a - ang) * swirl + PI, 2.0 * PI) - PI;
    if (rel > 0.0 && rel < 2.5 && pull > 0.02) {
        float u = rel / 2.5;
        float rb = mix(rad, uRadius * 0.4, u);
        float v = (r - rb) / (0.03 + 0.03 * pull);
        if (abs(v) < 1.0) {
            float cellA = floor(rel * 14.0 + uSpinT * 6.0), cellB = floor(v * 3.0);
            float on = step(0.45, hash12(vec2(cellA, cellB) + seed));
            vec3 dc = hueShift(vec3(0.2, 1.0, 0.9), u * 2.0 + uHue + seed);
            col += dc * on * (0.35 + 0.5 * uBeatPulse) * pull * (1.0 - u) * (1.0 - rev * 0.5);
        }
    }
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
    float surge = ejectT >= 0.0 ? (ejectT < 1.2 ? ejectT / 1.2 : exp(-(ejectT - 1.2) * 0.6)) : 0.0;
    uv += vec2(0.006 * sin(t * 50.0), 0.005 * cos(t * 37.0)) * surge;
    vec2 q = (uv - cen) * vec2(aspect, 1.0);
    float r = length(q), a = atan(q.y, q.x);
    float R = uRadius * (1.0 + 0.08 * uBassS * live + 0.04 * uBeatPulse + 0.25 * surge);
    // ---- Kern: das Foto um den Kern wird gedreht und verzerrt (Energie wirbelt), Farbe mit uHue
    vec2 duv = uv;
    float inside = smoothstep(R * 1.15, R * 0.6, r);
    vec2 qq = rot(uSpinT * 0.6 * inside) * q;
    qq += (vec2(fbm(q * 6.0 + uSpinT * 0.3), fbm(q * 6.0 - uSpinT * 0.2 + 5.0)) - 0.5) * 0.06 * inside * (1.0 + uBassS);
    duv = cen + qq / vec2(aspect, 1.0);
    vec3 col = scene(mix(uv, duv, inside));
    vec3 plate = col;
    float lum = max(col.r, max(col.g, col.b));
    col = mix(col, hueShift(col, uHue), inside);
    col += col * inside * (0.3 * uBassS + 0.5 * uBeatPulse + 0.8 * uFlash) * live;
    // Lichtbögen springen aus dem Kern (Bass), Funken (Höhen)
    for (int k = 0; k < 5; k++) {
        float fk = float(k);
        float an = fk * 1.26 + uSpinT * 0.5 + sin(t * 3.0 + fk) * 0.4;
        float on = step(0.6 - 0.4 * uBassS, hash12(vec2(fk, floor(t * 14.0))));
        vec2 dir = vec2(cos(an), sin(an));
        float along = dot(q, dir), across = abs(dot(q, vec2(-dir.y, dir.x)) + 0.02 * sin(along * 60.0 + t * 30.0));
        float arc = smoothstep(0.006, 0.0, across) * smoothstep(R * 0.9, R * 1.1, along) * smoothstep(R * 2.2, R * 1.3, along);
        col += hueShift(vec3(0.5, 0.9, 1.0), uHue) * arc * on * (0.8 + 0.5 * uBassS) * live;
    }
    for (int k = 0; k < 20; k++) {
        float fk = float(k);
        float h1 = hash12(vec2(fk, 21.0)), h2 = hash12(vec2(fk, 23.0));
        float age = mod(t * (0.5 + h2) + h1 * 4.0, 2.0);
        vec2 sp = vec2(cos(h1 * 6.28), sin(h1 * 6.28)) * (R + age * 0.25) + vec2(0.0, -age * age * 0.1);
        col += vec3(1.0, 0.9, 0.6) * smoothstep(0.004, 0.0, length(q - sp)) * (1.0 - age / 2.0) * (0.3 + 1.2 * uHighS) * live;
    }
    // Beat-Ringe laufen nach außen, Lichter im Foto (helle Punkte) pulsen mit dem Beat-Zähler (Lauflicht links/rechts)
    for (int i = 0; i < 6; i++) {
        float age = ringAt(i);
        if (age > 3.0) continue;
        col += hueShift(vec3(0.4, 0.9, 1.0), uHue) * exp(-pow((r - R - age * 0.35) * 40.0, 2.0)) * exp(-age * 1.5) * 0.6;
    }
    float lights = smoothstep(0.45, 0.8, lum) * (1.0 - inside) * smoothstep(0.35, 0.15, abs(uv.x - 0.5) * -1.0 + 0.35);
    float zone = floor(clamp((uv.y - 0.1) / 0.8, 0.0, 0.999) * 4.0);
    float runL = (zone == mod(uBeatStep, 4.0) ? 1.0 : 0.0) * uBeatPulse;
    col += plate * lights * (0.4 * uBassS + 1.2 * runL) * live;
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
            col += vec3(0.6, 0.9, 1.0) * exp(-pow((r - bt * 0.9) * 12.0, 2.0)) * exp(-bt * 0.8);
            for (int k = 0; k < 30; k++) {
                float fk = float(k);
                float h1 = hash12(vec2(fk, 3.0)), h2 = hash12(vec2(fk, 5.0)), h3 = hash12(vec2(fk, 7.0));
                vec2 dir = vec2(cos(h1 * 6.28), sin(h1 * 6.28));
                vec2 p = dir * (R + bt * (0.3 + 0.6 * h2)) + vec2(0.0, -0.15 * bt * bt);
                vec2 d = rot(bt * (h3 - 0.5) * 8.0) * (q - p) / (0.02 + 0.02 * h3);
                float blk = step(max(abs(d.x), abs(d.y)), 1.0);
                col = mix(col, hueShift(vec3(0.2, 0.9, 1.0), h3 * 4.0) * (0.6 + 0.4 * sin(t * 20.0 + fk)), blk * exp(-bt * 0.5));
            }
        }
    }
    // ---- EMP: weißer Ring, Bild kurz schwarzweiß und ohne Lichter
    if (uEmpT >= 0.0) {
        float e = exp(-uEmpT * 1.2);
        col += vec3(0.9, 0.95, 1.0) * exp(-pow((r - uEmpT * 1.2) * 15.0, 2.0)) * e;
        float gray = dot(col, vec3(0.33));
        col = mix(col, vec3(gray) * 0.6, smoothstep(0.0, 0.2, uEmpT) * e);
        col += (noise(vUv * 200.0 + t * 30.0) - 0.5) * 0.2 * e;
    }
    // ---- Drop: Blitz, Stille: Kern schläft
    col += hueShift(vec3(0.5, 0.9, 1.0), uHue) * uFlash * 0.3 * exp(-r * 2.0);
    col *= 0.7 + 0.3 * live;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
