import { describe, expect, it } from "vitest";
import type { DocRef } from "../api/types";
import { emptyHistory, pushTarget, sameDoc, targetFromDoc } from "./reader";

const doc = (d: Partial<DocRef>): DocRef => ({ kind: "article", id: "X", titre: "", sous_titre: "", date: null, ...d });

describe("targetFromDoc", () => {
  it("ouvre un article à sa date", () => {
    expect(targetFromDoc(doc({ id: "LEGIARTI1", date: "2024-01-01" }))).toEqual({
      kind: "article",
      id: "LEGIARTI1",
      date: "2024-01-01",
    });
  });

  it("ouvre un document BOFiP (y compris une version antérieure)", () => {
    expect(targetFromDoc(doc({ kind: "bofip", id: "739-PGP@2019-04-10" }))).toEqual({
      kind: "bofip",
      id: "739-PGP@2019-04-10",
    });
  });

  it("distingue la recherche BOFiP de la recherche dans les codes", () => {
    expect(targetFromDoc(doc({ kind: "recherche", id: "apport", titre: "BOFiP : apport" }))).toMatchObject({
      kind: "recherche",
      corpus: "bofip",
      q: "apport",
    });
    expect(targetFromDoc(doc({ kind: "recherche", id: "apport", titre: "Recherche : apport" }))).toMatchObject({
      kind: "recherche",
      corpus: "codes",
    });
  });
});

describe("historique du panneau", () => {
  it("n'empile pas deux fois la même cible et tronque l'avenir", () => {
    let h = pushTarget(emptyHistory, { kind: "textes" });
    h = pushTarget(h, { kind: "textes" });
    expect(h.entries).toHaveLength(1);
    h = pushTarget(h, { kind: "bofip-plan", noeud: null });
    h = pushTarget(h, { kind: "bofip", id: "1-PGP" });
    h = { ...h, index: 0 };
    h = pushTarget(h, { kind: "article", id: "A" });
    expect(h.entries.map((e) => e.kind)).toEqual(["textes", "article"]);
    expect(h.index).toBe(1);
  });

  it("sameDoc reconnaît la carte BOFiP active", () => {
    expect(sameDoc({ kind: "bofip", id: "1-PGP" }, doc({ kind: "bofip", id: "1-PGP" }))).toBe(true);
    expect(sameDoc({ kind: "article", id: "1-PGP" }, doc({ kind: "bofip", id: "1-PGP" }))).toBe(false);
  });
});
