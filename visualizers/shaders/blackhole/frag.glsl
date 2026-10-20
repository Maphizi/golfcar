#version 140
// Schwarzes Loch: Strahlverfolgung mit Lichtkrümmung. Akkretionsscheibe aus glühendem Gas, die sich
// über und unter dem Loch wölbt (Gravitationslinse), Photonenring, Doppler-Helligkeit (die Seite,
// die auf uns zukommt, ist heller), gekrümmter Sternenhintergrund, Jet aus den Polen.
// Musik: Bass pulst Scheibe und Linse, das Spektrum liegt als Ringe auf der Scheibe (innen Bass,
// außen Höhen), Mitten färben das Gas heißer, der Beat zündet Jet und Flare (vom Controller geglättet),
// Höhen lassen die Scheibe funkeln. uZoom = Nahaufnahme.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uSeed, uTilt, uAngle, uPalette, uJet, uFlare, uZoom, uBassS;

const int STEPS = 36;      // Pi 5: 64 Schritte bei 0.5 = 9 fps, 36 bei 0.35 ≈ 40 fps
const float R_H = 1.0;       // Horizont
const float R_IN = 2.3;      // Innenrand der Scheibe
const float R_OUT = 11.0;    // Außenrand

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p) { p = fract(p * vec3(0.1031, 0.1030, 0.0973)); p += dot(p, p.yxz + 33.33); return fract((p.x + p.y) * p.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 3; i++) { v += a * noise(p); p = p * 2.07 + 3.1; a *= 0.5; } return v; }
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

