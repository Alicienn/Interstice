import { Journal, Reponse, type ProprietesPiste } from "../commun";
import { dureeLisible, nf } from "../scenario";

/**
 * Encre — la réponse s'écrit mot à mot. Chaque mot naît flou et teinté d'encre bleue puis
 * sèche en quelques centaines de millisecondes ; une plume lumineuse suit le front d'écriture ;
 * une citation terminée reçoit un reflet qui la « scelle ».
 */
export function Encre({ p, e }: ProprietesPiste) {
  const redige = e.phase !== "travail";
  return (
    <div className={`piste encre ${e.fini ? "fini" : ""}`}>
      <div className={`encre-journal ${e.fini ? "replie" : ""}`}>
        {e.fini ? (
          <p className="bilan">A travaillé pendant {dureeLisible(p.finRedaction)}, {nf.format(e.tokens)} tokens</p>
        ) : (
          <Journal e={e} />
        )}
      </div>
      {redige && (
        <Reponse
          p={p}
          e={e}
          rendreMot={(m, i) => (
            <span className="mot-encre">
              {m.texte}
              {i === e.motsEmis - 1 && !e.fini && <span className="plume" aria-hidden />}
            </span>
          )}
        />
      )}
    </div>
  );
}
