#version 140
// F7 – Lagerfeuer auf einem fremden Planeten: Pixel-Art-Feuer, zwei Monde, Ringplanet, Nebel, Sternschnuppen.
// Zündet in den ersten Sekunden an (iTime startet beim Modusstart bei 0). Reagiert leicht auf Audio.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uEventForce;   // Test: >0 erzwingt Ereignis (Wert-1), 0 = zufällig

const float CELLS_Y = 128.0;     // Pixelraster: 128 Zeilen, Breite nach Seitenverhältnis
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
// Ganzzahl-Hash ohne sin(): auf jeder GPU gleich (die sin-Variante driftet bei großen Argumenten je nach Treiber)
float hash1(float n) { n = fract(n * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 11.0; a *= 0.5; }
    return v;
}
// Feuerfarben, auf 6 Stufen quantisiert (Pixel-Look)
vec3 firePal(int k) {           // k = 1..5, Stufen von dunkelrot bis weißgelb
    if (k <= 1) return vec3(0.45, 0.05, 0.35);     // violetter Saum
    if (k == 2) return vec3(0.85, 0.15, 0.25);
    if (k == 3) return vec3(1.0, 0.45, 0.08);
    if (k == 4) return vec3(1.0, 0.80, 0.25);
    return vec3(0.85, 0.95, 1.0);                  // weißblauer Kern
}
// Abstand Punkt–Strecke (für die Scheite)
float segDist(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}


