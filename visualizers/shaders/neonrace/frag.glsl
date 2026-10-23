#version 140
// Neonfahrt: Windschutzscheiben-Foto (uSceneTex) mit Fahrt: Straßen-Lichtstreifen laufen mit uDist/uSpeed auf die
// Kamera zu (Beat uBoost = heller/schneller), Regen auf der Scheibe (Höhen funkeln, Wischer uWiperT), Neon im Foto
// pulst mit dem Bass, wechselt je Schild die Farbe auf den Beat (uBeatStep, Drop = uHueAll alle gemeinsam) und
// Lauflicht durch die Fassaden (uStep/uStepPhase/uPattern: Zonen links nah, links weit, rechts weit, rechts nah).
// Hologramme (uHoloN: Zelle, Seite, z, Seed; Höhen = Glitch), Verkehr (uCarN: Zelle, Spur, z; uFlyN) und
// Hindernisse (uObsN: Zelle, Spur/x, z, Seed; Zelle >= 8 = Querung) kommen aus dem Fluchtpunkt uVanish.
// Autopilot: uLane fließend, uLaneVel kippt das Bild beim Spurwechsel, uGraze/uNear (Alter, Seite) = Ruck/Streiflicht
// bzw. Blitz am Rand, Nitro uNitro = Lichttunnel, Rückspiegel uMirror, Ereignisse uEvent.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uSceneBTex, uHoloTex, uTrafficTex, uObsTex;
uniform vec2 uSceneSize, uSceneBSize, uHoloSize, uTrafficSize, uObsSize, uVanish;
uniform float uDistT, uDistMix;                    // Stadtteilwechsel: Alter des Lichttors (-1 = keins), Überblendung A -> B
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uBoost, uHueAll;
uniform float uStep, uStepPhase, uPattern;
uniform float uSpeed, uDist, uLane, uLaneVel, uAuto, uEvadeT, uHonkT, uMirror;
uniform vec2 uGraze, uNear;
uniform float uWiperT, uNitro, uEvent, uEventT, uEventLen, uDriving;
uniform vec4 uHolo0, uHolo1, uHolo2, uHolo3, uHolo4, uHolo5, uHolo6, uHolo7, uHolo8, uHolo9;
uniform vec4 uCar0, uCar1, uCar2, uCar3, uCar4, uCar5;
uniform vec4 uFly0, uFly1, uFly2, uFly3, uFly4, uFly5;
uniform vec4 uObs0, uObs1, uObs2, uObs3, uObs4, uObs5;
const float PI = 3.14159265;

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
vec3 sceneA(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0).rgb; }
vec3 sceneB(vec2 uv) { return bilin(uSceneBTex, clamp(uv, 0.0, 1.0) * uSceneBSize, uSceneBSize, vec2(0.0), uSceneBSize - 1.0).rgb; }
// Stadtteil: beim Lichttor blendet das Bild vom Fluchtpunkt nach außen in den nächsten Stadtteil über
vec3 scene(vec2 uv) {
    if (uDistMix <= 0.001) return sceneA(uv);
    if (uDistMix >= 0.999) return sceneB(uv);
    float rr = length((uv - uVanish) * vec2(iResolution.x / iResolution.y, 1.0));
    float k = smoothstep(uDistMix * 1.3 + 0.08, uDistMix * 1.3 - 0.08, rr);        // innen zuerst das neue Bild
    return mix(sceneA(uv), sceneB(uv), k);
}
vec4 holoCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 160.0, (2.0 - ri) * 160.0);
    return bilin(uHoloTex, lo + (d * 0.5 + 0.5) * 160.0, uHoloSize, lo, lo + 159.0);
}
vec4 trafficCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (1.0 - ri) * 192.0);
    return bilin(uTrafficTex, lo + (d * 0.5 + 0.5) * 192.0, uTrafficSize, lo, lo + 191.0);
}
vec4 obsCell(float idx, vec2 d) {
    if (abs(d.x) >= 1.0 || abs(d.y) >= 1.0 || uObsSize.x < 8.0) return vec4(0.0);
    float ci = mod(idx, 8.0), ri = floor(idx / 8.0);
    vec2 lo = vec2(ci * 192.0, (1.0 - ri) * 192.0);
    vec4 s = bilin(uObsTex, lo + (d * 0.5 + 0.5) * 192.0, uObsSize, lo, lo + 191.0);
    s.a *= smoothstep(0.03, 0.12, max(s.r, max(s.g, s.b)));                            // Schwarz = frei
    return s;
}
vec4 holoAt(int i) { return i == 0 ? uHolo0 : (i == 1 ? uHolo1 : (i == 2 ? uHolo2 : (i == 3 ? uHolo3 : (i == 4 ? uHolo4 : (i == 5 ? uHolo5 : (i == 6 ? uHolo6 : (i == 7 ? uHolo7 : (i == 8 ? uHolo8 : uHolo9)))))))); }
vec4 carAt(int i) { return i == 0 ? uCar0 : (i == 1 ? uCar1 : (i == 2 ? uCar2 : (i == 3 ? uCar3 : (i == 4 ? uCar4 : uCar5)))); }
vec4 flyAt(int i) { return i == 0 ? uFly0 : (i == 1 ? uFly1 : (i == 2 ? uFly2 : (i == 3 ? uFly3 : (i == 4 ? uFly4 : uFly5)))); }
vec4 obsAt(int i) { return i == 0 ? uObs0 : (i == 1 ? uObs1 : (i == 2 ? uObs2 : (i == 3 ? uObs3 : (i == 4 ? uObs4 : uObs5)))); }
// Perspektive: z 0 (Fluchtpunkt) .. 1 (an der Kamera vorbei); Tiefe nichtlinear, damit es "beschleunigt"
float depth(float z) { return pow(z, 2.2); }
// Lauflicht: aktive Zone 0..3 aus Schritt und Muster (wie beim Orakel)
float activeZone() {
    float s = uStep;
    if (uPattern < 0.5) return s;
    if (uPattern < 1.5) return s < 2.0 ? s : (s == 2.0 ? 2.0 : 1.0);
    if (uPattern < 2.5) return s == 0.0 ? 1.0 : (s == 1.0 ? 2.0 : (s == 2.0 ? 0.0 : 3.0));
    return floor(hash12(vec2(s, uSeed)) * 4.0);
}
// Position eines Objekts auf der Straße (Spureinheiten x, Tiefe d) und seine Größe
vec2 roadPos(float x, float d) { return uVanish + vec2((x - uLane * 0.6) * (0.03 + 0.55 * d), -0.01 - 0.3 * d); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    int ev = int(uEvent + 0.5);
    float ek = clamp(uEventT / max(uEventLen, 0.1), 0.0, 1.0);
    float env = smoothstep(0.0, 0.1, ek) * smoothstep(1.0, 0.9, ek);
    vec2 van = uVanish;
    float honk = uHonkT >= 0.0 ? exp(-uHonkT * 3.0) : 0.0;
    float graze = uGraze.x >= 0.0 ? exp(-uGraze.x * 4.0) : 0.0;
    float near = uNear.x >= 0.0 ? exp(-uNear.x * 2.5) : 0.0;
    // Kamera: Spurwechsel kippt (Winkel aus der Spurgeschwindigkeit) und verschiebt, Bass vibriert, Nitro zieht nach vorn,
    // Streifschuss/Beinahe-Treffer rucken
    vec2 uv = vUv;
    float tilt = 0.03 * uLane + 0.07 * clamp(uLaneVel, -1.5, 1.5);
    tilt += 0.04 * uGraze.y * graze * sin(uGraze.x * 18.0) + 0.09 * uNear.y * near * sin(uNear.x * 14.0);
    uv = van + rot(tilt) * (uv - van);
    uv.x += 0.03 * uLane + 0.015 * uGraze.y * graze + 0.03 * uNear.y * near * cos(uNear.x * 20.0);
    uv += vec2(0.002 * sin(t * 90.0), 0.0025 * cos(t * 70.0)) * uBassS * uSpeed * uLive;
    uv.y += 0.01 * near * sin(uNear.x * 30.0);
    uv = van + (uv - van) * (1.0 - 0.08 * uNitro - 0.02 * uBoost * uSpeed);
    vec3 col = scene(uv);
    vec3 plate = col;
    float lum = max(col.r, max(col.g, col.b));
    float sat = lum - min(col.r, min(col.g, col.b));
    float neon = smoothstep(0.35, 0.7, lum) * smoothstep(0.15, 0.4, sat);
    // ---- Schilder wechseln die Farbe: je Block eigener Hue-Versatz, springt auf jeden Beat weiter, Drop = alle
    // (weich interpolierte Zufallsfelder statt harter Blöcke, damit keine Kanten durch die Schilder laufen)
    float hueBlk = noise(uv * vec2(9.0, 5.0) + uSeed) * 9.0;
    float hueAng = hueBlk + uBeatStep * (0.3 + 1.0 * noise(uv * vec2(6.0, 4.0) + 7.0)) + uHueAll;
    col = mix(col, hueShift(col, hueAng), neon * uLive * 0.75);
    // ---- Straße: Lichtstreifen laufen mit der Fahrt auf die Kamera zu (unterer Bereich, perspektivisch)
    vec2 q = uv - van;
    float road = smoothstep(0.0, -0.03, q.y) * smoothstep(-0.32, -0.12, q.y);        // zwischen Horizont und Armaturenbrett
    float invz = 1.0 / max(-q.y, 0.004);                                                 // Tiefe
    float lanesX = q.x * invz;                                                           // Spurkoordinate
    float along = invz * 0.12 - uDist * 6.0;                                             // entlang der Straße
    float stripe = smoothstep(0.35, 0.0, abs(fract(along) - 0.5) - 0.2) * smoothstep(0.08, 0.0, abs(abs(lanesX) - 1.3));
    float dash = smoothstep(0.3, 0.0, abs(fract(along * 0.5) - 0.5) - 0.15) * smoothstep(0.05, 0.0, abs(lanesX));
    float streak = (stripe * 0.5 + dash * 0.4) * road * uSpeed * (0.4 + 0.6 * uLive) * (1.0 + 1.2 * uBoost);
    col += mix(vec3(0.2, 0.9, 1.0), vec3(1.0, 0.3, 0.9), 0.5 + 0.5 * sin(along * 0.3 + uBeatStep)) * streak;
    // Pfützen-Reflexe laufen mit
    float refl = noise(vec2(lanesX * 2.0, along * 0.7)) * road * uSpeed * 0.25;
    col += plate * refl * 2.0 * (1.0 + 0.5 * uBoost);
    // ---- Neon pulst mit dem Bass, Lauflicht durch die Fassaden auf den Beat (Lichthupe: alles), Höhen = Flackern
    float zone = q.x < 0.0 ? (abs(q.x) > 0.22 ? 0.0 : 1.0) : (abs(q.x) > 0.22 ? 3.0 : 2.0);
    float run = (zone == activeZone() ? 1.0 : 0.0) * (1.0 - 0.7 * uStepPhase) * smoothstep(-0.08, 0.02, q.y);
    float flick = 1.0 - 0.5 * uHighS * step(0.6, hash12(vec2(floor(uv.y * 60.0), floor(t * 24.0))));
    col += col * neon * (0.5 * uBassS + 0.9 * run + 0.3 * uBeatPulse + 1.5 * honk) * uLive * flick;
    col += col * neon * 0.15 * (1.0 - uLive) * (0.5 + 0.5 * sin(t * 1.3 + uv.x * 5.0));
    // ---- Lichttor in den nächsten Stadtteil: Lichtstreifen rasen aus dem Fluchtpunkt, Ränder dunkel, Weißblitz in der Mitte
    if (uDistT >= 0.0) {
        float dk = uDistT / 3.2;
        float gate = smoothstep(0.0, 0.25, dk) * smoothstep(1.0, 0.7, dk);
        vec2 gq = (uv - van) * vec2(aspect, 1.0);
        float ga = atan(gq.y, gq.x), gr = length(gq);
        float streaks = step(0.93, hash12(vec2(floor(ga * 40.0), 7.0))) * smoothstep(0.05, 0.3, gr)
                      * step(0.5, fract(gr * 6.0 - uDistT * 9.0 + hash12(vec2(floor(ga * 40.0), 9.0))));
        col = mix(col, col * 0.4, gate * smoothstep(0.1, 0.5, gr));
        col += mix(vec3(0.3, 0.9, 1.0), vec3(1.0, 0.4, 0.9), hash12(vec2(floor(ga * 40.0), 3.0))) * streaks * gate * 1.4;
        col += vec3(0.8, 0.95, 1.0) * exp(-gr * 6.0) * gate * 0.5;
        col += vec3(1.0) * exp(max(-pow((dk - 0.5) * 9.0, 2.0), -60.0)) * 0.7;        // Blitz beim Durchfahren
    }
    // ---- Ereignisse: Tunnel, Konzernturm, Sturm, Kirschblüten, Markt
    if (ev == 4) {                                                                       // Tunnel: Seiten dunkel, Lichtbänder
        float side = smoothstep(0.15, 0.45, abs(q.x));
        col = mix(col, col * 0.15, side * env);
        float band = smoothstep(0.1, 0.0, abs(fract(along * 0.25) - 0.5) - 0.05) * side;
        col += vec3(1.0, 0.8, 0.3) * band * env * (0.6 + 0.4 * uBeatPulse);
    } else if (ev == 5) {                                                                // Konzernturm: Lichtkegel von oben, Scan
        float scan = exp(-pow((uv.y - fract(uEventT * 0.3)) * 25.0, 2.0));
        col += vec3(0.9, 0.2, 0.3) * scan * env * 0.5;
        col += vec3(0.3, 0.1, 0.4) * smoothstep(0.5, 1.0, uv.y) * env * 0.4 * (0.5 + 0.5 * sin(t * 2.0));
    }
    // ---- Hologramme am Straßenrand: eigener Farbversatz je Schild (Beat), Höhen = Glitch (Zeilen reißen)
    for (int i = 0; i < 10; i++) {
        vec4 h = holoAt(i);
        if (h.z < 0.0) continue;
        float d = depth(h.z);
        vec2 pos = van + vec2(h.y * (0.08 + 0.95 * d), 0.06 + 0.5 * d);
        float sz = (0.02 + 0.45 * d) * aspect * 0.5;
        vec2 l = (uv - pos) * vec2(aspect, 1.0) / sz;
        l.y += 0.2 * sin(t * 2.0 + h.w * 10.0) * d;
        float rowT = floor(l.y * 12.0 + t * 30.0);
        float tear = step(0.75 - 0.2 * uHighS, hash12(vec2(rowT, h.w * 40.0 + floor(t * 10.0)))) * (0.3 + 0.9 * uHighS);
        l.x += (hash12(vec2(rowT, h.w)) - 0.5) * 0.5 * tear;
        vec4 s = holoCell(h.x, l);
        float flk = 0.7 + 0.3 * step(0.3, noise(vec2(t * 12.0 + h.w * 50.0, h.w))) - 0.3 * tear;
        float hue = uNitro * 3.0 + uHueAll + uBeatStep * (0.5 + 0.9 * h.w) + h.w * 6.2832;
        s.rgb = hueShift(s.rgb, hue);
        col += s.rgb * s.a * flk * (0.6 + 0.4 * uBassS + 0.6 * uBeatPulse + honk) * smoothstep(0.0, 0.08, h.z) * (1.0 - smoothstep(0.9, 1.0, h.z));
    }
    // ---- Hindernisse auf der Straße (Zelle 0-7, feste Spur) und Querungen (Zelle 8-15, x wandert)
    for (int i = 0; i < 6; i++) {
        vec4 o = obsAt(i);
        if (o.z < 0.0) continue;
        float d = depth(o.z);
        bool cross = o.x >= 8.0;
        vec2 pos = roadPos(o.y, d);
        float sz = (0.012 + 0.42 * d) * aspect * 0.5 * (cross ? 1.0 : 0.9);
        vec2 l = (uv - pos) * vec2(aspect, 1.0) / sz;
        if (cross) l.y += 0.08 * abs(sin(t * 9.0 + o.w * 20.0));                           // Querung hüpft/läuft
        l.y = l.y - 1.0 + 0.1;
        vec4 s = obsCell(o.x, l);
        s.rgb *= 0.75 + 0.35 * uBassS;
        if (o.x == 4.0 || o.x == 13.0) s.rgb = hueShift(s.rgb, uBeatStep * 0.8 + uHueAll) * (1.0 + 0.5 * uBeatPulse);   // Holo-Schild, Werbesäule
        if (o.x == 11.0) s.rgb += vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 5.0)) * 0.4 + vec3(0.1, 0.3, 1.0) * step(0.5, fract(t * 5.0 + 0.5)) * 0.4;
        float warn = smoothstep(0.55, 0.85, o.z) * (0.5 + 0.5 * sin(t * 18.0));          // nahe Hindernisse blinken im Warnlicht
        s.rgb += vec3(1.0, 0.5, 0.1) * warn * 0.25 * max(0.0, 1.0 - abs(o.y - uLane));
        col = mix(col, s.rgb, s.a * (1.0 - smoothstep(0.92, 1.0, o.z)));
        col += s.rgb * s.a * 0.25 * uBeatPulse;
    }
    // ---- Autos auf der Straße, Flieger darüber (weit = klein, nah = groß)
    for (int i = 0; i < 6; i++) {
        vec4 c = carAt(i);
        if (c.z < 0.0) continue;
        float d = depth(c.z);
        vec2 pos = roadPos(c.y, d);
        float sz = (0.015 + 0.5 * d) * aspect * 0.5;
        vec2 l = (uv - pos) * vec2(aspect, 1.0) / sz;
        l.y = l.y - 1.0 + 0.1;
        vec4 s = trafficCell(c.x, l);
        s.rgb *= 0.8 + 0.3 * uBassS;
        if (c.x == 4.0) s.rgb += vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 4.0)) * 0.4 + vec3(0.1, 0.2, 1.0) * step(0.5, fract(t * 4.0 + 0.5)) * 0.4;
        col = mix(col, s.rgb, s.a * (1.0 - smoothstep(0.92, 1.0, c.z)));
        col += s.rgb * s.a * 0.3 * uBeatPulse;
    }
    for (int i = 0; i < 6; i++) {
        vec4 fl = flyAt(i);
        if (fl.z < 0.0) continue;
        float d = depth(fl.z);
        vec2 pos = van + vec2(fl.y * (0.05 + 1.1 * d), 0.1 + 0.55 * d * (0.5 + 0.5 * fl.w) + 0.02 * sin(t * 2.0 + fl.w * 8.0));
        float sz = (0.01 + 0.3 * d) * aspect * 0.5 * (fl.x == 9.0 || fl.x == 15.0 ? 1.8 : 1.0);
        vec2 l = (uv - pos) * vec2(aspect, 1.0) / sz;
        if (fl.x == 12.0) l = rot(t * 2.0 + fl.w * 6.0) * l;                               // Kirschblüte dreht
        vec4 s = trafficCell(fl.x, l);
        if (fl.x == 8.0 || fl.x == 10.0 || fl.x == 14.0) s.rgb += vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 5.0 + fl.w)) * 0.5 + vec3(0.1, 0.3, 1.0) * step(0.5, fract(t * 5.0 + fl.w + 0.5)) * 0.5;
        col = mix(col, s.rgb * (0.9 + 0.3 * uBassS), s.a * (1.0 - smoothstep(0.9, 1.0, fl.z)));
    }
    // ---- Streiflicht (knapp vorbei) und Beinahe-Treffer: Lichtblitz am Rand der betroffenen Seite
    float edgeG = smoothstep(0.55, 1.0, vUv.x * uGraze.y + (uGraze.y < 0.0 ? 1.0 : 0.0));
    col += vec3(1.0, 0.9, 0.6) * edgeG * graze * 0.5;
    float edgeN = smoothstep(0.3, 1.0, vUv.x * uNear.y + (uNear.y < 0.0 ? 1.0 : 0.0));
    col += mix(vec3(1.0, 0.2, 0.2), vec3(1.0), step(0.5, fract(uNear.x * 10.0))) * edgeN * near * 0.9;
    col += vec3(1.0, 0.95, 0.9) * near * exp(-uNear.x * 12.0) * 0.6;                     // Blitz der fremden Scheinwerfer
    // ---- Regen auf der Scheibe: Tropfen (Höhen funkeln), Streifen schräger mit dem Tempo, Sturm = mehr
    float storm = ev == 3 ? env : 0.0;
    vec2 ruv = vUv;
    float slant = 0.3 + 0.9 * uSpeed;
    vec2 rp = vec2(ruv.x * 40.0 + ruv.y * slant * 20.0, ruv.y * 60.0 + t * (3.0 + 12.0 * uSpeed));
    float drops = smoothstep(0.93 - 0.05 * storm, 1.0, noise(rp)) * (0.5 + 0.5 * uHighS);
    float drops2 = smoothstep(0.96, 1.0, noise(vUv * 120.0 + vec2(0.0, -t * 0.3)));         // ruhende Tropfen
    col += vec3(0.7, 0.9, 1.0) * (drops * 0.5 + drops2 * 0.35 * (0.5 + uHighS));
    col += plate * drops2 * 0.5;
    // Scheibenwischer: zwei Bögen, wischen die Tropfen weg (dunkler Keil)
    float wa = sin(uWiperT * 2.0) * 0.9;                                                 // Winkel
    vec2 wc = vec2(0.35, -0.3);
    float ang = atan(vUv.y - wc.y, (vUv.x - wc.x) * aspect);
    float wiper = smoothstep(0.03, 0.0, abs(ang - (1.2 + wa * 0.8))) * smoothstep(0.1, 0.3, length((vUv - wc) * vec2(aspect, 1.0)));
    col = mix(col, col * 0.5, wiper * 0.8 * uDriving);
    // ---- Beat-Schub: Lichtstrahlen aus dem Fluchtpunkt, kurz und schwach; Nitro: Lichttunnel, Farben kippen
    float a = atan(vUv.y - van.y, (vUv.x - van.x) * aspect);
    float r = length((vUv - van) * vec2(aspect, 1.0));
    if (uBoost > 0.0) {
        float rays = pow(0.5 + 0.5 * sin(a * 16.0 - t * 12.0), 8.0) * smoothstep(0.2, 0.7, r);
        col += vec3(0.4, 0.9, 1.0) * rays * uBoost * uSpeed * 0.25 * uLive;
    }
    if (uNitro > 0.0) {
        float rays = pow(0.5 + 0.5 * sin(a * 24.0 + t * 20.0), 6.0) * smoothstep(0.1, 0.6, r);
        col += vec3(1.0, 0.8, 0.4) * rays * uNitro * 0.3;
        col = mix(col, hueShift(col, uNitro * 2.0), uNitro * 0.35);
    }
    // ---- Rückspiegel: Einblendung oben rechts, gespiegelte Straße mit Verfolgern
    if (uMirror > 0.01) {
        vec2 mr = vec2(0.72, 0.84);
        vec2 msz = vec2(0.22, 0.1) * uMirror;
        vec2 md = (vUv - mr) / msz;
        if (abs(md.x) < 1.0 && abs(md.y) < 1.0) {
            vec2 muv = vec2(1.0 - (md.x * 0.5 + 0.5), 0.3 + 0.35 * (md.y * 0.5 + 0.5));
            vec3 m = scene(muv) * 0.7;
            float chase = ev == 1 ? env : 0.3;
            vec2 cp = vec2(0.0 + 0.3 * sin(t * 0.7), -0.2);
            vec4 s = trafficCell(4.0, (md - cp) / vec2(0.5, 0.5));
            s.rgb += vec3(1.0, 0.1, 0.1) * step(0.5, fract(t * 4.0)) * 0.6 + vec3(0.1, 0.2, 1.0) * step(0.5, fract(t * 4.0 + 0.5)) * 0.6;
            m = mix(m, s.rgb, s.a * chase);
            float frame = smoothstep(1.0, 0.92, max(abs(md.x), abs(md.y)));
            col = mix(col, m, frame);
            col += vec3(0.3, 0.8, 1.0) * (1.0 - frame) * smoothstep(1.1, 1.0, max(abs(md.x), abs(md.y))) * 0.6;
        }
    }
    // ---- Autopilot-Anzeige: schmaler Spurbalken unten, Marker = Spur, blinkt beim Ausweichen
    if (uDriving > 0.5) {
        vec2 bp = vec2(0.5, 0.135);
        float bar = smoothstep(0.004, 0.0, abs(vUv.y - bp.y)) * smoothstep(0.13, 0.11, abs(vUv.x - bp.x));
        float mark = smoothstep(0.012, 0.004, length((vUv - vec2(bp.x + uLane * 0.1, bp.y)) * vec2(aspect, 1.0)));
        vec3 bc = uAuto > 0.5 ? vec3(0.3, 1.0, 0.7) : vec3(1.0, 0.8, 0.3);
        float ev_k = uEvadeT >= 0.0 ? 0.5 + 0.5 * sin(uEvadeT * 25.0) : 0.0;
        col += bc * (bar * 0.35 + mark * 0.8) * (0.6 + 0.4 * ev_k);
    }
    // ---- Polizeidrohnen: Rot-Blau-Flackern über dem ganzen Bild
    if (ev == 1) {
        col += (vec3(0.6, 0.0, 0.0) * step(0.5, fract(t * 3.0)) + vec3(0.0, 0.1, 0.6) * step(0.5, fract(t * 3.0 + 0.5))) * env * 0.15;
    }
    // ---- Kirschblüten: rosa Schleier
    if (ev == 7) col = mix(col, col * vec3(1.2, 0.9, 1.1) + vec3(0.1, 0.02, 0.06), env * 0.4);
    // ---- Stillstand: Motor aus, Regen bleibt, Neon atmet langsam
    col = mix(col * 0.8, col, uDriving * 0.5 + 0.5);
    col *= 0.75 + 0.25 * uLive;
    col *= 1.0 - 0.25 * pow(length(vUv - 0.5) * 1.3, 2.5);
    col = col / (1.0 + col * 0.15);
    fragColor = vec4(col, 1.0);
}
