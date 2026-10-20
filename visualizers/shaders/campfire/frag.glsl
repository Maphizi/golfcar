#version 140
// Lagerfeuer als Cinemagraph: ein Foto der Szene (uPlate) wird lebendig. An der Feuerstelle (uFire:
// x, y, Breite, Höhe in Bildanteilen, y von unten) brennen echte Flammen aus dem Spritesheet uFlames
// (uGrid Spalten x Zeilen, Bild uFrame mit Überblendung zum nächsten), darüber Funken, Rauch und
// Hitzeflimmern; das Feuerlicht flackert auf dem ganzen Bild. Dazu langsamer Kameraschwenk (uCam),
// Sternschnuppen (uMeteor), Lauf des Abends als Farbstimmung (uDay) und Musik: Bass macht das Feuer
// größer und heller, Anschläge (uSpark) schicken Funken hoch, Wind (uWind) legt Flammen und Rauch.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uPlate, uFlames;
uniform float uSeed, uDay, uBassS, uEnergy, uSpark, uWind, uFireT, uFrame, uPlateOK, uFlamesOK;
uniform vec4 uFire, uMeteor;
uniform vec2 uGrid, uPlateSize, uFlamesSize, uCam;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
float sdSeg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }

// Bilinear aus einer Textur, die mit GL_NEAREST hochgeladen wurde (uv 0..1, Zeile 0 unten)
vec3 sampleBilinear(sampler2D tex, vec2 uv, vec2 size) {
    vec2 px = uv * size - 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 a = clamp(i, vec2(0.0), size - 1.0), b = clamp(i + 1.0, vec2(0.0), size - 1.0);
    vec3 s00 = texture(tex, (vec2(a.x, a.y) + 0.5) / size).rgb;
    vec3 s10 = texture(tex, (vec2(b.x, a.y) + 0.5) / size).rgb;
    vec3 s01 = texture(tex, (vec2(a.x, b.y) + 0.5) / size).rgb;
    vec3 s11 = texture(tex, (vec2(b.x, b.y) + 0.5) / size).rgb;
    return mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
}
// Ein Flammenbild (Index) an Position l (0..1 über die Zelle, y nach oben), bilinear innerhalb der Zelle
vec3 flameFrame(float idx, vec2 l) {
    if (l.x <= 0.0 || l.x >= 1.0 || l.y <= 0.0 || l.y >= 1.0) return vec3(0.0);
    float cols = uGrid.x, rows = uGrid.y;
    float ci = mod(idx, cols), ri = floor(idx / cols);
    vec2 cell = uFlamesSize / vec2(cols, rows);
    vec2 lo = vec2(ci * cell.x, (rows - 1.0 - ri) * cell.y);           // Zeile 0 des Sheets liegt oben = GL oben
    vec2 px = lo + l * cell - 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 a = clamp(i, lo, lo + cell - 1.0), b = clamp(i + 1.0, lo, lo + cell - 1.0);
    vec3 s00 = texture(uFlames, (vec2(a.x, a.y) + 0.5) / uFlamesSize).rgb;
    vec3 s10 = texture(uFlames, (vec2(b.x, a.y) + 0.5) / uFlamesSize).rgb;
    vec3 s01 = texture(uFlames, (vec2(a.x, b.y) + 0.5) / uFlamesSize).rgb;
    vec3 s11 = texture(uFlames, (vec2(b.x, b.y) + 0.5) / uFlamesSize).rgb;
    return mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
}
float nightAmount(float d) { return smoothstep(0.02, 0.16, d) * smoothstep(0.98, 0.84, d); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = 1.0 - uSilent;
    // Kamera: leichter Zoom mit langsamem Schwenk; alles weitere in Bildkoordinaten (0..1, y nach oben)
    vec2 uv = 0.5 + (vUv - 0.5) / 1.05 + uCam;
    // Feuerstelle
    vec2 fc = uFire.xy;                                   // Fuß der Flammen
    float fw = uFire.z, fh = uFire.w;
    float size = 1.0 + 0.35 * uBassS + 0.15 * uEnergy;    // Bass: größer
    float flick = 0.86 + 0.14 * noise(vec2(uFireT * 7.0, 3.0)) + 0.1 * uBassS;
    vec2 d = vec2((uv.x - fc.x) * aspect, uv.y - fc.y);   // Abstand in Bildhöhen
    float distF = length(d * vec2(1.0, 1.4));
    // Hitzeflimmern über dem Feuer: Bild leicht verzerren
    float heat = smoothstep(fh * 1.8, 0.0, length(vec2(d.x * 1.6, max(0.0, d.y - fh * 0.3)))) * step(0.0, d.y);
    vec2 shimmer = vec2(noise(vec2(uv.x * 60.0, uv.y * 40.0 - uFireT * 6.0)) - 0.5, noise(vec2(uv.x * 50.0 + 9.0, uv.y * 40.0 - uFireT * 8.0)) - 0.5) * 0.006 * heat;
    vec3 col = uPlateOK > 0.5 ? sampleBilinear(uPlate, clamp(uv + shimmer, 0.0, 1.0), uPlateSize) : vec3(0.02);
    // Statische Flammen im Foto abdunkeln, damit die bewegten übernehmen (Glut und Scheite bleiben)
    vec2 fm = vec2(d.x / (fw * 0.5), (d.y - fh * 0.3) / (fh * 0.7));
    float staticMask = smoothstep(1.0, 0.5, length(fm)) * smoothstep(0.0, fh * 0.15, d.y);
    col = mix(col, col * vec3(0.8, 0.4, 0.15) * 0.55, staticMask);      // zur Glut abdunkeln, warm statt grau
    // Feuerlicht flackert auf dem ganzen Bild (im Foto ist das Licht schon drin, hier nur die Schwankung)
    float lightK = exp(-distF * 2.2);
    col *= 1.0 + (flick - 0.93) * 2.0 * lightK + 0.25 * uBassS * lightK;
    // Lauf des Abends: Farbstimmung des Himmels und des Lichts
    float night = nightAmount(uDay), dusk = smoothstep(0.2, 0.0, uDay), dawn = smoothstep(0.82, 1.0, uDay);
    float skyMask = smoothstep(0.45, 0.8, uv.y);
    col = mix(col, col * vec3(1.25, 0.85, 0.6) + vec3(0.22, 0.09, 0.02) * skyMask, dusk * 0.8);
    col = mix(col, col * vec3(0.95, 1.0, 1.15) + vec3(0.08, 0.12, 0.22) * skyMask, dawn * 0.8);
    col *= 1.0 + 0.12 * (dusk + dawn);
    // ---- Flammen aus dem Spritesheet: zwei Bilder überblendet, Höhe mit dem Bass, Wind legt sie
    if (uFlamesOK > 0.5) {
        float lean = uWind * 0.35 * clamp(d.y / fh, 0.0, 1.0) * (1.0 + 0.25 * sin(uFireT * 5.0));
        vec2 l = vec2(d.x / (fw * size * aspect / aspect) - lean, d.y / (fh * size));
        l = vec2(l.x / 1.0 + 0.5, l.y);                      // Zelle: x 0..1, y 0..1 (Fuß bei 0)
        // Zelle ist 191x110: Flamme ist breiter als hoch -> Breite der Zelle = fw*size, Höhe = fh*size
        float f0 = floor(uFrame), f1 = mod(f0 + 1.0, uGrid.x * uGrid.y);
        float k = fract(uFrame);
        vec3 fl = mix(flameFrame(f0, l), flameFrame(f1, l), k);
        fl = max(fl - 0.06, 0.0) / 0.94;                       // Schwarzwert: Reste des Gitters und Rauschen weg
        // nur Feuerfarben behalten (grauer Rauch und Gitterlinien der Bilder fallen weg), Zellränder weich
        float fireKey = clamp((fl.r - fl.b - 0.04) * 5.0, 0.0, 1.0);
        float window = smoothstep(0.0, 0.1, l.x) * smoothstep(1.0, 0.9, l.x) * smoothstep(1.0, 0.85, l.y) * smoothstep(0.0, 0.04, l.y);
        fl *= fireKey * window;
        float lum = dot(fl, vec3(0.3, 0.5, 0.2));
        fl *= 1.1 + 0.6 * uBassS;
        col = col * (1.0 - clamp(lum * 1.4, 0.0, 1.0) * 0.8) + fl * 1.35;     // Flamme deckt, Rest leuchtet additiv
        col += vec3(1.0, 0.5, 0.15) * exp(-distF * 5.0) * (0.15 + 0.4 * uBassS) * flick;
    }
    // ---- Rauch: zieht über dem Feuer nach oben, Wind verweht ihn
    {
        vec2 sq = vec2(d.x - uWind * 0.25 * max(0.0, d.y) - 0.02 * sin(uFireT * 0.7 + d.y * 6.0), d.y);
        float smoke = fbm(vec2(sq.x * 5.0, sq.y * 2.5 - uFireT * 0.6) + uSeed);
        float smask = smoothstep(fh * 0.8, fh * 1.4, d.y) * smoothstep(0.9, 0.3, d.y) * smoothstep(fw * 0.9, 0.0, abs(sq.x) - d.y * 0.15);
        col = mix(col, col * 0.55 + vec3(0.2, 0.18, 0.17), smoothstep(0.4, 0.75, smoke) * smask * 0.4);
    }
    // ---- Funken: steigen aus der Glut auf, mehr bei Anschlägen, Wind trägt sie seitlich
    for (int i = 0; i < 24; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, uSeed)), h2 = hash12(vec2(fi + 30.0, uSeed));
        float life = 1.4 + h2 * 1.8;
        float age = mod(uFireT * 1.1 + h1 * life, life);
        float k = age / life;
        vec2 sp = vec2((h1 - 0.5) * fw * 0.5 + k * k * (0.05 + uWind * 0.25) * (h2 - 0.3) + 0.015 * sin(age * 7.0 + fi),
                       fh * 0.25 + k * (fh * 1.2 + 0.15 * h2) * size);
        vec2 dd = (d - sp) * vec2(1.0, 1.0);
        float sz = 0.0035 * (1.0 - k * 0.6);
        float s = smoothstep(sz, 0.0, length(dd));
        float on = step(0.45 - 0.45 * uSpark, h2 * (1.0 - k)) * (0.6 + 0.4 * sin(age * 30.0 + fi));
        col += vec3(1.0, 0.6, 0.15) * s * on * (1.0 + 1.5 * uSpark) * (1.0 - k);
    }
    // ---- Sternschnuppe: kurzer Strich am Himmel
    float mAge = uMeteor.w;
    if (mAge >= 0.0 && mAge < 1.2) {
        vec2 m0 = uMeteor.xy;
        vec2 dir = normalize(vec2(uMeteor.z * 0.7, -0.4));
        vec2 head = m0 + dir * mAge * 0.25;
        float ds = sdSeg(vec2(uv.x * aspect, uv.y), vec2(head.x * aspect, head.y) - dir * 0.08, vec2(head.x * aspect, head.y));
        float e = (1.0 - mAge / 1.2) * skyMask;
        col += vec3(0.9, 0.95, 1.0) * smoothstep(0.004, 0.0, ds) * e * 1.5 + vec3(0.6, 0.7, 1.0) * exp(-ds * 60.0) * e * 0.3;
    }
    // ---- Abschluss: nachts etwas dunkler, weiche Vignette
    col *= 0.9 + 0.1 * (1.0 - night);
    col *= 1.0 - 0.35 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.18);
    fragColor = vec4(col, 1.0);
}
