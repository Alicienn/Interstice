// Types du contrat d'API (docs/contrat-api.md). Toute évolution du contrat se reporte ici.

// ─── 1. Fournisseurs de modèles ──────────────────────────────────────────────

export type ThinkingSource = "api" | "heuristique" | "manuel";

export type ThinkingSupport = {
  supported: boolean;
  levels: string[];
  source: ThinkingSource;
};

export type ModeleActive = {
  id: string;
  label?: string;
  thinking: ThinkingSupport;
  context_length?: number | null;
};

export type TypeFournisseur = "openai" | "anthropic";

export type Fournisseur = {
  id: string;
  name: string;
  type: TypeFournisseur;
  base_url: string;
  api_key_set: boolean;
  models: ModeleActive[];
};

export type ModeleDistant = {
  id: string;
  owned_by?: string | null;
  context_length?: number | null;
  thinking: ThinkingSupport;
  enabled: boolean;
};

export type ModeleChoix = {
  key: string; // "<providerId>::<modelId>"
  provider_id: string;
  provider_name: string;
  model_id: string;
  label: string;
  thinking: ThinkingSupport;
};

export type NouveauFournisseur = {
  name: string;
  type: TypeFournisseur;
  base_url: string;
  api_key: string;
};

export type PatchFournisseur = {
  name?: string;
  base_url?: string;
  api_key?: string;
};

export type Reglages = {
  default_model_key: string | null;
  default_thinking: string | null;
};

// ─── 2. Conversations ────────────────────────────────────────────────────────

export type DocKind = "article" | "section" | "texte" | "recherche";

export type DocRef = {
  kind: DocKind;
  id: string;
  titre: string;
  sous_titre: string;
  date: string | null;
};

export type ToolStatus = "running" | "done" | "error";

export type ThinkingPart = { type: "thinking"; text: string };
export type TextPart = { type: "text"; text: string };
export type ToolPart = {
  type: "tool";
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: ToolStatus;
  summary?: string;
  documents: DocRef[];
};
export type Part = ThinkingPart | TextPart | ToolPart;

export type Usage = {
  input_tokens?: number;
  output_tokens?: number;
  cache_read_tokens?: number;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  parts: Part[];
  created_at: string;
  model_key?: string | null;
  thinking_level?: string | null;
  error?: string | null;
  usage?: Usage | null;
};

export type ConversationResume = { id: string; title: string; updated_at: string };
export type Conversation = ConversationResume & { messages: Message[] };

export type EnvoiMessage = {
  content: string;
  model_key: string;
  thinking_level: string | null;
};

// Événements SSE (nom `event:` → forme de `data:`)
export type StreamEvent =
  | { event: "user_message"; data: Message }
  | { event: "message_start"; data: { message_id: string; model_key: string | null; thinking_level: string | null } }
  | { event: "thinking_delta"; data: { text: string } }
  | { event: "text_delta"; data: { text: string } }
  | { event: "tool_call"; data: { call_id: string; name: string; arguments: Record<string, unknown> } }
  | {
      event: "tool_result";
      data: { call_id: string; status: ToolStatus; summary: string; documents: DocRef[] };
    }
  | { event: "message_end"; data: { message_id: string; usage: Usage | null } }
  | { event: "error"; data: { message: string } };

export type StreamEventName = StreamEvent["event"];

// ─── 3. Documents ────────────────────────────────────────────────────────────

export type Miette = { id: string; kind: "texte" | "section"; titre: string };

export type Renvoi = {
  id: string | null;
  cle: string | null;
  num: string | null;
  texte_titre: string;
  typelien: string;
  origine: "legi" | "texte";
  libelle: string;
};

export type VersionArticle = { id: string; etat: string; date_debut: string; date_fin: string };

export type VueArticle = {
  id: string;
  cle: string;
  num: string;
  texte_cid: string;
  texte_titre: string;
  sigle: string | null;
  etat: string;
  date_debut: string;
  date_fin: string;
  chemin: Miette[];
  html: string;
  nota_html: string | null;
  url_legifrance: string;
  versions: VersionArticle[];
  renvois_sortants: Renvoi[];
  renvois_entrants: Renvoi[];
};

export type EnfantNoeud = {
  kind: "section" | "article";
  id: string;
  titre: string;
  etat: string;
  nb_articles?: number;
};

export type VueNoeud = {
  id: string;
  kind: "texte" | "section";
  titre: string;
  texte_cid: string;
  chemin: Miette[];
  date: string;
  enfants: EnfantNoeud[];
};

export type LigneRecherche = {
  id: string;
  num: string;
  texte_titre: string;
  chemin: string;
  extrait_html: string;
};

export type ResultatRecherche = { resultats: LigneRecherche[] };

export type TexteCorpus = {
  cid: string;
  sigle: string;
  titre: string;
  nature: string;
  fiscal: boolean;
  nb_articles_vigueur: number;
};

// ─── 4. Divers ───────────────────────────────────────────────────────────────

export type Sante = { ok: boolean; db: { articles: number; derniere_ingestion: string | null } };
