#version 140
// Zeitsprung: Cockpit der Zeitmaschine (uCockpitTex, Alpha 0 = Windschutzscheibe) vor einer von vier Epochenstraßen
// (uEra0..3Tex, Mischung uEraA/uEraB/uEraMix). Fahrt durch radiale Streckung zum Fluchtpunkt uVanish (uDist/uSpeed),
// Straßenstreifen und Laternen prozedural, Verkehr aus dem Bogen (uMovN: Zelle, x, z, Seed; uMovPN: Art 0 Straße /
// 1 Rand / 2 Flieger, Höhe, Größe, Eigentempo). Bass = Motor/Scheibenwackeln, Beat = helle Stellen blitzen, Höhen =
// Partikel je Epoche. Zeitsprung uJumpT: Blaulicht am Scheibenrand, Feuerspuren, Weißblitz. Hupe uHonkT, Spur uLane,
// Zeitkreise uCircuitT, Ereignisse uEvent (1 Kutsche 2 Lok 3 Mistwagen 4 Tanzball 5 Skater 6 Einkaufszentrum
// 7 Hoverboards 8 Hologramm-Hai 9 Gewitter).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uCockpitTex, uEra0Tex, uEra1Tex, uEra2Tex, uEra3Tex, uTrafficTex;
uniform vec2 uCockpitSize, uEraSize, uTrafficSize, uVanish;
uniform vec4 uShield;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uSpeed, uMph, uDist, uLane, uDriving;
uniform float uHonkT, uCircuitT, uJumpT, uEraA, uEraB, uEraMix, uEvent, uEventT, uEventLen;
uniform vec4 uMov0, uMov1, uMov2, uMov3, uMov4, uMov5, uMov6, uMov7, uMov8, uMov9;
uniform vec4 uMovP0, uMovP1, uMovP2, uMovP3, uMovP4, uMovP5, uMovP6, uMovP7, uMovP8, uMovP9;
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
vec3 eraTex(int e, vec2 uv) {
    vec2 px = clamp(uv, 0.0, 1.0) * uEraSize;
    if (e == 0) return bilin(uEra0Tex, px, uEraSize, vec2(0.0), uEraSize - 1.0).rgb;
    if (e == 1) return bilin(uEra1Tex, px, uEraSize, vec2(0.0), uEraSize - 1.0).rgb;
    if (e == 2) return bilin(uEra2Tex, px, uEraSize, vec2(0.0), uEraSize - 1.0).rgb;
    return bilin(uEra3Tex, px, uEraSize, vec2(0.0), uEraSize - 1.0).rgb;
}
vec4 cockpit(vec2 uv) { return bilin(uCockpitTex, clamp(uv, 0.0, 1.0) * uCockpitSize, uCockpitSize, vec2(0.0), uCockpitSize - 1.0); }
float cockpitA(vec2 uv) { return texture(uCockpitTex, clamp(uv, 0.0, 1.0)).a * step(uv.y, 1.0); }
vec4 trafficCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (3.0 - ri) * 192.0);
    return bilin(uTrafficTex, lo + (d * 0.5 + 0.5) * 192.0, uTrafficSize, lo, lo + 191.0);
}
vec4 movAt(int i) { return i == 0 ? uMov0 : (i == 1 ? uMov1 : (i == 2 ? uMov2 : (i == 3 ? uMov3 : (i == 4 ? uMov4 : (i == 5 ? uMov5 : (i == 6 ? uMov6 : (i == 7 ? uMov7 : (i == 8 ? uMov8 : uMov9)))))))); }
vec4 movPAt(int i) { return i == 0 ? uMovP0 : (i == 1 ? uMovP1 : (i == 2 ? uMovP2 : (i == 3 ? uMovP3 : (i == 4 ? uMovP4 : (i == 5 ? uMovP5 : (i == 6 ? uMovP6 : (i == 7 ? uMovP7 : (i == 8 ? uMovP8 : uMovP9)))))))); }
float depth(float z) { return pow(z, 2.2); }
// Gewicht der Epoche e in der aktuellen Mischung
float eraW(int e) { return (int(uEraA + 0.5) == e ? 1.0 - uEraMix : 0.0) + (int(uEraB + 0.5) == e ? uEraMix : 0.0); }
// Farben je Epoche: Laternen/Streifen (x), Partikel (y)
vec3 lampCol(int e) { return e == 0 ? vec3(1.0, 0.6, 0.25) : (e == 1 ? vec3(1.0, 0.85, 0.55) : (e == 2 ? vec3(1.0, 0.55, 0.15) : vec3(0.3, 0.9, 1.0))); }
vec3 stripeCol(int e) { return e == 0 ? vec3(0.9, 0.7, 0.45) : (e == 1 ? vec3(1.0, 0.85, 0.3) : (e == 2 ? vec3(1.0, 0.8, 0.2) : vec3(0.6, 0.95, 1.0))); }
vec3 mixCol(vec3 a, vec3 b) { return mix(a, b, uEraMix); }

