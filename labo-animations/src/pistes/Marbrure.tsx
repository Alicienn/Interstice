/**
 * Marbrure — un champ d'encre liquide, calculé entièrement dans un shader (papier marbré).
 *
 * Le débit de tokens pilote la turbulence ; chaque appel d'outil lance une onde dans l'encre.
 * À la rédaction, l'encre se retire vers le haut pour dégager la page ; chaque nouveau mot
 * émerge à travers un filtre de déformation liquide avant de se figer.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { Reponse } from "../commun";
import { useShader } from "../shader";
import { amortir, lisse, useHorlogeScene } from "../horloge";
import { debit, dureeLisible, nf, type Prepare } from "../scenario";

const MAX_ONDES = 6;

const vertex = /* glsl */ `
  void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

const fragment = /* glsl */ `
  precision highp float;
  uniform vec2 uRes;
  uniform float uTemps;
  uniform float uEnergie;
  uniform float uEcriture;
  uniform float uFin;
  uniform vec4 uOndes[${MAX_ONDES}];
  uniform vec3 uFond;
  uniform vec3 uEncre;
  uniform vec3 uEncreVive;
  uniform vec3 uReflet;

  float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
  float bruit(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    mat2 r = mat2(0.8, 0.6, -0.6, 0.8);
    for (int i = 0; i < 6; i++) { v += a * bruit(p); p = r * p * 2.02 + 3.1; a *= 0.5; }
    return v;
  }

  void main() {
    vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
    // ondes des appels d'outils
    for (int i = 0; i < ${MAX_ONDES}; i++) {
      vec4 o = uOndes[i];
      float age = uTemps - o.z;
      if (o.w > 0.0 && age > 0.0 && age < 3.5) {
        vec2 d = p - o.xy;
        float r = length(d);
        float front = age * 0.55;
        float amp = exp(-abs(r - front) * 10.0) * (1.0 - age / 3.5) * 0.045 * o.w;
        p += normalize(d + 1e-4) * sin((r - front) * 34.0) * amp;
      }
    }
    float vitesse = 0.035 + uEnergie * 0.22;
    float t = uTemps * vitesse;
    vec2 q = vec2(fbm(p * 1.4 + vec2(0.0, t)), fbm(p * 1.4 + vec2(5.2, 1.3) - t * 0.8));
    vec2 r = vec2(fbm(p * 1.4 + 3.6 * q + vec2(1.7, 9.2) + t * 0.6), fbm(p * 1.4 + 3.6 * q + vec2(8.3, 2.8) - t * 0.4));
    float f = fbm(p * 1.4 + 3.8 * r);

    // filets du marbré : isolignes fines du champ déformé
    float iso = abs(fract(f * 7.0 + length(q) * 1.5) - 0.5);
    float filet = smoothstep(0.035, 0.0, iso - 0.012);

    vec3 c = mix(uFond, uEncre, clamp(f * f * 2.4, 0.0, 1.0));
    c = mix(c, uEncreVive, clamp(pow(length(r) * 0.85, 3.0), 0.0, 1.0) * (0.55 + 0.45 * uEnergie));
    c += uReflet * filet * (0.10 + 0.35 * uEnergie) * clamp(f * 1.6, 0.0, 1.0);

    // écriture : l'encre se retire vers le haut et dégage la page
    float y = gl_FragCoord.y / uRes.y;
    float degage = uEcriture * (1.0 - smoothstep(0.62, 0.9, y + (f - 0.5) * 0.18));
    c = mix(c, uFond, degage * 0.93);
    // fin : il ne reste qu'une bande marbrée en tête
    c = mix(c, uFond, uFin * (1.0 - smoothstep(0.84, 0.95, y + (f - 0.5) * 0.08)));
    // grain
    c += (hash(gl_FragCoord.xy + uTemps) - 0.5) * 0.018;
    gl_FragColor = vec4(c, 1.0);
  }
