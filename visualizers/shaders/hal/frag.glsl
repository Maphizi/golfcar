#version 140
// HAL 3000: Korridor aus roten Speicherbänken in Perspektive (Wände, Decke, Boden), deren Lichtzellen
// mit dem Spektrum leuchten; in der Mitte die schwarze Konsole mit Chromring und rotem Auge:
// Linse mit Tiefe, Lichtbögen, glühender Kern, der mit der Stimme pulst.
// uState 0 bereit, 1 hört, 2 denkt, 3 spricht, 4 lädt. uLevel VAD, uTalk 1 beim Sprechen, uBright Blende.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uState, uStateT, uLevel, uTalk, uBright, uVoice, uTalkMode;
// uRms/uBass/uMid/uHigh/uBeat: die Musik (Quelle playback). uVoice: Pegel von HALs eigener Stimme.

vec3 hueShift(vec3 c, float a) {
    const vec3 k = vec3(0.57735);
    float cs = cos(a), sn = sin(a);
    return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs);
}

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
// Fremde Schriftzeichen: 3x5-Muster aus einem Hash
float glyph(float id, vec2 l) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return 0.0;
    vec2 c = floor(l * vec2(3.0, 5.0));
    return step(0.45, hash12(vec2(id, c.x + c.y * 3.0)));
}
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
float sdBox(vec2 p, vec2 b, float r) { vec2 d = abs(p) - b + r; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r; }

