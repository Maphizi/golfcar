#version 140
// Lagerfeuer: Beduinen-Abend in der Wüste. Himmel mit Lauf des Abends (uDay: Dämmerung, Nacht mit
// Sternen, Milchstraße und großem Mond, Morgengrauen), Dünen in drei Ebenen, die sich leicht bewegen
// (Kämme wandern, Sand weht bei Wind über die Kuppen), Beduinenzelt mit warmem Licht und flatterndem
// Tuch, Teppiche, Kissen und Teetablett ums Feuer, ferne Kamelkarawane. Das Feuer atmet zur Musik:
// Bass pulst die Glut, Anschläge schicken Funken hoch, leise Stellen lassen es kleiner werden.
// Alles weich gezeichnet, kein Pixelraster. uWind legt Flammen und Rauch, uFireT ist die Feuerzeit.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uSeed, uDay, uBassS, uEnergy, uSpark, uWind, uCaravan, uCaravanDir, uFireT;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
float fbm3(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 3; i++) { v += a * noise(p); p = p * 2.1 + 0.3; a *= 0.5; } return v; }
float sdSeg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }
float sdEll(vec2 p, vec2 c, vec2 r) { return length((p - c) / r) - 1.0; }
float sdBox(vec2 p, vec2 b, float r) { vec2 d = abs(p) - b + r; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r; }

