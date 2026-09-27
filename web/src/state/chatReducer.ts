// Réducteur de l'état d'une conversation pendant la réception du flux SSE.
// Pur : l'horodatage courant est fourni par l'action.

import type { Message, Part, StreamEvent, ToolPart } from "../api/types";

export type ChatState = {
  messages: Message[];
  /** Un flux est en cours de lecture. */
  streaming: boolean;
  /** Message assistant en cours de construction. */
  assistantId: string | null;
  /** Message utilisateur optimiste en attente de son id définitif (`user_message`). */
  pendingUserId: string | null;
};

export type ChatAction =
  | { type: "load"; messages: Message[] }
  | { type: "send"; localId: string; content: string; now: string }
  /** Rattachement à une génération en cours côté serveur (GET /stream) : le rejeu va suivre. */
  | { type: "attach" }
  | { type: "event"; event: StreamEvent; now: string }
  | { type: "local_error"; message: string; now: string }
  | { type: "finish" };

export const initialChatState: ChatState = {
  messages: [],
  streaming: false,
  assistantId: null,
  pendingUserId: null,
};

export const INTERRUPTED_SUMMARY = "Interrompu";

function updateMessage(state: ChatState, id: string, fn: (m: Message) => Message): ChatState {
  return { ...state, messages: state.messages.map((m) => (m.id === id ? fn(m) : m)) };
}

/** Garantit l'existence d'un message assistant courant (si un delta arrive avant `message_start`). */
function ensureAssistant(state: ChatState, now: string): [ChatState, string] {
  if (state.assistantId && state.messages.some((m) => m.id === state.assistantId)) {
    return [state, state.assistantId];
  }
  const id = `local-assistant-${state.messages.length}`;
  const msg: Message = { id, role: "assistant", parts: [], created_at: now };
  return [{ ...state, assistantId: id, messages: [...state.messages, msg] }, id];
}

function appendDelta(parts: Part[], kind: "thinking" | "text", text: string): Part[] {
  const last = parts[parts.length - 1];
  if (last && last.type === kind) {
    return [...parts.slice(0, -1), { type: kind, text: last.text + text }];
  }
  return [...parts, { type: kind, text }];
}

function markInterrupted(parts: Part[]): Part[] {
  return parts.map((p) =>
    p.type === "tool" && p.status === "running"
      ? { ...p, status: "error" as const, summary: p.summary ?? INTERRUPTED_SUMMARY }
      : p,
  );
}

