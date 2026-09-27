/**
 * Codex — un code ouvert sur un pupitre, en 3D.
 *
 * Pendant la réflexion, les pages défilent en rafale (courbure calculée dans le vertex shader) ;
 * pour chaque source consultée, une page tourne lentement jusqu'à l'article lu, surligné. À la
 * rédaction, la caméra plonge dans la page de droite, qui devient la feuille de réponse.
 */
import { ContactShadows } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { Reponse } from "../commun";
import { useShader } from "../shader";
import { amortir, lisse, useHorlogeScene } from "../horloge";
import { alea, dureeLisible, nf, type Prepare } from "../scenario";

const L = 1.9; // largeur d'une page
const H = 2.6;

interface Tour { debut: number; duree: number; recto: number } // recto : index de page de contenu

const ARTICLES_FEUILLETES = ["39", "150-0 A", "150-0 D", "156", "199 undecies B", "200 A", "238 bis",
  "1649 A", "210 A", "209", "219", "244 bis A", "39 decies", "150 U", "757 B", "787 B", "885 A"];

/** Pages de contenu : feuilletage générique puis une page par source consultée, puis la feuille de réponse. */
function planifier(p: Prepare) {
  const tours: Tour[] = [];
  const pages: { titre: string; source: boolean; reponse?: boolean }[] = [{ titre: "Code général des impôts", source: false }];
  for (const e of p.sc.etapes) {
    if (e.type === "reflexion") {
      const n = Math.max(2, Math.floor(e.duree / 230));
      for (let k = 0; k < n; k++) {
        pages.push({ titre: `Article ${ARTICLES_FEUILLETES[(pages.length * 7) % ARTICLES_FEUILLETES.length]}`, source: false });
        tours.push({ debut: e.debut + k * (e.duree / n), duree: 520, recto: pages.length - 2 });
      }
    } else {
      pages.push({ titre: e.detail, source: true });
      tours.push({ debut: e.debut + 80, duree: Math.min(1100, e.duree - 100), recto: pages.length - 2 });
    }
  }
  pages.push({ titre: "", source: false, reponse: true });
  tours.push({ debut: p.sc.debutRedaction - 300, duree: 900, recto: pages.length - 2 });
  return { tours, pages };
}

