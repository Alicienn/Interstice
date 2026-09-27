/**
 * Tracé — un réseau dessiné en traits droits, gris et blanc, en 2D.
 *
 * Une tête lumineuse trace des segments droits de nœud en nœud (comme un traceur), le réseau se
 * densifie dans une zone compacte ; chaque nouveau nœud se relie aussi à ses voisins déjà visités.
 * Quand l'IA lit un document, le tracé file vers un nœud-document qui « encaisse » l'impact :
 * impulsion d'échelle, éclat de traits radiaux, connexions qui s'illuminent, étiquette du document.
 * À la rédaction, le réseau se dissout vers le haut et les mots se condensent à partir de grains fins.
 *
 * Tout est fonction de `t` : rejouable, curseur de lecture compris.
 */
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Reponse } from "../commun";
import { lisse, useHorlogeScene } from "../horloge";
import { alea, dureeLisible, nf, type Prepare } from "../scenario";

interface Noeud { x: number; y: number } // coordonnées normalisées dans la zone du réseau
interface Segment { de: number; vers: number; t0: number; t1: number; doc: number; secondaire: boolean }
interface Trace { noeuds: Noeud[]; segments: Segment[]; atteint: Map<number, number>; docs: { noeud: number; t: number; libelle: string }[] }

const GRAINS_PAR_MOT = 16;
const VIE_GRAINS = 750;
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

/** Échantillonnage de Poisson (rejet simple) dans une ellipse : répartition dense et régulière. */
function semer(r: () => number, n: number, distMin: number): Noeud[] {
  const pts: Noeud[] = [];
  for (let essai = 0; pts.length < n && essai < n * 60; essai++) {
    const a = r() * Math.PI * 2, rr = Math.sqrt(r());
    const p = { x: 0.5 + Math.cos(a) * rr * 0.5, y: 0.5 + Math.sin(a) * rr * 0.5 };
    if (pts.every((q) => Math.hypot(q.x - p.x, q.y - p.y) > distMin)) pts.push(p);
  }
  return pts;
}

function construire(p: Prepare): Trace {
  const r = alea(2027);
  const noeuds = semer(r, 150, 0.052);
  const dist = (a: number, b: number) => Math.hypot(noeuds[a].x - noeuds[b].x, noeuds[a].y - noeuds[b].y);
  const voisins = (i: number, k: number, filtre: (j: number) => boolean) =>
    noeuds.map((_, j) => j).filter((j) => j !== i && filtre(j)).sort((a, b) => dist(i, a) - dist(i, b)).slice(0, k);

  const segments: Segment[] = [];
  const atteint = new Map<number, number>(); // nœud → instant d'arrivée du tracé
  const docs: Trace["docs"] = [];
  const fin = p.sc.debutRedaction;
  const outils = p.sc.etapes.filter((e) => e.type === "outil");
  // départ : le nœud le plus central
  let courant = noeuds.reduce((best, n, i) => (Math.hypot(n.x - 0.5, n.y - 0.5) < Math.hypot(noeuds[best].x - 0.5, noeuds[best].y - 0.5) ? i : best), 0);
  atteint.set(courant, 0);
  let tau = 120;
  let prochainDoc = 0;

  const relier = (i: number, instant: number) => {
    // maillage minimal : rarement, un seul trait fin vers un voisin visité très proche
    if (r() > 0.2) return;
    for (const j of voisins(i, 1, (j) => atteint.has(j) && dist(i, j) < 0.075)) {
      segments.push({ de: j, vers: i, t0: instant + 20, t1: instant + 20 + 90 + dist(i, j) * 600, doc: -1, secondaire: true });
    }
  };

  while (tau < fin - 150) {
    const doc = outils[prochainDoc];
    const versDoc = doc && tau > doc.debut - 520;
    let cible: number;
    let duree: number;
    if (versDoc) {
      // un document : un nœud encore vierge, un peu éloigné, atteint pile au début de la lecture
      const candidats = noeuds.map((_, j) => j).filter((j) => !atteint.has(j) && dist(courant, j) > 0.12 && dist(courant, j) < 0.34);
      cible = candidats.length ? candidats[Math.floor(r() * candidats.length)] : voisins(courant, 1, (j) => !atteint.has(j))[0] ?? courant;
      duree = Math.max(220, doc.debut + 180 - tau);
    } else {
      const libres = voisins(courant, 3, (j) => !atteint.has(j));
      if (!libres.length || r() < 0.22) {
        // ramification : repartir d'un nœud déjà visité (saut sans trait)
        const visites = [...atteint.keys()];
        courant = visites[Math.floor(r() * visites.length)];
        tau += 15;
        continue;
      }
      // parmi les voisins libres, préférer (sans systématisme) celui qui garde le réseau centré
      const centre = (j: number) => Math.hypot(noeuds[j].x - 0.5, noeuds[j].y - 0.5);
      cible = r() < 0.65 ? libres.reduce((a, b) => (centre(a) < centre(b) ? a : b)) : libres[Math.floor(r() * libres.length)];
      duree = 60 + dist(courant, cible) * 700;
    }
    const t1 = tau + duree;
    segments.push({ de: courant, vers: cible, t0: tau, t1, doc: versDoc ? prochainDoc : -1, secondaire: false });
    if (!atteint.has(cible)) { atteint.set(cible, t1); relier(cible, t1); }
    if (versDoc) { docs.push({ noeud: cible, t: t1, libelle: doc.detail }); prochainDoc++; }
    courant = cible;
    tau = t1 + 8 + r() * 30;
  }
  return { noeuds, segments, atteint, docs };
}

