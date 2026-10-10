#version 140
// GNN-Holo-Studio: blauer Studiohintergrund mit Lichtkegeln, drehender Holo-Globus, Droiden-Sprecher
// am Pult, Bauchbinde (dunkles Feld unten links für die Meldung), Laufband unten, Eilmeldungsbalken,
// Wetterpanel rechts. Text zeichnet der Controller als Overlay.
// uState 3 = spricht (Mund bewegt sich mit uRms), uBreaking, uPanel, uTalk.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uState, uStateT, uLevel, uBreaking, uPanel, uTalk;

const vec3 BLUE = vec3(0.08, 0.25, 0.6);
const vec3 CYAN = vec3(0.3, 0.8, 1.0);
const vec3 GOLD = vec3(1.0, 0.84, 0.1);
const vec3 RED = vec3(0.95, 0.2, 0.15);
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }
float sdBox(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = vUv;
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    float t = iTime;
    float talk = uTalk * (0.3 + 2.0 * uRms);

    // ---- Studio: Verlauf, Lichtkegel, Sterne hinter Glas, Bodenreflex
    vec3 col = mix(vec3(0.02, 0.03, 0.08), BLUE * 0.35, smoothstep(0.0, 1.0, uv.y));
    col += BLUE * 0.25 * smoothstep(0.6, 0.0, abs(p.x)) * smoothstep(0.2, 0.9, uv.y);
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float ang = sin(t * 0.3 + fi * 2.1) * 0.5;
        vec2 q = rot(ang) * (p - vec2(-0.6 + fi * 0.6, 0.6));
        col += CYAN * 0.08 * smoothstep(0.05, 0.0, abs(q.x)) * smoothstep(0.0, -1.0, q.y);
    }
    vec2 sc = floor(uv * vec2(160.0, 90.0));
    col += vec3(0.6, 0.7, 0.9) * step(0.985, hash12(sc)) * step(0.5, uv.y) * (0.5 + 0.5 * sin(t * 2.0 + hash12(sc + 1.0) * 6.28));
    float floorY = 0.36;
    if (uv.y < floorY) {
        col = mix(vec3(0.03, 0.04, 0.08), BLUE * 0.3, smoothstep(floorY, 0.0, uv.y));
        col += CYAN * 0.06 * step(0.96, fract(p.x * 6.0)) * (floorY - uv.y) * 4.0;
    }
    // ---- Holo-Globus rechts oben (Breiten- und Längenkreise, dreht)
    vec2 gc = vec2(0.52, 0.2);
    vec2 g = (p - gc) / 0.17;
    float r = length(g);
    if (r < 1.0) {
        float z = sqrt(1.0 - r * r);
        float lon = atan(g.x, z) + t * 0.4;
        float lat = asin(clamp(g.y, -1.0, 1.0));
        float lines = step(0.92, fract(lon * 2.0)) + step(0.92, fract(lat * 2.5));
        float land = step(0.55, hash12(floor(vec2(lon * 3.0, lat * 3.0)) + 5.0));
        vec3 gcol = mix(CYAN * 0.25, CYAN * 0.6, land) * (0.4 + 0.6 * z);
        gcol += CYAN * lines * 0.5;
        col = mix(col, gcol, 0.85);
    }
    col += CYAN * 0.25 * smoothstep(0.08, 0.0, abs(r - 1.0)) * step(0.0, 1.2 - r);
    // ---- Sprecher: Droidenkopf mit Mundbalken, hinter dem Pult, leicht wippend beim Sprechen
    vec2 ac = vec2(-0.5, -0.03 + 0.005 * sin(t * 3.0) * uTalk);
    vec2 a = p - ac;
    float head = step(sdBox(a, vec2(0.11, 0.13)), 0.0);
    float dome = step(length((a - vec2(0.0, 0.13)) * vec2(1.0, 1.6)), 0.11);
    vec3 skin = vec3(0.75, 0.78, 0.85);
    col = mix(col, skin, max(head, dome));
    col = mix(col, vec3(0.2, 0.22, 0.28), step(sdBox(a - vec2(0.0, 0.0), vec2(0.09, 0.1)), 0.0) * head);
    float eyeL = step(length(a - vec2(-0.045, 0.05)), 0.022), eyeR = step(length(a - vec2(0.045, 0.05)), 0.022);
    float blink = step(0.97, fract(t * 0.19));
    col = mix(col, CYAN * (0.8 + 0.4 * uTalk), (eyeL + eyeR) * (1.0 - blink));
    for (int i = 0; i < 5; i++) {
        float fi = float(i) - 2.0;
        float h = 0.006 + 0.03 * talk * (0.5 + 0.5 * sin(t * 23.0 + fi * 1.7));
        col = mix(col, GOLD, step(sdBox(a - vec2(fi * 0.028, -0.055), vec2(0.009, h)), 0.0));
    }
    // Schultern und Pult
    col = mix(col, skin * 0.8, step(sdBox(a - vec2(0.0, -0.22), vec2(0.2, 0.07)), 0.0) * step(-0.27, a.y));
    float desk = rect(uv, vec2(0.0, 0.0), vec2(1.0, 0.36));
    col = mix(col, mix(vec3(0.05, 0.07, 0.12), BLUE * 0.5, smoothstep(0.36, 0.0, uv.y)), desk * step(uv.y, 0.36) * 0.0);
    // ---- Bauchbinde: dunkles Feld für Ressort, Schlagzeile und Meldung (unten links)
    float band = rect(uv, vec2(0.04, 0.095), vec2(0.72, 0.37));
    col = mix(col, vec3(0.02, 0.03, 0.06), band * 0.88);
    col += GOLD * (rect(uv, vec2(0.04, 0.365), vec2(0.72, 0.372)) + rect(uv, vec2(0.04, 0.095), vec2(0.047, 0.372)));
    col += mix(CYAN, RED, uBreaking) * rect(uv, vec2(0.04, 0.095), vec2(0.72, 0.1)) * (0.6 + 0.4 * sin(t * 4.0));
    // Eilmeldung: roter Balken oben, blinkend
    col = mix(col, RED * (0.6 + 0.4 * step(0.5, fract(t * 2.0))), uBreaking * rect(uv, vec2(0.0, 0.88), vec2(1.0, 0.91)));
    // ---- Wetterpanel rechts
    float panel = rect(uv, vec2(0.76, 0.45), vec2(0.96, 0.8)) * uPanel;
    col = mix(col, vec3(0.02, 0.03, 0.06), panel * 0.85);
    col += CYAN * uPanel * (rect(uv, vec2(0.76, 0.795), vec2(0.96, 0.8)) + rect(uv, vec2(0.76, 0.45), vec2(0.763, 0.8)));
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        vec2 pc = vec2(0.80, 0.70 - fi * 0.075);
        float pr = length((uv - pc) * vec2(aspect, 1.0));
        vec3 pcol = i == 0 ? vec3(0.8, 0.9, 1.0) : (i == 1 ? vec3(0.9, 0.7, 0.3) : vec3(0.5, 0.8, 0.4));
        col = mix(col, pcol * (0.6 + 0.4 * step(0.5, fract(pr * 20.0 + t * 0.3))), step(pr, 0.018) * uPanel);
    }
    // ---- Laufband unten: dunkle Leiste, LIVE-Punkt
    col = mix(col, vec3(0.02, 0.02, 0.04), rect(uv, vec2(0.0, 0.0), vec2(1.0, 0.075)) * 0.9);
    col += GOLD * rect(uv, vec2(0.0, 0.075), vec2(1.0, 0.079));
    col = mix(col, RED * (0.5 + 0.5 * step(0.5, fract(t))), step(length((uv - vec2(0.955, 0.955)) * vec2(aspect, 1.0)), 0.012));
    col += CYAN * 0.15 * step(0.5, fract(uv.y * 160.0)) * 0.3;    // Holo-Linien
    col *= 1.0 - 0.3 * pow(length(uv - 0.5) * 1.3, 2.0);
    fragColor = vec4(col, 1.0);
}
