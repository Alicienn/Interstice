import { AlertTriangle, ChevronRight, RotateCw } from "lucide-react";
import type { Miette } from "../../api/types";
import { etatInfo } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";

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
