import { useState } from "react";
import { Search } from "lucide-react";
import DOMPurify from "dompurify";
import { api } from "../../api/client";
import type { LigneRecherche, LigneRechercheBofip } from "../../api/types";
import { useAsync } from "../../hooks/useAsync";
import { dateCourte, libelleCourt } from "../../lib/format";
import type { Corpus, ReaderTarget } from "../../lib/reader";
import { CorpusSwitch, ReaderError, ReaderLoading } from "./common";

type Props = {
  q: string;
  corpus: Corpus;
  texte: string | null;
  serie: string | null;
  date: string | null;
  onNavigate: (t: ReaderTarget) => void;
};

const extrait = (html: string) => DOMPurify.sanitize(html, { ALLOWED_TAGS: ["mark", "b", "em", "i", "strong"] });

type Resultats = { corpus: "codes"; lignes: LigneRecherche[] } | { corpus: "bofip"; lignes: LigneRechercheBofip[] };

export function SearchView({ q, corpus, texte, serie, date, onNavigate }: Props) {
  const [draft, setDraft] = useState(q);
  const [draftCorpus, setDraftCorpus] = useState<Corpus>(corpus);
  const [draftSerie, setDraftSerie] = useState(serie ?? "");
  const res = useAsync<Resultats>(
    () =>
      corpus === "bofip"
        ? api.bofipRecherche(q, serie).then((r) => ({ corpus: "bofip" as const, lignes: r.resultats }))
        : api.recherche(q, texte, date).then((r) => ({ corpus: "codes" as const, lignes: r.resultats })),
    [q, corpus, texte, serie, date],
  );

  const submit = (c: Corpus = draftCorpus) => {
    const v = draft.trim();
    if (!v) return;
    onNavigate(
      c === "bofip"
        ? { kind: "recherche", q: v, corpus: "bofip", serie: draftSerie.trim().toUpperCase() || null }
        : { kind: "recherche", q: v, corpus: "codes", texte, date },
    );
  };

  const n = res.status === "ok" ? res.data.lignes.length : 0;

  return (
    <div className="search">
      <header className="node-head">
        <h2 className="node-title">Recherche</h2>
      </header>
      <CorpusSwitch
        value={draftCorpus}
        onChange={(c) => {
          setDraftCorpus(c);
          if (draft.trim()) submit(c);
        }}
      />
      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label className="filter big">
          <Search size={16} aria-hidden />
          <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Recherche plein texte" />
        </label>
        {draftCorpus === "bofip" && (
          <input
            className="input serie-input mono"
            value={draftSerie}
            onChange={(e) => setDraftSerie(e.target.value)}
            placeholder="Série"
            title="Restreindre à une série : IR, RPPM, BIC, TVA, CF…"
            aria-label="Série BOFiP"
          />
        )}
        <button className="btn" type="submit">
          Rechercher
        </button>
      </form>
      <div className="node-meta">
        <span>{corpus === "bofip" ? "BOFiP-Impôts" : "Codes"}</span>
        {texte && <span>dans {texte}</span>}
        {serie && <span>série {serie}</span>}
        {date && <span>au {dateCourte(date)}</span>}
      </div>

      {res.status === "loading" && <ReaderLoading />}
      {res.status === "error" && <ReaderError error={res.error} onRetry={res.reload} />}
      {res.status === "ok" &&
        (n === 0 ? (
          <p className="empty">Aucun résultat pour « {q} ».</p>
        ) : (
          <>
            <p className="search-count">
              {n} résultat{n > 1 ? "s" : ""}
            </p>
            <ol className="results">
              {res.data.corpus === "codes"
                ? res.data.lignes.map((r) => (
                    <li key={r.id}>
                      <button className="result" onClick={() => onNavigate({ kind: "article", id: r.id, date })}>
                        <span className="result-head">
                          <span className="result-num">Art. {r.num}</span>
                          <span className="result-texte">{r.texte_titre}</span>
                        </span>
                        {r.chemin && <span className="result-path">{r.chemin}</span>}
                        <span className="result-extract" dangerouslySetInnerHTML={{ __html: extrait(r.extrait_html) }} />
                      </button>
                    </li>
                  ))
                : res.data.lignes.map((r) => (
                    <li key={r.id}>
                      <button className="result" onClick={() => onNavigate({ kind: "bofip", id: r.id })}>
                        <span className="result-head">
                          <span className="result-num">{libelleCourt(r.titre)}</span>
                          {r.nature === "Actualité" && <span className="badge plain">Actualité</span>}
                        </span>
                        <span className="result-path">
                          <span className="mono">{r.boi}</span> · {r.serie} · {dateCourte(r.date)}
                        </span>
                        <span className="result-extract" dangerouslySetInnerHTML={{ __html: extrait(r.extrait_html) }} />
                      </button>
                    </li>
                  ))}
            </ol>
          </>
        ))}
    </div>
  );
}
