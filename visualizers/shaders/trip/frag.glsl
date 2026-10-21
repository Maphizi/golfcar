#version 140
// Waldtresen und psychedelische Reise. uPhase 0 browse (Tresen-Foto, Wesen auf dem Teller), 1 eat (Wesen
// fliegt auf die Kamera zu, Biss, Augenlider), 2 trip (Kaleidoskop aus Naturtexturen mit Verdrehung,
// Atmen, wandernden Farben, schwebenden Symbolen, Ereignissen), 3 comedown (zurück an den Tresen).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uBarTex, uBeingsTex, uSymbolTex, uFaceTex, uTex0, uTex1, uTex2, uGodTex, uRootTex;
uniform vec2 uBarSize, uBeingsSize, uSymbolSize, uFaceSize, uTexSize, uGodSize, uRootSize;
uniform float uGodOK, uRootOK;
uniform vec4 uVariant;                                    // Variante, vorige, Überblendung, Texturversatz
uniform float uNumTex, uPhase, uPhaseT, uSlide, uCell, uTripT, uSpin, uMirrors, uPalette, uIntensity;
uniform float uBassS, uMidS, uHighS, uEnergy, uPulse, uEvent, uEventT, uEventLen, uEventSeed, uFaceOK;
uniform vec4 uProfile, uProfile2, uSymA, uSymB, uEvSym;   // Profil: twist, warp, tempo, idx; Zeiten: eat, comedown
const float PI = 3.14159265;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
vec3 hueShift(vec3 c, float a) {
    const vec3 k = vec3(0.57735);
    float cs = cos(a), sn = sin(a);
    return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs);
}
vec3 pal(float t, float p) {
    // sechs Farbwelten: 0 Pilz (rot/gold), 1 Wüste (orange/violett), 2 Wald (grün/gelb), 3 Wasser (blau/cyan), 4 Nebel (violett/rosa), 5 Regenbogen
    vec3 a = vec3(0.5), b = vec3(0.5), c = vec3(1.0), d = vec3(0.0, 0.33, 0.67);
    if (p < 0.5)      { d = vec3(0.0, 0.1, 0.2); c = vec3(1.0, 0.7, 0.4); }
    else if (p < 1.5) { d = vec3(0.0, 0.15, 0.5); c = vec3(1.0, 0.8, 0.6); }
    else if (p < 2.5) { d = vec3(0.3, 0.2, 0.0); c = vec3(0.6, 1.0, 0.5); }
    else if (p < 3.5) { d = vec3(0.5, 0.6, 0.8); c = vec3(0.6, 0.9, 1.0); }
    else if (p < 4.5) { d = vec3(0.7, 0.4, 0.6); c = vec3(0.9, 0.6, 1.0); }
    return a + b * cos(2.0 * PI * (c * t + d));
}
vec3 palMix(float t) { float p0 = floor(uPalette), f = fract(uPalette); return mix(pal(t, p0), pal(t, mod(p0 + 1.0, 6.0)), f); }
// bilinear aus NEAREST-Texturen
vec4 bilin(sampler2D tex, vec2 px, vec2 size, vec2 lo, vec2 hi) {
    px -= 0.5;
    vec2 i = floor(px), f = fract(px);
    vec2 a = clamp(i, lo, hi), b = clamp(i + 1.0, lo, hi);
    vec4 s00 = texture(tex, (vec2(a.x, a.y) + 0.5) / size), s10 = texture(tex, (vec2(b.x, a.y) + 0.5) / size);
    vec4 s01 = texture(tex, (vec2(a.x, b.y) + 0.5) / size), s11 = texture(tex, (vec2(b.x, b.y) + 0.5) / size);
    return mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
}
vec3 texWrap(int which, vec2 uv) {
    uv = fract(uv);
    uv = abs(uv * 2.0 - 1.0);                                   // gespiegelt kacheln: keine Nähte
    uv = 1.0 - uv;
    vec2 px = uv * uTexSize;
    if (which == 1 && uNumTex > 1.5) return bilin(uTex1, px, uTexSize, vec2(0.0), uTexSize - 1.0).rgb;
    if (which == 2 && uNumTex > 2.5) return bilin(uTex2, px, uTexSize, vec2(0.0), uTexSize - 1.0).rgb;
    return bilin(uTex0, px, uTexSize, vec2(0.0), uTexSize - 1.0).rgb;
}
// Wesen aus dem Atlas (5x4 à 256): l 0..1 über die Zelle, y nach oben
vec4 being(float cell, vec2 l) {
    if (l.x <= 0.0 || l.x >= 1.0 || l.y <= 0.0 || l.y >= 1.0) return vec4(0.0);
    float c = mod(cell, 5.0), r = floor(cell / 5.0);
    vec2 lo = vec2(c * 256.0, (3.0 - r) * 256.0);
    return bilin(uBeingsTex, lo + l * 256.0, uBeingsSize, lo, lo + 255.0);
}
// Symbol aus dem Atlas (8x5 à 128), p Bildkoordinaten, c Mitte, sz halbe Größe, ang Drehung
vec4 symbol(float idx, vec2 p, vec2 c, float sz, float ang) {
    vec2 d = rot(ang) * (p - c) / sz;
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 128.0, (4.0 - ri) * 128.0);
    return bilin(uSymbolTex, lo + (d * 0.5 + 0.5) * 128.0, uSymbolSize, lo, lo + 127.0);
}
float symIdx(int i) { return i < 4 ? uSymA[i] : uSymB[i - 4]; }

