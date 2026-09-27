# Contrat d'API — backend FastAPI ↔ frontend React

Base : `/api`. JSON UTF-8. Le backend sert aussi le frontend compilé (`web/dist`) sur `/`.
En développement : Vite sur `:5173` avec proxy `/api` → `http://127.0.0.1:8765`.

## 1. Fournisseurs de modèles

Un fournisseur = une URL de base + une clé. Deux types :
- `openai` : toute API compatible OpenAI Chat Completions (OpenAI, OpenRouter, Mistral, DeepSeek,
  Groq, vLLM, Ollama, LM Studio, endpoint de compatibilité Anthropic…).
- `anthropic` : API Messages native d'Anthropic (cache de prompt, réflexion adaptative, `effort`).

La clé n'est **jamais** renvoyée au frontend (`api_key_set: bool` seulement).

```ts
type ThinkingSupport = {
  supported: boolean;            // réglage proposé dans le sélecteur
  levels: string[];              // ex. ["low","medium","high"] ou ["low","medium","high","xhigh","max"]
  source: "api" | "heuristique" | "manuel";  // d'où vient l'information
};
type ModeleActive = { id: string; label?: string; thinking: ThinkingSupport; context_length?: number | null };
type Fournisseur = {
  id: string; name: string; type: "openai" | "anthropic";
  base_url: string; api_key_set: boolean; models: ModeleActive[];
};
type ModeleDistant = {             // renvoyé par l'API du fournisseur, non encore activé
  id: string; owned_by?: string | null; context_length?: number | null;
  thinking: ThinkingSupport;       // meilleure détection possible (supported=false si inconnu)
  enabled: boolean;                // déjà activé chez nous
};
```

| Méthode | Route | Corps | Réponse |
|---|---|---|---|
| GET | `/providers` | — | `Fournisseur[]` |
| POST | `/providers` | `{name, type, base_url, api_key}` | `Fournisseur` |
| PATCH | `/providers/{id}` | `{name?, base_url?, api_key?}` | `Fournisseur` |
| DELETE | `/providers/{id}` | — | `204` |
| GET | `/providers/{id}/remote-models` | — | `ModeleDistant[]` (appel live à `GET {base_url}/models`) ; erreur fournisseur → `502 {detail}` |
| PUT | `/providers/{id}/models` | `{models: ModeleActive[]}` (liste complète des modèles cochés) | `Fournisseur` |
| GET | `/models` | — | `ModeleChoix[]` : tous les modèles activés, tous fournisseurs |

```ts
type ModeleChoix = { key: string /* "<providerId>::<modelId>" */; provider_id: string;
  provider_name: string; model_id: string; label: string; thinking: ThinkingSupport };
```

Réglages divers : `GET /settings` → `{default_model_key: string|null, default_thinking: string|null}` ;
`PUT /settings` (même forme).

## 2. Conversations

```ts
type Part =
  | { type: "thinking"; text: string }
  | { type: "text"; text: string }
  | { type: "tool"; call_id: string; name: string; arguments: Record<string, unknown>;
      status: "running" | "done" | "error"; summary?: string; documents: DocRef[] };
type Message = { id: string; role: "user" | "assistant"; parts: Part[]; created_at: string;
  model_key?: string | null; thinking_level?: string | null; error?: string | null;
  usage?: { input_tokens?: number; output_tokens?: number; cache_read_tokens?: number } | null };
type ConversationResume = { id: string; title: string; updated_at: string };
type Conversation = ConversationResume & { messages: Message[] };
type DocRef = { kind: "article" | "section" | "texte" | "recherche"; id: string;
  titre: string; sous_titre: string; date: string | null };
```

