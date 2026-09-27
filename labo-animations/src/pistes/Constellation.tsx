/**
 * Constellation — le graphe des renvois du CGI en 3D.
 *
 * ~240 articles forment une galaxie spirale reliée par des filaments (renvois). Pendant le travail,
 * chaque source consultée s'allume, un filament lumineux trace le chemin de l'IA d'article en
 * article et la caméra vole jusqu'au nœud lu. À la rédaction, la galaxie s'effondre en spirale dans
 * un noyau incandescent d'où jaillit le texte.
 */
import { Line } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import { useMemo, useRef, type RefObject } from "react";
import * as THREE from "three";
import { Reponse } from "../commun";
import { useShader } from "../shader";
import { amortir, lisse, useHorlogeScene } from "../horloge";
import { alea, dureeLisible, etatA, nf, type Prepare } from "../scenario";

const N = 240;

interface Galaxie {
  positions: Float32Array;
  graines: Float32Array;
  aretes: Float32Array;
  sources: number[]; // index du nœud pour chaque étape « outil »
}

function construireGalaxie(p: Prepare): Galaxie {
  const r = alea(42);
  const pts: THREE.Vector3[] = [];
  const graines = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const bras = i % 3;
    const rayon = 0.35 + 5.2 * Math.sqrt(r());
    const angle = (bras * 2 * Math.PI) / 3 + rayon * 0.85 + (r() - 0.5) * 0.7;
    const epaisseur = (r() + r() + r() - 1.5) * 0.55 * (1 - rayon / 7);
    pts.push(new THREE.Vector3(rayon * Math.cos(angle), epaisseur, rayon * Math.sin(angle)));
    graines[i] = r();
  }
  const positions = new Float32Array(N * 3);
  pts.forEach((v, i) => v.toArray(positions, i * 3));
  // filaments : chaque nœud relié à ses deux plus proches voisins
  const segs: number[] = [];
  for (let i = 0; i < N; i++) {
    const proches = pts
      .map((v, j) => [j, v.distanceToSquared(pts[i])] as const)
      .filter(([j]) => j !== i)
      .sort((a, b) => a[1] - b[1])
      .slice(0, 2);
    for (const [j] of proches) if (j > i) segs.push(...pts[i].toArray(), ...pts[j].toArray());
  }
  // sources : nœuds bien visibles, dans la couronne médiane, deux à deux éloignés
  const nOutils = p.sc.etapes.filter((e) => e.type === "outil").length;
  const candidats = pts.map((v, i) => [i, v.length()] as const).filter(([, l]) => l > 1.6 && l < 4.4);
  const sources: number[] = [];
  for (let k = 0; k < nOutils; k++) {
    const [i] = candidats[Math.floor(((k * 0.37 + 0.11) % 1) * candidats.length)];
    sources.push(i);
  }
  return { positions, graines, aretes: new Float32Array(segs), sources };
}

// Transformation commune aux points et aux filaments : effondrement en spirale vers le centre.
const EFFONDREMENT = /* glsl */ `
  uniform float uEffondrement;
  uniform float uTempsSpirale;
  vec3 effondrer(vec3 p) {
    float rayon = length(p.xz);
    // spirale : rotation d'autant plus forte que l'on est près du centre, qui continue une fois effondré
    float a = uEffondrement * uEffondrement * (7.0 + uTempsSpirale * 0.9) / (0.6 + rayon);
    float c = cos(a), s = sin(a);
    p.xz = mat2(c, -s, s, c) * p.xz;
    // la galaxie ne disparaît pas : elle finit en disque d'accrétion serré autour du noyau
    return p * (1.0 - 0.88 * smoothstep(0.0, 1.0, uEffondrement));
  }
`;

const vertexPoints = /* glsl */ `
  ${EFFONDREMENT}
  uniform float uTemps;
  uniform float uPouls;
  attribute float aGraine;
  varying float vEclat;
  void main() {
    vec3 p = effondrer(position);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float scintille = 0.55 + 0.45 * sin(uTemps * (0.8 + aGraine * 1.6) + aGraine * 40.0);
    vEclat = scintille * (0.5 + 0.5 * uPouls) + uEffondrement * 0.8;
    gl_PointSize = min(16.0, (1.0 + 2.2 * aGraine) * (1.0 + uPouls * 0.5 * scintille) * (150.0 / -mv.z));
  }
`;
const fragmentPoints = /* glsl */ `
  uniform vec3 uFroid;
  uniform vec3 uAccent;
  varying float vEclat;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float halo = pow(smoothstep(0.5, 0.0, d), 2.2);
    float coeur = smoothstep(0.16, 0.0, d);
    vec3 c = mix(uFroid, uAccent, vEclat * 0.6) * 0.8 + coeur * 0.55;
    gl_FragColor = vec4(c, halo * (0.18 + 0.55 * vEclat));
  }
`;
const vertexAretes = /* glsl */ `
  ${EFFONDREMENT}
  void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(effondrer(position), 1.0); }
`;
const fragmentAretes = /* glsl */ `
  uniform vec3 uFroid;
  uniform float uOpacite;
  void main() { gl_FragColor = vec4(uFroid, uOpacite); }
`;