// Fahrt: zwei Zoom-Phasen zum Fluchtpunkt, überblendet (Dreieck), damit das Standbild stetig näher kommt.
// Die Scheibe zeigt nur das obere Bild (uShield.z = Unterkante), darum liegt der Fluchtpunkt der Epoche (uVanish)
// um `shift` höher auf dem Schirm: das Epochenbild wird nach oben verschoben, unten verschwindet es hinter dem Brett.
vec3 eraView(int e, vec2 uv, vec2 van, float shift) {
    float amp = 0.03 + 0.22 * uSpeed;
    float ph = uDist * 1.6;
    float p1 = fract(ph), p2 = fract(ph + 0.5);
    float w1 = 1.0 - abs(2.0 * p1 - 1.0);
    vec2 d = uv - van;
    vec2 off = vec2(0.0, shift);
    vec3 a = eraTex(e, van - off + d / (1.0 + amp * p1));
    vec3 b = eraTex(e, van - off + d / (1.0 + amp * p2));
    return mix(b, a, w1);
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    int ev = int(uEvent + 0.5);
    float ek = clamp(uEventT / max(uEventLen, 0.1), 0.0, 1.0);
    float env = smoothstep(0.0, 0.1, ek) * smoothstep(1.0, 0.9, ek);
    int eA = int(uEraA + 0.5), eB = int(uEraB + 0.5);
    float jump = uJumpT >= 0.0 ? uJumpT : -1.0;
    float jflash = jump >= 0.0 ? exp(-abs(jump - 1.5) * 5.0) : 0.0;                       // Weißblitz in der Mitte
    float jfire = jump >= 0.0 ? smoothstep(0.0, 1.0, jump) * smoothstep(3.0, 2.0, jump) : 0.0;
    float honk = uHonkT >= 0.0 ? exp(-uHonkT * 2.5) : 0.0;
    float storm = ev == 9 ? env : 0.0;
    float w0 = eraW(0), w1 = eraW(1), w2 = eraW(2), w3 = eraW(3);
    float drive = 0.3 + 0.7 * uSpeed;
    // Kamera: Bass vibriert (Motor), Scheibe wackelt stärker als das Armaturenbrett
    vec2 shake = vec2(0.0025 * sin(t * 90.0), 0.003 * cos(t * 71.0)) * uBassS * drive * uLive * uDriving;
    vec2 cuv = vUv + shake * 0.4 + vec2(0.0, uShield.w);                               // Cockpit nach unten geschoben: mehr Scheibe
    vec4 ck = cockpit(cuv);
    float front = ck.a * step(cuv.y, 1.0);                                             // über dem Bildrand ist nur Scheibe
    // ---- Epoche hinter der Scheibe: Spurwechsel kippt, Hupe ruckt, Sprung zieht zum Fluchtpunkt
    vec2 van = vec2(uVanish.x, uShield.z + 0.4 * (1.0 - uShield.z));                  // Fluchtpunkt auf dem Schirm
    float eshift = van.y - uVanish.y;
    vec2 uv = vUv + shake * 1.6 + vec2(0.0, 0.004 * sin(t * 13.0) * uBassS * uDriving);
    uv = van + rot(0.05 * uLane) * (uv - van);
    uv.x += 0.04 * uLane;
    uv = van + (uv - van) * (1.0 - 0.12 * jfire - 0.03 * honk);
    vec3 col = eraView(eA, uv, van, eshift);
    if (uEraMix > 0.001) col = mix(col, eraView(eB, uv, van, eshift), uEraMix);
    vec3 plate = col;
    float lum = max(col.r, max(col.g, col.b));
    float sat = lum - min(col.r, min(col.g, col.b));
    float neon = smoothstep(0.45, 0.8, lum) * smoothstep(0.15, 0.45, sat);
    // ---- Straße: Streifen und Fahrbahn laufen mit uDist auf die Kamera zu
    vec2 q = uv - van;
    float road = smoothstep(0.0, -0.03, q.y) * smoothstep(-0.45, -0.2, q.y);
    float invz = 1.0 / max(-q.y, 0.004);
    float lanesX = q.x * invz;
    float along = invz * 0.12 - uDist * 6.0;
    vec3 sCol = mixCol(stripeCol(eA), stripeCol(eB));
    float center = smoothstep(0.3, 0.0, abs(fract(along * 0.5) - 0.5) - 0.15) * smoothstep(0.06, 0.0, abs(lanesX));
    float edge = smoothstep(0.35, 0.0, abs(fract(along) - 0.5) - 0.2) * smoothstep(0.1, 0.0, abs(abs(lanesX) - 1.35));
    float ruts = smoothstep(0.08, 0.0, abs(abs(lanesX) - 0.45)) * (0.5 + 0.5 * noise(vec2(lanesX * 4.0, along * 2.0)));
    float streak = (center * 0.5 + edge * 0.35) * (1.0 - w0) + ruts * 0.25 * w0;
    col += sCol * streak * road * uSpeed * (0.4 + 0.6 * uLive) * uDriving;
    float refl = noise(vec2(lanesX * 2.0, along * 0.7)) * road * uSpeed * 0.2 * (1.0 - 0.6 * w0);
    col += plate * refl * 2.0;
    // ---- Laternen ziehen vorbei: Lichtköpfe auf zwei Linien über dem Horizont, je Epoche gefärbt
    if (q.y > 0.0) {
        float D = 1.2 / max(q.y, 0.004);
        float lampAlong = D * 0.12 - uDist * 6.0;
        float lx = q.x * D;
        float near = smoothstep(0.9, 0.0, abs(abs(lx) - 1.9)) * smoothstep(0.5, 0.0, abs(fract(lampAlong * 0.5) - 0.5));
        float sizeK = clamp(1.0 / D, 0.0, 1.0);
        vec3 lc = mixCol(lampCol(eA), lampCol(eB));
        float lamp = near * sizeK * uSpeed * uDriving * (0.4 + 0.5 * uBeatPulse) * smoothstep(0.0, 0.03, q.y);
        col += lc * lamp * 1.4 * (1.0 - 0.7 * w0);
    }
    // ---- Beat: helle, gesättigte Stellen (Schilder, Neon, Laternen) blitzen, Bass pulst sie
    float flashMask = step(0.5, hash12(vec2(floor(uv.x * 14.0), floor(uv.y * 8.0) + uBeatStep)));
    float beatK = 1.0 - 0.6 * w0;                                                         // Sonnenuntergang 1885 nur sanft
    col += col * neon * (0.35 * uBassS + 0.8 * uBeatPulse * flashMask * beatK + 1.2 * honk) * uLive;
    col += col * neon * 0.12 * (1.0 - uLive) * (0.5 + 0.5 * sin(t * 1.3 + uv.x * 5.0));
    // ---- Ereignisse mit eigenem Licht
    if (ev == 4) {                                                                        // Tanzball: Girlanden mit bunten Birnen
        for (int k = 0; k < 2; k++) {
            float gy = 0.86 - 0.1 * float(k) + 0.04 * sin(uv.x * 9.0 + float(k) * 2.0) - 0.02 * smoothstep(0.0, 1.0, abs(uv.x - 0.5));
            vec2 g = vec2(uv.x * 22.0 + float(k) * 0.5, (uv.y - gy) * 22.0 * aspect * 0.6);
            vec2 gi = vec2(floor(g.x), float(k)), gf = vec2(fract(g.x) - 0.5, g.y);          // eine Reihe je Girlande
            float bulb = smoothstep(0.32, 0.05, length(gf));
            vec3 bc = hueShift(vec3(1.0, 0.3, 0.2), hash12(gi + float(k)) * 6.28);
            float on = 0.6 + 0.4 * step(0.4, fract(hash12(gi) * 7.0 + t * 1.5 + uBeatStep * 0.25));
            col += bc * bulb * on * env * (0.8 + 0.6 * uBeatPulse);
            col += bc * smoothstep(0.9, 0.0, length(gf)) * 0.12 * env;
        }
        col = mix(col, col * vec3(0.7, 0.85, 1.2), env * 0.25);
    } else if (ev == 6) {                                                                 // Einkaufszentrum: Neon in wechselnden Farben
        vec3 nc = hueShift(vec3(1.0, 0.3, 0.7), uv.x * 6.0 + t * 1.5 + uBeatStep);
        col += nc * neon * env * (0.8 + 0.5 * uBeatPulse);
        col += nc * smoothstep(0.08, 0.0, abs(uv.y - 0.5 - 0.02 * sin(uv.x * 30.0 + t * 3.0))) * env * 0.15;
    }
    // ---- Verkehr aus dem Bogen (fern zuerst): Straße, Straßenrand, Flieger
    for (int i = 0; i < 10; i++) {
        vec4 m = movAt(i);
        if (m.z < 0.0) continue;
        vec4 p = movPAt(i);
        int kind = int(p.x + 0.5);
        float d = depth(m.z);
        vec2 pos;
        float sz;
        if (kind == 0) {
            float hx = honk * sign(m.y - uLane + 0.001) * 0.5 * (0.03 + 0.55 * d);
            pos = van + vec2((m.y - uLane * 0.6) * (0.03 + 0.55 * d) + hx, -0.01 - 0.32 * d);
            sz = (0.015 + 0.5 * d) * aspect * 0.5 * p.z;
        } else if (kind == 1) {
            pos = van + vec2(m.y * (0.1 + 1.0 * d), -0.005 - 0.3 * d);
            sz = (0.02 + 0.6 * d) * aspect * 0.5 * p.z;
        } else {
            pos = van + vec2(m.y * (0.05 + 1.1 * d), 0.02 + 0.55 * d * (0.3 + 0.9 * p.y) + 0.015 * sin(t * 2.0 + m.w * 8.0) * d);
            pos.y += 0.35 * honk * d * w3;                                                   // Hupe 2015: alles steigt
            sz = (0.012 + 0.35 * d) * aspect * 0.5 * p.z;
        }
        vec2 l = (uv - pos) * vec2(aspect, 1.0) / sz;
        if (kind != 2) l.y -= 0.9; else l.y -= 0.3;
        if (m.x == 5.0) l = rot(uDist * 25.0 + m.w) * l;                                       // Steppenläufer rollt
        if (m.y < 0.0 && kind == 1) l.x = -l.x;                                                // linker Rand: gespiegelt
        vec4 s = trafficCell(m.x, l);
        float a = smoothstep(0.02, 0.1, max(max(s.r, s.g), s.b)) * s.a;                       // Schwarz = frei
        if (m.x < 8.0) s.rgb *= 0.85 + 0.3 * uBassS; else s.rgb *= 0.9 + 0.3 * uBassS;
        if (m.x == 14.0 || m.x == 28.0) s.rgb += (vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 4.0)) + vec3(0.1, 0.2, 1.0) * step(0.5, fract(t * 4.0 + 0.5))) * 0.4;
        if (m.x >= 24.0) s.rgb += vec3(0.2, 0.6, 1.0) * smoothstep(0.3, 0.0, l.y + 0.9) * 0.4 * (0.5 + 0.5 * uBeatPulse);   // Schweben: blaues Glühen unten
        float fade = smoothstep(0.0, 0.05, m.z) * (1.0 - smoothstep(0.92, 1.0, m.z));
        col = mix(col, s.rgb, a * fade);
        col += s.rgb * a * 0.25 * uBeatPulse * fade;
    }
    // ---- Hologramm-Hai: groß am Himmel, wächst, schnappt auf den Beat, stürzt sich am Ende auf die Scheibe
    if (ev == 8) {
        float lunge = smoothstep(0.82, 1.0, ek);
        vec2 sp = vec2(0.5 + 0.18 * sin(ek * 5.0), 0.68 - 0.1 * sin(ek * 3.0) - 0.25 * lunge);
        float ssz = (0.12 + 0.35 * smoothstep(0.0, 0.5, ek)) * (1.0 + 0.15 * uBeatPulse) * (1.0 + 3.0 * lunge);
        vec2 l = (uv - sp) * vec2(aspect, 1.0) / ssz;
        l.y -= 0.0;
        vec4 s = trafficCell(31.0, l);
        float a = smoothstep(0.03, 0.15, max(max(s.r, s.g), s.b)) * env;
        float flick = 0.75 + 0.25 * step(0.35, noise(vec2(t * 15.0, 3.0)));
        float scan = 0.8 + 0.2 * sin(uv.y * 300.0 + t * 20.0);
        col += s.rgb * a * flick * scan * 1.1 * (0.8 + 0.6 * uBeatPulse);
    }
    // ---- Partikel je Epoche (Höhen): Staub 1885, Sterne 1955, Regen 1985, Hologrammfunken 2015
    float hi = 0.4 + 0.6 * uHighS;
    if (w0 > 0.001) {
        float dust = smoothstep(0.8, 1.0, noise(vUv * vec2(70.0, 45.0) + vec2(-t * (1.0 + 4.0 * uSpeed), t * 0.4)));
        dust += smoothstep(0.75, 1.0, noise(vec2(lanesX * 3.0, along * 2.5))) * road * uSpeed;
        col += vec3(0.8, 0.6, 0.4) * dust * hi * 0.35 * w0 * smoothstep(0.7, 0.3, vUv.y);
    }
    if (w1 > 0.001) {
        vec2 g = vUv * vec2(90.0, 50.0);
        float star = smoothstep(0.985, 1.0, hash12(floor(g))) * smoothstep(0.5, 0.0, length(fract(g) - 0.5));
        float tw = 0.5 + 0.5 * sin(t * 6.0 + hash12(floor(g) + 1.0) * 20.0);
        col += vec3(1.0, 0.95, 0.75) * star * tw * hi * 1.4 * w1 * smoothstep(0.45, 0.65, vUv.y);
    }
    float rainK = w2 * 0.8 + storm;
    if (rainK > 0.001) {
        float slant = 0.3 + 0.9 * uSpeed;
        vec2 rp = vec2(vUv.x * 40.0 + vUv.y * slant * 20.0, vUv.y * 60.0 + t * (3.0 + 12.0 * uSpeed));
        float drops = smoothstep(0.93 - 0.05 * storm, 1.0, noise(rp)) * (0.5 + 0.5 * uHighS);
        float drops2 = smoothstep(0.96, 1.0, noise(vUv * 120.0 + vec2(0.0, -t * 0.3)));
        col += vec3(0.7, 0.85, 1.0) * (drops * 0.5 + drops2 * 0.3 * (0.5 + uHighS)) * rainK;
        col += plate * drops2 * 0.5 * rainK;
    }
    if (w3 > 0.001) {
        vec2 g = vUv * vec2(220.0, 124.0);
        float sp = step(0.975, hash12(floor(g) + floor(t * 12.0))) * smoothstep(0.45, 0.15, length(fract(g) - 0.5));
        vec3 hc = mix(vec3(0.2, 0.9, 1.0), vec3(1.0, 0.3, 0.9), hash12(floor(g) + 7.0));
        col += hc * sp * hi * 1.0 * w3;
        col += hc * smoothstep(0.1, 0.0, abs(fract(vUv.y * 40.0 + t * 2.0) - 0.5) - 0.45) * 0.03 * w3;
    }
    // ---- Mistwagen: braune Spritzer auf der Scheibe, wenn er vorne ist
    if (ev == 3 && ek > 0.5) {
        float sk = smoothstep(0.5, 0.6, ek) * smoothstep(1.0, 0.85, ek);
        float spl = smoothstep(0.55, 0.9, fbm(vUv * vec2(9.0, 6.0) + uSeed));
        col = mix(col, vec3(0.25, 0.15, 0.06) * (0.6 + 0.4 * spl), spl * sk * 0.9);
    }
    // ---- Gewitter: dunkler, Blitze erhellen den Himmel
    if (storm > 0.0) {
        float bolt = step(0.93, hash12(vec2(floor(t * 9.0), 2.0))) * (0.6 + 0.4 * hash12(vec2(floor(t * 9.0), 5.0)));
        col = mix(col, col * vec3(0.45, 0.5, 0.65), storm * 0.6);
        col += vec3(0.8, 0.85, 1.0) * bolt * storm * (0.3 + 0.7 * smoothstep(0.4, 0.9, vUv.y));
        float branch = smoothstep(0.03, 0.0, abs(vUv.x - 0.5 - 0.3 * sin(t * 3.0) - 0.08 * sin(vUv.y * 40.0 + t * 50.0))) * bolt * smoothstep(0.4, 0.8, vUv.y);
        col += vec3(0.7, 0.8, 1.0) * branch * storm * 0.8;
    }
    // ---- Zeitsprung: Feuerspuren auf der Straße zum Fluchtpunkt, Blaulicht am Scheibenrand, Weißblitz
    if (jump >= 0.0) {
        float trail = smoothstep(0.13, 0.0, abs(abs(lanesX) - 0.42)) * road;
        float fire = fbm(vec2(lanesX * 6.0, along * 3.0 - t * 9.0)) * (0.7 + 0.5 * uBeatPulse + 0.3 * sin(t * 40.0));
        float jt2 = jump > 2.0 ? 0.35 * (3.0 - jump) : 1.0;
        col += mix(vec3(1.0, 0.35, 0.05), vec3(1.0, 0.9, 0.4), fire) * trail * fire * 3.2 * jfire * jt2;
        col += vec3(1.0, 0.5, 0.1) * smoothstep(0.25, 0.0, abs(abs(lanesX) - 0.42)) * road * 0.3 * jfire;
        // Blaulicht: Band innen am Rand der Scheibe (Cockpit-Alpha erweitert), Blitze aus Rauschen
        vec2 px = vec2(0.007, 0.007 * aspect);                                            // Bandbreite in Bildanteilen
        float dil = max(max(cockpitA(cuv + vec2(px.x, 0.0)), cockpitA(cuv - vec2(px.x, 0.0))), max(cockpitA(cuv + vec2(0.0, px.y)), cockpitA(cuv - vec2(0.0, px.y))));
        vec2 px2 = px * 2.5;
        float dil2 = max(max(cockpitA(cuv + vec2(px2.x, 0.0)), cockpitA(cuv - vec2(px2.x, 0.0))), max(cockpitA(cuv + vec2(0.0, px2.y)), cockpitA(cuv - vec2(0.0, px2.y))));
        float rim = max(dil, 0.5 * dil2) * (1.0 - front);
        float bolt = step(0.55, noise(vUv * vec2(40.0, 25.0) + t * 60.0)) * step(0.3, noise(vUv * 6.0 - t * 20.0));
        float strobe = 0.6 + 0.4 * step(0.5, fract(t * 14.0));
        float jb = smoothstep(0.0, 0.3, jump) * smoothstep(3.0, 2.3, jump);
        col += vec3(0.4, 0.7, 1.0) * rim * (0.5 + 1.5 * bolt) * strobe * jb * 1.6;
        // Strahlen aus dem Fluchtpunkt
        float a = atan(uv.y - van.y, (uv.x - van.x) * aspect);
        float r = length((uv - van) * vec2(aspect, 1.0));
        float rays = pow(0.5 + 0.5 * sin(a * 30.0 + t * 25.0), 8.0) * smoothstep(0.05, 0.5, r);
        col += vec3(0.7, 0.85, 1.0) * rays * jfire * 0.35;
        col = mix(col, vec3(1.0), jflash);
    }
    // ---- Scheibe: leichter Schein und Stillstand; dann das Cockpit davor
    col *= 0.78 + 0.22 * uLive;
    col = mix(col * 0.75, col, 0.5 + 0.5 * uDriving);
    vec3 dash = ck.rgb;
    float dlum = max(dash.r, max(dash.g, dash.b));
    float dsat = dlum - min(dash.r, min(dash.g, dash.b));
    float lights = smoothstep(0.35, 0.7, dlum) * smoothstep(0.1, 0.4, dsat);                  // Anzeigen, Röhren, LEDs
    dash += dash * lights * (0.3 * uBassS + 0.5 * uBeatPulse * step(0.5, hash12(vec2(floor(cuv.x * 20.0), uBeatStep)))) * uLive;
    dash *= 1.0 + 0.15 * uDriving * uSpeed;                                                  // Fahrt: Armaturen leuchten
    dash += dash * vec3(0.5, 0.8, 1.2) * jflash * 2.5;                                        // Weißblitz spiegelt sich
    dash += vec3(0.3, 0.6, 1.0) * (jump >= 0.0 ? smoothstep(0.0, 0.3, jump) * smoothstep(3.0, 2.3, jump) : 0.0) * 0.12 * (0.5 + 0.5 * step(0.5, fract(t * 14.0)));
    if (uCircuitT >= 0.0) {                                                                   // Zeitkreise rattern: Kasten flackert
        vec2 bx = (cuv - vec2(0.80, 0.49)) / vec2(0.13, 0.15);
        float box = smoothstep(1.0, 0.7, max(abs(bx.x), abs(bx.y)));
        dash += vec3(1.0, 0.6, 0.2) * box * 0.25 * step(0.5, fract(t * 20.0)) * exp(-uCircuitT * 2.0);
    }
    dash += vec3(1.0, 0.7, 0.3) * lights * honk * 0.4;
    col = mix(col, dash, front);
    col *= 1.0 - 0.2 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.12);
    fragColor = vec4(col, 1.0);
}
