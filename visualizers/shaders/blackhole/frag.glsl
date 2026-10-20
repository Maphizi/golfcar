#version 140
// Schwarzes Loch: Strahlverfolgung mit Lichtkrümmung. Akkretionsscheibe aus glühendem Gas, die sich
// über und unter dem Loch wölbt (Gravitationslinse), Photonenring, Doppler-Helligkeit (die Seite,
// die auf uns zukommt, ist heller), gekrümmter Sternenhintergrund, Jet aus den Polen.
// Musik: Bass pulst Scheibe und Linse, das Spektrum liegt als Ringe auf der Scheibe (innen Bass,
// außen Höhen), Mitten färben das Gas heißer, der Beat zündet Jet und Flare (vom Controller geglättet),
// Höhen lassen die Scheibe funkeln. uZoom = Nahaufnahme.
// Geworfene Planeten (uThrow0/1): werden in Bildkoordinaten als Band gezeichnet, das sich spiralig ins
// Loch zieht, dabei immer länger und dünner wird (Spaghettisierung), schlangenförmig zur Musik wogt,
// die Farben langsam durchwandert und am Horizont rot verglüht.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uSeed, uTilt, uAngle, uPalette, uJet, uFlare, uZoom, uBassS, uMidS, uSnakeT;
uniform float uThrow0, uThrow1;                      // Fortschritt 0..1 (0 = kein Planet)
uniform vec2 uThrowPos0, uThrowPos1;                 // Startpunkt (Bildkoordinaten, Mitte 0/0)
uniform vec3 uThrowColA0, uThrowColB0, uThrowColA1, uThrowColB1;
uniform vec4 uThrowPar0, uThrowPar1;                 // Größe, Typ, Seed, Spirale (±Stärke)
uniform vec4 uThrowPar20, uThrowPar21;               // Ringe, frei
uniform float uSwarm;                                // Asteroidenschwarm: Fortschritt 0..1 (0 = keiner)
uniform vec2 uSwarmPos;
uniform vec4 uSwarmPar;                              // Seed, Spirale, Anzahl, 1 = wird ausgespuckt
uniform float uEjectT;                               // Umkehrung: Sekunden seit Auslösung, -1 = aus
uniform float uDiskT;                                // Scheibenzeit (läuft bei der Umkehrung rückwärts)

const int STEPS = 36;      // Pi 5: 64 Schritte bei 0.5 = 9 fps, 36 bei 0.35 ≈ 40 fps
const float R_H = 1.0;       // Horizont
const float R_IN = 2.3;      // Innenrand der Scheibe
const float R_OUT = 11.0;    // Außenrand

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p) { p = fract(p * vec3(0.1031, 0.1030, 0.0973)); p += dot(p, p.yxz + 33.33); return fract((p.x + p.y) * p.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 3; i++) { v += a * noise(p); p = p * 2.07 + 3.1; a *= 0.5; } return v; }
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

