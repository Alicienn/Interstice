// Client unique de l'API (docs/contrat-api.md). En mode maquette (VITE_MOCK=1), les requêtes
// sont servies par `mock.ts`, qui imite le backend au niveau de `fetch` (y compris le flux SSE) :
// le reste de l'application ne fait aucune différence.

import { readSSE } from "./sse";
import { toStreamEvent } from "../state/chatReducer";
import type {
  Conversation,
  ConversationResume,
  EnvoiMessage,
  Fournisseur,
  ModeleActive,
  ModeleChoix,
  ModeleDistant,
  NouveauFournisseur,
  PatchFournisseur,
  Reglages,
  ResultatRecherche,
  ResultatRechercheBofip,
  VueBofip,
  VueBofipNoeud,
  Sante,
  StreamEvent,
  TexteCorpus,
  VueArticle,
  VueNoeud,
} from "./types";

export const BASE = "api";
export const IS_MOCK = import.meta.env.VITE_MOCK === "1";

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

let fetchPromise: Promise<FetchFn> | null = null;
function getFetch(): Promise<FetchFn> {
  if (!fetchPromise) {
    fetchPromise = IS_MOCK
      ? import("./mock").then((m) => m.mockFetch)
      : Promise.resolve((input: string, init?: RequestInit) => fetch(input, init));
  }
  return fetchPromise;
}

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail = `${res.status} ${res.statusText}`.trim();
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail: unknown }).detail;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d))
        detail = d
          .map((e: unknown) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : String(e)))
          .join(" ; ");
    }
  } catch {
    /* corps non JSON */
  }
  return new ApiError(res.status, detail);
}

function url(path: string, query?: Record<string, string | null | undefined>): string {
  // Chemin relatif (« api/… ») : fonctionne quel que soit le préfixe de montage du frontend.
  let u = `${BASE}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) if (v != null && v !== "") params.set(k, v);
    const qs = params.toString();
    if (qs) u += `?${qs}`;
  }
  return u;
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const f = await getFetch();
  const init: RequestInit = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { ...init.headers, "Content-Type": "application/json" };
  }
  if (signal) init.signal = signal;
  const res = await f(path.startsWith(BASE) ? path : url(path), init);
  if (!res.ok) throw await errorFrom(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const enc = encodeURIComponent;

async function lireFlux(res: Response, onEvent: (ev: StreamEvent) => void): Promise<void> {
  if (!res.ok) throw await errorFrom(res);
  if (!res.body) throw new ApiError(res.status, "Réponse sans corps");
  await readSSE(res.body, (msg) => {
    const ev = toStreamEvent(msg.event, msg.data);
    if (ev) onEvent(ev);
  });
}

export const api = {
  // ── Fournisseurs
  listProviders: () => request<Fournisseur[]>("GET", "/providers"),
  createProvider: (body: NouveauFournisseur) => request<Fournisseur>("POST", "/providers", body),
  updateProvider: (id: string, body: PatchFournisseur) => request<Fournisseur>("PATCH", `/providers/${enc(id)}`, body),
  deleteProvider: (id: string) => request<void>("DELETE", `/providers/${enc(id)}`),
  remoteModels: (id: string, signal?: AbortSignal) =>
    request<ModeleDistant[]>("GET", `/providers/${enc(id)}/remote-models`, undefined, signal),
  setProviderModels: (id: string, models: ModeleActive[]) =>
    request<Fournisseur>("PUT", `/providers/${enc(id)}/models`, { models }),
  listModels: () => request<ModeleChoix[]>("GET", "/models"),

  // ── Réglages
  getSettings: () => request<Reglages>("GET", "/settings"),
  putSettings: (body: Reglages) => request<Reglages>("PUT", "/settings", body),

  // ── Conversations
  listConversations: () => request<ConversationResume[]>("GET", "/conversations"),
  createConversation: (title?: string) =>
    request<Conversation>("POST", "/conversations", title ? { title } : {}),
  getConversation: (id: string) => request<Conversation>("GET", `/conversations/${enc(id)}`),
  renameConversation: (id: string, title: string) =>
    request<ConversationResume>("PATCH", `/conversations/${enc(id)}`, { title }),
  deleteConversation: (id: string) => request<void>("DELETE", `/conversations/${enc(id)}`),
  stopConversation: (id: string) => request<void>("POST", `/conversations/${enc(id)}/stop`),

  /**
   * Envoie un message et lit le flux SSE de la réponse. `onEvent` reçoit chaque événement typé.
   * La promesse se résout à la fin du flux ; elle rejette sur erreur HTTP / réseau / abandon.
   */
  async sendMessage(
    id: string,
    body: EnvoiMessage,
    onEvent: (ev: StreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const f = await getFetch();
    const init: RequestInit = {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
    };
    if (signal) init.signal = signal;
    const res = await f(url(`/conversations/${enc(id)}/messages`), init);
    await lireFlux(res, onEvent);
  },

  /**
   * Se rattache à la génération en cours d'une conversation (rejeu depuis `user_message`, puis direct).
   * Renvoie `false` si aucune génération n'est en cours (204). Abandonner la lecture (signal)
   * n'arrête PAS la génération côté serveur ; seul `stopConversation` le fait.
   */
  async resumeStream(id: string, onEvent: (ev: StreamEvent) => void, signal?: AbortSignal): Promise<boolean> {
    const f = await getFetch();
    const init: RequestInit = { method: "GET", headers: { Accept: "text/event-stream" } };
    if (signal) init.signal = signal;
    const res = await f(url(`/conversations/${enc(id)}/stream`), init);
    if (res.status === 204) return false;
    await lireFlux(res, onEvent);
    return true;
  },

  // ── Documents
  article: (id: string, date?: string | null) =>
    request<VueArticle>("GET", url(`/documents/article/${enc(id)}`, { date })),
  section: (id: string, date?: string | null) =>
    request<VueNoeud>("GET", url(`/documents/section/${enc(id)}`, { date })),
  texte: (cid: string, date?: string | null) =>
    request<VueNoeud>("GET", url(`/documents/texte/${enc(cid)}`, { date })),
  recherche: (q: string, texte?: string | null, date?: string | null) =>
    request<ResultatRecherche>("GET", url("/documents/recherche", { q, texte, date })),
  textes: () => request<TexteCorpus[]>("GET", "/textes"),

  // ── BOFiP-Impôts
  bofipDocument: (id: string) => request<VueBofip>("GET", `/bofip/documents/${enc(id)}`),
  bofipPlan: (noeud?: string | null) => request<VueBofipNoeud>("GET", url("/bofip/plan", { noeud })),
  bofipRecherche: (q: string, serie?: string | null) =>
    request<ResultatRechercheBofip>("GET", url("/bofip/recherche", { q, serie })),

  // ── Divers
  health: () => request<Sante>("GET", "/health"),
};

export type Api = typeof api;
