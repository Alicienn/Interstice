/**
 * Nuée — ~14 000 particules en vortex 3D qui se condensent en texte.
 *
 * Pendant le travail, la nuée tourbillonne ; le débit de tokens l'agite et chaque source lue
 * provoque une onde de choc. À la rédaction, chaque mot émis attire exactement les particules
 * nécessaires pour dessiner ses lettres (pixels échantillonnés d'une mise en page calculée en
 * canvas) ; une fois posées, elles s'éteignent sous le texte net, rendu aux mêmes coordonnées.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { amortir, lisse, useHorlogeScene } from "../horloge";
import { useShader } from "../shader";
import { alea, debit, dureeLisible, nf, type Prepare } from "../scenario";

const NB = 14000;
const VOL = 950; // ms de vol d'une particule jusqu'à sa lettre
const APPARITION_TEXTE = 820; // ms après l'émission du mot, le texte net apparaît
const PAS = 2; // échantillonnage des pixels (1 point tous les 2 px)

// ------------------------------------------------------------------ mise en page (canvas = HTML)

interface MotPlace { i: number; x: number; y: number; texte: string; police: string; couleur: string }
interface MiseEnPage { mots: MotPlace[]; puces: { x: number; y: number; police: string; premier: number }[]; hauteur: number }
const BOITE = 28; // hauteur de la boîte d'un mot, texte centré (identique en canvas et en HTML)

const STYLES = {
  titre: { police: "600 16px Inter", interligne: 24, avant: 14, couleur: "fort" },
  paragraphe: { police: "400 15px Inter", interligne: 24, avant: 8, couleur: "texte" },
  puce: { police: "400 15px Inter", interligne: 24, avant: 4, couleur: "texte" },
  citation: { police: "400 13.5px Inter", interligne: 21, avant: 8, couleur: "attenue" },
} as const;

function mettreEnPage(p: Prepare, largeur: number): MiseEnPage {
  const ctx = document.createElement("canvas").getContext("2d")!;
  const mots: MotPlace[] = [];
  const puces: MiseEnPage["puces"] = [];
  let y = 0;
  let i = 0;
  p.sc.blocs.forEach((b, bi) => {
    const s = STYLES[b.type];
    ctx.font = s.police;
    const retrait = b.type === "puce" ? 20 : b.type === "citation" ? 14 : 0;
    y += bi === 0 ? 0 : s.avant;
    let x = retrait;
    const espace = ctx.measureText(" ").width;
    if (b.type === "puce") puces.push({ x: 4, y, police: s.police, premier: i });
    for (const texte of b.texte.split(" ")) {
      const w = ctx.measureText(texte).width;
      if (x + w > largeur && x > retrait) { x = retrait; y += s.interligne; }
      mots.push({ i: i++, x, y, texte, police: s.police, couleur: s.couleur });
      x += w + espace;
    }
    y += s.interligne;
  });
  return { mots, puces, hauteur: y };
}

/** Pixels allumés d'un mot, en coordonnées de mise en page. */
function echantillonner(m: MotPlace): [number, number][] {
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d", { willReadFrequently: true })!;
  ctx.font = m.police;
  const w = Math.ceil(ctx.measureText(m.texte).width) + 4;
  c.width = w; c.height = BOITE;
  ctx.font = m.police;
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#fff";
  ctx.fillText(m.texte, 0, BOITE / 2);
  const d = ctx.getImageData(0, 0, w, BOITE).data;
  const pts: [number, number][] = [];
  for (let py = 0; py < BOITE; py += PAS) for (let px = 0; px < w; px += PAS) {
    if (d[(py * w + px) * 4 + 3] > 110) pts.push([m.x + px, m.y + py]);
  }
  return pts;
}

// ------------------------------------------------------------------ particules