function textureDePage(titre: string, source: boolean, reponse: boolean, graine: number): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 760; c.height = 1040;
  const g = c.getContext("2d")!;
  const r = alea(graine);
  const papier = g.createLinearGradient(0, 0, c.width, 0);
  papier.addColorStop(0, "#dfe4ec"); papier.addColorStop(0.08, "#eef1f6"); papier.addColorStop(1, "#f3f5f9");
  g.fillStyle = papier; g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = "#8a95a6";
  g.font = "500 22px Inter, sans-serif";
  g.fillText(reponse ? "Réponse d'Interstice" : "Code général des impôts", 70, 80);
  g.fillRect(70, 98, c.width - 140, 1.5);
  if (!reponse) {
    g.fillStyle = "#1c2330";
    g.font = `600 ${source ? 40 : 34}px Inter, sans-serif`;
    g.fillText(titre.length > 30 ? titre.slice(0, 29) + "…" : titre, 70, 170);
    let y = 230;
    const surligne = source ? 2 + Math.floor(r() * 4) : -1;
    for (let ligne = 0; y < c.height - 90; ligne++) {
      const debutPar = ligne % 6 === 0;
      const largeur = (c.width - 140) * (ligne % 6 === 5 ? 0.35 + r() * 0.4 : 1) - (debutPar ? 40 : 0);
      if (ligne === surligne || ligne === surligne + 1) {
        g.fillStyle = "rgba(47, 91, 217, 0.22)";
        g.fillRect(64 + (debutPar ? 40 : 0), y - 14, largeur + 12, 26);
      }
      // mots : petits blocs gris de longueurs variées, justifiés
      let x = 70 + (debutPar ? 40 : 0);
      g.fillStyle = ligne === surligne || ligne === surligne + 1 ? "#23407f" : "#9aa4b3";
      while (x < 70 + (debutPar ? 40 : 0) + largeur - 20) {
        const w = 18 + r() * 70;
        g.fillRect(x, y - 6, Math.min(w, 70 + largeur - x), 9);
        x += w + 9;
      }
      y += ligne % 6 === 5 ? 52 : 30;
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

const vertexPage = /* glsl */ `
  uniform float uTour;
  varying vec2 vUv;
  varying float vOmbre;
  const float PI = 3.14159265;
  void main() {
    vUv = uv;
    float u = position.x / ${L.toFixed(2)};
    // le papier « traîne » : l'angle croît moins vite vers la tranche au milieu du geste
    float traine = sin(uTour * PI) * 0.55;
    float a = uTour * PI - traine * u * u + traine * 0.15;
    vec3 p = vec3(position.x * cos(a), position.y, position.x * sin(a));
    p.z += sin(u * PI) * sin(uTour * PI) * 0.12; // bombé
    vOmbre = 0.72 + 0.28 * abs(cos(a)) - 0.18 * (1.0 - smoothstep(0.0, 0.12, u));
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }
`;
const fragmentPage = /* glsl */ `
  uniform sampler2D uRecto;
  uniform sampler2D uVerso;
  varying vec2 vUv;
  varying float vOmbre;
  void main() {
    vec4 c = gl_FrontFacing ? texture2D(uRecto, vUv) : texture2D(uVerso, vec2(1.0 - vUv.x, vUv.y));
    gl_FragColor = vec4(c.rgb * vOmbre, 1.0);
    #include <colorspace_fragment>
  }
`;

function Feuille({ recto, verso, tour, z }: { recto: THREE.Texture; verso: THREE.Texture; tour: number; z: number }) {
  const geo = useMemo(() => new THREE.PlaneGeometry(L, H, 48, 1).translate(L / 2, 0, 0), []);
  const uniforms = useMemo(() => ({ uTour: { value: tour }, uRecto: { value: recto }, uVerso: { value: verso } }), [recto, verso]);
  const mat = useShader({ uniforms, vertexShader: vertexPage, fragmentShader: fragmentPage, side: THREE.DoubleSide });
  uniforms.uTour.value = tour;
  return <mesh geometry={geo} material={mat} position={[0, 0, z]} />;
}

function PageStatique({ texture, gauche }: { texture: THREE.Texture; gauche?: boolean }) {
  return (
    <mesh position={[gauche ? -L / 2 : L / 2, 0, 0]} rotation={[0, 0, 0]}>
      <planeGeometry args={[L, H]} />
      <meshBasicMaterial map={texture} color="#d8dde6" toneMapped={false} />
    </mesh>
  );
}

function Livre({ p }: { p: Prepare }) {
  const { tRef, t } = useHorlogeScene();
  const { camera } = useThree();
  const { tours, pages } = useMemo(() => planifier(p), [p]);
  const textures = useMemo(() => pages.map((pg, i) => textureDePage(pg.titre, pg.source, !!pg.reponse, i + 3)), [pages]);
  const verso = useMemo(() => textureDePage("", false, false, 999), []);
  const groupe = useRef<THREE.Group>(null);
  const zoom = useRef(0);

  useFrame((_, dt) => {
    const tt = tRef.current;
    const plonge = lisse(p.sc.debutRedaction + 300, p.sc.debutRedaction + 2200, tt);
    zoom.current = amortir(zoom.current, plonge, 6, dt);
    const z = zoom.current;
    const balance = Math.sin(tt / 2600) * 0.12 * (1 - z);
    // du plan d'ensemble au cadrage serré de la page de droite
    camera.position.set(0.1 + balance * 2 + z * (L / 2 - 0.1), 2.2 - z * 2.2, 4.4 - z * 1.25);
    camera.lookAt(z * (L / 2), -0.1 * (1 - z), 0);
    if (groupe.current) groupe.current.position.y = Math.sin(tt / 1400) * 0.03 * (1 - z);
  });

  const faits = tours.filter((x) => t >= x.debut + x.duree).length;
  const enCours = tours.filter((x) => t >= x.debut && t < x.debut + x.duree);
  const droite = textures[Math.min(textures.length - 1, faits + enCours.length)];
  return (
    <group ref={groupe} rotation={[-0.42, 0, 0]}>
      {/* couverture et tranches */}
      <mesh position={[0, 0, -0.07]}>
        <boxGeometry args={[L * 2 + 0.16, H + 0.16, 0.06]} />
        <meshStandardMaterial color="#1a2a52" roughness={0.55} metalness={0.15} />
      </mesh>
      <mesh position={[L / 2, 0, -0.025]}><boxGeometry args={[L, H, 0.05]} /><meshStandardMaterial color="#cfd5df" /></mesh>
      <mesh position={[-L / 2, 0, -0.025]}><boxGeometry args={[L, H, 0.05]} /><meshStandardMaterial color="#cfd5df" /></mesh>
      <group position={[0, 0, 0.002]}>
        <PageStatique texture={faits > 0 ? verso : textures[0]} gauche />
        <PageStatique texture={droite} />
      </group>
      {enCours.map((x, k) => (
        <Feuille key={x.debut} recto={textures[x.recto]} verso={verso}
          tour={lisse(x.debut, x.debut + x.duree, t)} z={0.006 + k * 0.004} />
      ))}
    </group>
  );
}

export function Codex() {
  const { prep: p, e } = useHorlogeScene();
  const texte = e.phase !== "travail" && e.t > p.sc.debutRedaction + 1900;
  const enCours = e.etapes.find((s) => s.statut === "en cours");
  return (
    <div className="stage codex">
      <Canvas camera={{ position: [0, 2.2, 4.4], fov: 38 }} dpr={[1, 2]} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <color attach="background" args={["#0a0d13"]} />
        <fog attach="fog" args={["#0a0d13", 5, 11]} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[2, 4, 3]} intensity={1.4} />
        <pointLight position={[-3, 1, 2]} intensity={6} color="#5b8cff" distance={8} />
        <Livre p={p} />
        <ContactShadows position={[0, -1.55, -0.3]} opacity={0.55} scale={9} blur={2.6} far={3} />
        <EffectComposer multisampling={0}>
          <Bloom intensity={0.35} luminanceThreshold={0.93} mipmapBlur />
          <Vignette offset={0.3} darkness={0.75} />
        </EffectComposer>
      </Canvas>
      <div className="stage-haut">
        <span className="stage-etat" key={enCours?.detail ?? e.phase}>
          {e.fini ? `A travaillé pendant ${dureeLisible(p.finRedaction)}` : e.phase === "redaction" ? "Rédige" : enCours ? `${enCours.libelle} : ${enCours.detail}` : "Prépare"}
        </span>
        <span className="stage-compteur">{nf.format(e.tokens)} tokens</span>
      </div>
      {texte && (
        <div className="stage-texte sur-papier">
          <Reponse p={p} e={e} rendreMot={(m) => <span className="mot-imprime">{m.texte}</span>} />
        </div>
      )}
    </div>
  );
}
