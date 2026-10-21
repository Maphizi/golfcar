#version 140
// Der Pilzautomat: Baumstumpf-Foto (uSceneTex) mit drei Fenstern (uWin0..2 x-Bereich, uWinY y-Bereich), in denen die
// Walzen drehen (Streifen im Atlas uSpriteTex wie bei der Space-Slotmaschine: Zeile 0 = 9 Symbole à uTile, Streifen
// ab uStripRow). Leuchtende Pilze im Foto (warm/türkis) pulsieren mit dem Bass, Beats glimmen im Moos, Höhen funkeln
// als Glühwürmchen, Drops: Sporen (uSporeT) + Farbwelle (uFlash). Gewinne: uWin 1 Glühwürmchen aus den Fenstern,
// 2 Blätter/Pollen + Fuchs (uFigTex), 3/4 Lichthirsch (Symbol 8) galoppiert, der Wald leuchtet auf.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSpriteTex, uSceneTex, uFigTex;
uniform vec2 uAtlasSize, uSceneSize, uFigSize, uTile, uWin0, uWin1, uWin2, uWinY;
uniform float uTheme, uState, uStateT, uWin, uWinMask, uWinLine, uFade, uStripRow;
uniform vec3 uColA, uColB, uReel, uSpeed, uBlur;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uFlash, uSporeT, uStake, uStakeT;
uniform vec4 uFox;                                       // Zelle A, Zelle B, Mischung
uniform float uStep, uStepPhase;                         // Beat-Lauflicht durch die Pilzgruppen 0..2
uniform vec3 uStopT;                                     // Sekunden seit dem Stopp jeder Walze
const float PI = 3.14159265;
const float STRIP = 32.0;
const float CELL = 0.333;                                // Fensterhöhe = 3 Zellen

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
vec3 hueShift(vec3 c, float a) { const vec3 k = vec3(0.57735); float cs = cos(a), sn = sin(a); return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs); }
vec4 bilin(sampler2D tex, vec2 px, vec2 size, vec2 lo, vec2 hi) {
    vec2 p = clamp(px - 0.5, lo, hi);
    vec2 i = floor(p), f = fract(p);
    vec2 i1 = min(i + 1.0, hi);
    vec4 a = texture(tex, (i + 0.5) / size), b = texture(tex, (vec2(i1.x, i.y) + 0.5) / size);
    vec4 c = texture(tex, (vec2(i.x, i1.y) + 0.5) / size), d = texture(tex, (i1 + 0.5) / size);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
vec3 scene(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0).rgb; }
// Leuchtmaske: helle, gesättigte Stellen im Foto (Pilze, Lichter) unterhalb des Stumpfrandes
float glowAt(vec2 uv) {
    vec3 c = scene(uv);
    float lum = max(c.r, max(c.g, c.b));
    float sat = lum - min(c.r, min(c.g, c.b));
    return smoothstep(0.32, 0.65, lum) * smoothstep(0.12, 0.35, sat) * smoothstep(0.8, 0.5, uv.y);
}
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (3.0 - ri) * 192.0);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
}
float stripSymbol(float reel, float k) {
    float kk = mod(k, STRIP);
    return floor(texture(uSpriteTex, vec2((kk + 0.5) / uAtlasSize.x, (uStripRow + reel + 0.5) / uAtlasSize.y)).r * 255.0 + 0.5);
}
// Symbol idx, l in 0..1 über die Kachel (3:2), Alpha aus dem Bogen (Schwarz = frei)
vec4 sprite(float idx, vec2 l) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return vec4(0.0);
    vec2 base = vec2(idx * uTile.x, 0.0);
    return bilin(uSpriteTex, base + l * uTile, uAtlasSize, base, base + uTile - 1.0);
}
vec2 winX(int i) { return i == 0 ? uWin0 : (i == 1 ? uWin1 : uWin2); }

