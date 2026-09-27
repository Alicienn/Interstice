# 03 — IA appliquée à l'analyse du droit fiscal : état de l'art 2024-2026 et cadre juridique optimisation / abus / fraude

> Projet Interstice : IA spécialisée en droit fiscal français, pour détecter les zones grises, ambiguïtés, incohérences et effets de bord de la législation (optimisation légale, dépenses fiscales / niches).
> Recherche web réalisée le 27/09/2026.

**Conventions de lecture**
- **[F]** : fait sourcé (source primaire, ou source secondaire nommée comme telle).
- **[F-sec]** : fait rapporté par une source secondaire (presse, blog d'avocat, comparatif). À recouper avant de s'en servir.
- **[I]** : inférence, analyse ou recommandation de l'auteur de cette note. Ce n'est pas un fait établi.
- **[À vérifier]** : point plausible, mais non confirmé pendant cette recherche.

---

## Sommaire

0. [Synthèse](#0-synthèse)
1. [Recherche académique](#1-recherche-académique)
2. [Produits existants et évaluations publiées](#2-produits-existants-et-évaluations-publiées)
3. [Usage de l'IA par la DGFiP](#3-usage-de-lia-par-la-dgfip)
4. [Cadre juridique : optimisation, abus de droit, fraude](#4-cadre-juridique--optimisation-abus-de-droit-fraude)
5. [Méthodologie des praticiens et taxonomie des zones grises](#5-méthodologie-des-praticiens-et-taxonomie-des-zones-grises)
6. [Grille de qualification automatique vert / orange / rouge](#6-grille-de-qualification-automatique-vert--orange--rouge)
7. [Implications pour l'architecture du projet](#7-implications-pour-larchitecture-du-projet)
8. [Sources](#8-sources)

---

## 0. Synthèse

1. **[F]** La recherche 2024-2026 sur les « failles fiscales » par LLM est surtout américaine. Elle vient principalement du groupe Johns Hopkins (Blair-Stanek, Holzenberger, Van Durme) et du MIT ALFA (O'Reilly, Hemberg). Les LLM de pointe vérifient bien une stratégie fiscale quand on leur fournit l'analyse. Ils détectent mal les stratégies viciées : Claude-4 a jugé viables 20 des 36 variantes piégées. Ils génèrent mal des stratégies ex nihilo : 18 à 31 % seulement obtiennent la note maximale. Un modèle (o1-preview) a toutefois produit une stratégie jugée **inédite** par des experts, qui l'ont signalée à l'IRS.
2. **[F]** Les approches **neuro-symboliques** donnent de meilleurs résultats que le LLM seul pour détecter une incohérence (LLM qui traduit le texte en Prolog ou en logique formelle, puis solveur déterministe). Sur l'IRC §121, le prompting seul détecte 33 % des incohérences, alors que Prolog les détecte de façon déterministe. De même, LLM + programmes logiques atteignent 86/100 sur SARA. La lignée française **Catala / Mlang (Inria, Merigoux)** a montré par solveur SMT qu'il existe des foyers dont le taux marginal effectif dépasse 100 % (effet de seuil), et Catala a trouvé un bug réel dans le logiciel de la CNAF.
3. **[F]** Il existe un benchmark **droit fiscal français** directement pertinent : *FiscalQA Pro* (ICML 2026 workshop), qui contient 32 436 versions d'articles du CGI de 1938 à 2031. Le RAG « statique » y obtient **2,7 %** d'exactitude sur les questions temporelles. Un retriever multi-versions atteint 98,3 %. **La gestion des versions dans le temps est le premier chantier technique.**
4. **[F]** Les outils commerciaux (Doctrine+Predictice, GenIA-L, Lexis+ with Protégé, Wisetax, FiscoGPT, Blue J, CoCounsel Tax) font de la **recherche documentaire sourcée et de la rédaction**. Aucun ne revendique publiquement la détection systématique de zones grises législatives ni la qualification abus / fraude **[I : sur la base de leurs pages produit]**. L'étude Stanford (2024) mesure 17 à 33 % d'hallucinations dans les outils juridiques RAG, alors que les éditeurs promettaient d'y avoir mis fin.
5. **[F]** Pour la DGFiP, en 2025, 52 % des dossiers professionnels et plus de 54 % des dossiers particuliers clôturés ont été orientés par le datamining, qui a rapporté 2,8 Md€. La Cour des comptes (déc. 2025) nuance : en 2023, ces contrôles représentaient 44 % des contrôles mais seulement 13,8 % des droits et pénalités. Ce que l'algorithme détecte bien, ce sont les **anomalies déclaratives** (réductions Pinel mal reportées : 93 % de pertinence), pas les montages.
6. **[F]** Le cadre de qualification repose sur plusieurs niveaux. L'abus de droit de l'art. L64 LPF exige un but exclusivement fiscal (majoration de 80 %). Le « mini-abus » de l'art. L64 A exige un motif principalement fiscal, ne s'applique pas à l'IS et n'entraîne pas de majoration automatique. La clause anti-abus IS de l'art. 205 A CGI vise les montages non authentiques. Le rescrit de l'art. L64 B vaut accord tacite après 6 mois de silence. DAC 6 impose une déclaration. Les majorations de l'art. 1729 CGI sont de 40 % ou 80 %. La fraude pénale (art. 1741 CGI) est punie de 5 ans et 500 k€, et de 7 ans et 3 M€ si aggravée. La dénonciation au parquet est automatique au-delà de 100 k€ de droits (art. L228 LPF). En 2024, le CADF a donné raison à l'administration dans 92 % des cas. En 2025, seulement dans 13 cas sur 30.
7. **[I]** Pour le projet, l'architecture recommandée est la suivante :
   - un corpus versionné dans le temps (CGI, LPF, BOFiP, jurisprudence, travaux parlementaires) ;
   - une formalisation partielle des règles (Catala ou Prolog) pour détecter mécaniquement les effets de seuil et les contradictions ;
   - un duo d'agents générateur / attaquant, calé sur la jurisprudence du CADF et du Conseil d'État ;
   - une grille de qualification à cinq niveaux (vert, jaune, orange clair, orange foncé, rouge) plus un drapeau DAC 6 ;
   - une barrière « contradiction / abstention » ;
   - une revue humaine obligatoire.

---

## 1. Recherche académique

### 1.1 Les LLM peuvent-ils trouver des failles fiscales ?

| Travail | Auteurs / date | Méthode | Résultats clés | URL |
|---|---|---|---|---|
| **Can LLMs Identify Tax Abuse?** | Blair-Stanek, Holzenberger, Van Durme — arXiv 2508.20097, août 2025 | Jeu de données *Shelter Check* : 36 stratégies de minimisation fiscale US tirées de dossiers IRS et de décisions de justice (9 à 40 h d'expert par stratégie). Chaque stratégie comporte ses sources, les faits, l'objectif, les étapes, l'analyse et une **variante piégée**. Tâches testées : vérifier l'analyse, vérifier l'objectif, repérer l'étape viciée, compléter une étape manquante, générer une stratégie ex nihilo. Modèles : o3, Claude-4, Gemini-2.5 (et o1-preview et Claude-3.5 pour la génération). | [F] Avec l'analyse fournie, o3 et Claude-4 valident 36/36 stratégies. **Détection des variantes piégées faible** : Claude-4 juge viables 20/36 stratégies vouées à l'échec. Génération ex nihilo : 18 à 31 % seulement notées au maximum. o1-preview a produit une stratégie **inédite**, vérifiée par des experts et **signalée à l'IRS** : elle utilise les périodes comptables des *common trust funds* pour contourner les restrictions sur les pertes de *straddles*. Les modèles notent mal les stratégies des autres modèles (Spearman 0,30 à 0,48 par rapport aux experts). Seules 5 stratégies sont publiées, pour éviter la contamination. | https://arxiv.org/abs/2508.20097 — code : https://github.com/BlairStanek/LLM-Tax-Abuse |
| **Can AI Expose Tax Loopholes? Towards a New Generation of Legal Policy Assistants** | Fratrič, Holzenberger, Restrepo Amariles — arXiv 2503.17339, mars 2025 | Système hybride : interface en langage naturel et **langage dédié de planification**. Des séquences d'opérations sont cherchées pour atteindre un résultat fiscal. | [F] Prototype pour identifier systématiquement des schémas d'évitement fiscal. Les failles naissent de réglementations mal alignées (au niveau national et international) ou du détournement d'incitations bien intentionnées. | https://arxiv.org/abs/2503.17339 |
| **A Hybrid LLM-Coevolution Framework to Generate Abusive Tax Strategies** | Bhattacharya, Hemberg, O'Reilly (MIT ALFA) — EuroGP 2026 | **Coévolution compétitive** : une population de stratégies évolue vers l'abus et la dissimulation, face à une population de **motifs d'audit** qui cherche à les exposer. Le LLM représente stratégies et motifs en langue naturelle, fait l'appariement par similarité et mute les individus. | [F] Démontré sur le schéma iBOB (*Installment Bogus Optional Basis*), dont il génère des variantes. Les opérateurs génétiques compensent la connaissance superficielle du LLM, et le LLM évite l'encodage manuel des règles. | https://link.springer.com/chapter/10.1007/978-3-032-23005-8_8 |
| **Evolutionary Computation for Tax-Minimizing Strategies in Special Economic Zones** | Leguizamon, Sanchez, Ocampo, O'Reilly, Hemberg — GECCO 2026 | Algorithmes génétiques appliqués aux incitations des zones économiques spéciales | [F] Génération de stratégies de minimisation dans des régimes incitatifs. Ce sont des **dépenses fiscales**, au sens de notre projet. | https://doi.org/10.1145/3795095.3805115 |
| **Tax non-compliance detection using co-evolution of tax evasion risk and audit likelihood** | Hemberg, O'Reilly et al. — ICAIL 2015 | Précurseur : coévolution fraude / audit | [F] Base de la lignée MIT | https://dl.acm.org/doi/10.1145/2746090.2746099 |
| **Language Models Identify Ambiguities and Exploit Loopholes** | Choi, Bansal, Stengel-Eskin — EMNLP 2025 (arXiv 2508.19546) | Scénarios où le LLM reçoit un objectif en conflit avec une instruction ambiguë de l'utilisateur (implicature scalaire, ambiguïté structurelle, rapports de pouvoir). Des cas fiscaux sont inclus. | [F] Les modèles fermés et les modèles ouverts puissants **identifient l'ambiguïté et l'exploitent** pour servir leur propre objectif, en raisonnant explicitement sur l'ambiguïté. Les auteurs y voient un risque de sûreté de l'IA. | https://arxiv.org/abs/2508.19546 |
| **Investigating Tax Evasion Emergence Using Dual LLM and Deep RL** | Lazebnik, Shami — arXiv 2501.18177 (2025) | Simulation multi-agents LLM + apprentissage par renforcement profond | [F] L'efficacité des biens publics et la robustesse du contrôle sont complémentaires. Aucune des deux ne suffit seule à contenir l'évasion. | https://arxiv.org/abs/2501.18177 |

**[I]** Enseignements pour Interstice :
- Le schéma **générateur contre attaquant** existe dans la littérature, mais sous forme évolutionnaire (MIT) plutôt que sous forme de débat entre agents LLM. Rien de publié ne traite spécifiquement d'agents LLM adversariaux pour la fiscalité. Une recherche sur « multi-agent adversarial tax » ne ramène que des travaux génériques de *red teaming*. **C'est une niche ouverte.**
- Le point faible documenté des LLM est la **détection de ce qui ne marche pas**. Or c'est exactement le rôle de l'agent attaquant. Il faut donc outiller cet attaquant par une vérification formelle et par la jurisprudence, et pas seulement par du prompting.
- Il y a un enjeu **de double usage**. Blair-Stanek et al. ont signalé leur découverte à l'IRS. Choi et al. montrent que les LLM exploitent spontanément les ambiguïtés. Le projet a besoin d'une politique de divulgation, par exemple un signalement au législateur ou à la DLF pour les failles « rouges ».

### 1.2 Raisonnement statutaire et benchmarks

| Ressource | Contenu | Résultats notables | URL |
|---|---|---|---|
| **SARA** (*StAtutory Reasoning Assessment*) — Holzenberger, Blair-Stanek, Van Durme, 2020 | [F] 9 sections du code fédéral US (légèrement éditées pour être autonomes et sans ambiguïté), 376 cas faits à la main, dont 100 avec calcul de l'impôt dû | [F] Utilisé au lancement de GPT-4. D'après Tax Notes, GPT-4 calculait l'impôt exactement dans environ un tiers des cas et se trompait de plus de 10 % dans environ un quart des cas. | https://arxiv.org/abs/2005.05257 ; https://www.taxnotes.com/featured-analysis/openai-cribbed-our-tax-example-can-gpt-4-really-do-tax/2023/08/11/7h0hc |
| **Language Models and Logic Programs for Trustworthy Tax Reasoning** — Jurayj, Holzenberger, Van Durme, AAAI 2026 | [F] Le LLM traduit la loi en programme logique, avec des exemples récupérés et une auto-cohérence, puis un solveur symbolique calcule. | [F] 86/100 sur SARA (secondaire : PaperNotes). Les auteurs proposent aussi un cadre d'évaluation **par le coût des erreurs** (pénalités réelles). | https://arxiv.org/abs/2508.21051 ; https://ojs.aaai.org/index.php/AAAI/article/download/41212/45173 |
| **Solving versus Verifying: Catching Contradictions in Tax Reasoning Systems** — Sadowski, Chudziak, ICTAI 2026 (arXiv 2609.05928) | [F] Cas SARA perturbés : faits manquants ou contradictoires | [F] Plus de 90 % d'exactitude sur les cas propres. Mais les meilleurs modèles **calculent sans signaler la contradiction dans 63 à 76 % des cas**. Interrogés en mode « vérification », ils détectent la plupart des contradictions. Une « **contradiction gate** » (appel de vérification préalable, avec abstention) récupère l'essentiel des détections manquées, pour un coût d'environ 5 points sur les cas propres. | https://arxiv.org/abs/2609.05928 |
| **LLM-Assisted Formalization Enables Deterministic Detection of Statutory Inconsistency in the IRC** — Yadamsuren, Platt, Diaz, nov. 2025 (Springer *AI & Law* 2026) | [F] GPT-4o et GPT-5 traduisent l'IRC §121 en Prolog | [F] Le prompting seul détecte 33 % des incohérences. Le prompting augmenté par Prolog couvre moins de règles (66 %). Le **Prolog pur** identifie de façon déterministe et reproductible une « zone d'incohérence » du §121. | https://arxiv.org/abs/2511.11954 ; https://link.springer.com/article/10.1007/s10506-026-09525-6 |
| **LegalBench** — Guha et al., 2023 | [F] 162 tâches de raisonnement juridique (repérage des questions, rappel et application des règles, interprétation), dont des tâches dérivées de SARA | Référence générique | https://github.com/HazyResearch/legalbench/ |
| **TaxCalcBench** (Column Tax) — v2 en juin 2026 | [F] Calcul de déclarations US (fédérales et d'État) à partir de pièces PDF | [F-sec] Le meilleur modèle n'atteint qu'environ 30 % de stricte exactitude | https://github.com/column-tax/tax-calc-bench |
| **Temporal Misgrounding in Legal RAG: A Versioned-Corpus Benchmark for French Tax Law** — Cymbler, Guez, Fabre, ICML 2026 Workshop AI for Law (arXiv 2608.09393) | [F] **FiscalQA Pro** : CGI versionné (32 436 versions d'articles, 1938-2031), 209 questions validées par des experts sur 33 articles, et 69 208 liens de citation vers la jurisprudence | [F] Aucun modèle ne retrouve la bonne version en « livre fermé ». RAG statique : **2,7 %** d'exactitude, et **0 %** de récupération de la version applicable, alors qu'il cite des articles réels mais périmés. Retriever multi-versions : **98,3 %**. | https://arxiv.org/abs/2608.09393 |
| **TaxPraBen** (fiscalité chinoise) — 2026 | [F] Benchmark de pratique fiscale réelle | Utile comme modèle de conception | https://arxiv.org/pdf/2604.08948 |
| **Large Legal Fictions** — Dahl, Magesh, Suzgun, Ho, 2024 | [F] Hallucinations de LLM généralistes sur des questions vérifiables de jurisprudence fédérale US : entre 58 % et 88 % selon le modèle | Référence pour le niveau de base d'un LLM sans RAG | https://arxiv.org/abs/2401.01301 |

### 1.3 Méthodes formelles : Catala, Mlang, SMT

- **[F] Mlang / langage M (DGFiP)**. La DGFiP calcule l'impôt sur le revenu dans un langage dédié, le « M ». Merigoux, Monat et Protzenko en ont donné une sémantique formelle et un compilateur (Mlang, CC 2021), et ont encodé le calcul dans le **solveur SMT Z3**. Ils ont cherché s'il existait un foyer au **taux marginal effectif supérieur à 100 %**. Le solveur a répondu oui et produit un contre-exemple : un couple pour qui +40 €/mois de salaire entraîne une perte nette de 60 €/mois, à cause d'un effet de seuil sur les bourses de lycée. Limites relevées par l'auteur : plus de 100 Go de RAM et plusieurs jours de calcul, un code M publié incomplet, et la question « qu'est-ce qui est acceptable ? » qui reste politique.
  - https://arxiv.org/pdf/2011.07966 ; https://dl.acm.org/doi/10.1145/3446804.3446850 ; https://blog.merigoux.ovh/en/2019/12/20/taxes-formal-proofs.html ; https://github.com/MLanguage/mlang ; code M : https://github.com/etalab/calculette-impots-m-source-code
- **[F] Catala** (Merigoux, Chataing, Protzenko, ICFP 2021). Ce langage suit la structure « règle générale + exceptions » des textes et se programme de façon littéraire, article par article. Il a révélé un **bug réel dans le logiciel des allocations familiales de la CNAF**. Une preuve de concept de recodage du calcul IR (M → Catala) est en cours avec la DGFiP. Catala a reçu en 2026 le prix d'interdisciplinarité scientifique (CNRS, France Universités, Collège des sociétés savantes).
  - https://arxiv.org/pdf/2103.03198 ; https://www.inria.fr/en/catala-software-dgfip-cnaf ; https://scholar.smu.edu/cgi/viewcontent.cgi?article=4932&context=smulr
- **[F] CUTECat** (exécution concolique pour Catala, 2025). Il génère des centaines de milliers de cas de test couvrant **toutes les branches** de l'aide au logement française et de l'IRC §132. **[I]** C'est directement utilisable pour repérer les branches mortes, les cas non prévus et les combinaisons de conditions contre-intuitives. https://link.springer.com/chapter/10.1007/978-3-031-91121-7_2
- **[F] « Closing the Loop: Formally Verified Law as a Reward Signal for Self-Improving Legal AI »** (Heydari, Leowald, avril 2026). Architecture « **le LLM propose, le vérificateur dispose** » : le LLM autoformalise dans un calcul juridique qui étend Catala, un noyau de vérification contrôle, et les explications sont tirées des traces de preuve. Les auteurs proposent un apprentissage par renforcement à partir des retours du vérificateur (RLVF). https://arxiv.org/pdf/2606.23913
- **[F] OpenFisca / LexImpact**. OpenFisca est un moteur libre de micro-simulation socio-fiscale, créé en 2011 chez France Stratégie. LexImpact (Assemblée nationale) l'utilise pour simuler les réformes. **[I]** Il sert d'oracle de calcul pour balayer les effets de seuil (gradients de revenu net en fonction du revenu brut). https://leximpact.an.fr/ ; https://fr.openfisca.org/showcase/leximpact/

**[I] Synthèse méthodologique.** Trois familles sont complémentaires :
1. le **LLM seul**, qui sert à lire, trouver des candidats et rédiger ;
2. le **LLM + formalisation** (Prolog, Catala, SMT), qui prouve l'existence d'un effet de seuil ou d'une contradiction, et fournit un contre-exemple concret ;
3. la **recherche adversariale** (coévolution ou agents), qui explore les combinaisons d'opérations.

Seule la famille 2 fournit des garanties. Elle est limitée aux parties calculables du droit (assiette, taux, seuils, conditions). Les notions à « texture ouverte » (but exclusivement fiscal, substance économique, intention libérale) restent du ressort d'un jugement, que l'on outille avec la jurisprudence.

---

## 2. Produits existants et évaluations publiées

### 2.1 Legaltech françaises et éditeurs

| Produit | Ce qu'il fait (déclaré) | Ce qu'il ne fait pas / limites observées | URL |
|---|---|---|---|
| **Doctrine** (avec **Predictice**, racheté le 17/09/2025) | [F-sec] Recherche dans les sources primaires, « Le Fiscal by Doctrine » (encyclopédie fiscale propre, dont un 3e volet contrôle / recouvrement / contentieux), résumés, chatbots, dont un sur la fiscalité internationale. Predictice apporte environ 60 M de décisions et l'analyse statistique des contentieux. 25 000 clients revendiqués. | [I] Aucune fonction publique de détection de zones grises législatives ni de qualification abus / fraude | https://www.doctrine.fr/solutions/fiscalite ; https://doctrine.pr.co/254391-doctrine-annonce-l-acquisition-de-predictice-et-assoit-sa-place-de-leader-europeen-de-l-ia-juridique/ ; https://www.maddyness.com/2025/09/17/doctrine-absorbe-son-rival-francais-predictice/ |
| **GenIA-L** (Lefebvre Dalloz) | [F-sec] IA fondée sur le fonds éditorial propriétaire, mis à jour chaque jour (5,4 M de décisions). Questions en langue naturelle, synthèses, « points de vigilance », rédaction (notes, clauses), analyse de conformité clause par clause, lecture de fichiers Excel. Hébergement UE. | [I] « Points de vigilance » = alertes sur une question posée, pas un audit systématique du texte | https://www.lefebvre-dalloz.fr/genia-l/ ; https://www.cnews.fr/shopping-high-tech/2025-12-08/genial-lefebvre-dalloz-liberer-temps-valoriser-expertise-securiser-pratique |
| **Lexis+ AI → « Lexis+ with Protégé »** (LexisNexis France) | [F-sec] Lexis+ remplace Lexis 360 Intelligence (lancé en avril 2025). Lexis+ AI est une option payante. Protégé (assistant personnalisé) arrive fin 2025. Renommage en février 2026. | Même logique de recherche et de rédaction | https://www.lexisnexis.com/blogs/fr-juridique/b/actualite/posts/lancement-lexis-plus-ai-france ; https://www.lexisnexis.com/community/pressroom/b/news/posts/lexisnexis-launches-protege-in-france-lexisnexis-launches-protege-in-france-the-next-generation-personalized-legal-ai-assistant-transforming-legal-practice |
| **Wisetax** (Marseille) | [F] IA pour fiscalistes : recherche sourcée (CGI, BOFiP, jurisprudence, conventions), simulateurs (plus-values…), documents du cabinet, livrables en marque blanche | [F] Aucune mention d'analyse des limites optimisation / abus | https://wisetax.fr/avocat-fiscaliste/ |
| **FiscoGPT** | [F-sec] Réponses sourcées CGI, BOFiP et jurisprudence, avec dates de mise à jour, pour experts-comptables et avocats | Idem | https://fiscogpt.fr/ |
| **Fiscal Expert France** | [F-sec] Analyse simultanée CGI, BOFiP, LPF et rescrits, loi de finances 2026 intégrée | Idem | https://fiscalexpertfrance.fr/ |
| **Fiscaly.ai** (néobanque Colbr, nov. 2025) | [F-sec] Pour les particuliers, gratuit : analyse l'avis ou la déclaration et **recommande des actions d'optimisation** | [I] Optimisation « catalogue » des niches existantes, pas de détection de failles | https://www.fiscaly.ai/ ; https://www.maddyness.com/2025/11/05/fiscaly-ai-ce-chatgpt-francais-pour-reduire-ses-impots/ |
| **Navaltech** | **Aucun résultat trouvé** sous ce nom. Nom à vérifier : il s'agit peut-être d'un autre acteur. | — | — |
| **« FiscalGPT »** | **Pas trouvé sous ce nom exact**. Équivalents : FiscoGPT, Fiscal Expert France, un GPT « Expert Fiscal France » sur ChatGPT. | — | https://chatgpt.com/g/g-rJgl8gqLu-expert-fiscal-france |
| **Connecteur MCP BOFiP** | [F] Il existe un connecteur MCP « BOFiP — Doctrine fiscale française » | [I] Brique d'ingestion possible, fiabilité à évaluer | https://glama.ai/mcp/connectors/dev.bofip/bofip |

Panorama et comparatifs (sources secondaires, souvent commerciales, à manier avec prudence) : https://zevra.tech/blog/comparatif-ia-juridiques ; https://www.alphadeep.fr/guides/comparatif-ia-juridique-france-2026 ; https://meta-doctrinal.org/centre-de-ressources/quelle-ia-juridique-choisir ; https://www.juriconnexion.fr/synthese-ia-2025-editeurs-et-legaltechs-rencontre-avec-juriconnexion/

### 2.2 Outils fiscaux spécialisés internationaux

| Produit | Ce qu'il fait | Chiffres / évaluations | URL |
|---|---|---|---|
| **Blue J** (Canada / US) | [F-sec] « Ask Blue J » : recherche fiscale générative avec citations (intégration Tax Notes). « Blue J Tax » : **prédiction de l'issue d'un litige** (tribunaux ou IRS) à partir de la jurisprudence. | [F-sec] Précision prédictive de 85-90 % selon l'éditeur. Plus de 4 000 organisations clientes (KPMG UK, Crowe, Agence du revenu du Canada). Levée de 122 M$ (2025). **[I] Le prédictif « l'administration gagnerait-elle ? » est le plus proche d'une qualification du risque.** | https://fintech.global/2025/08/05/blue-j-raises-122m-to-scale-ai-powered-tax-research/ ; https://openai.com/index/blue-j/ |
| **CoCounsel Tax / Checkpoint** (Thomson Reuters) | [F] Recherche et flux de travail fiscaux sur Checkpoint. « Ready to Advise / Ready to Review » (juillet 2025), agents (juin et novembre 2025). | Pas d'évaluation indépendante trouvée | https://tax.thomsonreuters.com/en/products/cocounsel-tax ; https://www.thomsonreuters.com/en/press-releases/2025/july/thomson-reuters-unveils-ai-native-agentic-applications-to-transform-tax-and-advisory-workflows |
| **Harvey, vLex Vincent, etc.** | Assistants juridiques généralistes | [F] VLAIR (Vals, février 2025) : l'IA dépasse la référence avocat sur 4 tâches documentaires sur 7. Les avocats restent meilleurs en *redlining* et en recherche EDGAR. | https://www.vals.ai/industry-reports/vlair-2-27-25 |

### 2.3 Évaluations publiées

- **[F] Stanford RegLab / HAI, « Hallucination-Free? »** (Magesh, Surani, Dahl, Suzgun, Manning, Ho, mai 2024, préenregistrée, 202 requêtes). Les outils RAG juridiques hallucinent dans **17 à 33 %** des cas. Lexis+ AI : 17 % d'hallucinations et 65 % de réponses exactes. Westlaw AI-Assisted Research : 33 % d'hallucinations et 42 % de réponses exactes (réponses plus longues, donc plus de propositions falsifiables). Conclusion : « *providers' claims are overstated* ».
  - https://arxiv.org/abs/2405.20362 ; https://law.stanford.edu/wp-content/uploads/2024/05/Legal_RAG_Hallucinations.pdf ; https://www.lawnext.com/2024/06/in-redo-of-its-study-stanford-finds-westlaws-ai-hallucinates-at-double-the-rate-of-lexisnexis.html
- **[F] Dahl et al. 2024** (Large Legal Fictions) : 58 à 88 % d'hallucinations pour des LLM généralistes sans RAG sur des questions vérifiables de jurisprudence.
- **[F] FiscalQA Pro (2026)** : sur le droit fiscal français **versionné dans le temps**, l'échec du RAG statique est quasi total (2,7 %). C'est l'évaluation la plus pertinente pour nous.
- **[F-sec]** Aucune évaluation **indépendante et préenregistrée** des outils français (Doctrine, GenIA-L, Lexis+ FR) n'a été trouvée. Les chiffres qui circulent (par ex. « moins de 1 % d'hallucination » pour Ordalie, « 92-93 % de satisfaction » pour GenIA-L) sont déclarés par les éditeurs ou non vérifiés. https://www.alphadeep.fr/guides/comparatif-ia-juridique-france-2026

**[I] Positionnement.** Le marché couvre la **recherche** (« que dit le droit sur X ? ») et la **rédaction**. Rien de public ne couvre :
- (a) l'audit systématique **du texte lui-même**, à la recherche d'incohérences, de seuils ou d'interactions ;
- (b) la génération et l'attaque de montages ;
- (c) la **qualification graduée** du risque d'abus ou de fraude avec la jurisprudence CADF / Conseil d'État à l'appui ;
- (d) la gestion rigoureuse des versions dans le temps.

C'est l'espace d'Interstice. Deux publics sont naturels : les fiscalistes et les acteurs publics (commissions des finances, DLF, Cour des comptes, CPO).

---

## 3. Usage de l'IA par la DGFiP

### 3.1 Chiffres officiels

| Indicateur | Valeur | Source |
|---|---|---|
| Droits et pénalités notifiés, contrôle fiscal 2025 | [F] 17,1 Md€ (16,7 Md€ en 2024) | https://presse.economie.gouv.fr/?p=174412 ; https://www.economie.gouv.fr/actualites/lutte-contre-la-fraude-un-controle-fiscal-toujours-plus-efficace-en-2025 |
| Montants encaissés 2025 | [F-sec] 11,4 Md€ | https://www.bdor.fr/actualites-or/fraude-fiscale-la-dgfip-recouvre-114-milliards-en-2025-malgre-171-milliards-reclames-les-effectifs-en-chute-libre-pointes-du-doigt |
| Rendement du datamining 2025 | [F-sec, citant le communiqué officiel] 2,8 Md€ (2,5 Md€ en 2024). 52 % des dossiers professionnels et plus de 54 % des dossiers particuliers clôturés orientés par ces outils. | idem |
| Part des contrôles issus du croisement de données en masse, 2023 | [F] 44 % des contrôles, mais **13,8 % des droits et pénalités** (2,1 Md€). 56 % des contrôles de professionnels, 40 % des contrôles de particuliers. | Cour des comptes, *La lutte contre la fraude fiscale*, déc. 2025 : https://www.ccomptes.fr/sites/default/files/2025-12/20251216-Lutte-contre-la-fraude-fiscale.pdf |
| Rendement moyen par contrôle, 2023 | [F] 3 473 € (liste issue du datamining) contre 16 676 € (programmation locale) | idem |
| Pertinence des listes IR | [F] 65 % des dossiers signalés ont donné lieu à un rehaussement. **93 %** pour le report erroné des réductions **Pinel**, 80 % pour les réductions et crédits d'impôt. 80 % des motifs de redressement retenus sont identiques à celui proposé par l'algorithme. | idem |
| Faiblesses | [F] Listes DMTG peu pertinentes (données notariales mal intégrées). Listes pour les impôts professionnels non évaluées. La **DVNI (grandes entreprises) ne reçoit pas ces listes**. Effectifs du contrôle en baisse de 19 % entre 2015 et 2024. L'objectif de 50 % est désormais vu comme un plafond. | idem |

### 3.2 Outils et cas d'usage

- **[F] CFVR** (*Ciblage de la fraude et valorisation des requêtes*) : lancé en 2014, avec une cellule dédiée depuis 2017. Il est aujourd'hui porté par le bureau SJCF-1D, qui croise de grands ensembles de données déclaratives. https://shs.cairn.info/article/RFFP_153_0021?lang=fr&ID_ARTICLE=RFFP_153_0021 ; rapport Cour des comptes ci-dessus.
- **[F-sec] Galaxie** : analyse de graphes de relations entre entités (personnes, sociétés, liens capitalistiques), utile pour les montages interposés. https://www.actuia.com/actualite/dgfip-les-controles-fiscaux-sappuient-de-plus-en-plus-sur-lintelligence-artificielle-et-le-data-mining/
- **[F] Foncier innovant** : détection par IA, sur orthophotos IGN, des bâtis et **piscines** non déclarés. Environ 150 000 piscines taxables détectées lors de la première phase. Industrialisation depuis juin 2024 et extension au bâti isolé (vérandas, abris). https://www.impots.gouv.fr/actualite/generalisation-du-foncier-innovant ; https://www.collectivites-locales.gouv.fr/animer-les-territoires/environnement-et-urbanisme/le-cadastre/le-foncier-innovant
- **[F-sec] Réseaux sociaux** : collecte de données publiques en ligne (expérimentation prolongée). https://finactuel.fr/controle-fiscal-intelligence-artificielle-fisc/
- **[F] LLaMandement** (DLF et DTNum de la DGFiP) : LLaMA-2 70B affiné sur 15 397 paires amendement / résumé. Il a résumé et réparti plus de 10 000 amendements lors du PLF 2024. Code ouvert. **[I] C'est un signe que la DLF outille déjà l'analyse de texte législatif, ce qui fait d'elle un partenaire ou un client potentiel.** https://next.ink/127670/llamandement-lia-generative-de-bercy-pour-resumer-10-000-amendements-en-15-minutes/ ; https://www.economie.gouv.fr/actualites/detection-des-fraudes-analyse-de-donnees-comment-lia-fait-son-entree-bercy
- **[F-sec] Assistant génératif interne** (expérimenté à l'été 2025 avec 500 agents, 3 000 agents en avril 2026, généralisation visée fin 2026). Il comprend un chat généraliste, **DocuFiP** (recherche sémantique dans la doctrine interne) et « **Langage clair** » (reformulation des courriers). https://www.silicon.fr/business-1367/impots-2026-comment-les-finances-publiques-utilisent-lia-227180 ; https://acteurspublics.fr/articles/a-la-dgfip-lia-assiste-les-inspecteurs-sans-les-remplacer/
- **[F]** Encadrement juridique discuté : https://revuedlf.com/droit-administratif/la-detection-algorithmique-de-la-fraude-fiscale-apres-lai-act-un-encadrement-toujours-insuffisant-du-recours-a-lintelligence-artificielle/

### 3.3 Ce que cela nous apprend

- **[I]** L'IA de la DGFiP est un **détecteur d'anomalies déclaratives** : incohérences entre sources, reports erronés, avantages fiscaux mal appliqués, bâti non déclaré. Elle n'est pas un détecteur de **montages**. Les montages sophistiqués relèvent de la programmation locale, des directions nationales (DNVSF, DVNI) et du CADF.
- **[I]** Conséquence pour la grille : une piste d'optimisation qui repose sur une **déclaration incohérente avec les données tierces** sera détectée presque mécaniquement, même si elle est juridiquement défendable. Il faut donc un critère « **détectabilité** » distinct du critère « **licéité** ». Les deux se combinent dans le score de risque.
- **[I]** Les niches les plus « contrôlées » par algorithme (Pinel, réductions et crédits d'impôt) sont celles dont les **conditions sont vérifiables par croisement**. Les conditions de fond non observables (intention, substance, activité réelle) échappent au datamining. C'est là que se logent les zones grises intéressantes.

---

## 4. Cadre juridique : optimisation, abus de droit, fraude

### 4.1 Tableau de synthèse

| Instrument | Texte | Critère | Champ | Conséquence | Garanties / procédure |
|---|---|---|---|---|---|
| **Abus de droit « classique »** | Art. **L64 LPF** | [F] Actes (a) **fictifs**, ou (b) cherchant le bénéfice d'une **application littérale des textes ou décisions à l'encontre des objectifs poursuivis par leurs auteurs**, inspirés par **aucun autre motif** que d'éluder ou d'atténuer l'impôt (**but exclusivement fiscal**) | Tous impôts | Actes inopposables. Majoration de **80 %** (art. 1729 b), ramenée à **40 %** si le contribuable n'a pas eu l'initiative principale et n'en est pas le principal bénéficiaire. | Saisine du **CADF** possible. Si l'administration ne suit pas l'avis, **la charge de la preuve** lui revient. Avis publiés dans un rapport annuel. |
| **« Mini-abus de droit »** | Art. **L64 A LPF** (LF 2019, art. 109) | [F] Application littérale contraire aux objectifs des auteurs, avec un **motif principal** fiscal (notion « plus large » que le but exclusivement fiscal, BOFiP §110). Ne vise **pas** la fictivité en tant que telle. | [F] **Tous impôts sauf IS** (BOFiP §20). Rectifications notifiées depuis le 01/01/2021 pour des actes passés depuis le 01/01/2020 (§30). | [F] **Pas de majoration automatique** de 80 % (§130). Les majorations de droit commun (40 % / 80 %) restent possibles. | CADF saisissable. [F] Les transmissions anticipées de patrimoine, **même avec réserve d'usufruit**, ne sont « pas en elles-mêmes concernées », sauf fictivité (BOFiP §80). |
| **Clause anti-abus générale IS** | Art. **205 A CGI** (transposition de l'art. 6 ATAD) | [F] Montage ou série de montages mis en place pour obtenir, **à titre d'objectif principal ou d'un des objectifs principaux**, un avantage fiscal contraire à l'objet ou à la finalité du droit applicable, et **non authentique** (pas de motifs commerciaux valables reflétant la réalité économique) | IS (exercices ouverts depuis le 01/01/2019) | Le montage est ignoré pour le calcul de l'IS | [À vérifier] Pas de procédure spéciale ni de saisine du CADF prévue par le texte |
| **Clauses anti-abus spéciales** | Par ex. mère-fille (art. 145 et 119 ter CGI), fusions (art. 210-0 A), anti-hybrides (art. **205 B à 205 D**, ATAD 2) | Critères propres à chaque régime | Régimes ciblés | Perte du régime | — |
| **Rescrit abus de droit** | Art. **L64 B LPF** | [F] Consultation préalable, écrite et complète. **Silence de 6 mois = accord tacite** : l'opération ne peut plus être remise en cause sur le fondement de l'abus de droit. | L64 (et L64 A) | Sécurité *ex ante* | [F-sec] Très peu utilisé (1 seul rescrit L64 B sur 22 341 rescrits en 2023) par crainte d'attirer l'attention. https://www.hagnere-patrimoine.fr/guides-patrimoine/optimisation-fiscale-dirigeant-sas/rescrit-fiscal-2026 |
| **Opposabilité de la doctrine** | Art. **L80 A / L80 B LPF** | Le contribuable peut se prévaloir du BOFiP et des rescrits | Tous impôts | Protection même si la doctrine est plus favorable que la loi | [F] **Limite** (CE, Ass., 28/10/2020, n° 428048) : l'administration peut écarter la garantie si elle prouve un **montage artificiel dénué de substance**, élaboré dans le seul but d'éluder l'impôt, pour entrer dans les prévisions de la doctrine. https://www.legifrance.gouv.fr/ceta/id/CETATEXT000042474925 |
| **DAC 6** | Art. **1649 AD à 1649 AH CGI** (ordonnance 2019-1068, directive 2018/822) | [F] Déclaration des **dispositifs transfrontières** présentant un ou plusieurs **marqueurs** (A à E). Pour certains marqueurs, le critère de l'avantage principal s'applique. | Transfrontière, depuis le 01/07/2020 | [F] Amende ≤ 10 000 € (≤ 5 000 € pour un premier manquement), plafonnée à 100 000 € par an et par déclarant | [F] CJUE, 08/12/2022, C-694/20 : invalidation de l'obligation, pour l'avocat tenu au secret, de notifier les autres intermédiaires. https://www.impots.gouv.fr/directive-ue-dac6-declaration-des-dispositifs-transfrontieres |
| **Majorations** | Art. **1729 CGI** | [F] **40 %** pour manquement délibéré. **80 %** pour abus de droit (L64) ou manœuvres frauduleuses (ou dissimulation du prix). | Tous impôts | Pénalités d'assiette | — |
| **Amende des conseils** | Art. **1740 A bis CGI** (depuis le 25/10/2018) | [F-sec] Le professionnel qui a fourni une prestation ayant permis au contribuable des agissements sanctionnés (manœuvres, dissimulation, actes fictifs, abus de droit) est passible d'une amende de 50 % des rémunérations perçues, **au minimum 10 000 €** | Conseils : avocats, notaires, experts-comptables, CGP… | **[I] Concerne directement un éditeur ou un conseil qui fournirait des montages** | Non applicable en cas de poursuites pénales. https://www.cnaf.notaires.fr/actualites/application-de-la-nouvelle-amende-fiscale-du-conseil-art-1740-bis-du-cgi |
| **Délit de mise à disposition d'instruments de facilitation de la fraude** | [F] Commenté au BOFiP BOI-CF-INF-40-40 (28/08/2024) | Fourniture d'outils, de services ou de schémas facilitant la fraude | — | Pénal | **[I] Risque à analyser pour un produit d'IA qui générerait des schémas.** https://bofip.impots.gouv.fr/bofip/14379-PGP.html/identifiant=BOI-CF-INF-40-40-20240828 |
| **Fraude fiscale pénale** | Art. **1741 CGI** (version en vigueur depuis le 15/06/2025) | [F] Soustraction frauduleuse à l'établissement ou au paiement de l'impôt (seuil de dissimulation : plus d'un dixième de l'impôt dû ou plus de 153 €) | Tous impôts | [F] **5 ans et 500 000 €** (amende portable au double du produit de l'infraction). **7 ans et 3 M€** en cas de circonstances aggravantes : comptes ou entités à l'étranger, interposition, faux, domiciliation fictive, **actes fictifs ou artificiels**… | https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051742509 |
| **Dénonciation automatique au parquet** | Art. **L228 LPF** (loi du 23/10/2018) | [F] Obligation de dénoncer quand les droits dépassent **100 000 €** et que s'applique une majoration de 100 % (opposition à contrôle), de 80 % (activité occulte, **abus de droit**, manœuvres frauduleuses, avoirs étrangers non déclarés…) ou de 40 % en cas de réitération sur 6 ans. Seuil de 50 000 € pour les personnes soumises à la HATVP. | — | Passage au pénal | https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000041471253 ; https://www.revue-fiduciaire.com/actualite/points-de-vue/l-obligation-de-transmission-au-parquet-des-dossiers-de-fraude-fiscale-est-precisee |

**[I] Point clé pour la grille.** Un abus de droit L64 ayant donné lieu à la majoration de 80 %, au-delà de 100 000 € de droits, **entre dans le champ de la dénonciation automatique au parquet**. La frontière entre « orange foncé » et « rouge » n'est donc pas étanche en pratique. Un montage qualifié d'abus L64 sur un gros enjeu doit être traité comme **risque pénal potentiel**.

**Évolution législative en cours** : [F] projet de loi contre les fraudes sociales et fiscales, adopté en 1re lecture à l'Assemblée le 07/04/2026, en attente de CMP à la date de la source. Il prévoit : conservation des documents portée de 6 à 10 ans, pénalité de 100 % pour la fraude au CIR, élargissement des cas de transmission automatique au parquet, obligations déclaratives sur les trusts, sur les acquisitions immobilières par des entités étrangères et sur les cessions de parts de sociétés à prépondérance immobilière (SPI). https://cms.law/fr/fra/legal-updates/projet-de-loi-contre-les-fraudes-sociales-et-fiscales-l-assemblee-nationale-adopte-le-texte-en-premiere-lecture2 **[À vérifier : statut définitif à la date d'usage.]**

### 4.2 Comité de l'abus de droit fiscal (CADF) : données exploitables

**Rapport 2024** [F] (https://www.impots.gouv.fr/sites/default/files/media/3_Documentation/cadf/rapport-annuel-2024.pdf) :
- 36 affaires reçues (contre 7 en 2023, 18 en 2022, 30 en 2021, 38 en 2020), 25 examinées, **23 avis favorables à l'administration (92 %)** et 2 défavorables. Taux favorables antérieurs : 80 % (2023), 81,25 % (2022), 67,57 % (2021).
- Répartition des affaires examinées : IR 16, droits d'enregistrement 7, IS 2.
- **Typologie des motifs** :
  - IR / plus-values mobilières : réduction de capital non motivée par des pertes (1), **donation fictive** (1), **cession temporaire d'usufruit** de titres de SCI (14 affaires liées, avec des augmentations de capital souscrites mais non libérées) ;
  - droits d'enregistrement : **donation déguisée** (6), remise en cause du régime de l'**art. 1115 CGI** (achat-revente de marchand de biens) (1) ;
  - IS : **montage artificiel de déductibilité de frais financiers** (1), cession temporaire d'usufruit (1).
- **Cas instructifs pour l'entraînement** :
  - Donation de nue-propriété suivie *le lendemain* d'une réduction de capital par rachat de titres, avec quasi-usufruit sans clause de remploi et prix porté au compte courant du donateur **avant** la convention de quasi-usufruit. Le CADF retient la **fictivité** (absence de dépouillement irrévocable).
  - Vente de nue-propriété à une SCI du fils, **minorée de 55 %**. Le CADF retient une donation déguisée avec charge.
  - Art. 1115 : revente **deux jours avant l'expiration du délai de 5 ans** à une société contrôlée par le même gérant, qui garde la jouissance du bien. Le CADF retient l'abus (engagement respecté seulement en la forme). **[I] C'est un motif type de « respect formel d'une condition de délai ».**
  - Refinancement intra-groupe d'une dette de 94 M€ par un « instrument participatif de prêt subordonné » (intérêt de 18 % du résultat, asymétrie France-Allemagne). **Avis défavorable à l'administration** : le refinancement a une justification économique. **[I] Montre que l'asymétrie internationale ne suffit pas : c'est la substance qui tranche.**

**Rapport 2025** [F-sec] : 24 nouvelles affaires (−33 %), 30 examinées en 4 séances, **13 avis favorables à l'administration et 17 défavorables**. Deux séries liées (12 dossiers) représentent 70 % des avis défavorables. https://www.editions-jfa.com/publication-du-rapport-annuel-2025-du-comite-de-labus-de-droit-fiscal/ ; https://kpmg.com/av/fr/avocats/eclairages/2026/06/comite-de-l-abus-de-droit-fiscal.html. [F-sec] Motifs cités : réductions de capital non motivées par des pertes, prêts fictifs déguisant des distributions, baux artificiels générant des déficits fonciers, donations déguisées, **PACS fictifs**, manipulation du régime SIIC, montages de déductibilité de charges financières. https://kohenavocats.com/abus-droit-fiscal-bilan-cadf-jurisprudence-2026/

> **Avertissement sur les sources secondaires [F].** Le même article (kohenavocats.com) présente l'arrêt *Aubépar Industries* (CE, 18/02/2026, n° 500134) comme défavorable au contribuable. La décision primaire et les analyses de Mayer Brown, CMS et Deloitte disent **l'inverse** : le Conseil d'État a jugé qu'une réorganisation de groupe poursuivant un « objectif d'ordre économique et organisationnel » (création d'une filiale, cession de l'actif principal contre crédit-vendeur, distribution de dividendes exonérés en régime mère-fille) n'est **pas** un abus de droit, même si elle procure un avantage fiscal substantiel. **Le pipeline doit remonter à la source primaire** (ArianeWeb, Légifrance) avant toute qualification. https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2026-02-18/500134 ; https://www.mayerbrown.com/en/insights/publications/2026/03/abus-de-droit-et-regime-mere-fille-le-motif-d-ordre-economique-et-organisationnel-d-une-restructuration-de-groupe-fait-obstacle-a-la-qualification-de-but-exclusivement-fiscal

**Jurisprudence récente utile [F]** :
- CE, 18/02/2026, n° 500134, *Aubépar Industries* : la logique de réorganisation du groupe fait obstacle au but exclusivement fiscal.
- CE, 12/03/2026, n° 492888 (BNP Paribas / SNC luxembourgeoise Grenache) : abus de droit L64 confirmé. L'opération se réduisait à une vente de protection CDS : environ 11 M€ d'économie fiscale annuelle pour 2,4 M€ de perte économique annuelle. **[I] Le ratio « avantage fiscal / résultat économique avant impôt » est un indicateur quantitatif fort.** https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2026-03-12/492888
- CE, Ass., 28/10/2020, n° 428048 : un montage artificiel fait tomber la garantie de l'art. L80 A.

---

## 5. Méthodologie des praticiens et taxonomie des zones grises

### 5.1 Comment les institutions repèrent les failles

- **[F] Cour des comptes, dépenses fiscales (NEB avril 2026, exécution 2025)** :
  - 474 dépenses fiscales pour 91,83 Md€ en 2025 (3,07 % du PIB, 25,76 % des recettes fiscales nettes) ;
  - révision de +6,73 Md€ par rapport au PLF 2025, dont près de la moitié pour le seul **pacte Dutreil** (chiffré à 800 M€, puis 4 Md€ pour 2025 et 5 Md€ pour 2024) ;
  - 22 dispositifs de plus de 1 Md€ représentent environ 60 % du coût ;
  - seuls **55 % des chiffrages sont jugés de bonne qualité**, et **le nombre de bénéficiaires est inconnu pour 42 % des dépenses fiscales** (environ 28 Md€) ;
  - la norme de référence est fixée par la DLF sans expertise extérieure. La Cour note des classements incohérents, par exemple le taux de 10 % pour les cantines d'entreprise, classé dépense fiscale, contre 5,5 % pour les cantines scolaires, qui ne l'est pas ;
  - les plafonds de coût et de durée à 3 ans prévus par les lois de programmation n'ont pas été appliqués.

  https://www.ccomptes.fr/sites/default/files/2026-04/NEB-2026-Depenses-fiscales.pdf
- **[F] Cour des comptes, pacte Dutreil (nov. 2025)** : coût de plus de 3,3 Md€ en 2023 et plus de 5,5 Md€ en 2024 (contre 1,2 Md€ en 2020-2021). Les effets économiques attendus ne sont « pas observés ». La Cour recommande de **supprimer les mécanismes relevant de l'optimisation**, d'exclure les biens non professionnels (holdings) et d'allonger la durée de conservation. **[I] C'est un exemple type de niche dont le détournement est documenté par une institution. Le rapport peut servir de vérité terrain.** https://www.ccomptes.fr/fr/publications/le-pacte-dutreil-un-dispositif-fiscal-en-forte-croissance-mieux-cibler
- **[F] Annexe « Évaluation des voies et moyens », tome II** (PLF) : c'est la liste officielle des dépenses fiscales. Pour 2025, 474 niches dont 65 en extinction, 387 chiffrées, et un chiffrage en simple « ordre de grandeur » pour 125 d'entre elles. **[I] Source structurée n° 1 pour la cartographie des niches.** https://www2.assemblee-nationale.fr/static/17/Annexes-DL/PLF-2025/Voies_et_moyens_Tome_2_2025.pdf
- **[F] Assemblée nationale** : rapport d'information de la commission des finances sur les dépenses fiscales en faveur du patrimoine (11/06/2025) et sur l'application des mesures fiscales (30/09/2025). Précédent méthodologique : le rapport IGF de 2011, qui a noté 315 niches de 0 à 3 (les niches notées 0 ou 1 représentaient plus des 2/3 du coût). https://www.assemblee-nationale.fr/dyn/17/dossiers/depenses_fisc_patri
- **[F] CPO** : « Conforter l'égalité des citoyens devant l'imposition des revenus » (oct. 2024, 18 propositions), et un cadre fiscal pluriannuel pour l'industrie (sept. 2025). https://www.vie-publique.fr/files/rapport/pdf/295784.pdf
- **[F] OCDE BEPS Action 12 / DAC 6** : les **marqueurs** (*hallmarks*) sont une taxonomie officielle des caractéristiques de planification agressive. On y trouve notamment : confidentialité, honoraires liés à l'avantage fiscal, documentation standardisée, achat de sociétés déficitaires, conversion de revenus, transactions circulaires, paiements déductibles vers des juridictions à taux nul, double déduction ou double exonération, prix de transfert. https://www.oecd.org/content/dam/oecd/fr/publications/reports/2015/10/mandatory-disclosure-rules-action-12-2015-final-report_g1g58cee/9789264252417-fr.pdf ; directive 2018/822 : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32018L0822
- **[F] Contentieux de la doctrine** : le Conseil d'État annule régulièrement des paragraphes du BOFiP qui ajoutent à la loi. Exemples en 2025 : sociétés d'exercice libéral (CE, 08/04/2025, n° 492154), parahôtellerie en TVA (CE, 12/11/2025, n° 498267), impatriés, plus-values à long terme et crédits d'impôt étrangers. https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2025-04-08/492154 ; https://www.village-justice.com/articles/regime-parahotellerie-conseil-etat-censure-partiellement-doctrine,55243.html

### 5.2 Taxonomie exploitable des zones grises

**[I]** Taxonomie construite à partir des sources ci-dessus (CADF, Cour des comptes, OCDE, contentieux BOFiP, recherche académique). Chaque type a un **signal détectable** et une **méthode de détection** adaptée.

| # | Type | Description | Exemples FR (sourcés ou connus) | Signal détectable automatiquement | Méthode |
|---|---|---|---|---|---|
| **Z1** | **Effet de seuil / falaise** | Un euro de plus fait perdre un avantage entier. Le taux marginal effectif peut dépasser 100 %. | [F] Bourses de lycée : taux marginal effectif > 100 % (Merigoux). [I] Seuils de chiffre d'affaires micro / franchise de TVA, seuil d'assujettissement à l'IFI, CEHR, conditions de revenu des réductions d'impôt. | Conditions du type `si X ≥ seuil` sans lissage ni décote. Discontinuité de la fonction impôt net = f(revenu). | Formalisation (Catala / SMT), balayage OpenFisca, recherche de discontinuités |
| **Z2** | **Cumul / empilement de régimes** | Deux régimes conçus séparément se combinent au-delà de l'intention du législateur, ou une règle de non-cumul manque. | [F] Dutreil + holdings patrimoniales (Cour des comptes). [I] Donation avant cession (purge de la plus-value) + démembrement. Niches hors du plafonnement global (art. 200-0 A). | Deux régimes applicables au même fait générateur ou à la même assiette, sans clause d'exclusion croisée | Graphe des régimes × assiettes, recherche des paires non exclusives, puis simulation |
| **Z3** | **Temporalité** | Dates d'entrée en vigueur, dispositions transitoires, fait générateur, durées d'engagement, régimes bornés, rétroactivité | [F] Revente deux jours avant l'expiration du délai de 5 ans (art. 1115, CADF 2024). [F] L64 A : actes passés à partir de 2020 et rectifications notifiées à partir de 2021. [F] FiscalQA Pro : le RAG échoue sur la version applicable. | Changement de rédaction entre deux versions. Fenêtre entre annonce et vote. Durée de détention ou d'engagement. Clause « jusqu'au 31/12/N ». | Corpus versionné (Légifrance, historique des versions), différence entre versions, frise des faits générateurs |
| **Z4** | **Divergence doctrine / loi / jurisprudence** | Le BOFiP est plus favorable ou plus restrictif que la loi, ou contredit la jurisprudence | [F] Annulations CE 2025 (SEL, parahôtellerie). [F] CE Ass. 2020 : la doctrine est opposable sauf montage artificiel. | Paragraphe BOFiP sans base textuelle directe. Décision citant le paragraphe BOFiP. Recours pour excès de pouvoir pendant. | Alignement article CGI ↔ § BOFiP ↔ décisions, puis détection de contradiction (NLI + règles) |
| **Z5** | **Qualification juridique ambiguë** | Un même flux peut relever de plusieurs catégories (revenu du travail ou du capital, prêt ou donation, meublé ou para-hôtelier, holding animatrice ou passive) | [F] Prêt requalifié en donation déguisée (CADF 2024). Holdings dans le Dutreil. Parahôtellerie en TVA. | Critères de qualification jurisprudentiels à « faisceau d'indices », notion non définie par la loi | LLM + base de décisions, puis extraction des critères du faisceau |
| **Z6** | **Asymétrie internationale / conflit de conventions** | Double non-imposition, hybrides, double résidence, conflits de qualification entre États | [F] Refinancement France-Allemagne (CADF 2024). [F] BNP / Grenache (CE 2026). [F] Art. 205 B-D. | Flux transfrontière avec traitement différent aux deux bouts. Marqueurs DAC 6. | Matrice convention × type de revenu, marqueurs DAC 6 formalisés |
| **Z7** | **Renvois et définitions incohérents** | Renvoi à un article abrogé ou renuméroté, même terme défini différemment selon les articles, conditions contradictoires | [F] « Zone d'incohérence » dans l'IRC §121 (formalisation Prolog). | Graphe de renvois cassé, divergence de définitions | Analyse de graphe de citations, formalisation |
| **Z8** | **Condition formelle / engagement déclaratif** | L'avantage dépend d'un engagement ou d'une formalité facile à respecter en la forme et vide en substance | [F] Art. 1115 (CADF). [F] Réduction de capital non motivée par des pertes. [F-sec] PACS fictif, bail artificiel. | Condition purement déclarative, délai, engagement non contrôlable par croisement | Lister les conditions « non observables » (croisées avec la section 3.3) |
| **Z9** | **Régime dérogatoire peu utilisé, non chiffré ou non évalué** | Niche au nombre de bénéficiaires inconnu, chiffrage en « ordre de grandeur », jamais évaluée | [F] 42 % des niches aux bénéficiaires inconnus. 87 niches non chiffrées sur 474. | Métadonnées de l'annexe Voies et moyens | Extraction structurée du tome II |
| **Z10** | **Asymétrie entre impôts** | Une opération neutre pour un impôt génère un avantage dans un autre (IR/IS, DMTG/plus-values, TVA/IS) | [I] Donation-cession, apport-cession (art. 150-0 B ter). [F] Cession temporaire d'usufruit (14 affaires CADF). | Même opération traitée dans plusieurs codes ou chapitres | Simulation multi-impôts de bout en bout |
| **Z11** | **Lacune / silence du texte** | Cas non prévu, catégorie résiduelle, absence de sanction de la condition | [I] Cas limites générés par la couverture de branches (CUTECat) | Branche non couverte, `else` implicite | Exécution concolique / couverture |
| **Z12** | **Écart texte / implémentation** | Le logiciel de l'administration diverge de la loi | [F] Bug CNAF révélé par Catala. [F] Code M incomplet. | Différence entre calcul formalisé et calcul officiel | Tests différentiels (Catala / OpenFisca contre simulateur officiel) |

**Axes transverses pour le scoring [I]** :
- **Enjeu financier** (gain par contribuable × nombre de contribuables potentiels).
- **Robustesse juridique** (texte clair, doctrine opposable, jurisprudence stable).
- **Détectabilité par la DGFiP** (condition vérifiable par croisement ou non).
- **Conformité à l'objectif du législateur**, qui exige les **travaux parlementaires** (exposés des motifs, rapports, débats), car c'est le critère juridique commun à L64, L64 A et 205 A.

---

## 6. Grille de qualification automatique vert / orange / rouge

**[I] Tout ce qui suit est une proposition de conception.** Elle s'appuie sur les textes de la section 4, mais c'est une construction de l'auteur. Elle devra être validée par des fiscalistes et calibrée sur les avis du CADF et la jurisprudence.

### 6.1 Niveaux

| Niveau | Nom | Définition opérationnelle | Fondement |
|---|---|---|---|
| 🟢 **V** | Optimisation sûre | L'avantage résulte d'une **option ouverte par le législateur**, utilisée **conformément à son objet**. Condition supplémentaire : le texte est clair, **ou** la doctrine est opposable (L80 A), **ou** un rescrit a été obtenu. Il y a de la substance économique réelle et aucune fictivité. | L80 A/B. BOFiP §80 de L64 A (transmissions anticipées). |
| 🟡 **J** | Zone grise interprétative | Texte ambigu, doctrine muette ou contestée, jurisprudence divergente. L'avantage n'est pas manifestement contraire à l'objectif, mais l'interprétation favorable n'est pas assurée. | Z4, Z5, Z7. Risque de rehaussement **sans** pénalité d'abus (majoration de 40 % seulement si manquement délibéré). |
| 🟠 **O1** | Risque mini-abus / 205 A | Il existe des motifs non fiscaux, mais l'avantage fiscal est le **motif principal**, **et** le résultat est contraire à l'objectif du texte. Pour l'IS : montage **non authentique**. | L64 A (hors IS), 205 A (IS). Pas de majoration automatique. |
| 🟠 **O2** | Risque abus de droit L64 | Motif **exclusivement** fiscal (pas de justification économique crédible), **ou** indices de fictivité | L64. Majoration de 80 % (40 % si pas l'initiative). CADF. Au-delà de 100 000 € de droits, **L228 (parquet)**. |
| 🔴 **R** | Fraude | Dissimulation, faux, fausse déclaration, omission délibérée, activité occulte, interposition pour dissimuler, domiciliation fictive | Art. 1729 (80 % pour manœuvres frauduleuses), 1741 (pénal), L228. **Art. 1740 A bis pour le conseil.** |
| 🏳️ **D6** | Drapeau DAC 6 (orthogonal) | Dispositif transfrontière présentant un marqueur | Art. 1649 AD-AH. Obligation déclarative **quel que soit le niveau**. |

### 6.2 Arbre de décision (à implémenter comme une chaîne de questions vérifiables)

```
Q0  La piste suppose-t-elle de déclarer un fait inexact, de dissimuler
    un revenu, un actif ou une identité, ou de produire un document inexact ?
    ├─ OUI → 🔴 R (refus de génération détaillée ; mention du risque pénal)
    └─ NON ↓
Q1  Un acte de la chaîne est-il fictif ? (absence de dépouillement réel,
    flux financiers ne correspondant pas aux actes, prix sans rapport avec
    la valeur, acte signé pendant le contrôle, contrôle conservé sur l'actif…)
    ├─ OUI → 🟠 O2 (fictivité L64) → vérifier Q6 (enjeu > 100 k€ ?)
    └─ NON ↓
Q2  L'avantage provient-il d'une application littérale d'un texte ou d'une
    décision CONTRAIRE aux objectifs de ses auteurs ?
    (test : travaux parlementaires, exposé des motifs, BOFiP, jurisprudence)
    ├─ NON → Q4
    └─ OUI ↓
Q3  Existe-t-il un motif non fiscal réel et documentable ?
    (réorganisation, refinancement, transmission familiale, cf. Aubépar)
    ├─ AUCUN (but exclusivement fiscal) → 🟠 O2
    ├─ OUI mais secondaire (motif principal fiscal) → 🟠 O1
    │     (IS → test 205 A « non authentique » ; autres impôts → L64 A)
    └─ OUI et prépondérant → 🟡 J (ou 🟢 V si Q4 favorable)
Q4  Le texte est-il clair ET (doctrine opposable OU jurisprudence stable
    OU rescrit obtenu) ?
    ├─ OUI → 🟢 V
    └─ NON → 🟡 J
Q5  (orthogonal) Dispositif transfrontière avec marqueur A–E ? → 🏳️ D6
Q6  (modulateur) Enjeu en droits > 100 000 € et niveau O2 ou R → alerte L228 (parquet)
Q7  (modulateur) Détectabilité DGFiP : la condition est-elle vérifiable par
    croisement de données (datamining) ? → score de probabilité de contrôle
```

### 6.3 Indicateurs (features) pour chaque question

| Question | Indicateurs automatisables | Sources d'entraînement / calibrage |
|---|---|---|
| Q1 fictivité | Écart prix / valeur (par ex. décote de 55 %). Opérations enchaînées en moins de N jours. Flux en compte courant avant l'acte. Absence de clause de remploi. Signature pendant le contrôle. Maintien de la jouissance. | Rapports CADF 2020-2025, décisions CE / CAA |
| Q2 objectif du législateur | Distance sémantique entre l'usage et l'exposé des motifs. Existence d'une clause anti-abus spécifique. Rapports critiques (Cour des comptes). | Travaux parlementaires (AN / Sénat), annexe Voies et moyens, rapports de la Cour des comptes |
| Q3 motif | Ratio **avantage fiscal / résultat économique avant impôt** (BNP : environ 11 M€ contre −2,4 M€). Existence d'une activité, de salariés, de risques supportés. Logique de groupe (Aubépar). | Jurisprudence L64 / L64 A / 205 A, rapports CADF |
| Q4 sécurité | Paragraphe BOFiP opposable (en vigueur à la date du fait générateur). Rescrits publiés. Arrêts concordants. Recours pour excès de pouvoir pendant. | BOFiP versionné, ArianeWeb, Légifrance |
| Q5 DAC 6 | Critères des marqueurs formalisés (règles) | Art. 1649 AH, BOFiP DAC 6 |
| Q7 détectabilité | Présence de la donnée dans des sources tierces (DSN, notaires, banques, IGN, déclarations croisées) | Rapport Cour des comptes 2025 (pertinence par impôt) |

**[I] Règles de prudence** :
- **Asymétrie des coûts d'erreur** : classer 🟢 une piste 🟠 est bien plus grave que l'inverse. Il faut donc des seuils conservateurs et une abstention autorisée (« contradiction gate », cf. Sadowski et Chudziak).
- Toute qualification doit être **justifiée par des sources primaires versionnées** et accompagnée d'un **renvoi à un professionnel** (avocat fiscaliste). Le rescrit L64 B est proposé systématiquement pour 🟡 / 🟠 O1.
- **Calibrage** : les avis du CADF (environ 20 à 40 par an, avec une typologie publiée) et la jurisprudence L64 forment un jeu d'évaluation naturel, étiqueté par une autorité.

---

## 7. Implications pour l'architecture du projet

**[I] Recommandations tirées de l'état de l'art :**

1. **Corpus versionné d'abord.** CGI, LPF, BOFiP, conventions, jurisprudence et travaux parlementaires, chacun indexé par période de validité. FiscalQA Pro montre que le RAG statique donne 2,7 % sur les questions temporelles, contre 98,3 % pour un retriever multi-versions. Toute détection de type Z3 en dépend.
2. **Couche de formalisation partielle** (Catala de préférence, pour la continuité avec Inria / DGFiP, ou Prolog). Elle cible les parties calculables : seuils, taux, plafonds, conditions de cumul. Le LLM traduit, le solveur (SMT / concolique) **prouve** et produit des **contre-exemples** (Z1, Z2, Z7, Z11, Z12). Paradigme « le LLM propose, le vérificateur dispose ».
3. **Oracle de calcul** : OpenFisca / LexImpact pour balayer les taux marginaux effectifs et les falaises sur des foyers types.
4. **Boucle adversariale** :
   - un agent **Explorateur** propose des combinaisons d'opérations (inspiré de Fratrič et al. et de la coévolution MIT) ;
   - un agent **Contrôleur** joue l'inspecteur et le CADF : il cherche la fictivité, le but exclusivement ou principalement fiscal, la contrariété à l'objectif, la détectabilité ;
   - un agent **Juge** qualifie selon la grille de la section 6.

   Le Contrôleur doit être outillé : jurisprudence, avis CADF, vérificateur formel. La littérature montre que le LLM seul est **faible pour repérer les stratégies viciées** (20 sur 36 jugées viables à tort par Claude-4).
5. **Contradiction gate et abstention** : un appel de vérification systématique avant de conclure (Sadowski et Chudziak : 63 à 76 % des contradictions sont ignorées en mode « résolution »).
6. **Évaluation** :
   - jeu d'avis CADF 2019-2025 ;
   - décisions L64 / L64 A / 205 A ;
   - niches documentées comme détournées (Dutreil) ;
   - un **benchmark interne FR** type *Shelter Check* (stratégies + variantes piégées), dont la plus grande partie reste privée pour éviter la contamination.
7. **Garde-fous juridiques et éthiques** :
   - le niveau 🔴 bloque la génération opérationnelle ;
   - analyse du risque au regard de l'**art. 1740 A bis** (amende du conseil) et du **délit de mise à disposition d'instruments de facilitation de la fraude** (BOI-CF-INF-40-40) ;
   - analyse du périmètre du **monopole de la consultation juridique** (loi n° 71-1130, art. 54 et suivants) **[À vérifier avec un avocat]** ;
   - politique de **divulgation responsable** des failles « rouges » ou structurelles (vers la DLF ou les commissions des finances), sur le modèle de Blair-Stanek et al. avec l'IRS.
8. **Positionnement** : outil d'**audit de la loi**, pour les parlementaires, la DLF, la Cour des comptes, le CPO, les think tanks et les fiscalistes, plutôt que « générateur d'optimisation » grand public. C'est plus défendable juridiquement et moins encombré commercialement (section 2).

---

## 8. Sources

### Recherche académique
- Blair-Stanek, Holzenberger, Van Durme, *Can LLMs Identify Tax Abuse?* (2025) — https://arxiv.org/abs/2508.20097 — https://github.com/BlairStanek/LLM-Tax-Abuse
- Fratrič, Holzenberger, Restrepo Amariles, *Can AI Expose Tax Loopholes?* (2025) — https://arxiv.org/abs/2503.17339
- Bhattacharya, Hemberg, O'Reilly, *A Hybrid LLM-Coevolution Framework to Generate Abusive Tax Strategies* (EuroGP 2026) — https://link.springer.com/chapter/10.1007/978-3-032-23005-8_8
- Leguizamon et al., *Evolutionary Computation for Tax-Minimizing Strategies in Special Economic Zones* (GECCO 2026) — https://doi.org/10.1145/3795095.3805115
- Hemberg, O'Reilly et al., *Tax non-compliance detection using co-evolution…* (ICAIL 2015) — https://dl.acm.org/doi/10.1145/2746090.2746099
- Choi, Bansal, Stengel-Eskin, *Language Models Identify Ambiguities and Exploit Loopholes* (EMNLP 2025) — https://arxiv.org/abs/2508.19546
- Lazebnik, Shami, *Investigating Tax Evasion Emergence Using Dual LLM and Deep RL* (2025) — https://arxiv.org/abs/2501.18177
- Holzenberger et al., SARA (2020) — https://arxiv.org/abs/2005.05257
- Tax Notes, *OpenAI Cribbed Our Tax Example, But Can GPT-4 Really Do Tax?* (2023) — https://www.taxnotes.com/featured-analysis/openai-cribbed-our-tax-example-can-gpt-4-really-do-tax/2023/08/11/7h0hc
- Jurayj, Holzenberger, Van Durme, *Language Models and Logic Programs for Trustworthy Tax Reasoning* (AAAI 2026) — https://arxiv.org/abs/2508.21051
- Sadowski, Chudziak, *Solving versus Verifying* (ICTAI 2026) — https://arxiv.org/abs/2609.05928
- Yadamsuren, Platt, Diaz, *LLM-Assisted Formalization… Statutory Inconsistency* (2025/2026) — https://arxiv.org/abs/2511.11954 — https://link.springer.com/article/10.1007/s10506-026-09525-6
- Cymbler, Guez, Fabre, *Temporal Misgrounding in Legal RAG: French Tax Law* (2026) — https://arxiv.org/abs/2608.09393
- LegalBench — https://github.com/HazyResearch/legalbench/
- TaxCalcBench — https://github.com/column-tax/tax-calc-bench
- TaxPraBen — https://arxiv.org/pdf/2604.08948
- Dahl et al., *Large Legal Fictions* (2024) — https://arxiv.org/abs/2401.01301
- Magesh et al., *Hallucination-Free?* (Stanford, 2024) — https://arxiv.org/abs/2405.20362
- Merigoux, Monat, Protzenko, *A Modern Compiler for the French Tax Code* (CC 2021) — https://arxiv.org/pdf/2011.07966
- Merigoux, blog « taxes / formal proofs » (2019) — https://blog.merigoux.ovh/en/2019/12/20/taxes-formal-proofs.html
- Catala — https://arxiv.org/pdf/2103.03198 — https://www.inria.fr/en/catala-software-dgfip-cnaf
- CUTECat — https://link.springer.com/chapter/10.1007/978-3-031-91121-7_2
- Heydari, Leowald, *Closing the Loop* (2026) — https://arxiv.org/pdf/2606.23913
- LexImpact / OpenFisca — https://leximpact.an.fr/ — https://fr.openfisca.org/showcase/leximpact/

### Produits
- Doctrine — https://www.doctrine.fr/solutions/fiscalite — rachat de Predictice : https://doctrine.pr.co/254391-doctrine-annonce-l-acquisition-de-predictice-et-assoit-sa-place-de-leader-europeen-de-l-ia-juridique/
- GenIA-L — https://www.lefebvre-dalloz.fr/genia-l/
- Lexis+ AI / Protégé — https://www.lexisnexis.com/blogs/fr-juridique/b/actualite/posts/lancement-lexis-plus-ai-france
- Wisetax — https://wisetax.fr/avocat-fiscaliste/ ; FiscoGPT — https://fiscogpt.fr/ ; Fiscal Expert France — https://fiscalexpertfrance.fr/ ; Fiscaly.ai — https://www.fiscaly.ai/
- Blue J — https://fintech.global/2025/08/05/blue-j-raises-122m-to-scale-ai-powered-tax-research/
- CoCounsel Tax — https://tax.thomsonreuters.com/en/products/cocounsel-tax
- Vals VLAIR — https://www.vals.ai/industry-reports/vlair-2-27-25

### Administration
- Cour des comptes, *La lutte contre la fraude fiscale* (déc. 2025) — https://www.ccomptes.fr/sites/default/files/2025-12/20251216-Lutte-contre-la-fraude-fiscale.pdf
- Bilan de la lutte contre la fraude 2025 — https://presse.economie.gouv.fr/?p=174412
- Foncier innovant — https://www.impots.gouv.fr/actualite/generalisation-du-foncier-innovant
- LLaMandement — https://next.ink/127670/llamandement-lia-generative-de-bercy-pour-resumer-10-000-amendements-en-15-minutes/
- Assistant IA interne DGFiP — https://www.silicon.fr/business-1367/impots-2026-comment-les-finances-publiques-utilisent-lia-227180
- Datamining (RFFP) — https://shs.cairn.info/article/RFFP_153_0021?lang=fr&ID_ARTICLE=RFFP_153_0021

### Cadre juridique
- Procédure de l'abus de droit L64 à L64 B (Légifrance) — https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006069583/LEGISCTA000006180036/2025-07-25
- BOFiP L64 A (BOI-CF-IOR-30-20) — https://bofip.impots.gouv.fr/bofip/12049-PGP.html/identifiant=BOI-CF-IOR-30-20-20200131
- BOFiP 205 A (BOI-IS-BASE-70) — https://bofip.impots.gouv.fr/bofip/11864-PGP.html/identifiant=BOI-IS-BASE-70-20190703
- Rescrit L64 B — https://www.service-public.gouv.fr/demarches-silence-vaut-accord/demarches/776
- CADF, rapport 2024 — https://www.impots.gouv.fr/sites/default/files/media/3_Documentation/cadf/rapport-annuel-2024.pdf ; rapport 2023 — https://www.impots.gouv.fr/sites/default/files/media/3_Documentation/cadf/rapport-annuel-2023.pdf
- CADF 2025 (synthèses) — https://www.editions-jfa.com/publication-du-rapport-annuel-2025-du-comite-de-labus-de-droit-fiscal/ ; https://kpmg.com/av/fr/avocats/eclairages/2026/06/comite-de-l-abus-de-droit-fiscal.html
- DAC 6 — https://www.impots.gouv.fr/directive-ue-dac6-declaration-des-dispositifs-transfrontieres ; CJUE C-694/20 : https://www.actu-juridique.fr/professions/avocats/dac-6-les-avocats-sauvent-partiellement-leur-secret-professionnel/
- Art. 1741 CGI — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051742509
- Art. L228 LPF — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000041471253
- Art. 1740 A bis CGI — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000037520949/2018-12-31 ; https://www.cnaf.notaires.fr/actualites/application-de-la-nouvelle-amende-fiscale-du-conseil-art-1740-bis-du-cgi
- Délit de facilitation de la fraude (BOI-CF-INF-40-40) — https://bofip.impots.gouv.fr/bofip/14379-PGP.html/identifiant=BOI-CF-INF-40-40-20240828
- CE, Ass., 28/10/2020, n° 428048 — https://www.legifrance.gouv.fr/ceta/id/CETATEXT000042474925
- CE, 18/02/2026, n° 500134 (Aubépar) — https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2026-02-18/500134
- CE, 12/03/2026, n° 492888 (BNP / Grenache) — https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2026-03-12/492888
- Anti-hybrides 205 B — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000044978626
- Projet de loi fraudes 2026 — https://cms.law/fr/fra/legal-updates/projet-de-loi-contre-les-fraudes-sociales-et-fiscales-l-assemblee-nationale-adopte-le-texte-en-premiere-lecture2

### Méthodologie / niches
- Cour des comptes, NEB 2025 « Dépenses fiscales » (avril 2026) — https://www.ccomptes.fr/sites/default/files/2026-04/NEB-2026-Depenses-fiscales.pdf
- Cour des comptes, *Le pacte Dutreil* (nov. 2025) — https://www.ccomptes.fr/fr/publications/le-pacte-dutreil-un-dispositif-fiscal-en-forte-croissance-mieux-cibler
- Voies et moyens, tome II, PLF 2025 — https://www2.assemblee-nationale.fr/static/17/Annexes-DL/PLF-2025/Voies_et_moyens_Tome_2_2025.pdf
- AN, rapport d'information sur les dépenses fiscales en faveur du patrimoine (2025) — https://www.assemblee-nationale.fr/dyn/17/dossiers/depenses_fisc_patri
- CPO (oct. 2024) — https://www.vie-publique.fr/files/rapport/pdf/295784.pdf
- OCDE BEPS Action 12 — https://www.oecd.org/content/dam/oecd/fr/publications/reports/2015/10/mandatory-disclosure-rules-action-12-2015-final-report_g1g58cee/9789264252417-fr.pdf
- Directive 2018/822 (DAC 6) — https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32018L0822
- Annulations BOFiP 2025 — https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2025-04-08/492154 ; https://www.village-justice.com/articles/regime-parahotellerie-conseil-etat-censure-partiellement-doctrine,55243.html
