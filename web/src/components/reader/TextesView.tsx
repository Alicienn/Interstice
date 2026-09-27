import { useMemo, useState } from "react";
import { ChevronRight, ScrollText, Search } from "lucide-react";
import { api } from "../../api/client";
import { useAsync } from "../../hooks/useAsync";
import { useStoredState } from "../../hooks/useStoredState";
import { nombre } from "../../lib/format";
import type { Corpus, ReaderTarget } from "../../lib/reader";
import { CorpusSwitch, ReaderError, ReaderLoading } from "./common";

export function TextesView({ onNavigate }: { onNavigate: (t: ReaderTarget) => void }) {
  const res = useAsync(() => api.textes(), []);
  const [fiscal, setFiscal] = useStoredState("interstice.textesFiscal", true);
  const [filtre, setFiltre] = useState("");
  const [q, setQ] = useState("");
  const [corpus, setCorpus] = useState<Corpus>("codes");

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
        <h2 className="node-title">Parcourir le corpus</h2>
        <p className="node-lead">Choisissez un code ou le BOFiP, puis descendez dans le plan jusqu'au document.</p>
      </header>

      <div className="search-corpus">
        <CorpusSwitch value={corpus} onChange={setCorpus} />
      </div>
      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) onNavigate({ kind: "recherche", q: q.trim(), corpus });
        }}
      >
        <label className="filter big">
          <Search size={16} aria-hidden />
          <input
            className="input"
            placeholder={corpus === "codes" ? "Recherche plein texte dans les articles…" : "Recherche plein texte dans le BOFiP…"}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Recherche plein texte"
          />
        </label>
        <button className="btn" type="submit" disabled={!q.trim()}>
          Rechercher
        </button>
      </form>

      <button className="bofip-entry" onClick={() => onNavigate({ kind: "bofip-plan", noeud: null })}>
        <span className="bofip-entry-icon" aria-hidden>
          <ScrollText size={18} />
        </span>
        <span className="bofip-entry-body">
          <span className="bofip-entry-title">BOFiP-Impôts</span>
          <span className="bofip-entry-sub">Doctrine administrative — plan de classement par série (IR, RPPM, BIC, TVA, CF…)</span>
        </span>
        <ChevronRight size={16} className="child-chev" aria-hidden />
      </button>

      <h3 className="list-h">Codes et textes</h3>
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