// Speicherbank-Zellen auf einer Wandfläche: w = Koordinate entlang des Korridors (Tiefe), h = Höhe/Breite
vec3 bankCells(vec2 wq, float depth, float t, float live, float side) {
    vec2 g = vec2(wq.x * 14.0, wq.y * 7.0);
    vec2 cell = floor(g);
    vec2 f = fract(g) - 0.5;
    float on = smoothstep(0.42, 0.36, abs(f.x)) * smoothstep(0.34, 0.26, abs(f.y));
    // Spektrum: Position entlang der Tiefe = Frequenz, dazu Wellen, die mit der Musik durch die Wand laufen
    float band = spec(fract(cell.x * 0.07 + side * 0.3));
    float wave = 0.5 + 0.5 * sin(wq.x * 1.5 - t * (1.5 + 3.0 * uBass * live) + wq.y * 0.8);
    float slow = 0.55 + 0.45 * sin(t * 0.8 + hash12(cell) * 6.28);
    float lit = mix(slow * 0.55, 0.25 + 1.3 * band + 0.5 * wave * uMid, live);
    lit += uBeat * live * step(0.8, hash12(cell + floor(t * 6.0)));
    float dark = step(0.93, hash12(cell + 3.0));                       // einzelne tote Zellen
    // Farbe: hauptsächlich rot, driftet langsam nach Orange und Magenta, Höhen färben kühler
    vec3 red = hueShift(vec3(1.0, 0.08, 0.05), (0.08 + 0.22 * live) * sin(t * 0.13 + wq.x * 0.2) + 0.3 * uHigh * live);
    vec3 c = red * on * lit * (1.0 - dark * 0.85);
    c += red * 0.18 * (1.0 - on) * lit * 0.5;                            // Schein zwischen den Zellen
    // Fremde Zeichen: in manchen Fenstern der Wand erscheinen weiße Glyphen und verschwinden wieder
    vec2 win = floor(vec2(wq.x * 1.4, wq.y * 1.0));
    float showT = floor(t * 0.5 + hash12(win) * 7.0);
    float show = step(0.86, hash12(win + showT)) * smoothstep(0.0, 0.2, fract(t * 0.5 + hash12(win) * 7.0)) * smoothstep(1.0, 0.7, fract(t * 0.5 + hash12(win) * 7.0));
    vec2 wl = fract(vec2(wq.x * 1.4, wq.y * 1.0));
    float gl = 0.0;
    for (int k = 0; k < 3; k++) {
        gl += glyph(hash12(win + float(k) * 11.0 + showT) * 99.0, (wl - vec2(0.1 + float(k) * 0.28, 0.25)) / vec2(0.2, 0.5));
    }
    c += vec3(1.0, 0.95, 0.9) * gl * show * (0.7 + 0.6 * uMid * live);
    // Weiße Lichter: Streifen, die beim Beat durch die Wand nach vorn schießen
    float streak = smoothstep(0.03, 0.0, abs(fract(wq.x * 0.5 + t * 2.5 + hash12(vec2(cell.y, side))) - 0.5)) * step(0.7, hash12(vec2(cell.y, floor(t * 2.0) + side)));
    c += vec3(1.0, 0.98, 0.95) * streak * (0.3 + 1.5 * uBeat) * live * on;
    return c * (0.35 + 0.65 * (1.0 - depth));                             // hinten dunkler
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    vec2 p = (vUv - 0.5) * vec2(aspect, 1.0);
    float t = iTime;
    float live = 1.0 - uSilent;
    int st = int(uState + 0.5);
    float talk = uTalk * (0.3 + 3.0 * uVoice);        // Auge: nur HALs Stimme, nicht die Musik
    float listening = float(st == 1), thinking = float(st == 2), loading = float(st == 4);

    // ---- Korridor: vier Flächen in Perspektive, Fluchtpunkt in der Mitte
    vec3 col = vec3(0.0);
    float ax = abs(p.x) / (aspect * 0.5), ay = abs(p.y) / 0.5;
    float wall = step(ay, ax);                                            // Seitenwand oder Decke/Boden
    float depthW = 1.0 - (0.28 / max(ax, 0.001));                         // Tiefe entlang der Wand (0 nah, 1 fern)
    float depthC = 1.0 - (0.28 / max(ay, 0.001));
    float depth = mix(depthC, depthW, wall);
    float along = depth * 6.0 - t * (0.15 + 0.9 * uBass * live);          // Fahrt durch den Korridor, Bass treibt
    // psychedelisch: die Wände atmen und drehen sich leicht mit der Musik
    along += 0.4 * sin(depth * 4.0 - t * 1.3) * uMid * live;
    vec2 wq = wall > 0.5 ? vec2(along, p.y / ax * 1.6) : vec2(along, p.x / ay * 1.6 / aspect);
    wq.y += 0.15 * sin(t * 0.4 + depth * 3.0) * uRms * live;
    float side = wall > 0.5 ? sign(p.x) : sign(p.y) + 2.0;
    float inCorr = step(0.28, max(ax, ay));
    col = bankCells(wq, clamp(depth, 0.0, 1.0), t, live, side) * inCorr;
    // Kanten der Flächen und Streben
    float edge = smoothstep(0.015, 0.0, abs(ax - ay)) * inCorr;
    col = mix(col, vec3(0.08, 0.02, 0.02), edge);
    float strut = step(0.9, fract(along * 0.5)) * inCorr;
    col = mix(col, vec3(0.03, 0.01, 0.01), strut);
    // Rote Füllung der Luft, Tiefennebel; Beat lässt den ganzen Gang kurz aufleuchten
    col += vec3(0.35, 0.03, 0.02) * (0.4 + 0.5 * uBass * live + 0.3 * uBeat * live) * smoothstep(0.0, 0.5, max(ax, ay)) * inCorr;
    col += vec3(0.5, 0.45, 0.4) * uBeat * live * 0.08 * inCorr;
    col = mix(col, vec3(0.08, 0.01, 0.01), smoothstep(0.6, 1.0, depth) * inCorr);
    // ---- Rückwand (dunkel), Konsole in der Mitte
    float back = 1.0 - inCorr;
    col = mix(col, vec3(0.03, 0.0, 0.0), back);
    vec2 cq = p / 0.28;                                                   // -1..1 über die Rückwand
    float panel = step(sdBox(p, vec2(0.14, 0.27), 0.015), 0.0);
    vec3 pcol = vec3(0.02, 0.02, 0.025);
    // feine Rillen und Schraubenpunkte auf der Konsole
    pcol += vec3(0.03) * step(0.5, fract(p.y * 80.0)) * step(0.11, abs(p.x));
    col = mix(col, pcol, panel);
    float chromeFrame = step(sdBox(p, vec2(0.145, 0.275), 0.018), 0.0) - panel;
    col = mix(col, vec3(0.55, 0.57, 0.6) * (0.6 + 0.6 * smoothstep(-0.3, 0.3, p.y)), chromeFrame);
    // Lautsprechergitter unten
    vec2 gq = p - vec2(0.0, -0.2);
    float grille = step(sdBox(gq, vec2(0.12, 0.05), 0.01), 0.0);
    float holes = smoothstep(0.35, 0.25, length(fract(gq * 140.0) - 0.5));
    col = mix(col, mix(vec3(0.3, 0.3, 0.32), vec3(0.05), holes), grille);
    // Namensschild oben (Text per Overlay), hier nur der Kasten
    float plate = step(sdBox(p - vec2(0.0, 0.215), vec2(0.1, 0.022), 0.004), 0.0);
    col = mix(col, vec3(0.04, 0.04, 0.05), plate);
    col += vec3(0.5, 0.55, 0.6) * (step(sdBox(p - vec2(0.0, 0.215), vec2(0.103, 0.025), 0.005), 0.0) - plate);

    // ---- Das Auge: Chromring, schwarze Fassung, Linse, Kern
    vec2 e = p - vec2(0.0, 0.02);
    float r = length(e);
    float R = 0.115;
    float ringOuter = smoothstep(R * 1.32, R * 1.3, r) * (1.0 - smoothstep(R * 1.02, R * 1.0, r));
    float ang = atan(e.y, e.x);
    vec3 chrome = mix(vec3(0.25), vec3(0.95), 0.5 + 0.5 * sin(ang * 1.0 + 1.0)) * (0.5 + 0.5 * smoothstep(-1.0, 1.0, e.y / R));
    chrome *= 0.8 + 0.2 * sin(r * 400.0);                                  // Drehrillen
    col = mix(col, chrome, ringOuter);
    if (r < R) {
        float rr = r / R;
        // Linse: tief dunkelrot außen, heller zur Mitte, mit leichter Textur
        float breathe = 0.85 + 0.15 * sin(t * 0.7);
        vec3 lens = mix(vec3(0.55, 0.0, 0.0), vec3(0.08, 0.0, 0.0), smoothstep(0.1, 0.95, rr));
        lens += vec3(0.35, 0.02, 0.0) * noise(e * 60.0 + t * 0.2) * (1.0 - rr) * 0.5;
        // Kern: gelboranger Punkt, pulst mit Stimme und Zustand
        float core = 0.07 + 0.04 * talk + 0.03 * listening * uLevel + 0.02 * sin(t * 2.0) * thinking;
        float k = smoothstep(core * 1.6, core * 0.4, rr);
        vec3 kcol = mix(vec3(1.0, 0.55, 0.1), vec3(1.0, 0.95, 0.7), smoothstep(core, 0.0, rr));
        lens = mix(lens, kcol, k);
        lens += vec3(1.0, 0.4, 0.1) * smoothstep(0.5, 0.0, rr) * (0.25 + 0.5 * talk + 0.3 * listening * uLevel) * breathe;
        // Lichtbögen (Reflexe der Decke), drei konzentrische Segmente oben
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            float ra = 0.58 + fi * 0.13;
            float arc = smoothstep(0.03, 0.015, abs(rr - ra)) * step(0.0, e.y) * step(abs(ang - 1.5708), 0.9 - fi * 0.2);
            float gaps = step(0.25, fract(ang * 4.0 + fi * 0.3));
            lens += vec3(0.95, 0.9, 0.9) * arc * gaps * 0.8;
        }
        // Denken: eine Markierung wandert um den Kern
        float mark = thinking * smoothstep(0.03, 0.0, abs(rr - 0.35)) * smoothstep(0.3, 0.0, abs(atan(sin(ang - t * 3.0), cos(ang - t * 3.0))));
        lens += vec3(1.0, 0.7, 0.4) * mark;
        // Glanzpunkt oben links
        lens += vec3(1.0) * smoothstep(0.05, 0.0, length(e - vec2(-0.04, 0.05)) / R) * 0.6;
        // Vignette im Glas
        lens *= 1.0 - 0.5 * pow(rr, 4.0);
        col = lens * (1.0 - loading * 0.6);
    }
    // Sprechmodus: schmaler weißer Rahmen um das Auge, pulsierend mit dem Mikrofonpegel
    col += vec3(0.9, 0.9, 1.0) * uTalkMode * smoothstep(0.006, 0.0, abs(r - R * 1.42)) * (0.3 + 0.7 * uLevel);
    // Schein des Auges auf Konsole und Korridor
    col += vec3(1.0, 0.25, 0.08) * exp(-r * 12.0) * (0.15 + 0.45 * talk + 0.2 * listening * uLevel) * (1.0 - step(r, R));
    // Laden: Scanlinie
    col = mix(col, col * 0.5 + vec3(0.3, 0.05, 0.02) * step(abs(vUv.y - fract(t * 0.5)), 0.01), loading);
    col *= uBright;
    col *= 1.0 - 0.35 * pow(length(vUv - 0.5) * 1.3, 2.0);
    fragColor = vec4(col, 1.0);
}
