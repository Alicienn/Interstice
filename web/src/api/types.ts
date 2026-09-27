// Types du contrat d'API (docs/contrat-api.md). Toute évolution du contrat se reporte ici.

// ─── 1. Fournisseurs de modèles ──────────────────────────────────────────────

export type ThinkingSource = "api" | "heuristique" | "manuel" | "catalogue";

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

/** Liste de l'API du fournisseur ∪ catalogue models.dev. */
export type ModeleDistant = {
  id: string;
  owned_by?: string | null;
  label?: string | null;
  context_length?: number | null;
  max_output?: number | null;
  /** Source « catalogue » (models.dev) > « api » > « heuristique ». */
  thinking: ThinkingSupport;
  /** « catalogue » : connu de models.dev mais non listé par GET /models du fournisseur. */
  origine: "api" | "api+catalogue" | "catalogue";
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

export type DocKind = "article" | "section" | "texte" | "recherche" | "bofip";

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
  /** Durée réelle de la génération (aussi dans message_end.usage). */
  duree_ms?: number;
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

export type ConversationResume = {
  id: string;
  title: string;
  updated_at: string;
  /** Une génération tourne côté serveur (indépendamment de toute connexion). */
  generation_en_cours?: boolean;
};
export type Conversation = ConversationResume & {
  messages: Message[];
  /** Message assistant partiel de la génération en cours (sauvegardé au fil de l'eau). */
  generation_message_id?: string | null;
};

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

export type DoctrineArticle = {
  id: string; // PGP
  boi: string;
  titre: string;
  nature: string;
  date: string;
  occurrences: number;
};

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
  /** Documents BOFiP citant l'article (vide si le BOFiP n'est pas ingéré ; absent sur un ancien backend). */
  doctrine?: DoctrineArticle[];
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

// ─── 3 bis. BOFiP-Impôts ─────────────────────────────────────────────────────

export type MietteBofip = { id: string; noeud: string; code: string | null; titre: string };

export type RefBofip = {
  id: string;
  boi: string | null;
  titre: string | null;
  nature: string | null;
  date: string | null;
  disponible: boolean;
  type: string;
  cible_type: string;
};

export type FichierBofip = {
  pgp: string;
  type: string;
  titre: string | null;
  mime: string | null;
  taille: number | null;
  chemin: string | null;
};

export type ArticleCite = {
  code: string;
  num: string;
  texte_cid: string | null;
  article_id: string | null;
  libelle: string;
  occurrences: number;
};

export type VueBofip = {
  id: string;
  pgp: string;
  boi: string;
  boi_base: string;
  titre: string;
  serie: string;
  division: string | null;
  nature: "Contenu" | "Actualité";
  type_contenu: string | null;
  date: string;
  permalien: string | null;
  courant: boolean;
  homonymes: unknown[];
  chemin: MietteBofip[];
  html: string;
  relations: { sortantes: RefBofip[]; entrantes: RefBofip[]; fichiers: FichierBofip[] };
  articles_cites: ArticleCite[];
  versions: { id: string; boi: string; date: string; motif: string }[];
};

export type EnfantBofip = {
  noeud: string;
  id: string | null; // PGP si le nœud est un document
  code: string | null;
  titre: string;
  origine: string;
  nb_documents: number;
};

export type VueBofipNoeud = {
  noeud: string | null;
  id: string | null;
  code: string | null;
  titre: string;
  chemin: MietteBofip[];
  enfants: EnfantBofip[];
};

export type LigneRechercheBofip = {
  id: string;
  boi: string;
  titre: string;
  serie: string;
  nature: string;
  date: string;
  extrait_html: string;
};

export type ResultatRechercheBofip = { resultats: LigneRechercheBofip[] };

// ─── 4. Divers ───────────────────────────────────────────────────────────────

export type Sante = { ok: boolean; db: { articles: number; derniere_ingestion: string | null } };
