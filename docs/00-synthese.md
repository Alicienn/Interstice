# Interstice — Synthèse de la recherche et proposition d'architecture

*27/09/2026 — basé sur `recherche/01`, `02`, `03`. Les chiffres viennent de ces notes (voir leurs sources) ; l'architecture est une proposition.*

## 1. Les 5 constats qui dimensionnent le projet

1. **Le corpus ne tient pas dans 1M tokens.** CGI + annexes (en vigueur) ≈ 1,5–1,8M, LPF ≈ 0,2M, CIBS ≈ 0,2–0,4M, BOFiP ≈ 19M, CGI toutes versions ≈ 20M, jurisprudence fiscale CE sur 20 ans ≈ 30M (estimé). Le « noyau » des codes fait déjà ~2M.
2. **Et même si ça tenait, ce serait une mauvaise idée** : la qualité se dégrade fortement avec la longueur de contexte (NoLiMa, Chroma « context rot »). Le 1M sert à *confronter* des textes choisis, pas à *stocker* le corpus.
3. **Le temps est le piège n°1.** Sur FiscalQA Pro (CGI versionné), RAG naïf : 2,7 % sur les questions temporelles vs 98,3 % pour une recherche version-aware. → Chaque article doit porter ses versions datées.
4. **Les LLM valident trop facilement.** Étude Johns Hopkins 2025 : Claude-4 juge viables 20/36 stratégies piégées. → Il faut un agent contradicteur + une vérification formelle quand c'est possible (solveur/Catala), pas un LLM seul.
5. **Personne ne fait la détection de zones grises** : Doctrine, GenIA-L, Lexis+, Blue J… font de la recherche sourcée, pas de l'analyse structurelle du texte ni de qualification abus/fraude.

## 2. Périmètre du corpus

| Niveau | Contenu | Volume | Usage |
|---|---|---|---|
| **A. Noyau en cache** | Cartes hiérarchiques annotées (plans CGI/LPF/CIBS/BOFiP), Voies et moyens t. II (liste chiffrée des niches), textes anti-abus (L64, L64 A, 205 A, 1729, 1741…), grille de qualification, taxonomie Z1–Z12 | 200–400k | Toujours présent, prompt caching |
| **B. Corpus navigable** | CGI + annexes, LPF, CIBS, Code des douanes, parties fiscales CSS/CGCT/urbanisme — **un fichier par article, toutes versions depuis ~2010** ; BOFiP en vigueur + archive de ses flux | ~40M | Outils de l'agent (`get_article(id, date)`, `cited_by`, `versions`…) |
| **C. Jurisprudence** | CE + CAA fiscal (open data exhaustif depuis 2021-22, sélection avant), Cass. com. (enregistrement, IFI, douane), QPC fiscales, CJUE fiscal, avis du CADF, conventions fiscales | ~30–40M | Indexée par article cité → rattachée au graphe |
| **Exclu** | Jugements de TA (masse, peu de valeur), versions antérieures à ~2010, droit non fiscal (sauf articles du Code civil/commerce atteints via les renvois du graphe), noms/adresses résiduels dans les décisions | — | — |

**À faire tout de suite :** archiver les flux BOFiP hebdomadaires — l'open data ne conserve pas l'historique, chaque semaine non archivée est perdue.

## 3. Architecture proposée (sans RAG vectoriel en première ligne)

```
                 ┌─────────────────────────────────────────┐
  Question  ───► │ Orchestrateur (Claude, contexte long)    │
  ou scan        │  noyau A en cache + mémoire de projet    │
                 └──────┬──────────────────────┬────────────┘
                        │ outils                │ sous-agents (balayages parallèles)
          ┌─────────────▼─────────┐   ┌─────────▼────────────────┐
          │ Graphe juridique      │   │ Détecteurs Z1…Z12        │
          │ temporel (articles,   │   │ par chapitre du CGI      │
          │ versions, renvois,    │   └─────────┬────────────────┘
          │ doctrine, décisions)  │             │ hypothèses
          └─────────────┬─────────┘   ┌─────────▼────────────────┐
                        │             │ Contradicteur (attaque)   │
          ┌─────────────▼─────────┐   │ + vérif. formelle (Z3 /   │
          │ Corpus fichiers       │   │   Catala) si calculable   │
          │ (1 article = 1 fichier│   └─────────┬────────────────┘
          │  + métadonnées LEGI)  │             │
          └───────────────────────┘   ┌─────────▼────────────────┐
                                      │ Qualification + citations │
                                      │ vérifiées → rapport       │
                                      └───────────────────────────┘
```

- **Graphe déterministe** construit depuis la structure LEGI (renvois explicites, liens de modification, dates de vigueur), enrichi ensuite de relations extraites par LLM *et validées*. Pas de GraphRAG/LightRAG (non versionnés, non déterministes).
- **Recherche agentique** : l'agent navigue via des outils spécialisés ; un index vectoriel ne sert qu'en repli (formulations libres).
- **Balayage parallèle, croisement centralisé** : les sous-agents scannent, mais la confrontation finale se fait dans un seul contexte long (les tâches très interdépendantes se parallélisent mal).
- **Pas de fine-tuning** pour la connaissance : non datable, non citable, plus d'hallucinations.

## 4. Grille de qualification de chaque piste

🟢 optimisation sûre · 🟡 sûre sous conditions · 🟠 risque L64 A (but principalement fiscal) · 🟠 risque L64 / 205 A · 🔴 fraude (1741) — plus un drapeau **DAC 6** et un critère séparé de **détectabilité** (le datamining DGFiP repère surtout les anomalies déclaratives, pas les montages). Arbre de décision détaillé : `recherche/03`, à calibrer sur les avis du CADF.

## 5. Premières étapes proposées

1. **Ingestion LEGI** → fichiers articles versionnés + graphe des renvois (partir de legi.py ou du XML DILA directement).
2. **Archiveur BOFiP** (tâche planifiée hebdomadaire).
3. **Carte des niches** : parser Voies et moyens t. II → plusieurs centaines de dépenses fiscales chiffrées, reliées à leurs articles. C'est un point d'entrée naturel pour la chasse aux zones grises.
4. **Banc d'évaluation** : 30–50 questions transversales avec réponse connue (dont des zones grises déjà tranchées par le CE ou le CADF) — aucun benchmark public ne mesure ça.
5. **Pilote sur un domaine** (ex. plus-values mobilières / apport-cession 150-0 B ter, très riche en contentieux) avant d'étendre.

## 6. Points de vigilance

- Tokens mesurés avec le tokenizer o200k : recompter avec `count_tokens` de Claude (+20–35 % probable).
- Toujours remonter aux sources primaires (un blog d'avocat présente l'arrêt Aubépar à l'envers).
- Usage commercial : art. 1740 A bis CGI, délit de facilitation de la fraude, monopole de la consultation juridique → avis d'avocat avant de proposer des montages à des tiers.
