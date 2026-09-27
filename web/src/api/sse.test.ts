import { describe, expect, it } from "vitest";
import { createSSEParser, readSSE, type SSEMessage } from "./sse";

function parseAll(chunks: string[], end = true): SSEMessage[] {
  const out: SSEMessage[] = [];
  const p = createSSEParser((m) => out.push(m));
  for (const c of chunks) p.feed(c);
  if (end) p.end();
  return out;
}

describe("createSSEParser", () => {
  it("parse un événement nommé simple", () => {
    expect(parseAll(['event: text_delta\ndata: {"text":"Bonjour"}\n\n'])).toEqual([
      { event: "text_delta", data: '{"text":"Bonjour"}' },
    ]);
  });

  it("utilise « message » comme nom par défaut", () => {
    expect(parseAll(["data: x\n\n"])).toEqual([{ event: "message", data: "x" }]);
  });

  it("joint les lignes data multiples par \\n", () => {
    expect(parseAll(["event: e\ndata: a\ndata: b\ndata:c\n\n"])).toEqual([
      { event: "e", data: "a\nb\nc" },
    ]);
  });

  it("gère un découpage arbitraire des morceaux, y compris au milieu d'un caractère de fin", () => {
    const flux = 'event: text_delta\r\ndata: {"text":"é"}\r\n\r\nevent: message_end\r\ndata: {}\r\n\r\n';
    const attendu = [
      { event: "text_delta", data: '{"text":"é"}' },
      { event: "message_end", data: "{}" },
    ];
    // Tous les découpages en deux morceaux
    for (let i = 0; i <= flux.length; i++) {
      expect(parseAll([flux.slice(0, i), flux.slice(i)])).toEqual(attendu);
    }
    // Caractère par caractère
    expect(parseAll(flux.split(""))).toEqual(attendu);
  });

  it("accepte les fins de ligne \\r seules", () => {
    expect(parseAll(["event: a\rdata: 1\r\r"])).toEqual([{ event: "a", data: "1" }]);
  });

  it("ignore les commentaires et champs inconnus, conserve l'id", () => {
    expect(parseAll([": ping\nretry: 1000\nfoo: bar\nid: 7\nevent: a\ndata: 1\n\n"])).toEqual([
      { event: "a", data: "1", id: "7" },
    ]);
  });

  it("n'envoie rien pour un bloc sans data et réinitialise le nom", () => {
    expect(parseAll(["event: vide\n\ndata: 2\n\n"])).toEqual([{ event: "message", data: "2" }]);
  });

  it("retire un seul espace après les deux-points", () => {
    expect(parseAll(["data:  deux espaces\n\n"])).toEqual([{ event: "message", data: " deux espaces" }]);
  });

  it("envoie à end() un événement non terminé par une ligne vide", () => {
    expect(parseAll(["event: a\ndata: 1"], true)).toEqual([{ event: "a", data: "1" }]);
    expect(parseAll(["event: a\ndata: 1"], false)).toEqual([]);
  });
});

describe("readSSE", () => {
  it("décode un ReadableStream d'octets UTF-8 coupé au milieu d'un caractère", async () => {
    const bytes = new TextEncoder().encode('event: text_delta\ndata: {"text":"réflexion"}\n\n');
    const cut = bytes.indexOf(0xc3) + 1; // coupe au milieu du « é »
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(bytes.slice(0, cut));
        c.enqueue(bytes.slice(cut));
        c.close();
      },
    });
    const out: SSEMessage[] = [];
    await readSSE(body, (m) => out.push(m));
    expect(out).toEqual([{ event: "text_delta", data: '{"text":"réflexion"}' }]);
  });
});