// Walze i im Fenster: q.x 0..1 über die Fensterbreite, q.y 0..1 über die Fensterhöhe (3 Zellen, Mitte = Gewinnlinie)
vec3 drum(int i, vec2 q, float winAspect) {
    float reel = float(i);
    float pos = uReel[i];
    float yn = clamp((q.y - 0.5) * 2.0, -0.999, 0.999);
    float ang = asin(yn);                                   // Trommel
    float yc = ang / (PI * 0.5) * 0.5 * 1.45;
    float k = floor(pos + yc / CELL + 0.5);
    float ly = (yc - (k - pos) * CELL) / CELL + 0.5;
    // Trommelband: feuchtes Holz, dunkel, mit Maserung
    float grainN = fbm(vec2(q.x * 3.0 + reel, yc * 14.0 + k * 0.0 + uSeed));
    vec3 wood = mix(vec3(0.10, 0.06, 0.03), vec3(0.22, 0.14, 0.07), grainN);
    wood *= 0.8 + 0.4 * noise(vec2(q.x * 200.0, yc * 300.0));
    // Symbol: 3:2 in die Zelle einpassen (Fensterbreite ist die Grenze)
    vec2 l = vec2(q.x, ly);
    float symW = 1.0, symH = symW / (1.5 * winAspect);      // Kachelhöhe in Zellenanteilen (winAspect = Zelle/Breite)
    vec2 sl = (l - vec2(0.5, 0.5)) / vec2(symW, min(0.94, symH)) + 0.5;
    float idx = stripSymbol(reel, k);
    vec4 s = sprite(idx, sl);
    vec3 col = mix(wood, s.rgb, s.a);
    // Glühen des Symbols im Dunkeln (Jackpot-Hirsch stärker), auf der Gewinnlinie mit dem Beat
    float onLine = smoothstep(0.35, 0.0, abs(q.y - 0.5)) ;
    float glow = (idx == 8.0 ? 0.5 : 0.25) + 0.35 * uBeatPulse * onLine;
    col += s.rgb * s.a * glow * uLive;
    float sep = smoothstep(0.03, 0.0, min(ly, 1.0 - ly));
    col *= 1.0 - 0.3 * sep;
    // Licht: Mondlicht von oben, Trommelabschattung, Fenster-Innenlicht (warm, pulst beim Drehen)
    float diffuse = 0.55 + 0.45 * pow(max(cos(ang), 0.0), 0.6);
    col *= diffuse;
    col *= 1.0 - 0.4 * smoothstep(0.4, 0.5, abs(q.x - 0.5));
    float spin = clamp(uSpeed[i] / 8.0, 0.0, 1.0);
    col += vec3(1.0, 0.7, 0.3) * 0.08 * spin * (0.6 + 0.4 * sin(iTime * 20.0 + reel));
    // Bewegungsunschärfe als Helligkeitsstreifen
    col = mix(col, col * (0.7 + 0.6 * noise(vec2(q.x * 10.0, yc * 60.0 - iTime * 40.0))), uBlur[i] * 0.5);
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    vec2 uv = vUv;
    // Kamera: näher am Automaten, atmet mit dem Bass, ruckt auf den Beat, Jackpot wackelt
    vec2 center = vec2(0.5, 0.47);
    uv = center + (uv - center) / 1.28;
    uv = center + (uv - center) * (1.0 - 0.025 * uBassS - 0.01 * uBeatPulse);
    uv.y -= 0.003 * uBeatPulse;
    float resultT = uState == 2.0 ? uStateT : -1.0;
    float big = (uWin >= 2.0 && resultT >= 0.0) ? 1.0 : 0.0;
    float jackpot = (uWin >= 3.0 && resultT >= 0.0) ? 1.0 : 0.0;
    uv += vec2(0.003, 0.002) * jackpot * sin(t * 30.0) * exp(-resultT * 0.6);
    vec3 plate = scene(uv);
    vec3 col = plate;
    // ---- Pilz-Lichtshow: Pilze und Lichter im Foto leuchten mit dem Bass, Lauflicht durch die drei Gruppen auf den
    //      Beat, Bloom-Schein drumherum, Farbwelle beim Drop, Gewinne lassen sie in Wellen laufen
    float lum = max(plate.r, max(plate.g, plate.b));
    float glowMask = glowAt(uv);
    float bloom = 0.0;                                                        // weicher Schein: Nachbarn abtasten
    for (int k = 0; k < 8; k++) {
        float a = float(k) * PI * 0.25;
        bloom += glowAt(uv + vec2(cos(a) / aspect, sin(a)) * 0.038);
    }
    bloom = bloom / 8.0;
    float zone = uv.x < 0.36 ? 0.0 : (uv.x < 0.64 ? 1.0 : 2.0);               // Pilzgruppen links, Mitte, rechts
    float run = (zone == uStep ? 1.0 : 0.0) * (1.0 - 0.6 * uStepPhase);
    float offZone = (zone == uStep ? 0.0 : 1.0) * uLive * 0.5;                   // die anderen Gruppen treten zurück
    vec3 glowCol = plate / max(lum, 0.2);                                       // Eigenfarbe des Pilzes, voll gesättigt
    if (uFlash > 0.0) {
        float wave = exp(-pow((uv.x - (1.0 - uFlash) * 1.6 + 0.3) * 6.0, 2.0));
        glowCol = mix(glowCol, hueShift(glowCol, 2.0 + uv.x * 3.0), wave * uFlash);
    }
    float stakeGlow = 0.2 + 0.4 * uStake;
    float breathe = 0.5 + 0.5 * sin(t * 1.2 + uv.x * 4.0);                     // ruhiges Atmen, wenn die Musik leise ist
    float drive = 0.15 * breathe + 1.0 * uBassS + 0.5 * uBeatPulse + 2.0 * run * uLive + stakeGlow * 0.3
                + 1.5 * big * (0.5 + 0.5 * sin(t * 6.0 - uv.x * 12.0)) + 0.4 * uHighS * noise(uv * 80.0 + t * 5.0);
    glowCol = mix(glowCol, hueShift(glowCol, uStep * 2.1 + t * 0.6), run * 0.6);   // Lauflicht färbt die Gruppe um
    // Pilze liegen ohne Musik gedimmt da und flammen mit Bass und Beat auf (deutlicher Hub)
    col = mix(col, col * 0.35, glowMask * uLive * (1.0 - clamp(drive, 0.0, 1.0)));
    col = mix(col, col * 0.5, glowMask * offZone * (0.5 + 0.5 * uBassS));
    col += glowCol * glowMask * drive * (0.4 + 0.8 * uLive);
    col += glowCol * bloom * drive * 1.1 * (0.3 + 0.7 * uLive);                 // Schein auf Moos und Boden
    col = mix(col, col * vec3(0.8, 0.9, 1.1), (1.0 - uLive) * 0.4);
    // Moos glimmt mit dem Beat (dunkle grüne Stellen)
    float moss = smoothstep(0.08, 0.0, abs(plate.g - 0.3)) * smoothstep(0.1, 0.0, plate.r - plate.g * 0.6) * smoothstep(0.75, 0.3, uv.y);
    col += vec3(0.3, 0.9, 0.4) * moss * (0.08 * uBeatPulse + 0.04 * uMidS + 0.5 * jackpot * exp(-resultT * 0.5));
    // ---- Fenster: Walzen
    float wh = uWinY.y - uWinY.x;
    for (int i = 0; i < 3; i++) {
        vec2 wx = winX(i);
        vec2 q = vec2((uv.x - wx.x) / (wx.y - wx.x), (uv.y - uWinY.x) / wh);
        if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) continue;
        float ww = (wx.y - wx.x) * aspect;                    // Fensterbreite isotrop
        float winAspect = wh / 3.0 / ww;                        // Zellenhöhe / Fensterbreite
        vec3 d = drum(i, q, winAspect);
        // Rand des Fensters: Schatten der Holzkante
        float edge = min(min(q.x, 1.0 - q.x) * 6.0, min(q.y, 1.0 - q.y) * 5.0);
        d *= 0.4 + 0.6 * smoothstep(0.0, 0.5, edge);
        // Gewinnwalze leuchtet, Gewinnlinie als Lichtstreifen
        float mask = mod(floor(uWinMask / pow(2.0, float(i))), 2.0);
        if (uWin > 0.0 && resultT >= 0.0 && mask > 0.5) {
            float line = 0.5;
            if (uWinLine == 1.0) line = 0.5 + (1.0 - float(i)) * CELL;   // ↘: links oben, rechts unten
            if (uWinLine == 2.0) line = 0.5 + (float(i) - 1.0) * CELL;
            float ll = exp(-pow((q.y - line) * 9.0, 2.0));
            d += vec3(0.6, 1.0, 0.7) * ll * (0.25 + 0.25 * sin(t * 8.0)) * (uWin >= 2.0 ? 1.4 : 0.7);
        }
        col = mix(col, d, 0.98);
    }
    // ---- Staubwölkchen, wenn eine Walze einrastet; Hebelknauf glüht beim Drehen
    for (int i = 0; i < 3; i++) {
        float st = uStopT[i];
        if (st < 0.0 || st > 1.2) continue;
        vec2 wx = winX(i);
        vec2 c = vec2((wx.x + wx.y) * 0.5, uWinY.x - 0.01);
        vec2 d = (uv - c) * vec2(aspect, 1.0);
        float puff = smoothstep(0.08 * st + 0.02, 0.0, length(d - vec2(0.0, st * 0.03))) * (1.0 - st / 1.2) * noise(d * 60.0 + st * 4.0);
        col += vec3(0.7, 0.6, 0.45) * puff * 0.8;
    }
    {
        vec2 knob = vec2(0.792, 0.875);
        float spinAll = clamp((uSpeed[0] + uSpeed[1] + uSpeed[2]) / 20.0, 0.0, 1.0);
        float kd = length((uv - knob) * vec2(aspect, 1.0));
        col += vec3(1.0, 0.75, 0.4) * exp(-kd * 35.0) * (0.3 * spinAll * (0.7 + 0.3 * sin(t * 25.0)) + 0.4 * uBeatPulse * spinAll);
    }
    // ---- Fenster-Innenlicht fällt auf die Rinde (beim Drehen warm, bei Gewinn grün)
    for (int i = 0; i < 3; i++) {
        vec2 wx = winX(i);
        vec2 c = vec2((wx.x + wx.y) * 0.5, (uWinY.x + uWinY.y) * 0.5);
        float dd = length((uv - c) * vec2(aspect, 1.0));
        float spin = clamp(uSpeed[i] / 8.0, 0.0, 1.0);
        float ins = smoothstep(0.0, 1.0, (abs(uv.x - c.x) / (wx.y - wx.x) - 0.5) * 2.0 + (abs(uv.y - c.y) / wh - 0.5) * 2.0);
        col += mix(vec3(1.0, 0.7, 0.3) * spin * 0.2, vec3(0.4, 1.0, 0.5) * big * 0.3, big) * exp(-dd * 10.0) * ins;
    }
    // ---- Gewinn klein: Glühwürmchen schwärmen aus den Fenstern
    if (uWin >= 1.0 && resultT >= 0.0) {
        int n = uWin >= 2.0 ? 40 : 18;
        for (int i = 0; i < 40; i++) {
            if (i >= n) break;
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
            vec2 wx = winX(int(mod(fi, 3.0)));
            vec2 start = vec2(mix(wx.x, wx.y, h1), mix(uWinY.x, uWinY.y, h2));
            float age = resultT - h3 * 0.8;
            if (age < 0.0) continue;
            vec2 p = start + vec2((h1 - 0.5) * 0.5 * age + 0.03 * sin(age * 3.0 + fi), age * (0.05 + 0.08 * h2) + 0.02 * sin(age * 4.0 + fi * 2.0));
            float g = smoothstep(0.006, 0.0, length((uv - p) * vec2(aspect, 1.0))) * (0.5 + 0.5 * sin(age * 8.0 + fi)) * smoothstep(6.0, 3.0, age);
            col += vec3(1.0, 0.95, 0.5) * g * 1.5;
        }
    }
    // ---- Gewinn groß: Blätter und Pollen regnen, der Fuchs tanzt links am Stumpf
    if (big > 0.0) {
        for (int i = 0; i < 30; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 13.0)), h2 = hash12(vec2(fi, 17.0)), h3 = hash12(vec2(fi, 19.0));
            float age = resultT * (0.5 + 0.5 * h3) - h2 * 1.5;
            if (age < 0.0) continue;
            vec2 p = vec2(h1 + 0.06 * sin(age * 2.0 + fi), 1.05 - age * 0.18);
            if (p.y < 0.1) continue;
            vec2 d = rot(age * 2.0 + fi) * ((uv - p) * vec2(aspect, 1.0));
            float leaf = smoothstep(0.0, -0.004, abs(d.x) * 1.6 + abs(d.y) * 0.9 - 0.012);
            vec3 lc = mix(vec3(0.9, 0.6, 0.2), vec3(0.4, 0.8, 0.3), h3);
            col = mix(col, lc * (0.7 + 0.3 * sin(fi)), leaf * 0.9);
        }
        vec2 fp = vec2(0.22, 0.30);
        fp.y += 0.012 * uBassS + 0.006 * sin(t * 6.0) * uBeatPulse;
        vec2 d = (uv - fp) * vec2(aspect, 1.0) / (0.15 * aspect * 0.5);
        d.y = d.y - 1.0 + 0.02;
        float enter = smoothstep(0.0, 0.6, resultT) * smoothstep(5.0, 4.4, resultT);
        if (abs(d.x) < 1.0 && abs(d.y) < 1.0 && enter > 0.0) {
            vec4 s = mix(figCell(uFox.x, d), figCell(uFox.y, d), uFox.z);
            col = mix(col, s.rgb * (0.8 + 0.3 * uBassS), s.a * enter);
        }
    }
    // ---- Jackpot: der Wald leuchtet auf, der Lichthirsch galoppiert von rechts nach links, Sporenfeuerwerk
    if (jackpot > 0.0) {
        col += plate * 0.8 * exp(-resultT * 0.4) * (0.6 + 0.4 * sin(t * 10.0));
        col = mix(col, hueShift(col, sin(t * 2.0) * 0.5), 0.3 * exp(-resultT * 0.3));
        float run = resultT / 6.0;
        vec2 hp = vec2(1.15 - run * 1.3, 0.56 + 0.05 * abs(sin(resultT * 6.0)));
        float hs = 0.22;
        vec2 d = (uv - hp) * vec2(aspect, 1.0) / (hs * aspect * 0.5);
        d.y = d.y * 1.5 / 1.0;                                  // 3:2-Kachel
        if (abs(d.x) < 1.0 && abs(d.y) < 1.0) {
            vec2 l = vec2(d.x, -d.y) * 0.5 + 0.5;                // Hirsch schaut nach links: Kachel spiegeln
            l.x = 1.0 - l.x;
            l.y = 1.0 - l.y;
            vec4 s = sprite(8.0, l);
            float gallop = 1.0 + 0.1 * sin(resultT * 12.0);
            col = mix(col, s.rgb * gallop + vec3(0.3, 0.2, 0.0) * s.a, s.a);
            col += s.rgb * s.a * 0.8;
        }
        // Funkenschweif hinter dem Hirsch
        for (int i = 0; i < 30; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 23.0)), h2 = hash12(vec2(fi, 29.0));
            vec2 p = hp + vec2(0.05 + h1 * 0.3, (h2 - 0.5) * 0.15 + 0.02 * sin(t * 5.0 + fi));
            float g = smoothstep(0.005, 0.0, length((uv - p) * vec2(aspect, 1.0))) * (0.5 + 0.5 * sin(t * 15.0 + fi * 3.0));
            col += vec3(1.0, 0.8, 0.3) * g * 1.5;
        }
    }
    // ---- Sporen beim Drop (und beim Jackpot) steigen vom Stumpf auf
    float sporeT = uSporeT;
    if (jackpot > 0.0 && resultT < 4.0) sporeT = max(sporeT, resultT);
    if (sporeT >= 0.0) {
        for (int i = 0; i < 36; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 11.0)), h2 = hash12(vec2(fi, 13.0)), h3 = hash12(vec2(fi, 17.0));
            float age = sporeT - h1 * 0.5;
            if (age < 0.0) continue;
            vec2 p = vec2(0.48 + (h2 - 0.5) * 0.3, 0.78) + vec2((h2 - 0.5) * 0.8 * age, age * (0.1 + 0.15 * h3) - 0.015 * age * age);
            p.x += 0.02 * sin(age * 3.0 + fi);
            float g = smoothstep(0.012 + 0.004 * h3, 0.0, length((uv - p) * vec2(aspect, 1.0))) * (1.0 - age / 4.0);
            col += hueShift(vec3(0.4, 1.0, 0.7), h3 * 1.5) * g * 1.2;
        }
    }
    // ---- Glühwürmchen und Tautropfen mit den Höhen, Nebel atmet mit den Mitten
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 33.0));
        vec2 c = vec2(h1 + 0.03 * sin(t * (0.3 + h2) + fi), 0.15 + h2 * 0.7 + 0.03 * sin(t * 0.7 + fi * 2.0));
        float g = smoothstep(0.006, 0.0, length((uv - c) * vec2(aspect, 1.0))) * (0.3 + 0.7 * pow(0.5 + 0.5 * sin(t * (2.0 + h1 * 3.0) + fi * 5.0), 2.0));
        col += vec3(1.0, 0.9, 0.5) * g * (0.3 + 1.0 * uHighS);
    }
    col += plate * smoothstep(0.55, 0.9, lum) * uHighS * 0.4 * (0.5 + 0.5 * sin(t * 9.0 + uv.x * 300.0 + uv.y * 200.0));
    float mist = fbm(vec2(uv.x * 3.0 + t * 0.03, uv.y * 5.0) + uSeed) * smoothstep(0.45, 0.65, uv.y) * smoothstep(0.95, 0.7, uv.y);
    col = mix(col, col * 0.8 + vec3(0.5, 0.6, 0.7), smoothstep(0.4, 0.8, mist) * (0.15 + 0.15 * uMidS));
    // Einsatzwechsel: kurzer Lichtkreis um den Stumpf
    float stakeFx = exp(-uStakeT * 2.0) * step(0.0, uStakeT);
    col += vec3(0.9, 0.8, 0.4) * stakeFx * exp(-pow((length((uv - vec2(0.5, 0.5)) * vec2(aspect, 1.0)) - uStakeT * 1.2) * 8.0, 2.0));
    // Stille: dunkler
    col *= 0.75 + 0.25 * uLive;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
