import { useMemo, useState } from "react";
import { ChevronRight, FileText, Folder, Search } from "lucide-react";
import { api } from "../../api/client";
import type { MietteBofip, VueBofipNoeud } from "../../api/types";
import { useAsync } from "../../hooks/useAsync";
import { nombre } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { BofipCrumbs, ReaderError, ReaderLoading } from "./common";

type Props = {
  noeud: string | null;
  trail: MietteBofip[];
  onNavigate: (t: ReaderTarget) => void;
};

export function BofipPlanView({ noeud, trail, onNavigate }: Props) {
  const res = useAsync(() => api.bofipPlan(noeud), [noeud]);
  if (res.status === "loading") return <ReaderLoading />;
  if (res.status === "error") return <ReaderError error={res.error} onRetry={res.reload} />;
  return <Plan n={res.data} trail={trail} onNavigate={onNavigate} />;
}

function Plan({ n, trail, onNavigate }: { n: VueBofipNoeud; trail: MietteBofip[]; onNavigate: (t: ReaderTarget) => void }) {
  const [filtre, setFiltre] = useState("");
  const racine = n.noeud === null;
  // Ascendants : ceux de l'API si fournis (nœud-document), sinon ceux mémorisés pendant la descente.
  const chemin = n.chemin.length > 0 ? n.chemin.filter((m) => m.noeud !== n.noeud) : trail;
  const ici: MietteBofip | null = n.noeud ? { id: n.id ?? n.noeud, noeud: n.noeud, code: n.code, titre: n.titre } : null;
  const total = n.enfants.reduce((acc, e) => acc + (e.id ? 1 : e.nb_documents), 0);

  const visibles = useMemo(() => {
    const f = filtre.trim().toLowerCase();
    if (!f) return n.enfants;
    return n.enfants.filter((e) => e.titre.toLowerCase().includes(f) || (e.code ?? "").toLowerCase().includes(f));
  }, [n.enfants, filtre]);

  return (
    <div className="node">
      {!racine && <BofipCrumbs chemin={chemin} onNavigate={onNavigate} />}
      <header className="node-head">
        <h2 className="node-title">{racine ? "BOFiP-Impôts" : n.titre}</h2>
        <div className="node-meta">
          {racine ? <span>Doctrine administrative · plan de classement</span> : n.code && <span className="mono">{n.code}</span>}
          <span>
            {nombre(total)} document{total > 1 ? "s" : ""}
          </span>
        </div>
        {n.id && (
          <button className="btn btn-sm node-doc-btn" onClick={() => onNavigate({ kind: "bofip", id: n.id! })}>
            <FileText size={14} /> Lire ce document
          </button>
        )}
      </header>

      {racine && (
        <form
          className="search-form"
          onSubmit={(e) => {
            e.preventDefault();
            const q = new FormData(e.currentTarget).get("q")?.toString().trim();
            if (q) onNavigate({ kind: "recherche", q, corpus: "bofip" });
          }}
        >
          <label className="filter big">
            <Search size={16} aria-hidden />
            <input className="input" name="q" placeholder="Rechercher dans le BOFiP…" aria-label="Recherche plein texte BOFiP" />
          </label>
          <button className="btn" type="submit">
            Rechercher
          </button>
        </form>
      )}

      {n.enfants.length > 10 && (
        <div className="node-tools">
          <label className="filter">
            <Search size={14} aria-hidden />
            <input className="input" placeholder="Filtrer cette liste…" value={filtre} onChange={(e) => setFiltre(e.target.value)} />
          </label>
        </div>
      )}

      {n.enfants.length === 0 ? (
        <p className="empty">Ce nœud ne contient aucun élément.</p>
      ) : (
        <ul className="children">
          {visibles.map((e) => {
            const doc = e.id !== null;
            // Un document qui a lui-même des sous-documents : on descend dans le plan (bouton « Lire »).
            const descend = !doc || e.nb_documents > 0;
            return (
              <li key={e.noeud}>
                <button
                  className={`child ${doc ? "child-article" : "child-section"}`}
                  onClick={() =>
                    descend
                      ? onNavigate({ kind: "bofip-plan", noeud: e.noeud, trail: ici ? [...chemin, ici] : [] })
                      : onNavigate({ kind: "bofip", id: e.id! })
                  }
                >
                  <span className="child-icon" aria-hidden>
                    {doc ? <FileText size={15} /> : <Folder size={15} />}
                  </span>
                  <span className="child-title">
                    {e.titre}
                    {e.code && <span className="child-code mono">{e.code}</span>}
                  </span>
                  {descend && (
                    <span className="child-count" title="Documents sous ce nœud">
                      {nombre(e.nb_documents)} doc.
                    </span>
                  )}
                  <ChevronRight size={15} className="child-chev" aria-hidden />
                </button>
              </li>
            );
          })}
          {visibles.length === 0 && <li className="empty small">Aucun élément ne correspond.</li>}
        </ul>
      )}
    </div>
  );
}
