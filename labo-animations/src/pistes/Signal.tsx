import { useLayoutEffect, useRef, useState } from "react";
import { Reponse, type ProprietesPiste } from "../commun";
import { dureeLisible, nf, tokensEntre } from "../scenario";

const TRANCHE = 100; // ms par barre
const HISTOIRE = 7000; // ms visibles

/**
 * Signal — le rythme du modèle devient visible : une onde trace le débit de tokens en direct
 * (réflexion en petites impulsions, lectures d'outils en pics, rédaction en masse dense).
 * Le texte se développe comme une photographie sous une tête de lecture qui descend avec lui ;
 * à la fin, l'onde s'aplatit en filet et laisse place au bilan.
 */
export function Signal({ p, e }: ProprietesPiste) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const corps = useRef<HTMLDivElement>(null);
  const [tete, setTete] = useState<number | null>(null);
  const pic = useRef(0);

  useLayoutEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const l = c.clientWidth, h = c.clientHeight;
    if (c.width !== l * dpr) { c.width = l * dpr; c.height = h * dpr; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, l, h);
    const style = getComputedStyle(c);
    const accent = style.getPropertyValue("--accent").trim();
    const filet = style.getPropertyValue("--filet").trim();
    const n = Math.floor(HISTOIRE / TRANCHE);
    const largeur = l / n;
    const fin = Math.min(e.t, p.finRedaction);
    const amortir = e.depuisFin > 0 ? Math.max(0, 1 - e.depuisFin / 900) : 1;
    const valeurs: number[] = [];
    for (let k = 0; k < n; k++) {
      const b = fin - (n - 1 - k) * TRANCHE;
      valeurs.push(b <= 0 ? 0 : tokensEntre(p, b - TRANCHE, b));
    }
    pic.current = Math.max(pic.current * 0.97, ...valeurs, 6);
    ctx.fillStyle = filet;
    ctx.fillRect(0, h / 2 - 0.5, l, 1);
    valeurs.forEach((v, k) => {
      const haut = Math.max(1, (v / pic.current) * (h / 2 - 3) * amortir);
      const age = (n - 1 - k) / n; // 0 = plus récent
      ctx.globalAlpha = 0.25 + 0.75 * (1 - age) ** 1.6;
      ctx.fillStyle = accent;
      const x = k * largeur + largeur * 0.18;
      const w = Math.max(1, largeur * 0.64);
      ctx.beginPath();
      ctx.roundRect(x, h / 2 - haut, w, haut * 2, w / 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  });

  useLayoutEffect(() => {
    const plume = corps.current?.querySelector<HTMLElement>(".repere");
    setTete(plume && corps.current ? plume.offsetTop + plume.offsetHeight + 4 : null);
  }, [e.motsEmis]);

  const enCours = e.etapes.find((s) => s.statut === "en cours");
  const libelle = e.fini ? "Terminé" : e.phase === "redaction" ? "Rédaction" : enCours ? `${enCours.libelle} : ${enCours.detail}` : "Prépare";
  return (
    <div className={`piste signal ${e.fini ? "fini" : ""}`}>
      <div className="signal-tete">
        <span className="signal-libelle" key={libelle}>{libelle}</span>
        <span className="signal-debit">
          {e.fini ? `${dureeLisible(p.finRedaction)}, ${nf.format(e.tokens)} tokens` : `${Math.round(e.tokensParSeconde)} tokens/s`}
        </span>
      </div>
      <canvas ref={canvas} className="signal-onde" aria-hidden />
      <div className="signal-corps" ref={corps}>
        {e.phase !== "travail" && (
          <Reponse
            p={p}
            e={e}
            rendreMot={(m, i) => (
              <span className={`mot-signal${i === e.motsEmis - 1 ? " repere" : ""}`}>{m.texte}</span>
            )}
          />
        )}
        {tete !== null && !e.fini && <div className="signal-lecture" style={{ top: tete }} aria-hidden />}
      </div>
    </div>
  );
}
