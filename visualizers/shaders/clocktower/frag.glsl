#version 140
// Der Uhrturm, neu: nah am Turm im Gewitter (uSceneTex), oben das leere Zifferblatt uClock (x, y, Radius in Bildbreiten),
// darunter 13 schiefe Fenster. Fensterkarte uWinTex: R = Fenster-Nr. x 16, G = Scheibe (weich), B = nächstes Fenster x 16,
// A = Lichtschein auf der Fassade. Je Fenster uWinA = Rechteck (x0, y0, x1, y1), uWinB = (Farbton, Sättigung, Stufe,
// gespiegelt + Wippen), uWinC = (Silhouette A, B, Überblendung, Versatz) aus uSilTex (8x3, Alpha = Schatten).
// Zeiger aus uHandTex (3 Zellen 128x512, Drehpunkt in der Mitte), uHands = Stunde, Minute, Sekunde in Umdrehungen.
// 22:04: uCrazy (Zifferblatt wird durchsichtig, Uhrwerk uGearTex dreht sich mit uGearRot, Funken, Beben), danach Blitz
// uBoltT (Einschlag, Sprünge im Glas, Weißblitz uFlash). Professor uDoc = (Zelle in uDocTex 8x2, Sichtbarkeit, klettert),
// uDocPos = Fußpunkt bzw. Kante. Zeitmaschine uCar = (x links, y Räder, Breite, Zelle in uCarTex 3x1, vormultipliziert),
// uCarT = (Alter, Tempo, fährt). Gewitter uStorm, ferne Blitze uFarBolt, Wetterleuchten uSheet, Kabel uCable/uCable2
// (Bezier) mit Funke uSparkT, Countdown uFinal, Nahaufnahme uZoom.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uWinTex, uSilTex, uDocTex, uHandTex, uGearTex, uCarTex;
uniform vec2 uSceneSize, uSilSize, uDocSize, uHandSize, uGearSize, uCarSize, uCable2;
uniform vec3 uClock, uHands;
uniform vec4 uCable, uSheet, uFarBolt, uDoc, uDocPos, uCar, uCarT;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uFlash, uClockT, uBoltT, uBoltSeed;
uniform float uCrazy, uGearRot, uStorm, uFinal, uSparkT, uZoom, uNWin;
uniform vec4 uWinA[15];
uniform vec4 uWinB[15];
uniform vec4 uWinC[15];
const float PI = 3.14159265;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 1.7; a *= 0.5; } return v; }
vec3 hsv(vec3 c) { vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0); return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y); }
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
// Zelle idx (Reihe 0 oben) eines Bogens mit grid Spalten/Reihen, q = 0..1 in der Zelle (y nach oben)
vec4 cellTex(sampler2D tex, vec2 size, vec2 grid, float idx, vec2 q) {
    if (idx < 0.0 || q.x <= 0.0 || q.x >= 1.0 || q.y <= 0.0 || q.y >= 1.0) return vec4(0.0);
    vec2 cell = size / grid;
    float ci = mod(idx, grid.x), ri = floor(idx / grid.x);
    vec2 lo = vec2(ci * cell.x, (grid.y - 1.0 - ri) * cell.y);
    return bilin(tex, lo + q * cell, size, lo, lo + cell - 1.0);
}
float segDist(vec2 p, vec2 a, vec2 b) {
    vec2 ab = b - a;
    float h = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
    return length(p - a - ab * h);
}
float bolt(vec2 p, vec2 a, vec2 b, float seed, float amp, int n) {
    float dmin = 1e3;
    vec2 prev = a;
    vec2 dir = normalize(b - a + 1e-5), nrm = vec2(-dir.y, dir.x);
    for (int i = 1; i <= 12; i++) {
        if (i > n) break;
        float f = float(i) / float(n);
        vec2 q = mix(a, b, f) + nrm * (hash12(vec2(float(i), seed)) - 0.5) * amp * sin(f * PI) * 1.3;
        dmin = min(dmin, segDist(p, prev, q));
        prev = q;
    }
    return dmin;
}
// Silhouette im Fenster i: Alpha (1 = Schatten)
float silAlpha(float cell, vec2 uv, vec4 A, float dx, float bob, float mirror, float aspect) {
    if (cell < 0.0) return 0.0;
    float h = (A.w - A.y) * 0.9;
    float w = h * (2.0 / 3.0) / aspect;
    float cx = 0.5 * (A.x + A.z) + dx * (A.z - A.x);
    vec2 q = vec2((uv.x - cx) / w + 0.5, (uv.y - A.y - (0.03 + bob) * (A.w - A.y)) / h);
    if (mirror > 0.5) q.x = 1.0 - q.x;
    return cellTex(uSilTex, uSilSize, vec2(8.0, 3.0), cell, q).a;
}
vec3 winLightCol(int i) { return hsv(vec3(uWinB[i].x, uWinB[i].y, 1.0)) * uWinB[i].z; }
vec3 windowAt(int i, vec2 uv, float aspect, float t) {
    vec4 A = uWinA[i], B = uWinB[i], C = uWinC[i];
    vec2 q = (uv - A.xy) / max(A.zw - A.xy, vec2(1e-4));
    vec3 lc = winLightCol(i);
    float lamp = exp(-dot((q - vec2(0.5, 0.82)) * vec2(1.3, 1.7), (q - vec2(0.5, 0.82)) * vec2(1.3, 1.7)));
    vec3 room = lc * (0.35 + 0.85 * lamp) * (0.92 + 0.08 * sin(q.x * 37.0 + float(i) * 3.0));   // Vorhangfalten
    float mirror = floor(B.w), bob = fract(B.w) * 0.025;
    float a = mix(silAlpha(C.x, uv, A, C.w, bob, mirror, aspect), silAlpha(C.y, uv, A, C.w, bob, mirror, aspect), C.z);
    room *= 1.0 - 0.9 * a;
    // Regen auf der Scheibe
    float drop = smoothstep(0.75, 1.0, noise(vec2(q.x * 18.0, q.y * 6.0 + t * 0.6 + float(i))));
    room += vec3(0.08, 0.09, 0.11) * drop * (0.4 + uStorm);
    return room;
}

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    float live = uLive;
    vec2 cc = uClock.xy;
    float R = uClock.z * aspect;                                                           // Radius in Bildhöhen
    float boltAge = uBoltT >= 0.0 ? uBoltT : 1e3;
    float boltK = boltAge < 1.4 ? exp(-boltAge * 2.2) * (0.6 + 0.4 * step(0.4, hash12(vec2(floor(t * 45.0), 7.0)))) : 0.0;
    // ---- Kamera: Nahaufnahme aufs Zifferblatt, Beben mit Bass, beim Verrücktspielen und beim Einschlag
    vec2 uv = mix(vUv, cc + (vUv - vec2(0.5, 0.56)) / 2.4, uZoom);
    float quake = 0.0018 * uBassS * uBassS * live + 0.005 * uCrazy * (0.5 + 0.5 * sin(t * 31.0)) + 0.012 * boltK;
    uv += vec2(hash12(vec2(floor(t * 50.0), 1.0)) - 0.5, hash12(vec2(floor(t * 50.0), 2.0)) - 0.5) * quake;
    uv += vec2(0.0008 * sin(t * 0.27), 0.0006 * cos(t * 0.19));
    vec3 plate = scene(uv);
    vec3 col = plate;
    float lum = max(plate.r, max(plate.g, plate.b));
    float skyM = smoothstep(0.012, 0.06, plate.b - plate.r) * smoothstep(0.35, 0.6, uv.y) * smoothstep(0.6, 0.25, lum);
    // ---- Himmel: Wolken glühen mit dem Bass, Wetterleuchten, ferne Blitze
    float cloud = fbm(vec2(uv.x * 3.0 + t * 0.015 * (1.0 + 2.0 * uStorm), uv.y * 4.0 - t * 0.006) + uSeed);
    col += vec3(0.45, 0.4, 0.75) * skyM * smoothstep(0.4, 0.8, cloud) * (0.06 + 0.4 * uBassS * uBassS * live + 0.1 * uStorm);
    float sheet = 0.0;
    if (uSheet.x < 0.9) {
        float fl = 0.7 + 0.3 * step(0.35, hash12(vec2(floor(t * 30.0), 3.0)));
        sheet = uSheet.z * exp(-uSheet.x * 5.0) * fl * smoothstep(0.7, 0.0, abs(uv.x - uSheet.y));
    }
    float farK = 0.0;
    if (uFarBolt.x < 0.6) {
        farK = uFarBolt.w * exp(-uFarBolt.x * 7.0) * (0.55 + 0.45 * step(0.4, hash12(vec2(floor(t * 40.0), 11.0))));
        vec2 p = uv * vec2(aspect, 1.0);
        vec2 a = vec2(uFarBolt.y * aspect, 1.05);
        vec2 b = vec2((uFarBolt.y + (hash12(vec2(uFarBolt.z, 3.0)) - 0.5) * 0.12) * aspect, 0.5 + 0.08 * hash12(vec2(uFarBolt.z, 4.0)));
        float d = bolt(p, a, b, uFarBolt.z, 0.09, 10);
        col += vec3(0.8, 0.85, 1.0) * (smoothstep(0.003, 0.0, d) * 1.6 + smoothstep(0.05, 0.0, d) * 0.4) * farK * skyM;
    }
    float storm_light = sheet * 0.9 + farK * 0.6 + boltK * 1.4;                            // Blitze erhellen alles bläulich
    col += vec3(0.75, 0.8, 1.0) * skyM * (0.5 + 0.5 * cloud) * storm_light;
    col += plate * vec3(0.55, 0.62, 0.85) * (1.0 - skyM) * (sheet * 0.25 + farK * 0.3 + boltK * 1.2);
    // ---- Fenster: Licht in eigener Farbe, Silhouetten, Lichtschein auf der Fassade
    {
        ivec2 ts = textureSize(uWinTex, 0);
        vec4 wm = texelFetch(uWinTex, ivec2(clamp(uv, 0.0, 0.9999) * vec2(ts)), 0);
        int id = int(wm.r * 255.0 / 16.0 + 0.5);
        int nid = int(wm.b * 255.0 / 16.0 + 0.5);
        float nw = uNWin;
        if (id > 0 && float(id) <= nw) {
            vec3 wc = windowAt(id - 1, uv, aspect, t);
            col = mix(col, wc + col * 0.15, wm.g);
        } else if (nid > 0 && float(nid) <= nw && wm.a > 0.01) {
            vec3 lc = winLightCol(nid - 1);
            col += (plate * 1.8 + 0.03) * lc * wm.a * 0.55;
        }
    }
    // ---- Regen: schräge Streifen, im Gewitter dichter und schräger
    {
        vec2 rp = vec2(uv.x * aspect + uv.y * (0.15 + 0.3 * uStorm), uv.y);
        float colX = floor(rp.x * 170.0);
        float speed = 2.4 + 1.4 * hash12(vec2(colX, 5.0));
        float ry = fract(rp.y * 2.5 + t * speed + hash12(vec2(colX, 6.0)));
        float streak = smoothstep(0.0, 0.08, ry) * smoothstep(0.3, 0.09, ry) * step(0.6 - 0.3 * uStorm, hash12(vec2(colX, floor(rp.y * 2.5 + t * speed) + 9.0)));
        float rain = streak * smoothstep(0.5, 0.0, abs(fract(rp.x * 170.0) - 0.5));
        col += vec3(0.6, 0.7, 0.9) * rain * (0.04 + 0.2 * uHighS * live + 0.25 * uStorm + 0.3 * storm_light);
    }
    // ---- Kabel (Bezier vom Sims zur Laterne): Funke läuft hinunter, im Countdown knistert es
    {
        vec2 p = uv * vec2(aspect, 1.0);
        vec2 P0 = uCable.xy * vec2(aspect, 1.0), P1 = uCable.zw * vec2(aspect, 1.0), P2 = uCable2 * vec2(aspect, 1.0);
        float dmin = 1e3, sPar = 0.0;
        vec2 prev = P0;
        for (int i = 1; i <= 14; i++) {
            float f = float(i) / 14.0;
            vec2 q = mix(mix(P0, P1, f), mix(P1, P2, f), f);
            float dd = segDist(p, prev, q);
            if (dd < dmin) { dmin = dd; sPar = f; }
            prev = q;
        }
        float halo = smoothstep(0.03, 0.0, dmin);
        float crackle = uFinal * step(0.55, hash12(vec2(floor(t * 22.0), floor(sPar * 10.0))));
        float pulse = uSparkT < 1.6 ? exp(-abs(sPar - uSparkT / 1.3) * 25.0) : 0.0;
        col += vec3(1.0, 0.75, 0.4) * halo * (0.5 * crackle + 1.2 * pulse + 0.6 * boltK);
        col += vec3(0.7, 0.85, 1.0) * smoothstep(0.004, 0.0, dmin) * (crackle + 2.0 * pulse);
    }
    // ---- Zifferblatt: leuchtet mit dem Bass, beim Verrücktspielen wird es durchsichtig und das Uhrwerk dreht sich
    {
        vec2 d = (uv - cc) * vec2(aspect, 1.0) / R;
        float r = length(d);
        float face = smoothstep(1.0, 0.96, r);
        if (r < 1.25) {
            float stopped = (boltAge < 10.0) ? 1.0 : 0.0;
            col += plate * face * (0.1 * uBassS * live + 0.25 * uFinal * (0.5 + 0.5 * sin(t * 6.283)) + 0.3 * stopped * (0.5 + 0.5 * sin(t * 2.0)));
            float gearK = max(uCrazy, stopped * exp(-boltAge * 0.25) * 0.5);
            if (gearK > 0.01) {
                float flick = 0.6 + 0.4 * step(0.3, hash12(vec2(floor(t * 18.0), 5.0)));
                float ang = r < 0.48 ? uGearRot : -uGearRot * 0.55;          // innen und außen gegenläufig
                vec2 gq = rot(ang) * d;
                vec4 g = bilin(uGearTex, (gq * 0.5 + 0.5) * uGearSize, uGearSize, vec2(0.0), uGearSize - 1.0);
                vec3 gc = g.rgb * (0.75 + 0.6 * uBassS + 0.5 * flick * uCrazy) + vec3(0.12, 0.08, 0.02) * uCrazy;
                col = mix(col, gc, face * g.a * gearK * (0.5 + 0.4 * flick));
            }
            // Sprünge im Glas nach dem Einschlag (vom Einschlagpunkt oben)
            if (boltAge < 12.5) {
                vec2 o = d - vec2(0.15, 0.85);
                float crack = 0.0;
                for (int k = 0; k < 7; k++) {
                    float a = hash12(vec2(float(k), uBoltSeed)) * 2.0 * PI;
                    vec2 dir = vec2(cos(a), sin(a));
                    float along = dot(o, dir);
                    float across = abs(dot(o, vec2(-dir.y, dir.x)) + 0.05 * (noise(vec2(along * 9.0, float(k) * 3.0)) - 0.5));
                    float len = 0.6 + 0.9 * hash12(vec2(float(k), uBoltSeed + 1.0));
                    crack = max(crack, smoothstep(0.012, 0.0, across) * step(0.0, along) * step(along, len));
                }
                float ck = face * crack * smoothstep(12.5, 10.0, boltAge);
                col = mix(col, col * 0.3, ck * 0.8);
                col += vec3(0.8, 0.9, 1.0) * ck * 0.15;
            }
            // Zeiger mit Schatten: Stunde, Minute, Sekunde
            float pxr = 250.0 / 0.86;                                                      // Zellpixel je Radius
            vec2 sh = vec2(0.035, -0.045);
            for (int k = 0; k < 3; k++) {
                float turns = k == 0 ? uHands.x : (k == 1 ? uHands.y : uHands.z);
                float a = turns * 2.0 * PI;
                vec2 ds = d - sh;
                vec2 hs = vec2(ds.x * cos(a) - ds.y * sin(a), ds.x * sin(a) + ds.y * cos(a));
                vec4 s = cellTex(uHandTex, uHandSize, vec2(3.0, 1.0), float(k), (vec2(64.0, 256.0) + hs * pxr) / vec2(128.0, 512.0));
                col = mix(col, col * 0.45, s.a * 0.6 * face);
            }
            for (int k = 0; k < 3; k++) {
                float turns = k == 0 ? uHands.x : (k == 1 ? uHands.y : uHands.z);
                float a = turns * 2.0 * PI;
                vec2 hp = vec2(d.x * cos(a) - d.y * sin(a), d.x * sin(a) + d.y * cos(a));
                vec4 s = cellTex(uHandTex, uHandSize, vec2(3.0, 1.0), float(k), (vec2(64.0, 256.0) + hp * pxr) / vec2(128.0, 512.0));
                vec3 hc = s.rgb * (0.85 + 0.4 * uBassS * live + 1.2 * boltK + 0.4 * storm_light);
                col = mix(col, hc, s.a);
            }
            // Funken am Rand, wenn die Uhr verrückt spielt
            if (uCrazy > 0.01) {
                for (int k = 0; k < 14; k++) {
                    float fk = float(k);
                    float slot = floor(t * 6.0 + fk * 0.37);
                    float age = fract(t * 6.0 + fk * 0.37) / 6.0;
                    float a = hash12(vec2(slot, fk)) * 2.0 * PI;
                    vec2 sp = vec2(cos(a), sin(a)) * (1.0 + age * 2.2) + vec2(0.0, -age * age * 6.0);
                    float on = step(0.35, hash12(vec2(slot, fk + 9.0))) * uCrazy;
                    col += vec3(1.0, 0.8, 0.45) * smoothstep(0.035, 0.0, length(d - sp)) * on * (1.0 - age * 5.0);
                }
            }
        }
    }
    // ---- Blitz beim Einschlag: vom Himmel in die Turmspitze über dem Zifferblatt
    if (boltK > 0.0) {
        vec2 p = uv * vec2(aspect, 1.0);
        vec2 top = vec2(cc.x * aspect + (hash12(vec2(uBoltSeed, 1.0)) - 0.5) * 0.9, 1.1);
        vec2 hit = vec2(cc.x * aspect + 0.15 * R, cc.y + 0.85 * R);
        float d1 = bolt(p, top, hit, uBoltSeed, 0.16, 12);
        vec2 m1 = mix(top, hit, 0.45);
        float d2 = bolt(p, m1, m1 + vec2(0.3 * (hash12(vec2(uBoltSeed, 2.0)) - 0.5), -0.2), uBoltSeed + 3.0, 0.1, 7);
        float dm = min(d1, d2 + 0.001);
        col += vec3(0.85, 0.9, 1.0) * (smoothstep(0.004, 0.0, dm) * 2.2 + smoothstep(0.08, 0.0, dm) * 0.5) * boltK;
        col += vec3(1.0) * smoothstep(0.12, 0.0, length(p - hit)) * boltK * 1.5;
    }
    // ---- Professor: klettert die Fassade hoch (Reihe 0), oben hängt oder steht er unter dem Zifferblatt (Reihe 1)
    if (uDoc.y > 0.01) {
        float idx = uDoc.x;
        float hgt = 0.27;
        float wid = hgt * (160.0 / 360.0) / aspect;
        bool hang = idx == 8.0 || idx == 9.0 || idx == 10.0 || idx == 14.0;
        float y0 = hang ? uDocPos.y - hgt * 0.94 : uDocPos.y - hgt * 0.04;
        vec2 q = vec2((uv.x - uDocPos.x) / wid + 0.5, (uv.y - y0) / hgt);
        vec4 s = cellTex(uDocTex, uDocSize, vec2(8.0, 2.0), idx, q);
        vec3 light = vec3(1.0, 0.9, 0.78) * (0.9 + 0.5 * storm_light + 0.25 * uBassS * live) + vec3(1.0) * boltK;   // Fensterlicht
        col = mix(col, s.rgb * light, smoothstep(0.08, 0.55, s.a) * uDoc.y);
    }
    // ---- Zeitmaschine: wartet im Countdown am Straßenrand (Blitzbögen), rast nach dem Einschlag mit Feuerspuren los
    if (uCar.x > -4.0) {
        float wcar = uCar.z;
        float hcar = wcar * aspect * (200.0 / 512.0);
        if (uCarT.z > 0.5) {                                                              // Feuerspuren auf der Straße
            float rear = uCar.x + 0.14 * wcar;
            float speed = max(uCarT.y, 0.05);
            if (uv.x < rear && uv.y < uCar.y + 0.035) {
                float ageX = (rear - uv.x) / speed;
                if (ageX < 4.0) {
                    float k = 1.0 - ageX / 4.0;
                    float fl = 0.5 + 0.5 * noise(vec2(uv.x * 90.0 - t * 12.0, t * 7.0));
                    float fy = min(abs(uv.y - (uCar.y + 0.006)), abs(uv.y - (uCar.y + 0.02)));
                    float line = smoothstep(0.006, 0.0, fy);
                    float flames = smoothstep(0.55, 1.0, noise(vec2(uv.x * 70.0, (uv.y - uCar.y) * 80.0 - t * 10.0))) * smoothstep(0.03, 0.0, fy);
                    vec3 fire = mix(vec3(1.0, 0.25, 0.03), vec3(1.0, 0.85, 0.35), fl);
                    col += fire * (line * 2.0 + flames * 1.4) * k * k * (0.6 + 0.4 * fl);
                }
            }
        }
        vec2 q = vec2((uv.x - uCar.x) / wcar, (uv.y - uCar.y + 0.004) / hcar);
        float cell = uCar.w;
        if (cell == 1.0) cell = step(0.45, hash12(vec2(floor(t * 14.0), 2.0)));           // Blitzbögen flackern
        vec4 s = cellTex(uCarTex, uCarSize, vec2(3.0, 1.0), cell, q);
        s *= smoothstep(0.0, 0.07, q.x) * smoothstep(1.0, 0.93, q.x) * smoothstep(1.0, 0.8, q.y);   // Zellränder weich
        col = col * (1.0 - s.a) + s.rgb * (1.0 + 0.4 * storm_light);
    }
    // ---- Weißblitz, Countdown-Rand, Stille, Vignette
    col += vec3(1.0) * uFlash * uFlash * 0.9;
    col *= 1.0 - 0.22 * uFinal * smoothstep(0.25, 0.75, length(vUv - 0.5));
    col *= 0.8 + 0.2 * live;
    col *= 1.0 - 0.25 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + max(col - 0.85, 0.0) * 0.8);
    fragColor = vec4(col, 1.0);
}