// ---- Hintergrund-Ereignisse (alle 16 s ein Fenster, Typ per Hash; manche Fenster bleiben leer)
float boxf(vec2 p, vec2 c, vec2 h) { vec2 d = abs(p - c) - h; return step(max(d.x, d.y), 0.0); }
float tri(vec2 p, vec2 a, vec2 b, vec2 c) {   // Punkt im Dreieck
    float s1 = sign((b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x));
    float s2 = sign((c.x - b.x) * (p.y - b.y) - (c.y - b.y) * (p.x - b.x));
    float s3 = sign((a.x - c.x) * (p.y - c.y) - (a.y - c.y) * (p.x - c.x));
    return step(2.5, abs(s1 + s2 + s3));
}
// Transporter: breiter Rumpf, Flügel, blinkende Lichter, Triebwerksglühen. q relativ zur Mitte, Größe s
vec3 transporter(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float body = boxf(q, vec2(0.0, 0.0), vec2(0.5, 0.09)) + boxf(q, vec2(0.15, 0.12), vec2(0.18, 0.06));
    float wing = tri(q, vec2(-0.2, 0.0), vec2(0.35, 0.0), vec2(0.0, -0.32)) + tri(q, vec2(-0.2, 0.0), vec2(0.35, 0.0), vec2(0.0, 0.3));
    float hull = clamp(body + wing, 0.0, 1.0);
    vec3 c = mix(col, vec3(0.22, 0.24, 0.28), hull);
    c = mix(c, vec3(0.35, 0.38, 0.42), hull * step(0.5, fract(q.y * 12.0)));             // Panels
    c += vec3(1.0, 0.3, 0.1) * step(0.5, fract(t * 2.0)) * boxf(q, vec2(0.48, 0.0), vec2(0.03, 0.03));
    c += vec3(0.3, 0.6, 1.0) * boxf(q, vec2(-0.52, 0.0), vec2(0.06, 0.05)) * (0.7 + 0.3 * sin(t * 30.0));
    return c;
}
// Jäger: kleiner Keil mit zwei Streben, roter Schweif
vec3 fighter(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float hull = tri(q, vec2(0.5, 0.0), vec2(-0.3, 0.18), vec2(-0.3, -0.18)) + boxf(q, vec2(-0.35, 0.0), vec2(0.08, 0.3));
    vec3 c = mix(col, vec3(0.75, 0.75, 0.8), clamp(hull, 0.0, 1.0));
    float trail = boxf(q, vec2(-0.9, 0.0), vec2(0.55, 0.05)) * smoothstep(-1.45, -0.4, q.x);
    c += vec3(1.0, 0.25, 0.15) * trail * 0.9;
    return c;
}
// Läufer: Kastenkopf, Rumpf, vier Beine (zwei Phasen), weit hinten am Horizont
vec3 walker(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float legA = 0.5 + 0.5 * sin(t * 2.5), legB = 0.5 - 0.5 * sin(t * 2.5);
    float body = boxf(q, vec2(0.0, 0.55), vec2(0.45, 0.18)) + boxf(q, vec2(0.55, 0.5), vec2(0.18, 0.12)) + boxf(q, vec2(0.68, 0.42), vec2(0.06, 0.04));
    float legs = boxf(q, vec2(-0.3 + legA * 0.1, 0.18), vec2(0.06, 0.2)) + boxf(q, vec2(0.3 + legB * 0.1, 0.18), vec2(0.06, 0.2))
               + boxf(q, vec2(-0.3 - legA * 0.15, -0.1), vec2(0.07, 0.1)) + boxf(q, vec2(0.3 - legB * 0.15, -0.1), vec2(0.07, 0.1))
               + boxf(q, vec2(-0.1 + legB * 0.1, 0.18), vec2(0.05, 0.2)) + boxf(q, vec2(0.12 + legA * 0.1, -0.1), vec2(0.06, 0.1));
    vec3 c = mix(col, vec3(0.24, 0.25, 0.28), clamp(body + legs, 0.0, 1.0));
    c += vec3(1.0, 0.2, 0.1) * step(0.7, fract(t * 1.5)) * boxf(q, vec2(0.6, 0.5), vec2(0.03, 0.02));
    return c;
}
// Gleiter am Boden: flach, schnell, Staubfahne
vec3 speeder(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float hull = boxf(q, vec2(0.0, 0.05), vec2(0.5, 0.07)) + boxf(q, vec2(0.1, 0.17), vec2(0.15, 0.06)) + boxf(q, vec2(-0.45, 0.1), vec2(0.08, 0.1));
    vec3 c = mix(col, vec3(0.5, 0.42, 0.3), clamp(hull, 0.0, 1.0));
    float dust = step(0.6, hash(vec2(floor(q.x * 8.0), floor(t * 12.0)))) * boxf(q, vec2(-1.0, -0.05), vec2(0.6, 0.12));
    c = mix(c, vec3(0.35, 0.3, 0.32), dust * 0.7);
    c += vec3(0.4, 0.7, 1.0) * boxf(q, vec2(-0.52, 0.05), vec2(0.04, 0.04));
    return c;
}
// Sonde: schwebende Kugel mit Armen, roter Scanstrahl nach unten
vec3 probe(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float head = step(length(q - vec2(0.0, 0.3)), 0.22);
    float arms = boxf(q, vec2(0.0, 0.0), vec2(0.04, 0.3)) + boxf(q, vec2(-0.25, 0.05), vec2(0.03, 0.2)) + boxf(q, vec2(0.25, 0.05), vec2(0.03, 0.2));
    vec3 c = mix(col, vec3(0.2, 0.2, 0.22), clamp(head + arms, 0.0, 1.0));
    float beam = step(abs(q.x - sin(t * 3.0) * 0.4 * (-q.y + 0.3)), 0.04 + 0.05 * (0.3 - q.y)) * step(q.y, 0.1) * step(-2.5, q.y) * step(0.5, fract(t * 1.3));
    c += vec3(1.0, 0.15, 0.1) * beam * 0.6;
    c += vec3(1.0, 0.2, 0.1) * step(length(q - vec2(0.0, 0.3)), 0.06) * (0.5 + 0.5 * sin(t * 20.0));
    return c;
}
// Großschiff: schmaler Keil hoch am Himmel, Positionslichter, sehr langsam
vec3 capital(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float hull = tri(q, vec2(0.7, 0.0), vec2(-0.7, 0.22), vec2(-0.7, -0.22)) + boxf(q, vec2(-0.3, 0.3), vec2(0.15, 0.1)) + boxf(q, vec2(-0.3, 0.42), vec2(0.03, 0.08));
    vec3 c = mix(col, vec3(0.3, 0.3, 0.34), clamp(hull, 0.0, 1.0));
    float lights = step(0.9, hash(vec2(floor(q.x * 30.0), floor(q.y * 30.0)))) * hull;
    c += vec3(0.9, 0.95, 1.0) * lights * 0.6;
    c += vec3(0.3, 0.6, 1.0) * boxf(q, vec2(-0.72, 0.0), vec2(0.04, 0.12));
    return c;
}


