import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowDownLeft, ArrowUpRight, ExternalLink, FileText, History, ListTree, Paperclip, Scale } from "lucide-react";
import { api } from "../../api/client";
import type { RefBofip, VueBofip } from "../../api/types";
import { useAsync } from "../../hooks/useAsync";
import { dateCourte, dateLongue, libelleCourt, nombre, taille } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { BofipCrumbs, ReaderError, ReaderLoading } from "./common";
import { ANCRE_PREFIX, LegalHtml, prepareLegalHtml } from "./LegalHtml";

type Props = {
  id: string;
  ancre: string | null;
  onNavigate: (t: ReaderTarget) => void;
  onArticle: (id: string) => void;
};

export function BofipView({ id, ancre, onNavigate, onArticle }: Props) {
  const res = useAsync(() => api.bofipDocument(id), [id]);
  if (res.status === "loading") return <ReaderLoading />;
  if (res.status === "error") return <ReaderError error={res.error} onRetry={res.reload} />;
  return <Document d={res.data} ancre={ancre} onNavigate={onNavigate} onArticle={onArticle} />;
}

type Onglet = "articles" | "cite" | "citepar" | "versions";

function Document({
  d,
  ancre,
  onNavigate,
  onArticle,
}: {
  d: VueBofip;
  ancre: string | null;
  onNavigate: (t: ReaderTarget) => void;
  onArticle: (id: string) => void;
}) {
  const prepared = useMemo(() => prepareLegalHtml(d.html, "bofip"), [d.html]);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [onglet, setOnglet] = useState<Onglet>(d.articles_cites.length > 0 ? "articles" : "cite");
  const titreCourt = libelleCourt(d.titre);
  const openBofip = (id: string, a: string | null = null) => onNavigate({ kind: "bofip", id, ancre: a });

  // Ancre demandée par un lien `data-ancre` : défile jusqu'à l'élément correspondant.
  useEffect(() => {
    if (!ancre || !bodyRef.current) return;
    const esc = CSS.escape(`${ANCRE_PREFIX}${ancre}`);
    const el = bodyRef.current.querySelector<HTMLElement>(`#${esc}, [name="${esc}"]`);
    el?.scrollIntoView({ block: "start" });
  }, [ancre, prepared]);

  const goTo = (tocId: string) => {
    bodyRef.current?.querySelector<HTMLElement>(`[data-toc="${tocId}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const fichiers = d.relations.fichiers;

  return (
    <article className="art bofip">
      {d.chemin.length > 0 && <BofipCrumbs chemin={d.chemin} currentId={d.pgp} onNavigate={onNavigate} />}

      <header className="art-head">
        <h2 className="doc-h">{titreCourt}</h2>
        {titreCourt !== d.titre && <p className="doc-fulltitle">{d.titre}</p>}
        <div className="art-status">
          <span className="badge plain">{d.nature === "Actualité" ? "Actualité" : d.type_contenu || "Commentaire"}</span>
          {!d.courant && <span className="badge modifie">Version antérieure</span>}
          <span className="art-period">publié le {dateLongue(d.date)}</span>
          {d.permalien && (
            <a className="art-lf" href={d.permalien} target="_blank" rel="noopener noreferrer">
              bofip.impots.gouv.fr <ExternalLink size={12} />
            </a>
          )}
        </div>
        <div className="doc-ident">
          <span className="mono">{d.boi}</span>
          <span className="mono muted">{d.pgp}</span>
          {!d.courant && (
            <button className="linklike link-accent" onClick={() => openBofip(d.pgp)}>
              Voir la version en vigueur
            </button>
          )}
        </div>
        {d.homonymes.length > 0 && (
          <p className="doc-note">
            Autres documents sous ce BOI : {d.homonymes.map((h) => (typeof h === "string" ? h : JSON.stringify(h))).join(", ")}
          </p>
        )}
      </header>

      {prepared.toc.length >= 3 && (
        <details className="toc" open={prepared.toc.length <= 14}>
          <summary>
            <ListTree size={14} aria-hidden /> Sommaire <span className="count">{prepared.toc.length}</span>
          </summary>
          <ol className="toc-list">
            {prepared.toc.map((t) => (
              <li key={t.id} className={`toc-l${t.level}`}>
                <button onClick={() => goTo(t.id)}>{t.text}</button>
              </li>
            ))}
          </ol>
        </details>
      )}

      <LegalHtml
        ref={bodyRef}
        html={d.html}
        prepared={prepared.html}
        variant="bofip"
        className="art-text bofip-text"
        onArticle={onArticle}
        onBofip={openBofip}
      />

      <section className="art-section">
        <div className="tabs" role="tablist">
          <Tab on={onglet === "articles"} onClick={() => setOnglet("articles")} icon={<Scale size={13} />} label="Articles cités" n={d.articles_cites.length} />
          <Tab on={onglet === "cite"} onClick={() => setOnglet("cite")} icon={<ArrowUpRight size={13} />} label="Cite" n={d.relations.sortantes.length + fichiers.length} />
          <Tab on={onglet === "citepar"} onClick={() => setOnglet("citepar")} icon={<ArrowDownLeft size={13} />} label="Cité par" n={d.relations.entrantes.length} />
          <Tab on={onglet === "versions"} onClick={() => setOnglet("versions")} icon={<History size={13} />} label="Versions" n={d.versions.length} />
        </div>

        {onglet === "articles" &&
          (d.articles_cites.length === 0 ? (
            <p className="empty small">Aucun article de loi repéré dans ce document.</p>
          ) : (
            <ul className="renvois">
              {d.articles_cites.map((a) => (
                <li key={`${a.code}:${a.num}`}>
                  {a.article_id ? (
                    <button className="ref-row" onClick={() => onArticle(a.article_id!)}>
                      <span className="ref-main">{a.libelle}</span>
                      <span className="ref-meta">{a.occurrences > 1 ? `${nombre(a.occurrences)} mentions` : "1 mention"}</span>
                    </button>
                  ) : (
                    <div className="ref-row unresolved" title="Article non trouvé dans la base LEGI">
                      <span className="ref-main">{a.libelle}</span>
                      <span className="ref-meta">{a.occurrences > 1 ? `${nombre(a.occurrences)} mentions` : "1 mention"}</span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ))}

        {onglet === "cite" && (
          <>
            <RefList refs={d.relations.sortantes} empty="Ce document ne renvoie à aucun autre document BOFiP." onOpen={openBofip} />
            {fichiers.length > 0 && (
              <>
                <h4 className="sub-h">
                  <Paperclip size={13} /> Pièces jointes
                </h4>
                <ul className="renvois">
                  {fichiers.map((f) => (
                    <li key={f.pgp}>
                      <div className="ref-row unresolved" title="Pièce jointe non servie par Interstice">
                        <span className="ref-main">{f.titre || f.pgp}</span>
                        <span className="ref-meta">
                          {[f.mime?.split("/").pop()?.toUpperCase(), taille(f.taille), "non disponible"].filter(Boolean).join(" · ")}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}

        {onglet === "citepar" && (
          <RefList refs={d.relations.entrantes} empty="Aucun document BOFiP ne renvoie ici." onOpen={openBofip} />
        )}

        {onglet === "versions" &&
          (d.versions.length === 0 ? (
            <p className="empty small">Aucune version antérieure archivée.</p>
          ) : (
            <ol className="versions">
              {d.courant && (
                <li className="version current">
                  <button className="version-btn" disabled aria-current="true">
                    <span className="version-dot" aria-hidden />
                    <span className="version-dates">Version en vigueur · {dateCourte(d.date)}</span>
                    <span className="version-here">affichée</span>
                  </button>
                </li>
              )}
              {d.versions.map((v) => {
                const cur = v.id === d.id;
                return (
                  <li key={v.id} className={`version ${cur ? "current" : ""}`}>
                    <button className="version-btn" disabled={cur} onClick={() => openBofip(v.id)} aria-current={cur ? "true" : undefined}>
                      <span className="version-dot" aria-hidden />
                      <span className="version-dates">{dateCourte(v.date)}</span>
                      <span className="version-motif">{v.motif}</span>
                      {cur && <span className="version-here">affichée</span>}
                    </button>
                  </li>
                );
              })}
            </ol>
          ))}
      </section>
    </article>
  );
}

function Tab({ on, onClick, icon, label, n }: { on: boolean; onClick: () => void; icon: ReactNode; label: string; n: number }) {
  return (
    <button role="tab" aria-selected={on} className={`tab ${on ? "on" : ""}`} onClick={onClick}>
      {icon} {label} <span className="count">{n}</span>
    </button>
  );
}

function RefList({ refs, empty, onOpen }: { refs: RefBofip[]; empty: string; onOpen: (id: string) => void }) {
  if (refs.length === 0) return <p className="empty small">{empty}</p>;
  return (
    <ul className="renvois">
      {refs.map((r, i) => (
        <li key={`${r.id}-${i}`}>
          {r.disponible ? (
            <button className="ref-row" onClick={() => onOpen(r.id)}>
              <FileText size={14} className="ref-icon" aria-hidden />
              <span className="ref-main">{libelleCourt(r.titre) || r.boi || r.id}</span>
              <span className="ref-meta">
                <span className="mono">{r.boi ?? r.id}</span>
                {r.date && ` · ${dateCourte(r.date)}`}
              </span>
            </button>
          ) : (
            <div className="ref-row unresolved" title="Document absent du corpus">
              <FileText size={14} className="ref-icon" aria-hidden />
              <span className="ref-main">{r.id}</span>
              <span className="ref-meta">non disponible</span>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
