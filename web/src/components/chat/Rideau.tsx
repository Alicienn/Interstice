import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Message, Part, ToolPart } from "../../api/types";
import { compact, nombre, totalJetons } from "../../lib/format";
import { libelleOutil } from "../../lib/journal";
import { targetFromDoc, type ReaderTarget } from "../../lib/reader";

type Nav = { activeTarget: ReaderTarget | null; onOpenTarget: (t: ReaderTarget) => void };

/** Chiffres qui défilent comme un compteur mécanique (les autres caractères restent fixes). */
export function Odometre({ valeur }: { valeur: string }) {
  return (
    <span className="odometre" aria-label={valeur} role="text">
      {[...valeur].map((c, i) =>
        /\d/.test(c) ? (
          <span key={i} className="odo-col" aria-hidden>
            <span className="odo-ruban" style={{ transform: `translateY(${-Number(c) * 10}%)` }}>
              {"0123456789".split("").map((d) => (
                <span key={d}>{d}</span>
              ))}
            </span>
          </span>
        ) : (
          <span key={i} className="odo-sep" aria-hidden>
            {c === " " || c === " " || c === " " ? " " : c}
          </span>
        ),
      )}
    </span>
  );
}

/** Temps écoulé « mm:ss » (les heures s'ajoutent au-delà : « 1:02:03 »). */
export function chrono(ms: number): string {
  const s = Math.floor(Math.max(0, ms) / 1000);
  const h = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/**
 * Jetons affichés en direct : l'usage exact reçu à la fin de chaque tour (entrée + sortie, cache
 * compté une seule fois), plus l'estimation de ce que le tour en cours a produit depuis.
 */
export function jetonsEnDirect(usageExact: number, estimeActuel: number, estimeAuDernierUsage: number): number {
  return usageExact + Math.max(0, estimeActuel - estimeAuDernierUsage);
}

/** Estimation des jetons produits (≈ 4 caractères par jeton), pour le tour dont l'usage n'est pas encore connu. */
export function jetonsEstimes(parts: Part[]): number {
  let car = 0;
  for (const p of parts) {
    if (p.type === "text" || p.type === "thinking") car += p.text.length;
    else car += JSON.stringify(p.arguments ?? {}).length;
  }
  return Math.round(car / 4);
}

function etatCourant(parts: Part[]): string {
  const dernier = parts[parts.length - 1];
  if (!dernier) return "Prépare";
  if (dernier.type === "thinking") return "Réfléchit";
  if (dernier.type === "text") return "Rédige la réponse";
  const lib = libelleOutil(dernier);
  return lib.objet ? `${lib.action} : ${lib.objet}` : lib.action;
}

/**
 * Scène affichée pendant que l'IA travaille : rien de la réponse, mais ce qui se passe réellement —
 * temps écoulé, jetons produits, sources lues. La réponse se révèle d'un seul geste à la fin.
 */
export function RideauLive({ message, depuis, ...nav }: { message: Message; depuis: number } & Nav) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);
  const parts = message.parts;
  // Point de départ de l'estimation : repris à chaque nouvel usage exact reçu.
  const exact = totalJetons(message.usage);
  const estime = jetonsEstimes(parts);
  const base = useRef({ exact, estime });
  if (base.current.exact !== exact) base.current = { exact, estime };
  const jetons = jetonsEnDirect(exact, estime, base.current.estime);
  const outils = parts.filter((p): p is ToolPart => p.type === "tool");
  const lues = outils.filter((p) => p.status !== "running").length;
  const etat = etatCourant(parts);
  return (
    <div className="rideau" aria-live="off">
      <div className="rideau-chrono">
        <Odometre valeur={chrono(now - depuis)} />
      </div>
      <p className="rideau-etat shimmer" key={etat}>
        {etat}
      </p>
      <div className="rideau-compteurs">
        <div title={`${nombre(jetons)} jetons (entrée + sortie, cache compris une seule fois) ; le tour en cours est estimé`}>
          <Odometre valeur={compact(jetons)} />
          <span className="rideau-libelle">jetons</span>
        </div>
        <div>
          <Odometre valeur={String(lues)} />
          <span className="rideau-libelle">{lues > 1 ? "sources lues" : "source lue"}</span>
        </div>
      </div>
      <div className="rideau-fil" aria-hidden>
        <span />
      </div>
      {outils.length > 0 && (
        <ol className="rideau-sources">
          {outils.slice(-4).map((p, i, arr) => {
            const lib = libelleOutil(p);
            const doc = p.documents[0];
            return (
              <li key={p.call_id} style={{ "--rang": arr.length - 1 - i } as CSSProperties}>
                <button
                  type="button"
                  disabled={!doc}
                  onClick={doc ? () => nav.onOpenTarget(targetFromDoc(doc)) : undefined}
                  title={doc ? `Ouvrir : ${doc.titre}` : undefined}
                >
                  <span className="rideau-action">{lib.action}</span>
                  {lib.objet && <span className="rideau-objet">{lib.objet}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}
      {message.error && <p className="rideau-erreur">{message.error}</p>}
    </div>
  );
}
