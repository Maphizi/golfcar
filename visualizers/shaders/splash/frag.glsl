#version 140
// Startbildschirm: Titelbild (uPlate, 3:2) bildfüllend auf 16:9 beschnitten (uCrop oben/unten), lebendig zur Musik:
// Sonne (uSun) glüht mit dem Bass und wirft drehende Lichtstrahlen (Energie), Beat = Zoom-Stoß, Höhen = Staub und
// Funken, Drop = Weißblitz (uFlash). Daneben der Knopf (uButton = x, y, Breite, Höhe): Neonpille in Bernstein/Orange,
// glüht mit dem Bass, hüpft auf den Beat, Lauflicht am Rand; der Text kommt als Overlay vom Controller.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uPlate;
uniform vec2 uPlateSize, uSun, uCrop;
uniform vec4 uButton;
uniform float uPlateOK, uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uFlash, uAge;

const float PI = 3.14159265;
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
float sq(float x) { return x * x; }
float ex(float x) { return exp(max(x, -60.0)); }
vec3 bilin(sampler2D tex, vec2 uv, vec2 size) {
    vec2 px = clamp(uv, 0.0, 1.0) * size - 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 lo = vec2(0.0), hi = size - 1.0;
    vec2 p00 = clamp(i, lo, hi), p11 = clamp(i + 1.0, lo, hi);
    vec3 a = texelFetch(tex, ivec2(p00), 0).rgb, b = texelFetch(tex, ivec2(p11.x, p00.y), 0).rgb;
    vec3 c = texelFetch(tex, ivec2(p00.x, p11.y), 0).rgb, d = texelFetch(tex, ivec2(p11), 0).rgb;
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float sdRoundRect(vec2 p, vec2 b, float r) { vec2 q = abs(p) - b + r; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    // ---- Bild: Beschnitt auf 16:9, Beat-Zoom um die Mitte, leichtes Atmen in der Stille
    vec2 uv = vUv;
    float zoom = 1.0 + 0.025 * uBeatPulse * live + 0.01 * sin(t * 0.5) * (1.0 - live) + 0.02 * uFlash;
    uv = 0.5 + (uv - 0.5) / zoom;
    vec2 puv = vec2(uv.x, uCrop.y + uv.y * (1.0 - uCrop.x - uCrop.y));              // Bildanteil (y von unten)
    vec3 col = uPlateOK > 0.5 ? bilin(uPlate, puv, uPlateSize) : vec3(0.05, 0.03, 0.02);
    float lum = dot(col, vec3(0.3, 0.55, 0.15));
    // ---- Sonne: glüht mit dem Bass, Strahlen drehen sich, Stärke mit der Energie
    vec2 sd = (uv - uSun) * vec2(aspect, 1.0);
    float sr = length(sd);
    float ang = atan(sd.y, sd.x);
    float rays = pow(0.5 + 0.5 * sin(ang * 14.0 + t * 0.35 + uSeed), 5.0) + 0.6 * pow(0.5 + 0.5 * sin(ang * 23.0 - t * 0.22), 7.0);
    rays *= smoothstep(0.02, 0.25, sr) * ex(-sr * 2.2);
    vec3 warm = vec3(1.0, 0.72, 0.35);
    col += warm * rays * (0.12 + 0.35 * uEnergy + 0.25 * uBassS) * live;
    col += warm * ex(-sr * 9.0) * (0.25 + 0.9 * uBassS) * live;                                  // Sonnenglut
    col += col * smoothstep(0.55, 0.95, lum) * (0.3 * uBassS + 0.25 * uBeatPulse) * live;         // helle Stellen (Scheinwerfer, Streifen) blitzen
    // ---- Staub und Funken in den Höhen: steigen aus dem unteren Bildteil auf
    float dust = 0.0;
    for (int k = 0; k < 24; k++) {
        float fk = float(k);
        float hx = hash12(vec2(fk, uSeed)), hy = hash12(vec2(fk + 40.0, uSeed)), hs = hash12(vec2(fk + 80.0, uSeed));
        float age = fract(t * (0.05 + 0.08 * hs) + hy);
        vec2 p = vec2(hx + 0.03 * sin(t * (0.7 + hs) + fk), 0.15 + age * 0.85);
        float d = length((uv - p) * vec2(aspect, 1.0));
        dust += smoothstep(0.004 + 0.003 * hs, 0.0, d) * (1.0 - age) * (0.3 + 0.7 * uHighS);
    }
    col += vec3(1.0, 0.8, 0.5) * dust * (0.5 + 0.5 * live);
    // Kleine Glutpunkte am Boden flackern mit den Höhen
    float ember = step(0.985, hash12(floor(uv * vec2(90.0, 50.0)) + floor(t * 6.0 + uBeatStep))) * smoothstep(0.4, 0.1, uv.y) * uHighS * live;
    col += vec3(1.0, 0.6, 0.3) * ember * 0.8;
    // ---- Drop: Weißblitz
    col = mix(col, vec3(1.0, 0.95, 0.85), uFlash * 0.6);
    // ---- Knopf: Neonpille, glüht mit dem Bass, hüpft auf den Beat, Lauflicht am Rand
    vec2 bc = vec2(uButton.x, uButton.y + 0.012 * uBeatPulse);
    vec2 bhalf = vec2(uButton.z * 0.5 * aspect, uButton.w * 0.5) * (1.0 + 0.04 * uBeatPulse + 0.02 * sin(t * 3.0));
    vec2 bp = (vUv - bc) * vec2(aspect, 1.0);
    float r = min(bhalf.x, bhalf.y);
    float dBtn = sdRoundRect(bp, bhalf, r);
    float glowAmt = 0.55 + 0.45 * uBassS * live + 0.3 * uBeatPulse + 0.15 * sin(t * 2.0) * (1.0 - live);
    vec3 neon = mix(vec3(1.0, 0.55, 0.12), vec3(1.0, 0.85, 0.3), 0.5 + 0.5 * sin(t * 1.3 + uBassS * 3.0));
    float halo = ex(-max(dBtn, 0.0) * 28.0) * glowAmt;
    col += neon * halo * 0.9;
    float body = smoothstep(0.004, -0.004, dBtn);
    vec3 bodyCol = mix(vec3(0.25, 0.08, 0.02), neon * 0.55, 0.5 + 0.5 * sin(bp.y * 40.0 + t * 2.0)) * (0.8 + 0.4 * glowAmt);
    bodyCol += neon * 0.25 * smoothstep(0.0, bhalf.y, bp.y + bhalf.y) * 0.5;                      // heller nach oben
    float rim = smoothstep(0.006, 0.0, abs(dBtn)) * (0.8 + 0.6 * glowAmt);
    float runner = pow(0.5 + 0.5 * sin(atan(bp.y, bp.x) * 3.0 - t * 4.0 - uBeatStep * 0.8), 8.0);     // Lauflicht am Rand
    col = mix(col, bodyCol, body);
    col += neon * rim * (0.9 + 1.2 * runner);
    col += vec3(1.0) * rim * runner * 0.4 * uBeatPulse;
    // Vignette und Einblendung beim Start
    float vig = smoothstep(1.3, 0.5, length((vUv - 0.5) * vec2(1.3, 1.0)));
    col *= 0.75 + 0.25 * vig;
    col *= smoothstep(0.0, 1.5, uAge);
    fragColor = vec4(col, 1.0);
}
