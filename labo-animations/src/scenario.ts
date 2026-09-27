/**
 * Scénarios de réponse et moteur de simulation.
 *
 * Tout est calculé à partir d'un instant `t` (ms depuis l'envoi) : l'état est une fonction pure
 * de `t`, ce qui synchronise les quatre pistes et rend chaque rejeu identique.
 */

export type TypeBloc = "titre" | "paragraphe" | "puce" | "citation";
export interface Bloc { type: TypeBloc; texte: string }

export interface Etape {
  type: "reflexion" | "outil";
  libelle: string; // ce que l'étape fait, en clair
  detail: string; // objet de l'étape (article, requête…)
  debut: number; // ms
  duree: number; // ms
}

export interface Scenario {
  id: string;
  nom: string;
  question: string;
  etapes: Etape[];
  debutRedaction: number; // ms
  motsParSeconde: number;
  blocs: Bloc[];
}

const REPONSE_LONGUE: Bloc[] = [
  { type: "titre", texte: "Report d'imposition de l'apport-cession" },
  { type: "paragraphe", texte: "Lorsque vous apportez des titres à une société que vous contrôlez, la plus-value d'apport n'est pas imposée immédiatement : elle est placée en report d'imposition." },
  { type: "titre", texte: "Conditions du report" },
  { type: "puce", texte: "La société bénéficiaire est soumise à l'impôt sur les sociétés et établie en France ou dans l'Union européenne." },
  { type: "puce", texte: "Vous contrôlez la société bénéficiaire à l'issue de l'apport, seul ou avec votre groupe familial." },
  { type: "puce", texte: "La soulte éventuelle ne dépasse pas 10 % de la valeur nominale des titres reçus." },
  { type: "titre", texte: "Ce qui met fin au report" },
  { type: "paragraphe", texte: "Le report prend fin si vous cédez les titres reçus, ou si la société cède les titres apportés dans les trois ans sans réinvestir au moins 60 % du produit dans une activité économique dans un délai de deux ans." },
  { type: "citation", texte: "CGI, art. 150-0 B ter, I et II ; BOI-RPPM-PVBMI-30-10-60-20" },
  { type: "paragraphe", texte: "Qualification : optimisation sûre si l'apport répond à un objectif économique réel. Un montage sans autre but que d'éviter l'impôt peut être requalifié en abus de droit (LPF, art. L64)." },
];

const REPONSE_COURTE: Bloc[] = [
  { type: "paragraphe", texte: "Le prélèvement forfaitaire unique s'élève à 30 % : 12,8 % d'impôt sur le revenu et 17,2 % de prélèvements sociaux." },
  { type: "citation", texte: "CGI, art. 200 A, 1, A, 1°" },
  { type: "paragraphe", texte: "Vous pouvez opter pour le barème progressif si votre taux marginal est inférieur à 12,8 % ; l'option est globale et vaut pour l'ensemble des revenus de l'année." },
];

export const SCENARIOS: Scenario[] = [
  {
    id: "outils",
    nom: "Travail avec outils",
    question: "Quelles sont les conditions du report d'imposition en cas d'apport-cession ?",
    etapes: [
      { type: "reflexion", libelle: "Réfléchit", detail: "situer l'apport-cession dans le CGI", debut: 0, duree: 2200 },
      { type: "outil", libelle: "Sommaire", detail: "CGI › Plus-values de cession de valeurs mobilières", debut: 2200, duree: 1100 },
      { type: "outil", libelle: "Lecture", detail: "CGI, art. 150-0 B ter", debut: 3300, duree: 1300 },
      { type: "outil", libelle: "Renvois", detail: "articles qui citent 150-0 B ter", debut: 4600, duree: 900 },
      { type: "outil", libelle: "Doctrine", detail: "BOI-RPPM-PVBMI-30-10-60-20", debut: 5500, duree: 1300 },
      { type: "reflexion", libelle: "Réfléchit", detail: "qualifier le risque d'abus de droit", debut: 6800, duree: 1400 },
    ],
    debutRedaction: 8200,
    motsParSeconde: 22,
    blocs: REPONSE_LONGUE,
  },
  {
    id: "direct",
    nom: "Réponse directe",
    question: "Quel est le taux du prélèvement forfaitaire unique ?",
    etapes: [
      { type: "reflexion", libelle: "Réfléchit", detail: "taux du PFU", debut: 0, duree: 900 },
      { type: "outil", libelle: "Lecture", detail: "CGI, art. 200 A", debut: 900, duree: 900 },
    ],
    debutRedaction: 1800,
    motsParSeconde: 20,
    blocs: REPONSE_COURTE,
  },
];

