import { Journal, Reponse, type ProprietesPiste } from "../commun";
import { alea, dureeLisible, nf } from "../scenario";

const GLYPHES = "§¶†‡°№∴≡abcdefghijklmnopqrstuvwxyzéèàç0123456789";
const DUREE_DECHIFFRAGE = 420; // ms pour qu'un mot se fixe
const DECALAGE_LETTRE = 22; // ms entre deux lettres

/**
 * Caviardage — la structure de la réponse est posée d'emblée, entièrement caviardée comme un
 * document administratif. Au fil de la rédaction, chaque mot est déchiffré : ses lettres
 * défilent parmi des glyphes juridiques (§ ¶ †) puis se fixent de gauche à droite. Aucun saut de
 * mise en page : le texte occupe dès le départ sa place définitive.
 */
export function Caviardage({ p, e }: ProprietesPiste) {
  const redige = e.phase !== "travail";
  return (
    <div className={`piste caviardage ${e.fini ? "fini" : ""}`}>
      {e.fini ? (
        <p className="bilan">Déchiffré en {dureeLisible(p.finRedaction)}, {nf.format(e.tokens)} tokens</p>
      ) : (
        <Journal e={e} />
      )}
      <Reponse
        p={p}
        e={e}
        tout
        classe={redige ? "ouvert" : "scelle"}
        rendreMot={(m, i, emis) => {
          if (!emis) return <span className="cache">{m.texte}</span>;
          const age = e.t - m.instant;
          if (age >= DUREE_DECHIFFRAGE + m.texte.length * DECALAGE_LETTRE) return <span className="clair">{m.texte}</span>;
          const r = alea(i * 131 + Math.floor(e.t / 45));
          return (
            <span className="dechiffre" aria-label={m.texte}>
              {[...m.texte].map((c, k) =>
                age >= DUREE_DECHIFFRAGE * 0.4 + k * DECALAGE_LETTRE || /[\s,.;:()'’]/.test(c)
                  ? <span key={k}>{c}</span>
                  : <span key={k} className="glyphe">{GLYPHES[Math.floor(r() * GLYPHES.length)]}</span>,
              )}
            </span>
          );
        }}
      />
    </div>
  );
}
