# Gérer la connaissance d'un LLM sans RAG vectoriel classique : état de l'art 2025-2026

> **Contexte.** Système d'IA spécialisé en droit fiscal français (CGI, LPF, BOFiP, jurisprudence). Le corpus fait plusieurs dizaines de millions de tokens et le modèle (famille Claude) a une fenêtre d'environ 1M tokens. Objectif : un **raisonnement transversal** (croiser des articles, repérer des incohérences, des interactions entre régimes et des zones grises), ce que le RAG « chunks + embeddings + top-k » fait mal.
>
> **Date de rédaction :** 27 septembre 2026.
>
> **Convention de lecture.** Chaque section sépare deux choses :
> - **Faits sourcés** : ce qu'affirme une source citée (URL). Quand la source est secondaire (blog, agrégateur), c'est indiqué.
> - **Analyse (inférence)** : mon interprétation et son application au cas fiscal. Ces passages ne sont pas des faits établis.

---

## Table des matières

1. [Long context « tout dans le prompt »](#1-long-context--tout-dans-le-prompt-)
2. [Cache-Augmented Generation (CAG) et prompt caching](#2-cache-augmented-generation-cag-et-prompt-caching)
3. [Recherche agentique (agentic search)](#3-recherche-agentique-agentic-search)
4. [Divulgation progressive et connaissance hiérarchique](#4-divulgation-progressive-et-connaissance-hiérarchique)
5. [Graphes de connaissance et ontologies juridiques](#5-graphes-de-connaissance-et-ontologies-juridiques)
6. [Mémoire d'agent, sous-agents et orchestration multi-agents](#6-mémoire-dagent-sous-agents-et-orchestration-multi-agents)
7. [Fine-tuning et continued pretraining](#7-fine-tuning-et-continued-pretraining)
8. [Formalisation du droit en code et détection de failles](#8-formalisation-du-droit-en-code-et-détection-de-failles)
9. [Synthèse : architecture hybride recommandée](#9-synthèse--architecture-hybride-recommandée)
10. [Sources](#10-sources)

---

## 1. Long context « tout dans le prompt »

### Faits sourcés

**Lost in the middle (Liu et al., 2023, TACL 2024).** La performance suit une courbe en U : elle est meilleure quand l'information pertinente se trouve au début ou à la fin du contexte, et se dégrade quand elle est au milieu. [arXiv 2307.03172](https://arxiv.org/abs/2307.03172)

**RULER (NVIDIA, 2024).** Les modèles ont un score quasi parfait sur le « needle in a haystack » simple, mais chutent fortement sur des tâches plus riches (multi-aiguilles, traçage de variables, agrégation). Parmi les modèles annonçant 32K tokens ou plus, seulement la moitié gardaient une performance satisfaisante à 32K. D'où la notion de **longueur de contexte effective**, distincte de la longueur annoncée. [arXiv 2404.06654](https://arxiv.org/abs/2404.06654), [GitHub NVIDIA/RULER](https://github.com/NVIDIA/RULER)

**NoLiMa (Adobe Research, ICML 2025).** Ce benchmark retire le recouvrement lexical entre la question et l'« aiguille » : le modèle doit faire une inférence latente, pas un simple appariement de mots. Sur 12 modèles annonçant au moins 128K, 10 tombent sous 50 % de leur score en contexte court dès **32K tokens**. [arXiv 2502.05167](https://arxiv.org/abs/2502.05167), [GitHub](https://github.com/adobe-research/NoLiMa)

**Context Rot (Chroma, 14 juillet 2025).** Étude de 18 modèles (Claude Opus 4, Sonnet 4, GPT-4.1, o3, Gemini 2.5, Qwen3…). [trychroma.com/research/context-rot](https://www.trychroma.com/research/context-rot)
- La performance se dégrade de façon **non uniforme** avec la longueur, même sur des tâches triviales (retrouver ou recopier du texte).
- Plus la similarité sémantique entre la question et l'information cherchée est faible, plus la dégradation est forte.
- Les **distracteurs** (passages proches mais faux) aggravent la dégradation, et chacun a un impact différent.
- Contre-intuitif : les modèles font mieux sur des « haystacks » dont les phrases sont mélangées que sur un texte cohérent.
- LongMemEval : il y a un écart significatif entre une entrée ciblée (environ 300 tokens) et l'entrée complète (environ 113k tokens), pour toutes les familles de modèles.
- Les Claude ont les taux d'hallucination les plus bas, mais s'abstiennent davantage. Les GPT hallucinent le plus en présence de distracteurs.

**LongBench v2 (THUDM, ACL 2025).** 503 QCM difficiles sur des contextes de 8k à 2M mots. Les experts humains atteignent 53,7 % (en 15 minutes). Le meilleur modèle en réponse directe atteint 50,1 %, et o1-preview, avec plus de raisonnement, 57,7 %. Le calcul au moment de l'inférence (raisonnement) compte donc beaucoup sur les tâches longues. [arXiv 2412.15204](https://arxiv.org/abs/2412.15204), [longbench2.github.io](https://longbench2.github.io/)

**MRCR v2 (8 aiguilles) et Fiction.LiveBench, 2026.** Chiffres relayés par une synthèse secondaire, [yage.ai (15 mars 2026)](https://yage.ai/share/long-context-benchmark-en-20260315.html), qui cite la system card d'Anthropic et contextarena.ai. À vérifier sur les sources primaires.
- Claude Opus 4.6 : **93 % à 256K** et **76 % à 1M**. Claude Sonnet 4.6 : 90,3 % à 256K et 65,8 % à 1M.
- Gemini 3 Pro : 45,4 % à 256K et 24,5 % à 1M. GPT-5.4 : 36,6 % sur la tranche 512K-1M.
- La même source parle d'une « capacité effective » d'environ 60-70 % de la fenêtre nominale. C'est une affirmation d'industrie, pas une mesure contrôlée.
- Fiction.LiveBench mesure la compréhension profonde de récits longs, pas la simple recherche d'information. [Leaderboard (fiction.live)](https://fiction.live/stories/Fiction-liveBench-Feb-21-2025/oQdzQvKHw8JyXbN87)

**Documentation Anthropic.**
- La doc des fenêtres de contexte reconnaît explicitement le *context rot* : « As token count grows, accuracy and recall degrade ». [platform.claude.com – Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)
- Les modèles Claude 4.6 et suivants (Opus 4.6 → Opus 5.5, Sonnet 4.6, Sonnet 5…) ont 1M tokens par défaut, au tarif standard.
- Bonnes pratiques officielles : placer les documents longs **en haut** du prompt et la question **à la fin**, ce qui améliore la qualité « jusqu'à 30 % » sur des entrées multi-documents complexes. Il est aussi recommandé de baliser les documents en XML (`<document>`, `<source>`) et de demander d'extraire des citations avant de raisonner. [Prompting best practices – Long context prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

**LaRA (Alibaba, ICML 2025).** Comparaison RAG vs long context sur 11 modèles : **pas de solution miracle**. Le bon choix dépend du modèle, de la longueur, du type de tâche (localisation, comparaison, raisonnement, détection d'hallucination) et de la qualité des chunks. [arXiv 2502.09977](https://arxiv.org/abs/2502.09977)

### Limites

- **Taille.** 1M tokens ne représente que quelques % d'un corpus de plusieurs dizaines de millions de tokens. « Tout dans le prompt » est impossible pour le corpus entier.
- **Dégradation avec la longueur.** Elle est forte dès que la tâche demande de l'inférence sémantique (NoLiMa) ou de l'agrégation (RULER, MRCR). Or c'est exactement le cas du raisonnement juridique transversal.
- **Distracteurs.** Le droit fiscal en est saturé : versions antérieures d'un article, régimes voisins aux conditions quasi identiques, BOFiP commentant d'autres millésimes. C'est le scénario le plus défavorable identifié par Chroma.
- **Coût et latence.** Chaque requête retraite tout le contexte, sauf s'il est mis en cache (voir §2).

### Analyse (inférence)

- La fenêtre de 1M est un **espace de travail**, pas une base de connaissance. Il faut la remplir avec un **sous-corpus cohérent**, par exemple un régime complet avec ses articles, les renvois, le BOFiP et la jurisprudence clé. Ordre de grandeur : 100k à 400k tokens.
- En première approximation, viser un remplissage de 25 à 60 % de la fenêtre pour les tâches de raisonnement fin. Le reste sert au raisonnement (thinking) et aux résultats d'outils.
- Le long context sert à ce que le RAG top-k ne sait pas faire : **comparer côte à côte** des textes entiers. Il ne sert pas à trouver une aiguille dans 30M tokens.
- Les chiffres MRCR des Claude récents sont très supérieurs à ceux de 2024-2025. Mais MRCR reste une tâche de recherche/désambiguïsation. Aucun benchmark public identifié ne mesure la détection d'incohérences juridiques à 1M tokens. **Il faudra construire un banc d'évaluation interne.**

---

## 2. Cache-Augmented Generation (CAG) et prompt caching

### Faits sourcés

**CAG (Chan et al., « Don't Do RAG », WWW 2025).** Le principe : précharger toute la base de connaissance dans le contexte et **précalculer le cache KV**, pour éliminer l'étape de recherche au moment de la question. Sur des bases de connaissance *de taille limitée*, les résultats sont comparables ou supérieurs au RAG, sans latence ni erreur de sélection de documents. [arXiv 2412.15605](https://arxiv.org/abs/2412.15605), [GitHub hhhuang/CAG](https://github.com/hhhuang/CAG)

**Cartridges (Stanford Hazy Research, 2025).** Une variante « entraînée » du CAG. On entraîne hors ligne un petit cache KV par corpus, par « self-study » : des conversations synthétiques sur le corpus, avec un objectif de distillation de contexte. Résultats [arXiv 2506.06266](https://arxiv.org/abs/2506.06266), [GitHub](https://github.com/HazyResearch/cartridges) :
- même performance que l'in-context learning avec **38,6× moins de mémoire** et un débit **26,4× plus élevé** ;
- extension de la longueur effective (de 128k à 484k sur MTOB) ;
- les cartouches sont composables.

Cela nécessite un accès aux poids du modèle, donc c'est **inapplicable à Claude via API**.

**Prompt caching Anthropic (doc consultée le 27/09/2026).** [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- **Écriture en cache :** 1,25× le prix d'entrée de base pour un TTL de 5 minutes, 2× pour un TTL d'1 heure.
- **Lecture en cache :** 0,1× le prix de base. Exceptions : **0,05× sur Claude Opus 5.5** et 0,025× sur Fable/Mythos 5.1.
- **Durée :** le TTL court depuis le début de la requête. Chaque lecture le rafraîchit.
- **Contraintes :** 4 points de cache (breakpoints) au maximum par requête et une fenêtre de rétro-recherche de 20 blocs.
- **Invalidation :** le cache est un **préfixe strict** dans l'ordre `tools → system → messages`. Modifier un niveau invalide ce niveau et tous les suivants.
- **Tarifs (par million de tokens) :** Opus 5.5 : entrée 4 $, écriture 5 min 5 $, écriture 1 h 8 $, lecture 0,20 $, sortie 20 $. Sonnet 5 : entrée 2 $, lecture 0,20 $, sortie 10 $.
- **Contexte long :** 1M tokens au tarif standard sur les modèles 4.6+. Pas de surcoût au-delà de 200k.
- La Batch API donne −50 % et se cumule avec le cache.
- Le tokenizer des modèles 4.7+ produit environ 30 % de tokens en plus pour un même texte.
- Les préfixes en cache **occupent toujours la fenêtre de contexte** : le cache change le prix, pas la capacité.

### Ordres de grandeur (calcul personnel à partir des tarifs ci-dessus)

| Scénario (Opus 5.5) | Coût d'entrée par requête |
|---|---|
| Préfixe de 500k tokens, non caché | ≈ 2,00 $ |
| Même préfixe, écriture initiale (TTL 1 h) | ≈ 4,00 $ une fois |
| Même préfixe, lecture en cache | ≈ 0,10 $ |
| Préfixe de 900k tokens, lecture en cache | ≈ 0,18 $ |

### Limites

- Le CAG ne marche que si la connaissance **tient dans la fenêtre**. Ce n'est pas le cas ici (plusieurs dizaines de millions de tokens).
- Le cache est invalidé à la moindre modification du préfixe. Il faut donc un préfixe **stable et versionné**, et placer le contenu variable après.
- Le cache ne corrige pas le *context rot* : un préfixe de 900k tokens mis en cache reste un contexte de 900k tokens pour l'attention du modèle.
- La latence du premier appel (écriture) reste élevée.

### Analyse (inférence)

- Utiliser le prompt caching pour un **« noyau fiscal » stable** d'environ 100k à 300k tokens. Contenu type : conventions d'interprétation, plan détaillé du CGI/LPF, définitions transversales (résidence fiscale, établissement stable, résultat fiscal…), fiches de synthèse par régime, index des renvois. Le cacher avec un TTL d'1 heure pour les sessions de travail.
- Construire aussi des **« packs régime » pré-assemblés** (ex. intégration fiscale, régime mère-fille, report déficitaire, abus de droit) qu'un sous-agent charge et cache pendant l'analyse.
- Mettre à jour le noyau au rythme des publications (lois de finances, rescrits BOFiP). Chaque mise à jour invalide le cache, donc il faut regrouper les mises à jour.

---

## 3. Recherche agentique (agentic search)

### Faits sourcés

**Retour d'expérience de Claude Code (Anthropic).** Boris Cherny, créateur de Claude Code : « Early versions of Claude Code used RAG + a local vector db, but we found pretty quickly that agentic search generally works better. It is also simpler and doesn't have the same issues around security, privacy, staleness, and reliability. » [X/@bcherny](https://x.com/bcherny/status/2017824286489383315). Sur le podcast Latent Space (mai 2025), il ajoute que l'agentic search « outperformed everything. By a lot. » (propos relayés par plusieurs sources secondaires, par ex. [vadim.blog](https://vadim.blog/claude-code-no-indexing/) et [smartscope.blog](https://smartscope.blog/en/ai-development/practices/rag-debate-agentic-search-code-exploration/)).

**Context engineering (Anthropic, 29 sept. 2025).** L'article décrit la stratégie « **just-in-time** ». L'agent garde des identifiants légers (chemins, requêtes, liens) et charge les données à la demande via des outils, au lieu de tout pré-récupérer par embeddings. Claude Code est hybride : « CLAUDE.md files are naively dropped into context up front, while primitives like glob and grep allow it to navigate its environment and retrieve files just-in-time. » [anthropic.com/engineering/effective-context-engineering-for-ai-agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

**LlamaIndex, « Did filesystem tools kill vector search? » (13 janv. 2026).** Comparaison entre un agent filesystem (Gemini 3 Flash, outils read/grep/parse) et un RAG hybride BM25 + dense (Qdrant). [llamaindex.ai](https://www.llamaindex.ai/blog/did-filesystem-tools-kill-vector-search)
- **Sur 5 documents :** l'agent est plus correct (8,4/10 contre 6,4) et plus pertinent (9,6 contre 8,0), car il lit des fichiers entiers sans perte liée au découpage. Il est en revanche plus lent (11,2 s contre 7,4 s).
- **Sur 100 et 1 000 documents :** la tendance **s'inverse**, et le RAG devient meilleur en vitesse *et* en exactitude.
- Conclusion des auteurs : aucune approche ne « tue » l'autre.

**PageIndex (VectifyAI, sept. 2025).** Un « RAG sans vecteurs » : chaque document reçoit un index arborescent (titre, résumé, plage de pages par nœud), et un LLM raisonne sur cet arbre pour choisir les sections à lire. L'éditeur annonce 98,7 % sur FinanceBench. C'est un chiffre de l'éditeur, non reproduit indépendamment à ma connaissance. [GitHub VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)

### Limites

- **Latence et coût :** de nombreux appels d'outils, et des tokens de lecture qui s'accumulent dans le contexte.
- **Passage à l'échelle :** l'étude LlamaIndex montre une dégradation de l'agent seul au-delà de quelques centaines de documents. Grep suppose aussi que l'agent **connaît les bons termes**.
- **Dépendance au vocabulaire :** le droit fiscal utilise des périphrases, des renvois (« les sociétés mentionnées au 1 de l'article 223 A ») et des notions définies ailleurs. Une recherche lexicale naïve manque les liens implicites.
- **Rappel non garanti :** l'agent peut s'arrêter trop tôt, ce qui est problématique quand l'objectif est l'exhaustivité (repérer *toutes* les interactions).

### Analyse (inférence)

- Le droit fiscal est un **terrain très favorable à la recherche agentique**, bien plus que du texte libre. Le corpus est déjà hiérarchisé (Livre > Partie > Titre > Chapitre > Section > Article), les identifiants sont stables (numéros d'articles, identifiants BOI-XXX, identifiants LEGIARTI, ECLI) et les renvois sont explicites. C'est l'équivalent d'un dépôt de code avec ses imports.
- Il faut donc matérialiser le corpus **en fichiers** (un article par fichier, métadonnées dans un en-tête YAML) et donner à l'agent des outils **spécialisés** : `get_article(id, date)`, `who_cites(id)`, `search(text, filters)`, `list_section(path)`. Le simple grep ne suffit pas.
- La recherche vectorielle peut rester **un outil parmi d'autres** (repli sémantique quand le vocabulaire est inconnu), mais pas le socle.

---

## 4. Divulgation progressive et connaissance hiérarchique

### Faits sourcés

**Agent Skills (Anthropic, 16 oct. 2025).** Un skill est un dossier contenant un `SKILL.md`, des scripts et des ressources. La divulgation progressive se fait à trois niveaux : [Engineering blog](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), [Doc Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
1. seules les métadonnées (nom et description) sont chargées au départ ;
2. le corps du `SKILL.md` est chargé si le skill est pertinent ;
3. les fichiers annexes sont chargés à la demande.

Citation : « the amount of context that can be bundled into a skill is effectively unbounded ». C'est devenu un standard ouvert adopté par d'autres plateformes.

**Context engineering (Anthropic).** Le document recommande la divulgation progressive (« incrementally discover relevant context through exploration »), des métadonnées signifiantes (noms de fichiers, hiérarchie de dossiers) et un contexte « le plus petit possible, à fort signal ». [Lien](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

**llms.txt (Jeremy Howard, 3 sept. 2024).** Un fichier Markdown à la racine d'un site, qui sert de carte (liens et résumés) pour les LLM au moment de l'inférence. C'est une proposition communautaire, pas un standard W3C/IETF. Selon des sources secondaires, aucun grand fournisseur n'a confirmé que ses crawlers le lisent systématiquement. [llmstxt.org](https://llmstxt.org/), [Search Engine Land](https://searchengineland.com/llms-txt-proposed-standard-453676)

**RAPTOR (Stanford, ICLR 2024).** Construit un arbre en partant du bas : les chunks sont regroupés par clusters, puis résumés récursivement. Au moment de la question, la recherche se fait à plusieurs niveaux d'abstraction. Associé à GPT-4, il améliore l'état de l'art sur QuALITY de 20 points absolus (d'après le résumé de l'article). [arXiv 2401.18059](https://arxiv.org/abs/2401.18059), [GitHub](https://github.com/parthsarthi03/raptor)

**PageIndex** (voir §3) applique le même principe d'index arborescent navigable par le LLM.

### Limites

- **Résumés :** ils perdent de l'information et peuvent introduire des erreurs, qui se propagent ensuite dans la navigation (risque d'« hallucination par résumé »).
- **Clusters RAPTOR :** leurs frontières sont sémantiques, pas juridiques. Deux articles d'un même régime peuvent se retrouver dans des branches différentes.
- **Maintenance :** il faut régénérer les résumés à chaque modification législative.
- **Maturité :** llms.txt n'est qu'une convention sans garantie d'usage.

### Analyse (inférence)

- Pour le droit fiscal, il ne faut **pas** construire l'arbre par clustering comme RAPTOR. Il faut utiliser **l'arborescence officielle** (plan du CGI/LPF, séries et divisions du BOFiP), déjà hiérarchique et faisant autorité, et la compléter par des **vues transversales** : par impôt, par type de contribuable, par notion définie, par opération (fusion, apport, cession…).
- Chaque nœud (dossier) reçoit un `INDEX.md` de style llms.txt : le résumé du nœud, la liste des enfants avec une ligne chacun, les renvois sortants majeurs et la date de dernière mise à jour. L'agent descend l'arbre comme Claude Code explore un dépôt.
- Des **skills « méthode »** encodent le savoir-faire procédural du fiscaliste : comment analyser l'interaction de deux régimes, comment vérifier la version en vigueur à une date, comment qualifier une zone grise. C'est distinct de la connaissance brute.
- Les résumés générés par LLM doivent être **marqués comme non normatifs**. L'agent doit toujours remonter au texte source avant de conclure.

---

## 5. Graphes de connaissance et ontologies juridiques

### Faits sourcés

**GraphRAG (Microsoft, 2024).**
- **Principe :** un LLM extrait entités et relations. Le graphe est ensuite découpé en communautés (algorithme de Leiden), puis chaque communauté est résumée à plusieurs niveaux. La « recherche globale » répond aux questions portant sur l'ensemble du corpus.
- **Coût :** l'indexation est chère. Un exemple rapporté : 2 984 communautés, et environ 650 $ et 106M tokens pour 100 questions en recherche globale (source secondaire).
- **LazyGraphRAG :** il réduit le coût d'indexation à 0,1 % de celui de GraphRAG, avec une qualité comparable en requête globale pour un coût de requête plus de 700× inférieur.

Sources : [Microsoft Research – LazyGraphRAG](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/), [Dynamic community selection](https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/).

**LightRAG (HKU, EMNLP 2025 Findings).** Graphe + vecteurs, recherche à deux niveaux (entités précises et thèmes abstraits), et **mise à jour incrémentale** sans réindexation complète. [arXiv 2410.05779](https://arxiv.org/abs/2410.05779), [GitHub HKUDS/LightRAG](https://github.com/hkuds/lightrag)

**SAT-Graph RAG (de Martim, Sénat fédéral du Brésil, 2025).** Un graphe **ontologique, temporel et déterministe** pour les normes juridiques :
- il distingue l'œuvre abstraite (Work) de ses versions datées (Expressions), sur le modèle LRMoo ;
- il modélise la hiérarchie structurelle de la norme ;
- il représente les événements législatifs comme des nœuds « Action » interrogeables ;
- il expose une API d'actions déterministes (`resolveItemReference`, `getValidVersion`, `traceCausality`) qui sépare la découverte probabiliste de la récupération de preuves déterministe.

Le graphe est construit **de haut en bas**, à partir de la structure formelle du droit, et non de bas en haut par extraction LLM. [arXiv 2505.00039](https://arxiv.org/abs/2505.00039)

**Autres travaux juridiques.** LegalGraphRAG (multi-agents, droit pénal chinois) : [arXiv 2605.28120](https://arxiv.org/abs/2605.28120). Un travail de 2026 montre que les taux d'hallucination rapportés dépendent de la **couverture du graphe de citations** utilisé comme oracle : [arXiv 2606.00898](https://arxiv.org/pdf/2606.00898).

**Standards et données ouvertes.**
- **ELI (European Legislation Identifier)** : un vocabulaire et des URI pour identifier la législation. Depuis fin 2014, les textes publiés au JO sur Légifrance ont une URI ELI. [Wikipedia ELI](https://en.wikipedia.org/wiki/European_Legislation_Identifier), [ACM – mapping ELI/AKN](https://dl.acm.org/doi/10.1145/3614321.3614327)
- **Akoma Ntoso** : un standard XML OASIS (LegalDocML) centré sur le cycle de vie des documents législatifs.
- **LegalRuleML** : un standard OASIS pour représenter les règles, les obligations et la défaisabilité.
- Ces vocabulaires coexistent avec ECLI (jurisprudence), LKIF et CEN Metalex.
- **Base LEGI (DILA)** : tous les codes, lois et règlements consolidés, **avec les versions historiques**, en XML. Un dump complet est publié environ deux fois par an, avec des mises à jour quotidiennes. Un décompte (blog, ancien) donne environ 1,6M de fichiers XML. L'API Légifrance est disponible via PISTE (stable depuis avril 2023). [data.gouv.fr – LEGI](https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides), [Légifrance – Open data et API](https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api), [Blog F. Gallaire](https://fgallaire.flext.net/open-data-juridique-lutilisation-de-la-base-legi/)
- Les bases jurisprudentielles de la DILA (JADE pour le Conseil d'État, CASS, CONSTIT…) partagent des DTD communes avec LEGI.

### Limites

- **GraphRAG « générique » :** l'extraction d'entités par LLM est bruitée et coûteuse. Le graphe produit est **non déterministe** et invérifiable, ce qui est un défaut rédhibitoire pour du droit si c'est la seule source.
- **Temporalité :** GraphRAG et LightRAG ne modélisent pas nativement le versionnage (« quelle rédaction était en vigueur au 31/12/2023 ? »), qui est **central** en fiscalité.
- **Frontières :** les graphes de citations explicites manquent les liens implicites (notions partagées sans renvoi, articles qui s'appliquent au même fait générateur).
- **Adoption :** Akoma Ntoso et LegalRuleML sont peu déployés en France. Les données LEGI ont leur propre DTD.

### Analyse (inférence)

- C'est **la brique la plus importante pour le raisonnement transversal**. Il faut un graphe **construit de haut en bas et déterministe**, à la manière de SAT-Graph, alimenté par LEGI (versions datées, liens de modification) et les identifiants ELI/ECLI. On l'enrichit ensuite par :
  1. l'extraction des renvois explicites par règles (regex et grammaire sur « article X du CGI », « au sens du I de l'article Y ») ;
  2. l'extraction par LLM, **validée**, des relations implicites : notion définie ↔ articles qui l'emploient, régime ↔ conditions, dérogation ↔ règle générale, BOFiP ↔ articles commentés, décision ↔ articles interprétés.
- Le graphe sert à **générer des hypothèses de croisement**. Par exemple : « tous les couples d'articles qui emploient la notion X avec des conditions différentes », ou « tous les régimes qui renvoient à 39-1-5° et leurs dates de modification respectives ». Le LLM vérifie ensuite ces hypothèses **en long context**, texte intégral sous les yeux.
- Il ne faut **pas** utiliser les résumés de communautés à la GraphRAG comme source de vérité. Tout au plus comme carte de navigation.

---

## 6. Mémoire d'agent, sous-agents et orchestration multi-agents

### Faits sourcés

**Context engineering (Anthropic).** Trois techniques pour les tâches longues [lien](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) :
1. la **compaction** (résumer puis repartir) ;
2. la **prise de notes structurée** hors contexte ;
3. les **sous-agents** à contexte isolé, qui renvoient un résumé condensé (« often 1,000-2,000 tokens »).

**Memory tool et context editing (Anthropic, 29 sept. 2025).** [Blog](https://claude.com/blog/context-management), [Doc memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- Le memory tool est un outil côté client (CRUD sur des fichiers persistants) ; c'est le développeur qui contrôle le stockage.
- Le context editing retire automatiquement les anciens résultats d'outils.
- Sur une évaluation interne de recherche web en 100 tours, le context editing réduit la consommation de tokens de 84 %.
- Gains annoncés : +39 % pour mémoire + context editing, +29 % pour le context editing seul.
- La compaction côté serveur est en bêta sur les modèles 4.6+. [Doc context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)

**Système de recherche multi-agents (Anthropic, 13 juin 2025).** [anthropic.com/engineering/multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Un orchestrateur Opus 4 avec des sous-agents Sonnet 4 fait **+90,2 %** par rapport à Opus 4 seul, sur une évaluation interne de recherche.
- Coût : environ **15× plus de tokens** qu'un chat (environ 4× pour un agent seul). La quantité de tokens explique à elle seule 80 % de la variance de performance.
- Le plan de recherche est sauvegardé en mémoire externe, car le contexte peut être tronqué au-delà de 200k tokens.
- Mise en garde des auteurs : l'approche convient mal aux tâches qui demandent un **contexte partagé** ou de nombreuses interdépendances.

### Limites

- **Coût :** multiplication des tokens (×15).
- **Perte d'information :** elle se produit à chaque résumé (sous-agent → orchestrateur, compaction).
- **Nature du raisonnement transversal :** il est, par définition, *interdépendant*. C'est précisément le cas où Anthropic dit que le multi-agent est moins adapté. Scinder naïvement le corpus entre sous-agents peut **casser** les croisements recherchés.
- **Mémoire persistante :** elle peut accumuler des erreurs (conclusions fausses réutilisées) si elle n'est pas versionnée et vérifiée.

### Analyse (inférence)

- Utiliser les sous-agents pour des **tâches parallélisables** : balayage exhaustif (« passer chaque article du chapitre X au crible de la question Y »), collecte de jurisprudence, vérification de citations, mise à jour des index.
- Garder le **croisement final dans un seul contexte long** : l'orchestrateur ou un agent « juge » reçoit les textes intégraux des articles candidats, pas seulement des résumés.
- Pattern proposé :
  1. le graphe propose N paires ou groupes d'articles candidats ;
  2. des sous-agents analysent chaque groupe en long context (100-300k tokens, avec le noyau en cache) ;
  3. chaque sous-agent renvoie une note structurée (hypothèse, textes, versions, citations exactes, niveau de confiance) ;
  4. un agent de vérification contrôle chaque citation contre le corpus à la date pertinente.
- La **mémoire du projet** (fichiers Markdown versionnés sous git) contient les conclusions validées, les zones grises déjà identifiées et les décisions d'interprétation. Elle sert de contexte de départ aux sessions suivantes.

---

## 7. Fine-tuning et continued pretraining

### Faits sourcés

**Ovadia et al. (Microsoft, EMNLP 2024).** Le RAG surpasse **systématiquement** le fine-tuning non supervisé pour injecter de la connaissance, qu'elle soit déjà vue ou nouvelle. Sur les connaissances nouvelles, RAG obtient environ 0,875 contre environ 0,50 pour le fine-tuning (Mistral, Orca). [arXiv 2312.05934](https://arxiv.org/abs/2312.05934)

**Gekhman et al. (Google, EMNLP 2024).**
- Les exemples de fine-tuning qui apportent une connaissance **nouvelle** sont appris plus lentement.
- Une fois appris, ils **augmentent linéairement la tendance à halluciner**.
- Les LLM acquièrent l'essentiel de leur connaissance factuelle au pré-entraînement. Le fine-tuning leur apprend surtout à mieux l'utiliser.

[arXiv 2405.05904](https://arxiv.org/abs/2405.05904)

**FineTuneBench (2024).** Via les API commerciales de fine-tuning, la précision de généralisation est en moyenne de **37 %** sur des connaissances nouvelles et de **19 %** sur des *mises à jour* de connaissances existantes. Gemini 1.5 n'apprend quasiment rien. [arXiv 2411.05059](https://arxiv.org/abs/2411.05059)

**Synthetic continued pretraining / EntiGraph (Stanford, ICLR 2025).**
- Le petit corpus est transformé en un grand corpus synthétique qui relie les entités entre elles, puis on continue le pré-entraînement dessus.
- La QA à livre fermé progresse régulièrement jusqu'à 455M tokens synthétiques, alors que le simple réentraînement ou les paraphrases plafonnent.
- Le gain **se cumule** avec le RAG.

[arXiv 2409.07431](https://arxiv.org/abs/2409.07431)

**Cartridges** (§2) : une forme d'« entraînement sur le corpus » ciblée sur le cache KV.

### Limites

- **Accès aux poids :** il n'y a pas d'accès aux poids de Claude. Le fine-tuning de Claude n'a été proposé que de façon limitée (historiquement Claude 3 Haiku sur Amazon Bedrock). *(Inférence : je n'ai pas vérifié l'offre actuelle ; c'est à confirmer avec Anthropic.)*
- **Versionnage :** le droit fiscal change à chaque loi de finances. Une connaissance « figée dans les poids » est **impossible à dater, à citer et à mettre à jour**. C'est le cas le plus défavorable identifié par FineTuneBench (19 % sur les mises à jour).
- **Hallucinations :** risque de fausses certitudes (Gekhman), incompatible avec l'exigence de citation exacte.

### Analyse (inférence)

- **Ne pas utiliser le fine-tuning pour injecter la connaissance fiscale.**
- Usages éventuels et secondaires : le style de rédaction, le format des notes d'analyse, la classification (type de relation entre articles), ou un petit modèle d'extraction de renvois pour construire le graphe. Tous ces usages relèvent de la *compétence*, pas de la *connaissance*.
- Claude connaît déjà, par pré-entraînement, une partie significative du droit fiscal français. Ce savoir est **non daté et non vérifiable**. Le système doit donc forcer l'ancrage textuel : pas d'affirmation normative sans citation d'un texte récupéré à la bonne date.

---

## 8. Formalisation du droit en code et détection de failles

### Faits sourcés

**Mlang / langage M (Inria et DGFiP).**
- Le calcul de l'impôt sur le revenu est écrit dans le **langage M**, un DSL interne de la DGFiP.
- Denis Merigoux et ses coauteurs ont rétro-ingénié sa sémantique et produit **Mlang**, un compilateur doté d'une sémantique formelle (CC 2021).
- En **2024**, pour la première fois, l'IR de tous les Français a été calculé avec du code compilé par Mlang.

[arXiv 2011.07966](https://arxiv.org/abs/2011.07966), [GitHub MLanguage/mlang](https://github.com/MLanguage/mlang), [Inria – Mlang](https://www.inria.fr/en/mlang-modernise-tax-calculations)

**Catala (Inria, Merigoux, Chataing et Protzenko, ICFP 2021).**
- C'est un langage fondé sur la **logique par défaut priorisée** (règle générale et exceptions, comme dans les textes).
- Il se pratique en programmation « littéraire » : le code est entrelacé avec le texte de loi.
- Le cœur du compilateur est prouvé en F*.
- Évalué sur la section 121 de l'IRC américain et sur les allocations familiales françaises. Ce travail a mis au jour **un bug dans l'implémentation officielle** des prestations familiales.

[arXiv 2103.03198](https://arxiv.org/abs/2103.03198), [ACM](https://dl.acm.org/doi/10.1145/3473582)

Réécriture de l'IR en Catala :
- depuis juin 2023, l'équipe réécrit l'algorithme de l'IR **à partir des seuls textes légaux**, avec l'objectif qu'il devienne le système officiel d'ici 5 à 6 ans ;
- des discussions sont en cours avec la CNAF ;
- Catala a reçu en 2026 un prix d'interdisciplinarité (CNRS / France Universités).

[Inria – Catala DGFiP/CNAF](https://www.inria.fr/en/catala-software-dgfip-cnaf), [merigoux.ovh](https://merigoux.ovh/)

**OpenFisca et LexImpact.**
- OpenFisca est un moteur libre de micro-simulation socio-fiscale (depuis 2011, France Stratégie et IDEP).
- Depuis 2020, **LexImpact** (Assemblée nationale) s'appuie sur OpenFisca pour permettre aux députés de simuler l'effet d'amendements sur le barème de l'IR.

[openfisca.org](https://openfisca.org/fr/), [leximpact.an.fr](https://leximpact.an.fr/), [Labo Société Numérique](https://labo.societenumerique.gouv.fr/fr/articles/openfisca-quand-un-commun-num%C3%A9rique-transforme-la-loi-en-code/)

**LLM → Catala.** Benchmark de traduction du droit fiscal en code Catala (NLLP 2025) : environ 88,8 % de code Catala syntaxiquement valide avec GPT-4.1 en few-shot sur du droit fiscal français (Lorenzo, Pietromatera et Holzenberger). La validité *sémantique* est un problème plus difficile. [ACL Anthology 2025.nllp-1.4](https://aclanthology.org/2025.nllp-1.4/)

**Détection d'incohérences et de failles.**
- **Yadamsuren, Platt et Diaz (2025, publié dans *AI and Law* en 2026).** Framework neuro-symbolique appliqué à la section 121 de l'IRC. GPT-4o seul ne détecte les incohérences que dans 1 stratégie sur 3. Une fois l'article formalisé en **Prolog** (avec l'aide de GPT-5), les interprétations concurrentes sont modélisées et une « zone d'incohérence » est détectée de façon **déterministe et reproductible**. [arXiv 2511.11954](https://arxiv.org/abs/2511.11954), [Springer](https://link.springer.com/article/10.1007/s10506-026-09525-6)
- **Fratrič, Holzenberger et Restrepo Amariles (2025), « Can AI expose tax loopholes? ».** Prototype hybride qui combine une interface en langage naturel et un **DSL de planification** pour exposer des schémas d'évitement. Démonstration sur cas d'étude. [arXiv 2503.17339](https://arxiv.org/abs/2503.17339)
- **Blair-Stanek, Holzenberger et Van Durme (AAAI 2026), « Can LLMs Identify Tax Abuse? ».** Les LLM interprètent, complètent et génèrent des stratégies de minimisation fiscale (droit américain). Le raisonnement du LLM a identifié une **stratégie entièrement nouvelle**. [arXiv 2508.20097](https://arxiv.org/abs/2508.20097)
- **Autres travaux :** combinaison LLM et solveurs SMT (Z3) pour la conformité financière (Hsia et al., 2025), et LM + programmes logiques pour un raisonnement fiscal fiable (Jurayj, Holzenberger et Van Durme, AAAI 2026). Ils sont cités dans les références des travaux ci-dessus ; je n'ai pas vérifié les articles eux-mêmes.
- Une étude de 2026 sur la **fidélité des LLM comme solveurs et autoformaliseurs** en raisonnement juridique met en garde contre les formalisations infidèles. [arXiv 2606.16118](https://arxiv.org/pdf/2606.16118)

### Limites

- **Coût de formalisation :** il est très élevé (des années-personnes pour l'IR en Catala). Il ne couvre que la partie **calculatoire** (assiette, barème, plafonds), pas les standards ouverts (abus de droit, acte anormal de gestion, « intérêt de l'entreprise »).
- **Fidélité de la formalisation :** si le LLM formalise mal, le solveur prouvera des choses fausses avec certitude. La validation humaine reste indispensable.
- **Zones grises :** beaucoup relèvent de l'**interprétation** (sens d'un terme, portée d'une doctrine) et non d'une contradiction logique. Un solveur ne les « voit » que si les interprétations concurrentes sont modélisées explicitement (approche Yadamsuren et al.).

### Analyse (inférence)

- La formalisation n'est pas une méthode de *gestion de la connaissance*. C'est une **méthode de vérification** : un « oracle » qui confirme ou infirme les hypothèses d'incohérence produites par le LLM.
- Stratégie pragmatique :
  1. le LLM repère une interaction suspecte entre régimes ;
  2. il formalise **localement** les articles concernés (Catala, Prolog ou Z3) avec leurs interprétations concurrentes ;
  3. le solveur cherche un contre-exemple (un contribuable fictif pour qui les règles se contredisent ou produisent un effet de bord : double exonération, cumul non voulu, effet de seuil) ;
  4. un fiscaliste humain valide.
- **Mlang et OpenFisca** peuvent servir d'**oracles de calcul** pour l'IR : on teste numériquement des cas limites générés par le LLM.

---

## 9. Synthèse : architecture hybride recommandée

> **Toute cette section est une inférence**, construite à partir des faits sourcés ci-dessus. Elle devra être validée par un banc d'évaluation interne.

### 9.1 Principes directeurs

1. **Séparer les rôles.** La *connaissance* vit dans un corpus canonique versionné, externe au modèle. La *navigation* passe par des index, un graphe et des outils. Le *raisonnement* se fait en long context sur des textes intégraux. La *vérification* repose sur des citations contrôlées et des solveurs.
2. **Déterministe d'abord, probabiliste ensuite.** Tout ce qui peut être calculé sans LLM doit l'être : versions en vigueur à une date, renvois explicites, identifiants. Le LLM découvre, compare et argumente (principe de SAT-Graph).
3. **Le long context est un espace de travail pour comparer**, pas un entrepôt.
4. **Aucune affirmation normative sans citation vérifiée** (texte, version, date).

### 9.2 Les couches

```
┌───────────────────────────────────────────────────────────────────────┐
│ 6. VÉRIFICATION : contrôle des citations (texte + version à la date)  │
│    + formalisation locale Catala/Prolog/Z3 + oracles Mlang/OpenFisca  │
├───────────────────────────────────────────────────────────────────────┤
│ 5. ORCHESTRATION : agent principal (Opus) + sous-agents à contexte    │
│    isolé (balayage, collecte) + agent « juge » en long context        │
│    + mémoire projet versionnée (conclusions, zones grises validées)   │
├───────────────────────────────────────────────────────────────────────┤
│ 4. NOYAU EN CACHE (~100-300k tokens, TTL 1 h) : méthode, plan         │
│    CGI/LPF/BOFiP, notions transversales, cartes des régimes           │
│    + « packs régime » chargés à la demande (100-400k tokens)          │
├───────────────────────────────────────────────────────────────────────┤
│ 3. OUTILS DE RECHERCHE (MCP) : get_article(id,date), list_section,    │
│    who_cites / cited_by, versions(id), search_lexical (BM25/grep),    │
│    search_semantic (repli), find_defined_term, bofip_for(article)     │
├───────────────────────────────────────────────────────────────────────┤
│ 2. GRAPHE JURIDIQUE TEMPOREL (descendant, déterministe) :             │
│    Work/Expression (versions datées), renvois explicites (parsing),   │
│    relations implicites extraites par LLM puis validées (définit,     │
│    déroge à, commente, interprète, s'applique au même fait générateur)│
├───────────────────────────────────────────────────────────────────────┤
│ 1. CORPUS CANONIQUE EN FICHIERS : LEGI/JORF (DILA), BOFiP, JADE/CASS  │
│    → 1 article = 1 fichier Markdown + frontmatter (LEGIARTI, ELI,     │
│    dates de vigueur, version, renvois) ; arborescence = plan officiel │
│    ; INDEX.md par nœud (style llms.txt) ; historique git              │
└───────────────────────────────────────────────────────────────────────┘
```

### 9.3 Flux type pour une question transversale

Exemple : « Interactions entre intégration fiscale, régime mère-fille et limitation des charges financières après la LF 2026 ».

1. **Cadrage.** Le noyau en cache fournit la carte. L'agent identifie les nœuds concernés via les `INDEX.md` et le graphe.
2. **Expansion par le graphe.** Récupérer les articles concernés *à la date visée*, leurs renvois sortants et entrants, les notions définies partagées, le BOFiP associé et la jurisprudence qui les interprète. Résultat : un sous-corpus de 150 à 400k tokens.
3. **Analyse en long context.** Textes intégraux en haut, question à la fin, balises XML par document, et consigne d'extraire les citations avant de raisonner. Si le sous-corpus est trop grand, on répartit entre des sous-agents par *paires de régimes*, pas par documents isolés.
4. **Production d'hypothèses.** L'agent produit des hypothèses structurées : incohérence, cumul, effet de seuil, zone grise. Pour chacune : les textes, les versions et le raisonnement.
5. **Vérification.** Chaque citation est vérifiée automatiquement. Les hypothèses calculatoires sont formalisées localement et testées au solveur ou à l'oracle.
6. **Mémorisation.** Les conclusions validées sont enregistrées dans la mémoire projet, avec leur date et leur statut.

### 9.4 Rôle retenu pour chaque approche

| Approche | Rôle | Justification (sourcée) | Principal risque |
|---|---|---|---|
| Long context 1M | Espace de travail pour comparer des textes intégraux | MRCR élevé des Claude récents ; « long docs en haut, question à la fin » | Context rot, distracteurs (Chroma, NoLiMa) |
| Prompt caching / CAG | Noyau stable et packs régime | Lecture en cache à 0,05× sur Opus 5.5 | Invalidation à chaque mise à jour ; pas de gain de qualité |
| Recherche agentique | Mode de navigation principal | Retour Claude Code ; LlamaIndex (petits corpus) | Rappel non garanti, latence, dégradation à grande échelle |
| Hiérarchie / skills / llms.txt | Cartes de navigation et savoir-faire méthodologique | Agent Skills, context engineering, RAPTOR, PageIndex | Résumés erronés, maintenance |
| Graphe temporel | Colonne vertébrale du raisonnement transversal | SAT-Graph (normes, temporalité) ; LEGI versionnée | Coût de construction, relations implicites manquées |
| Multi-agents + mémoire | Parallélisation et continuité entre sessions | +90,2 % en recherche (Anthropic) ; memory tool | ×15 tokens ; perte d'information aux résumés |
| Fine-tuning | Non utilisé pour la connaissance (éventuellement pour style ou extraction) | Ovadia, Gekhman, FineTuneBench | Hallucinations, impossible à dater |
| Formalisation / solveurs | Vérification des hypothèses calculatoires | Catala, Mlang, Yadamsuren et al., Blair-Stanek et al. | Coût, fidélité de la formalisation |
| RAG vectoriel | Outil de repli sémantique, pas le socle | LaRA : pas de solution miracle ; LlamaIndex : RAG meilleur à grande échelle | Chunks hors contexte, top-k aveugle |

### 9.5 Compromis principaux

- **Exhaustivité ou coût.** Chercher *toutes* les incohérences est combinatoire. Le graphe réduit l'espace des paires candidates, mais chaque vérification en long context coûte cher. Avec un noyau en cache, compter de quelques centimes à quelques dollars par hypothèse, et environ ×15 en multi-agents.
- **Précision ou rappel.** L'approche agentique et le graphe explicite sont précis, mais manquent les liens implicites. Le repli sémantique augmente le rappel au prix de distracteurs.
- **Fraîcheur ou stabilité du cache.** Les mises à jour fréquentes invalident le noyau. Il faut regrouper les mises à jour et séparer le noyau stable des nouveautés.
- **Déterminisme ou couverture.** La formalisation donne des preuves, mais sur un périmètre étroit. Le LLM couvre large, sans garantie.
- **Construction ou exploitation.** Le graphe temporel et les index représentent l'essentiel de l'effort d'ingénierie initial. Ensuite, l'exploitation est simple et auditable.

### 9.6 Priorités de mise en œuvre (proposition)

1. **Ingestion.** LEGI, BOFiP et jurisprudence vers des fichiers Markdown et un frontmatter, avec une arborescence officielle et les versions datées. C'est déterministe et ne demande pas de LLM.
2. **Graphe des renvois explicites et outils MCP.** `get_article(id, date)`, `cited_by` et `versions`.
3. **Banc d'évaluation interne.** 50 à 100 questions transversales rédigées par des fiscalistes, avec les réponses et les textes attendus. Mesurer le rappel des textes pertinents et la justesse des conclusions.
4. **Noyau en cache, `INDEX.md`, skills méthodologiques.**
5. **Relations implicites extraites par LLM**, puis validées par échantillonnage.
6. **Orchestration multi-agents** pour les balayages exhaustifs.
7. **Formalisation locale** (Catala ou Prolog) sur 2 ou 3 régimes pilotes à forte valeur.

---

## 10. Sources

### Long context
- Liu et al., *Lost in the Middle* — https://arxiv.org/abs/2307.03172
- RULER (NVIDIA) — https://arxiv.org/abs/2404.06654 ; https://github.com/NVIDIA/RULER
- NoLiMa (Adobe) — https://arxiv.org/abs/2502.05167 ; https://github.com/adobe-research/NoLiMa
- Chroma, *Context Rot* — https://www.trychroma.com/research/context-rot ; https://github.com/chroma-core/context-rot
- LongBench v2 — https://arxiv.org/abs/2412.15204 ; https://longbench2.github.io/
- LaRA — https://arxiv.org/abs/2502.09977
- Synthèse MRCR/Fiction.LiveBench 2026 (source secondaire) — https://yage.ai/share/long-context-benchmark-en-20260315.html
- Fiction.LiveBench — https://fiction.live/stories/Fiction-liveBench-Feb-21-2025/oQdzQvKHw8JyXbN87
- Anthropic, Context windows — https://platform.claude.com/docs/en/build-with-claude/context-windows
- Anthropic, Prompting best practices (long context) — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### CAG et cache
- Chan et al., *Don't Do RAG* — https://arxiv.org/abs/2412.15605 ; https://github.com/hhhuang/CAG
- Cartridges — https://arxiv.org/abs/2506.06266 ; https://github.com/HazyResearch/cartridges
- Anthropic, Prompt caching — https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Anthropic, Pricing — https://platform.claude.com/docs/en/about-claude/pricing

### Recherche agentique et divulgation progressive
- Anthropic, *Effective context engineering for AI agents* — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Boris Cherny (X) — https://x.com/bcherny/status/2017824286489383315
- LlamaIndex, *Did filesystem tools kill vector search?* — https://www.llamaindex.ai/blog/did-filesystem-tools-kill-vector-search
- PageIndex — https://github.com/VectifyAI/PageIndex
- Anthropic, Agent Skills — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills ; https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- llms.txt — https://llmstxt.org/
- RAPTOR — https://arxiv.org/abs/2401.18059

### Graphes et ontologies
- Microsoft LazyGraphRAG — https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- Microsoft GraphRAG dynamic community selection — https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/
- LightRAG — https://arxiv.org/abs/2410.05779 ; https://github.com/hkuds/lightrag
- SAT-Graph RAG — https://arxiv.org/abs/2505.00039
- LegalGraphRAG — https://arxiv.org/abs/2605.28120
- Citation grounding / graph coverage — https://arxiv.org/pdf/2606.00898
- ELI — https://en.wikipedia.org/wiki/European_Legislation_Identifier ; mapping ELI/AKN : https://dl.acm.org/doi/10.1145/3614321.3614327
- LEGI (DILA) — https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides ; https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api

### Mémoire et multi-agents
- Anthropic, Context management (memory tool, context editing) — https://claude.com/blog/context-management
- Anthropic, Memory tool — https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Anthropic, *How we built our multi-agent research system* — https://www.anthropic.com/engineering/multi-agent-research-system

### Fine-tuning
- Ovadia et al. — https://arxiv.org/abs/2312.05934
- Gekhman et al. — https://arxiv.org/abs/2405.05904
- FineTuneBench — https://arxiv.org/abs/2411.05059
- Synthetic continued pretraining (EntiGraph) — https://arxiv.org/abs/2409.07431

### Formalisation du droit
- Mlang (CC 2021) — https://arxiv.org/abs/2011.07966 ; https://github.com/MLanguage/mlang ; https://www.inria.fr/en/mlang-modernise-tax-calculations
- Catala (ICFP 2021) — https://arxiv.org/abs/2103.03198 ; https://www.inria.fr/en/catala-software-dgfip-cnaf
- OpenFisca — https://openfisca.org/fr/ ; LexImpact : https://leximpact.an.fr/
- *Translating Tax Law to Code with LLMs* (NLLP 2025) — https://aclanthology.org/2025.nllp-1.4/
- Yadamsuren et al., inconsistency detection IRC — https://arxiv.org/abs/2511.11954 ; https://link.springer.com/article/10.1007/s10506-026-09525-6
- Fratrič et al., *Can AI expose tax loopholes?* — https://arxiv.org/abs/2503.17339
- Blair-Stanek et al., *Can LLMs Identify Tax Abuse?* — https://arxiv.org/abs/2508.20097
- Fidélité des LLM comme autoformaliseurs juridiques — https://arxiv.org/pdf/2606.16118
