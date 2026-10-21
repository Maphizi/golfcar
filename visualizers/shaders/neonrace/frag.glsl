#version 140
// Neonfahrt: Windschutzscheiben-Foto (uSceneTex) mit Fahrt: Straßen-Lichtstreifen laufen mit uDist/uSpeed auf die
// Kamera zu, Regen auf der Scheibe (Höhen funkeln, Wischer uWiperT), Neon im Foto pulst mit dem Bass und blitzt auf
// den Beat, Hologramme (uHoloN: Zelle, Seite, z, Seed) und Verkehr (uCarN: Zelle, Spur, z; uFlyN) kommen aus dem
// Fluchtpunkt uVanish. Spurwechsel uLane kippt das Bild, Nitro uNitro = Lichttunnel, Rückspiegel uMirror, Ereignisse uEvent.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform sampler2D uSceneTex, uHoloTex, uTrafficTex;
uniform vec2 uSceneSize, uHoloSize, uTrafficSize, uVanish;
uniform float uSeed, uBassS, uMidS, uHighS, uEnergy, uLive, uBeatPulse, uBeatStep, uSpeed, uDist, uLane, uHonkT, uMirror;
uniform float uWiperT, uNitro, uEvent, uEventT, uEventLen, uDriving;
uniform vec4 uHolo0, uHolo1, uHolo2, uHolo3, uHolo4, uHolo5, uHolo6, uHolo7, uHolo8, uHolo9;
uniform vec4 uCar0, uCar1, uCar2, uCar3, uCar4, uCar5;
uniform vec4 uFly0, uFly1, uFly2, uFly3, uFly4, uFly5;
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
vec3 scene(vec2 uv) { return bilin(uSceneTex, clamp(uv, 0.0, 1.0) * uSceneSize, uSceneSize, vec2(0.0), uSceneSize - 1.0).rgb; }
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
vec4 holoAt(int i) { return i == 0 ? uHolo0 : (i == 1 ? uHolo1 : (i == 2 ? uHolo2 : (i == 3 ? uHolo3 : (i == 4 ? uHolo4 : (i == 5 ? uHolo5 : (i == 6 ? uHolo6 : (i == 7 ? uHolo7 : (i == 8 ? uHolo8 : uHolo9)))))))); }
vec4 carAt(int i) { return i == 0 ? uCar0 : (i == 1 ? uCar1 : (i == 2 ? uCar2 : (i == 3 ? uCar3 : (i == 4 ? uCar4 : uCar5)))); }
vec4 flyAt(int i) { return i == 0 ? uFly0 : (i == 1 ? uFly1 : (i == 2 ? uFly2 : (i == 3 ? uFly3 : (i == 4 ? uFly4 : uFly5)))); }
// Perspektive: z 0 (Fluchtpunkt) .. 1 (an der Kamera vorbei); Tiefe nichtlinear, damit es "beschleunigt"
float depth(float z) { return pow(z, 2.2); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float t = iTime;
    int ev = int(uEvent + 0.5);
    float ek = clamp(uEventT / max(uEventLen, 0.1), 0.0, 1.0);
    float env = smoothstep(0.0, 0.1, ek) * smoothstep(1.0, 0.9, ek);
    vec2 van = uVanish;
    // Kamera: Spurwechsel kippt und verschiebt, Bass vibriert, Nitro zieht nach vorn
    vec2 uv = vUv;
    uv = van + rot(0.04 * uLane) * (uv - van);
    uv.x += 0.03 * uLane;
    uv += vec2(0.002 * sin(t * 90.0), 0.0025 * cos(t * 70.0)) * uBassS * uSpeed * uLive;
    uv = van + (uv - van) * (1.0 - 0.08 * uNitro);
    vec3 col = scene(uv);
    vec3 plate = col;
    float lum = max(col.r, max(col.g, col.b));
    float sat = lum - min(col.r, min(col.g, col.b));
    float neon = smoothstep(0.35, 0.7, lum) * smoothstep(0.15, 0.4, sat);
    // ---- Straße: Lichtstreifen laufen mit der Fahrt auf die Kamera zu (unterer Bereich, perspektivisch)
    vec2 q = uv - van;
    float road = smoothstep(0.0, -0.03, q.y) * smoothstep(-0.32, -0.12, q.y);        // zwischen Horizont und Armaturenbrett
    float invz = 1.0 / max(-q.y, 0.004);                                                 // Tiefe
    float lanesX = q.x * invz;                                                           // Spurkoordinate
    float along = invz * 0.12 - uDist * 6.0;                                             // entlang der Straße
    float stripe = smoothstep(0.35, 0.0, abs(fract(along) - 0.5) - 0.2) * smoothstep(0.08, 0.0, abs(abs(lanesX) - 1.3));
    float dash = smoothstep(0.3, 0.0, abs(fract(along * 0.5) - 0.5) - 0.15) * smoothstep(0.05, 0.0, abs(lanesX - uLane * 0.0));
    float streak = (stripe * 0.5 + dash * 0.4) * road * uSpeed * (0.4 + 0.6 * uLive);
    col += mix(vec3(0.2, 0.9, 1.0), vec3(1.0, 0.3, 0.9), 0.5 + 0.5 * sin(along * 0.3 + uBeatStep)) * streak;
    // Pfützen-Reflexe laufen mit
    float refl = noise(vec2(lanesX * 2.0, along * 0.7)) * road * uSpeed * 0.25;
    col += plate * refl * 2.0;
    // ---- Neon pulst mit dem Bass und blitzt auf den Beat (Lichthupe: alles)
    float honk = uHonkT >= 0.0 ? exp(-uHonkT * 3.0) : 0.0;
    float flashMask = step(0.5, hash12(vec2(floor(uv.x * 14.0), floor(uv.y * 8.0) + uBeatStep)));
    col += col * neon * (0.4 * uBassS + 0.8 * uBeatPulse * flashMask + 1.5 * honk) * uLive;
    col += col * neon * 0.15 * (1.0 - uLive) * (0.5 + 0.5 * sin(t * 1.3 + uv.x * 5.0));
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
    // ---- Hologramme am Straßenrand, Autos auf der Straße, Flieger darüber (weit = klein, nah = groß)
    for (int i = 0; i < 10; i++) {
        vec4 h = holoAt(i);
        if (h.z < 0.0) continue;
        float d = depth(h.z);
        vec2 pos = van + vec2(h.y * (0.08 + 0.95 * d), 0.06 + 0.5 * d);
        float sz = (0.02 + 0.45 * d) * aspect * 0.5;
        vec2 l = (uv - pos) * vec2(aspect, 1.0) / sz;
        l.y += 0.2 * sin(t * 2.0 + h.w * 10.0) * d;
        vec4 s = holoCell(h.x, l);
        float flick = 0.7 + 0.3 * step(0.3, noise(vec2(t * 12.0 + h.w * 50.0, h.w)));
        s.rgb = hueShift(s.rgb, uNitro * 3.0 + 0.2 * sin(t + h.w));
        col += s.rgb * s.a * flick * (0.7 + 0.6 * uBeatPulse + honk) * smoothstep(0.0, 0.08, h.z) * (1.0 - smoothstep(0.9, 1.0, h.z));
    }
    for (int i = 0; i < 6; i++) {
        vec4 c = carAt(i);
        if (c.z < 0.0) continue;
        float d = depth(c.z);
        vec2 pos = van + vec2((c.y - uLane * 0.6) * (0.03 + 0.55 * d), -0.01 - 0.3 * d);
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
    // ---- Nitro: Lichttunnel aus Strahlen, Farben kippen, Ränder ziehen
    if (uNitro > 0.0) {
        float a = atan(vUv.y - van.y, (vUv.x - van.x) * aspect);
        float r = length((vUv - van) * vec2(aspect, 1.0));
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
