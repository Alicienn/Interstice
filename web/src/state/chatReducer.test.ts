import { describe, expect, it } from "vitest";
import type { Message, StreamEvent } from "../api/types";
import {
  chatReducer,
  initialChatState,
  INTERRUPTED_SUMMARY,
  stripGeneration,
  toStreamEvent,
  type ChatState,
} from "./chatReducer";

const NOW = "2026-09-27T12:00:00Z";

function run(state: ChatState, events: StreamEvent[]): ChatState {
  return events.reduce((s, event) => chatReducer(s, { type: "event", event, now: NOW }), state);
}

function sent(content = "Que dit l'article 150-0 B ter ?"): ChatState {
  return chatReducer(initialChatState, { type: "send", localId: "local-1", content, now: NOW });
}

const userMsg: Message = {
  id: "m-user",
  role: "user",
  parts: [{ type: "text", text: "Que dit l'article 150-0 B ter ?" }],
  created_at: NOW,
};

describe("chatReducer", () => {
  it("ajoute un message utilisateur optimiste puis le remplace par l'id définitif", () => {
    let s = sent();
    expect(s.streaming).toBe(true);
    expect(s.messages).toHaveLength(1);
    expect(s.messages[0]?.id).toBe("local-1");
    s = run(s, [{ event: "user_message", data: userMsg }]);
    expect(s.messages).toHaveLength(1);
    expect(s.messages[0]?.id).toBe("m-user");
    expect(s.pendingUserId).toBeNull();
  });

  it("construit la bulle assistant : réflexion, texte, outils, fin", () => {
    let s = run(sent(), [
      { event: "user_message", data: userMsg },
      { event: "message_start", data: { message_id: "m-a", model_key: "p::m", thinking_level: "high" } },
      { event: "thinking_delta", data: { text: "Je dois " } },
      { event: "thinking_delta", data: { text: "consulter le sommaire." } },
      { event: "tool_call", data: { call_id: "c1", name: "sommaire", arguments: { id: "LEGITEXT000006069577" } } },
      { event: "tool_call", data: { call_id: "c2", name: "lire_article", arguments: { num: "150-0 B ter" } } },
      {
        event: "tool_result",
        data: {
          call_id: "c1",
          status: "done",
          summary: "12 sections",
          documents: [{ kind: "texte", id: "LEGITEXT000006069577", titre: "CGI", sous_titre: "", date: null }],
        },
      },
      { event: "text_delta", data: { text: "L'article " } },
      { event: "text_delta", data: { text: "prévoit un report." } },
    ]);
    const a = s.messages[1]!;
    expect(a.role).toBe("assistant");
    expect(a.model_key).toBe("p::m");
    expect(a.thinking_level).toBe("high");
    expect(a.parts).toHaveLength(4);
    expect(a.parts[0]).toEqual({ type: "thinking", text: "Je dois consulter le sommaire." });
    expect(a.parts[1]).toMatchObject({ type: "tool", call_id: "c1", status: "done", summary: "12 sections" });
    expect(a.parts[1]).toHaveProperty("documents.length", 1);
    expect(a.parts[2]).toMatchObject({ type: "tool", call_id: "c2", status: "running", documents: [] });
    expect(a.parts[3]).toEqual({ type: "text", text: "L'article prévoit un report." });

    s = run(s, [{ event: "message_end", data: { message_id: "m-a", usage: { input_tokens: 10, output_tokens: 5 } } }]);
    expect(s.assistantId).toBeNull();
    expect(s.messages[1]?.usage).toEqual({ input_tokens: 10, output_tokens: 5 });
    expect(s.streaming).toBe(true); // tant que le flux n'est pas fermé
    s = chatReducer(s, { type: "finish" });
    expect(s.streaming).toBe(false);
  });

  it("sépare deux blocs de texte entourant un appel d'outil", () => {
    const s = run(sent(), [
      { event: "message_start", data: { message_id: "m-a", model_key: null, thinking_level: null } },
      { event: "text_delta", data: { text: "Avant." } },
      { event: "tool_call", data: { call_id: "c1", name: "rechercher", arguments: { q: "apport" } } },
      { event: "text_delta", data: { text: "Après." } },
    ]);
    const parts = s.messages[1]!.parts;
    expect(parts.map((p) => p.type)).toEqual(["text", "tool", "text"]);
  });

  it("crée une bulle assistant si un delta arrive sans message_start", () => {
    const s = run(sent(), [{ event: "text_delta", data: { text: "x" } }]);
    expect(s.messages).toHaveLength(2);
    expect(s.messages[1]?.role).toBe("assistant");
    expect(s.assistantId).toBe(s.messages[1]?.id);
  });

  it("affiche l'erreur dans la bulle courante, ou en crée une", () => {
    let s = run(sent(), [
      { event: "message_start", data: { message_id: "m-a", model_key: null, thinking_level: null } },
      { event: "error", data: { message: "Clé invalide" } },
    ]);
    expect(s.messages[1]?.error).toBe("Clé invalide");
    s = run(sent(), [{ event: "error", data: { message: "Modèle inconnu" } }]);
    expect(s.messages).toHaveLength(2);
    expect(s.messages[1]?.error).toBe("Modèle inconnu");
  });

  it("à l'interruption, les outils en cours passent en erreur « Interrompu »", () => {
    let s = run(sent(), [
      { event: "message_start", data: { message_id: "m-a", model_key: null, thinking_level: null } },
      { event: "tool_call", data: { call_id: "c1", name: "sommaire", arguments: {} } },
    ]);
    s = chatReducer(s, { type: "finish" });
    expect(s.messages[1]?.parts[0]).toMatchObject({ status: "error", summary: INTERRUPTED_SUMMARY });
    expect(s.streaming).toBe(false);
    expect(s.assistantId).toBeNull();
  });

  it("erreur locale (réseau) : message d'erreur sur une bulle assistant", () => {
    const s = chatReducer(sent(), { type: "local_error", message: "Réseau indisponible", now: NOW });
    expect(s.messages[1]).toMatchObject({ role: "assistant", error: "Réseau indisponible" });
  });

  it("ignore un tool_result inconnu et un delta vide", () => {
    const base = run(sent(), [{ event: "message_start", data: { message_id: "m-a", model_key: null, thinking_level: null } }]);
    const s = run(base, [
      { event: "tool_result", data: { call_id: "zzz", status: "done", summary: "", documents: [] } },
      { event: "text_delta", data: { text: "" } },
    ]);
    expect(s).toBe(base);
  });

  it("load réinitialise l'état", () => {
    const s = chatReducer(sent(), { type: "load", messages: [userMsg] });
    expect(s).toEqual({ ...initialChatState, messages: [userMsg] });
  });
});

