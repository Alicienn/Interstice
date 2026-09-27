import { FileText, FolderTree, Library, Search, type LucideIcon } from "lucide-react";
import type { DocKind, DocRef } from "../../api/types";
import { dateCourte } from "../../lib/format";

const ICONS: Record<DocKind, LucideIcon> = {
  article: FileText,
  section: FolderTree,
  texte: Library,
  recherche: Search,
};

const KIND_LABEL: Record<DocKind, string> = {
  article: "Article",
  section: "Section",
  texte: "Texte",
  recherche: "Recherche",
};

export function DocCard({ doc, active, onOpen }: { doc: DocRef; active: boolean; onOpen: () => void }) {
  const Icon = ICONS[doc.kind] ?? FileText;
  return (
    <button className={`doc-card kind-${doc.kind} ${active ? "active" : ""}`} onClick={onOpen} title={`Ouvrir : ${doc.titre}`}>
      <span className="doc-icon" aria-hidden>
        <Icon size={15} />
      </span>
      <span className="doc-body">
        <span className="doc-title">{doc.titre}</span>
        <span className="doc-sub">
          <span className="doc-kind">{KIND_LABEL[doc.kind]}</span>
          {doc.sous_titre && <span>{doc.sous_titre}</span>}
          {doc.date && <span className="doc-date">au {dateCourte(doc.date)}</span>}
        </span>
      </span>
    </button>
  );
}
