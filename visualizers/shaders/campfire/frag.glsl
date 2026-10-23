#version 140
// Lagerfeuer "Rast am Rand der Galaxis": Foto (uSceneTex, Glut ohne Flammen) mit Flammen aus vier Bögen (uFlameS/M/B/XTex
// 8x4 à 128x256, Schleife: uFlame = Bogen A, Bogen B, Mischung, Größe; uFlameK = Deckkraft, Blauanteil, Bild A, Bild B;
// uFrameMix), Feuerlicht auf den Steinen (Stufe uLevel, Glut uEmber), Hitzeflimmern, Rauch im Wind (uWind), Kesseldampf
// (uKettle), Funken uSp0..23 (x, y, Zelle in uSparkTex 8x2 à 128, Größe), Gegenstände uItem0..3 (x, y, Zelle in uItemTex
// 8x2 à 192, Größe) + uItemP (Deckkraft, Drehung), Motten uMoth0..2 (x, y, Zelle, Deckkraft), Himmel: Sterne funkeln mit
// den Höhen, Polarlicht mit dem Bass, Sternschnuppe uShoot (Alter, x, y, Winkel), Himmel steigt uSkyRise, Taxi-Lichter
// uTaxi/uTaxiT, Nahaufnahme uZoom, Marshmallow-Hitze uMallow.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uFlameSTex, uFlameMTex, uFlameBTex, uFlameXTex, uSparkTex, uItemTex;
uniform vec2 uSceneSize, uFlameSize, uSparkSize, uItemSize, uKettle;
uniform vec4 uFire, uTaxi, uFlame, uFlameK, uShoot, uMallow;
uniform float uSeed, uHorizon, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uLevel, uFrameMix, uWind, uEmber, uPokeT;
uniform float uSkyRise, uTaxiT, uZoom;
uniform vec4 uSp0, uSp1, uSp2, uSp3, uSp4, uSp5, uSp6, uSp7, uSp8, uSp9, uSp10, uSp11, uSp12, uSp13, uSp14, uSp15;
uniform vec4 uSp16, uSp17, uSp18, uSp19, uSp20, uSp21, uSp22, uSp23;
uniform vec4 uItem0, uItem1, uItem2, uItem3, uItemP0, uItemP1, uItemP2, uItemP3, uMoth0, uMoth1, uMoth2;
const vec2 FCELL = vec2(128.0, 256.0);

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { return 0.5 * noise(p) + 0.25 * noise(p * 2.1 + 3.0) + 0.125 * noise(p * 4.3 + 7.0); }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
vec4 bilin(sampler2D tex, vec2 px, vec2 size, vec2 lo, vec2 hi) {
    vec2 p = clamp(px - 0.5, lo, hi);
    vec2 i = floor(p), f = fract(p);
    vec2 i1 = min(i + 1.0, hi);
    vec4 a = texture(tex, (i + 0.5) / size), b = texture(tex, (vec2(i1.x, i.y) + 0.5) / size);
    vec4 c = texture(tex, (vec2(i.x, i1.y) + 0.5) / size), d = texture(tex, (i1 + 0.5) / size);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
vec3 scene(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0).rgb; }
// Flammenzelle: p.x 0..1 über die Zellbreite, p.y 0..1 von unten (Bild steht im Speicher auf dem Kopf, 4 Reihen)
vec4 flameCell(int sheet, float frame, vec2 p) {
    if (p.x <= 0.0 || p.x >= 1.0 || p.y <= 0.0 || p.y >= 1.0) return vec4(0.0);
    float ci = mod(frame, 8.0), ri = floor(frame / 8.0);
    vec2 lo = vec2(ci * FCELL.x, (3.0 - ri) * FCELL.y);
    vec2 px = lo + p * FCELL;
    if (sheet == 0) return bilin(uFlameSTex, px, uFlameSize, lo, lo + FCELL - 1.0);
    if (sheet == 1) return bilin(uFlameMTex, px, uFlameSize, lo, lo + FCELL - 1.0);
    if (sheet == 2) return bilin(uFlameBTex, px, uFlameSize, lo, lo + FCELL - 1.0);
    return bilin(uFlameXTex, px, uFlameSize, lo, lo + FCELL - 1.0);
}
vec4 flameAnim(int sheet, vec2 p) { return mix(flameCell(sheet, uFlameK.z, p), flameCell(sheet, uFlameK.w, p), uFrameMix); }
vec4 sparkCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 128.0, (1.0 - ri) * 128.0);
    return bilin(uSparkTex, lo + (d * 0.5 + 0.5) * 128.0, uSparkSize, lo, lo + 127.0);
}
vec4 itemCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (1.0 - ri) * 192.0);
    return bilin(uItemTex, lo + (d * 0.5 + 0.5) * 192.0, uItemSize, lo, lo + 191.0);
}
vec4 spAt(int i) {
    if (i == 0) return uSp0; if (i == 1) return uSp1; if (i == 2) return uSp2; if (i == 3) return uSp3;
    if (i == 4) return uSp4; if (i == 5) return uSp5; if (i == 6) return uSp6; if (i == 7) return uSp7;
    if (i == 8) return uSp8; if (i == 9) return uSp9; if (i == 10) return uSp10; if (i == 11) return uSp11;
    if (i == 12) return uSp12; if (i == 13) return uSp13; if (i == 14) return uSp14; if (i == 15) return uSp15;
    if (i == 16) return uSp16; if (i == 17) return uSp17; if (i == 18) return uSp18; if (i == 19) return uSp19;
    if (i == 20) return uSp20; if (i == 21) return uSp21; if (i == 22) return uSp22; return uSp23;
}
vec4 itemAt(int i) { return i == 0 ? uItem0 : (i == 1 ? uItem1 : (i == 2 ? uItem2 : uItem3)); }
vec4 itemPAt(int i) { return i == 0 ? uItemP0 : (i == 1 ? uItemP1 : (i == 2 ? uItemP2 : uItemP3)); }
vec4 mothAt(int i) { return i == 0 ? uMoth0 : (i == 1 ? uMoth1 : uMoth2); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    vec2 fire = uFire.xy;
    float fw = uFire.z;                                                       // Zellbreite auf dem Schirm (Anteil)
    float fh = fw * 2.0 * aspect;                                             // Zellhöhe (Zelle 1:2)
    float lv = uLevel / 3.0;
    // ---- Kamera: langsames Atmen, Nahaufnahme aufs Feuer
    vec2 look = fire + vec2(0.0, 0.18);
    vec2 uv = mix(vUv, look + (vUv - look) / 1.9, uZoom);
    uv += vec2(0.002 * sin(t * 0.13), 0.0015 * cos(t * 0.1));
    // Hitzeflimmern über dem Feuer
    vec2 hq = (uv - fire) * vec2(aspect, 1.0);
    float heat = smoothstep(0.35, 0.0, abs(hq.x)) * smoothstep(-0.05, 0.1, hq.y) * smoothstep(0.9, 0.2, hq.y) * (0.2 + 0.8 * lv);
    uv.x += 0.003 * heat * sin(uv.y * 90.0 - t * 9.0 + noise(uv * 20.0 + t) * 6.0);
    // Himmel steigt unmerklich (Planet geht auf): oberhalb des Horizonts wandert das Bild nach unten
    float skyM = smoothstep(uHorizon, uHorizon + 0.08, uv.y);
    vec2 suv = uv - vec2(0.0, 0.03 * uSkyRise * skyM);
    vec3 col = scene(suv);
    vec3 plate = col;
    float lum = max(col.r, max(col.g, col.b));
    float sat = lum - min(col.r, min(col.g, col.b));
    // ---- Himmel: Sterne funkeln mit den Höhen, Polarlicht pulst mit dem Bass, Sternschnuppe
    float star = smoothstep(0.55, 0.9, lum) * (1.0 - smoothstep(0.1, 0.3, sat)) * skyM;
    float tw = 0.75 + 0.45 * step(0.5, hash12(vec2(floor(uv.x * 400.0), floor(uv.y * 220.0) + floor(t * (2.0 + 6.0 * uHighS)))));
    col = mix(col, col * tw, star);
    float aurora = smoothstep(0.03, 0.15, col.g - max(col.r, col.b)) * skyM * (1.0 - smoothstep(uHorizon + 0.1, uHorizon + 0.3, uv.y));
    col += col * aurora * (0.15 + 0.5 * uBassS * live) * (0.6 + 0.4 * sin(t * 0.4 + uv.x * 6.0));
    if (uShoot.x >= 0.0) {
        vec2 dir = vec2(cos(uShoot.w), sin(uShoot.w));
        vec2 head = uShoot.yz + dir * uShoot.x * 0.35;
        vec2 rel = (uv - head) * vec2(aspect, 1.0);
        float along = dot(rel, -dir * vec2(aspect, 1.0));
        float across = abs(dot(rel, vec2(-dir.y, dir.x) * vec2(aspect, 1.0)));
        float tail = step(0.0, along) * smoothstep(0.12, 0.0, along) * smoothstep(0.0035, 0.0, across);
        col += vec3(0.9, 0.95, 1.0) * tail * (1.0 - uShoot.x / 1.6) * skyM * 1.2;
    }
    // ---- Taxi: Positionslichter blinken (warme helle Stellen im Rechteck)
    if (uTaxiT >= 0.0 && uv.x > uTaxi.x && uv.x < uTaxi.z && uv.y > uTaxi.y && uv.y < uTaxi.w) {
        float light = smoothstep(0.35, 0.6, plate.r) * smoothstep(0.5, 0.15, plate.b);
        float blink = step(0.5, fract(uTaxiT * 2.5)) * smoothstep(3.0, 2.5, uTaxiT);
        col += vec3(1.0, 0.7, 0.3) * light * blink * 1.2;
    }
    // ---- Feuerlicht: Steine und Boden um das Feuer leuchten mit der Stufe, flackern mit den Flammen
    vec2 fq = (uv - fire) * vec2(aspect, 1.0);
    float fr = length(fq * vec2(1.0, 1.6));
    float flick = 0.85 + 0.15 * noise(vec2(t * 6.0, uSeed)) + 0.1 * uBassS;
    float lightK = (0.35 + 0.95 * lv + 0.3 * uEmber) * flick;
    float near = exp(-fr * 4.5) * (1.0 - skyM);
    vec3 warm = mix(vec3(1.0, 0.55, 0.2), vec3(0.4, 0.55, 1.0), uFlameK.y);
    col *= 1.0 + near * (lightK - 0.55) * 1.4;                                // Glut klein = dunkler als das Foto
    col += warm * near * lightK * 0.18 * smoothstep(0.15, 0.5, lum);
    col = mix(col, col * vec3(0.6, 0.7, 1.1), near * uFlameK.y * 0.6);
    // Glut in der Feuerstelle pulst
    float emberM = smoothstep(0.45, 0.75, plate.r) * smoothstep(0.35, 0.1, plate.b) * smoothstep(0.12, 0.0, fr);
    col += vec3(1.0, 0.4, 0.1) * emberM * (0.2 + 0.4 * uEmber + 0.25 * uBassS + 0.15 * sin(t * 3.0 + uv.x * 40.0)) * (0.5 + lv);
    // ---- Rauch: Fahne über dem Feuer, legt sich im Wind, mehr nach Stochern
    {
        float rise = (uv.y - fire.y - 0.08) / 0.7;
        if (rise > 0.0 && rise < 1.3) {
            float cx = fire.x + 0.12 * uWind * rise * rise + 0.02 * sin(rise * 5.0 + t * 0.5) + 0.03 * (fbm(vec2(rise * 3.0, t * 0.3 + uSeed)) - 0.5) * rise;
            float wdt = 0.03 + 0.12 * rise;
            float dx = (uv.x - cx) * aspect / wdt;
            float body = exp(-dx * dx) * (1.0 - smoothstep(0.7, 1.3, rise)) * smoothstep(0.0, 0.15, rise);
            float dens = fbm(vec2(uv.x * 8.0 + t * 0.2 * uWind, uv.y * 6.0 - t * 0.25)) * 0.8 + 0.2;
            float smoke = body * dens * (0.08 + 0.18 * lv + (uPokeT >= 0.0 ? 0.3 * exp(-uPokeT * 1.2) : 0.0)) * (0.5 + 0.5 * live);
            col = mix(col, vec3(0.45, 0.42, 0.42) * (0.5 + 0.5 * lightK), smoke);
        }
    }
    // ---- Flammen: drei Bögen gemischt (uFlame), Wind legt sie, leichte Turbulenz, Blauanteil
    {
        vec2 p = vec2((uv.x - fire.x) / fw + 0.5, (uv.y - fire.y) / fh);
        p.x += 0.012 * sin(p.y * 7.0 - t * 2.5 + uSeed) * p.y;
        p.x -= uWind * 0.25 * p.y * p.y;
        float sc = uFlame.w * (1.0 + 0.04 * uBassS * live + 0.02 * uBeatPulse);
        p = vec2((p.x - 0.5) / sc + 0.5, p.y / sc);
        vec4 fa = flameAnim(int(uFlame.x + 0.5), p);
        vec4 fb = flameAnim(int(uFlame.y + 0.5), p);
        vec4 fl = mix(fa, fb, uFlame.z);
        if (uFlameK.y > 0.01) {
            vec4 fx = flameAnim(3, p);
            fl = mix(fl, fx, uFlameK.y);
        }
        fl.a *= uFlameK.x;
        col = mix(col, fl.rgb, fl.a);
        col += fl.rgb * fl.a * (0.25 + 0.2 * uBassS * live);
        // Schein um die Flammen
        col += warm * exp(-fr * 9.0) * (0.08 + 0.25 * lv) * flick;
    }
    // ---- Kesseldampf
    {
        vec2 kq = (uv - uKettle) * vec2(aspect, 1.0);
        float up = kq.y / 0.18;
        if (up > 0.0 && up < 1.2) {
            float cx = 0.02 * sin(up * 6.0 + t * 1.2) + 0.03 * uWind * up;
            float body = exp(-pow((kq.x - cx) / (0.012 + 0.04 * up), 2.0)) * (1.0 - smoothstep(0.6, 1.2, up));
            float dens = noise(vec2(kq.x * 40.0, up * 6.0 - t * 1.5)) * 0.7 + 0.3;
            col = mix(col, vec3(0.8, 0.8, 0.85), body * dens * (0.08 + 0.2 * lv) * live);
        }
    }
    // ---- Funken (Sprites), Sternfunken leuchten
    for (int i = 0; i < 24; i++) {
        vec4 s = spAt(i);
        if (s.y < -5.0 || s.w <= 0.0) continue;
        vec2 d = (uv - s.xy) * vec2(aspect, 1.0) / s.w;
        vec4 c = sparkCell(s.z, d);
        if (c.a > 0.01) {
            col += c.rgb * c.a * (1.2 + 0.4 * uBassS);
        }
    }
    // ---- Motten um das Feuer
    for (int i = 0; i < 3; i++) {
        vec4 m = mothAt(i);
        if (m.w < 0.02) continue;
        vec2 d = (uv - m.xy) * vec2(aspect, 1.0) / 0.035;
        vec4 c = itemCell(m.z, d);
        col = mix(col, c.rgb * (1.0 + 0.5 * uHighS), c.a * m.w * 0.9);
        col += vec3(0.5, 0.6, 1.0) * exp(-dot(d, d) * 1.5) * 0.08 * m.w;
    }
    // ---- Gegenstände: fliegendes Holz, Marshmallow-Stock, Alien (unterhalb der Fußlinie abgeschnitten)
    for (int i = 0; i < 4; i++) {
        vec4 it = itemAt(i), ip = itemPAt(i);
        if (it.y < -5.0 || it.w <= 0.0 || ip.x < 0.01) continue;
        vec2 d = rot(ip.y) * ((uv - it.xy) * vec2(aspect, 1.0) / it.w);
        if (i == 3) {                                                          // Alien: Fußlinie = it.y, Zelle steht darauf
            d = (uv - it.xy) * vec2(aspect, 1.0) / it.w;
            d.y = d.y - 1.0 + 0.1;
            if (uv.y < it.y) continue;
        }
        vec4 c = itemCell(it.z, d);
        if (c.a > 0.01) {
            vec3 cc = c.rgb;
            if (i < 2) cc *= 0.6 + 0.6 * exp(-length((it.xy - fire) * vec2(aspect, 1.0)) * 4.0);   // nah am Feuer beleuchtet
            if (i == 2 && uMallow.x >= 0.0) cc += vec3(1.0, 0.5, 0.2) * 0.25 * lv * (0.5 + 0.5 * sin(t * 7.0));
            col = mix(col, cc, c.a * ip.x);
        }
    }
    // ---- Stille: alles kühler und dunkler, nur die Glut bleibt
    col *= 0.78 + 0.22 * live;
    col *= 1.0 - 0.25 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + max(col - 0.85, 0.0) * 0.8);
    fragColor = vec4(col, 1.0);
}
