#version 140
// F4 – Digital Eye: abstraktes Maschinenauge, Retro-Pixel/CRT, leicht verstörend.
// Mapping: Bass -> Iris öffnet, Lautstärke -> Auge pulsiert, Mitten -> Geometrie dreht,
// Höhen -> Glitches, Beat -> Impulsring.
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
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) { v += a * noise(p); p *= 2.1; a *= 0.5; }
    return v;
}

void main() {
    float live = 1.0 - uSilent;
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;

    // Retro-Pixelraster
    float cells = 220.0;
    uv = floor(uv * cells) / cells + 0.5 / cells;

    // Glitch-Zeilen (Höhen)
    float row = floor(vUv.y * 36.0);
    float gl = step(0.975 - 0.2 * uHigh, hash(vec2(row, floor(iTime * 14.0))));
    uv.x += gl * (hash(vec2(row, 3.0)) - 0.5) * 0.35 * (0.3 + uHigh);

    // Puls mit Lautstärke
    uv /= 1.0 + 0.08 * uRms + 0.05 * uBeat;

    // Lidschlag (ca. alle 6 s) und Lidform
    float blink = pow(abs(sin(iTime * 0.52)), 60.0);
    float lid = 0.62 * sqrt(max(0.0, 1.0 - uv.x * uv.x * 0.5)) * (1.0 - 0.95 * blink);
    float open = smoothstep(lid, lid - 0.02, abs(uv.y));

    float r = length(uv);
    float a = atan(uv.y, uv.x);
    float rot = iTime * 0.15 + uMid * 2.0 * live;

    // Pupille: Bass öffnet
    float pr = 0.12 + 0.16 * uBass + 0.05 * uBeat;
    float irisR = 0.52;
    vec3 col = vec3(0.0);

    // Sklera: dunkles Technikfeld mit Rasterpunkten
    vec2 gp = fract(uv * 18.0) - 0.5;
    float dots = smoothstep(0.08, 0.04, length(gp));
    col += vec3(0.05, 0.08, 0.12) + vec3(0.1, 0.3, 0.4) * dots * 0.4;

    // Iris: radiale Fasern + Ringe, Spektrum als Zacken am Rand
    float fib = fbm(vec2(a * 6.0 + rot, r * 9.0 - iTime * 0.3));
    float rings = 0.5 + 0.5 * sin(r * 70.0 - iTime * 1.5 + fib * 6.0);
    float segs = step(0.5, fract((a + rot) / PI * 12.0));
    float specEdge = irisR + 0.06 * spec(fract((a + PI) / (2.0 * PI))) * live;
    float irisMask = smoothstep(pr + 0.01, pr + 0.03, r) * smoothstep(specEdge + 0.01, specEdge - 0.01, r);
    vec3 irisCol = mix(vec3(1.0, 0.45, 0.1), vec3(0.1, 0.9, 1.0), fib);
    irisCol = mix(irisCol, vec3(0.9, 0.1, 0.5), segs * 0.35);
    irisCol *= 0.45 + 0.55 * rings;
    irisCol *= 0.6 + 0.4 * (1.0 - smoothstep(pr, irisR, r));   // innen heller
    col = mix(col, irisCol * (0.7 + 0.5 * uRms + 0.3 * live), irisMask);

    // Pupille: schwarz mit rotem Kern-Glühen
    float pupil = smoothstep(pr + 0.012, pr - 0.012, r);
    vec3 pupilCol = vec3(0.02) + vec3(0.9, 0.05, 0.02) * (0.3 + 0.7 * uBass) * smoothstep(pr * 0.8, 0.0, r);
    col = mix(col, pupilCol, pupil);

    // Scanner-Linie, die über die Iris wandert
    float scanX = sin(iTime * 1.3) * irisR;
    col += vec3(1.0, 0.2, 0.1) * smoothstep(0.02, 0.0, abs(uv.x - scanX)) * irisMask * 0.8;

    // Beat-Impulsring, der nach außen läuft
    float ringR = irisR + (1.0 - uBeat) * 0.9;
    col += vec3(1.0, 0.3, 0.2) * smoothstep(0.03, 0.0, abs(r - ringR)) * uBeat * 1.5;

    // Lid anwenden, außerhalb dunkles Rauschen
    col = mix(vec3(0.01, 0.015, 0.02) + 0.02 * hash(uv + iTime), col, open);
    // Lidkante
    col += vec3(0.2, 0.6, 0.8) * smoothstep(0.015, 0.0, abs(abs(uv.y) - lid)) * step(abs(uv.x), 1.4);

    // CRT: Scanlines, Flimmern, Vignette
    col *= 0.85 + 0.15 * sin(vUv.y * iResolution.y * 3.14159);
    col *= 0.95 + 0.05 * sin(iTime * 60.0);
    col *= 1.0 - 0.5 * smoothstep(0.8, 1.9, length(vUv * 2.0 - 1.0));
    fragColor = vec4(col, 1.0);
}
