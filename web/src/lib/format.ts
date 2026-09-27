// Mise en forme (français) : dates, états LEGI, noms d'outils, résumés d'arguments.

import type { Usage } from "../api/types";

const MOIS = [
  "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

/** « 2024-01-01 » → « 1er janvier 2024 ». Renvoie la chaîne telle quelle si non reconnue. */
export function dateLongue(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const j = Number(m[3]);
  return `${j === 1 ? "1er" : j} ${MOIS[Number(m[2]) - 1] ?? ""} ${m[1]}`;
}

/** « 2024-01-01 » → « 01/01/2024 ». */
export function dateCourte(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** Date de fin « ouverte » dans LEGI (2999-01-01). */
export function finOuverte(iso: string | null | undefined): boolean {
  return !iso || iso.startsWith("2999");
}

export function periode(debut: string, fin: string): string {
  if (finOuverte(fin)) return `depuis le ${dateLongue(debut)}`;
  return `du ${dateLongue(debut)} au ${dateLongue(fin)}`;
}

/** Horodatage relatif pour la liste des conversations. */
export function ilYA(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.round((now - t) / 1000);
  if (s < 60) return "à l'instant";
  const min = Math.round(s / 60);
  if (min < 60) return `il y a ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `il y a ${h} h`;
  const j = Math.round(h / 24);
  if (j < 7) return j === 1 ? "hier" : `il y a ${j} j`;
  return dateCourte(new Date(t).toISOString());
}

export type Ton = "vigueur" | "modifie" | "abroge" | "neutre";

export function etatInfo(etat: string): { label: string; ton: Ton } {
  switch (etat.toUpperCase()) {
    case "VIGUEUR":
      return { label: "En vigueur", ton: "vigueur" };
    case "VIGUEUR_DIFF":
      return { label: "En vigueur différée", ton: "vigueur" };
    case "MODIFIE":
      return { label: "Modifié", ton: "modifie" };
    case "MODIFIE_MORT_NE":
      return { label: "Modifié (mort-né)", ton: "modifie" };
    case "ABROGE":
      return { label: "Abrogé", ton: "abroge" };
    case "ABROGE_DIFF":
      return { label: "Abrogation différée", ton: "abroge" };
    case "TRANSFERE":
      return { label: "Transféré", ton: "modifie" };
    case "PERIME":
      return { label: "Périmé", ton: "abroge" };
    case "ANNULE":
      return { label: "Annulé", ton: "abroge" };
    case "DISJOINT":
      return { label: "Disjoint", ton: "abroge" };
    default:
      return { label: etat ? etat.charAt(0) + etat.slice(1).toLowerCase() : "—", ton: "neutre" };
  }
}

const OUTILS: Record<string, string> = {
  lister_textes: "Liste des textes",
  sommaire: "Sommaire",
  lire_article: "Lecture d'article",
  historique_article: "Historique d'article",
  comparer_versions: "Comparaison de versions",
  rechercher: "Recherche plein texte",
  renvois: "Renvois",
  modifications: "Modifications",
  bofip_plan: "Plan du BOFiP",
  bofip_lire: "Lecture BOFiP",
  bofip_rechercher: "Recherche BOFiP",
  bofip_pour_article: "Doctrine d'un article",
};

export function nomOutil(name: string): string {
  const connu = OUTILS[name];
  if (connu) return connu;
  const t = name.replace(/[_-]+/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function valeurCourte(v: unknown): string | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "string") {
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return dateCourte(v);
    return v.length > 48 ? `${v.slice(0, 45)}…` : v;
  }
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return v.length <= 3 ? v.map((x) => valeurCourte(x) ?? "").join(", ") : `${v.length} éléments`;
  return "{…}";
}

/** Arguments d'outil résumés sur une ligne : [[clé, valeur], …]. */
export function resumeArguments(args: Record<string, unknown>, max = 4): [string, string][] {
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(args)) {
    const s = valeurCourte(v);
    if (s !== null) out.push([k, s]);
    if (out.length >= max) break;
  }
  return out;
}

export function nombre(n: number): string {
  return n.toLocaleString("fr-FR");
}

/** Nombre compact : 842 → « 842 » ; 1234 → « 1,2k » ; 124500 → « 125k » ; 2345678 → « 2,35M ». */
export function compact(n: number): string {
  const v = Math.max(0, Math.round(n));
  const fr = (x: number, dec: number) => x.toLocaleString("fr-FR", { maximumFractionDigits: dec });
  if (v < 1000) return String(v);
  if (v < 99_950) return `${fr(v / 1000, 1)}k`;
  if (v < 999_500) return `${fr(v / 1000, 0)}k`;
  return `${fr(v / 1_000_000, v < 9_995_000 ? 2 : 1)}M`;
}

/**
 * Total des jetons d'une génération : entrée + sortie. Les jetons lus en cache font déjà partie de
 * l'entrée (les deux adaptateurs les y incluent) : ils ne sont pas ajoutés une seconde fois.
 */
export function totalJetons(u: Usage | null | undefined): number {
  return (u?.input_tokens ?? 0) + (u?.output_tokens ?? 0);
}

/** 400000 → « 400k » ; 1048576 → « 1M » ; 8192 → « 8k ». */
export function contexte(n: number | null | undefined): string {
  if (!n) return "";
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })}M`;
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

export const NIVEAUX_LABEL: Record<string, string> = {
  minimal: "Minimale",
  low: "Faible",
  medium: "Moyenne",
  high: "Élevée",
  xhigh: "Très élevée",
  max: "Maximale",
};

export function niveauLabel(l: string): string {
  return NIVEAUX_LABEL[l] ?? l;
}

export const SOURCE_LABEL: Record<string, string> = {
  api: "déclaré par l'API",
  heuristique: "déduit du nom",
  manuel: "réglé à la main",
  catalogue: "catalogue models.dev",
};

/** Dernier segment d'un titre BOFiP (« RPPM - Plus-values - … - Report » → « Report »). */
export function libelleCourt(titre: string | null | undefined): string {
  const parts = (titre ?? "")
    .split(/\s+[-–]\s+/)
    .map((p) => p.trim())
    .filter(Boolean);
  return parts[parts.length - 1] ?? titre ?? "";
}

/** Taille de fichier lisible. */
export function taille(octets: number | null | undefined): string {
  if (!octets) return "";
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / 1024 / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo`;
}
