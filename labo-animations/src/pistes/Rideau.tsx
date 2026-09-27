import type { CSSProperties } from "react";
import { Odometre, Reponse, type ProprietesPiste } from "../commun";
import { dureeLisible, nf } from "../scenario";

function chrono(ms: number): string {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  const reste = (s - m * 60).toFixed(1).replace(".", ",").padStart(4, "0");
  return `${String(m).padStart(2, "0")}:${reste}`;
}

/**
 * Rideau — rien n'est montré tant que l'IA travaille. Une composition de compteurs (temps,
 * tokens, sources) occupe la scène ; à la fin, les compteurs se retirent en pied de réponse et
 * la réponse entière se révèle ligne à ligne derrière un masque.
 */
export function Rideau({ p, e }: ProprietesPiste) {
  const sources = e.etapes.filter((s) => s.type === "outil");
  const enCours = e.etapes.find((s) => s.statut === "en cours");
  const etat = e.phase === "travail" ? (enCours ? `${enCours.libelle} : ${enCours.detail}` : "Prépare")
    : "Rédige la réponse";
  return (
    <div className={`piste rideau ${e.fini ? "leve" : ""}`}>
      <div className="rideau-scene" aria-hidden={e.fini}>
        <div className="rideau-chrono">
          <Odometre valeur={chrono(Math.min(e.t, p.finRedaction))} />
        </div>
        <p className="rideau-etat" key={etat}>{etat}</p>
        <div className="rideau-compteurs">
          <div><Odometre valeur={nf.format(e.tokens)} /><span className="libelle">tokens</span></div>
          <div><Odometre valeur={String(sources.length)} /><span className="libelle">{sources.length > 1 ? "sources lues" : "source lue"}</span></div>
        </div>
        <div className="rideau-fil"><span /></div>
        <ol className="rideau-sources">
          {sources.slice(-4).map((s, i, arr) => (
            <li key={s.debut} style={{ "--rang": arr.length - 1 - i } as CSSProperties}>
              <span>{s.libelle}</span> {s.detail}
            </li>
          ))}
        </ol>
      </div>
      {e.fini && (
        <>
          <Reponse p={p} e={e} classe="revelee" rendreMot={(m) => m.texte} />
          <p className="rideau-pied">
            <span>{dureeLisible(p.finRedaction)} de travail</span>
            <span>{nf.format(e.tokens)} tokens</span>
            <span>{sources.length} sources</span>
          </p>
        </>
      )}
    </div>
  );
}
