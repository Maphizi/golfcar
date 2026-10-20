#version 140
// Lagerfeuer auf einem fremden Planeten, realistisch: weiche Flammen aus verformtem Rauschen mit
// Farbverlauf von Dunkelrot bis Weißgelb, Hitzeflimmern, Rauch, glühende Scheite mit Rissen, Funken
// mit Nachleuchten, Lichtschein auf dem Boden, Sternenhimmel mit Nebel und zwei Monden. Reagiert auf
// Audio (Bass = Flammenhöhe, Beat = Funken, Mitten = Flackern). Hintergrund-Ereignisse (Fahrzeuge,
// Läufer, Sonden) als Silhouetten mit Lichtern, alle 16 s ein Zeitfenster (uEventForce erzwingt).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uEventForce;   // Test: >0 erzwingt Ereignis (Wert-1), 0 = zufällig

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float hash1(float n) { n = fract(n * 0.1031); n *= n + 33.33; n *= n + n; return fract(n); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + 11.0; a *= 0.5; }
    return v;
}
// Feuerfarbe: 0 schwarz, 0.3 dunkelrot, 0.55 orange, 0.8 gelb, 1 weiß
vec3 fireRamp(float v) {
    v = clamp(v, 0.0, 1.0);
    vec3 c = mix(vec3(0.0), vec3(0.55, 0.03, 0.0), smoothstep(0.0, 0.25, v));
    c = mix(c, vec3(1.0, 0.35, 0.02), smoothstep(0.25, 0.55, v));
    c = mix(c, vec3(1.0, 0.85, 0.3), smoothstep(0.55, 0.82, v));
    c = mix(c, vec3(1.0, 0.98, 0.9), smoothstep(0.82, 1.0, v));
    return c;
}
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
    vec2 uv = vUv;
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y);
    float t = iTime;
    float live = 1.0 - uSilent;
    float ignite = smoothstep(0.8, 5.0, iTime);
    float flameH = mix(0.05, 1.0, ignite) * (1.0 + 0.15 * uBass * live);
    float groundY = 0.22;

    // ---- Hitzeflimmern über dem Feuer: der Himmel wabert leicht
    vec2 pS = p, uvS = uv;
    float heat = smoothstep(0.55, 0.0, abs(p.x)) * smoothstep(0.26, 0.5, uv.y) * smoothstep(1.1, 0.7, uv.y) * ignite;
    float shim = (noise(vec2(p.x * 16.0, uv.y * 10.0 - t * 3.0)) - 0.5) * 0.02 * heat;
    pS.x += shim; uvS.x += shim / aspect;

    // ---- Himmel: tiefes Violett, Nebel, weiche Sterne, zwei Monde, Sternschnuppe
    vec3 col = mix(vec3(0.03, 0.02, 0.07), vec3(0.14, 0.06, 0.22), smoothstep(0.2, 1.0, uvS.y));
    float neb = fbm(pS * 1.6 + vec2(t * 0.004, 0.0));
    col += mix(vec3(0.3, 0.1, 0.4), vec3(0.1, 0.25, 0.45), noise(pS * 2.5)) * smoothstep(0.45, 0.85, neb) * 0.5 * smoothstep(0.2, 0.6, uvS.y);
    for (int i = 0; i < 2; i++) {
        float fi = float(i);
        vec2 sg = pS * (70.0 + fi * 55.0) + fi * 13.0;
        vec2 cell = floor(sg);
        vec2 f = fract(sg) - 0.5 + (vec2(hash12(cell + 1.0), hash12(cell + 2.0)) - 0.5) * 0.6;
        float h = hash12(cell + fi);
        float star = step(0.93 - fi * 0.02, h) * smoothstep(0.08, 0.0, length(f)) * (0.5 + 0.5 * sin(t * (1.0 + h * 3.0) + h * 40.0));
        col += mix(vec3(0.9, 0.95, 1.0), vec3(1.0, 0.8, 0.6), hash12(cell + 7.0)) * star * (0.7 + 0.5 * uHigh * live) * smoothstep(groundY, 0.4, uvS.y);
    }
    // großer Mond mit Kratern und Terminator
    {
        vec2 mc = pS - vec2(0.55, 0.78);
        float mr = length(mc) / 0.085;
        if (mr < 1.0) {
            float z = sqrt(1.0 - mr * mr);
            vec3 n = vec3(mc / 0.085, z);
            float crat = fbm(n.xy * 9.0 + 3.0);
            float lit = 0.1 + 0.9 * clamp(dot(n, normalize(vec3(-0.5, 0.3, 0.8))), 0.0, 1.0);
            col = mix(col, mix(vec3(0.55, 0.58, 0.65), vec3(0.85, 0.87, 0.9), smoothstep(0.4, 0.7, crat)) * lit, smoothstep(1.0, 0.97, mr));
        }
        col += vec3(0.5, 0.55, 0.75) * smoothstep(0.2, 0.0, mr - 1.0) * 0.15;
        // kleiner Ringplanet links
        vec2 rc = pS - vec2(-0.62, 0.72);
        float rr = length(rc) / 0.035;
        vec2 rq = mat2(0.94, -0.34, 0.34, 0.94) * rc / 0.035;
        float ring = smoothstep(0.1, 0.0, abs(rq.y)) * step(1.3, abs(rq.x)) * step(abs(rq.x), 2.4);
        col = mix(col, vec3(0.85, 0.75, 0.6), ring * 0.8 * (1.0 - step(rr, 1.0) * step(0.0, rq.y)));
        if (rr < 1.0) col = mix(col, vec3(0.9, 0.7, 0.45) * (0.4 + 0.6 * sqrt(1.0 - rr * rr)) * (0.8 + 0.2 * sin(rc.y * 80.0)), 1.0);
    }
    // Sternschnuppe
    {
        float ph = fract(t / 9.0);
        vec2 sp = vec2(-0.9 + ph * 2.0, 0.97 - ph * 0.5);
        float shoot = smoothstep(0.004, 0.0, segDist(pS, sp, sp - vec2(0.12, 0.03))) * step(ph, 0.5) * step(0.05, ph);
        col += vec3(1.0, 0.95, 0.85) * shoot;
    }

    // ---- Boden: dunkler Staub mit Steinen, vom Feuer beleuchtet
    float ground = step(uv.y, groundY);
    float gn = fbm(vec2(p.x * 5.0, uv.y * 28.0));
    vec3 soil = mix(vec3(0.07, 0.05, 0.08), vec3(0.12, 0.09, 0.11), gn);
    float rock = smoothstep(0.84, 0.9, noise(vec2(p.x * 30.0, uv.y * 130.0))) * 0.5;
    soil = mix(soil, vec3(0.22, 0.2, 0.24) * (0.6 + 0.6 * gn), rock);
    col = mix(col, soil, ground);

    // ---- Hintergrund-Ereignisse (Silhouetten mit Lichtern)
    col = events(p, vec2(1.0 / iResolution.x, 1.0 / iResolution.y) * 3.0, t, groundY, col);

    // ---- Lichtschein des Feuers auf Boden und Luft, flackert
    float flick = 0.75 + 0.2 * noise(vec2(t * 7.0, 3.0)) + 0.12 * noise(vec2(t * 23.0, 9.0)) + 0.1 * uBeat * live + 0.1 * uMid * live;
    float d = length((p - vec2(0.0, groundY + 0.05)) * vec2(1.0, 1.4));
    col += vec3(1.0, 0.45, 0.2) * exp(-d * 4.0) * 0.45 * flick * ignite;
    col += vec3(1.0, 0.3, 0.08) * exp(-d * 1.6) * 0.12 * flick * ignite;
    float groundLit = ground * exp(-d * 2.6) * flick * ignite;
    col += vec3(1.0, 0.5, 0.2) * groundLit * 0.35 * (0.6 + 0.6 * gn);
    // Schatten der Scheite auf dem Boden
    col *= 1.0 - 0.3 * ground * smoothstep(0.26, 0.0, abs(p.x)) * smoothstep(groundY - 0.03, groundY - 0.1, uv.y) * ignite;

    // ---- Rauch: dunkle Schwaden, die im Wind abdriften
    if (uv.y > groundY + 0.25 * flameH) {
        float wind = sin(t * 0.17) * 0.35;
        float drift = (uv.y - groundY) * wind + sin(uv.y * 6.0 - t * 0.5) * 0.04;
        float sm = fbm(vec2(p.x * 4.0 - drift * 2.0 + t * 0.1, uv.y * 3.0 - t * 0.55));
        float column = smoothstep(0.3, 0.0, abs(p.x - drift)) * smoothstep(groundY + 0.3 * flameH, groundY + 0.75 * flameH, uv.y) * smoothstep(1.2, 0.8, uv.y);
        float smoke = smoothstep(0.42, 0.75, sm) * column * ignite * 0.55;
        col = mix(col, vec3(0.16, 0.13, 0.18), smoke);
    }

    // ---- Scheite: zwei gekreuzte Stämme, zylindrisch schattiert, Rinde, glühende Risse
    float logs = 0.0;
    {
        vec2 a1 = vec2(-0.24, groundY - 0.005), b1 = vec2(0.22, groundY + 0.075);
        vec2 a2 = vec2(0.24, groundY - 0.005), b2 = vec2(-0.22, groundY + 0.075);
        for (int i = 0; i < 2; i++) {
            vec2 a = i == 0 ? a1 : a2, b = i == 0 ? b1 : b2;
            vec2 ba = b - a;
            float h = clamp(dot(p - a, ba) / dot(ba, ba), 0.0, 1.0);
            vec2 perp = p - (a + ba * h);
            float dist = length(perp);
            float rad = 0.034;
            if (dist < rad && h > 0.0 && h < 1.0) {
                float s = perp.y / rad;                                  // -1..1 quer über den Stamm
                float shade = 0.2 + 0.8 * pow(max(0.0, 1.0 - s * s), 0.6) * (0.6 + 0.4 * smoothstep(-1.0, 0.4, s));
                float bark = noise(vec2(h * 60.0, s * 4.0)) * 0.6 + noise(vec2(h * 180.0, s * 14.0)) * 0.3;
                float ridges = smoothstep(0.3, 0.7, noise(vec2(h * 90.0, s * 3.0)));
                vec3 wood = mix(vec3(0.12, 0.06, 0.03), vec3(0.3, 0.17, 0.08), bark) * (0.7 + 0.3 * ridges) * shade;
                float charred = smoothstep(0.3, 0.0, abs(p.x)) * ignite;
                wood = mix(wood, vec3(0.05, 0.03, 0.03), charred * 0.6);                    // verkohlt zur Mitte hin
                float crack = smoothstep(0.66, 0.8, noise(vec2(h * 80.0, s * 7.0 + float(i) * 5.0))) * charred;
                float pulse = 0.55 + 0.45 * sin(t * 2.0 + h * 25.0 + float(i));
                wood = mix(wood, vec3(1.0, 0.3, 0.04) * (0.7 + 0.5 * pulse), crack * 0.95);
                wood += vec3(1.0, 0.45, 0.15) * charred * 0.12 * pulse * (1.0 - abs(s)) * flick;
                col = mix(col, wood, 1.0 - smoothstep(rad - 0.003, rad, dist));
                logs = max(logs, 1.0 - smoothstep(rad - 0.003, rad, dist));
            }
        }
        // Glut zwischen den Scheiten
        float ember = smoothstep(0.12, 0.0, length((p - vec2(0.0, groundY + 0.02)) * vec2(1.0, 2.5))) * ignite;
        float en = noise(vec2(p.x * 60.0, p.y * 60.0 + t * 0.3));
        col += fireRamp(0.5 + 0.4 * en) * ember * (0.5 + 0.5 * sin(t * 3.0 + en * 10.0)) * (1.0 - logs) * 0.9;
    }

    // ---- Flammen: verformtes Rauschen, das aufsteigt, in einer Hüllkurve (unten breit, oben spitz),
    //      mehrere Zungen, additiv mit Glühen
    float fy = (uv.y - groundY) / (0.42 * flameH);
    float fyp = max(fy, 0.0);
    if (fy > -0.02 && fy < 1.6) {
        vec2 fp = vec2(p.x, uv.y - groundY);
        float warp = fbm(vec2(fp.x * 6.0 + t * 0.3, fp.y * 5.0 - t * 2.2));
        float warp2 = fbm(vec2(fp.x * 11.0 - t * 0.5, fp.y * 9.0 - t * 3.6) + warp * 1.5);
        float cx = (warp - 0.5) * 0.1 * fyp + (warp2 - 0.5) * 0.14 * fyp * fyp;
        float width = 0.2 * flameH * (1.0 - fyp * 0.72) * (0.85 + 0.3 * warp);
        float env = 1.0 - clamp(abs(fp.x + cx) / max(width, 0.001), 0.0, 1.0);
        env = pow(env, 0.8);
        float v = env * (0.45 + 1.1 * warp2 + 0.3 * warp) - fyp * 0.85;
        // seitliche Zungen, die abreißen
        for (int sgn = -1; sgn <= 1; sgn += 2) {
            float sx = float(sgn) * (0.1 + 0.03 * sin(t * 1.7 + float(sgn)));
            float tn = fbm(vec2(fp.x * 10.0 + float(sgn) * 7.0, fp.y * 12.0 - t * 4.5));
            float tw = 0.07 * flameH * (1.0 - fyp * 1.1) * (0.5 + 0.8 * tn);
            float ts = 1.0 - clamp(abs(fp.x - sx) / max(tw, 0.001), 0.0, 1.0);
            v = max(v, ts * (0.35 + 0.9 * tn) - fyp * 1.3);
        }
        v += 0.1 * uMid * live;
        float core = clamp(v, 0.0, 1.0);
        vec3 fc = fireRamp(core);
        float alpha = smoothstep(0.02, 0.25, core);
        col = mix(col, fc, alpha * (1.0 - 0.6 * logs));                          // Scheite bleiben vor der Flammenbasis sichtbar
        col += fc * core * 0.35;                                             // Glühen
        // Hitzesaum
        col += vec3(0.9, 0.3, 0.1) * smoothstep(0.0, 0.15, core) * (1.0 - smoothstep(0.15, 0.4, core)) * 0.25;
    }
    // Funke vor dem Anzünden
    col += vec3(1.0, 0.9, 0.5) * step(iTime, 1.2) * smoothstep(0.012, 0.0, length(p - vec2(0.0, groundY + 0.06))) * step(0.5, fract(iTime * 8.0));

    // ---- Funken: steigen in Wirbeln auf, glühen mit Nachleuchten, kühlen von gelb nach rot ab
    for (int i = 0; i < 26; i++) {
        float fi = float(i);
        float speed = 0.1 + 0.12 * hash(vec2(fi, 2.0));
        float life = fract(t * speed + hash(vec2(fi, 3.0)));
        float sx = (hash(vec2(fi, 4.0)) - 0.5) * 0.22 + sin(t * 1.3 + fi) * 0.05 * life
                 + life * (hash(vec2(fi, 5.0)) - 0.5) * 0.3 + 0.03 * sin(t * 4.0 + fi * 2.0) * life;
        float sy = groundY + 0.08 + life * (0.45 + 0.45 * hash(vec2(fi, 6.0)));
        float bright = (1.0 - life) * ignite * step(0.25, hash(vec2(fi, floor(t * 6.0) + 0.0)));
        bright *= 1.0 + 1.5 * uBeat * live;
        float dd = length((p - vec2(sx, sy)) * vec2(1.0, 0.7));
        vec3 sc = mix(vec3(0.7, 0.1, 0.02), mix(vec3(1.0, 0.5, 0.1), vec3(1.0, 0.95, 0.6), bright), smoothstep(0.1, 0.7, bright));
        col += sc * bright * (smoothstep(0.004, 0.0, dd) + 0.5 * smoothstep(0.014, 0.0, dd));
    }
    // Knistern: Funkenregen alle paar Sekunden
    float burstT = mod(t, 3.0);
    float burstOn = step(0.55, hash(vec2(floor(t / 3.0), 7.0))) * ignite;
    if (burstOn > 0.5 && burstT < 1.0) {
        for (int i = 0; i < 8; i++) {
            float seed = floor(t / 3.0) * 10.0 + float(i);
            float vx = (hash(vec2(seed, 1.0)) - 0.5) * 0.9, vy = 0.5 + hash(vec2(seed, 2.0)) * 0.7;
            vec2 bp = vec2((hash(vec2(seed, 3.0)) - 0.5) * 0.15 + vx * burstT, groundY + 0.06 + vy * burstT - 0.45 * burstT * burstT);
            float dd = length(p - bp);
            col += mix(vec3(1.0, 0.95, 0.7), vec3(1.0, 0.4, 0.1), burstT) * (smoothstep(0.004, 0.0, dd) + 0.4 * smoothstep(0.012, 0.0, dd)) * (1.0 - burstT);
        }
    }

    // ---- Nachbearbeitung: leichtes Korn, Vignette
    col = col / (1.0 + col * 0.25);
    col += (hash12(vUv * iResolution + t) - 0.5) * 0.012;
    col *= 1.0 - 0.4 * smoothstep(0.6, 1.6, length(vUv * 2.0 - 1.0));
    fragColor = vec4(col, 1.0);
}
