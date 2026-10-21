#version 140
// Dachterrasse: Stadtfoto (uSceneTex); Fenster und Werbeflächen (helle Stellen oberhalb uSkyline) leuchten mit dem Bass,
// Beats laufen als Lichtwelle von unten durch die Türme (uPulseA/B), Suchscheinwerfer schwenken (uSearchT, Mitten),
// Verkehr als Lichtstreifen (uTrafficT, Energie), Höhen = Tropfen/Funken. Wetter uWeather 0..4 fließend (Regen, Nebel,
// Säure, Asche) mit Teilchen aus uPartTex (8x3 à 160). Drop uFlash + uHue, Feuerwerk uFireT, Blitz uLightT/uLightX,
// Stromausfall uBlackT/uBlackBeats, Blick nach unten uLook.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uPartTex;
uniform vec2 uSceneSize, uPartSize;
uniform float uSeed, uSkyline, uWeather, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash, uHue;
uniform float uFireT, uFireSeed, uBlackT, uBlackBeats, uLightT, uLightX, uSearchT, uTrafficT, uLook;
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
vec4 part(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 160.0, (2.0 - ri) * 160.0);
    return bilin(uPartTex, lo + (d * 0.5 + 0.5) * 160.0, uPartSize, lo, lo + 159.0);
}
float pulseAge(int i) { return i < 3 ? uPulseA[i] : uPulseB[i - 3]; }
float weatherW(float s) { float d = abs(mod(uWeather - s + 2.0, 4.0) - 2.0); return smoothstep(1.0, 0.0, d); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    float wRain = weatherW(0.0), wFog = weatherW(1.0), wAcid = weatherW(2.0), wAsh = weatherW(3.0);
    // Kamera: Blick nach unten kippt das Bild (unten wird gestreckt), Bass wackelt leicht
    vec2 uv = vUv;
    uv.y = mix(uv.y, pow(uv.y, 1.6) * 0.75, uLook);
    uv = 0.5 + (uv - 0.5) * (1.0 - 0.015 * uBassS * live);
    uv += vec2(0.001 * sin(t * 0.3), 0.001 * cos(t * 0.21));
    vec3 plate = scene(uv);
    vec3 col = plate;
    float lum = max(plate.r, max(plate.g, plate.b));
    float sat = lum - min(plate.r, min(plate.g, plate.b));
    float city = smoothstep(uSkyline - 0.05, uSkyline + 0.05, uv.y);
    float windows = smoothstep(0.35, 0.7, lum) * city;                                  // alle Lichter der Stadt
    float ads = smoothstep(0.45, 0.75, lum) * smoothstep(0.2, 0.45, sat) * city;        // große bunte Flächen
    // ---- Stromausfall: Blöcke der Stadt gehen aus, kommen mit den Beats zurück
    float black = 0.0;
    if (uBlackT >= 0.0) {
        vec2 blk = floor(uv * vec2(9.0, 5.0));
        float h = hash12(blk + uSeed);
        float off = smoothstep(0.0, 1.2, uBlackT - h * 1.0);                              // geht blockweise aus
        float back = smoothstep(h * 14.0 - 1.0, h * 14.0 + 1.0, uBlackBeats) * smoothstep(0.0, 1.0, uBlackT - 3.0);   // Beats schalten zurück
        black = off * (1.0 - back);
        float soft = smoothstep(0.0, 0.12, min(fract(uv.x * 9.0), 1.0 - fract(uv.x * 9.0))) * smoothstep(0.0, 0.12, min(fract(uv.y * 5.0), 1.0 - fract(uv.y * 5.0)));
        black *= 0.6 + 0.4 * soft;
        col = mix(col, col * 0.2, black * city);
    }
    // ---- Beat-Lichtwellen laufen von unten durch die Türme
    float wave = 0.0;
    for (int i = 0; i < 6; i++) {
        float age = pulseAge(i);
        if (age > 3.0) continue;
        float front = uSkyline + age * 0.3;
        wave += exp(-pow((uv.y - front) * 25.0, 2.0)) * exp(-age * 1.2);
    }
    vec3 adCol = hueShift(plate / max(lum, 0.2), uHue);
    col += adCol * windows * (0.5 * uBassS + 1.5 * wave + 0.3 * uBeatPulse) * live * (1.0 - black);
    col = mix(col, hueShift(col, uHue), ads * min(1.0, abs(uHue)));
    col += adCol * ads * (0.3 + 0.6 * uFlash) * live;
    col = mix(col, col * 0.55, windows * (1.0 - live) * 0.6);                             // Stille: Stadt schläft
    // ---- Verkehr: Lichtstreifen zwischen den Türmen (Energie), Flieger-Lichter
    for (int k = 0; k < 10; k++) {
        float fk = float(k);
        float h1 = hash12(vec2(fk, 41.0)), h2 = hash12(vec2(fk, 43.0));
        float y = uSkyline + 0.05 + h1 * 0.4;
        float x = fract(uTrafficT * (0.1 + 0.15 * h2) + h1 * 3.0) * 1.4 - 0.2;
        if (h2 > 0.5) x = 1.2 - x;
        float d = length((uv - vec2(x, y)) * vec2(aspect, 1.0) * vec2(0.4, 1.0));
        col += mix(vec3(1.0, 0.3, 0.2), vec3(0.3, 0.8, 1.0), h2) * smoothstep(0.012, 0.0, d) * (0.3 + 0.7 * uEnergy) * live * (1.0 - black) * city;
    }
    // ---- Suchscheinwerfer schwenken mit den Mitten (zwei Kegel von Dächern)
    for (int k = 0; k < 2; k++) {
        float fk = float(k);
        vec2 base = vec2(k == 0 ? 0.33 : 0.72, uSkyline + 0.25);
        float ang = PI * 0.5 + 0.6 * sin(uSearchT * (0.7 + 0.3 * fk) + fk * 2.0);
        vec2 dir = vec2(cos(ang), sin(ang));
        vec2 d = (uv - base) * vec2(aspect, 1.0);
        float along = dot(d, dir), across = abs(dot(d, vec2(-dir.y, dir.x)));
        float cone = smoothstep(0.02 + 0.06 * along, 0.0, across) * smoothstep(0.0, 0.05, along) * exp(-along * 2.5);
        col += vec3(0.8, 0.9, 1.0) * cone * (0.15 + 0.35 * uMidS) * live * (1.0 - black);
    }
    // ---- Blitz: Himmel wird weiß, verästelte Linie
    if (uLightT >= 0.0) {
        float e = exp(-uLightT * 5.0) * (0.6 + 0.4 * step(0.5, fract(uLightT * 30.0)));
        col += vec3(0.8, 0.85, 1.0) * e * smoothstep(0.5, 1.0, uv.y) * 0.8;
        float x = uLightX + 0.03 * sin(uv.y * 40.0 + uSeed) + 0.015 * sin(uv.y * 120.0);
        float bolt = smoothstep(0.004, 0.0, abs(uv.x - x)) * smoothstep(0.6, 1.0, uv.y);
        col += vec3(0.9, 0.95, 1.0) * bolt * e * 3.0;
        col += vec3(0.5, 0.6, 1.0) * e * 0.2;
    }
    // ---- Feuerwerk über der Stadt
    if (uFireT >= 0.0) {
        for (int k = 0; k < 8; k++) {
            float fk = float(k);
            float h1 = hash12(vec2(fk, uFireSeed)), h2 = hash12(vec2(fk, uFireSeed + 1.0)), h3 = hash12(vec2(fk, uFireSeed + 2.0));
            float t0 = fk * 0.7 + h1 * 0.5;
            float age = uFireT - t0;
            if (age < 0.0 || age > 2.5) continue;
            vec2 c = vec2(0.15 + h2 * 0.7, 0.65 + h3 * 0.3);
            vec2 d = (uv - c) * vec2(aspect, 1.0);
            float r = length(d), a = atan(d.y, d.x);
            float ring = exp(-pow((r - age * 0.12) * 45.0, 2.0)) * pow(0.5 + 0.5 * sin(a * 18.0 + fk), 2.0) * (1.0 - age / 2.5);
            float core = exp(-r * 40.0) * exp(-age * 4.0);
            col += hueShift(vec3(1.0, 0.5, 0.8), fk * 1.3 + uHue) * (ring * 1.5 + core * 2.0);
        }
    }
    // ---- Wetter: Regen (Streifen + Tropfen), Nebel (Schleier), Säure (grüne Tropfen, Ätzflecken), Asche (Flocken)
    float rainI = wRain + 0.6 * wAcid;
    if (rainI > 0.01) {
        vec2 rp = vec2(uv.x * 60.0 + uv.y * 8.0, uv.y * 40.0 + t * 9.0);
        float streak = smoothstep(0.9, 1.0, noise(rp)) * rainI;
        col += (vec3(0.7, 0.85, 1.0) * wRain + vec3(0.5, 1.0, 0.3) * wAcid) * streak * 0.35;
    }
    if (wFog > 0.01) {
        float fog = fbm(vec2(uv.x * 3.0 + t * 0.05, uv.y * 4.0) + uSeed) * city;
        col = mix(col, vec3(0.45, 0.5, 0.6) * (0.6 + 0.4 * uBassS * live), smoothstep(0.3, 0.8, fog) * wFog * 0.6);
    }
    if (wAcid > 0.01) col = mix(col, col * vec3(0.7, 1.1, 0.6) + vec3(0.0, 0.05, 0.0), wAcid * 0.5);
    if (wAsh > 0.01) col = mix(col, col * vec3(0.9, 0.85, 0.8), wAsh * 0.4);
    // Teilchen aus dem Bogen: Tropfen/Funken (Regen, Höhen), Konfetti (Feuerwerk, Drop), Flocken (Asche)
    {
        float storm = uFireT >= 0.0 ? 1.0 : 0.0;
        int n = 14 + int(16.0 * (wAsh + storm));
        for (int i = 0; i < 30; i++) {
            if (i >= n) break;
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
            float row, idx;
            if (storm > 0.0 && h3 > 0.5) { row = 1.0; idx = floor(h1 * 8.0); }
            else if (wAsh > h3) { row = 2.0; idx = floor(h1 * 8.0); }
            else if (wRain + wAcid > h3 * 1.5) { row = 0.0; idx = h2 < 0.7 ? 0.0 : floor(4.0 + h1 * 3.0); }
            else continue;
            float fall = row == 0.0 ? 0.5 : (0.06 + 0.06 * h2);
            float ph = mod(t * fall + h1 * 7.0 + h2 * 3.0, 1.0);
            vec2 p = vec2(0.05 + h1 * 0.9 + 0.03 * sin(t * (1.0 + h2) + fi) * (row == 0.0 ? 0.0 : 1.0), 1.0 - ph * 1.05);
            float sz = row == 0.0 ? 0.012 : 0.02 + 0.015 * h3;
            vec2 d = rot(row == 0.0 ? 0.0 : t * (0.5 + h2) * (h1 > 0.5 ? 1.0 : -1.0)) * ((uv - p) * vec2(aspect, 1.0)) / sz;
            vec4 s = part(row * 8.0 + idx, d);
            if (row == 0.0) s.rgb = mix(s.rgb, vec3(0.5, 1.0, 0.3), wAcid);
            col = mix(col, s.rgb * (0.7 + 0.3 * live + 0.5 * uHighS), s.a * (row == 0.0 ? 0.6 + 0.4 * uHighS : 0.9));
        }
    }
    // Tropfen am Geländer funkeln mit den Höhen (Vordergrund, helle Kanten)
    col += plate * (1.0 - city) * smoothstep(0.4, 0.8, lum) * uHighS * 0.6 * (0.5 + 0.5 * sin(t * 9.0 + uv.x * 300.0 + uv.y * 200.0));
    col *= 0.75 + 0.25 * live;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
