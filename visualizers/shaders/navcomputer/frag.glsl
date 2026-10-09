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
vec3 pal(float t) { return 0.5 + 0.5 * cos(2.0 * PI * (vec3(1.0, 0.9, 0.7) * t + vec3(0.0, 0.25, 0.5))); }

// Oberfläche eines Planeten nach Typ: n = Rauschen auf der Kugel, lat = Breite -1..1
vec3 surface(int type, vec3 sp, float lat, float t) {
    float n = vfbm3(sp * 3.0);
    float n2 = vfbm3(sp * 9.0 + 7.0);
    vec3 a = uColA, b = uColB;
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
        col *= light;
        if (type == 4) col += vec3(1.0, 0.8, 0.45) * (1.0 - smoothstep(0.0, 0.25, diff)) * step(0.85, fract(sp.x * 40.0)) * 0.6;  // Stadtlichter nachts
        if (type == 5) col += uColB * (1.0 - smoothstep(0.0, 0.3, diff)) * smoothstep(0.5, 0.52, 1.0 - abs(vfbm3(sp * 9.0 + 7.0) - 0.5) * 2.0) * 0.6;
        // Terminator weich, Rim-Licht der Atmosphäre
        col += mix(uColB, vec3(0.6, 0.8, 1.0), 0.5) * pow(1.0 - z, 3.0) * 0.6 * light;
        res = vec4(col, 1.0);
    }
    // Atmosphärenglühen außen
    float glow = smoothstep(1.35, 1.0, r) * (1.0 - step(r, 1.0));
    res.rgb += mix(uColA, vec3(0.5, 0.7, 1.0), 0.5) * glow * 0.35;
    res.a = max(res.a, glow * 0.6);
    return res;
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;
    float live = 1.0 - uSilent;
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

    // ---- Planet (browse: mittig, beim Wechsel seitlich hereingleitend)
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
    fragColor = vec4(col, 1.0);
}