// ------------------------------------------------------------------------------ préparation

export interface Mot {
  texte: string;
  bloc: number;
  instant: number; // ms d'apparition
  tokens: number;
}

export interface Prepare {
  sc: Scenario;
  mots: Mot[];
  finRedaction: number;
  total: number; // fin de l'animation (avec respiration finale)
  tokensReflexion: number[]; // tokens de réflexion cumulés, par tranche de 100 ms
}

/** Générateur pseudo-aléatoire déterministe (mulberry32). */
export function alea(graine: number): () => number {
  let a = graine >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function preparer(sc: Scenario): Prepare {
  const r = alea(sc.id.length * 7919);
  const mots: Mot[] = [];
  let t = sc.debutRedaction;
  const pas = 1000 / sc.motsParSeconde;
  sc.blocs.forEach((b, i) => {
    if (i > 0) t += pas * 2.2; // respiration entre deux blocs
    for (const m of b.texte.split(" ")) {
      // rafales : un modèle émet par paquets, pas à cadence régulière
      t += pas * (r() < 0.12 ? 2.6 : 0.45 + r() * 0.9);
      mots.push({ texte: m, bloc: i, instant: t, tokens: Math.max(1, Math.round(m.length / 3.6)) });
    }
  });
  const finRedaction = t + 120;
  const tokensReflexion: number[] = [];
  let cumul = 0;
  for (let ms = 0; ms < sc.debutRedaction; ms += 100) {
    const e = sc.etapes.find((x) => ms >= x.debut && ms < x.debut + x.duree);
    cumul += e?.type === "reflexion" ? 3 + Math.round(r() * 5) : e ? Math.round(r() * 2) : 0;
    tokensReflexion.push(cumul);
  }
  return { sc, mots, finRedaction, total: finRedaction + 2600, tokensReflexion };
}

// ------------------------------------------------------------------------------ état à l'instant t

export type Phase = "travail" | "redaction" | "fini";

export interface Etat {
  t: number;
  phase: Phase;
  etapes: (Etape & { statut: "en cours" | "fait" })[];
  motsEmis: number;
  tokens: number;
  tokensParSeconde: number;
  fini: boolean;
  depuisFin: number; // ms écoulées depuis la fin de la rédaction (négatif avant)
}

export function etatA(p: Prepare, t: number): Etat {
  const { sc, mots } = p;
  const etapes = sc.etapes
    .filter((e) => t >= e.debut)
    .map((e) => ({ ...e, statut: (t < e.debut + e.duree ? "en cours" : "fait") as "en cours" | "fait" }));
  let motsEmis = 0;
  while (motsEmis < mots.length && mots[motsEmis].instant <= t) motsEmis++;
  const tr = p.tokensReflexion[Math.min(p.tokensReflexion.length - 1, Math.floor(Math.min(t, sc.debutRedaction - 1) / 100))] ?? 0;
  let tokens = tr;
  for (let i = 0; i < motsEmis; i++) tokens += mots[i].tokens;
  const phase: Phase = t < sc.debutRedaction ? "travail" : t < p.finRedaction ? "redaction" : "fini";
  return {
    t, phase, etapes, motsEmis, tokens,
    tokensParSeconde: debit(p, t),
    fini: phase === "fini",
    depuisFin: t - p.finRedaction,
  };
}

/** Débit de tokens sur la fenêtre [t - 600 ms, t], en tokens par seconde. */
export function debit(p: Prepare, t: number, fenetre = 600): number {
  return (tokensEntre(p, t - fenetre, t) * 1000) / fenetre;
}

/** Tokens émis sur l'intervalle ]a, b] (réflexion + rédaction). */
export function tokensEntre(p: Prepare, a: number, b: number): number {
  let n = 0;
  for (const m of p.mots) if (m.instant > a && m.instant <= b) n += m.tokens;
  const idx = (ms: number) => Math.max(-1, Math.min(p.tokensReflexion.length - 1, Math.floor(ms / 100)));
  const ra = idx(a), rb = idx(Math.min(b, p.sc.debutRedaction - 1));
  if (rb > ra) n += (p.tokensReflexion[rb] ?? 0) - (ra >= 0 ? p.tokensReflexion[ra] : 0);
  return n;
}

export function dureeLisible(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

export const nf = new Intl.NumberFormat("fr-FR");
