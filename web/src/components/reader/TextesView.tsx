import { useMemo, useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import { api } from "../../api/client";
import { useAsync } from "../../hooks/useAsync";
import { useStoredState } from "../../hooks/useStoredState";
import { nombre } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { ReaderError, ReaderLoading } from "./common";

export function TextesView({ onNavigate }: { onNavigate: (t: ReaderTarget) => void }) {
  const res = useAsync(() => api.textes(), []);
  const [fiscal, setFiscal] = useStoredState("interstice.textesFiscal", true);
  const [filtre, setFiltre] = useState("");
  const [q, setQ] = useState("");

  const liste = useMemo(() => {
    if (res.status !== "ok") return [];
    const f = filtre.trim().toLowerCase();
    return res.data.filter(
      (t) => (!fiscal || t.fiscal) && (!f || t.titre.toLowerCase().includes(f) || t.sigle.toLowerCase().includes(f)),
    );
  }, [res, fiscal, filtre]);

  return (
    <div className="textes">
      <header className="node-head">
        <div className="art-code smallcaps">Corpus</div>
        <h2 className="node-title">Parcourir les codes</h2>
        <p className="node-lead">Choisissez un texte, puis descendez dans son plan jusqu'à l'article.</p>
      </header>

      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) onNavigate({ kind: "recherche", q: q.trim() });
        }}
      >
        <label className="filter big">
          <Search size={16} aria-hidden />
          <input className="input" placeholder="Recherche plein texte dans les articles…" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <button className="btn" type="submit" disabled={!q.trim()}>
          Rechercher
        </button>
      </form>

      <div className="node-tools">
        <div className="segmented" role="radiogroup" aria-label="Périmètre">
          <button role="radio" aria-checked={fiscal} className={fiscal ? "on" : ""} onClick={() => setFiscal(true)}>
            Fiscaux
          </button>
          <button role="radio" aria-checked={!fiscal} className={!fiscal ? "on" : ""} onClick={() => setFiscal(false)}>
            Tous
          </button>
        </div>
        <label className="filter">
          <Search size={14} aria-hidden />
          <input className="input" placeholder="Filtrer les textes…" value={filtre} onChange={(e) => setFiltre(e.target.value)} />
        </label>
      </div>

      {res.status === "loading" && <ReaderLoading />}
      {res.status === "error" && <ReaderError error={res.error} onRetry={res.reload} />}
      {res.status === "ok" && (
        <ul className="children textes-list">
          {liste.map((t) => (
            <li key={t.cid}>
              <button className="child texte-row" onClick={() => onNavigate({ kind: "texte", id: t.cid })}>
                <span className="texte-sigle">{t.sigle}</span>
                <span className="child-title">
                  {t.titre}
                  <span className="texte-nature">{t.nature.toLowerCase()}</span>
                </span>
                <span className="child-count">{nombre(t.nb_articles_vigueur)} art.</span>
                <ChevronRight size={15} className="child-chev" aria-hidden />
              </button>
            </li>
          ))}
          {liste.length === 0 && <li className="empty small">Aucun texte ne correspond.</li>}
        </ul>
      )}
    </div>
  );
}
