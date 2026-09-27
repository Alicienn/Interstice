import type { DocRef } from "../api/types";

/** Ce qu'affiche le panneau de lecture. */
export type ReaderTarget =
  | { kind: "article"; id: string; date?: string | null }
  | { kind: "section"; id: string; date?: string | null }
  | { kind: "texte"; id: string; date?: string | null }
  | { kind: "recherche"; q: string; texte?: string | null; date?: string | null }
  | { kind: "textes" };

export function targetFromDoc(doc: DocRef): ReaderTarget {
  if (doc.kind === "recherche") return { kind: "recherche", q: doc.id, date: doc.date };
  return { kind: doc.kind, id: doc.id, date: doc.date };
}

export function targetKey(t: ReaderTarget): string {
  switch (t.kind) {
    case "textes":
      return "textes";
    case "recherche":
      return `recherche:${t.q}:${t.texte ?? ""}:${t.date ?? ""}`;
    default:
      return `${t.kind}:${t.id}:${t.date ?? ""}`;
  }
}

/** Même document, sans tenir compte de la date (pour surligner la carte active). */
export function sameDoc(t: ReaderTarget | null, doc: DocRef): boolean {
  if (!t) return false;
  if (doc.kind === "recherche") return t.kind === "recherche" && t.q === doc.id;
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