export function Trace() {
  const { prep: p, e, tRef } = useHorlogeScene();
  const boite = useRef<HTMLDivElement>(null);
  const fondRef = useRef<HTMLCanvasElement>(null);
  const grainRef = useRef<HTMLCanvasElement>(null);
  const positionsMots = useRef(new Map<number, { x: number; y: number; w: number; h: number }>());
  const trace = useMemo(() => construire(p), [p]);

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
      const dr = p.sc.debutRedaction;
      const g = fond.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);

      // zone du réseau : compacte, centrée ; dissolution vers le haut à la rédaction
      const dissolution = lisse(dr - 150, dr + 1000, t);
      const taille = Math.min(W * 0.62, H * 0.82);
      const ox = (W - taille) / 2, oy = (H - taille) / 2 + 14 - dissolution * 18;
      const P = (i: number) => ({ x: ox + trace.noeuds[i].x * taille, y: oy + trace.noeuds[i].y * taille });
      const global = 1 - dissolution;
      if (global <= 0.001) { dessinerGrains(); return; }

      // champ latent : les nœuds non encore atteints, à peine visibles
      g.fillStyle = `rgba(200, 205, 212, ${0.16 * global * lisse(0, 600, t)})`;
      trace.noeuds.forEach((_, i) => {
        const a = trace.atteint.get(i);
        if (a !== undefined && a <= t) return;
        const q = P(i);
        g.fillRect(q.x - 0.6, q.y - 0.6, 1.2, 1.2);
      });

      // impacts des documents (pour l'illumination des connexions)
      const impact = (i: number) => {
        let m = 0;
        for (const d of trace.docs) {
          if (d.noeud !== i || t < d.t) continue;
          m = Math.max(m, Math.exp(-(t - d.t) / 520));
        }
        return m;
      };

      // segments
      g.lineCap = "round";
      for (const s of trace.segments) {
        if (t < s.t0) continue;
        const A = P(s.de), B = P(s.vers);
        const prog = s.t1 <= t ? 1 : easeInOut((t - s.t0) / (s.t1 - s.t0));
        const x = A.x + (B.x - A.x) * prog, y = A.y + (B.y - A.y) * prog;
        // sillage : blanc juste après le passage, puis refroidit vers le gris
        const refroidi = t > s.t1 ? lisse(0, 900, t - s.t1) : 0;
        const eclat = Math.max(impact(s.vers), impact(s.de));
        const base = s.secondaire ? 0.13 : 0.26;
        const alpha = (base + (1 - refroidi) * (s.secondaire ? 0.25 : 0.55) + eclat * 0.6) * global;
        g.strokeStyle = `rgba(232, 236, 241, ${Math.min(1, alpha)})`;
        g.lineWidth = s.secondaire ? 0.6 : 1;
        g.beginPath(); g.moveTo(A.x, A.y); g.lineTo(x, y); g.stroke();
        // tête du tracé
        if (prog < 1 && !s.secondaire) {
          const tete = g.createRadialGradient(x, y, 0, x, y, 7);
          tete.addColorStop(0, `rgba(255,255,255,${0.9 * global})`);
          tete.addColorStop(0.3, `rgba(255,255,255,${0.25 * global})`);
          tete.addColorStop(1, "rgba(255,255,255,0)");
          g.fillStyle = tete;
          g.beginPath(); g.arc(x, y, 7, 0, Math.PI * 2); g.fill();
        }
      }

      // nœuds atteints
      for (const [i, arrivee] of trace.atteint) {
        if (t < arrivee) continue;
        const q = P(i);
        const pop = easeInOut(Math.min(1, (t - arrivee) / 220));
        g.fillStyle = `rgba(214, 219, 226, ${0.75 * global})`;
        g.beginPath(); g.arc(q.x, q.y, 1.5 * pop, 0, Math.PI * 2); g.fill();
      }

      // documents : impulsion, éclat radial, point blanc, étiquette (placées sans chevauchement)
      const etiquettes: { x: number; y: number; w: number }[] = [];
      for (const d of trace.docs) {
        if (t < d.t) continue;
        const age = t - d.t;
        const q = P(d.noeud);
        const punch = 1 + 1.1 * Math.exp(-age / 140) * Math.sin(Math.min(Math.PI, age / 60));
        // éclat : six traits radiaux courts qui s'étirent et s'éteignent
        if (age < 520) {
          const k = age / 520;
          g.strokeStyle = `rgba(255,255,255,${(1 - k) * 0.9 * global})`;
          g.lineWidth = 1;
          for (let r = 0; r < 6; r++) {
            const a = (r / 6) * Math.PI * 2 + 0.26;
            const r0 = 5 + k * 6, r1 = 8 + k * 14;
            g.beginPath();
            g.moveTo(q.x + Math.cos(a) * r0, q.y + Math.sin(a) * r0);
            g.lineTo(q.x + Math.cos(a) * r1, q.y + Math.sin(a) * r1);
            g.stroke();
          }
        }
        g.fillStyle = `rgba(255,255,255,${global})`;
        g.beginPath(); g.arc(q.x, q.y, 2.6 * punch, 0, Math.PI * 2); g.fill();
        g.strokeStyle = `rgba(255,255,255,${0.35 * global})`;
        g.lineWidth = 1;
        g.beginPath(); g.arc(q.x, q.y, 5, 0, Math.PI * 2); g.stroke();
        // étiquette
        const entree = lisse(60, 380, age);
        const vif = Math.exp(-age / 1600);
        g.font = "500 11.5px Inter, system-ui, sans-serif";
        g.textBaseline = "middle";
        const w = g.measureText(d.libelle).width;
        const aDroite = q.x >= ox + taille / 2;
        let lx = aDroite ? q.x + 12 + (1 - entree) * 6 : q.x - 12 - w - (1 - entree) * 6;
        let ly = q.y;
        for (let essai = 0; essai < 8 && etiquettes.some((o) => Math.abs(o.y - ly) < 15 && lx < o.x + o.w && lx + w > o.x); essai++) {
          ly += 15;
        }
        lx = Math.max(8, Math.min(W - w - 8, lx));
        etiquettes.push({ x: lx, y: ly, w });
        const gris = Math.round(135 + 105 * vif);
        g.textAlign = "left";
        g.fillStyle = `rgba(${gris}, ${gris + 3}, ${gris + 8}, ${entree * global * (0.55 + 0.45 * vif)})`;
        g.fillText(d.libelle, lx, ly);
      }
      dessinerGrains();

      function dessinerGrains() {
        const h = grain!.getContext("2d")!;
        h.setTransform(dpr, 0, 0, dpr, 0, 0);
        h.clearRect(0, 0, W, H);
        for (let i = 0; i < p.mots.length; i++) {
          const age = t - p.mots[i].instant;
          if (age < 0 || age > VIE_GRAINS) continue;
          const pos = positionsMots.current.get(i);
          if (!pos) continue;
          const r = alea(i * 977 + 13);
          const prog = 1 - Math.pow(1 - age / VIE_GRAINS, 3);
          const vie = Math.sin(Math.PI * (age / VIE_GRAINS));
          for (let k = 0; k < GRAINS_PAR_MOT; k++) {
            const ox2 = (r() - 0.5) * (pos.w + 10), oy2 = (r() - 0.5) * (pos.h + 6);
            const disperse = 1.5 - prog * 0.8;
            h.fillStyle = `rgba(235,238,242,${vie * (0.2 + r() * 0.35)})`;
            h.fillRect(pos.x + pos.w / 2 + ox2 * disperse, pos.y + pos.h / 2 + oy2 * disperse - prog * 1.5, 1, 1);
          }
        }
      }
    };
    id = requestAnimationFrame(dessiner);
    return () => cancelAnimationFrame(id);
  }, [p, trace, tRef]);

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
