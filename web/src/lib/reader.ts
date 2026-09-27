import type { DocRef, MietteBofip } from "../api/types";

export type Corpus = "codes" | "bofip";

/** Ce qu'affiche le panneau de lecture. */
export type ReaderTarget =
  | { kind: "article"; id: string; date?: string | null }
  | { kind: "section"; id: string; date?: string | null }
  | { kind: "texte"; id: string; date?: string | null }
  | { kind: "recherche"; q: string; corpus?: Corpus; texte?: string | null; serie?: string | null; date?: string | null }
  | { kind: "textes" }
  | { kind: "bofip"; id: string; ancre?: string | null }
  /** `trail` : ascendants connus côté client (l'API ne fournit le chemin que pour un nœud-document). */
  | { kind: "bofip-plan"; noeud: string | null; trail?: MietteBofip[] };

/**
 * Une recherche BOFiP est renvoyée par le backend comme un DocRef `recherche` dont le titre commence
 * par « BOFiP » (cf. outils/bofip.py) : c'est le seul indice disponible pour choisir le corpus.
 */
export function isBofipSearch(doc: DocRef): boolean {
  return doc.kind === "recherche" && /^bofip\b/i.test(doc.titre.trim());
}

export function targetFromDoc(doc: DocRef): ReaderTarget {
  switch (doc.kind) {
    case "recherche":
      return isBofipSearch(doc)
        ? { kind: "recherche", q: doc.id, corpus: "bofip" }
        : { kind: "recherche", q: doc.id, corpus: "codes", date: doc.date };
    case "bofip":
      return { kind: "bofip", id: doc.id };
    default:
      return { kind: doc.kind, id: doc.id, date: doc.date };
  }
}

export function targetKey(t: ReaderTarget): string {
  switch (t.kind) {
    case "textes":
      return "textes";
    case "recherche":
      return `recherche:${t.corpus ?? "codes"}:${t.q}:${t.texte ?? ""}:${t.serie ?? ""}:${t.date ?? ""}`;
    case "bofip":
      return `bofip:${t.id}:${t.ancre ?? ""}`;
    case "bofip-plan":
      return `bofip-plan:${t.noeud ?? ""}`;
    default:
      return `${t.kind}:${t.id}:${t.date ?? ""}`;
  }
}

/** Même document, sans tenir compte de la date (pour surligner la carte active). */
export function sameDoc(t: ReaderTarget | null, doc: DocRef): boolean {
  if (!t) return false;
  if (doc.kind === "recherche") return t.kind === "recherche" && t.q === doc.id;
  if (doc.kind === "bofip") return t.kind === "bofip" && t.id === doc.id;
  return t.kind === doc.kind && "id" in t && t.id === doc.id;
}

export type ReaderHistory = { entries: ReaderTarget[]; index: number };

export const emptyHistory: ReaderHistory = { entries: [], index: -1 };

export function pushTarget(h: ReaderHistory, t: ReaderTarget): ReaderHistory {
  const current = h.entries[h.index];
  if (current && targetKey(current) === targetKey(t)) return h;
  const entries = [...h.entries.slice(0, h.index + 1), t].slice(-100);
  return { entries, index: entries.length - 1 };
}
