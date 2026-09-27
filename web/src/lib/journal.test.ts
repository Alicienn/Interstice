import { describe, expect, it } from "vitest";
import type { Part, ToolPart } from "../api/types";
import { decouperMessage, dureeLisible, libelleOutil } from "./journal";

const t = (text: string): Part => ({ type: "text", text });
const th = (text: string): Part => ({ type: "thinking", text });
const tool = (call_id: string, name = "lire_article", extra: Partial<ToolPart> = {}): ToolPart => ({
  type: "tool",
  call_id,
  name,
  arguments: {},
  status: "done",
  documents: [],
  ...extra,
});

describe("decouperMessage", () => {
  it("sans outil : tout le texte est final, la réflexion va au journal", () => {
    const parts = [th("je réfléchis"), t("Réponse "), t("complète")];
    const d = decouperMessage(parts);
    expect(d.journal).toEqual([parts[0]]);
    expect(d.final).toEqual([parts[1], parts[2]]);
  });

  it("avec outils : le texte intermédiaire va au journal, seul le texte après le dernier outil est final", () => {
    const parts = [th("a"), t("Je consulte le sommaire."), tool("c1"), t("Puis l'article."), tool("c2"), th("b"), t("Réponse finale.")];
    const d = decouperMessage(parts);
    expect(d.final).toEqual([t("Réponse finale.")]);
    expect(d.journal.map((p) => p.type)).toEqual(["thinking", "text", "tool", "text", "tool", "thinking"]);
  });

  it("message vide ou uniquement des outils", () => {
    expect(decouperMessage([])).toEqual({ journal: [], final: [] });
    const d = decouperMessage([tool("c1"), tool("c2")]);
    expect(d.final).toEqual([]);
    expect(d.journal).toHaveLength(2);
  });
});

describe("dureeLisible", () => {
  it("formate en français", () => {
    expect(dureeLisible(300)).toBe("1 s");
    expect(dureeLisible(42_000)).toBe("42 s");
    expect(dureeLisible(72_000)).toBe("1 min 12 s");
    expect(dureeLisible(180_000)).toBe("3 min");
    expect(dureeLisible(3_780_000)).toBe("1 h 03 min");
  });
});

describe("libelleOutil", () => {
  it("produit des libellés courts et lisibles", () => {
    expect(
      libelleOutil(
        tool("c", "lire_article", {
          arguments: { texte: "CGI", num: "150-0 B ter" },
          documents: [{ kind: "article", id: "A", titre: "CGI, art. 150-0 B ter", sous_titre: "", date: null }],
        }),
      ),
    ).toEqual({ action: "Lecture", objet: "CGI, art. 150-0 B ter", resultat: null });
    expect(libelleOutil(tool("c", "rechercher", { arguments: { q: "abus de droit", texte: "LPF" }, summary: "1 résultat" }))).toEqual({
      action: "Recherche",
      objet: "« abus de droit » (LPF)",
      resultat: "1 résultat",
    });
    expect(libelleOutil(tool("c", "bofip_pour_article", { arguments: { texte: "CGI", num: "150-0 B ter" }, summary: "4 documents" }))).toEqual({
      action: "Doctrine",
      objet: "CGI, art. 150-0 B ter",
      resultat: "4 documents",
    });
    expect(libelleOutil(tool("c", "outil_inconnu", { arguments: { cle: "valeur" } })).action).toBe("Outil inconnu");
  });
});
