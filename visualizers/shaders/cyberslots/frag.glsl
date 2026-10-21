#version 140
// Pachinko: Neon-Automat (uSceneTex) mit drei Fenstern (uWin0..2, uWinY), in denen die Walzen drehen (Atlas uSpriteTex
// wie Slotmaschine). Neon im Foto pulst mit dem Bass, Lauflicht durch die drei Säulen auf den Beat (uStep), Höhen =
// Funken, Drop = Glitch (uGlitchT) + Farbwelle (uFlash). Gewinne: uWin 1 Credits regnen, 2 Hologramm-Feuerwerk + Samurai
// (uFigTex Reihe 0, uSam), 3/4 Halle explodiert, Drohnen (uObjTex Zelle 0) bringen Koffer (Zelle 20).
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSpriteTex, uSceneTex, uFigTex, uObjTex;
uniform vec2 uAtlasSize, uSceneSize, uFigSize, uObjSize, uTile, uWin0, uWin1, uWin2, uWinY;
uniform float uTheme, uState, uStateT, uWin, uWinMask, uWinLine, uFade, uStripRow;
uniform vec3 uColA, uColB, uReel, uSpeed, uBlur, uStopT;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uFlash, uGlitchT, uStake, uStakeT, uStep, uStepPhase;
uniform vec4 uSam;
const float PI = 3.14159265;
const float STRIP = 32.0;
const float CELL = 0.333;

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
float neonAt(vec2 uv) {
    vec3 c = scene(uv);
    float lum = max(c.r, max(c.g, c.b));
    float sat = lum - min(c.r, min(c.g, c.b));
    return smoothstep(0.4, 0.75, lum) * smoothstep(0.2, 0.45, sat);
}
vec4 figCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (2.0 - ri) * 192.0);
    return bilin(uFigTex, lo + (d * 0.5 + 0.5) * 192.0, uFigSize, lo, lo + 191.0);
}
vec4 objCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 6.0), ri = floor(idx / 6.0);
    vec2 lo = vec2(ci * 192.0, (3.0 - ri) * 192.0);
    return bilin(uObjTex, lo + (d * 0.5 + 0.5) * 192.0, uObjSize, lo, lo + 191.0);
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

