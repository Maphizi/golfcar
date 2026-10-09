#version 140
// F2 – Hyperraum: Sternenfeld, das bei Bass zum Sprung wird (Streifen, blauer Tunnel), Mitten rollen das Schiff,
// Höhen funkeln, Beat blitzt. Ohne Musik: ruhiger Flug durchs All.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;

const float PI = 3.14159265;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float hash1(float p) { return fract(sin(p * 78.233) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.1 + 5.0; a *= 0.5; }
    return v;
}
float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;
    float live = 1.0 - uSilent;
    float jump = clamp(uBass * 1.3 + uBeat * 0.5, 0.0, 1.0) * live;       // Sprungintensität
    float roll = iTime * 0.05 + uMid * 0.8 * live;                           // Rollen des Schiffs
    float cs = cos(roll), sn = sin(roll);
    uv = mat2(cs, -sn, sn, cs) * uv;
    float r = length(uv);
    float a = atan(uv.y, uv.x);
    vec3 col = vec3(0.0);

    // Hintergrund: schwacher Nebel, bei Sprung blauer Tunnel
    float neb = fbm(vec2(a * 2.0, 1.0 / (r + 0.3) - iTime * (0.2 + 2.5 * jump)));
    col += vec3(0.05, 0.08, 0.2) * neb * (0.4 + 1.5 * jump);
    col += vec3(0.3, 0.5, 1.0) * pow(neb, 3.0) * jump * 1.2;

    // Sterne in drei Tiefenlagen: Position aus Winkel-Zelle, Radius läuft mit der Zeit nach außen
    for (int layer = 0; layer < 3; layer++) {
        float fl = float(layer);
        float cells = 140.0 + fl * 60.0;
        float speed = (0.18 + fl * 0.12) * (1.0 + 7.0 * jump);
        float ca = floor(a / (2.0 * PI) * cells + fl * 7.0);
        float h = hash(vec2(ca, fl));
        float ang = (ca + 0.5 + (h - 0.5) * 0.6) / cells * 2.0 * PI;
        // Stern läuft von innen nach außen; jede Zelle hat eine eigene Phase
        float ph = fract(iTime * speed * (0.6 + 0.8 * h) + hash(vec2(ca, fl + 10.0)));
        float sr = 0.02 + ph * ph * 1.8;
        float streak = 0.004 + jump * 0.25 * ph + uHigh * 0.02 * live;         // Streifenlänge
        float dAng = abs(atan(sin(a - ang), cos(a - ang))) * r;
        float dRad = r - sr;
        float along = smoothstep(streak, 0.0, -dRad) * step(dRad, 0.0) + smoothstep(0.006, 0.0, abs(dRad));
        float dot_ = smoothstep(0.004 + 0.002 * fl, 0.0, dAng) * along;
        float bright = (0.4 + 0.6 * h) * (0.3 + ph) * step(0.35, hash(vec2(ca, fl + 20.0)));
        vec3 sc = mix(vec3(1.0), vec3(0.6, 0.8, 1.0), jump);
        sc = mix(sc, vec3(1.0, 0.85, 0.6), step(0.85, h) * 0.6);
        col += sc * dot_ * bright * (0.8 + 0.4 * uHigh);
    }
    // Spektrum als Ring um den Fluchtpunkt
    float ringR = 0.12 + 0.05 * uRms;
    float specV = spec(fract(a / (2.0 * PI) + 0.5)) * live;
    col += vec3(0.4, 0.7, 1.0) * smoothstep(0.02 + 0.08 * specV, 0.0, abs(r - ringR - 0.04 * specV)) * specV * 0.8;
    // Kern-Glühen beim Sprung, Beat-Blitz
    col += vec3(0.6, 0.8, 1.0) * exp(-r * 6.0) * (0.15 + 1.5 * jump);
    col += vec3(1.0) * uBeat * 0.12 * live;
    col *= 1.0 - 0.4 * smoothstep(1.0, 1.8, r);
    fragColor = vec4(col, 1.0);
}