// Farbe des Gases nach Temperatur (0 kühl außen, 1 heiß innen) und Palette
vec3 gasColor(float temp, float heat) {
    vec3 cool, hot;
    if (uPalette < 0.5)      { cool = vec3(1.0, 0.30, 0.05); hot = vec3(1.0, 0.82, 0.55); }
    else if (uPalette < 1.5) { cool = vec3(0.25, 0.15, 1.0); hot = vec3(0.65, 0.85, 1.0); }
    else                     { cool = vec3(0.85, 0.10, 0.08); hot = vec3(1.0, 0.75, 0.35); }
    vec3 c = mix(cool, hot, smoothstep(0.0, 1.0, temp));
    return mix(c, vec3(0.75, 0.9, 1.0), heat * 0.5 * temp);     // Mitten: blauweißer
}
// Emission der Scheibe an Punkt (r, phi), Sichtrichtung rd (für Doppler)
vec3 diskEmission(vec3 p, vec3 rd, float t, float live, out float alpha) {
    float r = length(p.xz);
    float phi = atan(p.z, p.x);
    float u = (r - R_IN) / (R_OUT - R_IN);                 // 0 innen, 1 außen
    // Keplerrotation: innen schnell. Gaswirbel in log-polar-Koordinaten plus zwei Spiralarme
    float omega = 1.1 * pow(r, -1.5);
    float ang = phi + uDiskT * omega * 3.0;
    vec2 q = vec2(ang * 2.2, log(r) * 5.5 + uSeed);
    float n = fbm(q + vec2(0.0, -uDiskT * 0.08));
    float spiral = 0.5 + 0.5 * sin(ang * 2.0 - log(r) * 5.0 + uSeed);
    float dens = smoothstep(0.25, 0.8, n * 0.8 + spiral * 0.35);
    // Spektrum als Ringe: Position auf der Scheibe entspricht Frequenz
    float band = spec(u);
    dens *= 0.5 + 1.2 * band * live + 0.3 * (1.0 - live);
    // Funkeln bei Höhen
    dens += uHigh * live * step(0.985, hash13(vec3(floor(q * 6.0), floor(t * 20.0)))) * 2.0;
    // Kanten weich, innen am hellsten
    float edge = smoothstep(0.0, 0.08, u) * smoothstep(1.0, 0.65, u);
    float bright = (0.22 + 0.9 * pow(1.0 - u, 2.0)) * (1.0 + 1.2 * uBassS);
    // Doppler: Tangentialgeschwindigkeit gegen Blickrichtung
    vec3 vel = normalize(vec3(-p.z, 0.0, p.x));
    float dop = dot(vel, -rd);
    float beam = pow(clamp(1.0 + 0.7 * dop, 0.25, 1.9), 2.0);
    float temp = pow(1.0 - u, 1.3) + 0.3 * dop;
    alpha = clamp(dens * edge * 0.9, 0.0, 1.0);
    return gasColor(clamp(temp, 0.0, 1.0), uMid * live) * bright * beam * dens * edge;
}
vec3 background(vec3 d, float t) {
    // Sterne auf der Kugel plus schwacher Nebel, beide werden durch die Linse mitgezogen
    vec2 s = vec2(atan(d.z, d.x), asin(clamp(d.y, -1.0, 1.0)));
    vec2 cell = floor(s * vec2(70.0, 45.0));
    float h = hash12(cell + uSeed);
    vec2 f = fract(s * vec2(70.0, 45.0)) - 0.5;
    float star = step(0.955, h) * smoothstep(0.35, 0.0, length(f)) * (0.6 + 0.4 * sin(t * 2.0 + h * 40.0));
    vec3 col = vec3(star) * (0.6 + 0.6 * hash12(cell + 2.0));
    float neb = fbm(s * vec2(2.0, 3.0) + uSeed);
    col += mix(vec3(0.25, 0.05, 0.35), vec3(0.05, 0.15, 0.4), noise(s * 3.0)) * smoothstep(0.5, 0.85, neb) * 0.35;
    return col;
}

