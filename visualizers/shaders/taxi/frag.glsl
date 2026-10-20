#version 140
// Taxistand / Themenwahl. Links ein großes Plakat des Themas (eigenes Bild uCoverTex oder ein vom
// Shader gezeichnetes Plakat nach uCoverStyle), rechts das Fahrerplakat: Pilotenporträt in
// Duotone (uTint) mit Accessoires, darüber Sternenhimmel. Sterne, Band und Neon reagieren auf Musik.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uPhotoTex, uCoverTex;
uniform float uPhotoOK, uCoverOK, uCoverStyle, uAccessory, uSlide, uConfirm, uChosen, uSeed;
uniform vec3 uColA, uColB, uTint;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash1(float n) { n = fract(n * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.1 + 5.0; a *= 0.5; } return v; }
float sdBox(vec2 p, vec2 b, float r) { vec2 d = abs(p) - b + r; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r; }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

// ---- Gezeichnete Plakate. q: 0..1 im Plakat (x über die Breite, y nach oben), Seitenverhältnis 2:3
vec3 posterRocket(vec2 q, float t, float bass) {
    vec3 col = vec3(0.0);
    vec2 p = (q - 0.5) * vec2(2.0, 3.0);                 // -1..1 breit, -1.5..1.5 hoch
    // Mond groß hinter der Rakete
    vec2 mc = p - vec2(0.0, 0.35);
    float mr = length(mc);
    if (mr < 0.75) {
        float z = sqrt(1.0 - mr * mr / 0.5625);
        float crat = fbm(mc * 9.0 + uSeed) ;
        vec3 moon = mix(vec3(0.55, 0.65, 0.78), vec3(0.85, 0.92, 1.0), smoothstep(0.35, 0.7, crat)) * (0.35 + 0.75 * z);
        moon *= 0.8 + 0.2 * noise(mc * 40.0);
        col = moon;
    }
    col += uColB * 0.6 * smoothstep(0.1, 0.0, abs(mr - 0.75)) * step(0.75, mr);   // Mondsaum
    // Rakete: Zylinder mit Spitze und drei Flossen, Metall mit Lichtkante
    vec2 r = p - vec2(0.0, 0.1 + 0.01 * sin(t * 1.5));
    float body = step(abs(r.x), 0.13) * step(-0.75, r.y) * step(r.y, 0.55);
    float nose = step(abs(r.x), 0.13 * (1.0 - smoothstep(0.55, 1.05, r.y))) * step(0.55, r.y) * step(r.y, 1.05);
    float finL = step(0.0, -r.x - 0.13) * step(-r.x - 0.13, 0.17 * smoothstep(-0.3, -0.8, r.y)) * step(-0.85, r.y) * step(r.y, -0.3);
    float finR = step(0.0, r.x - 0.13) * step(r.x - 0.13, 0.17 * smoothstep(-0.3, -0.8, r.y)) * step(-0.85, r.y) * step(r.y, -0.3);
    float finT = step(0.0, r.x - 0.13) * step(r.x - 0.13, 0.12 * smoothstep(0.75, 0.45, r.y)) * step(0.45, r.y) * step(r.y, 0.8);
    float rocket = max(max(body, nose), max(max(finL, finR), finT));
    float shade = 0.45 + 0.7 * smoothstep(-0.13, 0.08, r.x) * smoothstep(0.13, 0.0, r.x);
    vec3 metal = vec3(0.78, 0.82, 0.88) * shade;
    metal *= 1.0 - 0.35 * step(0.5, fract(r.y * 9.0)) * step(0.1, r.y) * step(r.y, 0.55) * step(abs(r.x), 0.11);   // Rillen
    metal = mix(metal, vec3(0.12), step(0.9, r.y) * step(0.5, fract((r.x + r.y) * 20.0)) * step(0.5, fract((r.x - r.y) * 20.0)));
    col = mix(col, metal, rocket);
    // Triebwerksflamme
    float fl = smoothstep(0.12 + 0.08 * bass, 0.0, abs(r.x) / max(0.001, 1.0 + (r.y + 0.75) * 1.2)) * step(r.y, -0.75) * step(-1.45, r.y);
    fl *= 0.5 + 0.5 * noise(vec2(r.x * 20.0, r.y * 6.0 - t * 12.0));
    col += mix(uColB, vec3(0.9, 0.95, 1.0), fl) * fl * (1.5 + 2.0 * bass) * smoothstep(-1.45, -0.75, r.y);
    return col;
}
vec3 posterFortress(vec2 q, float t, float bass) {
    vec2 p = (q - 0.5) * vec2(2.0, 3.0);
    vec3 col = vec3(0.0);
    // rote Sonne hinter einer Planetenkante
    float sun = length(p - vec2(0.3, 0.9));
    col += uColA * smoothstep(0.55, 0.0, sun) * 0.9 + uColA * 0.3 * smoothstep(1.2, 0.3, sun);
    float planet = length((p - vec2(0.0, -2.0)) * vec2(1.0, 0.6));
    col = mix(col, vec3(0.08, 0.08, 0.12), smoothstep(1.55, 1.5, planet));
    col += uColA * 0.5 * smoothstep(0.08, 0.0, abs(planet - 1.52));
    // Festung: gestufte Silhouette mit Fensterreihen
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        float w = 0.55 - fi * 0.1, h = -0.55 + fi * 0.28;
        float tower = step(abs(p.x - 0.1 * sin(fi * 2.0)), w) * step(-0.6, p.y) * step(p.y, h);
        col = mix(col, vec3(0.05, 0.05, 0.08), tower);
        vec2 wc = floor(vec2(p.x * 18.0, p.y * 14.0));
        float win = step(0.5, fract(p.x * 18.0 + 0.25)) * step(0.5, fract(p.y * 14.0 + 0.25)) * step(0.4, hash12(wc + uSeed + floor(t * 0.3 + hash12(wc) * 3.0) * 0.0));
        col += uColA * win * tower * 0.5 * (0.5 + 0.5 * step(0.3, hash12(wc + floor(t * 0.5))));
    }
    // Scheinwerfer
    float beam = smoothstep(0.06, 0.0, abs(p.x + 0.2 - (p.y - 0.4) * sin(t * 0.4) * 0.6)) * smoothstep(-0.4, 0.4, p.y) * smoothstep(1.5, 0.4, p.y);
    col += uColA * beam * 0.25;
    return col;
}
vec3 posterDiner(vec2 q, float t, float bass) {
    vec2 p = (q - 0.5) * vec2(2.0, 3.0);
    vec3 col = vec3(0.01, 0.01, 0.03);
    // Asteroid mit Diner, Neonschrift als Balken
    float rock = length((p - vec2(0.0, -0.9)) * vec2(1.0, 1.6));
    col = mix(col, vec3(0.22, 0.2, 0.19) * (0.6 + 0.5 * noise(p * 18.0)), step(rock, 1.0));
    float diner = step(sdBox(p - vec2(0.0, -0.1), vec2(0.6, 0.22), 0.08), 0.0);
    col = mix(col, vec3(0.1, 0.1, 0.14), diner);
    float win = step(sdBox(p - vec2(0.0, -0.08), vec2(0.5, 0.1), 0.02), 0.0) * step(0.5, fract(p.x * 6.0));
    col += mix(uColB, vec3(1.0, 0.8, 0.5), 0.5) * win * 0.8;
    float neon = step(sdBox(p - vec2(0.0, 0.26), vec2(0.5, 0.04), 0.03), 0.0) - step(sdBox(p - vec2(0.0, 0.26), vec2(0.47, 0.015), 0.01), 0.0);
    float flick = 0.7 + 0.3 * step(0.2, hash1(floor(t * 10.0) + uSeed)) + 0.4 * bass;
    col += uColA * neon * flick;
    col += uColA * 0.2 * smoothstep(0.2, 0.0, sdBox(p - vec2(0.0, 0.26), vec2(0.5, 0.04), 0.03)) * flick;
    // Gleiter mit Positionslicht, parkend
    float ship = step(sdBox(rot(0.15) * (p - vec2(0.45, -0.6)), vec2(0.22, 0.05), 0.04), 0.0);
    col = mix(col, vec3(0.5, 0.52, 0.58), ship);
    col += vec3(1.0, 0.2, 0.2) * step(0.5, fract(t * 1.5)) * smoothstep(0.03, 0.0, length(p - vec2(0.62, -0.57)));
    // Neonschein auf dem Asteroiden
    col += uColA * 0.15 * step(rock, 1.0) * smoothstep(-0.6, -0.3, p.y);
    return col;
}
vec3 posterRetro(vec2 q, float t, float bass) {
    vec2 p = (q - 0.5) * vec2(2.0, 3.0);
    vec3 col = mix(vec3(0.02, 0.02, 0.06), uColB * 0.25, smoothstep(-1.5, 1.5, p.y));
    // Ringplanet
    vec2 pc = p - vec2(0.35, 0.75);
    float pr = length(pc);
    col = mix(col, mix(uColB, uColA, 0.5 + 0.5 * sin(pc.y * 14.0)) * (0.5 + 0.5 * sqrt(max(0.0, 1.0 - pr * pr / 0.12))), step(pr, 0.35));
    vec2 rq = rot(-0.4) * pc;
    float ring = step(abs(rq.y), 0.04) * step(0.45, abs(rq.x) + abs(rq.y) * 3.0) * step(abs(rq.x), 0.75);
    col = mix(col, vec3(0.9, 0.85, 0.7), ring * (1.0 - step(pr, 0.35) * step(0.0, rq.y)));
    // Retro-Rakete, bauchig, rot-weiß, mit Bullaugen und Flossen
    vec2 r = rot(-0.5) * (p - vec2(-0.25, -0.3));
    float wid = 0.22 * sqrt(max(0.0, 1.0 - pow(r.y / 0.95, 2.0)));
    float body = step(abs(r.x), wid) * step(abs(r.y), 0.95);
    vec3 paint = mix(uColA, vec3(0.95), step(0.5, fract(r.y * 2.5 + 0.2)));
    paint *= 0.5 + 0.6 * smoothstep(-wid, wid * 0.3, r.x);
    col = mix(col, paint, body);
    for (int i = 0; i < 3; i++) {
        float port = smoothstep(0.045, 0.035, length(r - vec2(0.0, 0.35 - float(i) * 0.3)));
        col = mix(col, vec3(0.3, 0.8, 1.0), port * body);
    }
    float fin = step(0.0, -r.y - 0.5) * step(abs(r.x), wid + 0.2 * smoothstep(-0.5, -1.0, r.y)) * step(-1.05, r.y);
    col = mix(col, uColA * 0.8, fin * (1.0 - body));
    float fl = smoothstep(0.15 + 0.1 * bass, 0.0, abs(r.x)) * step(r.y, -1.0) * step(-1.6, r.y) * (0.5 + 0.5 * noise(vec2(r.x * 15.0, r.y * 5.0 - t * 10.0)));
    col += vec3(1.0, 0.8, 0.3) * fl * 1.5;
    // Sternchen
    vec2 sc = floor(q * vec2(30.0, 45.0));
    col += vec3(1.0) * step(0.96, hash12(sc + uSeed)) * (0.5 + 0.5 * sin(t * 3.0 + hash12(sc) * 6.0));
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = vUv;
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    float t = iTime;
    float live = 1.0 - uSilent;
    float bass = uBass * live, beat = uBeat * live;

    // ---- Hintergrund: tiefer Raum mit Nebel in Themenfarben, Sterne funkeln zum Beat
    vec3 col = vec3(0.01, 0.01, 0.02);
    float neb = fbm(p * 1.3 + uSeed * 0.1 + vec2(t * 0.01, 0.0));
    col += mix(uColB, uColA, noise(p * 2.0)) * 0.12 * smoothstep(0.45, 0.9, neb);
    vec2 sc = floor(uv * vec2(220.0, 120.0));
    float star = step(0.985, hash12(sc + uSeed)) * (0.4 + 0.6 * sin(t * 2.0 + hash12(sc + 1.0) * 6.28));
    col += vec3(star) * smoothstep(0.6, 0.0, length(fract(uv * vec2(220.0, 120.0)) - 0.5) * 2.0) * (1.0 + beat);

    // ---- Großes Themenplakat links (Hochformat 2:3), gleitet beim Blättern
    vec2 pc = vec2(0.30 + uSlide * 0.08, 0.615);
    vec2 ps = vec2(0.255, 0.375);                       // halbe Größe in uv-Einheiten (x in Bildbreite)
    vec2 cq = (uv - pc) / ps;                          // -1..1
    cq.x *= aspect * ps.x / (ps.y * 1.5);              // auf 2:3 normieren
    float inPoster = step(abs(cq.x), 1.0) * step(abs(cq.y), 1.0);
    float slideFade = 1.0 - abs(uSlide) * 0.8;
    if (inPoster > 0.5) {
        vec2 q = cq * 0.5 + 0.5;
        vec3 pcol;
        if (uCoverOK > 0.5) {
            pcol = texture(uCoverTex, q).rgb;
        } else {
            int st = int(uCoverStyle + 0.5);
            pcol = st == 0 ? posterRocket(q, t, bass) : (st == 1 ? posterFortress(q, t, bass) : (st == 2 ? posterDiner(q, t, bass) : posterRetro(q, t, bass)));
            // Sterne auch im gezeichneten Plakat
            vec2 s2 = floor(q * vec2(60.0, 90.0));
            pcol += vec3(0.9) * step(0.985, hash12(s2 + uSeed + 9.0)) * 0.7;
        }
        // Papier: leichtes Korn, Vignette, Glanzstreifen
        pcol *= 0.92 + 0.08 * noise(q * 300.0);
        pcol *= 1.0 - 0.35 * pow(length(cq) * 0.75, 3.0);
        pcol += vec3(0.08) * smoothstep(0.03, 0.0, abs(q.x - q.y * 0.5 - 0.2 - 0.03 * sin(t * 0.5)));
        col = pcol * slideFade;
    }
    // Rahmen und Schein
    float frame = step(abs(cq.x), 1.03) * step(abs(cq.y), 1.02) - inPoster;
    vec3 fcol = mix(vec3(0.75, 0.7, 0.55), uColA, uChosen) * (0.8 + 0.4 * uConfirm + 0.2 * beat);
    col = mix(col, fcol, frame);
    col += uColA * 0.25 * smoothstep(0.25, 0.0, max(abs(cq.x) - 1.0, abs(cq.y) - 1.0)) * (1.0 - inPoster) * (0.6 + uChosen + 2.0 * uConfirm);

    // ---- Fahrerplakat rechts: Porträt als Duotone, darunter Textfeld (Overlay)
    vec2 dc = vec2(0.775, 0.625);
    vec2 ds = vec2(0.17, 0.33);
    vec2 dq = (uv - dc) / ds;
    dq.x *= aspect * ds.x / ds.y;                      // quadratisch
    float inDriver = step(abs(dq.x), 1.0) * step(abs(dq.y), 1.0);
    if (inDriver > 0.5) {
        vec2 q = dq * 0.5 + 0.5;
        vec3 bg2 = mix(vec3(0.02, 0.02, 0.04), uColB * 0.25, smoothstep(0.0, 1.0, q.y));
        vec2 s3 = floor(q * vec2(40.0, 40.0));
        bg2 += vec3(0.8) * step(0.97, hash12(s3 + uSeed + 4.0)) * 0.6;
        vec3 dcol = bg2;
        if (uPhotoOK > 0.5) {
            vec2 tq = vec2(q.x, (q.y - 0.02) * 1.15);          // Büste etwas tiefer, Kopf oben
            vec4 s = texture(uPhotoTex, clamp(tq, 0.0, 1.0));
            float inside = step(0.0, tq.y) * step(tq.y, 1.0);
            float lum = dot(s.rgb, vec3(0.3, 0.55, 0.15));
            lum = pow(lum, 0.85);
            vec3 duo = mix(vec3(0.03, 0.02, 0.04), uTint, smoothstep(0.05, 0.9, lum));   // Duotone wie ein Plakatdruck
            duo = mix(duo, vec3(1.0, 0.98, 0.9), smoothstep(0.85, 1.0, lum) * 0.5);
            int acc = int(uAccessory + 0.5);
            if (acc == 1 || acc == 3) {
                float gl = step(sdBox(tq - vec2(0.39, 0.61), vec2(0.075, 0.045), 0.03), 0.0) + step(sdBox(tq - vec2(0.595, 0.61), vec2(0.075, 0.045), 0.03), 0.0)
                         + step(sdBox(tq - vec2(0.49, 0.615), vec2(0.04, 0.006), 0.0), 0.0);
                duo = mix(duo, vec3(0.02), min(gl, 1.0));
                duo += vec3(0.5) * min(gl, 1.0) * smoothstep(0.02, 0.0, abs((tq.x - tq.y) + 0.14));
            }
            if (acc >= 2) {
                vec2 cap = tq - vec2(0.49, 0.80);
                float dome = step(length(cap * vec2(1.0, 1.9)), 0.26) * step(0.0, cap.y + 0.05);
                float brim = step(sdBox(tq - vec2(0.56, 0.72), vec2(0.26, 0.02), 0.01), 0.0);
                float checker = step(0.5, fract(tq.x * 16.0)) == step(0.5, fract(tq.y * 16.0)) ? 1.0 : 0.0;
                vec3 capc = vec3(0.08, 0.08, 0.12) * (0.6 + 0.8 * smoothstep(-0.1, 0.12, cap.y));
                capc = mix(capc, mix(uColA, vec3(0.05), checker), step(abs(cap.y + 0.02), 0.03));
                capc = mix(capc, vec3(0.03), brim * (1.0 - dome));
                duo = mix(duo, capc, max(dome, brim));
                s.a = max(s.a, max(dome, brim));
            }
            dcol = mix(dcol, duo, s.a * inside);
        }
        dcol *= 0.92 + 0.08 * noise(q * 300.0);
        dcol *= 1.0 - 0.3 * pow(length(dq) * 0.75, 3.0);
        col = dcol;
    }
    float dframe = step(abs(dq.x), 1.04) * step(abs(dq.y), 1.025) - inDriver;
    col = mix(col, vec3(0.75, 0.7, 0.55) * (0.8 + 0.2 * beat), dframe);
    // Textfeld unter dem Fahrerplakat
    col = mix(col, vec3(0.02, 0.02, 0.03), rect(uv, vec2(0.605, 0.065), vec2(0.945, 0.27)) * 0.8);
    col += uColA * (rect(uv, vec2(0.605, 0.267), vec2(0.945, 0.27)) + rect(uv, vec2(0.605, 0.065), vec2(0.608, 0.27)));
    // Schachbrettband unten und Fußleiste
    float bandY = step(0.040, uv.y) * step(uv.y, 0.050);
    float ck = step(0.5, fract(uv.x * 40.0 - t * (0.3 + 1.5 * bass))) == step(0.5, fract(uv.y * 200.0)) ? 1.0 : 0.0;
    col = mix(col, mix(uColA, vec3(0.03), ck), bandY);
    col = mix(col, vec3(0.0), rect(uv, vec2(0.0, 0.0), vec2(1.0, 0.040)) * 0.6);
    // Bestätigung: kurzer Lichtblitz in Themenfarbe
    col += uColA * uConfirm * uConfirm * 0.35;
    col *= 1.0 - 0.3 * pow(length(uv - 0.5) * 1.3, 2.0);
    fragColor = vec4(col, 1.0);
}
