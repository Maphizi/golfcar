#version 140
// F3 – Zielcomputer: gelber Drahtgitter-Graben in Perspektive, rote Querbalken, Zähler, Statusfelder,
// Waveform im unteren Fenster, Spektrum als Grabenwände. Gelb/Rot/Cyan auf Schwarz, Pixel-Look.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;

const vec3 YEL = vec3(1.0, 0.85, 0.1);
const vec3 RED = vec3(1.0, 0.2, 0.1);
const vec3 CYN = vec3(0.2, 0.9, 0.9);
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }
float wave(float x) { return texture(uAudioTex, vec2(x, 0.75)).r * 2.0 - 1.0; }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }
float frame(vec2 uv, vec2 a, vec2 b, float w) { return rect(uv, a, b) - rect(uv, a + w, b - w); }
int font[10] = int[10](31599, 11415, 29671, 29647, 23497, 31183, 31215, 29257, 31727, 31695);
float digit(int d, vec2 p) {
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    int bit = 14 - ((4 - int(p.y * 5.0)) * 3 + int(p.x * 3.0));
    return float((font[d] >> bit) & 1);
}
// Fremde Schriftzeichen: 3x5-Muster aus einem Hash, eckig wie auf einem Bordmonitor
float glyph(float id, vec2 p) {
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    vec2 c = floor(p * vec2(3.0, 5.0));
    float v = hash(vec2(id, c.x + c.y * 3.0));
    float on = step(0.45, v);
    on = max(on, step(4.0, c.y) * step(0.3, hash(vec2(id, 99.0))));   // oft eine Kopfzeile
    return on;
}
float text(vec2 uv, vec2 pos, float n, float seed, vec2 sz) {
    vec2 p = (uv - pos) / sz;
    float i = floor(p.x / 1.4);
    if (i < 0.0 || i >= n) return 0.0;
    return glyph(seed + i, vec2(fract(p.x / 1.4) * 1.4, p.y));
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    // Pixelraster 240 Zeilen
    vec2 uv = (floor(vUv * vec2(240.0 * aspect, 240.0)) + 0.5) / vec2(240.0 * aspect, 240.0);
    float px = 1.0 / 240.0;
    float live = 1.0 - uSilent;
    vec3 col = vec3(0.0);

    // ---- Oberes Fenster: Graben in Perspektive (uv 0.3..0.7 x, 0.5..0.92 y)
    vec2 A = vec2(0.30, 0.50), B = vec2(0.70, 0.92);
    col += YEL * frame(uv, A, B, 1.5 * px);
    if (rect(uv, A + 2.0 * px, B - 2.0 * px) > 0.5) {
        vec2 q = (uv - (A + B) * 0.5) / ((B - A) * 0.5);       // -1..1 im Fenster
        float W = (B.x - A.x) * aspect / (B.y - A.y);           // Fensterbreite in Höheneinheiten
        q.x *= W;
        float m = max(abs(q.x) / W, abs(q.y));                 // verschachtelte Rechtecke = Tiefe
        float speed = 1.5 + 8.0 * uBass * live;
        float z = -log(max(m, 0.001)) * 3.0 + iTime * speed;
        float fz = fract(z);
        float rung = smoothstep(0.07, 0.0, min(fz, 1.0 - fz)) * smoothstep(0.0, 0.12, m);
        float red = step(3.0, mod(floor(z), 4.0));              // jede vierte Querstrebe rot
        // Fluchtlinien zu Ecken und Seitenmitten
        float lines = 0.0;
        for (int k = 0; k < 8; k++) {
            float ang = float(k) * 0.7854;                      // 45°-Schritte
            vec2 dir = vec2(cos(ang) * W, sin(ang));
            dir = normalize(dir);
            float d = abs(q.x * dir.y - q.y * dir.x);
            lines += smoothstep(1.5 * px, 0.0, d) * step(0.0, dot(q, dir));
        }
        float fog = smoothstep(0.0, 0.15, m);
        col += YEL * clamp(lines, 0.0, 1.0) * fog * 0.9;
        col += mix(YEL, RED, red) * rung * 0.9;
        // Spektrum: Wandsegmente leuchten (links/rechts nach Frequenz)
        float s = spec(fract(0.5 + q.x / W * 0.5)) * live;
        col += YEL * s * 0.4 * step(abs(q.y), abs(q.x) / W) * fog;
        // Fadenkreuz
        col += CYN * (smoothstep(1.2 * px, 0.0, abs(q.x)) + smoothstep(1.2 * px, 0.0, abs(q.y))) * step(length(q), 0.12);
    }

    // ---- Zähler unter dem Fenster (rot, rollt mit der Zeit, Beat stört)
    {
        int n = int(mod(iTime * 37.0 + uBeat * 900.0, 1000000.0));
        vec2 sz = vec2(0.011, 0.028);
        float x0 = 0.43;
        for (int i = 0; i < 6; i++) {
            int d = (n / int(pow(10.0, float(5 - i)))) % 10;
            col += RED * digit(d, (uv - vec2(x0 + float(i) * 0.024, 0.44)) / sz);
        }
        col += RED * frame(uv, vec2(0.41, 0.425), vec2(0.60, 0.485), 1.0 * px);
    }

    // ---- Unteres Fenster: Waveform als Scanner (uv 0.3..0.7 x, 0.1..0.4 y)
    vec2 C = vec2(0.30, 0.10), D = vec2(0.70, 0.40);
    col += YEL * frame(uv, C, D, 1.5 * px);
    if (rect(uv, C + 2.0 * px, D - 2.0 * px) > 0.5) {
        vec2 q = (uv - C) / (D - C);
        // grüner Zielkreis mit Sweep
        vec2 c = (q - 0.5) * vec2(aspect * (D.x - C.x) / (D.y - C.y), 1.0);
        float rr = length(c);
        col += vec3(0.2, 0.8, 0.3) * 0.5 * (smoothstep(1.5 * px, 0.0, abs(rr - 0.35)) + smoothstep(1.5 * px, 0.0, abs(rr - 0.18)));
        float ang = atan(c.y, c.x);
        float sweep = fract((ang / 6.2832) - iTime * 0.25);
        col += vec3(0.2, 0.8, 0.3) * 0.35 * pow(1.0 - sweep, 6.0) * step(rr, 0.35);
        // Waveform
        float y0 = 0.5 + wave(q.x) * 0.3 * (0.3 + 0.7 * live);
        col += YEL * smoothstep(2.5 * px, 0.0, abs(q.y - y0)) * (0.6 + 0.4 * uRms);
        // rote Zielmarken, die bei Bass zusammenfahren
        float gap = 0.25 - 0.15 * uBass * live;
        for (int k = 0; k < 4; k++) {
            vec2 m = vec2(k < 2 ? -gap : gap, (k % 2 == 0) ? -gap : gap) * 0.5;
            col += RED * smoothstep(0.03, 0.02, length(c - m));
        }
    }

    // ---- Seitliche Statusfelder (links cyan/rot, rechts weiß/rot), reagieren auf Bänder
    for (int k = 0; k < 3; k++) {
        float y = 0.82 - float(k) * 0.11;
        float lvl = (k == 0) ? uBass : (k == 1 ? uMid : uHigh);
        vec3 c1 = (k == 0) ? CYN : (k == 1 ? RED : YEL);
        col += c1 * rect(uv, vec2(0.14, y - 0.04), vec2(0.22, y + 0.04)) * (0.25 + 0.75 * step(0.5 - lvl * 0.6, fract(iTime * (1.0 + lvl * 4.0))));
        col += vec3(0.0) * 0.0;
        // rechts: Kreise mit Balken
        vec2 cc = (uv - vec2(0.82, y)) * vec2(aspect, 1.0);
        float ring = smoothstep(0.04, 0.038, length(cc)) * (0.9);
        float bar = rect(cc, vec2(-0.03, -0.006), vec2(-0.03 + 0.06 * lvl, 0.006));
        col = mix(col, mix(vec3(0.95), RED, bar), ring);
    }
    // ---- Fremde Schrift: Kopfzeile und Statuszeile
    col += YEL * 0.9 * text(uv, vec2(0.31, 0.945), 10.0, 3.0, vec2(0.012, 0.028));
    col += CYN * 0.8 * text(uv, vec2(0.31, 0.03), 14.0, 17.0, vec2(0.009, 0.022));
    // Rahmen außen und Beat-Blitz
    col += YEL * 0.5 * frame(uv, vec2(0.04, 0.02), vec2(0.96, 0.98), 1.0 * px);
    col *= 1.0 + 0.2 * uBeat * live;
    col *= 0.9 + 0.1 * sin(vUv.y * iResolution.y * 3.14159 * 0.5);
    fragColor = vec4(col, 1.0);
}
