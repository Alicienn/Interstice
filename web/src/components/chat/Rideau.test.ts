import { describe, expect, it } from "vitest";
import { chrono, jetonsEnDirect, jetonsEstimes } from "./Rideau";

describe("chrono", () => {
  it("affiche minutes et secondes, sans fraction", () => {
    expect(chrono(0)).toBe("00:00");
    expect(chrono(9_999)).toBe("00:09");
    expect(chrono(72_400)).toBe("01:12");
    expect(chrono(3_723_000)).toBe("1:02:03");
  });
});

describe("jetonsEnDirect", () => {
  it("part de l'usage exact et n'ajoute que l'estimation produite depuis", () => {
    expect(jetonsEnDirect(0, 120, 0)).toBe(120);
    expect(jetonsEnDirect(18_500, 300, 250)).toBe(18_550);
    expect(jetonsEnDirect(18_500, 250, 250)).toBe(18_500);
  });
});

describe("jetonsEstimes", () => {
  it("compte ~4 caractères par jeton sur le texte, la réflexion et les arguments d'outils", () => {
    const n = jetonsEstimes([
      { type: "thinking", text: "a".repeat(40) },
      { type: "tool", call_id: "c1", name: "lire_article", arguments: { texte: "CGI" }, status: "done", documents: [] },
      { type: "text", text: "b".repeat(80) },
    ]);
    // 40 + len('{"texte":"CGI"}') = 15 + 80 = 135 caractères → 34 jetons
    expect(n).toBe(34);
  });

  it("vaut 0 sans contenu", () => {
    expect(jetonsEstimes([])).toBe(0);
  });
});