/** Même transformation que le GLSL `effondrer`, pour les objets calculés côté JavaScript. */
function effondrerJs(v: THREE.Vector3, eff: number, tempsSpirale: number): THREE.Vector3 {
  const rayon = Math.hypot(v.x, v.z);
  const a = (eff * eff * (7 + tempsSpirale * 0.9)) / (0.6 + rayon);
  const c = Math.cos(a), s = Math.sin(a);
  const k = 1 - 0.88 * eff * eff * (3 - 2 * eff);
  return new THREE.Vector3((c * v.x - s * v.z) * k, v.y * k, (s * v.x + c * v.z) * k);
}

const vertexHalo = /* glsl */ `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const fragmentHalo = /* glsl */ `
  uniform float uTemps;
  uniform float uForce;
  varying vec2 vUv;
  void main() {
    vec2 p = vUv - 0.5;
    float d = length(p) * 2.0;
    float a = atan(p.y, p.x);
    float rayons = 0.5 + 0.5 * sin(a * 9.0 + uTemps * 0.7) * sin(a * 5.0 - uTemps * 1.1);
    float coeur = smoothstep(0.16, 0.0, d);
    float lueur = (exp(-d * 5.0) * 0.9 + exp(-d * 2.4) * 0.35 * (0.7 + 0.3 * rayons)) * smoothstep(1.0, 0.55, d);
    vec3 c = mix(vec3(0.36, 0.55, 1.0), vec3(1.0), clamp(coeur + exp(-d * 9.0) * 0.6, 0.0, 1.0));
    // additif : la contribution s'annule avant le bord du panneau (aucun carré visible)
    gl_FragColor = vec4(c, clamp((lueur + coeur) * uForce, 0.0, 1.0));
  }
