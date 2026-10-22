#version 140
// Almanach: Casino-Automat aus dem falschen 1985 (uSceneTex) mit drei Fenstern (uWin0..2, uWinY), in denen die Walzen
// drehen (Atlas uSpriteTex wie Slotmaschine). Gold, Spiegel und Neon im Foto pulsen mit dem Bass, Lauflicht durch die
// drei Säulen auf den Beat (uStep), Glühbirnen flackern mit den Höhen, Funken. Drop = Blitz von oben (uBoltT) +
// Lichtwelle (uFlash). Gewinne: uWin 1 Dollarscheine regnen, 2 Feuerspuren + Professor tanzt (uFigTex Reihe 0, uFig),
// 3/4 Blitz, die Zeitmaschine fährt durch den Automaten (Reihe 1), Schwarzweiß wie 1955 (uSepia). Figurenbogen 8x3 à 192:
// Reihe 0 Professor (ragt 64 px in Reihe 1 hinein, daher 256 hoch gelesen), Reihe 1 Zeitmaschine (untere 128 px),
// Reihe 2 Tanzpaar (Zellen 16-23).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSpriteTex, uSceneTex, uFigTex;
uniform vec2 uAtlasSize, uSceneSize, uFigSize, uTile, uWin0, uWin1, uWin2, uWinY;
uniform float uTheme, uState, uStateT, uWin, uWinMask, uWinLine, uFade, uStripRow;
uniform vec3 uColA, uColB, uReel, uSpeed, uBlur, uStopT;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uFlash, uBoltT, uBoltSeed, uSepia, uStake, uStakeT, uStep, uStepPhase;
uniform vec4 uFig;
const float PI = 3.14159265;
const float STRIP = 32.0;
const float CELL = 0.333;
const vec3 GOLD = vec3(1.0, 0.78, 0.3);
const vec3 BOLT = vec3(0.75, 0.85, 1.0);

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
float sq(float x) { return x * x; }
float ex(float x) { return exp(max(x, -60.0)); }   // exp mit sehr großem negativem Argument liefert auf manchen Treibern Müll
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
// Gold, Neonröhren, Spiegelkanten: helle gesättigte Stellen des Fotos
float goldAt(vec2 uv) {
    vec3 c = scene(uv);
    float lum = max(c.r, max(c.g, c.b));
    float sat = lum - min(c.r, min(c.g, c.b));
    return smoothstep(0.42, 0.78, lum) * smoothstep(0.15, 0.42, sat);
}
// Glühbirnen: sehr helle, fast weiße Punkte
float bulbAt(vec3 c) {
    float lum = max(c.r, max(c.g, c.b));
    float sat = lum - min(c.r, min(c.g, c.b));
    return smoothstep(0.86, 0.97, lum) * smoothstep(0.5, 0.2, sat);
}
// Figurenbogen 8x3 à 192 (Schwarz = frei). Zeile 0 wird 256 hoch gelesen (Professor ragt nach unten über die Zelle),
// Zeile 1 nur die unteren 128 (Zeitmaschine), Zeile 2 normal. figH = Höhe der Zelle in Pixeln.
float figH(float ri) { return ri < 0.5 ? 256.0 : (ri < 1.5 ? 128.0 : 192.0); }
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0 || uFig.w < 0.5) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    float h = figH(ri);
    float y0 = ri < 0.5 ? 320.0 : (ri < 1.5 ? 192.0 : 0.0);
    vec2 lo = vec2(ci * 192.0, y0);
    vec4 s = bilin(uFigTex, lo + (d * 0.5 + 0.5) * vec2(192.0, h), uFigSize, lo, lo + vec2(191.0, h - 1.0));
    float lum = max(s.r, max(s.g, s.b));
    s.a = min(s.a, smoothstep(0.05, 0.2, lum));
    return s;
}
// Figur mit Fußpunkt foot (uv), halbe Breite hw (in Bildhöhen-Einheiten), richtiges Seitenverhältnis je Zeile
vec4 figAt(float idx, vec2 uv, vec2 foot, float hw, float aspect) {
    float ratio = figH(floor(idx / 8.0)) / 192.0;
    vec2 d = (uv - foot) * vec2(aspect, 1.0) / vec2(hw, hw * ratio);
    d.y = d.y - 1.0 + 0.04;
    return figCell(idx, d);
}
float stripSymbol(float reel, float k) {
    float kk = mod(k, STRIP);
    return floor(texture(uSpriteTex, vec2((kk + 0.5) / uAtlasSize.x, (uStripRow + reel + 0.5) / uAtlasSize.y)).r * 255.0 + 0.5);
}
vec4 sprite(float idx, vec2 l) {
    if (l.x < 0.0 || l.x >= 1.0 || l.y < 0.0 || l.y >= 1.0) return vec4(0.0);
    vec2 base = vec2(idx * uTile.x, 0.0);
    return bilin(uSpriteTex, base + l * uTile, uAtlasSize, base, base + uTile - 1.0);
}
vec2 winX(int i) { return i == 0 ? uWin0 : (i == 1 ? uWin1 : uWin2); }

