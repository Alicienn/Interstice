import { describe, expect, it } from "vitest";
import { compact, totalJetons } from "./format";

describe("compact", () => {
  it("abrège en k et M, à la française", () => {
    expect(compact(0)).toBe("0");
    expect(compact(842)).toBe("842");
    expect(compact(1000)).toBe("1k");
    expect(compact(1234)).toBe("1,2k");
    expect(compact(21_480)).toBe("21,5k");
    expect(compact(99_949)).toBe("99,9k");
    expect(compact(99_950)).toBe("100k");
    expect(compact(124_500)).toBe("125k");
    expect(compact(999_499)).toBe("999k");
    expect(compact(999_500)).toBe("1M");
    expect(compact(2_345_678)).toBe("2,35M");
    expect(compact(12_345_678)).toBe("12,3M");
  });
});

describe("totalJetons", () => {
  it("additionne entrée et sortie sans recompter le cache (déjà inclus dans l'entrée)", () => {
    expect(totalJetons({ input_tokens: 21_480, output_tokens: 1260, cache_read_tokens: 17_950 })).toBe(22_740);
    expect(totalJetons(null)).toBe(0);
  });
});
