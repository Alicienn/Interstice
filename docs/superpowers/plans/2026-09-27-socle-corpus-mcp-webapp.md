# Socle Interstice : corpus LEGI exhaustif, outils de navigation, MCP, application web

> **Pour les agents :** exécuter tâche par tâche. Les étapes utilisent des cases `- [ ]`.
> Écart assumé au format « code complet dans le plan » : le code du parseur dépend de la
> structure réelle des dumps DILA, explorée pendant l'exécution. Chaque tâche fixe donc les
> fichiers, les interfaces, les tests et les critères d'acceptation, pas le code ligne à ligne.

**Objectif :** une base locale **exhaustive** de LEGI (tous les codes et textes, toutes les versions),
des outils de navigation hiérarchique (catégories → sous-catégories → articles) exposés en MCP et
dans une application web de chat multi-fournisseurs qui affiche les documents consultés.

**Architecture :** dumps DILA → SQLite (tables versionnées + FTS5) → module `interstice.outils`
(fonctions pures, schémas JSON) → deux façades : serveur MCP (stdio) et API FastAPI
(agent à appels d'outils, flux SSE) → frontend React.

**Stack :** Python 3.11, uv, lxml, SQLite/FTS5, mcp (FastMCP), FastAPI, httpx ; React + TypeScript + Vite.

---

## Règle d'exhaustivité (non négociable)

Rien n'est filtré à l'ingestion : **chaque fichier XML de chaque archive est parsé et compté**.
L'audit prouve la complétude :
1. fichiers XML lus = objets insérés + doublons tracés + erreurs (erreurs = 0 attendu) ;
2. chaque `LIEN_ART` d'une structure de section pointe vers une version d'article présente ;
3. chaque version listée dans un bloc `<VERSIONS>` est présente ;
4. chaque article d'un code est atteignable depuis la racine du code (orphelins listés) ;
5. aucun article en vigueur sans texte (sauf mentions légitimes, listées) ;
6. comptage croisé indépendant (jeu AgentPublic/legi) sur les codes fiscaux.

## Tâches

### T1 — Téléchargement DILA ✅ (en cours d'exécution)
`src/interstice/sources/dila.py` : listing, chaîne global + incréments, reprise, manifest sha256.

### T2 — Parseur LEGI
- Créer `src/interstice/legi/parser.py` : `parse(xml_bytes) -> Texte | Section | Article | None`
  (dataclasses), HTML → texte brut lisible (`legi/html.py`).
- Tests `tests/legi/test_parser.py` sur fixtures réelles extraites d'un incrément (`tests/fixtures/legi/`).
- Critère : tous les champs de la DTD utiles (méta, contexte TM daté, VERSIONS, LIENS, NOTA, BLOC_TEXTUEL).

### T3 — Schéma SQLite + ingestion
- `src/interstice/store/schema.sql`, `store/db.py`.
- `src/interstice/legi/ingest.py` : lecture en flux des tar.gz, parsing parallèle, remplacement par
  identifiant (dernier gagne), listes de suppression, journal par archive.
- Regroupement des versions en **article logique** (union des blocs VERSIONS, clé = plus petit id).
- Commande `interstice ingest legi`.

### T4 — Audit d'exhaustivité
- `src/interstice/audit/legi.py` + commande `interstice audit` → rapport `data/audit/legi-<date>.md`.
- Tests sur une mini-base synthétique qui contient volontairement un orphelin et un lien cassé.

### T5 — Graphe des renvois
- Liens LEGI (`CITATION`, `MODIFIE`…) résolus au niveau article logique.
- `src/interstice/graph/citations.py` : extraction des renvois dans le texte
  (« articles 150-0 A à 150-0 E du présent code », « L. 64 du livre des procédures fiscales »…),
  résolution par **plus long préfixe existant** dans le texte cible. Tests sur phrases réelles du CGI.

### T6 — Outils de navigation (`src/interstice/outils/`)
Fonctions pures + schémas JSON, partagées MCP / web :
`lister_textes`, `sommaire` (enfants d'un nœud à une date, avec comptes), `lire_article`
(texte, fil d'Ariane, versions, renvois), `historique_article`, `comparer_versions`,
`rechercher` (FTS5 filtrable par texte / section / date), `renvois` (sortants / entrants),
`modifications` (articles modifiés sur une période).
Par défaut : date = aujourd'hui, périmètre = codes fiscaux.

### T7 — Serveur MCP
`src/interstice/mcp_server.py` (FastMCP, stdio), commande `interstice mcp`. Test : liste des outils + appel.

### T8 — Backend web
`src/interstice/web/` : FastAPI. Fournisseurs OpenAI-compatibles (URL + clé), `/models`,
modèles activés, niveau de réflexion, conversations persistées, boucle agent à outils, SSE.
Contrat : `docs/contrat-api.md`.

### T9 — Frontend
`web/` (React + TS + Vite) : réglages (fournisseurs, recherche + cases à cocher + validation),
chat en flux, sélecteur modèle / réflexion, cartes « document lu » + panneau de lecture.

### T10 — BOFiP
Archiveur (stock mensuel + flux hebdo, md5), ingestion avec plan de classement navigable, outils dédiés.

### T11 — Export Markdown (optionnel)
Un fichier par article, arborescence du code (lisible dans Obsidian).
