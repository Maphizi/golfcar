#version 140
// Startbildschirm Space-Taxi: Hintergrund je uBg (0 Raumstation-Skyline, 1 Asteroiden-Parkplatz mit
// Diner, 2 Nebel-Highway), Pilot als Hologramm über einem Projektor (uPhotoTex, Farbe uHolo),
// Accessoires (uAccessory 1 Sonnenbrille, 2 Taximütze, 3 beides), Neon-TAXI-Kasten, Schachbrettband.
// Reagiert auf Musik: Verkehr und Band laufen mit dem Bass, Fenster blinken zum Spektrum, Neon
// flackert zum Beat, Hologramm reißt bei Beats.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uPhotoTex;
uniform float uPhotoOK, uBg, uAccessory, uHolo, uSeed, uFree;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash1(float n) { n = fract(n * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.1 + 5.0; a *= 0.5; } return v; }
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
float sdBox(vec2 p, vec2 b, float r) { vec2 d = abs(p) - b + r; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r; }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }

vec3 skyline(vec2 p, vec2 uv, float t, float bass, float live) {
    vec3 col = mix(vec3(0.02, 0.02, 0.06), vec3(0.12, 0.05, 0.2), uv.y);
    col += vec3(0.5, 0.1, 0.4) * 0.3 * smoothstep(0.6, 0.0, uv.y);          // Stadtglühen
    // Sterne
    vec2 sc = floor(uv * vec2(200.0, 110.0));
    col += vec3(0.8) * step(0.992, hash12(sc + uSeed)) * uv.y;
    // Türme in zwei Ebenen
    for (int layer = 0; layer < 2; layer++) {
        float fl = float(layer);
        float sx = p.x * (3.0 + fl * 2.0) + uSeed + fl * 13.0;
        float id = floor(sx);
        float hgt = 0.18 + 0.45 * hash1(id + fl * 7.0) * (1.0 - fl * 0.4);
        float w = 0.3 + 0.6 * hash1(id + 2.0);
        float inside = step(abs(fract(sx) - 0.5), w * 0.5) * step(uv.y, hgt);
        vec3 tc = mix(vec3(0.05, 0.05, 0.1), vec3(0.02, 0.02, 0.04), fl);
        // Fenster blinken zum Spektrum
        vec2 win = floor(vec2(sx * 10.0, uv.y * 45.0));
        float lit = step(0.6, hash12(win + uSeed)) * step(0.5, spec(fract(hash12(win) * 2.0)) * 2.0 + hash12(win + floor(t * 0.5)) * 0.6);
        tc += vec3(1.0, 0.8, 0.4) * lit * step(abs(fract(sx * 10.0) - 0.5), 0.3) * step(abs(fract(uv.y * 45.0) - 0.5), 0.3) * 0.8 * (1.0 - fl * 0.5);
        col = mix(col, tc, inside);
    }
    // Flugverkehr: Lichtstreifen auf Höhenbändern
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float y = 0.3 + 0.45 * hash1(fi + uSeed);
        float dir = step(0.5, hash1(fi + 3.0)) * 2.0 - 1.0;
        float sp = (0.3 + 0.5 * hash1(fi + 5.0)) * (1.0 + 2.0 * bass * live);
        float x = mod(t * sp * dir + hash1(fi + 9.0) * 3.0, 2.4) - 1.2;
        float d = abs(p.y + 0.5 - y) * 60.0;
        float along = smoothstep(0.0, 0.25, dir * (x - p.x)) * step(0.0, dir * (x - p.x)) * step(dir * (x - p.x), 0.3);
        vec3 lc = mix(vec3(1.0, 0.3, 0.2), vec3(0.9, 0.95, 1.0), step(0.0, dir));
        col += lc * exp(-d * d) * (1.0 - along * 0.7) * step(abs(x - p.x), 0.3);
    }
    return col;
}
vec3 asteroids(vec2 p, vec2 uv, float t, float bass, float live) {
    vec3 col = mix(vec3(0.01, 0.01, 0.03), vec3(0.05, 0.03, 0.08), uv.y);
    vec2 sc = floor(uv * vec2(220.0, 120.0));
    col += vec3(0.9) * step(0.993, hash12(sc + uSeed + 1.0));
    // Felsbrocken, langsam driftend, mit Beleuchtung vom Diner
    for (int i = 0; i < 7; i++) {
        float fi = float(i);
        vec2 c = vec2(-0.9 + 1.8 * hash1(fi + uSeed), 0.35 + 0.5 * hash1(fi + 4.0)) + 0.03 * vec2(sin(t * 0.3 + fi), cos(t * 0.2 + fi));
        float r = 0.04 + 0.08 * hash1(fi + 8.0);
        vec2 d = p - vec2(c.x, c.y - 0.5);
        float rr = length(d) * (1.0 + 0.3 * noise(d * 20.0 + fi));
        float rock = step(rr, r);
        float shade = 0.3 + 0.7 * clamp(dot(normalize(d + 0.0001), vec2(0.6, -0.8)) * 0.5 + 0.5, 0.0, 1.0);
        col = mix(col, vec3(0.35, 0.3, 0.28) * shade * (0.6 + 0.4 * noise(d * 40.0)), rock);
    }
    // Diner rechts hinten: Kasten mit Fenstern und Neonkante
    float dn = rect(uv, vec2(0.62, 0.25), vec2(0.98, 0.45));
    col = mix(col, vec3(0.08, 0.07, 0.1), dn);
    col += vec3(1.0, 0.6, 0.2) * rect(uv, vec2(0.64, 0.3), vec2(0.96, 0.4)) * (0.5 + 0.5 * step(0.5, fract(uv.x * 20.0))) * 0.6;
    col += vec3(1.0, 0.2, 0.5) * (rect(uv, vec2(0.62, 0.45), vec2(0.98, 0.458))) * (0.7 + 0.3 * sin(t * 30.0) * step(0.9, hash1(floor(t * 4.0))));
    // Parkplatzmarkierungen
    col += vec3(0.3, 0.3, 0.1) * step(uv.y, 0.25) * step(0.9, fract(p.x * 4.0 + uv.y * 2.0)) * smoothstep(0.0, 0.25, uv.y);
    col += vec3(0.6, 0.3, 0.1) * 0.15 * step(uv.y, 0.25) * (0.5 + bass * live);
    return col;
}
vec3 highway(vec2 p, vec2 uv, float t, float bass, float live) {
    vec3 col = vec3(0.01, 0.01, 0.03);
    float n = fbm(vec2(p.x * 1.5 + t * 0.03, uv.y * 2.0 + uSeed));
    col += mix(vec3(0.3, 0.05, 0.4), vec3(0.05, 0.3, 0.5), n) * 0.5 * smoothstep(0.2, 0.9, n) * (0.6 + 0.6 * bass * live);
    vec2 sc = floor(uv * vec2(220.0, 120.0));
    col += vec3(0.9) * step(0.992, hash12(sc + uSeed + 2.0));
    // Fahrspur in Perspektive mit Leitlinien, die auf einen zu kommen
    float horizon = 0.42;
    if (uv.y < horizon) {
        float depth = (horizon - uv.y) / horizon;
        float z = 1.0 / max(depth, 0.02);
        float lx = p.x * z * 0.5;
        float lane = step(abs(lx), 1.6);
        vec3 road = vec3(0.04, 0.04, 0.07) * (0.3 + 0.7 * depth);
        float dash = step(0.5, fract(z * 0.4 - t * (1.5 + 4.0 * bass * live)));
        road += vec3(1.0, 0.85, 0.2) * step(abs(lx), 0.04) * dash * depth;
        road += vec3(0.3, 0.8, 1.0) * step(abs(abs(lx) - 1.6), 0.05) * depth;
        col = mix(col, road, lane * smoothstep(0.0, 0.05, depth));
    }
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = vUv;
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    float t = iTime;
    float live = 1.0 - uSilent;
    float bass = uBass * live, beat = uBeat * live;
    int bg = int(uBg + 0.5);
    vec3 col = bg == 0 ? skyline(p, uv, t, bass, live) : (bg == 1 ? asteroids(p, uv, t, bass, live) : highway(p, uv, t, bass, live));
    col *= 0.55;   // Hintergrund zurücknehmen, Text und Hologramm sollen vorn stehen

    // ---- Projektor und Hologramm des Piloten (links)
    vec3 hcol = uHolo < 0.5 ? vec3(0.35, 0.75, 1.0) : (uHolo < 1.5 ? vec3(1.0, 0.75, 0.3) : vec3(0.4, 1.0, 0.6));
    vec2 hc = vec2(-0.56, 0.11);                     // Mitte des Hologramms (p-Koordinaten)
    float hs = 0.62;                                  // Höhe
    vec2 hq = (p - hc) / hs + 0.5;                    // 0..1 Texturkoordinaten
    // Projektorsockel
    vec2 base = p - vec2(hc.x, hc.y - hs * 0.5 - 0.03);
    float sockel = step(sdBox(base, vec2(0.16, 0.025), 0.02), 0.0);
    col = mix(col, vec3(0.12, 0.13, 0.16), sockel);
    col += hcol * step(sdBox(base - vec2(0.0, 0.02), vec2(0.05, 0.006), 0.003), 0.0) * (0.6 + 0.4 * sin(t * 6.0));
    // Lichtkegel vom Sockel nach oben
    float cone = smoothstep(0.35, 0.0, abs(p.x - hc.x) / max(0.001, (p.y - (hc.y - hs * 0.5) + 0.05))) * step(hc.y - hs * 0.5, p.y) * step(p.y, hc.y + hs * 0.5);
    col += hcol * cone * 0.08;
    if (uPhotoOK > 0.5 && hq.x > 0.0 && hq.x < 1.0 && hq.y > 0.0 && hq.y < 1.0) {
        // Störungen: Zeilen verschieben sich bei Beats und ab und zu von selbst
        float band = floor(hq.y * 40.0);
        float glitchOn = step(0.93, hash12(vec2(band, floor(t * 7.0)))) * (0.4 + beat);
        float sh = (hash12(vec2(band, floor(t * 7.0) + 1.0)) - 0.5) * 0.08 * glitchOn;
        vec2 tq = vec2(hq.x + sh + 0.004 * sin(hq.y * 30.0 + t * 2.0), hq.y);
        vec4 s = texture(uPhotoTex, clamp(tq, 0.0, 1.0));
        vec4 sr = texture(uPhotoTex, clamp(tq + vec2(0.006 * (0.5 + glitchOn), 0.0), 0.0, 1.0));
        float lum = dot(s.rgb, vec3(0.3, 0.55, 0.15));
        vec3 holo = hcol * (0.25 + 1.1 * lum) + hcol * 0.4 * sr.a * (1.0 - s.a);
        // Accessoires in Texturkoordinaten (Augen bei (0.39, 0.61) und (0.59, 0.61))
        int acc = int(uAccessory + 0.5);
        if (acc == 1 || acc == 3) {
            float gl = step(sdBox(hq - vec2(0.39, 0.61), vec2(0.075, 0.045), 0.03), 0.0) + step(sdBox(hq - vec2(0.595, 0.61), vec2(0.075, 0.045), 0.03), 0.0);
            gl += step(sdBox(hq - vec2(0.49, 0.615), vec2(0.04, 0.006), 0.0), 0.0);
            holo = mix(holo, vec3(0.02), min(gl, 1.0) * s.a);
            holo += vec3(0.6) * min(gl, 1.0) * smoothstep(0.02, 0.0, abs((hq.x - hq.y) - (-0.14))) * s.a;
        }
        if (acc >= 2) {
            vec2 cap = hq - vec2(0.49, 0.80);
            float dome = step(length(cap * vec2(1.0, 1.9)), 0.26) * step(0.0, cap.y + 0.05);
            float brim = step(sdBox(hq - vec2(0.56, 0.72), vec2(0.26, 0.02), 0.01), 0.0);
            float checker = step(0.5, fract(hq.x * 16.0)) == step(0.5, fract(hq.y * 16.0)) ? 1.0 : 0.0;
            // dunkle Mütze mit gelbem Schachbrettband und schwarzem Schirm, hebt sich von jeder Hologrammfarbe ab
            vec3 capc = vec3(0.10, 0.11, 0.16) * (0.6 + 0.8 * smoothstep(-0.1, 0.12, cap.y));
            float bandRow = step(abs(cap.y + 0.02), 0.03);
            capc = mix(capc, mix(vec3(0.95, 0.8, 0.15), vec3(0.05), checker), bandRow);
            capc = mix(capc, vec3(0.03), brim * (1.0 - dome));
            holo = mix(holo, capc * (0.7 + 0.5 * lum), max(dome, brim));
            s.a = max(s.a, max(dome, brim));
        }
        float scan = 0.75 + 0.25 * step(0.5, fract(hq.y * 120.0 + t * 3.0));
        float flicker = 0.85 + 0.15 * hash1(floor(t * 18.0)) + 0.1 * beat;
        float alpha = s.a * (0.8 + 0.2 * sin(hq.y * 6.0 + t * 2.0)) * (1.0 - glitchOn * 0.4);
        col = mix(col, holo * scan * flicker, alpha * 0.92);
        col += hcol * 0.12 * alpha;
    }
    // Hologrammrahmen (Ecken)
    vec2 fq = abs(p - hc) - vec2(hs * 0.42, hs * 0.5);
    float corner = step(abs(fq.x), 0.004) * step(fq.y, 0.0) * step(-0.08, fq.y) + step(abs(fq.y), 0.004) * step(fq.x, 0.0) * step(-0.08, fq.x);
    col += hcol * corner * 0.7;

    // ---- Neon-TAXI-Kasten oben rechts (Text per Overlay darüber: "SPACE-TAXI NR.")
    vec2 nb = p - vec2(0.0, 0.425);
    float box = step(sdBox(nb, vec2(0.52, 0.055), 0.02), 0.0);
    float frame = box - step(sdBox(nb, vec2(0.51, 0.045), 0.015), 0.0);
    float neonFlick = 0.7 + 0.3 * step(0.15, hash1(floor(t * 12.0))) + 0.3 * beat;
    col = mix(col, vec3(0.04, 0.03, 0.02), box * 0.85);
    col += vec3(1.0, 0.85, 0.2) * frame * neonFlick;
    col += vec3(1.0, 0.8, 0.2) * 0.15 * smoothstep(0.08, 0.0, sdBox(nb, vec2(0.52, 0.055), 0.02)) * neonFlick;
    // ---- Schachbrettband unten, läuft mit dem Bass
    float bandY = step(0.088, uv.y) * step(uv.y, 0.112);
    float ck = step(0.5, fract(uv.x * 30.0 - t * (0.3 + 1.5 * bass))) == step(0.5, fract(uv.y * 66.0)) ? 1.0 : 0.0;
    col = mix(col, mix(vec3(0.95, 0.8, 0.15), vec3(0.03), ck), bandY);
    // dunkle Leisten für Lizenztext und Spruch
    col = mix(col, vec3(0.02, 0.02, 0.03), rect(uv, vec2(0.03, 0.12), vec2(0.46, 0.3)) * 0.0);
    col = mix(col, vec3(0.0), rect(uv, vec2(0.0, 0.0), vec2(1.0, 0.088)) * 0.6);
    // FREI/BESETZT-Lampe rechts oben
    col += (uFree > 0.5 ? vec3(0.2, 1.0, 0.4) : vec3(1.0, 0.3, 0.2)) * 0.15 * smoothstep(0.2, 0.0, length((uv - vec2(0.885, 0.925)) * vec2(aspect, 1.0)));

    col *= 1.0 - 0.35 * pow(length(uv - 0.5) * 1.3, 2.0);
    fragColor = vec4(col, 1.0);
}
