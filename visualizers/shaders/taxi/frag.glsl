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
uniform sampler2D uPhotoTex, uCoverTex, uDriverTex, uMissionTex, uSpriteTex;
uniform float uMissionOK, uSpriteOK, uSprT;
uniform vec2 uMissionSize, uSpriteSize;
uniform float uPhotoOK, uCoverOK, uCoverStyle, uAccessory, uSlide, uConfirm, uChosen, uSeed;
// Digitale Lizenz: Fahrerfoto mit Beat-Zoom auf die Augen (uBeatZoom), Bass (uBassS), Glitch, Spiralen (uSpinT)
uniform float uDriverOK, uBeatZoom, uBassS, uEnergy, uGlitch, uSpinT, uEyeR;
uniform vec2 uDriverSize;
uniform vec4 uEyes;                                   // Augenmitten im Foto (x1, y1, x2, y2), y von unten
uniform vec3 uColA, uColB, uTint;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash1(float n) { n = fract(n * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.1 + 5.0; a *= 0.5; } return v; }
vec3 palx(float t) { return 0.5 + 0.5 * cos(6.28318 * (vec3(1.0, 0.9, 0.7) * t + vec3(0.0, 0.25, 0.5))); }
// bilinear aus einer Textur, die mit GL_NEAREST vorliegt
vec3 bilin(sampler2D tex, vec2 uv, vec2 size) {
    vec2 px = uv * size - 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 a = clamp(i, vec2(0.0), size - 1.0), b = clamp(i + 1.0, vec2(0.0), size - 1.0);
    vec3 s00 = texture(tex, (vec2(a.x, a.y) + 0.5) / size).rgb, s10 = texture(tex, (vec2(b.x, a.y) + 0.5) / size).rgb;
    vec3 s01 = texture(tex, (vec2(a.x, b.y) + 0.5) / size).rgb, s11 = texture(tex, (vec2(b.x, b.y) + 0.5) / size).rgb;
    return mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
}
// Digitale Lizenz: Foto lebt. q 0..1 über das Feld. Beat zoomt auf die Augen, Kopf schwingt leicht,
// Hologramm-Streifen und Lichtwischer, Glitch-Scheiben bei harten Beats, in den Augen psychedelische Kreisel.
vec3 digitalLicense(vec2 q, float t) {
    vec2 eyeC = (uEyes.xy + uEyes.zw) * 0.5;
    float zoom = 1.0 + 0.9 * uBeatZoom + 0.08 * uBassS;
    vec2 tq = eyeC + (q - eyeC) / zoom;
    // leichtes Schwingen wie Atmen und Kopfwiegen, dazu langsamer Kameraschwenk
    float sway = 0.012 * sin(t * 0.9) + 0.012 * uBassS * sin(t * 4.0);
    tq.x += sway * (tq.y - 0.25);
    tq.y += 0.004 * sin(t * 1.3) + 0.006 * uBassS;
    tq += vec2(0.005 * sin(t * 0.37), 0.004 * cos(t * 0.29));
    // Glitch: einzelne Zeilenstreifen springen zur Seite
    float row = floor(tq.y * 28.0);
    float gl = uGlitch * step(0.65, hash12(vec2(row, floor(t * 24.0))));
    tq.x += gl * (hash12(vec2(row, floor(t * 11.0))) - 0.5) * 0.1;
    // Farbsaum bei Beat und Glitch
    float ca = 0.0025 * uBeatZoom + 0.005 * uGlitch;
    vec2 cq = clamp(tq, 0.0, 1.0);
    vec3 s;
    s.r = bilin(uDriverTex, clamp(tq + vec2(ca, 0.0), 0.0, 1.0), uDriverSize).r;
    s.g = bilin(uDriverTex, cq, uDriverSize).g;
    s.b = bilin(uDriverTex, clamp(tq - vec2(ca, 0.0), 0.0, 1.0), uDriverSize).b;
    // Augen: psychedelische Kreisel, wachsen mit dem Beat-Zoom
    float strength = clamp(uBeatZoom * 1.4 + 0.15 * uBassS, 0.0, 1.0);
    for (int i = 0; i < 2; i++) {
        vec2 ec = i == 0 ? uEyes.xy : uEyes.zw;
        vec2 e = tq - ec;
        float r = length(e) / (uEyeR * (1.0 + 0.5 * strength));
        if (r < 1.4) {
            float ang = atan(e.y, e.x);
            float sp = 0.5 + 0.5 * sin(ang * 3.0 + log(r + 0.04) * 9.0 - uSpinT * 7.0 * (i == 0 ? 1.0 : -1.0));
            sp = pow(sp, 1.5);
            vec3 sc = palx(sp * 0.6 + uSpinT * 0.25 + float(i) * 0.3) * (0.6 + 0.9 * sp);
            float m = smoothstep(1.0, 0.55, r) * strength;
            s = mix(s, sc, m);
            s += sc * exp(-r * 3.0) * strength * 0.5;                   // Leuchten nach außen
        }
    }
    // Hologramm: Zeilen, Lichtwischer, Rand in Themenfarbe, Rauschen
    s *= 0.92 + 0.08 * sin(q.y * 520.0 + t * 6.0);
    float sweep = exp(-pow((q.x + q.y * 0.6 - fract(t * 0.18) * 2.2 + 0.4) * 7.0, 2.0));
    s += vec3(0.6, 0.8, 1.0) * sweep * 0.25;
    s += uColA * 0.15 * (0.5 + 0.5 * sin(t * 2.0 + q.y * 6.0)) * uBassS;
    s += vec3(0.8, 0.9, 1.0) * uGlitch * 0.15 * step(0.8, hash12(vec2(floor(q.y * 90.0), floor(t * 40.0))));
    s *= 1.0 + 0.25 * uBeatZoom;
    return s;
}
vec4 bilin4(sampler2D tex, vec2 uv, vec2 size, vec2 lo, vec2 hi) {
    vec2 px = uv - 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 a = clamp(i, lo, hi), b = clamp(i + 1.0, lo, hi);
    vec4 s00 = texture(tex, (vec2(a.x, a.y) + 0.5) / size), s10 = texture(tex, (vec2(b.x, a.y) + 0.5) / size);
    vec4 s01 = texture(tex, (vec2(a.x, b.y) + 0.5) / size), s11 = texture(tex, (vec2(b.x, b.y) + 0.5) / size);
    return mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
}
// Schwebende Figur aus dem Atlas (8x3 Zellen à 96 px, Zeile 0 oben): c Mitte, sz halbe Größe (Höheneinheiten), ang Drehung
vec4 floater(vec2 p, vec2 c, float sz, float ang, float idx) {
    vec2 d = p - c;
    float cs = cos(ang), sn = sin(ang);
    d = vec2(cs * d.x + sn * d.y, -sn * d.x + cs * d.y) / sz;
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 96.0, (2.0 - ri) * 96.0);
    vec2 px = lo + (d * 0.5 + 0.5) * 96.0;
    return bilin4(uSpriteTex, px, uSpriteSize, lo, lo + 95.0);
}
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
        vec3 n = vec3(mc / 0.75, sqrt(max(0.0, 1.0 - mr * mr / 0.5625)));
        vec2 mq = n.xy * 6.0 + uSeed;
        float crat = fbm(mq);
        float craters = smoothstep(0.5, 0.62, noise(mq * 2.3)) * 0.5 + smoothstep(0.55, 0.7, noise(mq * 5.0 + 3.0)) * 0.3;
        // Kraterränder: Ableitung des Rauschens als Schattierung
        float e = 0.02;
        float slope = (noise(mq * 2.3 + vec2(e, 0.0)) - noise(mq * 2.3 - vec2(e, 0.0))) * 6.0;
        float lit = 0.25 + 0.85 * clamp(dot(n, normalize(vec3(-0.35, 0.3, 0.85))), 0.0, 1.0);
        vec3 moon = mix(vec3(0.62, 0.68, 0.78), vec3(0.88, 0.92, 0.98), smoothstep(0.35, 0.7, crat));
        moon *= 1.0 - craters * 0.35 + slope * 0.25;
        moon *= 0.9 + 0.1 * noise(mc * 60.0);
        col = moon * lit;
        col += uColB * 0.35 * pow(1.0 - n.z, 2.5);                                        // bläulicher Saum
    }
    col += uColB * 0.5 * smoothstep(0.12, 0.0, abs(mr - 0.75)) * step(0.75, mr);         // Mondschein
    // Rakete: Zylinder mit Spitze und drei Flossen, Metall mit Lichtkante
    vec2 r = p - vec2(0.0, 0.1 + 0.01 * sin(t * 1.5));
    float body = step(abs(r.x), 0.13) * step(-0.75, r.y) * step(r.y, 0.55);
    float nose = step(abs(r.x), 0.13 * (1.0 - smoothstep(0.55, 1.05, r.y))) * step(0.55, r.y) * step(r.y, 1.05);
    float finL = step(0.0, -r.x - 0.13) * step(-r.x - 0.13, 0.17 * smoothstep(-0.3, -0.8, r.y)) * step(-0.85, r.y) * step(r.y, -0.3);
    float finR = step(0.0, r.x - 0.13) * step(r.x - 0.13, 0.17 * smoothstep(-0.3, -0.8, r.y)) * step(-0.85, r.y) * step(r.y, -0.3);
    float finT = step(0.0, r.x - 0.13) * step(r.x - 0.13, 0.12 * smoothstep(0.75, 0.45, r.y)) * step(0.45, r.y) * step(r.y, 0.8);
    float rocket = max(max(body, nose), max(max(finL, finR), finT));
    float nx = clamp(r.x / 0.13, -1.0, 1.0);
    float nz = sqrt(1.0 - nx * nx);
    float shade = 0.25 + 0.75 * clamp(dot(vec2(nx, nz), normalize(vec2(-0.55, 0.85))), 0.0, 1.0);
    float specular = pow(clamp(dot(vec2(nx, nz), normalize(vec2(-0.35, 0.95))), 0.0, 1.0), 24.0) * 0.6;
    vec3 metal = vec3(0.72, 0.76, 0.82) * shade + specular;
    metal += uColB * 0.25 * smoothstep(0.3, 1.0, nx);                                       // Mondlicht von rechts
    float groove = smoothstep(0.35, 0.5, abs(fract(r.y * 9.0) - 0.5)) ;
    metal *= 1.0 - 0.45 * (1.0 - groove) * step(0.1, r.y) * step(r.y, 0.55) * step(abs(r.x), 0.11);   // Rillen
    metal *= 0.9 + 0.1 * noise(r * 40.0);
    metal = mix(metal, vec3(0.1), step(0.9, r.y) * step(0.5, fract((r.x + r.y) * 20.0)) * step(0.5, fract((r.x - r.y) * 20.0)));
    col = mix(col, metal, rocket);
    // Triebwerksflamme
    float fl = smoothstep(0.12 + 0.08 * bass, 0.0, abs(r.x) / max(0.001, 1.0 + (r.y + 0.75) * 1.2)) * step(r.y, -0.75) * step(-1.45, r.y);
    fl *= 0.5 + 0.5 * noise(vec2(r.x * 20.0, r.y * 6.0 - t * 12.0));
    col += mix(uColB, vec3(0.9, 0.95, 1.0), fl) * fl * (1.5 + 2.0 * bass) * smoothstep(-1.45, -0.75, r.y);
    return col;
}
// Gelbes Taxischild (Standard): Dachschild eines Taxis mit Karo-Band, Leuchtkasten, Schriftzug TAXI, Rakete
float sdSeg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }
float letterTAXI(vec2 p) {
    // p: x -1..1 über die Schriftbreite, y -1..1; Strichbreite 0.11
    float w = 0.11, d = 10.0;
    // T
    d = min(d, sdSeg(p, vec2(-0.95, 0.5), vec2(-0.55, 0.5)));
    d = min(d, sdSeg(p, vec2(-0.75, 0.5), vec2(-0.75, -0.5)));
    // A
    d = min(d, sdSeg(p, vec2(-0.45, -0.5), vec2(-0.25, 0.5)));
    d = min(d, sdSeg(p, vec2(-0.25, 0.5), vec2(-0.05, -0.5)));
    d = min(d, sdSeg(p, vec2(-0.38, -0.1), vec2(-0.12, -0.1)));
    // X
    d = min(d, sdSeg(p, vec2(0.1, 0.5), vec2(0.5, -0.5)));
    d = min(d, sdSeg(p, vec2(0.1, -0.5), vec2(0.5, 0.5)));
    // I
    d = min(d, sdSeg(p, vec2(0.75, 0.5), vec2(0.75, -0.5)));
    d = min(d, sdSeg(p, vec2(0.62, 0.5), vec2(0.88, 0.5)));
    d = min(d, sdSeg(p, vec2(0.62, -0.5), vec2(0.88, -0.5)));
    return smoothstep(w, w - 0.03, d);
}
vec3 posterTaxi(vec2 q, float t, float bass) {
    vec2 p = (q - 0.5) * vec2(2.0, 3.0);                 // -1..1 breit, -1.5..1.5 hoch
    vec3 yellow = vec3(0.98, 0.78, 0.08);
    vec3 col = yellow * (0.92 + 0.08 * noise(p * 30.0));
    // Karo-Bänder oben und unten (schwarz-gelb), leicht zum Takt flackernd
    float checker = step(0.5, fract(p.x * 4.0 + 0.25)) == step(0.5, fract(p.y * 4.0)) ? 1.0 : 0.0;
    float bandTop = step(1.1, p.y) * step(p.y, 1.35);
    float bandBot = step(-1.35, p.y) * step(p.y, -1.1);
    col = mix(col, vec3(0.05), (bandTop + bandBot) * checker);
    // Leuchtkasten in der Mitte: schwarzer Rahmen, gelb leuchtende Fläche, Schriftzug TAXI
    vec2 bq = p - vec2(0.0, 0.25);
    float boxOuter = step(abs(bq.x), 0.92) * step(abs(bq.y), 0.42);
    float boxInner = step(abs(bq.x), 0.86) * step(abs(bq.y), 0.36);
    float glow = 0.85 + 0.15 * sin(t * 2.0) + 0.25 * bass;
    col = mix(col, vec3(0.06), boxOuter);
    col = mix(col, yellow * (1.05 * glow) + vec3(0.1, 0.05, 0.0), boxInner);
    float txt = letterTAXI(vec2(bq.x / 0.8, bq.y / 0.26)) * boxInner;
    col = mix(col, vec3(0.05), txt);
    // Dachlampen links und rechts vom Kasten
    for (int i = -1; i <= 1; i += 2) {
        vec2 lq = p - vec2(float(i) * 0.78, 0.78);
        float lamp = smoothstep(0.1, 0.08, length(lq * vec2(1.0, 1.6)));
        col = mix(col, vec3(1.0, 0.95, 0.7) * (0.8 + 0.3 * sin(t * 3.0 + float(i))), lamp);
        col += vec3(1.0, 0.9, 0.5) * exp(-length(lq) * 6.0) * 0.3;
    }
    // Rakete als Silhouette unten (Space Taxi), mit Flämmchen
    vec2 r = (p - vec2(0.0, -0.62)) * 1.6;
    r = rot(0.5) * r;
    float body = step(abs(r.x), 0.12) * step(-0.45, r.y) * step(r.y, 0.3);
    float nose = step(abs(r.x), 0.12 * (1.0 - smoothstep(0.3, 0.7, r.y))) * step(0.3, r.y) * step(r.y, 0.7);
    float fins = step(abs(r.x) - 0.12, 0.14 * smoothstep(-0.2, -0.5, r.y)) * step(-0.5, r.y) * step(r.y, -0.2) * step(0.12, abs(r.x));
    float win = smoothstep(0.06, 0.05, length(r - vec2(0.0, 0.12)));
    float rocket = max(max(body, nose), fins);
    col = mix(col, vec3(0.05), rocket);
    col = mix(col, yellow * 1.2, win * rocket);
    float fl = smoothstep(0.1 + 0.06 * bass, 0.0, abs(r.x) / max(0.01, 1.0 + (r.y + 0.45) * 1.5)) * step(r.y, -0.45) * step(-0.95, r.y);
    fl *= 0.6 + 0.4 * noise(vec2(r.x * 20.0, r.y * 6.0 - t * 12.0));
    col += vec3(1.0, 0.4, 0.05) * fl * (1.2 + 1.5 * bass);
    // Nummernzeile als Balken unten (Taxi-Nummer stilisiert)
    float plate = step(abs(p.x), 0.55) * step(abs(p.y + 1.0), 0.06);
    col = mix(col, vec3(0.05), plate);
    col = mix(col, yellow, plate * step(0.5, fract(p.x * 9.0)) * step(abs(p.y + 1.0), 0.04));
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
        vec2 wg = vec2(p.x * 30.0, p.y * 22.0);
        vec2 wc = floor(wg);
        vec2 wf = fract(wg) - 0.5;
        float win = smoothstep(0.3, 0.2, abs(wf.x)) * smoothstep(0.32, 0.22, abs(wf.y)) * step(0.45, hash12(wc + uSeed));
        float winGlow = smoothstep(0.6, 0.0, length(wf)) * step(0.45, hash12(wc + uSeed)) * 0.3;
        col += uColA * (win + winGlow) * tower * 0.55 * (0.6 + 0.4 * step(0.3, hash12(wc + floor(t * 0.5))));
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
    for (int i = 0; i < 2; i++) {
        float fi = float(i);
        vec2 sg = p * (60.0 + fi * 45.0) + fi * 11.0;
        vec2 cell = floor(sg);
        vec2 f = fract(sg) - 0.5 + (vec2(hash12(cell + 1.0), hash12(cell + 2.0)) - 0.5) * 0.6;
        float h = hash12(cell + uSeed + fi);
        float star = step(0.94, h) * smoothstep(0.09, 0.0, length(f)) * (0.5 + 0.5 * sin(t * (1.0 + h * 3.0) + h * 40.0));
        col += mix(vec3(0.9, 0.95, 1.0), vec3(1.0, 0.85, 0.7), hash12(cell + 7.0)) * star * (0.8 + beat);
    }

    // ---- Links: das Missionslogo groß (schwarzer Hintergrund, additiv über Sternen), pulst leicht mit dem Bass
    {
        vec2 mc = vec2(0.315 + uSlide * 0.03, 0.62);
        vec2 ms = vec2(0.28, 0.28 * aspect * uMissionSize.y / max(uMissionSize.x, 1.0));   // Seitenverhältnis des Logos
        float mscale = 1.0 + 0.025 * uBassS + 0.01 * sin(t * 0.7);
        vec2 mq = (uv - mc) / (ms * mscale);
        if (uMissionOK > 0.5 && abs(mq.x) < 1.0 && abs(mq.y) < 1.0) {
            vec2 q = mq * 0.5 + 0.5;
            vec4 logo = bilin4(uMissionTex, q * uMissionSize, uMissionSize, vec2(0.0), uMissionSize - 1.0);
            float sheen = exp(-pow((q.x - q.y * 0.4 - fract(t * 0.07) * 1.9 + 0.5) * 6.0, 2.0));
            logo.rgb *= 1.0 + 0.25 * sheen + 0.15 * uBassS;
            float edge = smoothstep(1.0, 0.9, abs(mq.x)) * smoothstep(1.0, 0.9, abs(mq.y));
            col = mix(col, logo.rgb, logo.a * edge);
            col += uColA * logo.a * edge * 0.06 * (0.5 + uBassS);
        }
        // Figuren schweben über das Logo: jede auf eigener Bahn, wippt leicht zur Musik
        if (uSpriteOK > 0.5) {
            vec2 pp = vec2(uv.x * aspect, uv.y);
            for (int i = 0; i < 12; i++) {
                float fi = float(i);
                float h1 = hash12(vec2(fi, 7.0)), h2 = hash12(vec2(fi, 13.0)), h3 = hash12(vec2(fi, 29.0)), h4 = hash12(vec2(fi, 41.0));
                float dir = h1 < 0.5 ? 1.0 : -1.0;
                float ph = fract(uSprT * (0.012 + 0.010 * h2) + h3);
                float x = mix(0.02, 0.61, dir > 0.0 ? ph : 1.0 - ph);
                float y = mix(0.27, 0.97, h4) + 0.018 * sin(uSprT * (0.5 + h2) + fi * 2.0) * (1.0 + 2.5 * uBassS);
                float fade = smoothstep(0.02, 0.08, x) * smoothstep(0.61, 0.55, x);
                float sz = (0.03 + 0.022 * h3) * (1.0 + 0.1 * uBassS);
                float ang = 0.18 * sin(uSprT * 0.4 + fi) + dir * 0.08 + 0.05 * uBassS * sin(uSprT * 5.0 + fi);
                vec4 sp = floater(pp, vec2(x * aspect, y), sz, ang, mod(fi * 7.0 + 3.0, 24.0));
                col = mix(col, sp.rgb * (0.9 + 0.3 * uBassS), sp.a * fade * 0.95);
            }
        }
    }
    // ---- Rechts: der Taxischein. Gelbes Taxischild als Karte (Karo-Bänder, Leuchtkasten TAXI), darauf das Foto
    vec3 frameCol = mix(vec3(0.2, 0.6, 0.9), uColA, 0.5 + 0.5 * sin(t * 1.5)) * (0.7 + 0.5 * uBassS + 0.6 * uBeatZoom);
    {
        vec2 cc = vec2(0.805, 0.5);
        vec2 ch = vec2(0.165, 0.44);                             // halbe Größe (uv); 0.33*aspect : 0.88 ≈ 2:3
        vec2 cq = (uv - cc) / ch;                                // -1..1
        float inCard = step(abs(cq.x), 1.0) * step(abs(cq.y), 1.0);
        if (inCard > 0.5) {
            vec2 p = cq * vec2(1.0, 1.5);                        // -1..1 breit, -1.5..1.5 hoch (isotrop)
            vec3 yellow = uColA;
            vec3 c = yellow * (0.92 + 0.08 * noise(p * 30.0));
            // Karo-Bänder oben und unten, laufen ganz langsam
            float ck2 = step(0.5, fract(p.x * 4.0 + 0.25 + t * 0.05)) == step(0.5, fract(p.y * 4.0)) ? 1.0 : 0.0;
            float bandTop = step(1.22, p.y) * step(p.y, 1.44);
            float bandBot = step(-1.44, p.y) * step(p.y, -1.22);
            c = mix(c, vec3(0.05), (bandTop + bandBot) * ck2);
            // Leuchtkasten mit TAXI
            vec2 bq = p - vec2(0.0, 1.06);
            float boxOuter = step(abs(bq.x), 0.9) * step(abs(bq.y), 0.15);
            float boxInner = step(abs(bq.x), 0.85) * step(abs(bq.y), 0.115);
            float glow = 0.85 + 0.15 * sin(t * 2.0) + 0.3 * uBassS + 0.3 * beat;
            c = mix(c, vec3(0.06), boxOuter);
            c = mix(c, yellow * (1.05 * glow) + vec3(0.1, 0.05, 0.0), boxInner);
            float txt = letterTAXI(vec2(bq.x / 0.78, bq.y / 0.09)) * boxInner;
            c = mix(c, vec3(0.05), txt);
            // Foto: schwarzer Rahmen, darin die digitale Lizenz (Beat-Zoom, Kreisel in den Augen)
            vec2 fq = p - vec2(0.0, 0.12);
            float phOuter = step(abs(fq.x), 0.64) * step(abs(fq.y), 0.64);
            float phInner = step(abs(fq.x), 0.60) * step(abs(fq.y), 0.60);
            c = mix(c, vec3(0.05), phOuter);
            if (phInner > 0.5) {
                vec2 q = fq / 0.60 * 0.5 + 0.5;
                c = uDriverOK > 0.5 ? digitalLicense(q, t) : (uPhotoOK > 0.5 ? texture(uPhotoTex, q).rgb : vec3(0.1));
            }
            // Textfeld unten (Overlay-Text), dunkler Streifen mit Nummernleiste und Strichcode
            float field = step(abs(p.x), 0.86) * step(-1.2, p.y) * step(p.y, -0.56);
            c = mix(c, yellow * 0.75, field * 0.5);
            float bar = step(0.5, hash12(vec2(floor(p.x * 60.0), 1.0))) * step(abs(p.x), 0.5) * step(-1.19, p.y) * step(p.y, -1.13);
            c = mix(c, vec3(0.05), bar);
            // Papierkorn, Vignette, Lichtblitz bei Bestätigung
            c *= 0.94 + 0.06 * noise(p * 300.0);
            c *= 1.0 - 0.3 * pow(length(cq) * 0.75, 3.0);
            c += uColA * uConfirm * 0.3;
            col = c;
        }
        // Rand: dunkler Kartenrand plus pulsender Schein in Rahmenfarbe
        float rim = step(abs(cq.x), 1.03) * step(abs(cq.y), 1.015) - inCard;
        col = mix(col, vec3(0.05), rim);
        col += frameCol * 0.3 * smoothstep(0.2, 0.0, max(abs(cq.x) - 1.0, abs(cq.y) - 1.0)) * (1.0 - inCard) * (0.4 + uBeatZoom + uChosen * 0.5);
    }
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