describe("rattachement à une génération en arrière-plan (GET /stream)", () => {
  const u0: Message = { id: "u0", role: "user", parts: [{ type: "text", text: "Première question" }], created_at: NOW };
  const a0: Message = { id: "a0", role: "assistant", parts: [{ type: "text", text: "Première réponse." }], created_at: NOW };
  const u1: Message = { id: "u1", role: "user", parts: [{ type: "text", text: "Seconde question" }], created_at: NOW };
  const a1Partiel: Message = {
    id: "a1",
    role: "assistant",
    parts: [
      { type: "thinking", text: "Je lis" },
      { type: "text", text: "Le report" },
    ],
    created_at: NOW,
  };
  const replay: StreamEvent[] = [
    { event: "user_message", data: u1 },
    { event: "message_start", data: { message_id: "a1", model_key: "p::m", thinking_level: "low" } },
    { event: "thinking_delta", data: { text: "Je lis" } },
    { event: "tool_call", data: { call_id: "c1", name: "lire_article", arguments: { num: "150-0 B ter" } } },
    { event: "tool_result", data: { call_id: "c1", status: "done", summary: "ok", documents: [] } },
    { event: "text_delta", data: { text: "Le report" } },
  ];

  it("stripGeneration retire le message partiel et la question qui le précède", () => {
    expect(stripGeneration([u0, a0, u1, a1Partiel], "a1").map((m) => m.id)).toEqual(["u0", "a0"]);
    // Message assistant pas encore créé côté serveur : on retire la dernière question.
    expect(stripGeneration([u0, a0, u1], "a1").map((m) => m.id)).toEqual(["u0", "a0"]);
    expect(stripGeneration([u0, a0], null).map((m) => m.id)).toEqual(["u0", "a0"]);
  });

  it("rejoue puis suit le direct après retrait des messages partiels", () => {
    let s = chatReducer(initialChatState, { type: "load", messages: stripGeneration([u0, a0, u1, a1Partiel], "a1") });
    s = chatReducer(s, { type: "attach" });
    expect(s.streaming).toBe(true);
    s = run(s, replay);
    expect(s.messages.map((m) => m.id)).toEqual(["u0", "a0", "u1", "a1"]);
    expect(s.assistantId).toBe("a1");
    // Direct
    s = run(s, [
      { event: "text_delta", data: { text: " est maintenu." } },
      { event: "message_end", data: { message_id: "a1", usage: null } },
    ]);
    s = chatReducer(s, { type: "finish" });
    const a1 = s.messages[3]!;
    expect(a1.parts.map((p) => p.type)).toEqual(["thinking", "tool", "text"]);
    expect(a1.parts[2]).toEqual({ type: "text", text: "Le report est maintenu." });
    expect(s.streaming).toBe(false);
  });

  it("ne duplique rien si le rejeu arrive sur une conversation déjà chargée (non épurée)", () => {
    let s = chatReducer(initialChatState, { type: "load", messages: [u0, a0, u1, a1Partiel] });
    s = chatReducer(s, { type: "attach" });
    s = run(s, replay);
    expect(s.messages.map((m) => m.id)).toEqual(["u0", "a0", "u1", "a1"]);
    // Les deltas rejoués reconstruisent le message au lieu de s'ajouter au partiel.
    expect(s.messages[3]!.parts).toEqual([
      { type: "thinking", text: "Je lis" },
      expect.objectContaining({ type: "tool", call_id: "c1", status: "done" }),
      { type: "text", text: "Le report" },
    ]);
  });

  it("rattachement après changement de conversation : l'état précédent est entièrement remplacé", () => {
    // Conversation A en cours de flux…
    let s = run(sent("Question A"), [
      { event: "message_start", data: { message_id: "xa", model_key: null, thinking_level: null } },
      { event: "text_delta", data: { text: "Réponse A partielle" } },
    ]);
    // …on quitte (lecture abandonnée), puis on ouvre B dont une génération tourne en arrière-plan.
    s = chatReducer(s, { type: "finish" });
    s = chatReducer(s, { type: "load", messages: stripGeneration([u0, a0, u1, a1Partiel], "a1") });
    s = chatReducer(s, { type: "attach" });
    s = run(s, replay);
    expect(s.messages.map((m) => m.id)).toEqual(["u0", "a0", "u1", "a1"]);
    expect(s.messages.some((m) => m.id === "xa")).toBe(false);
    expect(s.streaming).toBe(true);
  });
});

describe("toStreamEvent", () => {
  it("convertit les événements connus et rejette le reste", () => {
    expect(toStreamEvent("text_delta", '{"text":"a"}')).toEqual({ event: "text_delta", data: { text: "a" } });
    expect(toStreamEvent("ping", "{}")).toBeNull();
    expect(toStreamEvent("text_delta", "pas du json")).toBeNull();
  });
});
