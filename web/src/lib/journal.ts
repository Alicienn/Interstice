// Découpage d'un message assistant en « journal d'étapes » (réflexions, outils, texte intermédiaire)
// et « texte final » (ce qui est réellement rédigé pour l'utilisateur), plus les libellés d'étapes.

import type { DocRef, Part, TextPart, ToolPart } from "../api/types";
import { dateCourte, nomOutil, resumeArguments } from "./format";

export type Decoupage = {
  /** Étapes de travail, dans l'ordre : réflexions, appels d'outils, texte écrit entre deux outils. */
  journal: Part[];
  /** Texte final : blocs de texte après le dernier appel d'outil (tout le texte s'il n'y a pas d'outil). */
  final: TextPart[];
};

export function decouperMessage(parts: Part[]): Decoupage {
  let dernierOutil = -1;
  parts.forEach((p, i) => {
    if (p.type === "tool") dernierOutil = i;
  });
  const journal: Part[] = [];
  const final: TextPart[] = [];
  parts.forEach((p, i) => {
    if (p.type === "text" && i > dernierOutil) final.push(p);
    else journal.push(p);
  });
  return { journal, final };
}

/** « 42 s », « 1 min 12 s », « 3 min », « 1 h 03 min ». */
export function dureeLisible(ms: number): string {
  const s = Math.max(1, Math.round(ms / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m} min ${r} s` : `${m} min`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h} h ${String(m).padStart(2, "0")} min`;
}

const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : typeof v === "number" ? String(v) : null);

function refArticle(args: Record<string, unknown>): string | null {
  const num = str(args.num);
  if (!num) return str(args.id);
  const texte = str(args.texte);
  return texte ? `${texte}, art. ${num}` : `art. ${num}`;
}

function guillemets(q: string | null): string | null {
  return q ? `« ${q} »` : null;
}

export type Libelle = {
  /** Verbe court (« Lecture », « Recherche »…). */
  action: string;
  /** Objet de l'étape (« CGI, art. 150-0 B ter »), si connu. */
  objet: string | null;
  /** Résultat résumé (« 4 documents »), une fois l'étape terminée. */
  resultat: string | null;
};

/** Libellé lisible d'un appel d'outil ; le document principal sert d'objet quand il est connu. */
export function libelleOutil(p: ToolPart): Libelle {
  const a = p.arguments ?? {};
  const doc: DocRef | undefined = p.documents[0];
  const resultat = p.summary?.trim() || null;
  const docTitre = doc ? (doc.kind === "bofip" && doc.sous_titre ? doc.sous_titre : doc.titre) : null;
  switch (p.name) {
    case "sommaire":
      return { action: "Sommaire", objet: docTitre ?? str(a.id) ?? str(a.texte), resultat };
    case "lire_article":
      return { action: "Lecture", objet: doc?.titre ?? refArticle(a), resultat: null };
    case "historique_article":
      return { action: "Historique", objet: refArticle(a), resultat };
    case "comparer_versions":
      return { action: "Comparaison de versions", objet: refArticle(a), resultat };
    case "renvois":
      return { action: "Renvois", objet: refArticle(a), resultat };
    case "rechercher": {
      const texte = str(a.texte);
      const q = guillemets(str(a.requete) ?? str(a.q));
      return { action: "Recherche", objet: q ? (texte ? `${q} (${texte})` : q) : null, resultat };
    }
    case "modifications": {
      const du = str(a.du) ?? str(a.debut);
      const au = str(a.au) ?? str(a.fin);
      return {
        action: "Modifications",
        objet: du || au ? [du && `du ${dateCourte(du)}`, au && `au ${dateCourte(au)}`].filter(Boolean).join(" ") : null,
        resultat,
      };
    }
    case "lister_textes":
      return { action: "Textes du corpus", objet: null, resultat };
    case "bofip_pour_article":
      return { action: "Doctrine", objet: refArticle(a), resultat };
    case "bofip_lire": {
      const para = str(a.paragraphe);
      const objet = docTitre ?? str(a.id);
      return { action: "Lecture BOFiP", objet: objet && para ? `${objet}, § ${para}` : objet, resultat: null };
    }
    case "bofip_rechercher": {
      const q = guillemets(str(a.requete) ?? str(a.q));
      const serie = str(a.serie);
      return { action: "Recherche BOFiP", objet: q ? (serie ? `${q} (${serie})` : q) : null, resultat };
    }
    case "bofip_plan":
      return { action: "Plan du BOFiP", objet: str(a.noeud) ?? str(a.serie), resultat };
    default: {
      const premier = resumeArguments(a, 1)[0];
      return { action: nomOutil(p.name), objet: premier ? premier[1] : null, resultat };
    }
  }
}
