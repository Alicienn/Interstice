/**
 * Synapses — un réseau neuronal en 2D, gris et blanc.
 *
 * Pendant le travail, des neurones naissent à des positions pseudo-aléatoires, se relient à leurs
 * voisins par des courbes fines et des influx parcourent les connexions ; chaque source consultée
 * déclenche une décharge qui se propage dans une grappe. Les neurones anciens montent en s'estompant
 * (fade up), le réseau se renouvelle sans cesse. À la rédaction, tout s'évapore vers le haut, et
 * chaque mot se matérialise à partir de grains qui se condensent puis s'éteignent.
 *
 * Tout est fonction de `t` : rejouable, et le curseur de lecture fonctionne.
 */
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Reponse } from "../commun";
import { lisse, useHorlogeScene } from "../horloge";
import { alea, debit, dureeLisible, nf, type Prepare } from "../scenario";

interface Neurone { x: number; y: number; naissance: number; mort: number; grappe: number; taille: number; distCentre: number }
interface Lien { a: number; b: number; courbure: number; vitesse: number; phase: number }
interface Grappe { x: number; y: number; debut: number; libelle: string }
interface Reseau { neurones: Neurone[]; liens: Lien[]; grappes: Grappe[] }

const GRAINS_PAR_MOT = 42;
const VIE_GRAINS = 1100;

function construireReseau(p: Prepare, ratio: number): Reseau {
  const r = alea(1234);
  const gauss = () => (r() + r() + r() - 1.5) / 1.5;
  const neurones: Neurone[] = [];
  const grappes: Grappe[] = [];
  const fin = p.sc.debutRedaction;
  let precedent = { x: 0.5, y: 0.5 };
  p.sc.etapes.forEach((e) => {
    // centre de grappe : pseudo-aléatoire, pas trop près du précédent
    let c = { x: 0.2 + r() * 0.6, y: 0.25 + r() * 0.5 };
    for (let essai = 0; essai < 8 && Math.hypot(c.x - precedent.x, (c.y - precedent.y) / ratio) < 0.22; essai++) {
      c = { x: 0.2 + r() * 0.6, y: 0.25 + r() * 0.5 };
    }
    precedent = c;
    if (e.type === "outil") grappes.push({ ...c, debut: e.debut, libelle: `${e.libelle} : ${e.detail}` });
    const n = Math.round(e.duree / (e.type === "reflexion" ? 38 : 30));
    const etalement = e.type === "reflexion" ? 0.26 : 0.15;
    for (let i = 0; i < n; i++) {
      const x = Math.min(0.97, Math.max(0.03, c.x + gauss() * etalement));
      const y = Math.min(0.95, Math.max(0.12, c.y + gauss() * etalement * ratio));
      const naissance = e.debut + r() * e.duree * 0.95;
      neurones.push({
        x, y, naissance,
        mort: Math.min(fin + 2000, naissance + 2600 + r() * 3200),
        grappe: e.type === "outil" ? grappes.length - 1 : -1,
        taille: 0.9 + r() * 1.6,
        distCentre: Math.hypot(x - c.x, (y - c.y) / ratio),
      });
    }
  });
  // neurones d'ambiance : répartis sur toute la scène, ils relient les grappes entre elles
  for (let i = 0; i < 70; i++) {
    const naissance = r() * (fin - 400);
    neurones.push({ x: 0.04 + r() * 0.92, y: 0.12 + r() * 0.83, naissance, mort: Math.min(fin + 2000, naissance + 3500 + r() * 4000),
      grappe: -1, taille: 0.7 + r() * 1.1, distCentre: 1 });
  }
  neurones.sort((a, b) => a.naissance - b.naissance);
  // connexions : chaque neurone se relie à 2 ou 3 voisins plus anciens encore vivants à sa naissance
  const liens: Lien[] = [];
  neurones.forEach((n, i) => {
    const proches = neurones
      .slice(0, i)
      .map((m, j) => ({ j, d: Math.hypot(m.x - n.x, (m.y - n.y) / ratio), m }))
      .filter(({ d, m }) => d < 0.21 && m.mort > n.naissance + 400)
      .sort((a, b) => a.d - b.d)
      .slice(0, r() < 0.4 ? 3 : 2);
    for (const { j } of proches) {
      liens.push({ a: j, b: i, courbure: (r() - 0.5) * 0.5, vitesse: 0.00035 + r() * 0.0005, phase: r() });
    }
  });
  return { neurones, liens, grappes };
}