// Walze i im Fenster: q.x 0..1 über die Fensterbreite, q.y 0..1 über die Fensterhöhe (3 Zellen, Mitte = Gewinnlinie)
vec3 drum(int i, vec2 q, float winAspect) {
    float reel = float(i);
    float pos = uReel[i];
    float yn = clamp((q.y - 0.5) * 2.0, -0.999, 0.999);
    float ang = asin(yn);
    float yc = ang / (PI * 0.5) * 0.5 * 1.45;
    float k = floor(pos + yc / CELL + 0.5);
    float ly = (yc - (k - pos) * CELL) / CELL + 0.5;
    // Trommelband: dunkles Glas mit Leiterbahnen, die mit dem Beat leuchten
    float trace = smoothstep(0.02, 0.0, abs(fract(q.x * 6.0 + yc * 2.0) - 0.5) - 0.02) + smoothstep(0.02, 0.0, abs(fract(yc * 9.0) - 0.5) - 0.01);
    vec3 glass = vec3(0.03, 0.02, 0.06) + vec3(0.1, 0.0, 0.2) * noise(vec2(q.x * 20.0, yc * 40.0));
    glass += vec3(0.1, 0.5, 0.9) * trace * (0.05 + 0.25 * uBeatPulse);
    vec2 l = vec2(q.x, ly);
    float symW = min(1.0, 1.5 * winAspect * 1.08), symH = min(1.0, symW / (1.5 * winAspect));   // Symbol im richtigen Seitenverhältnis
    vec2 sl = (l - vec2(0.5, 0.5)) / vec2(symW, symH) + 0.5;
    float idx = stripSymbol(reel, k);
    vec4 s = sprite(idx, sl);
    vec3 col = mix(glass, s.rgb, s.a);
    float onLine = smoothstep(0.35, 0.0, abs(q.y - 0.5));
    float glow = (idx == 8.0 ? 0.6 : 0.3) + 0.4 * uBeatPulse * onLine;
    col += s.rgb * s.a * glow * uLive;
    float sep = smoothstep(0.03, 0.0, min(ly, 1.0 - ly));
    col = mix(col, vec3(0.2, 0.8, 1.0), sep * 0.5);
    float diffuse = 0.6 + 0.4 * pow(max(cos(ang), 0.0), 0.6);
    col *= diffuse;
    col *= 1.0 - 0.35 * smoothstep(0.4, 0.5, abs(q.x - 0.5));
    float spin = clamp(uSpeed[i] / 8.0, 0.0, 1.0);
    col += vec3(0.9, 0.2, 1.0) * 0.1 * spin * (0.6 + 0.4 * sin(iTime * 25.0 + reel));
    col = mix(col, col * (0.7 + 0.6 * noise(vec2(q.x * 10.0, yc * 60.0 - iTime * 40.0))), uBlur[i] * 0.5);
    return col;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    vec2 uv = vUv;
    vec2 center = vec2(0.5, 0.52);
    uv = center + (uv - center) / 1.22;
    uv = center + (uv - center) * (1.0 - 0.02 * uBassS - 0.01 * uBeatPulse);
    uv.y -= 0.003 * uBeatPulse;
    float resultT = uState == 2.0 ? uStateT : -1.0;
    float big = (uWin >= 2.0 && resultT >= 0.0) ? 1.0 : 0.0;
    float jackpot = (uWin >= 3.0 && resultT >= 0.0) ? 1.0 : 0.0;
    uv += vec2(0.003, 0.002) * jackpot * sin(t * 30.0) * exp(-resultT * 0.6);
    // Drop-Glitch: Zeilen springen, Kanäle trennen sich
    float gl = uGlitchT >= 0.0 ? exp(-uGlitchT * 2.5) : 0.0;
    if (gl > 0.01) {
        float row = floor(uv.y * 50.0 + floor(t * 10.0));
        uv.x += (hash12(vec2(row, floor(t * 8.0))) - 0.5) * 0.06 * gl * step(0.6, hash12(vec2(row, 7.0)));
    }
    vec3 plate = gl > 0.01 ? vec3(scene(uv + vec2(0.006 * gl, 0.0)).r, scene(uv).g, scene(uv - vec2(0.006 * gl, 0.0)).b) : scene(uv);
    vec3 col = plate;
    float lum = max(plate.r, max(plate.g, plate.b));
    // ---- Neon-Lichtshow: Röhren und Bildschirme leuchten mit dem Bass, Lauflicht durch die Säulen (links, Mitte, rechts)
    float neon = neonAt(uv);
    float bloom = 0.0;
    for (int k = 0; k < 8; k++) {
        float a = float(k) * PI * 0.25;
        bloom += neonAt(uv + vec2(cos(a) / aspect, sin(a)) * 0.03);
    }
    bloom /= 8.0;
    float zone = uv.x < 0.33 ? 0.0 : (uv.x < 0.67 ? 1.0 : 2.0);
    float run = (zone == uStep ? 1.0 : 0.0) * (1.0 - 0.6 * uStepPhase);
    float offZone = (zone == uStep ? 0.0 : 1.0) * uLive * 0.4;
    vec3 glowCol = plate / max(lum, 0.2);
    if (uFlash > 0.0) {
        float wave = exp(-pow((uv.x - (1.0 - uFlash) * 1.6 + 0.3) * 6.0, 2.0));
        glowCol = mix(glowCol, hueShift(glowCol, 2.0 + uv.x * 3.0), wave * uFlash);
    }
    float stakeGlow = 0.2 + 0.4 * uStake;
    float breathe = 0.5 + 0.5 * sin(t * 1.5 + uv.y * 6.0);
    float drive = 0.15 * breathe + 0.9 * uBassS + 0.5 * uBeatPulse + 1.6 * run * uLive + stakeGlow * 0.3
                + 1.5 * big * (0.5 + 0.5 * sin(t * 6.0 - uv.y * 12.0)) + 0.3 * uHighS * noise(uv * 80.0 + t * 5.0);
    col = mix(col, col * 0.4, neon * uLive * (1.0 - clamp(drive, 0.0, 1.0)));
    col = mix(col, col * 0.55, neon * offZone * (0.5 + 0.5 * uBassS));
    col += glowCol * neon * drive * (0.4 + 0.7 * uLive);
    col += glowCol * bloom * drive * 0.9 * (0.3 + 0.7 * uLive);
    // Bildschirme flimmern (dunkle, leicht bunte Flächen)
    col += plate * smoothstep(0.3, 0.1, lum) * 0.15 * step(0.96, hash12(vec2(floor(uv.y * 120.0), floor(t * 30.0)))) * uLive;
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
            float ll = exp(-pow((q.y - line) * 9.0, 2.0));
            d += vec3(1.0, 0.4, 1.0) * ll * (0.25 + 0.25 * sin(t * 8.0)) * (uWin >= 2.0 ? 1.4 : 0.7);
        }
        col = mix(col, d, 0.98);
    }
    // Stopp-Blitz je Walze, Hebelknauf glüht beim Drehen
    for (int i = 0; i < 3; i++) {
        float st = uStopT[i];
        if (st < 0.0 || st > 0.5) continue;
        vec2 wx = winX(i);
        float inWin = step(wx.x, uv.x) * step(uv.x, wx.y) * step(uWinY.x, uv.y) * step(uv.y, uWinY.y);
        col += vec3(0.6, 0.9, 1.0) * inWin * (1.0 - st / 0.5) * 0.5;
    }
    {
        vec2 knob = vec2(0.79, 0.62);
        float spinAll = clamp((uSpeed[0] + uSpeed[1] + uSpeed[2]) / 20.0, 0.0, 1.0);
        float kd = length((uv - knob) * vec2(aspect, 1.0));
        col += vec3(1.0, 0.3, 0.9) * exp(-kd * 35.0) * (0.4 * spinAll * (0.7 + 0.3 * sin(t * 25.0)) + 0.4 * uBeatPulse * spinAll);
    }
    // ---- Gewinn klein/groß: Credits regnen (leuchtende Chips), groß zusätzlich Hologramm-Feuerwerk
    if (uWin >= 1.0 && resultT >= 0.0) {
        int n = uWin >= 2.0 ? 50 : 24;
        for (int i = 0; i < 50; i++) {
            if (i >= n) break;
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.0)), h2 = hash12(vec2(fi, 5.0)), h3 = hash12(vec2(fi, 7.0));
            float age = resultT * (0.6 + 0.6 * h3) - h2 * 1.5;
            if (age < 0.0) continue;
            vec2 p = vec2(0.15 + h1 * 0.7 + 0.03 * sin(age * 3.0 + fi), 1.05 - age * 0.25);
            if (p.y < 0.0) continue;
            vec2 d = rot(age * 4.0 + fi) * ((uv - p) * vec2(aspect, 1.0));
            float chip = step(max(abs(d.x) * 1.6, abs(d.y) * 2.5), 0.012);
            col = mix(col, mix(vec3(1.0, 0.85, 0.2), vec3(0.3, 0.9, 1.0), h3) * (0.8 + 0.4 * sin(t * 10.0 + fi)), chip * 0.95);
        }
    }
    if (big > 0.0) {
        for (int k = 0; k < 6; k++) {                                            // Hologramm-Feuerwerk
            float fk = float(k);
            float h1 = hash12(vec2(fk, 13.0)), h2 = hash12(vec2(fk, 17.0));
            float age = mod(resultT * 0.8 + h1 * 3.0, 2.0);
            vec2 c = vec2(0.15 + h1 * 0.7, 0.55 + h2 * 0.35);
            vec2 d = (uv - c) * vec2(aspect, 1.0);
            float r = length(d), a = atan(d.y, d.x);
            float ring = exp(-pow((r - age * 0.15) * 40.0, 2.0)) * pow(0.5 + 0.5 * sin(a * 14.0 + fk), 3.0) * (1.0 - age / 2.0);
            col += hueShift(vec3(1.0, 0.3, 0.9), fk * 1.1) * ring * 1.2;
        }
        vec2 sp = vec2(0.12, 0.08);
        sp.y += 0.01 * uBassS + 0.008 * sin(t * 8.0) * uBeatPulse;
        float hw = 0.2 * aspect * 0.5;
        vec2 d = (uv - sp) * vec2(aspect, 1.0) / hw;
        d.y = d.y - 1.0 + 0.04;
        float enter = smoothstep(0.0, 0.6, resultT) * smoothstep(5.0, 4.4, resultT);
        vec4 s = mix(figCell(uSam.x, d), figCell(uSam.y, d), uSam.z);
        col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * enter);
    }
    // ---- Jackpot: Halle explodiert in Neon, Drohnen bringen Koffer von oben
    if (jackpot > 0.0) {
        col += plate * 0.8 * exp(-resultT * 0.4) * (0.6 + 0.4 * sin(t * 12.0));
        col = mix(col, hueShift(col, sin(t * 3.0) * 1.0), 0.4 * exp(-resultT * 0.3));
        for (int k = 0; k < 4; k++) {
            float fk = float(k);
            float h1 = hash12(vec2(fk, 23.0));
            float drop = clamp((resultT - fk * 0.8) / 4.0, 0.0, 1.0);
            vec2 dp = vec2(0.15 + fk * 0.23 + 0.02 * sin(t * 3.0 + fk), 1.1 - drop * (0.55 + 0.1 * h1) + 0.01 * sin(t * 6.0 + fk));
            float hw = 0.12 * aspect * 0.5;
            vec2 d = (uv - dp) * vec2(aspect, 1.0) / hw;
            vec4 s = objCell(0.0, d);
            s.rgb += vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 4.0 + fk)) * 0.3;
            col = mix(col, s.rgb, s.a * step(0.001, drop));
            vec4 b = objCell(20.0, (d + vec2(0.0, 1.6)) * 1.4);
            col = mix(col, b.rgb * (1.0 + 0.3 * uBeatPulse), b.a * step(0.001, drop));
            col += b.rgb * b.a * 0.4 * (0.5 + 0.5 * sin(t * 10.0 + fk));
        }
    }
    // ---- Funken mit den Höhen, Einsatzwechsel: Lichtkreis
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 31.0)), h2 = hash12(vec2(fi, 33.0));
        vec2 c = vec2(h1, 0.1 + h2 * 0.8);
        float on = step(0.85 - 0.4 * uHighS, hash12(vec2(fi, floor(t * 15.0))));
        col += vec3(1.0, 0.6, 1.0) * smoothstep(0.007, 0.0, length((uv - c) * vec2(aspect, 1.0))) * on * uLive;
    }
    float stakeFx = exp(-uStakeT * 2.0) * step(0.0, uStakeT);
    col += vec3(0.9, 0.4, 1.0) * stakeFx * exp(-pow((length((uv - vec2(0.5, 0.5)) * vec2(aspect, 1.0)) - uStakeT * 1.2) * 8.0, 2.0));
    col += (noise(vUv * 250.0 + t * 20.0) - 0.5) * 0.15 * gl;
    col *= 0.75 + 0.25 * uLive;
    col *= 1.0 - 0.3 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