function reduceEvent(state: ChatState, ev: StreamEvent, now: string): ChatState {
  switch (ev.event) {
    case "user_message": {
      const msg = ev.data;
      if (state.pendingUserId) {
        const pending = state.pendingUserId;
        return {
          ...state,
          pendingUserId: null,
          messages: state.messages.map((m) => (m.id === pending ? msg : m)),
        };
      }
      // Rejeu : un message déjà présent est remplacé, jamais dupliqué.
      if (state.messages.some((m) => m.id === msg.id))
        return { ...state, messages: state.messages.map((m) => (m.id === msg.id ? msg : m)) };
      return { ...state, messages: [...state.messages, msg] };
    }
    case "message_start": {
      const { message_id, model_key, thinking_level } = ev.data;
      const existing = state.messages.find((m) => m.id === message_id);
      const msg: Message = {
        id: message_id,
        role: "assistant",
        parts: [],
        created_at: now,
        model_key,
        thinking_level,
      };
      // Rejeu : le message partiel existant est remplacé par une bulle vierge que les deltas rejoués
      // vont reconstruire (sinon le texte serait doublé).
      if (existing)
        return {
          ...state,
          assistantId: message_id,
          messages: state.messages.map((m) => (m.id === message_id ? { ...msg, created_at: existing.created_at } : m)),
        };
      return { ...state, assistantId: message_id, messages: [...state.messages, msg] };
    }
    case "thinking_delta":
    case "text_delta": {
      const kind = ev.event === "thinking_delta" ? "thinking" : "text";
      const text = ev.data.text;
      if (!text) return state;
      const [s, id] = ensureAssistant(state, now);
      return updateMessage(s, id, (m) => ({ ...m, parts: appendDelta(m.parts, kind, text) }));
    }
    case "tool_call": {
      const [s, id] = ensureAssistant(state, now);
      const part: ToolPart = {
        type: "tool",
        call_id: ev.data.call_id,
        name: ev.data.name,
        arguments: ev.data.arguments ?? {},
        status: "running",
        documents: [],
      };
      return updateMessage(s, id, (m) => ({ ...m, parts: [...m.parts, part] }));
    }
    case "tool_result": {
      const { call_id, status, summary, documents } = ev.data;
      // La part peut se trouver dans le message courant ou (cas limite) un précédent.
      const target = [...state.messages]
        .reverse()
        .find((m) => m.parts.some((p) => p.type === "tool" && p.call_id === call_id));
      if (!target) return state;
      return updateMessage(state, target.id, (m) => ({
        ...m,
        parts: m.parts.map((p) =>
          p.type === "tool" && p.call_id === call_id
            ? { ...p, status, summary, documents: documents ?? [] }
            : p,
        ),
      }));
    }
    case "message_end": {
      const { message_id, usage } = ev.data;
      const id = state.messages.some((m) => m.id === message_id) ? message_id : state.assistantId;
      const s = id ? updateMessage(state, id, (m) => ({ ...m, usage: usage ?? null })) : state;
      return { ...s, assistantId: null };
    }
    case "error": {
      const [s, id] = ensureAssistant(state, now);
      return updateMessage(s, id, (m) => ({ ...m, error: ev.data.message }));
    }
    default: {
      const _exhaustive: never = ev;
      return _exhaustive;
    }
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "load":
      return { ...initialChatState, messages: action.messages };
    case "send": {
      const msg: Message = {
        id: action.localId,
        role: "user",
        parts: [{ type: "text", text: action.content }],
        created_at: action.now,
      };
      return {
        messages: [...state.messages, msg],
        streaming: true,
        assistantId: null,
        pendingUserId: action.localId,
      };
    }
    case "attach":
      return { ...state, streaming: true, assistantId: null, pendingUserId: null };
    case "event":
      return reduceEvent(state, action.event, action.now);
    case "local_error": {
      const [s, id] = ensureAssistant(state, action.now);
      return updateMessage(s, id, (m) => ({ ...m, error: action.message }));
    }
    case "finish": {
      const s = state.assistantId
        ? updateMessage(state, state.assistantId, (m) => ({ ...m, parts: markInterrupted(m.parts) }))
        : state;
      return { ...s, streaming: false, assistantId: null, pendingUserId: null };
    }
  }
}

/** Convertit un message SSE brut en événement typé (ou null si inconnu / JSON invalide). */
export function toStreamEvent(name: string, data: string): StreamEvent | null {
  const known = [
    "user_message",
    "message_start",
    "thinking_delta",
    "text_delta",
    "tool_call",
    "tool_result",
    "message_end",
    "error",
  ];
  if (!known.includes(name)) return null;
  try {
    return { event: name, data: JSON.parse(data) } as StreamEvent;
  } catch {
    return null;
  }
}

/**
 * Messages d'une conversation dont une génération est en cours, prêts pour le rejeu de GET /stream :
 * retire le message assistant partiel `generationMessageId` et le message utilisateur qui le précède
 * (ou, si le message assistant n'existe pas encore, le dernier message s'il est de l'utilisateur).
 */
export function stripGeneration(messages: Message[], generationMessageId: string | null | undefined): Message[] {
  const idx = generationMessageId ? messages.findIndex((m) => m.id === generationMessageId) : -1;
  if (idx >= 0) {
    let userIdx = -1;
    for (let i = idx - 1; i >= 0; i--)
      if (messages[i]!.role === "user") {
        userIdx = i;
        break;
      }
    return messages.filter((_, i) => i !== idx && i !== userIdx);
  }
  const last = messages[messages.length - 1];
  return last && last.role === "user" ? messages.slice(0, -1) : messages;
}
