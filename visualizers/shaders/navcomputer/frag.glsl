#version 140
// F2 – Navigationscomputer: Planet im Sternenfeld, Anflug in vier Phasen.
// uPhase: 0 browse, 1 launch (Sterne werden zu Streifen), 2 cruise (psychedelischer Schweif), 3 arrive (Ziel wächst).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uPhase, uPhaseT, uSlide, uPlanetType, uPlanetSize, uRings, uMoons, uLaunchS, uCruiseS, uArriveS;
// Vorbeiflug im Hyperraum (Controller): uFly 0..1 Fortschritt (0 = keiner), Typ, Farben, Größe, Ringe, Seite
uniform float uFly, uFlyType, uFlySize, uFlyRings, uFlySide;
uniform vec3 uFlyColA, uFlyColB;
uniform sampler2D uSponsorTex;
uniform float uSponsorOK;
// Verkehr im Hyperraum: uShipN = (x, y, Größe, Art), uShipPN = (Alpha, Drehung, Fortschritt, Richtung)
uniform vec4 uShip0, uShip1, uShip2, uShipP0, uShipP1, uShipP2;
uniform vec2 uCross, uLaserTo;
uniform float uLaser, uBoomKind, uShoot;
uniform vec4 uBoom;             // (x, y, Alter in s, Größe)
// Ereignisse unterwegs: uEvent 0 keins, 1 Asteroidenfeld, 2 Farbnebel, 3 Sonne, 4 Wurmloch (5/6 laufen über den Verkehr)
uniform float uEvent, uEventT, uEventLen, uEventWarn, uEventSeed, uShield;
uniform vec4 uImpact;           // Einschlag: x, y, Alter in s
uniform vec4 uFlash;            // Blitz im Nebel: Winkel, Alter in s

vec3 gA, gB;      // Farben des gerade gezeichneten Objekts (Hauptplanet oder Vorbeiflug)
uniform vec3 uColA, uColB;

const float PI = 3.14159265;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float hash3(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float vn3(vec3 p) {
    vec3 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y);
    float b = mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y);
    return mix(a, b, f.z);
}
float vfbm3(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * vn3(p); p = p * 2.1 + 3.0; a *= 0.5; }
    return v;
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.1 + 5.0; a *= 0.5; }
    return v;
}

