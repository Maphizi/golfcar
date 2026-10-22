#version 140
// Marktplatz: derselbe Platz mit Rathaus und Uhrturm in vier Epochen (uEra0Tex 1885, uEra1Tex 1955, uEra2Tex 1985,
// uEra3Tex 2015). Gezeigt wird Epoche uEraA, beim Zeitsprung (uJumpT 0..3 s, Richtung uJumpDir) laufen zwei Feuerspuren
// über den Platz, ein Weißblitz deckt den Wechsel nach uEraB (uEraMix nur kurz in der Mitte des Blitzes). Fenster und
// Schilder (helle Stellen oberhalb uGround) leuchten mit dem Bass, der Boden bebt; Beats laufen als Lichtwelle vom Uhrturm
// (uClock) horizontal durch die Häuserzeile (uPulseA/B), Mitten = Verkehrs-/Passantenlichter am Boden (uTrafficT), Höhen
// je Epoche: Staub, Regen, Neon-Flackern, Hologramm-Funken. Drop uFlash + uHue, Feuerwerk uFireT/uFireSeed (1885 Kanonen,
// 2015 Drohnenshow, sonst bunt), Stromausfall uBlackT/uBlackBeats, Blitz in den Turm uLightT/uLightSeed, Nahaufnahme uZoom.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uEra0Tex, uEra1Tex, uEra2Tex, uEra3Tex, uPartTex;
uniform vec2 uEra0Size, uEra1Size, uEra2Size, uEra3Size, uPartSize, uClock;
uniform float uSeed, uGround, uEra, uEraA, uEraB, uEraMix, uJumpT, uJumpDir, uBassS, uMidS, uHighS, uEnergy, uLive;
uniform float uBeatPulse, uBeatStep, uFlash, uHue, uFireT, uFireSeed, uBlackT, uBlackBeats, uLightT, uLightSeed, uTrafficT, uZoom;
uniform vec3 uPulseA, uPulseB;
const float PI = 3.14159265;
const float JUMP_SWITCH = 1.1;      // Sekunde im Sprung, in der die Epoche wechselt (wie im Controller)
const float JUMP_LEN = 3.0;

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
    uv = clamp(uv, 0.0, 1.0);
    if (e == 0) return bilin(uEra0Tex, uv * uEra0Size, uEra0Size, vec2(0.0), uEra0Size - 1.0).rgb;
    if (e == 1) return bilin(uEra1Tex, uv * uEra1Size, uEra1Size, vec2(0.0), uEra1Size - 1.0).rgb;
    if (e == 2) return bilin(uEra2Tex, uv * uEra2Size, uEra2Size, vec2(0.0), uEra2Size - 1.0).rgb;
    return bilin(uEra3Tex, uv * uEra3Size, uEra3Size, vec2(0.0), uEra3Size - 1.0).rgb;
}
vec3 scene(vec2 uv) {
    vec3 a = eraTex(int(uEraA + 0.5), uv);
    if (uEraMix <= 0.001) return a;
    return mix(a, eraTex(int(uEraB + 0.5), uv), uEraMix);
}
vec4 part(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 160.0, (2.0 - ri) * 160.0);
    return bilin(uPartTex, lo + (d * 0.5 + 0.5) * 160.0, uPartSize, lo, lo + 159.0);
}
float pulseAge(int i) { return i < 3 ? uPulseA[i] : uPulseB[i - 3]; }
// Gewicht der Epoche s (0..3): vor dem Wechsel uEraA, in der Mitte des Blitzes Überblendung nach uEraB
float eraW(float s) { return mix(step(abs(uEraA - s), 0.5), step(abs(uEraB - s), 0.5), uEraMix); }
// Abstand Punkt - Strecke (für Blitzäste)
float segDist(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    float w0 = eraW(0.0), w1 = eraW(1.0), w2 = eraW(2.0), w3 = eraW(3.0);
    float jumpOn = uJumpT >= 0.0 ? 1.0 : 0.0;
    float preJump = jumpOn * smoothstep(0.0, JUMP_SWITCH, uJumpT) * (1.0 - step(JUMP_SWITCH, uJumpT));   // Anlauf bis zum Wechsel
    float postJump = jumpOn * step(JUMP_SWITCH, uJumpT);
    // ---- Kamera: Nahaufnahme auf das Zifferblatt, Bass lässt den Boden beben, Zeitsprung rüttelt
    vec2 uv = mix(vUv, uClock + (vUv - uClock) / 4.0, uZoom);
    float groundMask = 1.0 - smoothstep(uGround - 0.02, uGround + 0.06, vUv.y);
    uv.y += 0.003 * uBassS * live * sin(t * 37.0) * (0.4 + 0.6 * groundMask) * (1.0 - 0.7 * uZoom);
    uv += 0.006 * preJump * preJump * vec2(sin(t * 53.0 + uSeed), cos(t * 47.0));
    uv += vec2(0.0008 * sin(t * 0.3), 0.0008 * cos(t * 0.21));
    vec3 plate = scene(uv);
    vec3 col = plate;
    float lum = max(plate.r, max(plate.g, plate.b));
    float sat = lum - min(plate.r, min(plate.g, plate.b));
    float ground = 1.0 - smoothstep(uGround - 0.03, uGround + 0.03, uv.y);
    float town = 1.0 - ground;
    float windows = smoothstep(0.35, 0.7, lum) * town;                                   // alle Lichter der Häuserzeile
    float signs = smoothstep(0.45, 0.75, lum) * smoothstep(0.2, 0.45, sat) * town;       // bunte Schilder, Leuchtreklamen, Hologramme
    float lanterns = smoothstep(0.8, 0.97, lum) * smoothstep(0.0, 0.25, plate.r - plate.b);   // warme, sehr helle Punkte
    float reflect = smoothstep(0.3, 0.65, lum) * ground;                                 // Spiegelungen auf dem Pflaster
    // ---- Farbstimmung je Epoche (Sepia/Öllampen, Pastell-Diner, Natriumdampf/Videothek, Hologramm-Blau)
    float grey = dot(plate, vec3(0.3, 0.59, 0.11));
    col = mix(col, grey * vec3(1.0, 0.8, 0.55) * 0.9, w0 * 0.6);
    col = mix(col, pow(col, vec3(0.92)) * vec3(0.95, 1.0, 1.06), w1 * 0.5);
    col = mix(col, col * vec3(1.15, 0.92, 0.78) + signs * vec3(0.35, 0.0, 0.3), w2 * 0.55);
    col = mix(col, col * vec3(0.9, 0.96, 1.12), w3 * 0.4);
    // ---- Stromausfall: Blöcke des Platzes gehen aus, kommen mit den Beats zurück
    float black = 0.0;
    if (uBlackT >= 0.0) {
        vec2 blk = floor(uv * vec2(9.0, 5.0));
        float h = hash12(blk + uSeed);
        float off = smoothstep(0.0, 1.2, uBlackT - h * 1.0);
        float back = smoothstep(h * 14.0 - 1.0, h * 14.0 + 1.0, uBlackBeats) * smoothstep(0.0, 1.0, uBlackT - 3.0);
        black = off * (1.0 - back);
        float soft = smoothstep(0.0, 0.12, min(fract(uv.x * 9.0), 1.0 - fract(uv.x * 9.0))) * smoothstep(0.0, 0.12, min(fract(uv.y * 5.0), 1.0 - fract(uv.y * 5.0)));
        black *= 0.6 + 0.4 * soft;
        col = mix(col, col * 0.1 + plate * lanterns * 0.12, black);
    }
    // ---- Beat-Lichtwellen laufen vom Uhrturm aus nach beiden Seiten durch die Häuserzeile
    float wave = 0.0;
    for (int i = 0; i < 6; i++) {
        float age = pulseAge(i);
        if (age > 3.0) continue;
        float front = age * 0.42;
        float d = abs(uv.x - uClock.x) * aspect;
        wave += exp(-pow((d - front) * 18.0, 2.0)) * exp(-age * 1.1);
    }
    vec3 lightCol = hueShift(plate / max(lum, 0.2), uHue);
    lightCol = mix(lightCol, vec3(1.0, 0.7, 0.35), w0 * 0.7);                                  // 1885: Öllampen und Kerzen
    float lampFlicker = 1.0 + w0 * 0.25 * (noise(vec2(t * 7.0, floor(uv.x * 30.0))) - 0.5);
    col += lightCol * windows * (0.3 * uBassS + 0.9 * wave + 0.2 * uBeatPulse) * lampFlicker * live * (1.0 - black);
    col += lightCol * reflect * (0.2 * uBassS + 0.45 * wave) * live * (1.0 - black);
    col = mix(col, hueShift(col, uHue), signs * min(1.0, abs(uHue)));
    col += lightCol * signs * (0.15 + 0.5 * uFlash) * live;
    // Stille: die Stadt schläft, nur die Laternen bleiben
    col = mix(col, col * 0.5, (windows + reflect) * (1.0 - live) * 0.6);
    col += plate * lanterns * (1.0 - live) * 0.35;
    // ---- Verkehr und Passanten: wandernde Lichtpunkte auf dem Platz (Mitten), mit Spiegelstreifen
    {
        vec3 c1 = mix(mix(vec3(1.0, 0.75, 0.35), vec3(1.0, 0.95, 0.85), w1 + w2), vec3(0.4, 0.8, 1.0), w3);
        vec3 c2 = mix(mix(vec3(1.0, 0.55, 0.2), vec3(1.0, 0.25, 0.15), w1 + w2), vec3(0.7, 0.4, 1.0), w3);
        float era = uEra;
        for (int k = 0; k < 12; k++) {
            float fk = float(k);
            float h1 = hash12(vec2(fk, 41.0)), h2 = hash12(vec2(fk, 43.0)), h3 = hash12(vec2(fk, 47.0 + floor(era)));
            float depth = h1;                                                            // 0 = fern (oben am Platz), 1 = nah
            float y = uGround * (0.95 - 0.8 * depth);
            float x = fract(uTrafficT * (0.04 + 0.12 * depth) * (0.6 + 0.8 * h3) + h2 * 5.0) * 1.3 - 0.15;
            if (h2 > 0.5) x = 1.15 - x;
            float sz = 0.006 + 0.016 * depth;
            vec2 d = (uv - vec2(x, y)) * vec2(aspect, 1.0);
            float dot1 = smoothstep(sz, 0.0, length(d)) + 0.5 * exp(-length(d) * 90.0);
            float streak = smoothstep(sz * 0.6, 0.0, abs(d.x)) * smoothstep(0.0, -sz * 6.0, d.y) * smoothstep(-sz * 6.0, 0.0, d.y);
            col += mix(c1, c2, h3) * (dot1 * 1.6 + 0.5 * streak) * (0.3 + 0.9 * uMidS) * live * (1.0 - black) * ground;
        }
    }
    // ---- Höhen je Epoche: Staub (1885), Regen (1955), Neon-Flackern (1985), Hologramm-Funken (2015)
    if (w0 > 0.01) {
        float dust = fbm(vec2(uv.x * 3.0 + t * 0.12, uv.y * 7.0 + uSeed)) * (1.0 - smoothstep(0.2, 0.6, uv.y));
        col = mix(col, vec3(0.75, 0.6, 0.4) * (0.5 + 0.4 * uBassS * live), smoothstep(0.35, 0.8, dust) * w0 * (0.2 + 0.5 * uHighS) * (1.0 - black));
    }
    if (w1 > 0.01) {
        vec2 rp = vec2(uv.x * 60.0 + uv.y * 6.0, uv.y * 40.0 + t * 9.0);
        float streak = smoothstep(0.88, 1.0, noise(rp)) * w1;
        col += vec3(0.7, 0.85, 1.0) * streak * (0.15 + 0.35 * uHighS) * (0.6 + 0.4 * live);
        col += vec3(0.6, 0.9, 1.0) * reflect * w1 * 0.25 * uHighS * (0.5 + 0.5 * noise(uv * vec2(120.0, 30.0) + t * 3.0));
    }
    if (w2 > 0.01) {
        float cell = floor(uv.x * 14.0) + 7.0 * floor(uv.y * 8.0);
        float flick = step(0.85 - 0.3 * uHighS, hash12(vec2(cell, floor(t * 18.0))));
        float buzz = 0.5 + 0.5 * sin(t * 120.0 + cell);
        col += signs * flick * buzz * vec3(1.0, 0.4, 0.9) * (0.4 + 0.9 * uHighS) * w2 * live * (1.0 - black);
        col = mix(col, col * 0.4, signs * step(0.96, hash12(vec2(cell + 3.0, floor(t * 6.0)))) * w2 * 0.8);
    }
    if (w3 > 0.01) {
        vec2 g = floor(uv * vec2(180.0, 100.0));
        float spark = step(0.985 - 0.012 * uHighS, hash12(g + floor(t * 14.0) * 0.37 + uSeed));
        col += mix(vec3(0.4, 0.8, 1.0), vec3(0.8, 0.5, 1.0), hash12(g + 9.0)) * spark * smoothstep(0.15, 0.45, sat) * (0.5 + 2.0 * uHighS) * w3 * live * (1.0 - black);
        float scan = smoothstep(0.96, 1.0, sin(uv.y * 400.0 - t * 30.0));
        col += vec3(0.3, 0.6, 1.0) * scan * signs * 0.15 * uHighS * w3;
    }
    // ---- Blitz in den Uhrturm: verästelte Linie von oben auf uClock, Himmel wird weiß, Zifferblatt glüht
    if (uLightT >= 0.0) {
        float e = exp(-uLightT * 4.5) * (0.6 + 0.4 * step(0.5, fract(uLightT * 30.0)));
        float dy = uv.y - uClock.y;
        float bx = uClock.x + dy * (0.22 * sin(uv.y * 11.0 + uLightSeed) + 0.1 * sin(uv.y * 43.0 + uLightSeed * 3.0) + 0.03 * sin(uv.y * 160.0 + uLightSeed * 7.0));
        float bolt = smoothstep(0.0045, 0.0, abs(uv.x - bx) * aspect) * step(0.0, dy);
        float glow = exp(-abs(uv.x - bx) * aspect * 25.0) * step(0.0, dy) * 0.35;
        vec2 p = uv * vec2(aspect, 1.0);
        for (int k = 0; k < 4; k++) {
            float fk = float(k);
            float by = uClock.y + 0.08 + fk * 0.1 + 0.05 * hash12(vec2(fk, uLightSeed));
            float bxx = uClock.x + (by - uClock.y) * (0.22 * sin(by * 11.0 + uLightSeed) + 0.1 * sin(by * 43.0 + uLightSeed * 3.0) + 0.03 * sin(by * 160.0 + uLightSeed * 7.0));
            vec2 a = vec2(bxx, by) * vec2(aspect, 1.0);
            vec2 dir = normalize(vec2((hash12(vec2(fk, uLightSeed + 2.0)) > 0.5 ? 1.0 : -1.0) * (0.3 + 0.5 * hash12(vec2(fk, uLightSeed + 3.0))), 0.6));
            vec2 b = a + dir * (0.08 + 0.1 * hash12(vec2(fk, uLightSeed + 4.0)));
            float dseg = segDist(p + 0.004 * vec2(sin(p.y * 90.0 + fk), 0.0), a, b);
            bolt += smoothstep(0.003, 0.0, dseg) * 0.8 * step(float(k) + 0.5, 1.5 + 3.0 * fract(uLightSeed * 3.1));
        }
        col += vec3(0.8, 0.85, 1.0) * e * smoothstep(0.45, 1.0, uv.y) * 0.4;
        col += vec3(0.9, 0.95, 1.0) * (bolt * 4.0 + glow) * e;
        float cd = length((uv - uClock) * vec2(aspect, 1.0));
        col += vec3(1.0, 0.95, 0.8) * (exp(-cd * 45.0) * e * 2.0 + exp(-cd * 30.0) * exp(-uLightT * 1.2) * 0.7);
        col += vec3(0.5, 0.6, 1.0) * e * 0.15;
    }
    // ---- Feuerwerk: 1885 Kanonenblitze am Boden, 2015 Drohnenshow in Blau/Violett, sonst bunte Raketen
    if (uFireT >= 0.0) {
        float cannon = w0, drones = w3, bunt = max(0.0, 1.0 - cannon - drones);
        if (cannon > 0.01) {
            for (int k = 0; k < 8; k++) {
                float fk = float(k);
                float h1 = hash12(vec2(fk, uFireSeed)), h2 = hash12(vec2(fk, uFireSeed + 1.0));
                float t0 = fk * 0.85 + h1 * 0.5;
                float age = uFireT - t0;
                if (age < 0.0 || age > 3.0) continue;
                vec2 c = vec2(h2 < 0.5 ? 0.08 + h1 * 0.25 : 0.67 + h1 * 0.25, uGround * (0.35 + 0.4 * h1));
                vec2 d = (uv - c) * vec2(aspect, 1.0);
                float r = length(d);
                float burst = exp(-r * 12.0) * exp(-age * 3.5) * 3.0 * (0.7 + 0.3 * sin(age * 40.0 + fk)) + exp(-r * 3.5) * exp(-age * 5.0) * 0.9;
                vec2 sp = d + vec2(h2 < 0.5 ? -1.0 : 1.0, 0.0) * age * 0.15;
                float smoke = fbm(sp * 8.0 + vec2(fk, t * 0.5)) * exp(-length(sp) * 5.0 + age * 0.3) * smoothstep(0.0, 0.5, age) * (1.0 - age / 3.0);
                col += vec3(1.0, 0.55, 0.15) * burst * cannon;
                col = mix(col, vec3(0.55, 0.5, 0.45), smoothstep(0.2, 0.7, smoke) * 0.6 * cannon);
                col += vec3(1.0, 0.6, 0.2) * exp(-age * 6.0) * 0.3 * cannon * (0.5 + 0.5 * ground);
            }
        }
        if (drones > 0.01) {
            float phase = floor(uFireT / 2.0);
            float ph = smoothstep(0.0, 0.6, fract(uFireT / 2.0));
            vec2 center = vec2(uClock.x, 0.74);
            for (int k = 0; k < 24; k++) {
                float a = float(k) / 24.0 * 2.0 * PI;
                vec2 form0 = vec2(cos(a), sin(a)) * 0.2;                                               // Ring
                vec2 form1 = vec2(sin(a) * 0.26, sin(2.0 * a) * 0.13);                                 // Acht
                vec2 form2 = vec2(mod(float(k), 6.0) / 5.0 - 0.5, floor(float(k) / 6.0) / 3.0 - 0.5) * vec2(0.5, 0.3);   // Raster
                vec2 form3 = vec2(cos(a) * (0.12 + 0.1 * cos(3.0 * a)), sin(a) * (0.12 + 0.1 * cos(3.0 * a)));         // Blüte
                float m = mod(phase + fract(uFireSeed) * 4.0, 4.0);
                vec2 from = m < 1.0 ? form0 : (m < 2.0 ? form1 : (m < 3.0 ? form2 : form3));
                vec2 to = m < 1.0 ? form1 : (m < 2.0 ? form2 : (m < 3.0 ? form3 : form0));
                vec2 pos = center + mix(from, to, ph) * vec2(1.0 / aspect, 1.0) + 0.004 * vec2(sin(t * 3.0 + a * 5.0), cos(t * 2.7 + a * 3.0));
                vec2 d = (uv - pos) * vec2(aspect, 1.0);
                float r = length(d);
                vec3 dc = mix(vec3(0.3, 0.7, 1.0), vec3(0.8, 0.4, 1.0), 0.5 + 0.5 * sin(a * 3.0 + uFireT));
                col += dc * (smoothstep(0.007, 0.0, r) * 1.5 + exp(-r * 60.0) * 0.6) * drones * smoothstep(0.0, 1.0, uFireT) * smoothstep(8.0, 6.5, uFireT);
            }
        }
        if (bunt > 0.01) {
            for (int k = 0; k < 8; k++) {
                float fk = float(k);
                float h1 = hash12(vec2(fk, uFireSeed)), h2 = hash12(vec2(fk, uFireSeed + 1.0)), h3 = hash12(vec2(fk, uFireSeed + 2.0));
                float t0 = fk * 0.7 + h1 * 0.5;
                float age = uFireT - t0;
                if (age < 0.0 || age > 2.5) continue;
                vec2 c = vec2(0.15 + h2 * 0.7, 0.62 + h3 * 0.33);
                vec2 d = (uv - c) * vec2(aspect, 1.0);
                float r = length(d), a = atan(d.y, d.x);
                float ring = exp(-pow((r - age * 0.12) * 45.0, 2.0)) * pow(0.5 + 0.5 * sin(a * 18.0 + fk), 2.0) * (1.0 - age / 2.5);
                float core = exp(-r * 40.0) * exp(-age * 4.0);
                col += hueShift(vec3(1.0, 0.5, 0.8), fk * 1.3 + uHue) * (ring * 1.5 + core * 2.0) * bunt;
            }
        }
    }
    // ---- Zeitsprung: zwei Feuerspuren laufen über den Platz, Blaulicht knistert, Weißblitz (am Ende über allem), danach Nachglühen
    float jumpFlash = 0.0;
    if (uJumpT >= 0.0) {
        float run = clamp(uJumpT / JUMP_SWITCH, 0.0, 1.0);
        float head = uJumpDir >= 0.0 ? -0.1 + 1.3 * run : 1.1 - 1.3 * run;
        float burn = 1.0 - smoothstep(JUMP_SWITCH, JUMP_LEN, uJumpT);
        float fire = 0.0;
        for (int k = 0; k < 2; k++) {
            float yl = uGround * (k == 0 ? 0.33 : 0.52) + 0.012 * sin(uv.x * 9.0 + float(k) * 2.0);
            float behind = uJumpDir >= 0.0 ? step(uv.x, head) * smoothstep(head - 1.4, head - 0.02, uv.x) : step(head, uv.x) * smoothstep(head + 1.4, head + 0.02, uv.x);
            float w = 0.006 + 0.006 * noise(vec2(uv.x * 40.0 - t * 15.0, float(k) * 7.0));
            float line = exp(-pow((uv.y - yl) / w, 2.0)) * behind;
            float flames = noise(vec2(uv.x * 50.0 + float(k) * 11.0, (uv.y - yl) * 60.0 - t * 12.0)) * smoothstep(0.05, 0.0, abs(uv.y - yl - 0.02)) * behind;
            fire += line + flames * 0.6;
            float hd = length((uv - vec2(head, yl)) * vec2(aspect, 1.0));
            col += vec3(0.6, 0.8, 1.0) * exp(-hd * 40.0) * 2.0 * (1.0 - step(1.0, run)) * burn;
        }
        col += (vec3(1.0, 0.55, 0.15) * fire * 1.6 + vec3(1.0, 0.9, 0.6) * fire * fire) * burn;
        jumpFlash = smoothstep(0.55, JUMP_SWITCH - 0.03, uJumpT) * (1.0 - smoothstep(JUMP_SWITCH + 0.05, JUMP_SWITCH + 0.75, uJumpT));
        vec2 cg = floor(uv * vec2(260.0, 150.0));
        float crackle = step(0.997 - 0.006 * preJump, hash12(cg + floor(t * 30.0) * 0.173 + uSeed)) * preJump * preJump * (1.0 - jumpFlash);
        col += vec3(0.5, 0.7, 1.0) * crackle * 2.0 * (0.3 + 0.7 * town);
        col += vec3(0.25, 0.35, 0.7) * exp(-(uJumpT - JUMP_SWITCH) * 2.0) * postJump * 0.5;
    }
    // ---- Teilchen aus dem Bogen je Epoche (Reihe 0 Wilder Westen, 1 Fünfziger/Achtziger, 2 Zukunft), beim Feuerwerk Konfetti und
    // Ballons, beim Zeitsprung Feuerspur-Stücke
    {
        float storm = uFireT >= 0.0 ? 1.0 : 0.0;
        int n = 5 + int(18.0 * clamp(0.15 + uEnergy + 0.5 * uHighS, 0.0, 1.0) * (0.4 + 0.6 * live)) + int(6.0 * (storm + jumpOn));
        for (int i = 0; i < 30; i++) {
            if (i >= n) break;
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0)), h4 = hash12(vec2(fi, 9.0));
            float era = h4 < uEraMix ? uEraB : uEraA;
            float idx;
            float rise = 0.0, hover = 0.0, roll = 0.0, fall = 0.08 + 0.08 * h2;
            vec2 p;
            if (jumpOn > 0.0 && h3 > 0.6 && uJumpT < JUMP_SWITCH + 0.6) {
                idx = 19.0;                                                                   // Feuerspur-Stück entlang der Spuren
                float run = clamp(uJumpT / JUMP_SWITCH, 0.0, 1.0);
                float head = uJumpDir >= 0.0 ? -0.1 + 1.3 * run : 1.1 - 1.3 * run;
                float yl = uGround * (h1 < 0.5 ? 0.33 : 0.52);
                p = vec2(head - uJumpDir * (0.03 + 0.25 * h2), yl + 0.02 + 0.03 * h2 + 0.02 * sin(t * 9.0 + fi));
            } else if (storm > 0.0 && h3 > 0.5 && era < 0.5) {
                idx = h1 < 0.5 ? 2.0 : 6.0;                                                   // 1885: Funken und Glut steigen von den Kanonen auf
                rise = 1.0;
                fall = 0.25 + 0.2 * h2;
                float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
                p = vec2(0.05 + h1 * 0.9 + 0.05 * sin(t * (2.0 + h2) + fi), ph * 0.8 - 0.05);
            } else if (storm > 0.0 && h3 > 0.5) {
                idx = h1 < 0.5 ? 8.0 : (h1 < 0.8 ? 12.0 : 9.0);                              // Konfetti, Luftschlange, Ballon
                rise = idx == 9.0 ? 1.0 : 0.0;
                fall = idx == 9.0 ? 0.05 + 0.03 * h2 : 0.2 + 0.1 * h2;
                float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
                p = vec2(0.05 + h1 * 0.9 + 0.04 * sin(t * (1.0 + h2) + fi), rise > 0.0 ? ph * 1.1 - 0.05 : 1.0 - ph * 1.1);
            } else if (era < 0.5) {
                idx = floor(h1 * 8.0);                                                        // 1885: Staub, Steppenläufer, Funken, Hufeisen, Patrone, Feder, Glut, Rauch
                if (idx == 3.0 || idx == 4.0) idx = h2 < 0.5 ? 0.0 : 7.0;                     // Hufeisen/Patrone nur selten
                roll = idx == 1.0 ? 1.0 : 0.0;
                fall = idx == 5.0 ? 0.04 + 0.02 * h2 : (idx == 1.0 ? 0.06 + 0.04 * h2 : 0.05 + 0.04 * h2);
                float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
                if (roll > 0.0) p = vec2(ph * 1.3 - 0.15, uGround * (0.2 + 0.3 * h2) + 0.01 * abs(sin(t * 6.0 + fi)));
                else if (idx == 0.0 || idx == 7.0) p = vec2(mod(h1 * 3.0 + t * (0.02 + 0.03 * h2), 1.2) - 0.1, 0.05 + 0.5 * h2 + 0.03 * sin(t * 0.7 + fi));
                else p = vec2(0.05 + h1 * 0.9 + 0.03 * sin(t * (1.0 + h2) + fi), idx == 2.0 || idx == 6.0 ? ph * 0.8 : 1.0 - ph * 1.1);
            } else if (era < 1.5) {
                float pick = floor(h1 * 5.0);                                                 // 1955: Konfetti, Ballon, Schallplatte, Milchshake, Luftschlange
                idx = 8.0 + pick;
                rise = pick == 1.0 ? 1.0 : 0.0;
                fall = pick == 1.0 ? 0.04 + 0.03 * h2 : (pick == 0.0 || pick == 4.0 ? 0.12 + 0.08 * h2 : 0.06 + 0.04 * h2);
                float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
                p = vec2(0.05 + h1 * 0.9 + 0.03 * sin(t * (1.0 + h2) + fi), rise > 0.0 ? ph * 1.1 - 0.05 : 1.0 - ph * 1.1);
            } else if (era < 2.5) {
                float pick = floor(h1 * 5.0);                                                 // 1985: Konfetti, Luftschlange, Kassette, Pappbecher, Neonsplitter
                idx = pick == 0.0 ? 8.0 : 11.0 + pick;
                fall = pick == 0.0 || pick == 1.0 ? 0.12 + 0.08 * h2 : 0.07 + 0.04 * h2;
                float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
                p = vec2(0.05 + h1 * 0.9 + 0.03 * sin(t * (1.0 + h2) + fi), 1.0 - ph * 1.1);
            } else {
                float pick = floor(h1 * 7.0);                                                 // 2015: Scherbe, Drohne, Lichtpunkt, Regentropfen, Blatt, Pizza, Schneeflocke
                idx = 16.0 + (pick < 3.0 ? pick : pick + 1.0);
                hover = pick == 1.0 || pick == 2.0 ? 1.0 : 0.0;
                fall = pick == 3.0 ? 0.35 + 0.1 * h2 : 0.06 + 0.05 * h2;
                float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
                if (hover > 0.0) p = vec2(0.1 + h1 * 0.8 + 0.08 * sin(t * (0.3 + 0.3 * h2) + fi), 0.45 + 0.4 * h2 + 0.04 * sin(t * 1.3 + fi * 2.0));
                else p = vec2(0.05 + h1 * 0.9 + 0.03 * sin(t * (1.0 + h2) + fi), 1.0 - ph * 1.1);
            }
            float sz = 0.014 + 0.016 * h3;
            if (idx == 19.0) sz = 0.02 + 0.015 * h3;
            if (idx == 0.0 || idx == 7.0) sz = 0.05 + 0.04 * h3;
            if (idx == 18.0) sz = 0.008 + 0.006 * h3;
            float spin = roll > 0.0 ? -t * 4.0 : (hover > 0.0 || idx == 9.0 || idx == 20.0 ? 0.0 : t * (0.4 + h2) * (h1 > 0.5 ? 1.0 : -1.0));
            vec2 d = rot(spin) * ((uv - p) * vec2(aspect, 1.0)) / sz;
            vec4 s = part(idx, d);
            float alpha = s.a * (idx == 0.0 || idx == 7.0 ? 0.08 + 0.14 * uHighS : 0.9);
            col = mix(col, s.rgb * (0.7 + 0.3 * live + 0.4 * uHighS), alpha);
            if (idx == 2.0 || idx == 6.0 || idx == 18.0 || idx == 19.0) col += s.rgb * s.a * 0.6;    // Funken, Glut, Lichtpunkt, Feuer leuchten
        }
    }
    col *= 0.75 + 0.25 * live;
    col += vec3(1.0, 0.97, 0.9) * uFlash * 0.25;
    col = mix(col, vec3(1.0, 0.97, 0.9), jumpFlash * 0.97);
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
