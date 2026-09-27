import { useEffect, useState, type CSSProperties } from "react";
import type { Message, Part, ToolPart } from "../../api/types";
import { nombre } from "../../lib/format";
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

function chrono(ms: number): string {
  const s = Math.max(0, ms) / 1000;
  const m = Math.floor(s / 60);
  const reste = (s - m * 60).toFixed(1).replace(".", ",").padStart(4, "0");
  return `${String(m).padStart(2, "0")}:${reste}`;
}

/** Estimation des jetons produits jusqu'ici (≈ 4 caractères par jeton) : l'usage exact n'arrive qu'en fin de flux. */
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
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, []);
  const parts = message.parts;
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
        <div title="Estimation en direct ; le décompte exact s'affiche à la fin">
          <Odometre valeur={nombre(jetonsEstimes(parts))} />
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
