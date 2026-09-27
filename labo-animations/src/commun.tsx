import type { ReactNode } from "react";
import type { Etat, Mot, Prepare } from "./scenario";

export interface ProprietesPiste {
  p: Prepare;
  e: Etat;
}

/**
 * Rend la réponse bloc par bloc. `rendreMot` décide de l'apparence de chaque mot
 * (index global, mot, déjà émis ou non) ; `tout` rend aussi les mots non émis.
 */
export function Reponse({ p, e, rendreMot, tout = false, classe = "" }: ProprietesPiste & {
  rendreMot: (m: Mot, i: number, emis: boolean) => ReactNode;
  tout?: boolean;
  classe?: string;
}) {
  const parBloc: { m: Mot; i: number }[][] = p.sc.blocs.map(() => []);
  p.mots.forEach((m, i) => {
    if (tout || i < e.motsEmis) parBloc[m.bloc].push({ m, i });
  });
  const sortie: ReactNode[] = [];
  let puces: ReactNode[] = [];
  const viderPuces = (cle: string) => {
    if (puces.length) sortie.push(<ul key={cle}>{puces}</ul>);
    puces = [];
  };
  p.sc.blocs.forEach((b, bi) => {
    const mots = parBloc[bi];
    if (!mots.length) return;
    const contenu = mots.map(({ m, i }) => (
      // data-front : dernier mot émis, que la scène garde en vue pendant la rédaction
      <span key={i} data-front={i === e.motsEmis - 1 && !e.fini ? "" : undefined}>{rendreMot(m, i, i < e.motsEmis)}{" "}</span>
    ));
    const complet = mots.length === b.texte.split(" ").length && mots[mots.length - 1].i < e.motsEmis;
    if (b.type === "puce") {
      puces.push(<li key={bi}>{contenu}</li>);
      return;
    }
    viderPuces(`ul-${bi}`);
    if (b.type === "titre") sortie.push(<h3 key={bi}>{contenu}</h3>);
    else if (b.type === "citation") sortie.push(<p key={bi} className={`citation${complet ? " complete" : ""}`}>{contenu}</p>);
    else sortie.push(<p key={bi}>{contenu}</p>);
  });
  viderPuces("ul-fin");
  return <div className={`reponse ${classe}`}>{sortie}</div>;
}

/** Journal compact des étapes, comme dans l'application (ligne en cours animée). */
export function Journal({ e, lueur = true }: { e: Etat; lueur?: boolean }) {
  return (
    <ol className="journal">
      {e.etapes.map((s, i) => (
        <li key={i} className={`etape ${s.statut === "en cours" ? "en-cours" : "faite"}`}>
          <span className={`puce-etape ${s.type}`} aria-hidden />
          <span className={s.statut === "en cours" && lueur ? "lueur" : undefined}>
            {s.libelle}<span className="etape-detail"> {s.detail}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Chiffres qui défilent comme un compteur mécanique. */
export function Odometre({ valeur, chiffres }: { valeur: string; chiffres?: number }) {
  const texte = chiffres ? valeur.padStart(chiffres, " ") : valeur;
  return (
    <span className="odometre" aria-label={valeur}>
      {[...texte].map((c, i) =>
        /\d/.test(c) ? (
          <span key={i} className="colonne" aria-hidden>
            <span className="ruban" style={{ transform: `translateY(${-Number(c) * 10}%)` }}>
              {"0123456789".split("").map((d) => <span key={d}>{d}</span>)}
            </span>
          </span>
        ) : (
          <span key={i} className="separateur" aria-hidden>{c === " " ? " " : c}</span>
        ),
      )}
    </span>
  );
}
