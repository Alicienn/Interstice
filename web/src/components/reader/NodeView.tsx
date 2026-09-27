import { useMemo, useState } from "react";
import { ChevronRight, FileText, Folder, Search } from "lucide-react";
import { api } from "../../api/client";
import type { EnfantNoeud, VueNoeud } from "../../api/types";
import { useAsync } from "../../hooks/useAsync";
import { dateLongue, etatInfo, nombre } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { Breadcrumb, EtatBadge, ReaderError, ReaderLoading } from "./common";

type Props = {
  kind: "section" | "texte";
  id: string;
  date: string | null;
  onNavigate: (t: ReaderTarget) => void;
};

export function NodeView({ kind, id, date, onNavigate }: Props) {
  const res = useAsync(() => (kind === "texte" ? api.texte(id, date) : api.section(id, date)), [kind, id, date]);
  if (res.status === "loading") return <ReaderLoading />;
  if (res.status === "error") return <ReaderError error={res.error} onRetry={res.reload} />;
  return <Noeud n={res.data} date={date} onNavigate={onNavigate} />;
}

function Noeud({ n, date, onNavigate }: { n: VueNoeud; date: string | null; onNavigate: (t: ReaderTarget) => void }) {
  const [filtre, setFiltre] = useState("");
  const [masquerAbroges, setMasquerAbroges] = useState(false);
  const sections = n.enfants.filter((e) => e.kind === "section").length;
  const arts = n.enfants.length - sections;
  const abroges = n.enfants.filter((e) => etatInfo(e.etat).ton === "abroge").length;

  const visibles = useMemo(() => {
    const f = filtre.trim().toLowerCase();
    return n.enfants.filter(
      (e) => (!f || e.titre.toLowerCase().includes(f)) && (!masquerAbroges || etatInfo(e.etat).ton !== "abroge"),
    );
  }, [n.enfants, filtre, masquerAbroges]);

  const open = (e: EnfantNoeud) =>
    onNavigate(e.kind === "section" ? { kind: "section", id: e.id, date } : { kind: "article", id: e.id, date });

  return (
    <div className="node">
      <Breadcrumb chemin={n.chemin} date={date} onNavigate={onNavigate} />
      <header className="node-head">
        <h2 className="node-title">{n.titre}</h2>
        <div className="node-meta">
          {sections > 0 && <span>{nombre(sections)} {sections > 1 ? "subdivisions" : "subdivision"}</span>}
          {arts > 0 && <span>{nombre(arts)} {arts > 1 ? "articles" : "article"}</span>}
          <span>au {dateLongue(n.date)}</span>
        </div>
      </header>

      {n.enfants.length > 8 && (
        <div className="node-tools">
          <label className="filter">
            <Search size={14} aria-hidden />
            <input className="input" placeholder="Filtrer cette liste…" value={filtre} onChange={(e) => setFiltre(e.target.value)} />
          </label>
          {abroges > 0 && (
            <label className="check-inline">
              <input type="checkbox" className="checkbox" checked={masquerAbroges} onChange={(e) => setMasquerAbroges(e.target.checked)} />
              Masquer les abrogés ({abroges})
            </label>
          )}
        </div>
      )}

      {n.enfants.length === 0 ? (
        <p className="empty">Cette subdivision ne contient aucun élément à cette date.</p>
      ) : (
        <ul className="children">
          {visibles.map((e) => {
            const ton = etatInfo(e.etat).ton;
            return (
              <li key={e.id}>
                <button className={`child child-${e.kind} ${ton === "abroge" ? "is-dead" : ""}`} onClick={() => open(e)}>
                  <span className="child-icon" aria-hidden>
                    {e.kind === "section" ? <Folder size={15} /> : <FileText size={15} />}
                  </span>
                  <span className="child-title">{e.titre}</span>
                  {ton !== "vigueur" && <EtatBadge etat={e.etat} />}
                  {e.kind === "section" && e.nb_articles !== undefined && (
                    <span className="child-count" title="Articles en vigueur">
                      {nombre(e.nb_articles)} art.
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
