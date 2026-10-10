#version 140
// Bord-Droide BIBO: Pixel-Droide in einem Hangar, tanzt zur Musik, Auge und Haltung zeigen die Laune.
// uState 0 idle, 1 hört, 2 denkt, 3 spricht, 4 lädt. uMood -1..1, uEnergy/uOil 0..1,
// uAction 1 ölen, 2 füttern, 3 schubsen (uActionT Sekunden seit der Aktion), uTalk 1 beim Sprechen.
in vec2 vUv;
out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float uRms, uBass, uMid, uHigh, uBeat, uSilent;
uniform sampler2D uAudioTex;
uniform float uState, uStateT, uLevel, uMood, uEnergy, uOil, uAction, uActionT, uTalk;

const float CELLS_Y = 108.0;
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float spec(float x) { return texture(uAudioTex, vec2(clamp(x, 0.0, 1.0), 0.25)).r; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdBox(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }

void main() {
    float aspect = iResolution.x / iResolution.y;
    float cellsX = floor(CELLS_Y * aspect);
    vec2 cell = floor(vUv * vec2(cellsX, CELLS_Y));
    vec2 uv = (cell + 0.5) / vec2(cellsX, CELLS_Y);
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y);
    float t = iTime;
    float live = 1.0 - uSilent;
    float beat = uBeat * live;
    int st = int(uState + 0.5);
    float talking = uTalk;
    float act = uAction;
    float at = uActionT;
    float actOn = step(0.0, at) * step(at, 2.2) * step(0.5, act);
    float shove = actOn * step(2.5, act);
    float mood = uMood;

    // ---- Hangar: Boden mit Gitter, Rückwand mit Panels, zwei Scheinwerfer
    vec3 col = vec3(0.03, 0.035, 0.05);
    float groundY = 0.26;
    if (uv.y < groundY) {
        float depth = (groundY - uv.y) / groundY;
        float gx = step(0.93, fract(p.x / (0.08 + depth * 0.25) + 0.5));
        float gy = step(0.9, fract(depth * depth * 12.0));
        col = mix(vec3(0.06, 0.07, 0.09), vec3(0.12, 0.14, 0.2), max(gx, gy) * 0.8);
        col *= 0.6 + 0.4 * depth;
    } else {
        col = mix(vec3(0.04, 0.045, 0.07), vec3(0.08, 0.09, 0.13), smoothstep(0.26, 1.0, uv.y));
        // Panels mit Lämpchen, die zum Spektrum blinken
        vec2 pc = floor(vec2(p.x * 6.0 + 10.0, uv.y * 7.0));
        float panel = step(0.5, hash12(pc + 3.0)) * step(0.55, uv.y) * step(abs(p.x), 0.85) * step(0.35, abs(p.x));
        vec2 pl = fract(vec2(p.x * 6.0 + 10.0, uv.y * 7.0));
        float frame = step(0.05, pl.x) * step(pl.x, 0.95) * step(0.08, pl.y) * step(pl.y, 0.92);
        col = mix(col, vec3(0.07, 0.08, 0.11), panel * frame);
        float lamp = step(abs(pl.x - 0.5), 0.08) * step(abs(pl.y - 0.3), 0.05) * panel;
        float lampOn = step(0.5, spec(fract(hash12(pc) * 3.0)) * 2.0 + hash12(pc + floor(t * 2.0)) * 0.5);
        col += mix(vec3(0.1, 0.5, 0.2), vec3(0.9, 0.3, 0.2), hash12(pc + 7.0)) * lamp * lampOn;
        // Scheinwerferkegel
        float beamL = smoothstep(0.08, 0.0, abs(p.x + 0.45 - (uv.y - 1.0) * 0.5)) * smoothstep(1.0, 0.3, uv.y);
        float beamR = smoothstep(0.08, 0.0, abs(p.x - 0.45 + (uv.y - 1.0) * 0.5)) * smoothstep(1.0, 0.3, uv.y);
        col += vec3(0.25, 0.22, 0.3) * (beamL + beamR) * (0.5 + 0.5 * beat) * 0.6;
    }

    // ---- Droide: Position tanzt zur Musik
    float bob = 0.02 * sin(t * 6.0) * beat + 0.012 * sin(t * 2.2) * live;
    float sway = 0.04 * sin(t * 1.4) * (0.5 + uMid * live) + shove * 0.12 * sin(at * 14.0) * exp(-at * 1.5);
    float tilt = 0.08 * sin(t * 1.4) * uMid * live + shove * 0.35 * sin(at * 14.0) * exp(-at * 1.5);
    float droop = (1.0 - uEnergy) * 0.03;                       // müde: hängt
    vec2 base = vec2(sway, groundY + bob - droop);
    vec2 q = p - base;                                           // lokale Koordinaten (Füße bei y=0)
    q = rot(tilt) * q;
    vec3 body = vec3(0.78, 0.8, 0.86);
    vec3 dark = vec3(0.25, 0.27, 0.33);
    vec3 accent = mix(vec3(0.95, 0.55, 0.1), vec3(0.3, 0.8, 1.0), 0.5 + 0.5 * mood);
    vec3 eyeCol = mix(mix(vec3(1.0, 0.2, 0.15), vec3(0.3, 0.75, 1.0), smoothstep(-0.6, 0.0, mood)), vec3(0.4, 1.0, 0.4), smoothstep(0.1, 0.8, mood));
    float d = 1.0;
    // Füße/Rollen
    float feet = step(sdBox(q - vec2(-0.09, 0.03), vec2(0.06, 0.03)), 0.0) + step(sdBox(q - vec2(0.09, 0.03), vec2(0.06, 0.03)), 0.0);
    // Beine
    float legs = step(sdBox(q - vec2(-0.08, 0.1), vec2(0.02, 0.06)), 0.0) + step(sdBox(q - vec2(0.08, 0.1), vec2(0.02, 0.06)), 0.0);
    // Körper (Tonne) und Bauchplatte
    float torso = step(sdBox(q - vec2(0.0, 0.3), vec2(0.15, 0.16)), 0.0);
    float belly = step(sdBox(q - vec2(0.0, 0.29), vec2(0.08, 0.07)), 0.0);
    // Arme (schwingen beim Tanzen)
    float armA = sin(t * 6.0) * beat * 0.5 + 0.2 * sin(t * 1.5);
    vec2 qa = rot(armA) * (q - vec2(-0.17, 0.4)) ;
    vec2 qb = rot(-armA) * (q - vec2(0.17, 0.4));
    float arms = step(sdBox(qa - vec2(-0.02, -0.07), vec2(0.022, 0.08)), 0.0) + step(sdBox(qb - vec2(0.02, -0.07), vec2(0.022, 0.08)), 0.0);
    // Kopf: Kuppel, dreht leicht mit den Mitten
    float headTurn = 0.03 * sin(t * 2.0) * uMid * live;
    vec2 qh = q - vec2(headTurn, 0.46);
    float head = step(length(qh * vec2(1.0, 1.25)), 0.17) * step(0.0, qh.y);
    float neck = step(sdBox(q - vec2(0.0, 0.47), vec2(0.17, 0.02)), 0.0);
    // Auge: Linse, Pupille schaut zum Pegel, Lid bei wenig Energie
    vec2 qe = qh - vec2(0.0, 0.08);
    float eye = step(length(qe * vec2(1.0, 1.2)), 0.065);
    float pupilX = 0.012 * sin(t * 0.7) + 0.015 * (uLevel - 0.5) * step(0.5, uState) * step(uState, 1.5);
    float pupil = step(length((qe - vec2(pupilX, 0.0)) * vec2(1.0, 1.2)), 0.03);
    float lid = step(qe.y, 0.065 - (1.0 - uEnergy) * 0.09);        // müde Augen
    float blink = step(0.97, fract(t * 0.23)) ;
    // Antenne mit Blinklicht
    float antenna = step(sdBox(qh - vec2(0.0, 0.2), vec2(0.008, 0.05)), 0.0);
    float tip = step(length(qh - vec2(0.0, 0.26)), 0.018);
    // Mundgitter: Balken schwingen beim Sprechen mit dem Pegel
    float mouthY = 0.31;
    float grille = 0.0;
    for (int i = -2; i <= 2; i++) {
        float fi = float(i);
        float hgt = 0.012 + 0.03 * talking * spec(0.2 + 0.15 * (fi + 2.0)) * (0.5 + 0.5 * sin(t * 25.0 + fi));
        grille += step(sdBox(q - vec2(fi * 0.03, mouthY), vec2(0.009, hgt)), 0.0);
    }
    // Ohrschüsseln leuchten beim Hören
    float ears = step(sdBox(qh - vec2(-0.19, 0.03), vec2(0.015, 0.035)), 0.0) + step(sdBox(qh - vec2(0.19, 0.03), vec2(0.015, 0.035)), 0.0);
    float listening = step(0.5, uState) * step(uState, 1.5);
    float thinking = step(1.5, uState) * step(uState, 2.5);

    // Zeichnen, von hinten nach vorn
    col = mix(col, dark, clamp(feet + legs, 0.0, 1.0));
    col = mix(col, body, torso);
    col = mix(col, dark * 1.3, belly);
    col = mix(col, accent, belly * step(abs(q.y - 0.29), 0.012) * step(abs(q.x), 0.06 * uEnergy));   // Energiebalken
    col = mix(col, body * 0.9, clamp(arms, 0.0, 1.0));
    col = mix(col, dark, neck);
    col = mix(col, body, head);
    col = mix(col, mix(dark, accent, listening * (0.5 + 0.5 * sin(t * 10.0))), clamp(ears, 0.0, 1.0) * head);
    col = mix(col, dark, eye);
    col = mix(col, eyeCol * (0.8 + 0.5 * beat + 0.4 * thinking * step(0.5, fract(t * 6.0))), pupil * lid * (1.0 - blink));
    col = mix(col, dark, antenna);
    col = mix(col, mix(vec3(0.3), vec3(1.0, 0.3, 0.2), step(0.5, fract(t * (1.0 + 3.0 * thinking)))), tip);
    col = mix(col, mix(dark * 0.6, accent, talking), grille);
    // Mundwinkel: Laune (fröhlich = Balken, mies = zwei Punkte)
    float smile = step(sdBox(q - vec2(0.0, mouthY - 0.045), vec2(0.05 + 0.03 * mood, 0.006)), 0.0) * step(0.0, mood);
    float frown = (step(length(q - vec2(-0.05, mouthY - 0.05)), 0.01) + step(length(q - vec2(0.05, mouthY - 0.05)), 0.01)) * step(mood, 0.0);
    col = mix(col, accent, (smile + frown) * torso);
    // Glanz
    col += vec3(0.12) * head * smoothstep(0.1, 0.17, qh.x + qh.y);
    // Öl-Glanz am Körper je nach Ölstand, Rost bei wenig Öl
    float rust = step(0.6, noise(q * 40.0)) * smoothstep(0.5, 0.0, uOil) * torso;
    col = mix(col, vec3(0.45, 0.25, 0.12), rust * 0.7);

    // ---- Aktionen
    if (actOn > 0.5) {
        if (act < 1.5) {           // Öl: Tropfen fallen auf den Kopf, Funkeln
            for (int i = 0; i < 5; i++) {
                float fi = float(i);
                float dy = 0.9 - fract(at * 0.9 + fi * 0.2) * 0.5;
                vec2 dp = vec2(base.x + (fi - 2.0) * 0.03, dy);
                col = mix(col, vec3(0.9, 0.8, 0.3), step(length((p - dp) * vec2(1.0, 0.6)), 0.012) * step(0.62, dy));
            }
            float sparkle = step(0.985, hash12(cell + floor(t * 12.0))) * step(sdBox(q - vec2(0.0, 0.35), vec2(0.25, 0.35)), 0.0);
            col += vec3(1.0) * sparkle;
        } else if (act < 2.5) {    // Futter: Batterie fliegt in den Bauch
            float k = smoothstep(0.0, 1.2, at);
            vec2 bp = mix(vec2(-0.6, 0.6), base + vec2(0.0, 0.29), k);
            float bat = step(sdBox(p - bp, vec2(0.04, 0.02)), 0.0) * (1.0 - step(0.99, k));
            col = mix(col, vec3(0.2, 0.9, 0.3), bat);
            col += vec3(0.3, 1.0, 0.4) * step(0.99, k) * exp(-(at - 1.2) * 3.0) * torso * 0.5;
        } else {                   // Schubsen: Ausrufezeichen und Funken
            float ex = step(sdBox(q - vec2(0.3, 0.6), vec2(0.015, 0.05)), 0.0) + step(length(q - vec2(0.3, 0.52)), 0.018);
            col = mix(col, vec3(1.0, 0.25, 0.2), ex * step(0.5, fract(at * 6.0)));
            float sp = step(0.99, hash12(cell + floor(t * 20.0))) * step(length(q - vec2(0.0, 0.4)), 0.35);
            col += vec3(1.0, 0.6, 0.2) * sp;
        }
    }
    // Laden: nur Silhouette mit Scanlinie
    float loading = step(3.5, uState);
    col = mix(col, col * 0.4 + vec3(0.1, 0.4, 0.2) * step(abs(uv.y - fract(t * 0.5)), 0.01), loading);
    // Bodenreflexion des Droiden
    col += accent * 0.05 * step(uv.y, groundY) * smoothstep(0.3, 0.0, abs(p.x - base.x)) * (0.6 + 0.4 * beat);

    col *= 0.92 + 0.08 * sin(vUv.y * iResolution.y * 3.14159 * 0.5);
    col *= 1.0 - 0.3 * smoothstep(0.7, 1.6, length(vUv * 2.0 - 1.0));
    fragColor = vec4(col, 1.0);
}