// ---- Lauf des Abends: 0 Abenddämmerung, ~0.12..0.85 Nacht, dann Morgengrauen, dann wieder Dämmerung
float nightAmount(float d) { return smoothstep(0.02, 0.16, d) * smoothstep(0.98, 0.84, d); }
vec3 skyColor(vec2 p, float d) {
    float night = nightAmount(d);
    float dusk = smoothstep(0.2, 0.0, d);                       // Abendrot
    float dawn = smoothstep(0.82, 1.0, d);                      // kühler Morgen
    float h = clamp(p.y, 0.0, 1.0);                             // 0 Horizont, 1 oben
    vec3 nightSky = mix(vec3(0.05, 0.07, 0.16), vec3(0.01, 0.015, 0.05), h);
    vec3 duskSky = mix(vec3(0.95, 0.45, 0.15), vec3(0.3, 0.12, 0.35), smoothstep(0.0, 0.7, h));
    vec3 dawnSky = mix(vec3(0.75, 0.6, 0.55), vec3(0.2, 0.3, 0.5), smoothstep(0.0, 0.8, h));
    vec3 sky = nightSky;
    sky = mix(sky, duskSky, dusk);
    sky = mix(sky, dawnSky, dawn);
    return sky;
}
// Dünenkamm-Höhe einer Ebene an Position x (Ebene k), wandert ganz langsam
float duneH(float x, float k, float t) {
    float drift = t * (0.004 + 0.003 * k);
    float h = 0.5 + 0.5 * sin(x * (0.9 + k * 0.4) + uSeed * k + drift);
    h = h * 0.7 + 0.3 * sin(x * (2.3 + k) * 1.1 - drift * 1.7 + uSeed);
    h += 0.25 * fbm3(vec2(x * 1.3 + k * 7.0, k * 3.0 + drift * 0.5)) - 0.12;
    return h;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 p = (vUv - 0.5) * vec2(aspect, 1.0);             // Mitte 0/0, Höhe -0.5..0.5
    float t = iTime;
    float live = 1.0 - uSilent;
    float day = uDay;
    float night = nightAmount(day);
    float dusk = smoothstep(0.2, 0.0, day), dawn = smoothstep(0.82, 1.0, day);
    float horizon = 0.02;                                   // Horizontlinie
    // Feuerparameter
    vec2 fire = vec2(0.0, -0.33);                           // Feuerboden
    float fireSize = 0.55 + 0.45 * uEnergy + 0.25 * uBassS;  // leise: kleiner, laut: größer
    float flick = 0.85 + 0.15 * noise(vec2(uFireT * 9.0, 1.0)) + 0.12 * uBassS;
    float wind = uWind;

    // ---- Himmel
    vec2 skyP = vec2(p.x, (p.y - horizon) / (0.5 - horizon));
    vec3 col = skyColor(skyP, day);
    // Sterne (nur nachts), funkeln; Milchstraße als schräges Band aus Rauschen
    if (p.y > horizon - 0.05) {
        vec2 sg = p * 70.0;
        vec2 cell = floor(sg);
        vec2 f = fract(sg) - 0.5 + (vec2(hash12(cell + 1.0), hash12(cell + 2.0)) - 0.5) * 0.7;
        float h = hash12(cell + uSeed);
        float star = step(0.9, h) * smoothstep(0.09, 0.0, length(f)) * (0.55 + 0.45 * sin(t * (1.5 + h * 3.0) + h * 40.0));
        star *= 0.4 + 0.6 * h;
        vec2 mw = vec2(p.x * 0.8 + p.y * 1.2, -p.x * 0.5 + p.y * 0.7) + t * 0.004;
        float band = exp(-pow((mw.y - 0.25) * 2.2, 2.0));
        float milky = band * smoothstep(0.35, 0.75, fbm(mw * 3.0 + uSeed)) * 0.35;
        float sky_f = night * smoothstep(horizon - 0.05, horizon + 0.15, p.y);
        col += vec3(0.9, 0.92, 1.0) * star * sky_f;
        col += mix(vec3(0.5, 0.55, 0.8), vec3(0.8, 0.7, 0.75), noise(mw * 6.0)) * milky * sky_f;
        col += vec3(1.0) * step(0.985, hash12(cell + uSeed + 5.0)) * smoothstep(0.03, 0.0, length(f)) * sky_f * 0.6;   // helle Sterne
    }
    // Mond: steigt im Lauf der Nacht auf und wandert nach links
    vec2 moonC = vec2(0.55 - 0.9 * smoothstep(0.1, 0.9, day), -0.05 + 0.45 * sin(clamp((day - 0.05) / 0.85, 0.0, 1.0) * 3.14159));
    float moonR = 0.075;
    vec2 md = p - moonC;
    float mr = length(md) / moonR;
    float moonVis = smoothstep(0.03, 0.12, day) * smoothstep(0.97, 0.88, day);
    if (mr < 1.0) {
        vec3 n = vec3(md / moonR, sqrt(max(0.0, 1.0 - mr * mr)));
        float crat = fbm(n.xy * 3.0 + uSeed);
        float craters = smoothstep(0.45, 0.7, fbm3(n.xy * 5.0 + 3.0)) * 0.25;
        vec3 moon = mix(vec3(0.85, 0.85, 0.75), vec3(0.98, 0.97, 0.9), smoothstep(0.4, 0.7, crat)) * (1.0 - craters);
        moon *= 0.55 + 0.45 * clamp(dot(n, normalize(vec3(-0.4, 0.3, 0.85))), 0.0, 1.0);
        col = mix(col, moon, smoothstep(1.0, 0.97, mr) * moonVis);
    }
    col += vec3(0.8, 0.8, 0.7) * exp(-max(mr - 1.0, 0.0) * 4.0) * 0.25 * moonVis * step(1.0, mr);
    // Sonne im Abendrot / Morgengrauen: Glühen am Horizont
    col += vec3(1.0, 0.5, 0.2) * exp(-abs(p.y - horizon) * 10.0) * exp(-abs(p.x + 0.5) * 2.0) * dusk * 0.5;
    col += vec3(0.9, 0.7, 0.5) * exp(-abs(p.y - horizon) * 10.0) * exp(-abs(p.x - 0.6) * 2.0) * dawn * 0.4;

    // ---- Dünen: drei Ebenen von fern nach nah; Sand mit Rippeln, Mond- und Feuerlicht, Sandfahnen bei Wind
    vec3 moonLight = vec3(0.45, 0.5, 0.7) * (0.35 + 0.65 * night) * moonVis + vec3(0.9, 0.55, 0.3) * dusk * 0.6 + vec3(0.7, 0.65, 0.6) * dawn * 0.5;
    vec3 sandBase = vec3(0.78, 0.62, 0.42);
    for (int k = 2; k >= 0; k--) {
        float fk = float(k);
        // ferne Ebene (k = 2) liegt am Horizont, nahe Ebenen (k = 0) weiter unten und größer
        float base = horizon - 0.02 - (2.0 - fk) * 0.1;
        float amp = 0.05 + (2.0 - fk) * 0.05;
        float x = p.x * (1.6 - fk * 0.35) + fk * 3.1;
        float ridge = base + amp * duneH(x, fk, t) * (fk < 1.5 ? 1.0 : 0.8);
        if (p.y < ridge) {
            // Hang: Steigung aus der Ableitung, lichtzugewandte Seite heller
            float e = 0.01;
            float slope = (duneH(x + e, fk, t) - duneH(x - e, fk, t)) / (2.0 * e) * amp;
            float lit = clamp(0.5 - slope * 1.5, 0.0, 1.0);
            float depth = (ridge - p.y);
            float rip = 0.5 + 0.5 * sin((p.x * 60.0 + p.y * 120.0 + fk * 9.0) + fbm3(p * 20.0) * 6.0);   // Sandrippel
            vec3 sand = sandBase * (0.22 + 0.5 * fk / 2.0 * 0.0 + 0.3) * (0.85 + 0.15 * rip);
            sand *= (0.35 + 0.65 * lit);
            sand *= moonLight * 1.6 + 0.05;
            sand *= 1.0 - 0.35 * smoothstep(0.0, 0.25, depth) * (1.0 - fk * 0.3);    // zum Fuß dunkler
            // ferne Ebenen bläulicher und dunkler (Dunst)
            sand = mix(sand, skyColor(vec2(p.x, 0.0), day) * 0.6, fk * 0.22);
            // Feuerlicht auf den nahen Dünen
            float fd = length((p - fire) * vec2(1.0, 1.5));
            sand += vec3(1.0, 0.55, 0.2) * exp(-fd * 3.5) * 0.55 * flick * fireSize * (1.0 - fk * 0.45);
            sand *= 1.0 - 0.25 * fk;                                                // ferne Ebenen dunkler
            col = sand;
        }
        // Sandfahne über dem Kamm bei Wind
        float above = p.y - ridge;
        if (above > 0.0 && above < 0.06) {
            float fx = p.x * 25.0 - t * (2.0 + 6.0 * wind) * (1.0 + fk * 0.3);
            float sandBlow = noise(vec2(fx, p.y * 40.0 + fk)) * smoothstep(0.06, 0.0, above) * wind * 0.35;
            col = mix(col, sandBase * moonLight * 1.5 + vec3(0.15), sandBlow);
        }
    }
    // Sichtbarkeit für die Karawane: nur wo keine nähere Düne (Ebene 0/1) davor liegt
    float nearRidge = -1.0;
    for (int k = 0; k <= 1; k++) {
        float fk = float(k);
        float base = horizon - 0.02 - (2.0 - fk) * 0.1;
        float amp = 0.05 + (2.0 - fk) * 0.05;
        float x = p.x * (1.6 - fk * 0.35) + fk * 3.1;
        nearRidge = max(nearRidge, base + amp * duneH(x, fk, t));
    }
    float farVisible = step(nearRidge, p.y);

    // ---- Karawane: Kamele ziehen als Silhouette über die ferne Düne (Ebene 2)
    if (uCaravan > 0.0 && uCaravan < 1.0) {
        float cx0 = (uCaravan * 2.6 - 1.3) * uCaravanDir;    // von einer Seite zur anderen
        for (int i = 0; i < 5; i++) {
            float fi = float(i);
            float cx = cx0 - fi * 0.06 * uCaravanDir;
            float xr = cx * (1.6 - 2.0 * 0.35) + 2.0 * 3.1;
            float ry = horizon - 0.02 + 0.05 * duneH(xr, 2.0, t) * 0.8;    // auf dem Kamm der fernen Düne
            vec2 c = p - vec2(cx, ry + 0.012);
            float sc = 0.014;
            float walk = sin(t * 2.0 + fi) * 0.15;
            // Körper mit Höcker, Hals, Kopf, Beine
            float body = step(sdEll(c, vec2(0.0, 0.0), vec2(sc * 1.4, sc * 0.75)), 0.0);
            float hump = step(sdEll(c, vec2(-sc * 0.2, sc * 0.6), vec2(sc * 0.6, sc * 0.5)), 0.0);
            float neck = step(sdSeg(c, vec2(sc * 1.2, sc * 0.2), vec2(sc * 1.9 * uCaravanDir, sc * 1.1)), sc * 0.22);
            float head = step(sdEll(c, vec2(sc * 2.0 * uCaravanDir, sc * 1.15), vec2(sc * 0.4, sc * 0.25)), 0.0);
            float legs = 0.0;
            for (int l = 0; l < 4; l++) {
                float fl = float(l);
                float lx = (-0.9 + fl * 0.6) * sc;
                float sw = sin(t * 2.0 + fi + fl * 1.5) * 0.25 * sc;
                legs = max(legs, step(sdSeg(c, vec2(lx, -sc * 0.4), vec2(lx + sw, -sc * 1.5)), sc * 0.12));
            }
            float rider = step(sdEll(c, vec2(sc * 0.3, sc * 1.25 + walk * sc), vec2(sc * 0.25, sc * 0.45)), 0.0) * step(0.5, hash12(vec2(fi, 3.0)));
            float camel = max(max(body, hump), max(max(neck, head), max(legs, rider)));
            float fade = smoothstep(0.0, 0.08, uCaravan) * smoothstep(1.0, 0.92, uCaravan);
            col = mix(col, vec3(0.02, 0.02, 0.03) + col * 0.15, camel * fade * farVisible);
        }
    }

    // ---- Zelt links: dunkles Tuch, Dachkanten, warm leuchtender Eingang, Tuch flattert im Wind
    vec2 tz = p - vec2(-0.58, -0.2);
    float flutter = sin(p.y * 40.0 + t * (4.0 + 10.0 * wind)) * 0.004 * (0.3 + wind);
    vec2 tq = tz + vec2(flutter, 0.0);
    float roof = step(abs(tq.x), 0.26 - max(0.0, tq.y) * 0.9) * step(-0.12, tq.y) * step(tq.y, 0.22);
    float wall = step(abs(tq.x), 0.26) * step(-0.14, tq.y) * step(tq.y, -0.11);
    float tent = max(roof, wall);
    if (tent > 0.5) {
        float stripe = 0.5 + 0.5 * sin(tq.x * 70.0 + tq.y * 20.0);
        vec3 cloth = mix(vec3(0.12, 0.08, 0.06), vec3(0.2, 0.13, 0.08), stripe) * (0.8 + 0.2 * noise(tq * 80.0));
        cloth *= 0.5 + 0.5 * smoothstep(-0.14, 0.2, tq.y);                 // Firstkante heller
        cloth *= 0.4 + 0.6 * night + dusk * 0.8 + dawn * 0.6;
        // Feuerschein auf dem Tuch
        cloth += vec3(1.0, 0.5, 0.2) * exp(-length((p - fire) * vec2(1.0, 1.4)) * 2.5) * 0.5 * flick * fireSize;
        col = cloth;
        // Eingang: warmes Licht von innen, Lampe als heller Punkt, Schatten einer Person
        vec2 dq = tq - vec2(0.06, -0.06);
        float door = step(sdBox(dq, vec2(0.07, 0.085), 0.02), 0.0) * step(-0.14, tq.y);
        float lampGlow = 0.75 + 0.25 * sin(t * 1.3) + 0.1 * noise(vec2(t * 5.0, 2.0));
        vec3 inside = mix(vec3(0.9, 0.5, 0.15), vec3(1.0, 0.85, 0.5), smoothstep(0.1, 0.0, length(dq - vec2(0.0, 0.03)))) * lampGlow;
        float person = step(sdEll(dq, vec2(-0.02, -0.03), vec2(0.022, 0.05)), 0.0) + step(sdEll(dq, vec2(-0.02, 0.03), vec2(0.012, 0.014)), 0.0);
        inside *= 1.0 - 0.85 * clamp(person, 0.0, 1.0);
        col = mix(col, inside, door);
    }
    // Spannseile vom Zelt in den Sand
    float rope = min(sdSeg(p, vec2(-0.84, -0.0), vec2(-0.98, -0.2)), sdSeg(p, vec2(-0.32, -0.0), vec2(-0.2, -0.22)));
    col = mix(col, vec3(0.1, 0.08, 0.06), smoothstep(0.0025, 0.0, rope) * 0.8);
    // Zeltlicht fällt auf den Sand davor
    col += vec3(0.9, 0.5, 0.15) * exp(-length((p - vec2(-0.52, -0.3)) * vec2(1.0, 2.5)) * 5.0) * 0.25 * step(p.y, -0.23);

    // ---- Boden ums Feuer: Teppiche, Kissen, Teetablett (vom Feuer beleuchtet)
    float fireLight = exp(-length((p - fire) * vec2(1.0, 1.6)) * 3.0) * flick * fireSize;
    if (p.y < -0.2) {
        // Teppich links und rechts (Rauten- und Streifenmuster)
        for (int i = -1; i <= 1; i += 2) {
            vec2 rq = p - vec2(float(i) * 0.36, -0.42);
            float rug = step(sdBox(rq, vec2(0.2, 0.06), 0.01), 0.0);
            float stripes = step(0.5, fract(rq.x * 40.0));
            float diamonds = step(abs(fract(rq.x * 12.0) - 0.5) + abs(fract(rq.y * 24.0) - 0.5), 0.35);
            vec3 rugCol = mix(vec3(0.5, 0.1, 0.08), vec3(0.75, 0.55, 0.15), stripes * 0.4 + diamonds * 0.6);
            rugCol = mix(rugCol, vec3(0.1, 0.15, 0.35), step(abs(rq.y), 0.06) * step(0.055, abs(rq.y)));   // Bordüre
            col = mix(col, rugCol * (0.15 + 1.6 * fireLight), rug);
            // Kissen
            vec2 kq = rq - vec2(float(-i) * 0.05, 0.03);
            float cushion = step(sdEll(kq, vec2(0.0), vec2(0.07, 0.035)), 0.0);
            vec3 kc = (i < 0 ? vec3(0.2, 0.35, 0.55) : vec3(0.6, 0.2, 0.3)) * (0.15 + 1.5 * fireLight) * (0.8 + 0.4 * smoothstep(0.0, -0.035, kq.y));
            col = mix(col, kc, cushion);
        }
        // Teetablett rechts vorn: Tablett, Kanne mit Tülle, drei Gläser
        vec2 tt = p - vec2(0.22, -0.47);
        float tray = step(sdEll(tt, vec2(0.0), vec2(0.11, 0.03)), 0.0);
        col = mix(col, vec3(0.7, 0.55, 0.25) * (0.2 + 1.8 * fireLight), tray);
        vec2 pot = tt - vec2(-0.03, 0.035);
        float potB = step(sdEll(pot, vec2(0.0), vec2(0.03, 0.03)), 0.0) + step(sdSeg(pot, vec2(0.025, 0.0), vec2(0.05, 0.035)), 0.006) + step(sdSeg(pot, vec2(0.0, 0.03), vec2(0.0, 0.045)), 0.005);
        col = mix(col, vec3(0.75, 0.6, 0.3) * (0.2 + 1.8 * fireLight) * (0.6 + 0.6 * smoothstep(0.03, -0.01, pot.x)), clamp(potB, 0.0, 1.0));
        for (int g = 0; g < 3; g++) {
            vec2 gq = tt - vec2(0.03 + float(g) * 0.025, 0.02);
            float glass = step(sdBox(gq, vec2(0.006, 0.012), 0.002), 0.0);
            col = mix(col, vec3(0.9, 0.5, 0.2) * (0.3 + 1.5 * fireLight), glass);
        }
    }

    // ---- Feuer: Holzscheite, Glut, Flammen (fbm, nach oben gezogen), Funken, Rauch, Hitzeflimmern
    vec2 fq = p - fire;
    // Holz: drei Scheite, verkohlt, mit glühenden Rissen
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float ang = -0.5 + fi * 0.5;
        vec2 a = vec2(cos(ang), sin(ang) * 0.35) * 0.1, b = -a;
        vec2 lq = fq - vec2(0.0, 0.015 + fi * 0.006);
        float d = sdSeg(lq, a, b);
        float logm = smoothstep(0.016, 0.013, d);
        float ember = smoothstep(0.65, 0.9, noise(lq * 90.0 + fi * 5.0 + uFireT * 0.5)) * (0.5 + 0.5 * uBassS + 0.3 * sin(uFireT * 6.0 + fi));
        vec3 logc = mix(vec3(0.08, 0.05, 0.03), vec3(1.0, 0.35, 0.05), ember) * (0.6 + 0.6 * fireLight);
        col = mix(col, logc, logm);
    }
    // Glutbett
    float bed = smoothstep(0.1, 0.0, length(fq * vec2(1.0, 3.0)));
    col += vec3(1.0, 0.35, 0.05) * bed * (0.6 + 0.8 * uBassS) * flick;
    // Flammen
    {
        float height = 0.3 * fireSize;
        vec2 f = fq;
        f.x -= wind * 0.12 * clamp(f.y, 0.0, 1.0) * (1.0 + 0.3 * sin(uFireT * 7.0));          // Wind legt die Flamme
        float ny = clamp(f.y / height, 0.0, 1.0);
        vec2 nq = vec2(f.x * 9.0, f.y * 5.0 - uFireT * 3.0);
        float n = fbm(nq + vec2(0.0, uFireT * 0.5));
        float n2 = fbm(nq * 2.2 + vec2(uFireT * 0.8, -uFireT * 2.0));
        float width = (0.1 + 0.04 * uBassS) * (1.0 - ny * 0.85) * (0.7 + 0.6 * n);
        float shape = smoothstep(width, width * 0.3, abs(f.x + (n - 0.5) * 0.08 * ny)) * step(0.0, f.y) * smoothstep(height * 1.05, height * 0.5, f.y);
        float flame = shape * (0.6 + 0.6 * n2) * smoothstep(0.0, 0.05, f.y + 0.02);
        vec3 fc = mix(vec3(1.0, 0.95, 0.6), vec3(1.0, 0.5, 0.05), smoothstep(0.0, 0.5, ny));
        fc = mix(fc, vec3(0.8, 0.15, 0.02), smoothstep(0.5, 1.0, ny));
        col = mix(col, fc, clamp(flame * 1.3, 0.0, 1.0));
        col += fc * flame * 0.6;
        // Glühen in die Umgebung
        col += vec3(1.0, 0.55, 0.2) * exp(-length(fq * vec2(1.0, 1.2)) * 6.0) * 0.5 * flick * fireSize;
        // Rauch darüber
        vec2 sq = vec2(fq.x - wind * 0.3 * max(0.0, fq.y) - 0.02 * sin(uFireT + fq.y * 8.0), fq.y);
        float smoke = fbm(vec2(sq.x * 6.0, sq.y * 3.0 - uFireT * 0.8)) * smoothstep(0.0, 0.25, fq.y) * smoothstep(0.9, 0.3, fq.y) * smoothstep(0.2, 0.0, abs(sq.x) - 0.02 * fq.y * 3.0);
        col = mix(col, col * 0.6 + vec3(0.25, 0.22, 0.2), smoothstep(0.35, 0.7, smoke) * 0.45);
    }
    // Funken: steigen auf, flackern, mehr bei Anschlägen
    for (int i = 0; i < 20; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, uSeed)), h2 = hash12(vec2(fi + 20.0, uSeed));
        float life = 1.2 + h2 * 1.5;
        float age = mod(uFireT * 0.9 + h1 * life, life);
        float k = age / life;
        vec2 sp = fire + vec2((h1 - 0.5) * 0.08 + k * k * (0.08 + wind * 0.25) * (h2 - 0.3) + 0.02 * sin(age * 6.0 + fi), 0.02 + k * (0.3 + 0.2 * h2) * fireSize);
        float sz = 0.004 * (1.0 - k * 0.7);
        float s = smoothstep(sz, 0.0, length(p - sp));
        float on = step(0.5 - 0.5 * uSpark, h2 * (1.0 - k)) * (0.6 + 0.4 * sin(age * 30.0 + fi));
        col += vec3(1.0, 0.6, 0.15) * s * on * (1.0 + 1.5 * uSpark) * (1.0 - k);
    }

    // ---- Abschluss: nachts etwas dunkler, warme Vignette am Rand
    col *= 0.85 + 0.15 * (1.0 - night);
    col *= 1.0 - 0.4 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.25);
    fragColor = vec4(col, 1.0);
}
