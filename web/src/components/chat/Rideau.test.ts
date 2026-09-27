import { describe, expect, it } from "vitest";
import { jetonsEstimes } from "./Rideau";

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
