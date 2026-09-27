// Parseur SSE (text/event-stream) incrémental, conforme à la spécification WHATWG :
// lignes terminées par \n, \r\n ou \r ; « event: », « data: » (multi-lignes jointes par \n),
// « id: », « retry: » ; lignes commençant par « : » = commentaires ; ligne vide = envoi.

export type SSEMessage = { event: string; data: string; id?: string };

export type SSEParser = {
  /** Donne un morceau de texte décodé (peut couper une ligne n'importe où). */
  feed(chunk: string): void;
  /** Fin du flux : envoie un éventuel événement non terminé par une ligne vide. */
  end(): void;
};

export function createSSEParser(onMessage: (msg: SSEMessage) => void): SSEParser {
  let buffer = "";
  let eventName = "";
  let dataLines: string[] = [];
  let lastId: string | undefined;
  // Un \r en fin de morceau peut être suivi d'un \n au morceau suivant.
  let pendingCR = false;

  const dispatch = () => {
    if (dataLines.length === 0) {
      eventName = "";
      return;
    }
    const msg: SSEMessage = { event: eventName || "message", data: dataLines.join("\n") };
    if (lastId !== undefined) msg.id = lastId;
    eventName = "";
    dataLines = [];
    onMessage(msg);
  };

  const processLine = (line: string) => {
    if (line === "") {
      dispatch();
      return;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    let field: string;
    let value: string;
    if (colon === -1) {
      field = line;
      value = "";
    } else {
      field = line.slice(0, colon);
      value = line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
    }
    switch (field) {
      case "event":
        eventName = value;
        break;
      case "data":
        dataLines.push(value);
        break;
      case "id":
        if (!value.includes("\0")) lastId = value;
        break;
      default:
        // « retry » et champs inconnus : ignorés.
        break;
    }
  };

  return {
    feed(chunk: string) {
      if (pendingCR) {
        pendingCR = false;
        if (chunk.startsWith("\n")) chunk = chunk.slice(1);
      }
      buffer += chunk;
      let start = 0;
      for (let i = 0; i < buffer.length; i++) {
        const c = buffer[i];
        if (c === "\n" || c === "\r") {
          processLine(buffer.slice(start, i));
          if (c === "\r") {
            if (i + 1 < buffer.length) {
              if (buffer[i + 1] === "\n") i++;
            } else {
              pendingCR = true;
            }
          }
          start = i + 1;
        }
      }
      buffer = buffer.slice(start);
    },
    end() {
      if (buffer !== "") {
        processLine(buffer);
        buffer = "";
      }
      dispatch();
    },
  };
}

/**
 * Lit le corps d'une réponse SSE et appelle `onMessage` pour chaque événement.
 * Se termine quand le flux est fini ; rejette si la lecture échoue (dont AbortError).
 */
export async function readSSE(
  body: ReadableStream<Uint8Array>,
  onMessage: (msg: SSEMessage) => void,
): Promise<void> {
  const parser = createSSEParser(onMessage);
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
    parser.feed(decoder.decode());
    parser.end();
  } finally {
    reader.releaseLock();
  }
}