const vertex = /* glsl */ `
  uniform float uTemps;     // ms
  uniform float uEnergie;
  uniform float uEclat;     // ms du dernier choc
  uniform float uFin;
  uniform float uEchelle;
  attribute vec4 aAleat;
  attribute vec3 aCible;
  attribute float aDebut;   // ms d'attribution à une lettre (1e9 : jamais)
  varying float vAlpha;
  varying float vChaleur;
  const float PI = 3.14159265;

  vec3 vortex(vec4 a, float t) {
    float r = 1.1 + a.x * 2.6;
    float vit = 0.00022 * (1.0 + 1.6 / r) * (1.0 + uEnergie * 1.4);
    float ang = a.y * 2.0 * PI + t * vit;
    float h = (a.z - 0.5) * 1.5 * (0.35 + 0.65 * (r / 3.7));
    vec3 p = vec3(cos(ang) * r, h, sin(ang) * r);
    p += 0.12 * vec3(sin(t * 0.0011 + a.w * 20.0), cos(t * 0.0013 + a.x * 17.0), sin(t * 0.0009 + a.z * 13.0)) * (1.0 + uEnergie);
    // choc : expansion radiale amortie
    float age = t - uEclat;
    if (age > 0.0 && age < 1400.0) p *= 1.0 + 0.32 * sin(age / 1400.0 * PI) * exp(-age / 700.0);
    return p;
  }

  void main() {
    vec3 v = vortex(aAleat, uTemps);
    // incliner le disque pour une lecture en 3/4
    float c = cos(0.45), s = sin(0.45);
    v = vec3(v.x, v.y * c - v.z * s, v.y * s + v.z * c);
    float k = clamp((uTemps - aDebut) / ${VOL.toFixed(1)}, 0.0, 1.0);
    float e = 1.0 - pow(1.0 - k, 4.0);
    vec3 ailleurs = normalize(cross(aCible - v + 1e-3, vec3(0.0, 0.0, 1.0)));
    vec3 p = mix(v, aCible, e) + ailleurs * sin(k * PI) * 0.55 * (aAleat.w - 0.5);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float pose = step(0.999, k);
    float extinction = 1.0 - smoothstep(aDebut + ${VOL.toFixed(1)}, aDebut + ${(VOL + 650).toFixed(1)}, uTemps);
    float libre = 1.0 - step(0.0001, k);
    vAlpha = mix(0.55 + 0.45 * aAleat.w, 1.0, e) * mix(1.0, extinction, pose) * (1.0 - uFin * libre);
    vChaleur = e * (1.0 - pose * 0.6) + uEnergie * 0.25 * libre;
    float taille = mix(1.2 + aAleat.x * 1.8, 1.25, e) * (1.0 + uEnergie * 0.5 * libre);
    gl_PointSize = taille * uEchelle / -mv.z;
  }
`;
const fragment = /* glsl */ `
  uniform vec3 uFroid;
  uniform vec3 uChaud;
  varying float vAlpha;
  varying float vChaleur;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.05, d) * vAlpha;
    gl_FragColor = vec4(mix(uFroid, uChaud, clamp(vChaleur, 0.0, 1.0)), a);
  }
`;

interface Cadre { gauche: number; haut: number; largeur: number }

function Particules({ p, page, cadre }: { p: Prepare; page: MiseEnPage; cadre: Cadre }) {
  const { tRef } = useHorlogeScene();
  const { size, camera } = useThree();
  const energie = useRef(0);

  // attribution déterministe : chaque mot reçoit les particules de ses pixels, à l'instant de son émission
  const geo = useMemo(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const hMonde = 2 * cam.position.z * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
    const k = hMonde / size.height;
    const versMonde = (x: number, y: number) => [
      (cadre.gauche + x - size.width / 2) * k, -(cadre.haut + y - size.height / 2) * k, 0,
    ];
    const r = alea(7);
    const aleat = new Float32Array(NB * 4);
    const cibles = new Float32Array(NB * 3);
    const debuts = new Float32Array(NB).fill(1e9);
    for (let i = 0; i < NB * 4; i++) aleat[i] = r();
    const parMot = page.mots.map(echantillonner);
    const total = parMot.reduce((s, x) => s + x.length, 0);
    const ratio = Math.min(1, (NB * 0.92) / total);
    let n = 0;
    parMot.forEach((pts, mi) => {
      const instant = p.mots[page.mots[mi].i].instant;
      for (let j = 0; j < pts.length && n < NB; j++) {
        if (r() > ratio) continue;
        cibles.set(versMonde(pts[j][0], pts[j][1]), n * 3);
        debuts[n] = instant + r() * 140;
        n++;
      }
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(NB * 3), 3));
    g.setAttribute("aAleat", new THREE.BufferAttribute(aleat, 4));
    g.setAttribute("aCible", new THREE.BufferAttribute(cibles, 3));
    g.setAttribute("aDebut", new THREE.BufferAttribute(debuts, 1));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 50);
    return g;
  }, [p, page, cadre, size.width, size.height, camera]);

  const uniforms = useMemo(() => ({
    uTemps: { value: 0 }, uEnergie: { value: 0 }, uEclat: { value: -1e6 }, uFin: { value: 0 }, uEchelle: { value: 300 },
    uFroid: { value: new THREE.Color("#5d78b8") }, uChaud: { value: new THREE.Color("#e6eeff") },
  }), []);
  const chocs = useMemo(() => p.sc.etapes.filter((e) => e.type === "outil").map((e) => e.debut), [p]);

  useFrame((_, dt) => {
    const t = tRef.current;
    uniforms.uTemps.value = t;
    energie.current = amortir(energie.current, Math.min(1, debit(p, t, 500) / 50), 3, dt);
    uniforms.uEnergie.value = energie.current;
    uniforms.uEclat.value = chocs.filter((c) => c <= t).pop() ?? -1e6;
    uniforms.uFin.value = lisse(p.finRedaction, p.finRedaction + 1800, t);
    uniforms.uEchelle.value = size.height * 0.55;
  });

  const mat = useShader({ uniforms, vertexShader: vertex, fragmentShader: fragment, transparent: true,
    depthWrite: false, blending: THREE.AdditiveBlending });
  return <points geometry={geo} material={mat} frustumCulled={false} />;
}

