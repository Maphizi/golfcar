#version 140
// F2 – Psychedelic: Kaleidoskop-Tunnel mit Plasma/FBM, ShaderToy-Stil.
// Eigenständig geschrieben, kein fremder Shader-Code übernommen.
// Mapping: Bass -> Zoom/Puls, Mitten -> Rotation, Höhen -> Glitches, Lautstärke -> Intensität.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;

const float PI = 3.14159265;

float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i), b = hash(i + vec2(1, 0)), c = hash(i + vec2(0, 1)), d = hash(i + vec2(1, 1));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, amp = 0.5;
    mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
    for (int i = 0; i < 4; i++) { v += amp * noise(p); p = m * p; amp *= 0.5; }
    return v;
}
vec3 pal(float t) {
    return 0.5 + 0.5 * cos(2.0 * PI * (vec3(1.0, 0.8, 0.6) * t + vec3(0.10, 0.35, 0.65)));
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;
    float t = iTime * 0.2;                       // langsame Grundbewegung, auch bei Stille
    float live = 1.0 - uSilent;

    // Glitch-Zeilen aus den Höhen
    float row = floor(vUv.y * 48.0);
    float g = step(0.985 - uHigh * 0.15, hash(vec2(row, floor(iTime * 18.0))));
    uv.x += g * (hash(vec2(row, 7.0)) - 0.5) * 0.3 * uHigh;

    // Polar + Kaleidoskop (Mitten drehen)
    float r = length(uv);
    float ang = atan(uv.y, uv.x) + t * 0.6 + uMid * 1.2 * live;
    float seg = 6.0;
    float a = mod(ang, 2.0 * PI / seg);
    a = abs(a - PI / seg);

    // Tunnel: Bass zoomt/pulst
    float zoom = 1.0 + 0.9 * uBass + 0.4 * uBeat;
    float depth = 1.0 / (r * zoom + 0.12);
    vec2 tc = vec2(a * 3.5, depth * 0.9 + t * 3.0);

    // Plasma aus zwei FBM-Lagen
    float n1 = fbm(tc * 1.3 + vec2(0.0, t * 1.5));
    float n2 = fbm(tc * 2.6 - vec2(t * 1.1, 0.0) + n1 * 2.5);
    float v = n1 * 0.6 + n2 * 0.5;
    v += 0.18 * sin(depth * 5.0 - iTime * 2.2 + v * 5.0);
    v += 0.25 * spec(fract(a / PI * seg * 0.5)) * live;   // Spektrum als Muster auf den Segmenten

    vec3 col = pal(v * 1.6 + t * 0.8 + uBass * 0.4);
    // Tiefe: nach innen dunkler, Bass hellt den Kern auf
    float core = smoothstep(0.0, 0.35, r);
    col *= mix(0.25, 1.0, core);
    col += vec3(1.0, 0.6, 0.3) * (1.0 - core) * (0.25 + 0.75 * uBass) * 0.6;
    // Gesamtintensität: Grundhelligkeit auch ohne Musik, Lautstärke steigert
    col *= 0.55 + 0.6 * uRms + 0.5 * uBeat;
    // Fraktal-artige Kanten
    col += 0.12 * vec3(smoothstep(0.45, 0.5, fract(v * 4.0 + depth)));
    col *= 1.0 - 0.45 * smoothstep(0.9, 1.8, r);     // Vignette
    fragColor = vec4(pow(col, vec3(0.9)), 1.0);
}