`;

function Champ({ p }: { p: Prepare }) {
  const { tRef } = useHorlogeScene();
  const { size, gl } = useThree();
  const energie = useRef(0);
  const uniforms = useMemo(() => ({
    uRes: { value: new THREE.Vector2() },
    uTemps: { value: 0 }, uEnergie: { value: 0 }, uEcriture: { value: 0 }, uFin: { value: 0 },
    uOndes: { value: Array.from({ length: MAX_ONDES }, () => new THREE.Vector4()) },
    uFond: { value: new THREE.Color("#07090e") },
    uEncre: { value: new THREE.Color("#132a66") },
    uEncreVive: { value: new THREE.Color("#4f7fff") },
    uReflet: { value: new THREE.Color("#dbe6ff") },
  }), []);
  const ondes = useMemo(() => p.sc.etapes.filter((e) => e.type === "outil").map((e, k) => {
    const a = k * 2.39996;
    return { x: Math.cos(a) * 0.35, y: Math.sin(a) * 0.22, t: e.debut / 1000 };
  }), [p]);

  useFrame((_, dt) => {
    const t = tRef.current;
    const dpr = gl.getPixelRatio();
    uniforms.uRes.value.set(size.width * dpr, size.height * dpr);
    uniforms.uTemps.value = t / 1000;
    const cible = Math.min(1, debit(p, t, 500) / 55);
    energie.current = amortir(energie.current, cible, 3.2, dt);
    uniforms.uEnergie.value = energie.current;
    uniforms.uEcriture.value = lisse(p.sc.debutRedaction - 200, p.sc.debutRedaction + 1400, t);
    uniforms.uFin.value = lisse(p.finRedaction, p.finRedaction + 1600, t);
    ondes.forEach((o, i) => i < MAX_ONDES && uniforms.uOndes.value[i].set(o.x, o.y, o.t, 1));
  });

  const mat = useShader({ uniforms, vertexShader: vertex, fragmentShader: fragment, depthTest: false });
  return (
    <mesh frustumCulled={false} material={mat}>
      <planeGeometry args={[2, 2]} />
    </mesh>
  );
}

const AGE_LIQUIDE = 900;

export function Marbrure() {
  const { prep: p, e } = useHorlogeScene();
  const turbulence = useRef<SVGFETurbulenceElement>(null);
  const deplacement = useRef<SVGFEDisplacementMapElement>(null);
  const enCours = e.etapes.find((s) => s.statut === "en cours");
  // le filtre ondule : fréquence et amplitude suivent le débit
  const d = Math.min(1, e.tokensParSeconde / 55);
  turbulence.current?.setAttribute("baseFrequency", `${0.018 + 0.004 * Math.sin(e.t / 300)} ${0.05 + 0.01 * Math.cos(e.t / 410)}`);
  deplacement.current?.setAttribute("scale", String(6 + d * 14));
  return (
    <div className="stage marbrure">
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <filter id="liquide" x="-10%" y="-40%" width="120%" height="180%">
          <feTurbulence ref={turbulence} type="fractalNoise" baseFrequency="0.02 0.05" numOctaves={2} seed={3} />
          <feDisplacementMap ref={deplacement} in="SourceGraphic" scale="14" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>
      <Canvas orthographic dpr={[1, 1.5]} gl={{ antialias: false, preserveDrawingBuffer: true }}>
        <Champ p={p} />
      </Canvas>
      <div className="stage-haut">
        <span className="stage-etat" key={enCours?.detail ?? e.phase}>
          {e.fini ? `A travaillé pendant ${dureeLisible(p.finRedaction)}` : e.phase === "redaction" ? "Rédige" : enCours ? `${enCours.libelle} : ${enCours.detail}` : "Prépare"}
        </span>
        <span className="stage-compteur">{nf.format(e.tokens)} tokens</span>
      </div>
      {e.phase !== "travail" && (
        <div className="stage-texte stage-texte-marbre">
          <Reponse p={p} e={e} rendreMot={(m) => {
            const age = e.t - m.instant;
            return <span className={age < AGE_LIQUIDE ? "mot-liquide" : "mot-fige"}>{m.texte}</span>;
          }} />
        </div>
      )}
    </div>
  );
}
