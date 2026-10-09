#version 140
// F5 – Bordcomputer: gelbe Pixel-OLED-Optik. Panels mit fremder Schrift, Radar mit Sweep, Spektrum,
// Statussymbole (Kreis = bereit, Sanduhr = verarbeitet), Pegelbalken rechts, Waveform.
// Zustände (uState): 0 idle, 1 listening, 2 thinking, 3 speaking, 4 loading. uLevel: VAD-Wahrscheinlichkeit.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uState, uStateT, uLevel;

const vec3 YEL = vec3(1.0, 0.84, 0.05);
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float spec(float x) { return texture(uAudioTex, vec2(x, 0.25)).r; }
float wave(float x) { return texture(uAudioTex, vec2(x, 0.75)).r * 2.0 - 1.0; }
float rect(vec2 uv, vec2 a, vec2 b) { vec2 s = step(a, uv) * step(uv, b); return s.x * s.y; }
float frame(vec2 uv, vec2 a, vec2 b, float w) { return rect(uv, a, b) - rect(uv, a + w, b - w); }
float glyph(float id, vec2 p) {
    if (p.x < 0.0 || p.x >= 1.0 || p.y < 0.0 || p.y >= 1.0) return 0.0;
    vec2 c = floor(p * vec2(3.0, 5.0));
    float on = step(0.45, hash(vec2(id, c.x + c.y * 3.0)));
    return max(on, step(4.0, c.y) * step(0.3, hash(vec2(id, 99.0))));
}
float text(vec2 uv, vec2 pos, float n, float seed, vec2 sz) {
    vec2 p = (uv - pos) / sz;
    float i = floor(p.x / 1.4);
    if (i < 0.0 || i >= n) return 0.0;
    return glyph(seed + i, vec2(fract(p.x / 1.4) * 1.4, p.y));
}
// Rahmen mit abgeschrägter Ecke oben links (wie auf dem Gerät)
float panel(vec2 uv, vec2 a, vec2 b, float w, float cut) {
    float f = frame(uv, a, b, w);
    float corner = step(uv.x - a.x + (b.y - uv.y), cut);     // Dreieck oben links wegschneiden
    float edge = smoothstep(w, 0.0, abs((uv.x - a.x) + (b.y - uv.y) - cut)) * step(uv.x, a.x + cut) * step(b.y - cut, uv.y);
    return max(f * (1.0 - corner), edge * rect(uv, a, b));
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float rows = 160.0;                                      // grobes OLED-Raster
    vec2 uv = (floor(vUv * vec2(rows * aspect, rows)) + 0.5) / vec2(rows * aspect, rows);
    float px = 1.0 / rows;
    int st = int(uState + 0.5);
    float listening = float(st == 1), thinking = float(st == 2), speaking = float(st == 3), loading = float(st == 4);
    float live = 1.0 - uSilent;
    float on = 0.0;                                          // Pixel an/aus (monochrom)

    // ---- Linkes großes Panel: Kopfzeile Schrift, Radar, Spektrum, Symbole
    vec2 A = vec2(0.05, 0.08), B = vec2(0.66, 0.92);
    on += panel(uv, A, B, 2.0 * px, 0.06);
    on += text(uv, vec2(0.14, 0.80), 11.0, 11.0, vec2(0.016, 0.06));        // Titel in fremder Schrift
    on += rect(uv, vec2(0.08, 0.76), vec2(0.63, 0.76 + 1.5 * px));           // Linie unter dem Titel
    // Statusdoppellinie, die beim Zuhören/Verarbeiten wandert
    float bar = rect(uv, vec2(0.08, 0.70), vec2(0.08 + 0.55 * clamp(uStateT * 0.5, 0.0, 1.0) * (listening + thinking) + 0.55 * (1.0 - listening - thinking), 0.70 + 2.0 * px));
    on += bar * (0.6 + 0.4 * step(0.5, fract(iTime * 2.0)) * thinking);
    // Radar links
    {
        vec2 c = (uv - vec2(0.19, 0.42)) * vec2(aspect, 1.0) / 0.17;
        float rr = length(c);
        float ang = atan(c.y, c.x);
        on += smoothstep(2.5 * px, 0.0, abs(rr - 1.0) * 0.17) * step(0.0, 0.5 - fract(ang * 1.6));   // gestrichelter Kreis
        float sweep = fract(ang / 6.2832 - iTime * (0.2 + 0.6 * listening + 1.5 * thinking));
        on += step(0.75, 1.0 - sweep) * step(rr, 1.0) * 0.5 * step(0.5, fract((rr * 8.0)));
        // Blip = Pegel (Mikrofon beim Zuhören, Stimme beim Sprechen)
        float lvl = listening * uLevel + speaking * uRms + loading * 0.3;
        on += smoothstep(0.1, 0.0, length(c - vec2(0.3, 0.35) * (0.4 + lvl))) * step(0.2, lvl);
        on += smoothstep(0.05, 0.0, rr);
    }
    // Spektrum in der Mitte: 20 Balken
    {
        vec2 q = (uv - vec2(0.36, 0.36)) / vec2(0.18, 0.16);
        if (q.x >= 0.0 && q.x < 1.0 && q.y >= 0.0 && q.y < 1.0) {
            float i = floor(q.x * 20.0);
            float h = spec((i + 0.5) / 20.0) * (0.6 + 0.4 * live);
            h = max(h, 0.06 + 0.04 * sin(iTime * 2.0 + i));
            on += step(fract(q.x * 20.0), 0.7) * step(q.y, h);
        }
    }
    // Symbole: Kreis (bereit) und Sanduhr (verarbeitet) / Lautsprecher-Dreieck (spricht)
    {
        vec2 c = (uv - vec2(0.45, 0.22)) * vec2(aspect, 1.0) / 0.05;
        float ring = smoothstep(0.25, 0.1, abs(length(c) - 1.0));
        on += ring * (1.0 - thinking * step(0.5, fract(iTime * 3.0)));
        vec2 h = (uv - vec2(0.56, 0.22)) * vec2(aspect, 1.0) / 0.05;
        float hour = step(abs(h.x), 1.0 - abs(h.y) * 0.9) * step(abs(h.y), 1.0) * step(0.15, abs(h.y));
        float fill = step(abs(h.x), (1.0 - abs(h.y) * 0.9) * 0.9);
        // Sanduhr: oben läuft leer, unten füllt sich (nur beim Verarbeiten animiert)
        float ph = thinking * fract(uStateT * 0.7) + speaking * 1.0;
        float sand = fill * ((step(h.y, 0.0) * step(-1.0 + ph * 0.9, h.y)) + (step(0.0, h.y) * step(h.y, 1.0 - ph * 0.9) * (1.0 - speaking)));
        on += max(hour - fill, sand);
        // Dreieck beim Sprechen
        vec2 t = (uv - vec2(0.56, 0.22)) * vec2(aspect, 1.0) / 0.05;
        on += speaking * step(abs(t.y), (1.0 - t.x) * 0.6) * step(-0.8, t.x) * step(t.x, 1.0) * step(0.5, fract(iTime * 4.0 + uRms));
    }
    // Waveform unten im Panel
    {
        vec2 q = (uv - vec2(0.08, 0.10)) / vec2(0.55, 0.08);
        if (q.x >= 0.0 && q.x < 1.0 && q.y >= 0.0 && q.y < 1.0) {
            float y0 = 0.5 + wave(q.x) * 0.45 * (0.2 + 0.8 * (listening + speaking) + 0.3 * live);
            on += smoothstep(2.0 * px, 0.0, abs(q.y - y0) * 0.08);
        }
    }

    // ---- Schmaler senkrechter Balken (Thermometer): VAD-Pegel bzw. Stimme
    vec2 T0 = vec2(0.69, 0.08), T1 = vec2(0.74, 0.92);
    on += frame(uv, T0, T1, 2.0 * px);
    {
        float lvl = listening * uLevel + speaking * uRms + thinking * (0.5 + 0.5 * sin(iTime * 6.0)) + loading * fract(iTime * 0.5);
        lvl = max(lvl, 0.05);
        vec2 q = (uv - T0) / (T1 - T0);
        on += step(0.2, q.x) * step(q.x, 0.8) * step(q.y, lvl) * step(0.25, fract(q.y * 24.0)) * step(0.02, q.y);
    }

    // ---- Rechts: sechs breite Balken (Bänder und Zustand)
    for (int k = 0; k < 6; k++) {
        float y = 0.84 - float(k) * 0.13;
        float lvl;
        if (k == 0) lvl = uBass; else if (k == 1) lvl = uMid; else if (k == 2) lvl = uHigh;
        else if (k == 3) lvl = uRms; else if (k == 4) lvl = listening * uLevel + speaking; else lvl = thinking * step(0.5, fract(iTime * 2.0)) + loading * step(0.5, fract(iTime * 1.0));
        lvl = max(lvl * live + (k >= 4 ? lvl : 0.0), 0.08);
        float w = 0.20 * lvl;
        on += rect(uv, vec2(0.78, y - 0.045), vec2(0.78 + w, y + 0.045)) * step(0.3, fract((uv.y - y) * 40.0));
        on += frame(uv, vec2(0.78, y - 0.045), vec2(0.98, y + 0.045), 1.0 * px) * 0.35;
    }
    // Zustandszeile unten rechts in fremder Schrift (anderer Text je Zustand)
    on += text(uv, vec2(0.78, 0.945), 9.0, 100.0 + uState * 10.0, vec2(0.011, 0.03));

    // ---- Monochrom gelb, Beat-Blitz, Pixelraster, leichte Vignette
    on = clamp(on, 0.0, 1.0);
    vec3 col = YEL * on * (0.85 + 0.15 * step(0.5, fract(iTime * 60.0)) * 0.3);
    col += YEL * 0.04;                                           // Grundleuchten des Panels
    col *= 1.0 + 0.3 * uBeat * speaking;
    vec2 sub = fract(vUv * vec2(rows * aspect, rows));
    col *= 0.75 + 0.25 * step(0.12, sub.x) * step(0.12, sub.y);  // Pixelgitter
    col *= 1.0 - 0.35 * smoothstep(0.8, 1.6, length(vUv * 2.0 - 1.0));
    fragColor = vec4(col, 1.0);
}