export function Nuee() {
  const { prep: p, e } = useHorlogeScene();
  const boite = useRef<HTMLDivElement>(null);
  const [cadre, setCadre] = useState<Cadre | null>(null);
  const [policesPretes, setPolicesPretes] = useState(false);
  useEffect(() => { document.fonts.ready.then(() => setPolicesPretes(true)); }, []);
  useEffect(() => {
    const maj = () => {
      const r = boite.current?.getBoundingClientRect();
      if (!r) return;
      const largeur = Math.min(620, r.width - 96);
      setCadre({ gauche: (r.width - largeur) / 2, haut: 92, largeur });
    };
    maj();
    const ro = new ResizeObserver(maj);
    if (boite.current) ro.observe(boite.current);
    return () => ro.disconnect();
  }, []);
  const page = useMemo(() => (cadre && policesPretes ? mettreEnPage(p, cadre.largeur) : null), [p, cadre, policesPretes]);
  const enCours = e.etapes.find((s) => s.statut === "en cours");

  return (
    <div className="stage nuee" ref={boite}>
      {page && cadre && (
        <Canvas camera={{ position: [0, 0, 7], fov: 40 }} dpr={[1, 2]} gl={{ antialias: true, preserveDrawingBuffer: true }}>
          <color attach="background" args={["#06080d"]} />
          <Particules p={p} page={page} cadre={cadre} />
          <EffectComposer multisampling={0}>
            <Bloom intensity={0.9} luminanceThreshold={0.25} mipmapBlur radius={0.6} />
          </EffectComposer>
        </Canvas>
      )}
      <div className="stage-haut">
        <span className="stage-etat" key={enCours?.detail ?? e.phase}>
          {e.fini ? `A travaillé pendant ${dureeLisible(p.finRedaction)}` : e.phase === "redaction" ? "Rédige" : enCours ? `${enCours.libelle} : ${enCours.detail}` : "Prépare"}
        </span>
        <span className="stage-compteur">{nf.format(e.tokens)} tokens</span>
      </div>
      {page && cadre && (
        <div className="nuee-texte" style={{ left: cadre.gauche, top: cadre.haut, width: cadre.largeur, height: page.hauteur }}>
          {page.puces.map((b, k) => {
            const instant = p.mots[b.premier].instant;
            return (
              <span key={`p${k}`} className="nuee-puce" style={{ left: b.x, top: b.y, font: b.police,
                opacity: lisse(instant + APPARITION_TEXTE, instant + APPARITION_TEXTE + 420, e.t) }}>•</span>
            );
          })}
          {page.mots.map((m) => {
            const instant = p.mots[m.i].instant;
            const o = lisse(instant + APPARITION_TEXTE, instant + APPARITION_TEXTE + 420, e.t);
            return o > 0 ? (
              <span key={m.i} className={`nuee-mot ${m.couleur}`} style={{ left: m.x, top: m.y, font: m.police, opacity: o }}>
                {m.texte}
              </span>
            ) : null;
          })}
        </div>
      )}
    </div>
  );
}