export function Synapses() {
  const { prep: p, e, tRef } = useHorlogeScene();
  const boite = useRef<HTMLDivElement>(null);
  const fondRef = useRef<HTMLCanvasElement>(null);
  const grainRef = useRef<HTMLCanvasElement>(null);
  const positionsMots = useRef(new Map<number, { x: number; y: number; w: number; h: number }>());
  const reseau = useMemo(() => construireReseau(p, 1.55), [p]);

  // mesure des mots affichés (pour y faire naître les grains)
  useLayoutEffect(() => {
    const b = boite.current?.getBoundingClientRect();
    if (!b) return;
    boite.current!.querySelectorAll<HTMLElement>("[data-mot]").forEach((el) => {
      const i = Number(el.dataset.mot);
      if (positionsMots.current.has(i)) return;
      const r = el.getBoundingClientRect();
      positionsMots.current.set(i, { x: r.left - b.left, y: r.top - b.top, w: r.width, h: r.height });
    });
  }, [e.motsEmis]);
  useEffect(() => { positionsMots.current.clear(); }, [p]);

  useEffect(() => {
    let id = 0;
    const dessiner = () => {
      id = requestAnimationFrame(dessiner);
      const fond = fondRef.current, grain = grainRef.current, st = boite.current;
      if (!fond || !grain || !st) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const W = st.clientWidth, H = st.clientHeight;
      for (const c of [fond, grain]) {
        if (c.width !== Math.round(W * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
      }
      const t = tRef.current;
      const g = fond.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const dr = p.sc.debutRedaction;
      const activite = Math.min(1, debit(p, t, 600) / 40);

      // état de chaque neurone
      const etats = reseau.neurones.map((n) => {
        const apparition = lisse(n.naissance, n.naissance + 650, t);
        const declin = lisse(n.mort - 1000, n.mort, t);
        // évaporation générale à la rédaction : le haut (où le texte s'écrit) se dégage en premier
        const evap = lisse(dr - 450 + n.y * 900, dr + 350 + n.y * 900, t);
        const alpha = apparition * (1 - declin) * (1 - evap);
        let excite = 0;
        if (n.grappe >= 0) {
          const gr = reseau.grappes[n.grappe];
          const age = t - gr.debut - n.distCentre * 2600; // onde qui se propage depuis le centre
          if (age > 0) excite = Math.exp(-age / 420) * Math.min(1, age / 60);
        }
        // léger tremblement organique, propre à chaque neurone
        const graine = n.naissance * 0.013;
        return {
          x: n.x * W + Math.sin(t / 900 + graine) * 2.2,
          y: n.y * H + Math.cos(t / 1100 + graine * 1.7) * 1.8 + (1 - apparition) * 10 - declin * 16 - evap * 34,
          alpha, excite,
        };
      });

      // connexions (courbes), avec croissance à la naissance du neurone récent
      g.lineCap = "round";
      for (const l of reseau.liens) {
        const A = etats[l.a], B = etats[l.b];
        const a = Math.min(A.alpha, B.alpha);
        if (a < 0.01) continue;
        const nb = reseau.neurones[l.b];
        const croissance = lisse(nb.naissance, nb.naissance + 800, t);
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
        const dx = B.x - A.x, dy = B.y - A.y;
        const cx = mx - dy * l.courbure, cy = my + dx * l.courbure;
        const ex = Math.max(A.excite, B.excite);
        g.strokeStyle = `rgba(210, 214, 222, ${a * (0.1 + 0.35 * ex + 0.06 * activite)})`;
        g.lineWidth = 0.7 + ex * 0.6;
        g.beginPath();
        g.moveTo(A.x, A.y);
        if (croissance >= 1) g.quadraticCurveTo(cx, cy, B.x, B.y);
        else {
          // portion [0, croissance] de la courbe de Bézier (subdivision de De Casteljau)
          const u = croissance;
          const q1x = A.x + (cx - A.x) * u, q1y = A.y + (cy - A.y) * u;
          const q2x = cx + (B.x - cx) * u, q2y = cy + (B.y - cy) * u;
          g.quadraticCurveTo(q1x, q1y, q1x + (q2x - q1x) * u, q1y + (q2y - q1y) * u);
        }
        g.stroke();
        // influx : un point lumineux qui parcourt la connexion
        if (croissance >= 1) {
          const u = (t * l.vitesse * (1 + activite * 1.5) + l.phase) % 1;
          const px = (1 - u) * (1 - u) * A.x + 2 * (1 - u) * u * cx + u * u * B.x;
          const py = (1 - u) * (1 - u) * A.y + 2 * (1 - u) * u * cy + u * u * B.y;
          const pa = a * (0.45 + 0.55 * ex) * Math.sin(Math.PI * u);
          const lueur = g.createRadialGradient(px, py, 0, px, py, 5 + ex * 4);
          lueur.addColorStop(0, `rgba(255,255,255,${pa})`);
          lueur.addColorStop(0.25, `rgba(255,255,255,${pa * 0.5})`);
          lueur.addColorStop(1, "rgba(255,255,255,0)");
          g.fillStyle = lueur;
          g.beginPath();
          g.arc(px, py, 5 + ex * 4, 0, Math.PI * 2);
          g.fill();
        }
      }

      // neurones
      for (let i = 0; i < etats.length; i++) {
        const s = etats[i];
        if (s.alpha < 0.01) continue;
        const n = reseau.neurones[i];
        const rayon = n.taille * (1 + s.excite * 0.9);
        if (s.excite > 0.05) {
          const halo = g.createRadialGradient(s.x, s.y, 0, s.x, s.y, rayon * 9);
          halo.addColorStop(0, `rgba(255,255,255,${0.22 * s.excite * s.alpha})`);
          halo.addColorStop(1, "rgba(255,255,255,0)");
          g.fillStyle = halo;
          g.beginPath(); g.arc(s.x, s.y, rayon * 9, 0, Math.PI * 2); g.fill();
        }
        const gris = Math.round(150 + 105 * s.excite);
        g.fillStyle = `rgba(${gris}, ${gris + 2}, ${gris + 6}, ${s.alpha * (0.55 + 0.45 * s.excite)})`;
        g.beginPath(); g.arc(s.x, s.y, rayon, 0, Math.PI * 2); g.fill();
      }

      // décharge d'une source : cercle fin qui s'étend + libellé
      for (const gr of reseau.grappes) {
        const age = t - gr.debut;
        if (age < 0 || age > 2600 || t > dr + 300) continue;
        const k = age / 2600;
        const x = gr.x * W, y = gr.y * H;
        g.strokeStyle = `rgba(255,255,255,${0.35 * (1 - k)})`;
        g.lineWidth = 0.8;
        g.beginPath(); g.arc(x, y, 8 + k * Math.min(W, H) * 0.32, 0, Math.PI * 2); g.stroke();
        const la = lisse(0, 300, age) * (1 - lisse(1800, 2600, age));
        g.font = "500 12px Inter, system-ui, sans-serif";
        g.fillStyle = `rgba(235, 238, 243, ${0.85 * la})`;
        g.textAlign = "center";
        g.fillText(gr.libelle, x, y - 22 - lisse(0, 400, age) * 6);
      }

      // grains : chaque mot se condense à partir d'une poussière qui s'éteint
      const h = grain.getContext("2d")!;
      h.setTransform(dpr, 0, 0, dpr, 0, 0);
      h.clearRect(0, 0, W, H);
      for (let i = 0; i < p.mots.length; i++) {
        const age = t - p.mots[i].instant;
        if (age < 0 || age > VIE_GRAINS) continue;
        const pos = positionsMots.current.get(i);
        if (!pos) continue;
        const r = alea(i * 977 + 13);
        const prog = 1 - Math.pow(1 - Math.min(1, age / 700), 3);
        const vie = Math.sin(Math.PI * Math.min(1, age / VIE_GRAINS));
        for (let k = 0; k < GRAINS_PAR_MOT; k++) {
          const ox = (r() - 0.5) * (pos.w + 16), oy = (r() - 0.5) * (pos.h + 10);
          const disperse = 1.9 - prog * 1.15;
          const x = pos.x + pos.w / 2 + ox * disperse + Math.sin(age / 90 + k) * 0.6;
          const y = pos.y + pos.h / 2 + oy * disperse - prog * 2;
          const blanc = 200 + Math.round(r() * 55);
          h.fillStyle = `rgba(${blanc},${blanc},${blanc},${vie * (0.35 + r() * 0.55)})`;
          const s = 0.6 + r() * 1.0;
          h.fillRect(x, y, s, s);
        }
      }
      // grain de film sur la zone de texte pendant la rédaction, qui s'éteint à la fin
      const film = lisse(dr, dr + 800, t) * (1 - lisse(p.finRedaction, p.finRedaction + 1600, t)) * (0.35 + 0.65 * activite);
      if (film > 0.01) {
        const r = alea(Math.floor(t / 42));
        for (let k = 0; k < 260 * film; k++) {
          h.fillStyle = `rgba(255,255,255,${0.05 + r() * 0.1})`;
          h.fillRect(r() * W, H * 0.12 + r() * H * 0.86, 1, 1);
        }
      }
    };
    id = requestAnimationFrame(dessiner);
    return () => cancelAnimationFrame(id);
  }, [p, reseau, tRef]);

  const enCours = e.etapes.find((s) => s.statut === "en cours");
  return (
    <div className="stage synapses" ref={boite}>
      <canvas ref={fondRef} className="calque" aria-hidden />
      <div className="stage-haut">
        <span className="stage-etat" key={enCours?.detail ?? e.phase}>
          {e.fini ? `A travaillé pendant ${dureeLisible(p.finRedaction)}` : e.phase === "redaction" ? "Rédige" : enCours ? enCours.libelle : "Prépare"}
        </span>
        <span className="stage-compteur">{nf.format(e.tokens)} tokens</span>
      </div>
      {e.phase !== "travail" && (
        <div className="stage-texte stage-texte-synapses">
          <Reponse p={p} e={e} rendreMot={(m, i) => <span className="mot-grain" data-mot={i}>{m.texte}</span>} />
        </div>
      )}
      <canvas ref={grainRef} className="calque calque-dessus" aria-hidden />
    </div>
  );
}