mat2 rot2(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdBox2(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
float sdSeg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }
// Einfache Beleuchtung einer Silhouette: hell oben links, dunkel unten rechts
vec3 hullShade(vec3 base, vec2 q, float d) {
    float edge = smoothstep(0.0, -0.08, d);
    float light = 0.55 + 0.45 * clamp(0.5 - q.y * 1.5 - q.x * 0.5, 0.0, 1.0);
    return base * light * (0.7 + 0.3 * edge);
}
// Schiff der Art kind an Position c, Größe s (Halbbreite), Drehung a. Gibt Farbe und Deckung zurück.
vec4 ship(vec2 p, vec2 c, float s, int kind, float a, float t, float dir) {
    vec2 q = rot2(a) * (p - c) / max(s, 0.0005);
    q.x *= dir;
    vec3 col = vec3(0.0);
    float alpha = 0.0;
    if (kind == 0) {                                   // Jäger: Kugel mit Fenster, zwei hohe Flügelplatten, Streben
        float pod = length(q) - 0.28;
        float win = length(q - vec2(0.0, 0.0)) - 0.14;
        float wingL = sdBox2(q - vec2(-0.78, 0.0), vec2(0.06, 0.75));
        float wingR = sdBox2(q - vec2(0.78, 0.0), vec2(0.06, 0.75));
        float strut = sdBox2(q, vec2(0.75, 0.05));
        float d = min(min(pod, min(wingL, wingR)), strut);
        alpha = smoothstep(0.02, -0.02, d);
        vec3 c0 = hullShade(vec3(0.45, 0.48, 0.55), q, pod);
        c0 = mix(c0, vec3(0.08, 0.08, 0.1) * (0.8 + 0.4 * step(0.5, fract(q.y * 4.0))), step(min(wingL, wingR), 0.0) * step(0.0, pod));
        c0 = mix(c0, vec3(0.2, 0.22, 0.26), step(win, 0.0) * (1.0 - step(0.5, fract(atan(q.y, q.x) * 1.9))) * 0.7);
        c0 += vec3(1.0, 0.3, 0.2) * smoothstep(0.08, 0.0, length(q - vec2(0.0, -0.3))) * (0.6 + 0.4 * sin(t * 20.0));   // Triebwerk
        col = c0;
    } else if (kind == 1) {                            // Satellit: Kasten, Schüssel, zwei Solarflügel
        float body = sdBox2(q, vec2(0.22, 0.3));
        float wingL = sdBox2(q - vec2(-0.85, 0.0), vec2(0.6, 0.18));
        float wingR = sdBox2(q - vec2(0.85, 0.0), vec2(0.6, 0.18));
        float dish = length(q - vec2(0.0, 0.5)) - 0.18;
        float d = min(min(body, dish), min(wingL, wingR));
        alpha = smoothstep(0.02, -0.02, d);
        vec3 c0 = hullShade(vec3(0.85, 0.85, 0.88), q, body);
        float grid = step(0.85, fract(q.x * 5.0)) + step(0.85, fract(q.y * 6.0));
        vec3 panel = mix(vec3(0.1, 0.15, 0.4), vec3(0.3, 0.45, 0.8), 0.5 + 0.5 * sin(q.x * 3.0 + 1.0)) * (1.0 - grid * 0.6);
        c0 = mix(c0, panel, step(min(wingL, wingR), 0.0));
        c0 = mix(c0, vec3(0.9) * (0.6 + 0.4 * smoothstep(0.18, 0.0, abs(length(q - vec2(0.0, 0.5)) - 0.1))), step(dish, 0.0));
        c0 += vec3(1.0, 0.2, 0.2) * step(0.5, fract(t * 1.5)) * smoothstep(0.05, 0.0, length(q - vec2(0.15, -0.3)));
        col = c0;
    } else if (kind == 2) {                            // Kreuzer: langer Keil mit Aufbauten, Triebwerke hinten
        vec2 h = q;
        float hull = sdBox2(h, vec2(1.3, 0.18 + 0.12 * smoothstep(1.3, -1.3, h.x)));
        float sup = sdBox2(h - vec2(-0.3, 0.3), vec2(0.5, 0.12));
        float tower = sdBox2(h - vec2(-0.5, 0.5), vec2(0.12, 0.15));
        float d = min(hull, min(sup, tower));
        alpha = smoothstep(0.02, -0.02, d);
        vec3 c0 = hullShade(vec3(0.5, 0.47, 0.4), h, d);
        c0 *= 0.75 + 0.25 * step(0.5, fract(h.x * 6.0)) * step(0.5, fract(h.y * 9.0));            // Panels
        c0 += vec3(1.0, 0.9, 0.6) * step(0.92, fract(h.x * 12.0 + 0.3)) * step(abs(h.y - 0.05), 0.04) * 0.6;   // Fensterreihe
        c0 += vec3(0.3, 0.6, 1.0) * smoothstep(0.12, 0.0, length((h - vec2(-1.3, 0.0)) * vec2(1.0, 2.0))) * (0.6 + 0.4 * sin(t * 15.0));
        col = c0;
    } else if (kind == 3) {                            // Ringstation: Ring, Nabe, drei geschwungene Pylone
        float rr = length(q);
        float ring = abs(rr - 0.95) - 0.07;
        float hub = rr - 0.3;
        float py = 1.0;
        for (int i = 0; i < 3; i++) {
            float an = float(i) * 2.094 + 0.5;
            vec2 pq = rot2(-an) * q;
            float arc = abs(length(pq - vec2(0.0, -0.9)) - 1.25) - 0.045;
            arc = max(arc, pq.y - 0.9); arc = max(arc, -pq.y + 0.2);
            py = min(py, arc);
        }
        float d = min(min(ring, hub), py);
        alpha = smoothstep(0.02, -0.02, d);
        vec3 c0 = hullShade(vec3(0.42, 0.44, 0.5), q, d);
        c0 += vec3(1.0, 0.85, 0.4) * step(0.9, fract(atan(q.y, q.x) * 6.0 + t * 0.2)) * step(ring, 0.0) * 0.5;   // Lichter auf dem Ring
        c0 += vec3(0.4, 0.8, 1.0) * smoothstep(0.12, 0.0, rr) * (0.5 + 0.5 * sin(t * 3.0));
        col = c0;
    } else if (kind == 4) {                            // Komet: Kern mit Koma und Schweif gegen die Flugrichtung
        float core = length(q) - 0.25;
        float tail = sdSeg(q, vec2(0.0), vec2(2.6, 0.0)) - 0.12 - 0.25 * smoothstep(0.0, 2.6, q.x);
        float coma = smoothstep(0.9, 0.0, length(q)) * 0.5;
        float ta = smoothstep(0.2, -0.2, tail) * smoothstep(2.8, 0.0, q.x) * (0.5 + 0.5 * vn3(vec3(q * 3.0, t * 2.0)));
        alpha = max(smoothstep(0.03, -0.05, core), max(coma, ta * 0.7));
        col = mix(vec3(0.6, 0.8, 1.0), vec3(1.0), smoothstep(0.3, -0.2, core)) * (0.6 + 0.6 * smoothstep(0.3, -0.2, core));
        col = mix(col, vec3(0.8, 0.9, 1.0) * 0.8, ta * step(0.0, core));
    } else {                                           // Stationsmodule: Zylinderkette mit großen goldenen Solarflügeln
        float mods = 1.0;
        for (int i = 0; i < 3; i++) {
            float x = -0.8 + float(i) * 0.8;
            mods = min(mods, sdBox2(q - vec2(x, 0.0), vec2(0.38, 0.17 + 0.05 * float(i == 1))));
        }
        float wingU = sdBox2(q - vec2(0.3, 0.9), vec2(0.22, 0.7));
        float wingD = sdBox2(q - vec2(0.3, -0.9), vec2(0.22, 0.7));
        float d = min(mods, min(wingU, wingD));
        alpha = smoothstep(0.02, -0.02, d);
        vec3 c0 = hullShade(vec3(0.8, 0.8, 0.82), q, mods);
        c0 *= 0.8 + 0.2 * step(0.5, fract(q.x * 10.0));
        vec3 gold = vec3(0.85, 0.65, 0.15) * (0.7 + 0.3 * step(0.5, fract(q.y * 8.0))) * (0.8 + 0.2 * step(0.5, fract(q.x * 12.0)));
        c0 = mix(c0, gold, step(min(wingU, wingD), 0.0) * step(0.0, mods));
        c0 += vec3(1.0, 0.95, 0.8) * step(0.5, fract(t * 1.0)) * smoothstep(0.05, 0.0, length(q - vec2(1.2, 0.0)));
        col = c0;
    }
    return vec4(col, alpha);
}
vec3 pal(float t) { return 0.5 + 0.5 * cos(2.0 * PI * (vec3(1.0, 0.9, 0.7) * t + vec3(0.0, 0.25, 0.5))); }

// Oberfläche eines Planeten nach Typ: n = Rauschen auf der Kugel, lat = Breite -1..1
vec3 surface(int type, vec3 sp, float lat, float t) {
    float n = vfbm3(sp * 3.0);
    float n2 = vfbm3(sp * 9.0 + 7.0);
    vec3 a = gA, b = gB;
    if (type == 0 || type == 8 || type == 2) {              // Wüste, Gras, Wald: Flecken und Bänder
        float band = 0.5 + 0.5 * sin(lat * 8.0 + n * 4.0);
        vec3 c = mix(a, b, smoothstep(0.35, 0.65, n * 0.7 + band * 0.3));
        if (type == 2 || type == 8) c = mix(c, b, step(0.62, n2) * 0.6);   // Seen
        return c;
    }
    if (type == 1 || type == 10) {                           // Eis, Kristall: hell mit Rissen
        float crack = smoothstep(0.48, 0.5, abs(n2 - 0.5)) ;
        return mix(a, b, (1.0 - crack) * 0.35 + step(0.6, n) * 0.4);
    }
    if (type == 3) {                                         // Ozean: Wasser mit Wolken und kleinen Inseln
        vec3 c = mix(b, a, smoothstep(0.3, 0.7, n));
        c = mix(c, vec3(0.85, 0.8, 0.6), step(0.68, n2) * 0.8);
        c = mix(c, vec3(1.0), smoothstep(0.55, 0.75, vfbm3(sp * 4.0 + vec3(t * 0.05, 0.0, 0.0))) * 0.7);
        return c;
    }
    if (type == 4) {                                         // Stadt: graue Fläche, Lichtraster
        vec3 c = mix(a, b, n);
        float grid = step(0.9, fract(sp.x * 40.0 + n * 3.0)) + step(0.9, fract(sp.y * 40.0));
        return c + vec3(1.0, 0.85, 0.5) * grid * 0.35;
    }
    if (type == 5) {                                         // Vulkan: dunkel mit Lavaadern
        float vein = smoothstep(0.5, 0.52, abs(n2 - 0.5) * 2.0);
        vein = 1.0 - vein;
        return mix(a, b, vein * (0.7 + 0.3 * sin(t * 3.0 + n * 10.0)) + step(0.7, n) * 0.3);
    }
    if (type == 6) {                                         // Gasriese: Bänder mit Wirbeln
        float band = sin(lat * 14.0 + n * 3.0 + t * 0.1);
        return mix(a, b, 0.5 + 0.5 * band);
    }
    if (type == 7) {                                         // Sumpf: trüb, Nebelflecken
        vec3 c = mix(a, b, n);
        return mix(c, vec3(0.6, 0.65, 0.55), smoothstep(0.6, 0.8, n2) * 0.4);
    }
    if (type == 11) {                                        // Stern: kochende Granulation, dunkle Flecken, pulst mit dem Bass
        float gran = vfbm3(sp * 7.0 + vec3(0.0, 0.0, t * 0.25));
        float spots = smoothstep(0.62, 0.7, vfbm3(sp * 2.5 + 3.0));
        vec3 c = mix(a, b, smoothstep(0.3, 0.7, gran));
        c = mix(c, a * 0.25, spots * 0.8);
        return c * (1.3 + 0.6 * uBass * (1.0 - uSilent));
    }
    if (type == 12) {                                        // Komet: dunkler Kern mit hellen Flecken (Eis)
        return mix(a, b, smoothstep(0.4, 0.75, n2)) * (0.6 + 0.5 * step(0.72, n2));
    }
    if (type == 13) {                                        // Kampfstation: Panelraster, Äquatorgraben, Schüssel
        vec3 c = mix(a, b, 0.5 + 0.5 * step(0.5, fract(sp.x * 24.0 + floor(sp.y * 12.0) * 0.5)) * step(0.5, fract(sp.y * 12.0)));
        c *= 0.85 + 0.15 * step(0.93, fract(sp.x * 48.0)) + 0.15 * step(0.93, fract(sp.y * 24.0));
        c *= 1.0 - 0.75 * smoothstep(0.03, 0.015, abs(lat - 0.02));                            // Graben
        float dish = length(sp - normalize(vec3(-0.35, 0.45, 0.82)));
        c = mix(c, b * 0.6, smoothstep(0.34, 0.3, dish));                                       // Schüssel
        c = mix(c, a * 1.4, smoothstep(0.32, 0.3, dish) * smoothstep(0.26, 0.3, dish));          // Rand
        c += vec3(0.4, 1.0, 0.5) * smoothstep(0.04, 0.0, dish) * (0.5 + 0.5 * sin(t * 3.0));   // Fokus
        return c;
    }
    return mix(a, b, smoothstep(0.3, 0.7, n) + step(0.7, n2) * 0.2);      // Fels: Krater
}

// Planet an Position c (Bildkoordinaten, Mitte 0), Radius R; gibt Farbe und Deckung zurück
vec4 planet(vec2 p, vec2 c, float R, int type, float rot, float t) {
    vec2 d = (p - c) / R;
    float r = length(d);
    vec4 res = vec4(0.0);
    if (r < 1.0) {
        float z = sqrt(1.0 - r * r);
        vec3 nrm = vec3(d, z);
        // Kugel drehen (Längengrad), Textur aus 3D-Rauschen
        float cs = cos(rot), sn = sin(rot);
        vec3 sp = vec3(nrm.x * cs - nrm.z * sn, nrm.y, nrm.x * sn + nrm.z * cs);
        vec3 col = surface(type, sp, nrm.y, t);
        vec3 L = normalize(vec3(-0.6, 0.4, 0.7));
        float diff = clamp(dot(nrm, L), 0.0, 1.0);
        float light = 0.12 + 0.95 * pow(diff, 0.8);
        if (type == 11) light = 1.0;                                                            // Stern leuchtet selbst
        col *= light;
        if (type == 4) col += vec3(1.0, 0.8, 0.45) * (1.0 - smoothstep(0.0, 0.25, diff)) * step(0.85, fract(sp.x * 40.0)) * 0.6;  // Stadtlichter nachts
        if (type == 5) col += gB * (1.0 - smoothstep(0.0, 0.3, diff)) * smoothstep(0.5, 0.52, 1.0 - abs(vfbm3(sp * 9.0 + 7.0) - 0.5) * 2.0) * 0.6;
        // Terminator weich, Rim-Licht der Atmosphäre
        col += mix(gB, vec3(0.6, 0.8, 1.0), 0.5) * pow(1.0 - z, 3.0) * 0.6 * light;
        res = vec4(col, 1.0);
    }
    // Atmosphärenglühen außen
    float glow = smoothstep(1.35, 1.0, r) * (1.0 - step(r, 1.0));
    res.rgb += mix(gA, vec3(0.5, 0.7, 1.0), 0.5) * glow * 0.35;
    res.a = max(res.a, glow * 0.6);
    if (type == 11) {                                        // Korona und Protuberanzen
        float an = atan(d.y, d.x);
        float flare = vfbm3(vec3(an * 2.0, r * 3.0 - t * 0.3, 1.0));
        float corona = smoothstep(2.4, 1.0, r) * (1.0 - step(r, 1.0)) * (0.35 + 0.65 * flare) * (1.0 + 0.8 * uBass * (1.0 - uSilent));
        res.rgb += gA * corona * 0.8;
        res.a = max(res.a, corona);
    }
    if (type == 12) {                                        // Koma und Schweif, weg von der Sonne (links oben)
        vec2 dirT = normalize(vec2(0.65, -0.35));
        float along = dot(d, dirT), across = abs(dot(d, vec2(-dirT.y, dirT.x)));
        float tail = smoothstep(0.0, 1.5, along) * smoothstep(0.6 + along * 0.35, 0.0, across) * smoothstep(9.0, 1.0, along);
        tail *= 0.5 + 0.5 * vfbm3(vec3(along * 1.5 - t * 1.5, across * 3.0, 2.0));
        vec3 tcol = mix(vec3(0.6, 0.8, 1.0), vec3(1.0, 0.95, 0.8), smoothstep(0.0, 0.5, across));
        float coma = smoothstep(2.2, 0.9, r) * (1.0 - step(r, 1.0));
        res.rgb += tcol * tail * 0.7 + vec3(0.8, 0.9, 1.0) * coma * 0.4;
        res.a = max(res.a, max(tail * 0.8, coma * 0.6));
    }
    return res;
}

// ---- Ereignisse unterwegs ---------------------------------------------------------------------
// Asteroidenfeld: Brocken strömen aus der Tiefe radial nach außen (vorn groß), unregelmäßig, vom Tunnel beleuchtet
vec3 asteroidField(vec3 col, vec2 uv, float k, float t) {
    float env = smoothstep(0.0, 0.15, k) * smoothstep(1.0, 0.85, k);
    for (int i = 0; i < 26; i++) {
        float fi = float(i);
        float h1 = hash(vec2(fi, uEventSeed * 50.0)), h2 = hash(vec2(fi * 2.0 + 1.0, uEventSeed * 50.0)), h3 = hash(vec2(fi * 3.0 + 2.0, uEventSeed * 50.0));
        float ang = h1 * 6.2832;
        float ph = fract(t * (0.06 + 0.12 * h2) + h3);           // 0 fern .. 1 nah
        float rad = 0.03 + ph * ph * 2.2;
        vec2 c = vec2(cos(ang), sin(ang)) * rad;
        float size = (0.01 + 0.05 * h2) * (0.2 + ph * ph * 2.5);
        vec2 d = uv - c;
        if (abs(d.x) > size * 1.4 || abs(d.y) > size * 1.4) continue;
        float aa = atan(d.y, d.x);
        float rr = size * (0.85 + 0.2 * sin(aa * 3.0 + h1 * 9.0 + t * (h3 - 0.5) * 2.0) + 0.1 * sin(aa * 7.0 + h2 * 5.0));
        float v = length(d) / rr;
        if (v > 1.3) continue;
        float nz = sqrt(max(0.0, 1.0 - v * v));
        vec3 N = normalize(vec3(d / rr, nz));
        vec3 L = normalize(vec3(-c, 0.7));                          // Licht aus dem Tunnelzentrum
        float light = 0.15 + 0.85 * max(dot(N, L), 0.0);
        vec3 rock = mix(vec3(0.22, 0.2, 0.18), vec3(0.45, 0.4, 0.35), hash(vec2(fi, 7.0))) * light;
        rock += pal(h1) * 0.15 * nz;                                 // Tunnelfarben schimmern auf dem Gestein
        float a = smoothstep(1.0, 0.85, v) * env * smoothstep(0.0, 0.1, ph);
        col = mix(col, rock, a);
    }
    return col;
}
// Einschlag auf den Schild: Blitz am Einschlagpunkt, Wabenschimmer, Rand färbt sich
vec3 impactFx(vec3 col, vec2 uv) {
    float age = uImpact.z;
    if (age > 0.9 || age < 0.0) return col;
    float e = exp(-age * 4.0);
    vec2 d = uv - uImpact.xy;
    col += vec3(1.0, 0.9, 0.7) * exp(-length(d) * 6.0) * e * 1.5;
    vec2 hp = uv * 12.0;
    float hex = smoothstep(0.06, 0.0, abs(length(fract(hp) - 0.5) - 0.42));
    col += vec3(0.4, 0.8, 1.0) * hex * exp(-length(d) * 5.0) * e * 1.2;
    col += vec3(0.3, 0.6, 1.0) * smoothstep(1.2, 1.9, length(uv)) * e * 0.4;
    return col;
}
// Farbnebel: dichte, langsam treibende Schwaden in wandernden Farben, dazwischen gezackte Blitze
vec3 nebulaFx(vec3 col, vec2 uv, float k, float t) {
    float env = smoothstep(0.0, 0.2, k) * smoothstep(1.0, 0.8, k);
    float n = fbm(uv * 1.5 + vec2(t * 0.15, -t * 0.1) + uEventSeed * 9.0);
    float n2 = fbm(uv * 3.0 - vec2(t * 0.2, t * 0.05) + n);
    vec3 neb = pal(n * 0.8 + t * 0.05 + uEventSeed) * (0.5 + 0.5 * n2);
    float dens = smoothstep(0.25, 0.8, n * 0.7 + n2 * 0.5) * (0.6 + 0.4 * uRms);
    col = mix(col, col * 0.4 + neb * 0.9, dens * env * 0.85);
    float age = uFlash.y;
    if (age >= 0.0 && age < 0.5) {
        float e = exp(-age * 7.0);
        vec2 p0 = vec2(cos(uFlash.x), sin(uFlash.x)) * 2.0;
        float dmin = 10.0;
        vec2 prev = p0;
        for (int s = 1; s <= 6; s++) {
            float fs = float(s) / 6.0;
            vec2 pn = p0 * (1.0 - fs) + vec2(hash(vec2(fs, uFlash.x)) - 0.5, hash(vec2(fs, uFlash.x + 3.0)) - 0.5) * 0.4 * (1.0 - fs);
            dmin = min(dmin, sdSeg(uv, prev, pn));
            prev = pn;
        }
        col += vec3(0.8, 0.85, 1.0) * (smoothstep(0.012, 0.0, dmin) + 0.3 * exp(-dmin * 8.0)) * e * 2.0 * env;
        col += vec3(0.6, 0.7, 1.0) * e * 0.15 * env;
    }
    return col;
}
// Sonne: zieht groß am Bildrand vorbei, Granulation, Korona, Protuberanzen, Lens-Flare, Hitze im Bild
vec3 sunFx(vec3 col, vec2 uv, float k, float t) {
    float env = smoothstep(0.0, 0.1, k) * smoothstep(1.0, 0.9, k);
    float side = uEventSeed > 0.5 ? 1.0 : -1.0;
    vec2 c = vec2(side * (2.7 - 1.9 * sin(k * PI)), 0.2 - 0.4 * k);
    float R = 0.8;
    vec2 d = uv - c;
    float rr = length(d) / R;
    if (rr > 4.0) { return col + vec3(1.0, 0.6, 0.3) * exp(-length(d) * 1.2) * 0.25 * env; }
    float ang = atan(d.y, d.x);
    float gran = fbm(d * 6.0 + t * 0.3);
    vec3 disc = mix(vec3(1.0, 0.45, 0.05), vec3(1.0, 0.95, 0.7), gran) * (1.25 - 0.3 * rr);
    float prot = fbm(vec2(ang * 3.0 + uEventSeed * 9.0, t * 0.4));
    float corona = exp(-(rr - 1.0) * (3.0 + 4.0 * prot)) * step(1.0, rr);
    col = mix(col, disc, smoothstep(1.02, 0.98, rr) * env);
    col += vec3(1.0, 0.5, 0.1) * corona * env * (0.8 + 0.5 * uBass);
    float arc = smoothstep(0.06, 0.0, abs(rr - (1.15 + 0.25 * prot))) * smoothstep(0.3, 0.7, fbm(vec2(ang * 5.0, t * 0.5 + uEventSeed)));
    col += vec3(1.0, 0.35, 0.05) * arc * env * 1.2;
    for (int i = 1; i <= 4; i++) {
        float fi = float(i) * 0.35;
        vec2 gpos = c * (1.0 - fi * 1.4);
        float gs = 0.05 + 0.08 * fi;
        col += pal(fi + 0.2) * smoothstep(gs, gs * 0.6, length(uv - gpos)) * 0.25 * env;
    }
    col += vec3(1.0, 0.6, 0.3) * exp(-length(d) * 1.2) * 0.25 * env;
    return col;
}
// Wurmloch: rasende Ringe mit Spiralverdrehung, Farben kippen, am Ende Durchbruch mit Weißblitz
vec3 wormholeFx(vec3 col, vec2 uv, float k, float t, float r, float a) {
    float env = smoothstep(0.0, 0.25, k) * smoothstep(1.0, 0.75, k);
    float depth = 1.0 / (r + 0.12);
    float rings = 0.5 + 0.5 * sin(depth * 6.0 - t * 9.0 + a * 3.0 * env);
    rings = pow(rings, 4.0);
    vec3 rc = pal(depth * 0.15 - t * 0.5 + uEventSeed);
    col = mix(col, col * 0.5 + rc * rings * 1.3, env * (0.6 + 0.4 * uBass));
    col += vec3(0.7, 0.8, 1.0) * exp(-r * 4.0) * env * (0.5 + 0.5 * sin(t * 6.0));
    col += vec3(1.0) * exp(-abs(k - 0.85) * 25.0) * 1.2;
    return col;
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;
    float live = 1.0 - uSilent;
    // Einschlag: das ganze Bild ruckt kurz
    if (uImpact.z >= 0.0 && uImpact.z < 0.6) {
        float e = exp(-uImpact.z * 5.0);
        uv += vec2(hash(vec2(floor(iTime * 40.0), 1.0)) - 0.5, hash(vec2(floor(iTime * 40.0), 2.0)) - 0.5) * 0.06 * e;
    }
    int type = int(uPlanetType + 0.5);
    int phase = int(uPhase + 0.5);
    float pt = uPhaseT;
    vec3 col = vec3(0.0);

    // ---- Phasenwerte: stretch (Streifenlänge), warp (Tunnelanteil), planetScale, planetAlpha
    float stretch = 0.0, warp = 0.0, pscale = 1.0, palpha = 1.0, speed = 0.03;
    if (phase == 1) {                 // launch: Planet weicht zurück, Sterne ziehen sich lang
        float k = clamp(pt / uLaunchS, 0.0, 1.0);
        stretch = pow(k, 2.0) * 1.0;
        pscale = 1.0 - 0.9 * smoothstep(0.0, 0.7, k);
        palpha = 1.0 - smoothstep(0.5, 0.9, k);
        speed = 0.03 + 0.6 * k * k;
        warp = smoothstep(0.7, 1.0, k) * 0.6;
    } else if (phase == 2) {          // cruise: langsamer, träumerischer Schweif
        stretch = 1.0;
        warp = 1.0;
        pscale = 0.0; palpha = 0.0;
        speed = 0.35;
    } else if (phase == 3) {          // arrive: Tunnel bricht zusammen, Ziel wächst
        float k = clamp(pt / uArriveS, 0.0, 1.0);
        stretch = 1.0 - smoothstep(0.0, 0.5, k);
        warp = 1.0 - smoothstep(0.0, 0.45, k);
        pscale = smoothstep(0.3, 1.0, k);
        palpha = smoothstep(0.3, 0.7, k);
        speed = 0.6 * (1.0 - k) + 0.03;
    }

    // ---- Sterne (radial, 3 Lagen). Im Browse-Modus sanfter Drift, sonst Streifen nach außen.
    vec2 su = uv;
    float roll = iTime * 0.01 + uMid * 0.2 * live * warp;
    su = mat2(cos(roll), -sin(roll), sin(roll), cos(roll)) * su;
    float r = length(su), a = atan(su.y, su.x);
    for (int layer = 0; layer < 3; layer++) {
        float fl = float(layer);
        float cells = 120.0 + fl * 70.0;
        float ca = floor(a / (2.0 * PI) * cells + fl * 3.0);
        float h = hash(vec2(ca, fl));
        float ang = (ca + 0.5 + (h - 0.5) * 0.7) / cells * 2.0 * PI;
        float ph = fract(iTime * speed * (0.5 + 0.9 * h) + hash(vec2(ca, fl + 10.0)));
        float sr = 0.05 + ph * ph * 1.9;
        float len = 0.003 + stretch * (0.1 + 0.5 * ph) * (0.6 + 0.4 * h);
        float dAng = abs(atan(sin(a - ang), cos(a - ang))) * r;
        float dRad = r - sr;
        float along = step(dRad, 0.0) * smoothstep(len, len * 0.2, -dRad) + smoothstep(0.006, 0.0, abs(dRad));
        float dot_ = smoothstep(0.0035 + 0.002 * fl, 0.0, dAng) * along;
        float bright = (0.4 + 0.6 * h) * (0.35 + 0.65 * ph) * step(0.3, hash(vec2(ca, fl + 20.0)));
        bright *= 0.8 + 0.4 * uHigh * live + 0.3 * sin(iTime * 3.0 + h * 20.0) * (1.0 - stretch);
        vec3 sc = mix(vec3(1.0), pal(ph + h + iTime * 0.1), stretch * 0.8);
        col += sc * dot_ * bright;
    }

    // ---- Psychedelischer Schweif im Hyperraum: Tunnel aus Rauschen, Farben wandern langsam, Bass pulst
    if (warp > 0.0) {
        float depth = 1.0 / (r * (1.0 + 0.6 * uBass * live) + 0.15);
        float tw = iTime * 0.25;
        vec2 tc = vec2(sin(a) * 1.6 + cos(a * 2.0) * 0.9 + sin(depth * 0.5 + tw) * 0.5, depth * 0.8 - tw * 2.0);   // periodisch in a: keine Naht
        float n = fbm(tc);
        float n2 = fbm(tc * 2.3 + vec2(tw * 0.7, 0.0) + n * 2.0);
        float v = n * 0.6 + n2 * 0.5 + 0.15 * sin(depth * 4.0 - iTime * 1.2);
        vec3 tunnel = pal(v * 1.2 + tw * 0.3 + uBass * 0.3) * (0.35 + 0.65 * smoothstep(0.1, 0.5, r));
        tunnel *= pow(clamp(v, 0.0, 1.0), 1.6) * 0.9;                 // dunkler, kontrastreicher
        tunnel *= 1.0 - 0.6 * smoothstep(0.9, 1.9, r);                 // Rand dunkel
        tunnel += vec3(0.4, 0.6, 1.0) * exp(-r * 5.0) * (0.3 + 0.7 * uBass);
        col = mix(col, col * 0.8 + tunnel * (0.45 + 0.45 * uRms + 0.1 * live), warp);
        col += vec3(1.0) * uBeat * 0.1 * warp * live;
    }

    // ---- Ereignisse unterwegs (nur im Hyperraum)
    int ev = int(uEvent + 0.5);
    float ek = uEventLen > 0.0 ? clamp(uEventT / uEventLen, 0.0, 1.0) : 0.0;
    if (phase == 2 && ev > 0) {
        if (ev == 3) col = sunFx(col, uv, ek, iTime);
        if (ev == 4) col = wormholeFx(col, uv, ek, iTime, r, a);
        if (ev == 2) col = nebulaFx(col, uv, ek, iTime);
        if (ev == 1) col = asteroidField(col, uv, ek, iTime);
    }
    if (phase == 2) col = impactFx(col, uv);
    // Warnung: der Bildrand pulst rot, bevor ein Ereignis beginnt
    col += vec3(1.0, 0.1, 0.05) * smoothstep(1.0, 1.9, length(uv)) * uEventWarn * (0.5 + 0.5 * sin(iTime * 12.0)) * 0.5;

    // ---- Planet (browse: mittig, beim Wechsel seitlich hereingleitend)
    // ---- Vorbeiflug: ein anderes Objekt zieht im Hyperraum seitlich vorbei (wächst, driftet, verschwindet)
    if (uFly > 0.001 && phase == 2) {
        gA = uFlyColA; gB = uFlyColB;
        float k = uFly;
        float grow = k * k;
        float Rf = (0.03 + 1.1 * grow) * uFlySize;
        vec2 cf = vec2(uFlySide * (0.15 + 2.2 * grow), -0.05 + 0.5 * grow * uFlySide * 0.3);
        float fa = smoothstep(0.0, 0.15, k) * smoothstep(1.0, 0.85, k);
        int ft = int(uFlyType + 0.5);
        if (uFlyRings > 0.5) {
            vec2 q = (uv - cf) / Rf;
            float rr = length(vec2(q.x, q.y * 3.2));
            float ring = smoothstep(1.3, 1.35, rr) * smoothstep(2.2, 2.1, rr);
            col = mix(col, gA * 0.7, ring * fa * 0.9);
        }
        vec4 fp = planet(uv, cf, Rf, ft, iTime * 0.3, iTime);
        col = mix(col, fp.rgb, fp.a * fa);
        // Bewegungsunschärfe-Schein in Flugrichtung
        col += gA * 0.15 * fa * smoothstep(Rf * 2.5, Rf * 0.8, length((uv - cf) * vec2(0.5, 1.0)));
    }
    // ---- Verkehr: kleine Schiffe und Kometen zwischen den Planeten
    if (phase == 2) {
        for (int i = 0; i < 3; i++) {
            vec4 sh = i == 0 ? uShip0 : (i == 1 ? uShip1 : uShip2);
            vec4 sp = i == 0 ? uShipP0 : (i == 1 ? uShipP1 : uShipP2);
            if (sp.x <= 0.001 || sh.z <= 0.0) continue;
            int kind = int(sh.w + 0.5);
            float ang = kind == 4 ? atan(sh.y, sh.x) + 3.14159 : sp.y * (kind == 3 ? 1.0 : 0.3);   // sp.y kommt bereits auf 0..2pi reduziert
            if (sp.w < 0.0 && kind != 4) ang += 0.0;
            vec4 sc = ship(uv, sh.xy, sh.z, kind, ang, iTime + float(i) * 7.0, sp.w);
            // Bewegungsschein in Flugrichtung
            col += vec3(0.6, 0.7, 1.0) * sc.a * 0.15 * smoothstep(1.0, 0.0, sp.z) * sp.x;
            col = mix(col, sc.rgb, sc.a * sp.x);
        }
        // Explosion: Blitz, Ring, Trümmer
        if (uBoom.z < 1.4) {
            float age = uBoom.z;
            vec2 bq = uv - uBoom.xy;
            float br = length(bq);
            float sz = uBoom.w * 1.2 + 0.05;
            float flash = exp(-age * 9.0) * smoothstep(sz * 3.0, 0.0, br);
            float ring = smoothstep(0.03, 0.0, abs(br - age * sz * 4.0)) * exp(-age * 2.5);
            float debris = 0.0;
            for (int k = 0; k < 10; k++) {
                float fk = float(k);
                float an = fk * 0.628 + hash(vec2(fk, 2.0)) * 0.5;
                vec2 dp = uBoom.xy + vec2(cos(an), sin(an)) * (age * (0.4 + 0.5 * hash(vec2(fk, 3.0))) * sz * 6.0);
                debris += smoothstep(0.012, 0.0, length(uv - dp)) * exp(-age * 2.0) * step(0.03, age);
            }
            col += vec3(1.0, 0.95, 0.8) * flash * 2.0 + vec3(1.0, 0.5, 0.15) * ring + vec3(1.0, 0.6, 0.3) * debris;
            col += vec3(1.0, 0.7, 0.4) * smoothstep(sz * 2.0, 0.0, br) * exp(-age * 4.0) * 0.6 * (0.5 + 0.5 * fbm(bq * 12.0 + age * 3.0));
        }
        // Laser: zwei Strahlen von den unteren Ecken zum Ziel
        if (uLaser > 0.0) {
            float aspect = iResolution.x / iResolution.y;
            float l1 = sdSeg(uv, vec2(-aspect * 0.9, -1.0), uLaserTo);
            float l2 = sdSeg(uv, vec2(aspect * 0.9, -1.0), uLaserTo);
            float beam = smoothstep(0.012, 0.0, min(l1, l2)) + 0.4 * smoothstep(0.035, 0.0, min(l1, l2));
            col += vec3(0.3, 1.0, 0.4) * beam * uLaser;
            col += vec3(0.6, 1.0, 0.7) * smoothstep(0.05, 0.0, length(uv - uLaserTo)) * uLaser;
        }
        // Fadenkreuz
        if (uShoot > 0.5) {
            vec2 cq = uv - uCross;
            float cr = length(cq);
            float reticle = smoothstep(0.004, 0.0, abs(cr - 0.07)) * step(0.5, fract(atan(cq.y, cq.x) * 1.27 + 0.25));
            reticle += smoothstep(0.003, 0.0, abs(cq.x)) * step(abs(cq.y), 0.1) * step(0.025, abs(cq.y));
            reticle += smoothstep(0.003, 0.0, abs(cq.y)) * step(abs(cq.x), 0.1) * step(0.025, abs(cq.x));
            col += vec3(1.0, 0.5, 0.2) * reticle * (0.6 + 0.4 * sin(iTime * 6.0));
        }
    }
    gA = uColA; gB = uColB;
    if (palpha > 0.0) {
        float R = 0.40 * uPlanetSize * pscale;
        // Browse: Planet rechts, Text links; beim Anflug/Ankunft in die Mitte
        float side = 0.62 * (1.0 - float(phase == 2)) * (float(phase == 0) + (1.0 - pscale) * float(phase == 1) * 0.0 + float(phase == 1) * pscale + float(phase == 3) * (1.0 - pscale) * 0.0);
        if (phase == 3) side = 0.62 * pscale;
        vec2 c = vec2(side + uSlide * 1.8 * abs(uSlide), -0.02);
        float rot = iTime * 0.08 + uSlide * 0.5;
        // Ringe hinter dem Planeten
        if (uRings > 0.5 && R > 0.01) {
            vec2 q = (uv - c) / R;
            float rr = length(vec2(q.x, q.y * 3.2));
            float ring = smoothstep(1.3, 1.35, rr) * smoothstep(2.2, 2.1, rr) * step(0.0, -q.y + 0.0);
            col = mix(col, uColA * 0.7 * (0.6 + 0.4 * noise(vec2(rr * 20.0, 0.0))), ring * palpha);
        }
        vec4 pl = planet(uv, c, R, type, rot, iTime);
        col = mix(col, pl.rgb, pl.a * palpha);
        if (uRings > 0.5 && R > 0.01) {
            vec2 q = (uv - c) / R;
            float rr = length(vec2(q.x, q.y * 3.2));
            float ring = smoothstep(1.3, 1.35, rr) * smoothstep(2.2, 2.1, rr) * step(0.0, q.y);
            col = mix(col, uColA * 0.75 * (0.6 + 0.4 * noise(vec2(rr * 20.0, 0.0))), ring * palpha);
        }
        // Monde
        for (int m = 0; m < 3; m++) {
            if (float(m) < uMoons - 0.5) {
                float fm = float(m);
                float orb = iTime * (0.15 + 0.1 * fm) + fm * 2.1;
                vec2 mc = c + vec2(cos(orb) * (1.5 + 0.4 * fm), sin(orb) * 0.35) * R;
                if (sin(orb) < 0.0 || length(uv - c) > R) {
                    vec2 md = (uv - mc) / (R * (0.09 + 0.03 * fm));
                    float mr = length(md);
                    if (mr < 1.0) {
                        float mz = sqrt(1.0 - mr * mr);
                        float ml = 0.15 + 0.85 * clamp(dot(vec3(md, mz), normalize(vec3(-0.6, 0.4, 0.7))), 0.0, 1.0);
                        col = mix(col, vec3(0.7, 0.68, 0.62) * ml * (0.7 + 0.3 * hash(vec2(fm, 1.0))), palpha);
                    }
                }
            }
        }
        // Puls mit der Musik: leichter Lichtkranz
        col += mix(uColA, vec3(1.0), 0.5) * smoothstep(0.15, 0.0, abs(length(uv - c) - R * 1.05)) * uRms * live * 0.25 * palpha;
    }
    col *= 1.0 - 0.35 * smoothstep(1.0, 1.9, length(uv));
    if (uSponsorOK > 0.5) {
        // Logo klein unten rechts, Seitenverhältnis 3:1, mit leichter Transparenz
        vec2 lq = (vUv - vec2(0.86, 0.035)) / vec2(0.115, 0.04) + 0.5;
        if (lq.x > 0.0 && lq.x < 1.0 && lq.y > 0.0 && lq.y < 1.0) {
            vec4 lg = texture(uSponsorTex, lq);
            float lum = dot(lg.rgb, vec3(0.33));
            float a = lg.a * (1.0 - smoothstep(0.85, 0.98, lum));     // weißer Hintergrund wird durchsichtig
            col = mix(col, vec3(0.75, 0.8, 0.9), a * 0.85);
        }
    }
    fragColor = vec4(col, 1.0);
}
