import { useState } from "react";
import { ArrowDownLeft, ArrowUpRight, ChevronRight, ExternalLink, History, ScrollText, StickyNote } from "lucide-react";
import { api } from "../../api/client";
import type { Renvoi, VueArticle } from "../../api/types";
import { useAsync } from "../../hooks/useAsync";
import { dateCourte, dateLongue, etatInfo, finOuverte, libelleCourt, nombre, periode } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { Breadcrumb, EtatBadge, ReaderError, ReaderLoading } from "./common";
import { LegalHtml } from "./LegalHtml";

type Props = {
  id: string;
  date: string | null;
  onNavigate: (t: ReaderTarget) => void;
  onArticle: (id: string) => void;
};

export function ArticleView({ id, date, onNavigate, onArticle }: Props) {
  const res = useAsync(() => api.article(id, date), [id, date]);
  if (res.status === "loading") return <ReaderLoading />;
  if (res.status === "error") return <ReaderError error={res.error} onRetry={res.reload} />;
  return <Article a={res.data} date={date} onNavigate={onNavigate} onArticle={onArticle} />;
}

function Article({
  a,
  date,
  onNavigate,
  onArticle,
}: {
  a: VueArticle;
  date: string | null;
  onNavigate: (t: ReaderTarget) => void;
  onArticle: (id: string) => void;
}) {
  const doctrine = a.doctrine ?? [];
  const [onglet, setOnglet] = useState<"sortants" | "entrants" | "doctrine">(
    a.renvois_sortants.length === 0 && a.renvois_entrants.length > 0 ? "entrants" : "sortants",
  );
  const chemin = a.chemin.length > 0 ? a.chemin : [{ id: a.texte_cid, kind: "texte" as const, titre: a.texte_titre }];
  const renvois = onglet === "sortants" ? a.renvois_sortants : onglet === "entrants" ? a.renvois_entrants : [];
  const versions = [...a.versions].sort((x, y) => y.date_debut.localeCompare(x.date_debut));

  return (
    <article className="art">
      <Breadcrumb chemin={chemin} date={date} onNavigate={onNavigate} />

      <header className="art-head">
        <h2 className="doc-h">
          <span className="doc-h-pre">Article</span> {a.num}
        </h2>
        <div className="art-status">
          <EtatBadge etat={a.etat} />
          <span className="art-period">{periode(a.date_debut, a.date_fin)}</span>
          {date && <span className="art-asof">· consulté au {dateCourte(date)}</span>}
          <span className="art-links">
            <button
              className="chip-link"
              onClick={() => onNavigate({ kind: "texte", id: a.texte_cid, date })}
              title={`Plan : ${a.texte_titre}`}
            >
              {a.sigle ?? a.texte_titre}
            </button>
            <a className="chip-link" href={a.url_legifrance} target="_blank" rel="noopener noreferrer">
              Légifrance <ExternalLink size={12} />
            </a>
          </span>
        </div>
      </header>

      <LegalHtml html={a.html} onArticle={onArticle} className="art-text" />

      {a.nota_html && (
        <details className="nota">
          <summary>
            <ChevronRight size={14} className="chev" />
            <StickyNote size={14} />
            Nota
          </summary>
          <LegalHtml html={a.nota_html} onArticle={onArticle} className="nota-text" />
        </details>
      )}

      {versions.length > 0 && (
        <section className="art-section">
          <h3 className="art-h3">
            <History size={14} /> Versions <span className="count">{versions.length}</span>
          </h3>
          <ol className="versions">
            {versions.map((v) => {
              const cur = v.id === a.id;
              const { ton } = etatInfo(v.etat);
              return (
                <li key={v.id} className={`version ${cur ? "current" : ""} ton-${ton}`}>
                  <button
                    className="version-btn"
                    onClick={() => !cur && onNavigate({ kind: "article", id: v.id })}
                    disabled={cur}
                    aria-current={cur ? "true" : undefined}
                  >
                    <span className="version-dot" aria-hidden />
                    <span className="version-dates">
                      {finOuverte(v.date_fin)
                        ? `Depuis le ${dateLongue(v.date_debut)}`
                        : `${dateCourte(v.date_debut)} → ${dateCourte(v.date_fin)}`}
                    </span>
                    <EtatBadge etat={v.etat} />
                    {cur && <span className="version-here">affichée</span>}
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      <section className="art-section">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={onglet === "sortants"} className={`tab ${onglet === "sortants" ? "on" : ""}`} onClick={() => setOnglet("sortants")}>
            <ArrowUpRight size={13} /> Cite <span className="count">{a.renvois_sortants.length}</span>
          </button>
          <button role="tab" aria-selected={onglet === "entrants"} className={`tab ${onglet === "entrants" ? "on" : ""}`} onClick={() => setOnglet("entrants")}>
            <ArrowDownLeft size={13} /> Cité par <span className="count">{a.renvois_entrants.length}</span>
          </button>
          <button role="tab" aria-selected={onglet === "doctrine"} className={`tab ${onglet === "doctrine" ? "on" : ""}`} onClick={() => setOnglet("doctrine")}>
            <ScrollText size={13} /> Doctrine (BOFiP) <span className="count">{doctrine.length}</span>
          </button>
        </div>
        {onglet === "doctrine" ? (
          doctrine.length === 0 ? (
            <p className="empty small">
              {a.doctrine === undefined ? "Doctrine non fournie par le serveur." : "Aucun document BOFiP ne cite cet article."}
            </p>
          ) : (
            <ul className="renvois">
              {doctrine.map((d) => (
                <li key={d.id}>
                  <button className="ref-row" onClick={() => onNavigate({ kind: "bofip", id: d.id })}>
                    <ScrollText size={14} className="ref-icon" aria-hidden />
                    <span className="ref-main">
                      {libelleCourt(d.titre)}
                      {d.nature === "Actualité" && <span className="badge plain ref-badge">Actualité</span>}
                    </span>
                    <span className="ref-meta">
                      <span className="mono">{d.boi}</span> · {dateCourte(d.date)} ·{" "}
                      {d.occurrences > 1 ? `${nombre(d.occurrences)} mentions` : "1 mention"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : renvois.length === 0 ? (
          <p className="empty small">{onglet === "sortants" ? "Aucun renvoi sortant." : "Aucun article ne renvoie ici."}</p>
        ) : (
          <ul className="renvois">
            {renvois.map((r, i) => (
              <RenvoiItem key={`${r.id ?? r.libelle}-${i}`} r={r} onArticle={onArticle} />
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}

function RenvoiItem({ r, onArticle }: { r: Renvoi; onArticle: (id: string) => void }) {
  const content = (
    <>
      <span className="renvoi-num">{r.num ? `Art. ${r.num}` : r.libelle}</span>
      <span className="renvoi-texte">{r.texte_titre}</span>
      {r.num && r.libelle && <span className="renvoi-lib">{r.libelle}</span>}
      <span className="renvoi-type smallcaps">{r.typelien.toLowerCase()}</span>
    </>
  );
  return (
    <li>
      {r.id ? (
        <button className="renvoi-row" onClick={() => onArticle(r.id!)}>
          {content}
        </button>
      ) : (
        <div className="renvoi-row unresolved" title="Renvoi non résolu dans le corpus">
          {content}
        </div>
      )}
    </li>
  );
}