| Méthode | Route | Corps | Réponse |
|---|---|---|---|
| GET | `/conversations` | — | `ConversationResume[]` (récentes d'abord) |
| POST | `/conversations` | `{title?}` | `Conversation` |
| GET | `/conversations/{id}` | — | `Conversation` |
| PATCH | `/conversations/{id}` | `{title}` | `ConversationResume` |
| DELETE | `/conversations/{id}` | — | `204` |
| POST | `/conversations/{id}/messages` | `{content, model_key, thinking_level: string\|null}` | **flux SSE** |
| POST | `/conversations/{id}/stop` | — | `204` (interrompt la génération en cours) |

### Événements SSE (`event:` + `data:` JSON)

| event | data | effet côté UI |
|---|---|---|
| `user_message` | `Message` | ajoute le message utilisateur (id définitif) |
| `message_start` | `{message_id, model_key, thinking_level}` | crée la bulle assistant |
| `thinking_delta` | `{text}` | ajoute au bloc « réflexion » courant (repliable) |
| `text_delta` | `{text}` | ajoute au bloc texte courant (markdown) |
| `tool_call` | `{call_id, name, arguments}` | ajoute une part `tool` en `running` |
| `tool_result` | `{call_id, status, summary, documents: DocRef[]}` | passe la part en `done`/`error`, affiche les cartes |
| `message_end` | `{message_id, usage}` | fin |
| `error` | `{message}` | affiche l'erreur dans la bulle |

Le titre d'une conversation sans titre = premiers mots du premier message.

## 3. Documents (panneau de lecture)

| Méthode | Route | Réponse |
|---|---|---|
| GET | `/documents/article/{id}?date=AAAA-MM-JJ` | `VueArticle` |
| GET | `/documents/section/{id}?date=` | `VueNoeud` |
| GET | `/documents/texte/{cid}?date=` | `VueNoeud` (racine du texte) |
| GET | `/documents/recherche?q=&texte=&date=` | `{resultats: LigneRecherche[]}` |
| GET | `/textes` | `{cid, sigle, titre, nature, fiscal: boolean, nb_articles_vigueur}[]` |

```ts
type Miette = { id: string; kind: "texte" | "section"; titre: string };
type VueArticle = {
  id: string; cle: string; num: string; texte_cid: string; texte_titre: string; sigle: string | null;
  etat: string; date_debut: string; date_fin: string; chemin: Miette[];
  html: string; nota_html: string | null; url_legifrance: string;
  versions: { id: string; etat: string; date_debut: string; date_fin: string }[];
  renvois_sortants: Renvoi[]; renvois_entrants: Renvoi[];
};
type Renvoi = { id: string | null; cle: string | null; num: string | null; texte_titre: string;
  typelien: string; origine: "legi" | "texte"; libelle: string };
type VueNoeud = { id: string; kind: "texte" | "section"; titre: string; texte_cid: string;
  chemin: Miette[]; date: string;
  enfants: { kind: "section" | "article"; id: string; titre: string; etat: string;
             nb_articles?: number }[] };
type LigneRecherche = { id: string; num: string; texte_titre: string; chemin: string; extrait_html: string };
```

`html` / `nota_html` : HTML d'origine LEGI, assaini côté serveur (balises de structure seulement).
Dans `html`, les renvois résolus sont des liens `<a data-article="LEGIARTI…">` que le panneau
intercepte pour naviguer sans quitter le chat.

`VueArticle` porte aussi `doctrine: {id /* PGP */, boi, titre, nature, date, occurrences}[]` : documents
BOFiP qui citent l'article (vide si le BOFiP n'est pas ingéré).

## 3 bis. BOFiP-Impôts (doctrine)

`DocRef.kind` accepte `"bofip"` : `id` = identifiant PGP (`"739-PGP"`) ou `"739-PGP@AAAA-MM-JJ"` pour une
version antérieure ; `titre` = BOI daté ; `sous_titre` = titre court ; `date` = date de publication.

| Méthode | Route | Réponse |
|---|---|---|
| GET | `/bofip/documents/{id}` | `VueBofip` |
| GET | `/bofip/plan?noeud=` | `VueBofipNoeud` (sans `noeud` : les séries) |
| GET | `/bofip/recherche?q=&serie=` | `{resultats: {id, boi, titre, serie, nature, date, extrait_html}[]}` |

```ts
type MietteBofip = { id: string /* PGP ou nœud */; noeud: string; code: string | null; titre: string };
type RefBofip = { id: string; boi: string | null; titre: string | null; nature: string | null;
  date: string | null; disponible: boolean; type: string; cible_type: string };
type VueBofip = {
  id: string; pgp: string; boi: string; boi_base: string; titre: string; serie: string; division: string | null;
  nature: "Contenu" | "Actualité"; type_contenu: string | null; date: string; permalien: string | null;
  courant: boolean; homonymes: unknown[]; chemin: MietteBofip[]; html: string;
  relations: { sortantes: RefBofip[]; entrantes: RefBofip[];
               fichiers: { pgp: string; type: string; titre: string | null; mime: string | null; taille: number | null; chemin: string | null }[] };
  articles_cites: { code: string; num: string; texte_cid: string | null; article_id: string | null;
                    libelle: string; occurrences: number }[];
  versions: { id: string; boi: string; date: string; motif: string }[];
};
type VueBofipNoeud = { noeud: string | null; id: string | null; code: string | null; titre: string;
  chemin: MietteBofip[];
  enfants: { noeud: string; id: string | null /* PGP si le nœud est un document */; code: string | null;
             titre: string; origine: string; nb_documents: number }[] };
```

Dans `html` : `<a data-bofip="NNN-PGP" data-ancre="…">` (autre document BOFiP), `<a data-bofip-fichier>` (pièce
jointe, non servie), `<img data-bofip-image>` (image non servie), `<a data-article="LEGIARTI…">` (article de loi).

## 4. Divers
- `GET /health` → `{ok: true, db: {articles: number, derniere_ingestion: string|null}}`
- `GET /tools` → schémas des outils exposés à l'agent (débogage).
