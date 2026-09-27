import { useState } from "react";
import { Search } from "lucide-react";
import DOMPurify from "dompurify";
import { api } from "../../api/client";
import { useAsync } from "../../hooks/useAsync";
import { dateCourte } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { ReaderError, ReaderLoading } from "./common";

type Props = {
  q: string;
  texte: string | null;
  date: string | null;
  onNavigate: (t: ReaderTarget) => void;
};

export function SearchView({ q, texte, date, onNavigate }: Props) {
  const [draft, setDraft] = useState(q);
  const res = useAsync(() => api.recherche(q, texte, date), [q, texte, date]);

  return (
    <div className="search">
      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          const v = draft.trim();
          if (v && v !== q) onNavigate({ kind: "recherche", q: v, texte, date });
        }}
      >
        <label className="filter big">
          <Search size={16} aria-hidden />
          <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Recherche plein texte" />
        </label>
        <button className="btn" type="submit">
          Rechercher
        </button>
      </form>
      <div className="node-meta">
        {texte && <span>dans {texte}</span>}
        {date && <span>au {dateCourte(date)}</span>}
      </div>

      {res.status === "loading" && <ReaderLoading />}
      {res.status === "error" && <ReaderError error={res.error} onRetry={res.reload} />}
      {res.status === "ok" &&
        (res.data.resultats.length === 0 ? (
          <p className="empty">Aucun article ne correspond à « {q} ».</p>
        ) : (
          <>
            <p className="search-count">
              {res.data.resultats.length} résultat{res.data.resultats.length > 1 ? "s" : ""}
            </p>
            <ol className="results">
              {res.data.resultats.map((r) => (
                <li key={r.id}>
                  <button className="result" onClick={() => onNavigate({ kind: "article", id: r.id, date })}>
                    <span className="result-head">
                      <span className="result-num">Art. {r.num}</span>
                      <span className="result-texte">{r.texte_titre}</span>
                    </span>
                    {r.chemin && <span className="result-path">{r.chemin}</span>}
                    <span
                      className="result-extract"
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(r.extrait_html, { ALLOWED_TAGS: ["mark", "b", "em", "i", "strong"] }) }}
                    />
                  </button>
                </li>
              ))}
            </ol>
          </>
        ))}
    </div>
  );
}