`;

function Halo({ echelle }: { echelle: RefObject<number> }) {
  const { tRef } = useHorlogeScene();
  const mesh = useRef<THREE.Mesh>(null);
  const uniforms = useMemo(() => ({ uTemps: { value: 0 }, uForce: { value: 0 } }), []);
  useFrame(({ camera }) => {
    const m = mesh.current;
    if (!m) return;
    m.quaternion.copy(camera.quaternion); // panneau toujours face caméra
    const s = echelle.current ?? 0;
    m.scale.setScalar(Math.max(0.0001, s * 7));
    uniforms.uTemps.value = tRef.current / 1000;
    uniforms.uForce.value = Math.min(1, s * 4);
  });
  const mat = useShader({ uniforms, vertexShader: vertexHalo, fragmentShader: fragmentHalo, transparent: true,
    depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false });
  return (
    <mesh ref={mesh} material={mat}>
      <planeGeometry args={[1, 1]} />
    </mesh>
  );
}

function Scene({ p, galaxie, etiquette }: { p: Prepare; galaxie: Galaxie; etiquette: RefObject<HTMLDivElement | null> }) {
  const { tRef } = useHorlogeScene();
  const { camera, size } = useThree();
  const noyau = useRef<THREE.Mesh>(null);
  const echelleNoyau = useRef(0);
  const focus = useRef(new THREE.Vector3());
  const rayonCam = useRef(10);
  const outils = p.sc.etapes.filter((e) => e.type === "outil");

  const uniformsPoints = useMemo(() => ({
    uTemps: { value: 0 }, uPouls: { value: 0 }, uEffondrement: { value: 0 }, uTempsSpirale: { value: 0 },
    uFroid: { value: new THREE.Color("#7f93b8") }, uAccent: { value: new THREE.Color("#6f9bff") },
  }), []);
  const uniformsAretes = useMemo(() => ({
    uEffondrement: { value: 0 }, uTempsSpirale: { value: 0 },
    uFroid: { value: new THREE.Color("#5b6f93") }, uOpacite: { value: 0.16 },
  }), []);
  // fond : poussière d'étoiles lointaines, immobile, qui habite la scène après l'effondrement
  const fond = useMemo(() => {
    const r = alea(9);
    const n = 1400;
    const pos = new Float32Array(n * 3);
    const graines = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const u = r() * 2 - 1, th = r() * Math.PI * 2, rr = 26 + r() * 14;
      pos.set([rr * Math.sqrt(1 - u * u) * Math.cos(th), rr * u * 0.6, rr * Math.sqrt(1 - u * u) * Math.sin(th)], i * 3);
      graines[i] = r() * 0.35;
    }
    return { pos, graines };
  }, []);
  const uniformsFond = useMemo(() => ({
    uTemps: { value: 0 }, uPouls: { value: 0 }, uEffondrement: { value: 0 }, uTempsSpirale: { value: 0 },
    uFroid: { value: new THREE.Color("#5a6b8c") }, uAccent: { value: new THREE.Color("#6f9bff") },
  }), []);
  const matFond = useShader({ uniforms: uniformsFond, vertexShader: vertexPoints, fragmentShader: fragmentPoints,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
  const matPoints = useShader({ uniforms: uniformsPoints, vertexShader: vertexPoints, fragmentShader: fragmentPoints,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const matAretes = useShader({ uniforms: uniformsAretes, vertexShader: vertexAretes, fragmentShader: fragmentAretes,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });

  useFrame((_, dt) => {
    const t = tRef.current;
    const e = etatA(p, t);
    const eff = lisse(p.sc.debutRedaction - 300, p.sc.debutRedaction + 1800, t);
    const reflexion = e.etapes.some((s) => s.type === "reflexion" && s.statut === "en cours") ? 1 : 0;
    uniformsPoints.uTemps.value = t / 1000;
    uniformsPoints.uPouls.value = amortir(uniformsPoints.uPouls.value, reflexion, 4, dt);
    uniformsPoints.uEffondrement.value = eff;
    uniformsAretes.uEffondrement.value = eff;
    const spirale = Math.max(0, t - p.sc.debutRedaction) / 1000;
    uniformsPoints.uTempsSpirale.value = spirale;
    uniformsAretes.uTempsSpirale.value = spirale;
    uniformsAretes.uOpacite.value = 0.16 * (1 - eff * 0.7);
    uniformsFond.uTemps.value = t / 1000;

    // caméra : survol en orbite, vol vers la source en cours, recul pendant l'effondrement
    const enCours = outils.findIndex((s) => t >= s.debut && t < s.debut + s.duree);
    const cible = new THREE.Vector3();
    let rayon = 10.5;
    if (enCours >= 0 && eff === 0) {
      cible.fromArray(galaxie.positions, galaxie.sources[enCours] * 3);
      rayon = 4.4;
    } else if (eff > 0) {
      rayon = 7.5 - eff * 1.5;
    }
    focus.current.lerp(cible, 1 - Math.exp(-2.4 * dt));
    rayonCam.current = amortir(rayonCam.current, rayon, 1.8, dt);
    const az = t / 1000 * 0.12 + 0.6;
    const el = 0.62 - eff * 0.25;
    camera.position.set(
      focus.current.x + rayonCam.current * Math.cos(az) * Math.cos(el),
      focus.current.y + rayonCam.current * Math.sin(el),
      focus.current.z + rayonCam.current * Math.sin(az) * Math.cos(el),
    );
    camera.lookAt(focus.current);

    // étiquette HTML projetée sur le nœud en cours
    const bulle = etiquette.current;
    if (bulle) {
      if (enCours >= 0 && eff === 0) {
        camera.updateMatrixWorld();
        const v = new THREE.Vector3().fromArray(galaxie.positions, galaxie.sources[enCours] * 3).project(camera);
        bulle.style.transform = `translate(${(v.x * 0.5 + 0.5) * size.width}px, ${(-v.y * 0.5 + 0.5) * size.height}px) translate(-50%, -150%)`;
        bulle.style.opacity = "1";
      } else {
        bulle.style.opacity = "0";
      }
    }

    const pulse = 1 + 0.08 * Math.sin(t / 180) * (e.phase === "redaction" ? 1 : 0.3);
    echelleNoyau.current = eff * 0.34 * pulse * (e.fini ? 1 - lisse(0, 1400, e.depuisFin) * 0.55 : 1);
    if (noyau.current) noyau.current.scale.setScalar(Math.max(0.0001, echelleNoyau.current * 0.28));
  });

  // chemin de l'IA à travers les sources visitées
  const t = tRef.current;
  const eff = lisse(p.sc.debutRedaction - 300, p.sc.debutRedaction + 1800, t);
  const visites = outils.map((s, k) => ({ s, k })).filter(({ s }) => t >= s.debut);
  const spirale = Math.max(0, t - p.sc.debutRedaction) / 1000;
  const pos = (k: number) => effondrerJs(new THREE.Vector3().fromArray(galaxie.positions, galaxie.sources[k] * 3), eff, spirale);

  return (
    <>
      <points material={matPoints} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[galaxie.positions, 3]} />
          <bufferAttribute attach="attributes-aGraine" args={[galaxie.graines, 1]} />
        </bufferGeometry>
      </points>
      <lineSegments material={matAretes} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[galaxie.aretes, 3]} />
        </bufferGeometry>
      </lineSegments>
      <points material={matFond} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[fond.pos, 3]} />
          <bufferAttribute attach="attributes-aGraine" args={[fond.graines, 1]} />
        </bufferGeometry>
      </points>

      {eff < 0.98 && visites.map(({ s, k }) => {
        const a = pos(k);
        const avancee = lisse(s.debut, s.debut + 700, t);
        const encore = t < s.debut + s.duree;
        const precedent = k > 0 ? pos(k - 1) : null;
        return (
          <group key={k}>
            {precedent && (
              <Line points={[precedent, precedent.clone().lerp(a, avancee)]} color="#8fb0ff" lineWidth={2.2}
                transparent opacity={0.9 * (1 - eff)} depthWrite={false} toneMapped={false} />
            )}
            <mesh position={a} scale={(encore ? 0.045 + 0.012 * Math.sin(t / 120) : 0.035) * (1 - eff)}>
              <sphereGeometry args={[1, 24, 24]} />
              <meshBasicMaterial color={encore ? "#dfe8ff" : "#7fa4ff"} toneMapped={false} />
            </mesh>
            {avancee < 1 && eff === 0 && (
              <mesh position={a} scale={0.1 + avancee * 0.9} rotation={[Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.95, 1, 64]} />
                <meshBasicMaterial color="#6f9bff" transparent opacity={(1 - avancee) * 0.8} depthWrite={false}
                  side={THREE.DoubleSide} toneMapped={false} blending={THREE.AdditiveBlending} />
              </mesh>
            )}
          </group>
        );
      })}

      <mesh ref={noyau}>
        <sphereGeometry args={[1, 48, 48]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      <Halo echelle={echelleNoyau} />
    </>
  );
}

export function Constellation() {
  const { prep: p, e } = useHorlogeScene();
  const galaxie = useMemo(() => construireGalaxie(p), [p]);
  const etiquette = useRef<HTMLDivElement>(null);
  const sourceEnCours = e.etapes.find((s) => s.type === "outil" && s.statut === "en cours");
  const texte = e.phase !== "travail" && e.t > p.sc.debutRedaction + 700;
  const enCours = e.etapes.find((s) => s.statut === "en cours");
  return (
    <div className="stage constellation">
      <Canvas camera={{ position: [0, 5, 10], fov: 42, near: 0.1, far: 100 }} dpr={[1, 2]}
        gl={{ antialias: true, powerPreference: "high-performance", preserveDrawingBuffer: true }}>
        <color attach="background" args={["#070a10"]} />
        <fog attach="fog" args={["#070a10", 9, 22]} />
        <Scene p={p} galaxie={galaxie} etiquette={etiquette} />
        <EffectComposer multisampling={0}>
          <Bloom intensity={0.85} luminanceThreshold={0.42} luminanceSmoothing={0.3} mipmapBlur radius={0.6} />
          <Vignette offset={0.25} darkness={0.7} />
        </EffectComposer>
      </Canvas>
      <div ref={etiquette} className="etiquette-3d" style={{ opacity: 0 }}>
        {sourceEnCours && <><span>{sourceEnCours.libelle}</span>{sourceEnCours.detail}</>}
      </div>
      <div className="stage-haut">
        <span className="stage-etat" key={enCours?.detail ?? e.phase}>
          {e.fini ? `A travaillé pendant ${dureeLisible(p.finRedaction)}` : e.phase === "redaction" ? "Rédige" : enCours ? `${enCours.libelle}` : "Prépare"}
        </span>
        <span className="stage-compteur">{nf.format(e.tokens)} tokens</span>
      </div>
      {texte && (
        <div className="stage-texte stage-texte-bas">
          <Reponse p={p} e={e} rendreMot={(m) => <span className="mot-eclat">{m.texte}</span>} />
        </div>
      )}
    </div>
  );
}
