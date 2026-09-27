import { AlertTriangle, ChevronRight, RotateCw } from "lucide-react";
import type { Miette, MietteBofip } from "../../api/types";
import { etatInfo } from "../../lib/format";
import type { Corpus, ReaderTarget } from "../../lib/reader";

export function Breadcrumb({
  chemin,
  date,
  onNavigate,
}: {
  chemin: Miette[];
  date?: string | null;
  onNavigate: (t: ReaderTarget) => void;
}) {
  if (chemin.length === 0) return null;
  return (
    <nav className="crumbs" aria-label="Fil d'Ariane">
      {chemin.map((m, i) => (
        <span key={m.id} className="crumb">
          {i > 0 && <ChevronRight size={12} className="crumb-sep" aria-hidden />}
          <button
            className={`crumb-btn ${m.kind === "texte" ? "is-texte" : ""}`}
            onClick={() => onNavigate({ kind: m.kind, id: m.id, date: date ?? null })}
            title={m.titre}
          >
            {m.titre}
          </button>
        </span>
      ))}
    </nav>
  );
}

/** Fil d'Ariane du plan de classement BOFiP ; `currentId` = document affiché (non cliquable). */
export function BofipCrumbs({
  chemin,
  currentId,
  onNavigate,
}: {
  chemin: MietteBofip[];
  currentId?: string | null;
  onNavigate: (t: ReaderTarget) => void;
}) {
  const items = chemin.filter((m) => !currentId || m.id !== currentId);
  return (
    <nav className="crumbs" aria-label="Plan de classement">
      <span className="crumb">
        <button className="crumb-btn is-texte" onClick={() => onNavigate({ kind: "bofip-plan", noeud: null })}>
          BOFiP-Impôts
        </button>
      </span>
      {items.map((m, i) => (
        <span key={m.noeud} className="crumb">
          <ChevronRight size={12} className="crumb-sep" aria-hidden />
          <button
            className="crumb-btn"
            onClick={() => onNavigate({ kind: "bofip-plan", noeud: m.noeud, trail: items.slice(0, i) })}
            title={m.code ? `${m.code} — ${m.titre}` : m.titre}
          >
            {m.titre}
          </button>
        </span>
      ))}
    </nav>
  );
}

export function EtatBadge({ etat }: { etat: string }) {
  const { label, ton } = etatInfo(etat);
  return <span className={`badge ${ton}`}>{label}</span>;
}

export function ReaderLoading() {
  return (
    <div className="reader-loading" aria-busy="true" aria-label="Chargement">
      <div className="skeleton" style={{ height: 11, width: "55%", marginBottom: 22 }} />
      <div className="skeleton" style={{ height: 30, width: "48%", marginBottom: 14 }} />
      <div className="skeleton" style={{ height: 12, width: "32%", marginBottom: 30 }} />
      {[96, 100, 88, 94, 70].map((w, i) => (
        <div key={i} className="skeleton" style={{ height: 13, width: `${w}%`, marginBottom: 11 }} />
      ))}
    </div>
  );
}

export function ReaderError({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="reader-error">
      <div className="alert">
        <AlertTriangle size={15} />
        <span>{error}</span>
      </div>
      <button className="btn btn-sm" onClick={onRetry}>
        <RotateCw size={13} /> Réessayer
      </button>
    </div>
  );
}

export function CorpusSwitch({ value, onChange }: { value: Corpus; onChange: (c: Corpus) => void }) {
  return (
    <div className="segmented" role="radiogroup" aria-label="Corpus">
      <button type="button" role="radio" aria-checked={value === "codes"} className={value === "codes" ? "on" : ""} onClick={() => onChange("codes")}>
        Codes
      </button>
      <button type="button" role="radio" aria-checked={value === "bofip"} className={value === "bofip" ? "on" : ""} onClick={() => onChange("bofip")}>
        BOFiP
      </button>
    </div>
  );
}
