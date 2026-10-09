#version 140
// F4 – Taktik-Scanner: grünes Gitter, weißes 3D-Drahtgitter eines Gleiters (dreht mit den Mitten),
// Radar mit Sweep und Blips (Spektrum), fremde Schrift, rote Statusbalken. Beat lässt Blips aufleuchten.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;

const vec3 GRN = vec3(0.35, 0.95, 0.35);
const vec3 WHT = vec3(0.92, 0.96, 0.92);
const vec3 RED = vec3(1.0, 0.25, 0.2);
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }
float wave(float x) { return texture(uAudioTex, vec2(x, 0.75)).r * 2.0 - 1.0; }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }
float frame(vec2 uv, vec2 a, vec2 b, float w) { return rect(uv, a, b) - rect(uv, a + w, b - w); }
float segDist(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}
float glyph(float id, vec2 p) {
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    vec2 c = floor(p * vec2(3.0, 5.0));
    float on = step(0.45, hash(vec2(id, c.x + c.y * 3.0)));
    return max(on, step(4.0, c.y) * step(0.3, hash(vec2(id, 99.0))));
}
float text(vec2 uv, vec2 pos, float n, float seed, vec2 sz) {
    vec2 p = (uv - pos) / sz;
    float i = floor(p.x / 1.4);
    if (i < 0.0 || i >= n) return 0.0;
    return glyph(seed + i, vec2(fract(p.x / 1.4) * 1.4, p.y));
}
// 3D-Punkt drehen und projizieren
vec2 proj(vec3 v, float ry, float rx) {
    float c = cos(ry), s = sin(ry);
    v.xz = mat2(c, -s, s, c) * v.xz;
    c = cos(rx); s = sin(rx);
    v.yz = mat2(c, -s, s, c) * v.yz;
    float d = 3.0 / (3.0 + v.z);
    return v.xy * d;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = (floor(vUv * vec2(270.0 * aspect, 270.0)) + 0.5) / vec2(270.0 * aspect, 270.0);
    float px = 1.0 / 270.0;
    float live = 1.0 - uSilent;
    vec3 col = vec3(0.0);

    // Gitter im Hintergrund
    vec2 g = abs(fract(uv * vec2(24.0 * aspect / 1.78, 24.0)) - 0.5);
    col += GRN * 0.12 * smoothstep(0.48, 0.5, max(g.x, g.y));
    col += GRN * 0.35 * frame(uv, vec2(0.03, 0.03), vec2(0.97, 0.97), 1.5 * px);

    // ---- Rechts: Drahtgitter-Gleiter (Deltaflügel + Kabine), dreht mit Zeit und Mitten
    vec2 R0 = vec2(0.52, 0.18), R1 = vec2(0.96, 0.90);
    col += GRN * 0.6 * frame(uv, R0, R1, 1.5 * px);
    if (rect(uv, R0, R1) > 0.5) {
        vec2 c = (uv - (R0 + R1) * 0.5) / ((R1 - R0) * 0.5);
        c.x *= (R1.x - R0.x) * aspect / (R1.y - R0.y);
        float ry = iTime * 0.35 + uMid * 2.0 * live;
        float rx = 0.35 + 0.15 * sin(iTime * 0.5) + uBass * 0.3 * live;
        // Segmente: Rumpf, Flügel, Heckflosse
        vec3 P[8];
        P[0] = vec3(0.0, 0.0, 1.0);      // Bug
        P[1] = vec3(0.0, 0.0, -0.8);     // Heck
        P[2] = vec3(0.9, 0.0, -0.7);     // Flügel rechts
        P[3] = vec3(-0.9, 0.0, -0.7);    // Flügel links
        P[4] = vec3(0.0, 0.55, -0.6);    // Flosse oben
        P[5] = vec3(0.0, 0.12, 0.2);     // Kabine
        P[6] = vec3(0.35, 0.0, 0.0);     // Mittelstreben
        P[7] = vec3(-0.35, 0.0, 0.0);
        vec2 Q[8];
        for (int i = 0; i < 8; i++) Q[i] = proj(P[i] * 0.55, ry, rx);
        float d = 1e3;
        d = min(d, segDist(c, Q[0], Q[2])); d = min(d, segDist(c, Q[0], Q[3]));
        d = min(d, segDist(c, Q[2], Q[1])); d = min(d, segDist(c, Q[3], Q[1]));
        d = min(d, segDist(c, Q[0], Q[1])); d = min(d, segDist(c, Q[1], Q[4]));
        d = min(d, segDist(c, Q[4], Q[5])); d = min(d, segDist(c, Q[5], Q[0]));
        d = min(d, segDist(c, Q[6], Q[2])); d = min(d, segDist(c, Q[7], Q[3]));
        d = min(d, segDist(c, Q[6], Q[7]));
        col += WHT * smoothstep(2.0 * px, 0.0, d) * (0.75 + 0.25 * uRms);
        // Triebwerksglühen am Heck mit Bass
        col += RED * smoothstep(0.05 + 0.08 * uBass * live, 0.0, length(c - Q[1])) * (0.3 + 0.7 * uBass) * live;
        // Schrift rechts oben
        col += GRN * text(uv, vec2(0.55, 0.84), 9.0, 41.0, vec2(0.009, 0.022));
        col += GRN * 0.7 * text(uv, vec2(0.55, 0.80), 6.0, 57.0, vec2(0.009, 0.022));
    }

    // ---- Links oben: Radar mit Sweep und Blips
    vec2 L0 = vec2(0.05, 0.50), L1 = vec2(0.47, 0.90);
    col += GRN * 0.6 * frame(uv, L0, L1, 1.5 * px);
    if (rect(uv, L0, L1) > 0.5) {
        vec2 c = (uv - (L0 + L1) * 0.5) * vec2(aspect, 1.0) / ((L1.y - L0.y) * 0.5);
        float rr = length(c);
        float ang = atan(c.y, c.x);
        for (int k = 1; k <= 3; k++) col += GRN * 0.35 * smoothstep(1.5 * px, 0.0, abs(rr - float(k) * 0.3));
        col += GRN * 0.25 * (smoothstep(1.2 * px, 0.0, abs(c.x)) + smoothstep(1.2 * px, 0.0, abs(c.y))) * step(rr, 0.9);
        float sweep = fract(ang / 6.2832 - iTime * 0.3);
        col += GRN * 0.45 * pow(1.0 - sweep, 8.0) * step(rr, 0.9);
        // Blips: 16 Richtungen, Abstand aus dem Spektrum
        for (int i = 0; i < 16; i++) {
            float fi = float(i);
            float ba = fi / 16.0 * 6.2832 + 0.2;
            float br = 0.15 + 0.7 * spec(fi / 16.0) * live;
            vec2 bp = vec2(cos(ba), sin(ba)) * br;
            float seen = pow(1.0 - fract(ba / 6.2832 - iTime * 0.3), 3.0);
            col += mix(GRN, RED, uBeat) * smoothstep(0.03, 0.015, length(c - bp)) * (0.3 + 0.7 * seen) * step(0.08, br - 0.15 + 0.1);
        }
    }

    // ---- Links unten: Waveform-Fenster und rote Statusbalken
    vec2 W0 = vec2(0.05, 0.18), W1 = vec2(0.47, 0.46);
    col += GRN * 0.6 * frame(uv, W0, W1, 1.5 * px);
    if (rect(uv, W0, W1) > 0.5) {
        vec2 q = (uv - W0) / (W1 - W0);
        float y0 = 0.5 + wave(q.x) * 0.35 * (0.3 + 0.7 * live);
        col += WHT * smoothstep(2.5 * px, 0.0, abs(q.y - y0)) * 0.9;
        col += GRN * 0.2 * smoothstep(1.0 * px, 0.0, abs(q.y - 0.5));
    }
    for (int k = 0; k < 3; k++) {
        float lvl = (k == 0) ? uBass : (k == 1 ? uMid : uHigh);
        float x = 0.07 + float(k) * 0.035;
        col += RED * rect(uv, vec2(x, 0.06), vec2(x + 0.025, 0.06 + 0.08 * (0.15 + 0.85 * lvl)));
        col += RED * 0.25 * frame(uv, vec2(x, 0.06), vec2(x + 0.025, 0.14), 1.0 * px);
    }
    col += GRN * 0.8 * text(uv, vec2(0.20, 0.08), 12.0, 73.0, vec2(0.009, 0.022));
    col += GRN * 0.9 * text(uv, vec2(0.30, 0.935), 14.0, 5.0, vec2(0.011, 0.026));
    col *= 1.0 + 0.15 * uBeat * live;
    col *= 0.92 + 0.08 * sin(vUv.y * iResolution.y * 3.14159 * 0.5);
    fragColor = vec4(col, 1.0);
}