// Blitz: gezackte Linie von oben (x0, y 1.0) bis zum Ziel (x1, y1); Rückgabe = Leuchtstärke an uv
float bolt(vec2 uv, float aspect, vec2 from, vec2 to, float seed, float width) {
    float v = clamp((uv.y - to.y) / (from.y - to.y), 0.0, 1.0);
    if (uv.y > from.y + 0.02 || uv.y < to.y - 0.03) return 0.0;
    float x = mix(to.x, from.x, v);
    float wob = (noise(vec2(v * 7.0 + seed, seed)) - 0.5) * 0.07 + (noise(vec2(v * 29.0 + seed * 3.0, seed + 5.0)) - 0.5) * 0.025;
    x += wob * smoothstep(0.0, 0.08, v) * smoothstep(1.0, 0.9, v);
    float d = abs(uv.x - x) * aspect;
    return ex(-d / width) + 0.35 * ex(-d / (width * 6.0));
}
// Feuerspur: zwei parallele Glutlinien von x0 bis Kopf x1 auf Höhe y, Flammen darüber; rgb = Farbe, a = Deckung
// (wird deckend über das helle Gold gelegt, additiv wäre dort unsichtbar)
vec4 fireTrail(vec2 uv, float aspect, float y, float x0, float x1, float t, float flare) {
    float lo = min(x0, x1), hi = max(x0, x1);
    if (uv.x < lo - 0.03 || uv.x > hi + 0.05) return vec4(0.0);
    float along = clamp((uv.x - lo) / max(hi - lo, 0.001), 0.0, 1.0);
    float head = x1 > x0 ? along : 1.0 - along;             // 1 = am Kopf
    float ends = smoothstep(lo - 0.03, lo + 0.03, uv.x) * smoothstep(hi + 0.05, hi - 0.02, uv.x);
    float dy = uv.y - y;
    float lines = ex(-sq(dy * 200.0)) + ex(-sq((dy - 0.022) * 200.0));
    float flick = 0.6 + 0.4 * noise(vec2(uv.x * 60.0 - t * 9.0, t * 4.0));
    float fl = fbm(vec2(uv.x * 30.0, dy * 50.0 - t * 5.0));
    float flames = smoothstep(0.035, 0.0, max(dy - 0.012 - fl * 0.03 * (1.0 + flare), 0.0)) * step(-0.01, dy) * fl * 1.5;
    vec3 c = vec3(1.0, 0.55, 0.12) * lines * flick * 1.4 + vec3(1.0, 0.35, 0.05) * flames;
    c += vec3(1.0, 0.9, 0.6) * ex(-sq(dy * 320.0)) * (0.5 + 0.5 * flick) * 0.5;
    float a = clamp(lines * 1.8 + flames * 1.6, 0.0, 1.0) * ends * (0.5 + 0.5 * head);
    return vec4(c * (0.35 + 0.65 * head), a);
}
vec3 blendFire(vec3 col, vec4 f) { col = mix(col, col * 0.3, f.a * 0.8); return mix(col, f.rgb * 1.4, f.a) + f.rgb * f.a * 0.3; }   // Brandspur dunkel, Glut hell