// ---- Geworfener Planet als Spaghetti-Band
vec3 hueShift(vec3 c, float a) {
    const vec3 k = vec3(0.57735);
    float cs = cos(a), sn = sin(a);
    return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs);
}
// Punkt auf der Bahn: s 0 = Startpunkt, 1 = Loch. Spirale, die sich zum Loch hin enger zieht, dazu
// Schlangenwellen quer zur Bahn, deren Stärke und Tempo von der Musik kommen (uBassS, uMidS, uSnakeT).
vec2 pathPoint(vec2 p0, float s, float swirl, float seed, float wob) {
    float rad = pow(1.0 - s, 1.15);
    vec2 q = rot(swirl * pow(s, 2.4) * 2.4) * p0 * rad;            // nahe am Loch wickelt sich die Bahn herum
    vec2 dir = q / max(length(q), 1e-4);
    vec2 nrm = vec2(-dir.y, dir.x);
    float w = 0.6 * sin(s * 9.0 - uSnakeT * 1.3 + seed) + 0.4 * sin(s * 17.0 + uSnakeT * 0.7 + seed * 2.0);
    return q + nrm * w * wob * (1.0 - s) * length(p0) * 0.22;
}
float segDist(vec2 p, vec2 a, vec2 b, out float h) {
    vec2 ab = b - a, ap = p - a;
    h = clamp(dot(ap, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
    return length(ap - ab * h);
}
vec3 ribbon(vec3 col, vec2 uv, float P, vec2 p0, vec3 cA, vec3 cB, vec4 par, vec4 par2, float live) {
    float size = par.x, kind = par.y, seed = par.z, swirl = par.w;
    float wob = 0.35 + 0.9 * uBassS * live + 0.5 * uMidS * live;
    float sH = pow(P, 1.5);                             // Kopf: erst langsam, dann schneller zum Loch
    float sT = pow(P, 3.4) * 0.9;                       // Schwanz hinkt nach: erst Kugel, dann immer längeres Band
    const int N = 22;
    float dmin = 1e9, sAt = 0.0, sideAt = 0.0;
    vec2 qAt = vec2(0.0);
    vec2 prev = pathPoint(p0, sT, swirl, seed, wob);
    for (int j = 1; j <= N; j++) {
        float s1 = mix(sT, sH, float(j) / float(N));
        vec2 cur = pathPoint(p0, s1, swirl, seed, wob);
        float h;
        float d = segDist(uv, prev, cur, h);
        if (d < dmin) {
            dmin = d;
            sAt = mix(mix(sT, sH, float(j - 1) / float(N)), s1, h);
            vec2 e = cur - prev;
            sideAt = sign(e.x * (uv.y - prev.y) - e.y * (uv.x - prev.x));
            qAt = mix(prev, cur, h);
        }
        prev = cur;
    }
    // Breite: mit der Zeit dünner (die Enden sind durch den Abstand zur Linie von selbst rund),
    // entlang des Bands leicht geknotet (Gezeitenkräfte)
    float along = (sAt - sT) / max(sH - sT, 1e-4);
    float w = size * mix(1.0, 0.22, smoothstep(0.1, 1.0, P)) * (0.9 + 0.1 * sin(along * 40.0 + seed) * smoothstep(0.2, 0.6, P));
    float v = dmin / max(w, 1e-4);
    float rq = length(qAt);
    float rh = mix(0.15, 0.2, uZoom);                   // Schattenradius des Lochs im Bild
    float vanish = smoothstep(rh * 0.95, rh * 1.35, rq); // am Horizont verschwinden
    float heat = smoothstep(rh * 2.8, rh * 1.1, rq);    // Glut nahe am Loch
    float alpha = smoothstep(1.0, 0.85, v) * vanish * smoothstep(1.0, 0.95, P) * smoothstep(0.0, 0.04, P);
    if (alpha <= 0.0 && v > 3.0) return col;
    // Oberfläche: Bänder entlang des Körpers, Farben des Planeten, langsam psychedelisch durchwandernd
    float nz = sqrt(max(0.0, 1.0 - v * v));
    float n = fbm(vec2(sAt * 28.0 + seed, sideAt * v * 2.5 + seed * 0.3) + uSnakeT * 0.05);
    vec3 surf = mix(cA, cB, smoothstep(0.3, 0.7, n));
    surf = hueShift(surf, (0.1 + 1.6 * P * P) * sin(along * 9.0 - uSnakeT * 0.3 + seed));          // Farben wandern langsam durch, je gestreckter desto bunter
    if (kind > 5.5 && kind < 6.5) surf = mix(cA, cB, 0.5 + 0.5 * sin(sAt * 90.0 + n * 4.0));         // Gasplanet: Streifen
    if (kind > 12.5) surf = mix(vec3(0.5, 0.52, 0.56), vec3(0.25), step(0.5, fract(sAt * 60.0)) * step(0.5, fract(v * 4.0)));  // Station
    if (kind > 3.5 && kind < 4.5) surf += vec3(1.0, 0.85, 0.5) * step(0.93, hash12(floor(vec2(sAt * 120.0, sideAt * v * 6.0)) + seed)) * 0.8;  // Stadtlichter
    // Licht: Kugelschattierung, die dem Loch (und der Scheibe) zugewandte Seite heller
    vec2 toHole = -qAt / max(rq, 1e-4);
    vec3 nrm3 = vec3((uv - qAt) / max(w, 1e-4), nz);
    vec3 L = normalize(vec3(toHole * 0.8, 0.6));
    float light = 0.28 + 0.8 * max(dot(normalize(nrm3), L), 0.0);
    light += 0.25 * pow(max(dot(normalize(nrm3), normalize(L + vec3(0.0, 0.0, 1.0))), 0.0), 12.0);   // Glanz
    vec3 body = surf * light;
    if (kind > 10.5 && kind < 11.5) body = surf * (1.6 + 1.2 * nz) + vec3(1.0, 0.9, 0.7) * pow(nz, 3.0);   // Stern: leuchtet selbst
    if (kind > 11.5 && kind < 12.5) body = mix(surf * light, vec3(0.8, 0.9, 1.0), pow(1.0 - nz, 2.0) * 0.5);  // Komet: Koma
    // Nahe am Loch: rotverschoben, glühend, dann weg
    vec3 glow = gasColor(0.8, 0.0);
    body = mix(body, vec3(dot(body, vec3(0.5, 0.4, 0.1))) * vec3(1.0, 0.25, 0.08), heat * 0.8);
    body += glow * heat * (1.4 + 0.8 * uBassS * live) * (0.4 + 0.6 * nz);
    col = mix(col, body, alpha);
    // Halo außen: Stern/Komet stärker, sonst zart; am Horizont ein roter Schweif
    float halo = exp(-max(v - 1.0, 0.0) * mix(6.0, 2.0, heat)) * vanish * smoothstep(1.0, 0.9, P);
    float haloK = (kind > 10.5 && kind < 12.5) ? 0.45 : 0.08;
    col += mix(cA, glow, heat) * halo * (haloK + 0.6 * heat);
    // Ringsystem (z. B. Saturn): zwei dünne Linien neben dem Körper, verschwinden mit der Streckung
    if (par2.x > 0.5) {
        float ring = smoothstep(0.12, 0.0, abs(v - 1.9)) + smoothstep(0.1, 0.0, abs(v - 2.4)) * 0.6;
        col += mix(cA, vec3(0.9, 0.85, 0.75), 0.5) * ring * 0.5 * smoothstep(0.3, 0.08, P) * vanish * smoothstep(0.0, 0.04, P);
    }
    return col;
}

// ---- Asteroidenschwarm: Kette aus Brocken auf der Spiralbahn, jeder wackelt für sich
vec3 swarm(vec3 col, vec2 uv, float P, vec2 p0, vec4 par, float live) {
    float seed = par.x, swirl = par.y, cnt = par.z, back = par.w;
    float wob = 0.3 + 0.8 * uBassS * live + 0.4 * uMidS * live;
    float rh = mix(0.15, 0.2, uZoom);
    float head = pow(P, 1.3);
    vec3 glow = gasColor(0.8, 0.0);
    for (int i = 0; i < 28; i++) {
        float fi = float(i);
        if (fi >= cnt) break;
        float h1 = hash12(vec2(fi, seed)), h2 = hash12(vec2(fi * 3.0 + 1.0, seed)), h3 = hash12(vec2(fi * 7.0 + 2.0, seed));
        float s = head - fi * (0.022 + 0.014 * h1) * (0.5 + 0.7 * P);     // Perlenkette hinter dem Kopf
        if (s <= 0.0 || s >= 1.0) continue;
        vec2 c = pathPoint(p0, s, swirl, seed + fi * 0.37, wob * (0.5 + h2));
        vec2 dir0 = normalize(c + 1e-5);
        c += vec2(-dir0.y, dir0.x) * (h2 - 0.5) * 0.09 * (1.0 - s);         // quer zur Bahn gestreut
        // eigener Wackler je Brocken
        c += vec2(sin(uSnakeT * 1.7 + fi * 1.3), cos(uSnakeT * 1.3 + fi * 2.1)) * 0.012 * (0.3 + uBassS * live);
        float rq = length(c);
        float vanish = smoothstep(rh * 0.95, rh * 1.3, rq);
        if (vanish <= 0.0) continue;
        float heat = smoothstep(rh * 2.8, rh * 1.1, rq);
        float size = (0.009 + 0.016 * h3) * (1.0 - 0.35 * smoothstep(0.5, 1.0, s));
        vec2 d = uv - c;
        // nahe am Loch in Bahnrichtung langgezogen
        vec2 dir = normalize(c - pathPoint(p0, s - 0.01, swirl, seed + fi * 0.37, wob * (0.5 + h2)) + 1e-5);
        vec2 dl = vec2(dot(d, dir) / (1.0 + 2.5 * heat), dot(d, vec2(-dir.y, dir.x)));
        float ang = atan(dl.y, dl.x);
        float rr = size * (0.8 + 0.25 * sin(ang * 3.0 + h1 * 9.0) + 0.1 * sin(ang * 7.0 + h2 * 5.0));   // unregelmäßig
        float v = length(dl) / rr;
        if (v > 1.6) continue;
        float nz = sqrt(max(0.0, 1.0 - v * v));
        vec3 N = normalize(vec3(dl / rr, nz));
        vec3 L = normalize(vec3(-c * 0.8, 0.6));
        float light = 0.25 + 0.75 * max(dot(N, L), 0.0);
        vec3 rock = mix(vec3(0.26, 0.22, 0.19), vec3(0.45, 0.4, 0.35), h2) * light;
        rock += vec3(1.0, 0.45, 0.12) * uBassS * live * (0.3 + 0.7 * step(0.5, h3)) * pow(nz, 2.0) * 0.8;   // Bass: Glut in den Rissen
        rock += vec3(1.0, 0.95, 0.85) * uHigh * live * step(0.7, h1) * pow(nz, 8.0) * 1.5;                 // Höhen: Funkeln
        rock = mix(rock, vec3(dot(rock, vec3(0.5, 0.4, 0.1))) * vec3(1.0, 0.3, 0.1), heat * 0.7);
        rock += glow * heat * (1.2 + 0.6 * uBassS * live) * (0.4 + 0.6 * nz);
        if (back > 0.5) rock += vec3(1.0, 0.6, 0.3) * 0.5;                                               // ausgespuckt: glüht nach
        float a = smoothstep(1.0, 0.8, v) * vanish * smoothstep(0.0, 0.03, P);
        col = mix(col, rock, a);
        col += mix(vec3(0.6, 0.5, 0.4), glow, heat) * exp(-max(v - 1.0, 0.0) * 5.0) * vanish * (0.05 + 0.4 * heat);
    }
    return col;
}
// ---- Umkehrung: das Loch spuckt aus. et = Sekunden seit Auslösung (Ausbruch bei 1.2 s)
vec3 ejectFx(vec3 col, vec2 uv, float et, float fov, float live) {
    float screenR = length(uv) / fov;
    float build = clamp(et / 1.2, 0.0, 1.0);
    float bt = et - 1.2;                                   // Zeit seit dem Ausbruch
    vec3 hot = gasColor(0.9, 0.0);
    if (bt < 0.0) {
        // Anschwellen: Glut um das Loch pulst immer schneller, Bild wird nach innen gezogen
        float pulse = 0.5 + 0.5 * sin(et * et * 14.0);
        col += hot * exp(-screenR * 2.0) * build * (0.4 + 0.5 * pulse);
        col *= 1.0 - 0.25 * build * smoothstep(0.3, 1.2, screenR);
        return col;
    }
    // Blitz und Druckwelle
    col += vec3(1.0, 0.95, 0.85) * exp(-bt * 5.0) * exp(-screenR * 1.2) * 2.5;
    float ringR = bt * 0.9;
    float ring = exp(-pow((screenR - ringR) * 14.0, 2.0)) * exp(-bt * 0.7);
    col += mix(hot, vec3(0.7, 0.85, 1.0), 0.5 + 0.5 * sin(bt * 3.0)) * ring * 1.3;
    col = mix(col, col * 1.6, ring * 0.5);
    // Trümmerfontäne: Partikel fliegen aus dem Loch nach außen, leicht verdreht, mit Schweif
    for (int k = 0; k < 44; k++) {
        float fk = float(k);
        float a0 = hash12(vec2(fk, 3.0)) * 6.2832;
        float sp = 0.18 + 0.4 * hash12(vec2(fk, 5.0));
        float life = 3.0 + 3.0 * hash12(vec2(fk, 9.0));
        float age = bt - hash12(vec2(fk, 7.0)) * 0.6;      // nicht alle zugleich
        if (age < 0.0 || age > life) continue;
        float a1 = a0 + 0.5 * (hash12(vec2(fk, 11.0)) - 0.5) * age;
        vec2 dir = vec2(cos(a1), sin(a1));
        vec2 pos = dir * (0.12 + sp * age * (1.0 - 0.06 * age));
        float sz = (0.007 + 0.012 * hash12(vec2(fk, 13.0))) * (1.0 - 0.6 * age / life);
        vec2 d = uv - pos;
        float along = dot(d, dir), side = dot(d, vec2(-dir.y, dir.x));
        float tail = sp * 0.12;
        float dist = length(vec2(max(0.0, -along) - max(0.0, -along - tail) + max(0.0, along), side));  // Strecke mit Schweif
        float g = smoothstep(sz, 0.0, dist) + 0.5 * exp(-dist / (sz * 2.0));
        float fade = (1.0 - age / life) * (0.6 + 0.4 * uBassS * live);
        vec3 pc = mix(vec3(1.0, 0.85, 0.5), vec3(0.9, 0.3, 0.1), age / life);
        col += pc * g * fade * 1.3;
    }
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = (vUv - 0.5) * vec2(aspect, 1.0);
    float t = iTime;
    float live = 1.0 - uSilent;
    // Kamera: kreist, leicht geneigt, bei Zoom näher dran; Bass schüttelt minimal
    float dist = mix(26.0, 16.0, uZoom);
    float tilt = uTilt + 0.1 * uZoom;
    vec3 ro = vec3(sin(uAngle) * cos(tilt), sin(tilt), cos(uAngle) * cos(tilt)) * dist;
    ro += vec3(hash12(vec2(floor(t * 30.0), 1.0)) - 0.5, hash12(vec2(floor(t * 30.0), 2.0)) - 0.5, 0.0) * 0.08 * uBassS * live;
    vec3 fw = normalize(-ro);
    vec3 rt = normalize(cross(vec3(0.0, 1.0, 0.0), fw));
    vec3 up = cross(fw, rt);
    float fov = mix(0.62, 0.8, uZoom);
    vec3 rd = normalize(fw + uv.x * rt * fov + uv.y * up * fov);
    vec3 p = ro, v = rd;
    vec3 col = vec3(0.0);
    float T = 1.0;                                 // Transmission
    float G = 2.4 * (1.0 + 0.25 * uBassS * live);  // Linsenstärke
    float glow = 0.0;
    bool captured = false, escaped = false;
    float yPrev = p.y;
    float minR = 100.0;
    for (int i = 0; i < STEPS; i++) {
        float r = length(p);
        minR = min(minR, r);
        if (r < R_H) { captured = true; break; }
        if (r > 60.0 && dot(p, v) > 0.0) { escaped = true; break; }
        // Schrittweite: fein nahe am Loch und nahe der Scheibenebene
        float ds = clamp(r * 0.3, 0.08, 2.6);
        ds = min(ds, max(abs(p.y) * 1.2, 0.08) + 0.35);
        // Lichtablenkung (Newton-Näherung, stärker nahe am Horizont)
        vec3 acc = -p * (G / (r * r * r)) * (1.0 + 1.5 / r);
        v = normalize(v + acc * ds);
        vec3 pn = p + v * ds;
        // Scheibenebene durchquert?
        if (sign(pn.y) != sign(yPrev) && T > 0.02) {
            float k = clamp(yPrev / (yPrev - pn.y), 0.0, 1.0);
            vec3 hit = mix(p, pn, k);
            float rh = length(hit.xz);
            if (rh > R_IN && rh < R_OUT) {
                float a;
                vec3 e = diskEmission(hit, v, t, live, a);
                col += e * T;
                glow += a * T;
                T *= 1.0 - a * 0.85;
            }
        }
        // Volumenglühen nahe der Ebene (dicke, dunstige Scheibe) und Photonenring-Glühen
        float rp = length(pn.xz);
        float thick = 0.18 + 0.35 * uBassS * live;
        if (rp > R_IN * 0.9 && rp < R_OUT) {
            float h = exp(-abs(pn.y) / thick) * ds * 0.045 * (1.0 - smoothstep(R_IN, R_OUT, rp));
            col += gasColor(1.0 - (rp - R_IN) / (R_OUT - R_IN), uMid * live) * h * T * (0.6 + 1.5 * uBassS);
        }
        // Jet: Säule entlang der Achse, nach dem Beat
        if (uJet > 0.01 && abs(pn.y) > 2.2 && rp < 2.6) {
            float jl = abs(pn.y);
            float jn = noise(vec2(jl * 1.2 - t * 12.0, atan(pn.z, pn.x) * 2.0 + uSeed));
            float width = 0.35 + jl * 0.09;
            float jr = smoothstep(width * (0.7 + 0.5 * jn), 0.0, rp);
            float jf = smoothstep(16.0 * uJet + 2.0, 2.0, jl) * uJet;
            col += mix(vec3(0.45, 0.75, 1.0), vec3(1.0, 0.95, 0.9), jn) * jr * jf * ds * 1.2 * T;
        }
        yPrev = pn.y;
        p = pn;
    }
    if (escaped || (!captured && length(p) > 12.0)) {
        col += background(normalize(v), t) * T;
    }
    // Photonenring: Strahlen, die dem Horizont sehr nah kamen und doch entkommen sind
    float ring = exp(-pow((minR - 1.5) * 3.5, 2.0)) * (1.0 - float(captured));
    col += gasColor(0.95, uMid * live) * ring * (0.5 + 0.8 * uBassS * live + 2.0 * uFlare);
    // Flare nach dem Beat: kurzer Lichtblitz um das Loch
    float screenR = length(uv) / fov;
    col += gasColor(0.7, 0.0) * exp(-screenR * 2.5) * uFlare * 0.9;
    // Geworfene Planeten (vor der Kamera, deshalb über dem Bild)
    if (uThrow0 > 0.0) col = ribbon(col, uv, uThrow0, uThrowPos0, uThrowColA0, uThrowColB0, uThrowPar0, uThrowPar20, live);
    if (uThrow1 > 0.0) col = ribbon(col, uv, uThrow1, uThrowPos1, uThrowColA1, uThrowColB1, uThrowPar1, uThrowPar21, live);
    if (uSwarm > 0.0) col = swarm(col, uv, uSwarm, uSwarmPos, uSwarmPar, live);
    if (uEjectT >= 0.0) col = ejectFx(col, uv, uEjectT, fov, live);
    // Tonemapping und Vignette
    col = col / (1.0 + col * 0.45);
    col *= 1.0 - 0.45 * pow(length(vUv - 0.5) * 1.35, 2.5);
    fragColor = vec4(col, 1.0);
}