// Shuttle: landet weit hinten, steht, startet wieder (Flügel klappen beim Landen ein)
vec3 shuttle(vec2 q, float s, float t, float fold, vec3 col) {
    q /= s;
    float body = boxf(q, vec2(0.0, 0.15), vec2(0.14, 0.3)) + boxf(q, vec2(0.0, 0.5), vec2(0.06, 0.2));
    float wingL = tri(q, vec2(-0.12, 0.0), vec2(-0.12, 0.45), vec2(-0.75 + fold * 0.5, -0.3 + fold * 0.6));
    float wingR = tri(q, vec2(0.12, 0.0), vec2(0.12, 0.45), vec2(0.75 - fold * 0.5, -0.3 + fold * 0.6));
    vec3 c = mix(col, vec3(0.55, 0.56, 0.6), clamp(body + wingL + wingR, 0.0, 1.0));
    c += vec3(0.4, 0.7, 1.0) * boxf(q, vec2(0.0, -0.17), vec2(0.1, 0.03)) * (0.5 + 0.5 * sin(t * 25.0)) * (1.0 - fold);
    c += vec3(1.0, 0.3, 0.1) * step(0.5, fract(t * 1.5)) * boxf(q, vec2(0.0, 0.72), vec2(0.02, 0.02));
    return c;
}
// Konvoi: drei kastige Fahrzeuge hintereinander mit Scheinwerfern
vec3 convoy(vec2 q, float s, float t, float dir, vec3 col) {
    q /= s;
    vec3 c = col;
    for (int i = 0; i < 3; i++) {
        vec2 o = q - vec2(float(i) * 1.5, 0.0);
        float hull = boxf(o, vec2(0.0, 0.18), vec2(0.5, 0.14)) + boxf(o, vec2(0.25, 0.4), vec2(0.2, 0.1));
        float wheels = boxf(o, vec2(-0.3, 0.0), vec2(0.1, 0.06)) + boxf(o, vec2(0.3, 0.0), vec2(0.1, 0.06));
        c = mix(c, vec3(0.38, 0.33, 0.28) * (0.8 + 0.2 * float(i)), clamp(hull + wheels, 0.0, 1.0));
        c += vec3(1.0, 0.95, 0.7) * boxf(o, vec2(0.52 * dir, 0.2), vec2(0.04, 0.03));
    }
    return c;
}
// Droide: runde Kuppel auf Zylinder, rollt nah am Boden vorbei, Lichter blinken
vec3 droid(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float body = boxf(q, vec2(0.0, 0.25), vec2(0.22, 0.3)) + step(length((q - vec2(0.0, 0.55)) * vec2(1.0, 1.3)), 0.22);
    float legs = boxf(q, vec2(-0.3, 0.2), vec2(0.06, 0.28)) + boxf(q, vec2(0.3, 0.2), vec2(0.06, 0.28));
    vec3 c = mix(col, vec3(0.8, 0.8, 0.85), clamp(body + legs, 0.0, 1.0));
    c = mix(c, vec3(0.2, 0.4, 0.9), boxf(q, vec2(0.0, 0.3), vec2(0.22, 0.04)) + boxf(q, vec2(0.0, 0.12), vec2(0.22, 0.04)));
    c += vec3(1.0, 0.2, 0.2) * step(0.5, fract(t * 3.0)) * step(length(q - vec2(0.08, 0.62)), 0.04);
    c += vec3(0.3, 0.6, 1.0) * step(0.5, fract(t * 1.7 + 0.5)) * step(length(q - vec2(-0.08, 0.5)), 0.035);
    return c;
}
// Kriecher: riesige Kastenmaschine auf Raupen, kriecht am Horizont
vec3 crawler(vec2 q, float s, float t, vec3 col) {
    q /= s;
    float hull = tri(q, vec2(-1.0, 0.2), vec2(1.0, 0.2), vec2(0.0, 0.9)) * step(0.2, q.y) + boxf(q, vec2(0.0, 0.12), vec2(1.0, 0.12));
    float treads = boxf(q, vec2(0.0, -0.05), vec2(0.95, 0.07)) * step(0.5, fract(q.x * 12.0 - t * 2.0));
    vec3 c = mix(col, vec3(0.3, 0.26, 0.22), clamp(hull + treads, 0.0, 1.0));
    c += vec3(1.0, 0.9, 0.6) * step(0.8, hash(vec2(floor(q.x * 10.0), floor(q.y * 10.0)))) * hull * step(0.25, q.y) * 0.5;
    return c;
}
// Suchscheinwerfer einer fernen Basis: Kegel schwenkt über den Himmel
vec3 searchlight(vec2 p, float t, float x0, float groundY, vec3 col) {
    vec2 d = p - vec2(x0, groundY);
    float ang = atan(d.y, d.x);
    float target = 1.2 + 0.7 * sin(t * 0.6);
    if (x0 > 0.0) target = 3.14159 - target;           // von rechts nach links in die Szene leuchten
    float beam = smoothstep(0.1, 0.0, abs(ang - target)) * smoothstep(0.0, 0.1, d.y) * exp(-length(d) * 0.9);
    col += vec3(0.8, 0.9, 1.0) * beam * 0.7;
    col += vec3(1.0, 0.95, 0.8) * step(length(d * vec2(1.0, 2.0)), 0.015);
    return col;
}