// Walze i im Fenster: q.x 0..1 über die Fensterbreite, q.y 0..1 über die Fensterhöhe (3 Zellen, Mitte = Gewinnlinie)
vec3 drum(int i, vec2 q, float winAspect) {
    float reel = float(i);
    float pos = uReel[i];
    float yn = clamp((q.y - 0.5) * 2.0, -0.999, 0.999);
    float ang = asin(yn);
    float yc = ang / (PI * 0.5) * 0.5 * 1.45;
    float k = floor(pos + yc / CELL + 0.5);
    float ly = (yc - (k - pos) * CELL) / CELL + 0.5;
    // Trommelband: dunkler Samt mit feinen Goldlinien, die mit dem Beat aufleuchten
    float lines = smoothstep(0.02, 0.0, abs(fract(yc * 14.0) - 0.5) - 0.02);
    vec3 velvet = vec3(0.08, 0.02, 0.03) + vec3(0.12, 0.03, 0.03) * noise(vec2(q.x * 24.0, yc * 48.0));
    velvet += GOLD * lines * (0.05 + 0.2 * uBeatPulse);
    vec2 l = vec2(q.x, ly);
    float symW = min(1.0, 1.5 * winAspect * 1.08), symH = min(1.0, symW / (1.5 * winAspect));   // Symbol im richtigen Seitenverhältnis
    vec2 sl = (l - vec2(0.5, 0.5)) / vec2(symW, symH) + 0.5;
    float idx = stripSymbol(reel, k);
    vec4 s = sprite(idx, sl);
    vec3 col = mix(velvet, s.rgb, s.a);
    float onLine = smoothstep(0.35, 0.0, abs(q.y - 0.5));
    float glow = (idx == 8.0 ? 0.6 : 0.25) + 0.4 * uBeatPulse * onLine;
    col += s.rgb * s.a * glow * uLive;
    if (idx == 8.0) col += BOLT * s.a * 0.25 * (0.5 + 0.5 * sin(iTime * 9.0 + reel));      // die Uhr knistert blau
    float sep = smoothstep(0.03, 0.0, min(ly, 1.0 - ly));
    col = mix(col, GOLD, sep * 0.55);
    float diffuse = 0.6 + 0.4 * pow(max(cos(ang), 0.0), 0.6);
    col *= diffuse;
    col *= 1.0 - 0.35 * smoothstep(0.4, 0.5, abs(q.x - 0.5));
    float spin = clamp(uSpeed[i] / 8.0, 0.0, 1.0);
    col += GOLD * 0.12 * spin * (0.6 + 0.4 * sin(iTime * 25.0 + reel));
    col = mix(col, col * (0.7 + 0.6 * noise(vec2(q.x * 10.0, yc * 60.0 - iTime * 40.0))), uBlur[i] * 0.5);
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    vec2 uv = vUv;
    vec2 center = vec2(0.5, 0.5);
    uv = center + (uv - center) / 1.1;
    uv = center + (uv - center) * (1.0 - 0.02 * uBassS - 0.01 * uBeatPulse);
    uv.y -= 0.003 * uBeatPulse;
    float resultT = uState == 2.0 ? uStateT : -1.0;
    float big = (uWin >= 2.0 && resultT >= 0.0) ? 1.0 : 0.0;
    float jackpot = (uWin >= 3.0 && resultT >= 0.0) ? 1.0 : 0.0;
    uv += vec2(0.003, 0.002) * jackpot * sin(t * 30.0) * ex(-resultT * 0.6);
    // Blitz: beim Drop (uBoltT) und zum Jackpot (resultT 0..0.9) schlägt er von oben in den Goldbalken über den Fenstern ein
    float boltAge = -1.0, boltSeed = uBoltSeed;
    if (uBoltT >= 0.0) boltAge = uBoltT;
    if (jackpot > 0.0 && resultT < 1.2) { boltAge = resultT * 0.5; boltSeed = 42.0; }
    float boltK = boltAge >= 0.0 ? ex(-boltAge * 4.0) * (0.6 + 0.4 * step(0.5, hash12(vec2(floor(t * 40.0), 1.0)))) : 0.0;
    uv += vec2(0.004, 0.003) * boltK * sin(t * 50.0);
    vec3 plate = scene(uv);
    vec3 col = plate;
    float lum = max(plate.r, max(plate.g, plate.b));
    // ---- Lichtshow: Gold und Neon leuchten mit dem Bass, Lauflicht durch die Säulen (links, Mitte, rechts)
    float gold = goldAt(uv);
    float bloom = 0.0;
    for (int k = 0; k < 8; k++) {
        float a = float(k) * PI * 0.25;
        bloom += goldAt(uv + vec2(cos(a) / aspect, sin(a)) * 0.03);
    }
    bloom /= 8.0;
    float z0 = 1.0 - smoothstep(0.41, 0.45, uv.x), z2 = smoothstep(0.55, 0.59, uv.x), z1 = 1.0 - z0 - z2;   // Säulen links / Mitte / rechts, weiche Kanten
    float sel = uStep < 0.5 ? z0 : (uStep < 1.5 ? z1 : z2);
    float run = sel * (1.0 - 0.6 * uStepPhase);
    float offZone = (1.0 - sel) * uLive * 0.4;
    vec3 glowCol = plate / max(lum, 0.2);
    if (uFlash > 0.0) {
        float wave = ex(-sq((uv.y - (uFlash * 1.6 - 0.3)) * 6.0));          // Lichtwelle läuft nach dem Blitz von oben nach unten
        glowCol = mix(glowCol, mix(BOLT, GOLD, uv.x), wave * uFlash);
    }
    float stakeGlow = 0.2 + 0.4 * uStake;
    float breathe = 0.5 + 0.5 * sin(t * 1.5 + uv.y * 6.0);
    float drive = 0.15 * breathe + 0.9 * uBassS + 0.5 * uBeatPulse + 1.6 * run * uLive + stakeGlow * 0.3
                + 0.8 * big * (0.5 + 0.5 * sin(t * 6.0 - uv.y * 12.0)) + 0.3 * uHighS * noise(uv * 80.0 + t * 5.0);
    col = mix(col, col * 0.45, gold * uLive * (1.0 - clamp(drive, 0.0, 1.0)));
    col = mix(col, col * 0.6, gold * offZone * (0.5 + 0.5 * uBassS));
    col += glowCol * gold * drive * (0.35 + 0.6 * uLive);
    col += glowCol * bloom * drive * 0.8 * (0.3 + 0.7 * uLive);
    // Glühbirnen: flackern mit den Höhen, auf dem Beat alle hell
    float bulb = bulbAt(plate);
    float twinkle = step(0.55 - 0.4 * uHighS, hash12(vec2(floor(uv.x * 60.0), floor(uv.y * 34.0) + floor(t * 12.0))));
    col += vec3(1.0, 0.9, 0.6) * bulb * (0.25 * twinkle * uLive + 0.5 * uBeatPulse + 0.3 * big);
    col = mix(col, col * 0.7, bulb * (1.0 - twinkle) * uLive * 0.5 * (1.0 - uBeatPulse));
    // ---- Fenster: Walzen
    float wh = uWinY.y - uWinY.x;
    for (int i = 0; i < 3; i++) {
        vec2 wx = winX(i);
        vec2 q = vec2((uv.x - wx.x) / (wx.y - wx.x), (uv.y - uWinY.x) / wh);
        if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) continue;
        float ww = (wx.y - wx.x) * aspect;
        float winAspect = wh / 3.0 / ww;
        vec3 d = drum(i, q, winAspect);
        float edge = min(min(q.x, 1.0 - q.x) * 6.0, min(q.y, 1.0 - q.y) * 5.0);
        d *= 0.4 + 0.6 * smoothstep(0.0, 0.5, edge);
        float mask = mod(floor(uWinMask / pow(2.0, float(i))), 2.0);
        if (uWin > 0.0 && resultT >= 0.0 && mask > 0.5) {
            float line = 0.5;
            if (uWinLine == 1.0) line = 0.5 + (1.0 - float(i)) * CELL;
            if (uWinLine == 2.0) line = 0.5 + (float(i) - 1.0) * CELL;
            float ll = ex(-sq((q.y - line) * 9.0));
            d += mix(GOLD, BOLT, jackpot) * ll * (0.25 + 0.25 * sin(t * 8.0)) * (uWin >= 2.0 ? 1.4 : 0.7);
        }
        col = mix(col, d, 0.98);
    }
    // Stopp-Ruck je Walze (Goldblitz im Fenster), Hebelknauf glüht beim Drehen
    for (int i = 0; i < 3; i++) {
        float st = uStopT[i];
        if (st < 0.0 || st > 0.5) continue;
        vec2 wx = winX(i);
        float inWin = step(wx.x, uv.x) * step(uv.x, wx.y) * step(uWinY.x, uv.y) * step(uv.y, uWinY.y);
        col += vec3(1.0, 0.85, 0.5) * inWin * (1.0 - st / 0.5) * 0.5;
    }
    {
        vec2 knob = vec2(0.83, 0.845);
        float spinAll = clamp((uSpeed[0] + uSpeed[1] + uSpeed[2]) / 20.0, 0.0, 1.0);
        float kd = length((uv - knob) * vec2(aspect, 1.0));
        col += vec3(1.0, 0.25, 0.15) * ex(-kd * 30.0) * (0.5 * spinAll * (0.7 + 0.3 * sin(t * 25.0)) + 0.4 * uBeatPulse * spinAll);
    }
    // ---- Gewinn klein/groß: Dollarscheine regnen (grün-graue Scheine, flattern), groß mehr davon
    if (uWin >= 1.0 && resultT >= 0.0) {
        int n = uWin >= 2.0 ? 50 : 24;
        for (int i = 0; i < 50; i++) {
            if (i >= n) break;
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
            float age = resultT * (0.5 + 0.5 * h3) - h2 * 1.5;
            if (age < 0.0) continue;
            vec2 p = vec2(0.12 + h1 * 0.76 + 0.04 * sin(age * 2.5 + fi), 1.05 - age * 0.2);
            if (p.y < -0.05) continue;
            vec2 d = rot(0.6 * sin(age * 3.0 + fi * 2.0) + h1 * 0.8) * ((uv - p) * vec2(aspect, 1.0));
            float flap = 0.45 + 0.55 * abs(cos(age * 6.0 + fi));             // Schein kippt um seine Längsachse
            vec2 e = abs(d) / vec2(0.028, 0.013 * flap);
            float bill = step(max(e.x, e.y), 1.0);
            float border = step(0.78, max(e.x, e.y));
            float oval = smoothstep(0.45, 0.3, length(d / vec2(0.011, 0.009 * flap)));
            vec3 bc = mix(vec3(0.55, 0.68, 0.5), vec3(0.3, 0.45, 0.32), border + oval * 0.6) * (0.75 + 0.25 * flap);
            bc *= 0.85 + 0.3 * uBeatPulse;
            col = mix(col, bc, bill * 0.95);
        }
    }
    // ---- Großer Gewinn: Feuerspuren laufen durch das Bild, der Professor tanzt auf den Beat
    if (big > 0.0 && jackpot < 1.0) {
        for (int k = 0; k < 3; k++) {
            float fk = float(k);
            float yk = 0.14 + fk * 0.11;
            float head = mod(resultT * 0.45 + fk * 0.37, 1.3) - 0.15;
            float dir = mod(fk, 2.0) < 0.5 ? 1.0 : -1.0;
            float x1 = dir > 0.0 ? head : 1.0 - head;
            col = blendFire(col, fireTrail(uv, aspect, yk, x1 - dir * 0.55, x1, t + fk * 3.0, uBassS));
        }
    }
    if (big > 0.0) {
        float enter = smoothstep(0.0, 0.6, resultT) * smoothstep(5.0, 4.4, resultT);
        if (jackpot > 0.0) enter = smoothstep(4.0, 4.8, resultT) * smoothstep(8.0, 7.4, resultT);   // beim Jackpot erst nach der Zeitmaschine
        // Professor tanzt links unten (Reihe 0), das Tanzpaar rechts unten (Reihe 2), beide wechseln die Pose auf den Beat
        vec2 sp = vec2(0.12, 0.04);
        sp.y += 0.012 * uBassS + 0.01 * sin(t * 8.0) * uBeatPulse;
        float hw = 0.2 * aspect * 0.5;
        vec4 s = mix(figAt(uFig.x, uv, sp, hw, aspect), figAt(uFig.y, uv, sp, hw, aspect), uFig.z);
        col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * enter);
        col += GOLD * s.a * enter * 0.25 * uBeatPulse;
        vec2 dp = vec2(0.88, 0.04);
        dp.y += 0.01 * sin(t * 8.0 + 1.0) * uBeatPulse;
        vec4 c2 = mix(figAt(16.0 + mod(uFig.x + 3.0, 8.0), uv, dp, hw, aspect), figAt(16.0 + mod(uFig.y + 3.0, 8.0), uv, dp, hw, aspect), uFig.z);
        col = mix(col, c2.rgb * (0.9 + 0.3 * uBassS), c2.a * enter);
    }
    // ---- Jackpot: Blitz, dann fährt die Zeitmaschine durch den Automaten (Reihe 1), Feuerspuren hinter ihr
    if (jackpot > 0.0) {
        col += plate * 0.35 * ex(-resultT * 0.5) * (0.6 + 0.4 * sin(t * 12.0));
        float drive = clamp((resultT - 0.9) / 3.0, 0.0, 1.0);
        if (resultT >= 0.9 && drive < 1.0) {
            float cx = -0.35 + drive * 1.7;
            float cy = 0.40 + 0.012 * sin(t * 7.0);
            float hw = 0.36 * aspect * 0.5;
            float frame = 12.0 + step(0.5, fract(t * 8.0));                            // Wagen (Zellen 12/13, Feuer flackert)
            vec4 car = figAt(frame, uv, vec2(cx, cy), hw, aspect);
            col = blendFire(col, fireTrail(uv, aspect, cy + 0.005, cx - 0.9, cx - 0.12, t, 1.5));
            col += BOLT * car.a * 0.3 * step(0.5, fract(t * 10.0));                 // Zeitkreise blitzen blau
            col = mix(col, car.rgb * (1.0 + 0.3 * uBeatPulse), car.a);
            col += BOLT * ex(-abs(uv.x - cx) * 6.0) * 0.08 * (0.5 + 0.5 * sin(t * 40.0));
        }
        if (drive >= 1.0) {                                                            // danach glüht der Rest der Feuerspur aus
            vec4 rest = fireTrail(uv, aspect, 0.405, 0.3, 1.2, t, 0.5);
            rest.a *= ex(-(resultT - 3.9) * 1.2);
            col = blendFire(col, rest);
        }
    }
    // ---- Blitz von oben durch die Krone in den Automaten (Drop und Jackpot)
    if (boltK > 0.01) {
        vec2 hit = vec2(0.5 + 0.2 * (hash12(vec2(boltSeed, 2.0)) - 0.5), 0.69);
        float b = bolt(uv, aspect, vec2(0.3 + 0.4 * hash12(vec2(boltSeed, 1.0)), 1.05), hit, boltSeed, 0.009);
        b += 0.6 * bolt(uv, aspect, vec2(0.2 + 0.6 * hash12(vec2(boltSeed, 3.0)), 1.05), hit + vec2(0.05, 0.02), boltSeed + 7.0, 0.004);
        col *= 1.0 - 0.55 * boltK;                                                                // Saal wird kurz dunkel
        col = mix(col, BOLT * 1.7, clamp(b * boltK * 2.5, 0.0, 1.0));                            // Blitz deckend über dem Gold
        col += BOLT * boltK * 0.2 * smoothstep(0.5, 1.0, uv.y);                                 // Himmel über dem Automaten
        col += vec3(1.0) * ex(-length((uv - hit) * vec2(aspect, 1.0)) * 6.0) * boltK * 0.9;    // Einschlag
        col += plate * boltK * 0.8 * step(0.7, boltK);                                           // Weißblitz
    }
    // ---- Funken und Glitzer mit den Höhen, Einsatzwechsel: Goldring
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 33.0));
        vec2 c = vec2(h1, 0.1 + h2 * 0.8);
        float on = step(0.85 - 0.4 * uHighS, hash12(vec2(fi, floor(t * 15.0))));
        col += vec3(1.0, 0.9, 0.5) * smoothstep(0.007, 0.0, length((uv - c) * vec2(aspect, 1.0))) * on * uLive;
    }
    col += GOLD * gold * uHighS * 0.5 * step(0.93, noise(uv * vec2(140.0, 80.0) + t * 7.0)) * uLive;        // Glitzer auf dem Gold
    float stakeFx = ex(-uStakeT * 2.0) * step(0.0, uStakeT);
    col += GOLD * stakeFx * ex(-sq((length((uv - vec2(0.5, 0.5)) * vec2(aspect, 1.0)) - uStakeT * 1.2) * 8.0));
    col *= 0.75 + 0.25 * uLive;
    // ---- Schwarzweiß wie 1955: Film mit Korn und Kratzern, kommt mit Farbe zurück
    if (uSepia > 0.001) {
        float g = dot(col, vec3(0.3, 0.59, 0.11));
        vec3 film = vec3(pow(max(g, 0.0), 1.15)) * vec3(1.0, 0.96, 0.9);
        film *= 0.9 + 0.2 * (noise(vUv * 400.0 + t * 30.0) - 0.5);
        float scratch = step(0.995, hash12(vec2(floor(vUv.x * 300.0 + floor(t * 7.0) * 13.0), 1.0)));
        film += scratch * 0.3;
        film *= 0.85 + 0.15 * hash12(vec2(floor(t * 24.0), 3.0));
        col = mix(col, film, uSepia);
    }
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