// Farbe des Gases nach Temperatur (0 kühl außen, 1 heiß innen) und Palette
vec3 gasColor(float temp, float heat) {
    vec3 cool, hot;
    if (uPalette < 0.5)      { cool = vec3(1.0, 0.30, 0.05); hot = vec3(1.0, 0.82, 0.55); }
    else if (uPalette < 1.5) { cool = vec3(0.25, 0.15, 1.0); hot = vec3(0.65, 0.85, 1.0); }
    else                     { cool = vec3(0.85, 0.10, 0.08); hot = vec3(1.0, 0.75, 0.35); }
    vec3 c = mix(cool, hot, smoothstep(0.0, 1.0, temp));
    return mix(c, vec3(0.75, 0.9, 1.0), heat * 0.5 * temp);     // Mitten: blauweißer
}
// Emission der Scheibe an Punkt (r, phi), Sichtrichtung rd (für Doppler)
vec3 diskEmission(vec3 p, vec3 rd, float t, float live, out float alpha) {
    float r = length(p.xz);
    float phi = atan(p.z, p.x);
    float u = (r - R_IN) / (R_OUT - R_IN);                 // 0 innen, 1 außen
    // Keplerrotation: innen schnell. Gaswirbel in log-polar-Koordinaten plus zwei Spiralarme
    float omega = 1.1 * pow(r, -1.5);
    float ang = phi + t * omega * 3.0;
    vec2 q = vec2(ang * 2.2, log(r) * 5.5 + uSeed);
    float n = fbm(q + vec2(0.0, -t * 0.08));
    float spiral = 0.5 + 0.5 * sin(ang * 2.0 - log(r) * 5.0 + uSeed);
    float dens = smoothstep(0.25, 0.8, n * 0.8 + spiral * 0.35);
    // Spektrum als Ringe: Position auf der Scheibe entspricht Frequenz
    float band = spec(u);
    dens *= 0.5 + 1.2 * band * live + 0.3 * (1.0 - live);
    // Funkeln bei Höhen
    dens += uHigh * live * step(0.985, hash13(vec3(floor(q * 6.0), floor(t * 20.0)))) * 2.0;
    // Kanten weich, innen am hellsten
    float edge = smoothstep(0.0, 0.08, u) * smoothstep(1.0, 0.65, u);
    float bright = (0.22 + 0.9 * pow(1.0 - u, 2.0)) * (1.0 + 1.2 * uBassS);
    // Doppler: Tangentialgeschwindigkeit gegen Blickrichtung
    vec3 vel = normalize(vec3(-p.z, 0.0, p.x));
    float dop = dot(vel, -rd);
    float beam = pow(clamp(1.0 + 0.7 * dop, 0.25, 1.9), 2.0);
    float temp = pow(1.0 - u, 1.3) + 0.3 * dop;
    alpha = clamp(dens * edge * 0.9, 0.0, 1.0);
    return gasColor(clamp(temp, 0.0, 1.0), uMid * live) * bright * beam * dens * edge;
}
vec3 background(vec3 d, float t) {
    // Sterne auf der Kugel plus schwacher Nebel, beide werden durch die Linse mitgezogen
    vec2 s = vec2(atan(d.z, d.x), asin(clamp(d.y, -1.0, 1.0)));
    vec2 cell = floor(s * vec2(70.0, 45.0));
    float h = hash12(cell + uSeed);
    vec2 f = fract(s * vec2(70.0, 45.0)) - 0.5;
    float star = step(0.955, h) * smoothstep(0.35, 0.0, length(f)) * (0.6 + 0.4 * sin(t * 2.0 + h * 40.0));
    vec3 col = vec3(star) * (0.6 + 0.6 * hash12(cell + 2.0));
    float neb = fbm(s * vec2(2.0, 3.0) + uSeed);
    col += mix(vec3(0.25, 0.05, 0.35), vec3(0.05, 0.15, 0.4), noise(s * 3.0)) * smoothstep(0.5, 0.85, neb) * 0.35;
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = (vUv - 0.5) * vec2(aspect, 1.0);
    float t = iTime;
    float live = 1.0 - uSilent;
    // Kamera: kreist, leicht geneigt, bei Zoom näher dran; Bass schüttelt minimal
    float dist = mix(26.0, 16.0, uZoom);
    float tilt = uTilt + 0.1 * uZoom;
    vec3 ro = vec3(sin(uAngle) * cos(tilt), sin(tilt), cos(uAngle) * cos(tilt)) * dist;
    ro += vec3(hash12(vec2(floor(t * 30.0), 1.0)) - 0.5, hash12(vec2(floor(t * 30.0), 2.0)) - 0.5, 0.0) * 0.08 * uBassS * live;
    vec3 fw = normalize(-ro);
    vec3 rt = normalize(cross(vec3(0.0, 1.0, 0.0), fw));
    vec3 up = cross(fw, rt);
    float fov = mix(0.62, 0.8, uZoom);
    vec3 rd = normalize(fw + uv.x * rt * fov + uv.y * up * fov);
    vec3 p = ro, v = rd;
    vec3 col = vec3(0.0);
    float T = 1.0;                                 // Transmission
    float G = 2.4 * (1.0 + 0.25 * uBassS * live);  // Linsenstärke
    float glow = 0.0;
    bool captured = false, escaped = false;
    float yPrev = p.y;
    float minR = 100.0;
    for (int i = 0; i < STEPS; i++) {
        float r = length(p);
        minR = min(minR, r);
        if (r < R_H) { captured = true; break; }
        if (r > 60.0 && dot(p, v) > 0.0) { escaped = true; break; }
        // Schrittweite: fein nahe am Loch und nahe der Scheibenebene
        float ds = clamp(r * 0.3, 0.08, 2.6);
        ds = min(ds, max(abs(p.y) * 1.2, 0.08) + 0.35);
        // Lichtablenkung (Newton-Näherung, stärker nahe am Horizont)
        vec3 acc = -p * (G / (r * r * r)) * (1.0 + 1.5 / r);
        v = normalize(v + acc * ds);
        vec3 pn = p + v * ds;
        // Scheibenebene durchquert?
        if (sign(pn.y) != sign(yPrev) && T > 0.02) {
            float k = clamp(yPrev / (yPrev - pn.y), 0.0, 1.0);
            vec3 hit = mix(p, pn, k);
            float rh = length(hit.xz);
            if (rh > R_IN && rh < R_OUT) {
                float a;
                vec3 e = diskEmission(hit, v, t, live, a);
                col += e * T;
                glow += a * T;
                T *= 1.0 - a * 0.85;
            }
        }
        // Volumenglühen nahe der Ebene (dicke, dunstige Scheibe) und Photonenring-Glühen
        float rp = length(pn.xz);
        float thick = 0.18 + 0.35 * uBassS * live;
        if (rp > R_IN * 0.9 && rp < R_OUT) {
            float h = exp(-abs(pn.y) / thick) * ds * 0.045 * (1.0 - smoothstep(R_IN, R_OUT, rp));
            col += gasColor(1.0 - (rp - R_IN) / (R_OUT - R_IN), uMid * live) * h * T * (0.6 + 1.5 * uBassS);
        }
        // Jet: Säule entlang der Achse, nach dem Beat
        if (uJet > 0.01 && abs(pn.y) > 2.2 && rp < 2.6) {
            float jl = abs(pn.y);
            float jn = noise(vec2(jl * 1.2 - t * 12.0, atan(pn.z, pn.x) * 2.0 + uSeed));
            float width = 0.35 + jl * 0.09;
            float jr = smoothstep(width * (0.7 + 0.5 * jn), 0.0, rp);
            float jf = smoothstep(16.0 * uJet + 2.0, 2.0, jl) * uJet;
            col += mix(vec3(0.45, 0.75, 1.0), vec3(1.0, 0.95, 0.9), jn) * jr * jf * ds * 1.2 * T;
        }
        yPrev = pn.y;
        p = pn;
    }
    if (escaped || (!captured && length(p) > 12.0)) {
        col += background(normalize(v), t) * T;
    }
    // Photonenring: Strahlen, die dem Horizont sehr nah kamen und doch entkommen sind
    float ring = exp(-pow((minR - 1.5) * 3.5, 2.0)) * (1.0 - float(captured));
    col += gasColor(0.95, uMid * live) * ring * (0.5 + 0.8 * uBassS * live + 2.0 * uFlare);
    // Flare nach dem Beat: kurzer Lichtblitz um das Loch
    float screenR = length(uv) / fov;
    col += gasColor(0.7, 0.0) * exp(-screenR * 2.5) * uFlare * 0.9;
    // Tonemapping und Vignette
    col = col / (1.0 + col * 0.45);
    col *= 1.0 - 0.45 * pow(length(vUv - 0.5) * 1.35, 2.5);
    fragColor = vec4(col, 1.0);
}