vec3 events(vec2 p, vec2 cellsz, float t, float groundY, vec3 col) {
    float slot = floor(t / 16.0);
    float u = fract(t / 16.0);                     // 0..1 im Zeitfenster
    float kind = floor(hash1(slot + 3.7) * 16.0);  // 0..15: 14 Ereignisse, 14/15 = Pause
    if (uEventForce > 0.5) kind = uEventForce - 1.0;
    // Orbitalstation: langsam driftender Lichtpunkt, in jedem dritten Fenster sichtbar
    if (mod(slot, 3.0) < 1.0) {
        vec2 st = p - vec2(mix(-1.2, 1.2, u) * (step(0.5, hash1(slot + 44.4)) * 2.0 - 1.0), 0.9);
        col += vec3(0.9, 0.95, 1.0) * step(length(st), 0.008);
        col += vec3(1.0, 0.3, 0.2) * step(0.5, fract(t * 1.0)) * step(length(st - vec2(0.012, 0.0)), 0.006);
    }
    float dir = step(0.5, hash1(slot + 91.1)) * 2.0 - 1.0;
    float x = mix(-1.3, 1.3, u) * dir;             // von links nach rechts oder umgekehrt
    vec2 q;
    if (kind < 1.0) {                              // Transporter hoch über dem Horizont
        q = p - vec2(x, 0.72 + 0.03 * sin(u * 6.28)); q.x *= dir;
        col = transporter(q, 0.16, t, col);
    } else if (kind < 2.0) {                       // zwei Jäger, schnell (nur im ersten Drittel)
        float uu = u * 3.0;
        if (uu < 1.2) {
            float xx = mix(-1.5, 1.5, uu) * dir;
            q = p - vec2(xx, 0.62); q.x *= dir; col = fighter(q, 0.09, t, col);
            q = p - vec2(xx - 0.22 * dir, 0.56); q.x *= dir; col = fighter(q, 0.08, t + 1.0, col);
        }
    } else if (kind < 3.0) {                       // Läufer am Horizont, sehr langsam
        float xx = mix(-1.1, 1.1, u) * dir;
        q = p - vec2(xx, groundY + 0.06); q.x *= dir; col = walker(q, 0.09, t, col);
    } else if (kind < 4.0) {                       // Gleiter am Boden, zügig
        float uu = u * 2.0;
        if (uu < 1.3) {
            float xx = mix(-1.5, 1.5, uu) * dir;
            q = p - vec2(xx, groundY - 0.04); q.x *= dir; col = speeder(q, 0.1, t, col);
        }
    } else if (kind < 5.0) {                       // Sonde kommt, scannt, verschwindet
        float xx = mix(-1.2, 0.5 * dir, smoothstep(0.0, 0.4, u)) * (dir) + (1.0 - smoothstep(0.75, 1.0, u)) * 0.0;
        xx = mix(xx, 1.4 * dir, smoothstep(0.75, 1.0, u));
        q = p - vec2(xx, 0.5 + 0.02 * sin(t * 2.0)); col = probe(q, 0.09, t, col);
    } else if (kind < 6.0) {                       // Großschiff, weit und langsam
        float xx = mix(-1.2, 1.2, u) * dir;
        q = p - vec2(xx, 0.85); q.x *= dir; col = capital(q, 0.22, t, col);
    } else if (kind < 7.0) {                       // Ferne Gefechtsblitze am Horizont (siehe unten)
    } else if (kind < 8.0) {                       // Shuttle landet hinten, bleibt, startet wieder
        float xx = 0.75 * dir;
        float land = smoothstep(0.0, 0.3, u), lift = smoothstep(0.7, 1.0, u);
        float yy = groundY + 0.03 + (1.0 - land) * 0.7 + lift * 0.8;
        float fold = smoothstep(0.2, 0.3, u) * (1.0 - smoothstep(0.7, 0.8, u));
        q = p - vec2(xx, yy); col = shuttle(q, 0.17, t, fold, col);
        // Landelicht auf dem Boden, solange es steht
        col += vec3(0.4, 0.7, 1.0) * fold * 0.25 * exp(-length((p - vec2(xx, groundY)) * vec2(2.0, 8.0)) * 3.0);
    } else if (kind < 9.0) {                       // Konvoi hinten über den Boden
        float xx = mix(-1.6, 1.6, u) * dir;
        q = p - vec2(xx, groundY + 0.01); q.x *= dir; col = convoy(q, 0.06, t, dir, col);
    } else if (kind < 10.0) {                      // Droide rollt nah vorbei
        float uu = u * 1.6;
        if (uu < 1.2) {
            float xx = mix(-1.5, 1.5, uu) * dir;
            q = p - vec2(xx, groundY - 0.1 + 0.01 * abs(sin(t * 6.0))); col = droid(q, 0.08, t, col);
        }
    } else if (kind < 11.0) {                      // Kriecher am Horizont, sehr langsam
        float xx = mix(-0.9, 0.9, u) * dir;
        q = p - vec2(xx, groundY + 0.02); q.x *= dir; col = crawler(q, 0.09, t, col);
    } else if (kind < 12.0) {                      // Meteorschauer
        for (int i = 0; i < 6; i++) {
            float fi = float(i);
            float ph = fract(t / 1.8 + hash(vec2(fi, slot)));
            vec2 sp = vec2(-1.2 + hash(vec2(fi, slot + 1.0)) * 2.4 + ph * 0.9, 0.98 - ph * 0.45);
            float shoot = smoothstep(0.012, 0.0, segDist(p, sp, sp - vec2(0.09, 0.035))) * step(ph, 0.55) * step(0.15, u) * step(u, 0.95);
            col += vec3(1.0, 0.95, 0.8) * shoot;
        }
    } else if (kind < 13.0) {                      // Suchscheinwerfer einer fernen Basis
        col = searchlight(p, t, 0.82 * dir, groundY, col);   // p.x reicht nur bis ±0.89
    } else if (kind < 14.0) {                      // Patrouille: Transporter plus zwei Jäger als Eskorte
        q = p - vec2(x, 0.72); q.x *= dir; col = transporter(q, 0.14, t, col);
        q = p - vec2(x + 0.3 * dir, 0.66); q.x *= dir; col = fighter(q, 0.07, t, col);
        q = p - vec2(x + 0.3 * dir, 0.78); q.x *= dir; col = fighter(q, 0.07, t + 1.0, col);
    }
    if (kind >= 6.0 && kind < 7.0) {               // Gefecht
        float fl = step(0.93, hash(vec2(floor(t * 6.0), slot))) * step(0.2, u) * step(u, 0.8);
        float fx = (hash(vec2(floor(t * 6.0), 1.0)) - 0.5) * 2.0;
        col += vec3(1.0, 0.75, 0.45) * fl * exp(-length((p - vec2(fx, groundY + 0.04)) * vec2(1.0, 3.0)) * 3.5) * 1.6;
        col += vec3(1.0, 0.4, 0.2) * fl * step(length((p - vec2(fx, groundY + 0.04)) * vec2(1.0, 1.6)), 0.03);
        col += vec3(0.6, 0.5, 0.6) * fl * 0.12 * step(groundY, p.y);          // Himmel hellt kurz auf
        // Leuchtspuren, die zum Blitz hinziehen
        float tr = step(0.97, hash(vec2(floor(t * 9.0), slot + 2.0))) * step(0.2, u) * step(u, 0.8);
        float ty = groundY + 0.05 + fract(t * 0.9) * 0.25;
        col += vec3(0.3, 1.0, 0.4) * tr * step(abs(p.x - fx - (ty - groundY) * 0.6), 0.006) * step(abs(p.y - ty), 0.03);
    }
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float cellsX = floor(CELLS_Y * aspect);
    // Pixelraster
    vec2 cell = floor(vUv * vec2(cellsX, CELLS_Y));
    vec2 uv = (cell + 0.5) / vec2(cellsX, CELLS_Y);
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y);       // p.x zentriert, p.y 0..1

    // Anzünden: Flammenhöhe wächst in den ersten 5 s, Funke bei 0.5 s
    float ignite = smoothstep(0.8, 5.0, iTime);
    float flameH = mix(0.05, 1.0, ignite) * (1.0 + 0.12 * uRms * (1.0 - uSilent));
    float t = iTime;
    // Hitzeflimmern: über dem Feuer wabert der Himmel (Feuer, Scheite und Boden bleiben unverzerrt)
    vec2 pF = p, uvF = uv;
    float heat = smoothstep(0.5, 0.0, abs(p.x)) * smoothstep(0.27, 0.6, uv.y) * smoothstep(1.05, 0.7, uv.y) * ignite;
    float shim = (noise(vec2(p.x * 14.0, uv.y * 9.0 - t * 2.8)) - 0.5) * 0.022 * heat;
    p.x += shim; uv.x += shim / aspect;

    // ---- Himmel: violetter Nebel, zwei Monde, Ringplanet, Sternschnuppe; Boden: fremder Staub
    vec3 col = mix(vec3(0.02, 0.01, 0.05), vec3(0.08, 0.03, 0.14), uv.y);
    float neb = fbm(vec2(uv.x * 3.0 + 1.0, uv.y * 2.0 + t * 0.01));
    col += vec3(0.25, 0.08, 0.35) * pow(neb, 2.2) * step(0.3, uv.y) * 1.3;
    col += vec3(0.05, 0.2, 0.35) * pow(fbm(vec2(uv.x * 2.0 + 7.0, uv.y * 3.0)), 3.0) * step(0.3, uv.y);
    float star = step(0.994, hash(cell)) * (0.5 + 0.5 * sin(t * 2.0 + hash(cell + 7.0) * 6.28)) * step(0.3, uv.y);
    col += vec3(0.8, 0.85, 1.0) * star * 0.7;
    // großer Mond mit Kratern
    vec2 m1 = (p - vec2(0.55, 0.78)) * vec2(1.0, 1.0);
    float moon = smoothstep(0.075, 0.07, length(m1));
    float crater = 1.0 - 0.35 * step(0.6, noise(m1 * 60.0)) ;
    col = mix(col, vec3(0.75, 0.72, 0.65) * crater * (0.6 + 0.4 * smoothstep(0.07, -0.02, m1.x)), moon);
    // kleiner Ringplanet
    vec2 m2 = p - vec2(-0.6, 0.72);
    float planet = smoothstep(0.045, 0.04, length(m2));
    float ring = smoothstep(0.012, 0.0, abs(length(m2 * vec2(1.0, 3.5)) - 0.085)) * (1.0 - planet * step(0.0, m2.y));
    col = mix(col, vec3(0.9, 0.6, 0.35), planet);
    col += vec3(0.8, 0.7, 0.5) * ring * 0.8;
    // Sternschnuppe alle ~9 s
    float sh = fract(t / 9.0);
    vec2 sp = vec2(-0.9 + sh * 2.2, 0.95 - sh * 0.5);
    float shoot = smoothstep(0.012, 0.0, segDist(p, sp, sp - vec2(0.08, 0.018))) * step(sh, 0.35);
    col += vec3(1.0, 0.95, 0.8) * shoot;
    float groundY = 0.22;
    p = pF; uv = uvF;
    float ground = step(uv.y, groundY);
    col = mix(col, vec3(0.08, 0.05, 0.09) * (0.5 + 0.5 * hash(cell * 0.37)), ground);
    // Steine
    float rock = step(0.985, hash(floor(cell / 3.0))) * ground * step(uv.y, groundY - 0.02);
    col = mix(col, vec3(0.3, 0.28, 0.33), rock);

    // ---- Ereignisse im Hintergrund (Fahrzeuge, Läufer, Sonden, Gefechte)
    col = events(p, vec2(1.0 / cellsX, 1.0 / CELLS_Y), t, groundY, col);

    // ---- Lichtschein des Feuers (flackert)
    float flick = 0.75 + 0.2 * noise(vec2(t * 7.0, 3.0)) + 0.12 * noise(vec2(t * 23.0, 9.0)) + 0.1 * uBeat;
    float d = length((p - vec2(0.0, groundY + 0.05)) * vec2(1.0, 1.4));
    col += vec3(1.0, 0.5, 0.3) * exp(-d * 4.5) * 0.4 * flick * ignite;
    col += vec3(1.0, 0.35, 0.1) * exp(-d * 1.8) * 0.1 * flick * ignite;
    // Lichtflecken auf dem Boden, die mit dem Flackern wandern
    float groundLit = ground * exp(-d * 3.0) * flick * ignite;
    col += vec3(0.9, 0.45, 0.2) * groundLit * 0.25 * step(0.4, noise(vec2(p.x * 25.0, p.y * 25.0 + t * 0.8)));

    // ---- Scheite (zwei gekreuzte Stämme, Streifen in Holzmaserung)
    float logs = 0.0;
    float dl1 = segDist(p, vec2(-0.22, groundY - 0.01), vec2(0.20, groundY + 0.07));
    float dl2 = segDist(p, vec2(0.22, groundY - 0.01), vec2(-0.20, groundY + 0.07));
    float dl = min(dl1, dl2);
    if (dl < 0.035) {
        float stripe = step(0.5, fract((p.x + p.y * 0.3) * 30.0 + hash(vec2(floor(dl * 60.0), 1.0)) * 0.5));
        vec3 wood = mix(vec3(0.30, 0.16, 0.07), vec3(0.18, 0.09, 0.04), stripe);
        // Glut an den Innenseiten und glühende Risse, die pulsieren
        float glow = smoothstep(0.1, 0.0, abs(p.x)) * ignite * (0.6 + 0.4 * noise(vec2(t * 3.0, p.x * 20.0)));
        float crack = step(0.72, noise(vec2(p.x * 45.0, p.y * 45.0))) * ignite * (0.5 + 0.5 * sin(t * 2.5 + p.x * 30.0));
        wood = mix(wood, vec3(1.0, 0.35, 0.05), glow * 0.7);
        wood = mix(wood, vec3(1.0, 0.55, 0.15), crack * (0.3 + 0.7 * smoothstep(0.2, 0.0, abs(p.x))));
        col = wood;
        logs = 1.0;
    }

    // ---- Rauch: dunkle Schwaden über dem Feuer, die im Wind abdriften (Flammen übermalen ihn)
    float fy = (uv.y - groundY) / (0.55 * flameH);     // 0 am Boden, 1 an der Spitze
    if (logs < 0.5 && uv.y > groundY + 0.25 * flameH) {
        float wind = sin(t * 0.17) * 0.35;
        float drift = (uv.y - groundY) * wind + sin(uv.y * 6.0 - t * 0.5) * 0.04;
        float sm = fbm(vec2(p.x * 4.0 - drift * 2.0 + t * 0.1, uv.y * 3.0 - t * 0.55));
        float column = smoothstep(0.28, 0.0, abs(p.x - drift)) * smoothstep(groundY + 0.3 * flameH, groundY + 0.7 * flameH, uv.y) * smoothstep(1.15, 0.75, uv.y);
        float smoke = smoothstep(0.45, 0.75, sm) * column * ignite * 0.6;
        col = mix(col, vec3(0.17, 0.14, 0.2), smoke);
    }
    // ---- Flammen: Rauschen, das nach oben zieht, mit Form (unten breit, oben spitz), seitliche
    //      Zungen, die abreißen, und Fetzen, die über der Spitze davonfliegen
    if (fy > -0.05 && fy < 1.45 && logs < 0.5) {
        float n = fbm(vec2(p.x * 5.0 + sin(t * 0.7) * 0.3, uv.y * 6.0 - t * 2.4));
        float n2 = noise(vec2(p.x * 12.0 + 3.0, uv.y * 16.0 - t * 4.5));
        float n3 = fbm(vec2(p.x * 9.0 - t * 0.4, uv.y * 10.0 - t * 3.6));
        float wobble = (n - 0.5) * 0.12 * (0.3 + fy);
        float width = 0.30 * flameH * (1.0 - fy * 0.8) + wobble;
        float cx = (n2 - 0.5) * 0.06 * fy + (n3 - 0.5) * 0.09 * fy * fy;   // die Spitze schwankt stärker
        float shape = 1.0 - clamp(abs(p.x + cx) / max(width, 0.001), 0.0, 1.0);
        float v = shape * (0.35 + 1.1 * n + 0.3 * n2) - fy * 0.75;
        for (int sgn = -1; sgn <= 1; sgn += 2) {
            float sx = float(sgn) * (0.14 + 0.03 * sin(t * 1.7 + float(sgn)));
            float ty = fy * 1.7;
            float tn = noise(vec2(p.x * 10.0 + float(sgn) * 7.0, uv.y * 14.0 - t * 5.0));
            float tw = 0.10 * flameH * (1.0 - ty * 0.7) * (0.5 + 0.7 * tn);
            float ts = 1.0 - clamp(abs(p.x - sx) / max(tw, 0.001), 0.0, 1.0);
            v = max(v, ts * (0.3 + 0.9 * tn) - ty * 0.6);
        }
        float torn = noise(vec2(p.x * 8.0, uv.y * 9.0 - t * 3.4));
        v += step(0.95, fy) * step(0.8, torn) * 0.55 * (1.45 - fy) * smoothstep(0.25, 0.0, abs(p.x + cx));
        v += 0.1 * uMid * (1.0 - uSilent);
        int k = int(clamp(v, 0.0, 0.999) * 6.0);
        if (k >= 1) {
            col = firePal(k);
        }
    }
    // Funke vor dem Anzünden
    if (iTime < 1.2 && abs(p.x) < 0.012 && abs(uv.y - groundY - 0.06) < 0.012 && fract(iTime * 8.0) > 0.5) {
        col = vec3(1.0, 0.9, 0.5);
    }

    // ---- Funken: 22 Partikel steigen in Wirbeln auf, kühlen von gelb nach dunkelrot ab und verlöschen
    for (int i = 0; i < 22; i++) {
        float fi = float(i);
        float speed = 0.1 + 0.12 * hash(vec2(fi, 2.0));
        float life = fract(t * speed + hash(vec2(fi, 3.0)));         // 0..1 Lebenszeit
        float sx = (hash(vec2(fi, 4.0)) - 0.5) * 0.25 + sin(t * 1.3 + fi) * 0.05 * life
                 + life * (hash(vec2(fi, 5.0)) - 0.5) * 0.25 + 0.03 * sin(t * 4.0 + fi * 2.0) * life;
        float sy = groundY + 0.08 + life * (0.45 + 0.4 * hash(vec2(fi, 6.0)));
        vec2 sc = floor(vec2(sx / aspect + 0.5, sy) * vec2(cellsX, CELLS_Y));
        float bright = (1.0 - life) * ignite * step(0.25, hash(vec2(fi, floor(t * 6.0))));
        bright *= 1.0 + 1.5 * uBeat;
        if (sc == cell && bright > 0.12) {
            col = mix(vec3(0.6, 0.12, 0.02), mix(vec3(1.0, 0.5, 0.1), vec3(1.0, 0.9, 0.5), bright), smoothstep(0.1, 0.6, bright));
        }
    }
    // ---- Knistern: alle paar Sekunden sprüht ein Funkenregen aus dem Scheit
    float burstT = mod(t, 3.0);
    float burstOn = step(0.55, hash(vec2(floor(t / 3.0), 7.0))) * ignite;
    if (burstOn > 0.5 && burstT < 1.0) {
        for (int i = 0; i < 8; i++) {
            float fi = float(i);
            float seed = floor(t / 3.0) * 10.0 + fi;
            float vx = (hash(vec2(seed, 1.0)) - 0.5) * 0.9;
            float vy = 0.5 + hash(vec2(seed, 2.0)) * 0.7;
            float bx = (hash(vec2(seed, 3.0)) - 0.5) * 0.15 + vx * burstT;
            float by = groundY + 0.06 + vy * burstT - 0.45 * burstT * burstT;
            vec2 sc = floor(vec2(bx / aspect + 0.5, by) * vec2(cellsX, CELLS_Y));
            if (sc == cell) col = mix(vec3(1.0, 0.95, 0.7), vec3(1.0, 0.4, 0.1), burstT);
        }
    }

    // ---- leichte CRT-Scanlines und Vignette
    col *= 0.9 + 0.1 * sin(vUv.y * iResolution.y * 3.14159 * 0.5);
    col *= 1.0 - 0.35 * smoothstep(0.7, 1.6, length(vUv * 2.0 - 1.0));
    fragColor = vec4(col, 1.0);
}