// ---- Kaleidoskop-Reise
vec3 tripImage(vec2 uv, float t, float inten, float variant) {
    float twist = uProfile.x, warp = uProfile.y;
    vec2 p = uv;
    // Atmen mit dem Bass, Beat-Stoß, langsame Drehung
    p *= 1.0 - 0.1 * uBassS * inten - 0.04 * uPulse * inten - 0.03 * sin(t * 0.7) * inten;
    float r = length(p), a = atan(p.y, p.x) + uSpin;
    // Spiralverdrehung: Winkel hängt vom Radius ab
    a += twist * inten * (1.5 * sin(r * 3.0 - t * 0.6) + 0.8 * r);
    // Kaleidoskop: Winkel in Segmente falten
    float m = max(2.0, floor(uMirrors + 0.5));
    float seg = 2.0 * PI / m;
    float af = mod(a, seg);
    af = min(af, seg - af);
    vec2 q;
    if (variant < 0.5) {                                                      // 0 klassisch
        q = vec2(cos(af), sin(af)) * r;
    } else if (variant < 1.5) {                                               // 1 Tunnel: log-polar, zieht nach innen
        q = vec2(af / seg * 1.6 - 0.8, log(r + 0.06) * 1.3 - t * 0.35 * (0.6 + 0.8 * uBassS));
    } else if (variant < 2.5) {                                               // 2 Blüte: Radius gefaltet, Blütenblätter
        float rf = abs(fract(r * 1.5 - t * 0.06 - 0.3 * uBassS * inten) - 0.5) * 2.0;
        q = vec2(cos(af), sin(af)) * (0.25 + rf * 0.9);
    } else {                                                                  // 3 Zellen: Spiegel-Raster über dem Kaleidoskop
        q = vec2(cos(af), sin(af)) * r;
        q = abs(fract(q * 1.4 + t * 0.03) - 0.5) * 2.0;
    }
    // Domain-Warp mit Rauschen, Stärke aus Profil und Intensität (und Mitten)
    vec2 w = vec2(fbm(q * 2.0 + t * 0.15), fbm(q * 2.0 - t * 0.12 + 7.0)) - 0.5;
    q += w * (0.35 + 0.3 * uMidS) * warp * inten;
    // Texturkoordinaten: Zoom pulst, Texturen überblenden alle ~20 s, Drop versetzt
    float zoom = 0.9 + 0.25 * sin(t * 0.21) + 0.15 * uPulse;
    vec2 tc = q * zoom + vec2(t * 0.02, -t * 0.015) + uVariant.w * 0.37;
    float cyc = t * 0.05 + uVariant.w;
    float which = mod(floor(cyc), max(1.0, uNumTex));
    float nextw = mod(which + 1.0, max(1.0, uNumTex));
    float blend = smoothstep(0.7, 1.0, fract(cyc));
    vec3 tex = mix(texWrap(int(which), tc), texWrap(int(nextw), tc * 1.1 + 0.3), blend);
    // Farben: Hue wandert, Palette färbt die Helligkeit ein, Sättigung steigt mit der Intensität
    float lum = dot(tex, vec3(0.3, 0.55, 0.15));
    vec3 col = hueShift(tex, (t * 0.08 + r * 0.6 * inten) * inten * 2.0);
    vec3 tinted = palMix(lum * 1.2 + t * 0.03 + r * 0.4);
    col = mix(col, col * 0.4 + tinted * (0.5 + 0.6 * lum), 0.55 * inten);
    col = mix(vec3(lum), col, 1.0 + 0.6 * inten);                               // übersättigt
    // Lichtadern: dünne leuchtende Linien in den Spiegeln, pulsen mit dem Beat
    float vein = smoothstep(0.03, 0.0, abs(fract(q.x * 3.0 + q.y * 2.0 + t * 0.1) - 0.5)) * 0.25 * inten * (0.5 + uPulse);
    col += palMix(t * 0.1 + 0.5) * vein;
    // Ringe aus der Tiefe (Tunnel), schwach
    float ring = pow(0.5 + 0.5 * sin(log(r + 0.05) * 6.0 - t * 1.2), 6.0) * 0.18 * inten;
    col += palMix(r + t * 0.05) * ring;
    // Mitte leuchtet mit dem Bass
    col += palMix(t * 0.07) * exp(-r * 3.0) * (0.15 + 0.5 * uBassS) * inten;
    return col;
}
// Schwebende Symbole: in Kaleidoskop-Koordinaten (werden gespiegelt) und frei im Bild
vec3 tripSymbols(vec3 col, vec2 uv, float t, float inten) {
    float m = max(2.0, floor(uMirrors + 0.5)), seg = 2.0 * PI / m;
    float r = length(uv), a = atan(uv.y, uv.x) + uSpin * 0.5;
    float af = mod(a, seg); af = min(af, seg - af);
    vec2 q = vec2(cos(af), sin(af)) * r;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 9.0));
        float orbit = 0.25 + 0.6 * h1 + 0.08 * sin(t * (0.3 + h2) + fi);
        float ang = seg * (0.15 + 0.7 * h2) + 0.15 * sin(t * 0.4 + fi * 1.7);
        vec2 c = vec2(cos(ang), sin(ang)) * orbit;
        float sz = (0.06 + 0.08 * h3) * (1.0 + 0.25 * uBassS);
        vec4 s = symbol(symIdx(i), q, c, sz, 0.4 * sin(t * 0.5 + fi) + t * 0.1 * (h1 - 0.5));
        s.rgb = hueShift(s.rgb, t * 0.1 * inten);
        col = mix(col, s.rgb * (0.9 + 0.4 * uBassS), s.a * inten * 0.92);
    }
    // frei im Bild: vier Symbole ziehen langsam vorbei
    for (int i = 0; i < 4; i++) {
        float fi = float(i) + 8.0;
        float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0));
        float ph = fract(t * (0.02 + 0.02 * h1) + h2);
        vec2 c = vec2(mix(-1.2, 1.2, ph) * (h1 < 0.5 ? 1.0 : -1.0), mix(-0.5, 0.5, h2) + 0.08 * sin(t * 0.6 + fi));
        float fade = smoothstep(0.0, 0.1, ph) * smoothstep(1.0, 0.9, ph);
        vec4 s = symbol(symIdx(i), uv, c, 0.1 + 0.05 * h2, 0.3 * sin(t * 0.3 + fi));
        col = mix(col, s.rgb, s.a * fade * inten * 0.9);
    }
    return col;
}
// Ereignisse
vec3 tripEvent(vec3 col, vec2 uv, float t, float aspect) {
    int ev = int(uEvent + 0.5);
    if (ev == 0) return col;
    float k = clamp(uEventT / max(uEventLen, 0.1), 0.0, 1.0);
    float env = smoothstep(0.0, 0.12, k) * smoothstep(1.0, 0.85, k);
    float r = length(uv);
    if (ev == 1) {                                                           // Froschkonzert: Ring aus Fröschen, Schallringe
        for (int i = 0; i < 8; i++) {
            float fi = float(i);
            float ang = fi * PI * 0.25 + t * 0.15;
            float hop = abs(sin(t * 3.0 + fi * 0.9)) * 0.06 * (0.5 + uPulse);
            vec2 c = vec2(cos(ang), sin(ang)) * (0.55 + hop);
            vec4 s = symbol(uEvSym[i % 4], uv, c, 0.1, -ang + PI * 0.5);
            col = mix(col, s.rgb, s.a * env);
        }
        float ripple = pow(0.5 + 0.5 * sin(r * 25.0 - uEventT * 6.0), 8.0) * exp(-r * 1.2) * (0.3 + uPulse);
        col += vec3(0.5, 1.0, 0.6) * ripple * env * 0.6;
    } else if (ev == 2) {                                                    // Pilzregen
        for (int i = 0; i < 14; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, uEventSeed * 40.0)), h2 = hash12(vec2(fi, 7.0 + uEventSeed));
            float y = 0.7 - mod(uEventT * (0.12 + 0.1 * h2) + h1 * 1.5, 1.6);
            vec2 c = vec2((h1 - 0.5) * 2.2 * aspect * 0.5, y);
            vec4 s = symbol(uEvSym[i % 4], uv, c, 0.05 + 0.05 * h2, sin(uEventT + fi) * 0.4);
            col = mix(col, s.rgb, s.a * env);
        }
    } else if (ev == 3) {                                                    // Augen öffnen sich: groß, blinzeln
        for (int i = 0; i < 5; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 11.0 + uEventSeed)), h2 = hash12(vec2(fi, 13.0));
            vec2 c = vec2((h1 - 0.5) * 1.5 * aspect * 0.5, (h2 - 0.5) * 0.9);
            float open = smoothstep(0.0, 1.0, (uEventT - fi * 1.2) / 2.0);
            float blink = 1.0 - 0.9 * pow(abs(sin(uEventT * 0.9 + fi * 2.0)), 40.0);
            vec4 s = symbol(uEvSym[i % 4], uv, c, 0.18 * open, 0.0);
            vec2 d = (uv - c);
            float lid = step(abs(d.y), 0.18 * open * blink);
            col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * env * open * lid);
        }
    } else if (ev == 4) {                                                    // Schmetterlingsschwarm
        for (int i = 0; i < 16; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 17.0 + uEventSeed)), h2 = hash12(vec2(fi, 19.0));
            float ph = fract(uEventT * (0.08 + 0.06 * h2) + h1);
            vec2 c = vec2(mix(-1.3, 1.3, ph), (h2 - 0.5) * 1.0 + 0.1 * sin(uEventT * 5.0 + fi));
            float flap = 0.75 + 0.25 * sin(uEventT * 14.0 + fi * 2.0);
            vec4 s = symbol(uEvSym[i % 4], uv, c, 0.07 * (0.6 + 0.6 * h1), 0.2 * sin(uEventT * 2.0 + fi));
            col = mix(col, s.rgb * flap, s.a * env);
        }
    } else if (ev == 5) {                                                    // Pollensturm: Kugeln strahlen aus der Mitte
        for (int i = 0; i < 20; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 23.0 + uEventSeed)), h2 = hash12(vec2(fi, 29.0));
            float ang = h1 * 2.0 * PI + uEventT * 0.3;
            float rad = mod(uEventT * (0.15 + 0.2 * h2) + h2, 1.3);
            vec2 c = vec2(cos(ang), sin(ang)) * rad;
            vec4 s = symbol(uEvSym[i % 3], uv, c, 0.03 + 0.05 * rad, uEventT * (h1 - 0.5));
            col = mix(col, s.rgb, s.a * env * (1.0 - rad / 1.3));
        }
        col += palMix(t * 0.2) * exp(-r * 2.0) * env * (0.3 + 0.6 * uPulse);
    } else if (ev == 6) {                                                    // Lichthirsch: Geweih groß, Strahlen
        float ang = atan(uv.y, uv.x);
        float rays = pow(0.5 + 0.5 * sin(ang * 12.0 + uEventT * 0.8), 8.0) * exp(-r * 1.5);
        col += vec3(1.0, 0.95, 0.7) * rays * env * 0.5;
        vec4 s = symbol(uEvSym[0], uv, vec2(0.0, -0.05), 0.55 + 0.03 * sin(uEventT * 2.0), 0.0);
        col = mix(col, s.rgb + vec3(0.3, 0.25, 0.1) * uBassS, s.a * env);
        col += vec3(1.0, 0.9, 0.6) * s.a * env * 0.3 * (0.5 + 0.5 * sin(uEventT * 3.0));
    } else if (ev == 8) {                                                    // Wurzeln wachsen von außen durch dich hindurch
        float grow = smoothstep(0.0, 0.45, k);                                 // Länge der Wurzeln
        float pull = smoothstep(0.5, 0.9, k);                                  // dann ziehen sie durch die Mitte
        float n = 6.0;
        for (int i = 0; i < 6; i++) {
            float fi = float(i);
            float ang = fi * 2.0 * PI / n + uEventSeed * 6.28 + 0.15 * sin(t * 0.3 + fi) + pull * 0.6 * sin(t * 0.8 + fi);
            vec2 d = rot(-ang) * uv;                                           // Wurzel läuft entlang +x von außen (1.3) zur Mitte
            float along = 1.0 - (d.x + 0.1) / 1.4;                             // 0 am Rand, 1 in der Mitte
            if (d.x < -0.1 || d.x > 1.35) continue;
            float reach = grow * (0.85 + 0.15 * hash12(vec2(fi, 2.0))) + pull * 0.3;
            if (along > reach) continue;
            float wob = 0.03 * sin(d.x * 9.0 + t * 1.5 + fi) + 0.015 * sin(d.x * 23.0 - t * 2.0);
            float thick = (uRootOK > 0.5 ? 0.11 - 0.06 * along : 0.07 - 0.05 * along) * (1.0 + 0.3 * uBassS);
            float dist = abs(d.y - wob);
            float body, glowv;
            if (uRootOK > 0.5) {
                vec2 rc = vec2(clamp(along / max(reach, 0.05), 0.0, 1.0), clamp((d.y - wob) / (thick * 2.6) + 0.5, 0.0, 1.0));   // dickes Ende am Rand, Spitze wächst voran
                vec4 rs = bilin(uRootTex, rc * uRootSize, uRootSize, vec2(0.0), uRootSize - 1.0);
                body = rs.a * step(dist, thick);
                col = mix(col, rs.rgb * (0.6 + 0.4 * uPulse), body * env);
            } else {
                body = smoothstep(thick, thick * 0.6, dist);
                vec3 bark = vec3(0.25, 0.16, 0.08) * (0.7 + 0.5 * noise(vec2(d.x * 30.0, d.y * 60.0)));
                col = mix(col, bark, body * env);
            }
            glowv = smoothstep(thick * 1.5, thick * 0.9, dist) * (0.5 + 0.5 * sin(along * 20.0 - t * 4.0 - uEventT * 2.0));
            col += palMix(along + t * 0.1) * glowv * env * (0.3 + 0.7 * uBassS);
        }
        // in der Mitte verknoten sie sich: Sog
        col = mix(col, col * 0.6 + palMix(t * 0.2) * 0.4, pull * env * exp(-r * 4.0));
    } else if (ev == 9 && uGodOK > 0.5) {                                    // Waldgott: Gesicht aus der Mitte, atmet, löst sich auf
        float g = floor(uEventSeed * 6.0);
        vec2 lo = vec2(mod(g, 3.0) * 512.0, (1.0 - floor(g / 3.0)) * 512.0);
        float appear = smoothstep(0.0, 0.3, k);
        float gone = smoothstep(0.82, 1.0, k);
        float sc = mix(0.3, 0.8, appear) * (1.0 + 0.04 * uBassS + 0.02 * uPulse);
        vec2 d = uv / sc;
        d.x += 0.02 * sin(d.y * 5.0 + uEventT * 1.1) * appear;
        d.y += 0.015 * sin(d.x * 4.0 - uEventT * 0.9) * appear;
        vec2 q = d * 0.5 + 0.5;
        if (q.x > 0.0 && q.x < 1.0 && q.y > 0.0 && q.y < 1.0) {
            vec4 s = bilin(uGodTex, lo + q * 512.0, uGodSize, lo, lo + 511.0);
            float dissolve = step(gone, noise(q * 40.0 + uEventSeed * 10.0));
            vec3 fc = s.rgb * (0.85 + 0.3 * uBassS);
            fc = mix(fc, hueShift(fc, sin(uEventT * 0.7) * 0.8), 0.35);
            col = mix(col, fc, s.a * appear * dissolve * 0.95);
            col += fc * s.a * appear * 0.25 * uPulse;                         // flackert mit dem Beat
        }
        // Lichtkranz und Strahlen hinter dem Gesicht
        float ang = atan(uv.y, uv.x);
        float rays = pow(0.5 + 0.5 * sin(ang * 16.0 - uEventT * 1.2), 6.0) * exp(-r * 1.2) * appear * (1.0 - gone);
        col += palMix(t * 0.1 + 0.3) * rays * 0.45 * (0.5 + 0.5 * uBassS);
        col += palMix(t * 0.15) * exp(-pow((r - 0.62 * sc) * 10.0, 2.0)) * appear * (1.0 - gone) * 0.5;
    } else if (ev == 7 && uFaceOK > 0.5) {                                   // Dein Gesicht: riesig, verzerrt, atmend
        vec2 d = uv * (1.0 - 0.06 * uBassS);
        d.x += 0.05 * sin(d.y * 6.0 + uEventT * 1.5) * env;
        d.y += 0.04 * sin(d.x * 5.0 - uEventT * 1.2) * env;
        vec2 q = d / vec2(0.9 * uFaceSize.x / uFaceSize.y, 0.9) * 0.5 + 0.5;
        if (q.x > 0.0 && q.x < 1.0 && q.y > 0.0 && q.y < 1.0) {
            vec4 s = bilin(uFaceTex, q * uFaceSize, uFaceSize, vec2(0.0), uFaceSize - 1.0);
            vec3 fc = hueShift(s.rgb, uEventT * 0.4 * env);
            col = mix(col, fc, s.a * env * 0.9);
        }
    }
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 uv = (vUv - 0.5) * vec2(aspect, 1.0);
    float t = iTime;
    int phase = int(uPhase + 0.5);
    float pt = uPhaseT;
    vec3 col = vec3(0.0);
    // ---- Tresen (browse, eat, comedown)
    float barMix = 1.0;
    if (phase == 2) barMix = 0.0;
    if (phase == 3) barMix = smoothstep(0.0, uProfile2.y, pt);
    if (barMix > 0.001) {
        vec2 bq = 0.5 + (vUv - 0.5) / 1.03 + vec2(0.004 * sin(t * 0.23), 0.003 * cos(t * 0.19));
        vec3 bar = bilin(uBarTex, clamp(bq, 0.0, 1.0) * uBarSize, uBarSize, vec2(0.0), uBarSize - 1.0).rgb;
        // Kerzen und Glühwürmchen flackern, Bass lässt das Licht atmen
        bar *= 0.92 + 0.08 * noise(vec2(t * 4.0, 1.0)) + 0.08 * uBassS;
        // Glühwürmchen schweben
        for (int i = 0; i < 10; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 37.0));
            vec2 c = vec2((h1 - 0.5) * aspect * 1.6 + 0.1 * sin(t * (0.2 + h2) + fi), 0.05 + h2 * 0.45 + 0.05 * sin(t * 0.5 + fi * 2.0));
            float g = smoothstep(0.012, 0.0, length(uv - c)) * (0.5 + 0.5 * sin(t * (2.0 + h1 * 3.0) + fi * 5.0));
            bar += vec3(1.0, 0.85, 0.4) * g * 0.8;
        }
        // Wesen auf dem Teller: gleitet beim Blättern, atmet mit dem Bass, beim Essen fliegt es auf die Kamera zu
        vec2 plate = vec2(-0.03, -0.1);
        float scale = 0.26 * (1.0 + 0.05 * uBassS + 0.02 * sin(t * 1.1));
        float alpha = 1.0;
        if (phase == 1) {
            float k = clamp(pt / uProfile2.x, 0.0, 1.0);
            scale *= 1.0 + 7.0 * pow(k, 2.2);
            plate = mix(plate, vec2(0.0, 0.0), k);
            alpha = 1.0 - smoothstep(0.85, 1.0, k);
        }
        vec2 l = (uv - plate - vec2(uSlide * 0.25, 0.0)) / scale * 0.5 + vec2(0.5, 0.0);
        vec4 w = being(uCell, l);
        // Schein des Wesens auf dem Teller
        bar += vec3(0.4, 0.9, 0.5) * exp(-length(uv - plate) * 5.0) * 0.12 * w.a;
        bar = mix(bar, w.rgb * (0.95 + 0.2 * uBassS), w.a * alpha * (1.0 - abs(uSlide) * 0.6));
        bar += w.rgb * w.a * 0.15 * uPulse;
        col = mix(col, bar, barMix);
    }
    // ---- Biss: Bildruck und Augenlider (eat), danach Schwarz
    if (phase == 1) {
        float k = clamp(pt / uProfile2.x, 0.0, 1.0);
        float lid = smoothstep(0.6, 1.0, k);                                 // Lider schließen sich
        float open = 1.0 - lid;
        float eye = smoothstep(0.0, 0.08, open * 0.6 - abs(uv.y) + 0.02 * sin(uv.x * 6.0));
        col *= eye;
        col *= 1.0 + 0.5 * exp(-pow((k - 0.45) * 12.0, 2.0));              // Biss-Blitz
    }
    // ---- Reise
    float inten = uIntensity;
    if (phase == 2 || phase == 3) {
        float tripMix = phase == 2 ? smoothstep(0.0, 2.0, pt) : 1.0 - smoothstep(0.0, uProfile2.y, pt);
        vec3 trip = tripImage(uv, uTripT, max(inten, 0.15), uVariant.x);
        if (uVariant.z < 0.999) trip = mix(tripImage(uv, uTripT, max(inten, 0.15), uVariant.y), trip, smoothstep(0.0, 1.0, uVariant.z));
        trip = tripSymbols(trip, uv, uTripT, max(inten, 0.2));
        trip = tripEvent(trip, uv, uTripT, aspect);
        // Rand atmet
        float vig = 1.0 - (0.45 + 0.2 * uBassS) * pow(length(vUv - 0.5) * 1.35, 2.5);
        trip *= vig;
        col = mix(col, trip, tripMix);
    }
    col = col / (1.0 + col * 0.2);
    fragColor = vec4(col, 1.0);
}
