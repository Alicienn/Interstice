# Sources de données juridiques françaises pour un corpus de droit fiscal

> **Contexte.** Inventaire des sources exploitables pour construire le corpus d'une IA spécialisée en droit fiscal français : textes (CGI, LPF, CIBS), doctrine (BOFiP), jurisprudence (CE, CAA, Cass., Conseil constitutionnel, CJUE), conventions, sources parlementaires et budgétaires. Pour chaque source : contenu, format, accès, fréquence, licence, volume et gestion des versions.
>
> **Date de rédaction :** 27 septembre 2026. Les listings de serveurs et les mesures ont été faits ce jour-là.
>
> **Convention de lecture.** Chaque information porte l'une de ces trois étiquettes :
> - **[Fait sourcé]** : affirmé par une source citée (URL). Une source secondaire est signalée comme telle.
> - **[Mesuré]** : constaté directement pendant cette recherche (listing de répertoire, téléchargement, comptage par script). La méthode est indiquée.
> - **[Estimation]** : extrapolation ou ordre de grandeur. Ce n'est pas un fait établi.

---

## Table des matières

1. [Synthèse](#1-synthèse)
2. [DILA open data (LEGI, JORF, KALI, JADE, CASS, INCA, CAPP, CONSTIT, CNIL)](#2-dila-open-data)
3. [API Légifrance (PISTE)](#3-api-légifrance-piste)
4. [Décisions de justice en open data : Judilibre et justice administrative](#4-décisions-de-justice-en-open-data)
5. [BOFiP-Impôts](#5-bofip-impôts)
6. [Conventions fiscales, droit de l'UE et jurisprudence CJUE](#6-conventions-fiscales-droit-de-lue-et-jurisprudence-cjue)
7. [Conseil constitutionnel (QPC fiscales)](#7-conseil-constitutionnel-qpc-fiscales)
8. [Rescrits, réponses ministérielles, dépenses fiscales, Cour des comptes et CPO](#8-rescrits-réponses-ministérielles-dépenses-fiscales-cour-des-comptes-cpo)
9. [Outils et jeux de données open source existants](#9-outils-et-jeux-de-données-open-source-existants)
10. [Volumes en tokens du noyau fiscal](#10-volumes-en-tokens-du-noyau-fiscal)
11. [Recommandations pour le pipeline](#11-recommandations-pour-le-pipeline)
12. [Sources](#12-sources)

---

## 1. Synthèse

| Source | Contenu utile au fiscal | Format | Accès | Mise à jour | Licence | Volume (compressé) |
|---|---|---|---|---|---|---|
| DILA **LEGI** | CGI, annexes I-IV, LPF, CIBS, lois de finances consolidées, **toutes versions** | XML (DTD Légifrance) | Dump HTTPS/FTPS, sans authentification | Incréments quotidiens | Licence Ouverte 2.0 | Global 1,1 Go + incréments |
| DILA **JORF** | Lois de finances (version publiée), décrets, arrêtés | XML | Dump | Plusieurs fois par jour | LO 2.0 | Global 1,6 Go |
| DILA **JADE** | CE (Lebon depuis 1965, sélection d'inédits), CAA (sélection), TC | XML | Dump | Quotidienne | LO 2.0 | Global 1,2 Go |
| DILA **CASS / INCA / CAPP** | Cass. publiés / inédits / sélection des CA | XML | Dump | Hebdomadaire / irrégulière | LO 2.0 | 248 Mo / 655 Mo / 279 Mo |
| DILA **CONSTIT** | Décisions du Conseil constitutionnel (DC, QPC…) | XML | Dump | Irrégulière | LO 2.0 | 12 Mo |
| **API Légifrance** (PISTE) | Mêmes fonds que ci-dessus, en requête unitaire | JSON (REST) | OAuth2 client credentials, inscription gratuite | Temps réel | LO 2.0 + CGU | Quotas visibles dans PISTE seulement |
| **opendata.justice-administrative.fr** | **Toutes** les décisions CE (depuis sept. 2021), CAA (mars 2022), TA (juin 2022) | XML dans des ZIP mensuels | Téléchargement libre | Continue, ZIP par mois | LO 2.0 + CGU | CE ≈ 2 Mo/mois, CAA ≈ 12 Mo/mois, TA ≈ 75 Mo/mois |
| **Judilibre** (PISTE) | Cass. (≈ 480 000 décisions en 2021), CA, TJ, TCom, CPH | JSON (REST) | Clé PISTE | Continue | LO 2.0 + CGU | API uniquement |
| **BOFiP** open data | Doctrine en vigueur (≈ 9 150 documents), rescrits RES, actualités | tar.gz : XML (métadonnées) + HTML ; API CSV/JSON | Téléchargement libre | Stock **mensuel**, flux **hebdomadaire** | LO 2.0 | Stock 117 Mo |
| **EUR-Lex / CELLAR** | Directives TVA, DAC, ATAD… ; arrêts CJUE | Formex XML, XHTML, PDF, RDF | SPARQL public, REST, webservice SOAP (inscription) | Quotidienne | CC BY 4.0 (décision 2011/833/UE) | À la demande |
| **Voies et moyens, tome II** | ≈ 465 dépenses fiscales, coût, base légale | PDF (≈ 250 p.) ; tableur pour PLF 2023 et 2024 seulement | Libre | Annuelle (PLF) | LO 2.0 (jeux data.economie) | 1,5 Mo (PDF) |
| **Questions écrites** AN / Sénat / DILA | Réponses ministérielles | JSON/XML (AN), dump PostgreSQL (Sénat), XML (DILA) | Libre | Quotidienne (AN) | Licences propres AN/Sénat, LO (DILA) | ≈ 48 Mo par législature (AN) |

**Principaux constats**

1. **LEGI est la seule source officielle qui donne toutes les versions dans le temps** des articles (CGI, LPF, CIBS), avec leurs dates de début et de fin de vigueur. C'est le socle de tout raisonnement « à date ».
2. **Le BOFiP en open data ne contient que la version en vigueur** (stock mensuel et flux hebdomadaires). Pour avoir les versions antérieures, il faut accumuler les flux soi-même ou récupérer les pages « versions antérieures » du site.
3. **La jurisprudence administrative est exhaustive depuis 2021-2022** (opendata.justice-administrative.fr). Avant cette date, on n'a qu'une **sélection** (JADE, ArianeWeb).
4. **[Mesuré] Noyau textuel fiscal en vigueur (CGI + annexes I-IV + LPF + CIBS) : ≈ 1,9 à 2,4 M tokens en o200k**, et jusqu'à ≈ 3 M avec des tokenizers plus gourmands. Avec le **BOFiP en vigueur (≈ 18,5 à 25 M tokens)**, on dépasse largement une fenêtre de 1 M tokens.

---

## 2. DILA open data

### 2.1 Accès, licence, organisation

- **[Fait sourcé]** Accès libre en HTTPS (`https://echanges.dila.gouv.fr/OPENDATA/`) et en FTPS (`ftps://echanges.dila.gouv.fr`), sans authentification. Licence : **Licence Ouverte / Open Licence** (Etalab). Contact : donnees-dila@dila.gouv.fr. Source : fiches data.gouv.fr de [LEGI](https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides), [JADE](https://www.data.gouv.fr/datasets/jade), [CASS](https://www.data.gouv.fr/datasets/cass), [INCA](https://www.data.gouv.fr/datasets/inca) et [CAPP](https://www.data.gouv.fr/datasets/capp).
- **[Fait sourcé]** Les bases LEGI, KALI, JORF, CAPP, CASS, INCA, JADE, ACCO, DOLE, CNIL et CONSTIT partagent des **DTD génériques** et ont chacune des DTD spécifiques. Le tout est regroupé dans le référentiel « DTD LEGIFRANCE » ([répertoire](https://echanges.dila.gouv.fr/OPENDATA/DTD_LEGIFRANCE/), qui contient aussi une note de migration technique d'octobre 2023).
- **[Fait sourcé]** Avertissement sur les données personnelles : leur mise à disposition « n'affranchit pas le réutilisateur du respect de la loi Informatique et Libertés » ([PDF](https://echanges.dila.gouv.fr/OPENDATA/AVERTISSEMENT-Donnees_a_caractere_personnel.pdf)).
- **[Mesuré, listing du 27/09/2026]** Chaque base contient :
  - une archive globale `Freemium_<base>_global_20250713-140000.tar.gz`, datée du **13 juillet 2025** (le dernier dump global a donc plus d'un an) ;
  - des archives incrémentales `<BASE>_AAAAMMJJ-HHMMSS.tar.gz`. Reconstituer l'état courant suppose d'appliquer au global tous les incréments publiés depuis.

| Base | Archive globale (13/07/2025) | Cadence des incréments observée | Dernier incrément |
|---|---|---|---|
| LEGI | **1,1 Go** | quotidienne (1 à 8 Mo) | 26/09/2026 |
| JORF | **1,6 Go** | 1 à 2 par jour | 27/09/2026 |
| JADE | **1,2 Go** | quotidienne (0,25 à 2,6 Mo) | 26/09/2026 |
| KALI | 173 Mo | quasi quotidienne | 25/09/2026 |
| INCA | 655 Mo | hebdomadaire | 14/09/2026 |
| CAPP | 279 Mo | irrégulière (quelques-uns par mois) | 12/06/2026 |
| CASS | 248 Mo | hebdomadaire (lundi) | 21/09/2026 |
| CONSTIT | 12 Mo | irrégulière | 04/08/2026 |
| CNIL | 18 Mo | plusieurs par semaine | 25/09/2026 |

- **[Fait sourcé]** Selon le README de legi.py, la DILA publie une nouvelle archive LEGI « à la fin de chaque jour ouvré » ([legi.py](https://github.com/Legilibre/legi.py)).

### 2.2 Contenu des bases

- **LEGI** **[Fait sourcé]** ([data.gouv](https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides)) : « le texte intégral consolidé de la législation et de la réglementation nationale ». La base comprend :
  - les codes officiels : « 73 codes officiels en vigueur consolidés (et les autres 29 abrogés) » ;
  - les lois, décrets-lois, ordonnances et décrets, de façon exhaustive depuis 1945, plus une sélection d'arrêtés.

  Surtout, « les versions modifiées ou abrogées sont présentes dans le fonds documentaire au même titre que les versions en vigueur ».
- **JORF** **[Fait sourcé]** ([data.gouv](https://www.data.gouv.fr/datasets/jorf-les-donnees-de-l-edition-lois-et-decrets-du-journal-officiel)) : l'édition « Lois et décrets » depuis 1990, dans sa **version publiée, non consolidée**. Certaines mesures nominatives sont exclues (naturalisations, changements de nom…). Pour le fiscal, c'est là qu'on trouve les lois de finances telles que votées.
- **JADE** **[Fait sourcé]** ([data.gouv](https://www.data.gouv.fr/datasets/jade)) : décisions du Conseil d'État, des CAA et du Tribunal des conflits.
  - Pour le CE : les « grands arrêts », les décisions publiées au Lebon depuis 1965, et « une sélection limitée de décisions inédites au recueil entre 1975 et 1986, sélection élargie depuis 1986 ».
  - Pour les CAA : « une sélection d'arrêts, variable selon chacune des 8 Cours ».
  - Texte intégral, avec abstracts et résumés pour les décisions publiées au Lebon.
- **CASS** **[Fait sourcé]** : arrêts de la Cour de cassation publiés au Bulletin (chambres civiles depuis 1960, chambre criminelle depuis 1963), avec titrages et sommaires. Le contentieux fiscal judiciaire (droits d'enregistrement, ISF/IFI, douanes) relève surtout de la **chambre commerciale**.
- **INCA** **[Fait sourcé]** : arrêts **inédits** de la Cour de cassation depuis 1989.
- **CAPP** **[Fait sourcé]** : sélection de décisions des cours d'appel et des juridictions du premier degré depuis 1997.
- **CONSTIT** **[Mesuré]** : l'archive globale (12 Mo compressés, 95 Mo décompressés) contient **7 112 décisions**, dont 4 038 AN (contentieux électoral), **1 022 QPC**, 884 DC, 310 L, 305 SEN… Chaque fichier XML porte les métadonnées `NATURE`, `NUMERO`, `DATE_DEC`, `SOLUTION`, `ECLI`, `LOI_DEF` et `URL_CC`, puis le texte dans `BLOC_TEXTUEL`.
- **CNIL** : délibérations de la CNIL. Marginal pour le fiscal.
- **Questions-Réponses** **[Mesuré]** : sous-répertoires `AN/` et `SENAT/`, organisés par année de 2011 à 2025, plus `Annee_en_cours/`. Il s'agit des questions écrites et réponses publiées au JO (voir §8).

### 2.3 Structure XML de LEGI (constatée sur l'incrément `LEGI_20260926-210736`)

**[Mesuré]** L'archive incrémentale du 26/09/2026 (1,3 Mo) compte 10 761 entrées, dont 533 articles `LEGIARTI`. Arborescence :

```
legi/global/
  code_et_TNC_en_vigueur/
    code_en_vigueur/LEGI/TEXT/00/00/06/06/95/LEGITEXT000006069577/   <- un code (ici le chemin du CGI)
      texte/struct/LEGITEXT….xml     (structure : sections de 1er niveau)
      texte/version/LEGITEXT….xml    (métadonnées de version du texte)
      section_ta/LEGI/SCTA/…/LEGISCTA….xml
      article/LEGI/ARTI/…/LEGIARTI….xml
    TNC_en_vigueur/…                  (textes non codifiés : lois, décrets)
  code_et_TNC_non_vigueur/…
  eli/…                               (alias ELI, ex. eli/arrete/2026/…)
```

Identifiants utiles pour le fiscal **[Mesuré]**, déduits de la fréquence des auto-références dans les `links` du jeu AgentPublic (§9) et de l'URL Légifrance du CGI :
- CGI : `LEGITEXT000006069577` ;
- LPF : `LEGITEXT000006069583` ;
- CIBS : `LEGITEXT000044595989` ;
- probablement annexe II : `LEGITEXT000006069569`, annexe III : `LEGITEXT000006069574` (à confirmer dans `texte/version`).

**Les trois objets de LEGI**

1. **`LEGITEXT`** (texte ou code). Deux fichiers :
   - `texte/version` : `TITRE`, `ETAT`, `DATE_DEBUT`, `DATE_FIN`, `NOTA`, `VISAS`, etc. ;
   - `texte/struct` : `META_TEXTE_CHRONICLE` avec `DERNIERE_MODIFICATION` et **`VERSIONS_A_VENIR`** (exemple observé sur le code de commerce : 2026-10-01, 2027-01-01, 2027-01-06, 2029-01-01), puis `<STRUCT>` qui liste des `LIEN_SECTION_TA` (attributs `id`, `cid`, `debut`, `fin`, `etat`, `niv`, `url`).
2. **`LEGISCTA`** (section : partie, livre, titre, chapitre…). Contient `TITRE_TA` et `STRUCTURE_TA`, qui liste des `LIEN_SECTION_TA` (sous-sections) et des `LIEN_ART` (articles). Chaque lien porte ses propres dates `debut`/`fin` et son `etat`. **L'arborescence est donc elle-même versionnée** : un article peut changer de section au fil du temps.
3. **`LEGIARTI`** (une **version** d'article ; un identifiant par version). Extrait réel :

```xml
<ARTICLE><META><META_COMMUN><ID>LEGIARTI000006255835</ID><ANCIEN_ID>…</ANCIEN_ID>
  <ORIGINE>LEGI</ORIGINE><URL>article/LEGI/ARTI/…</URL><NATURE>Article</NATURE></META_COMMUN>
 <META_SPEC><META_ARTICLE><NUM>R123-1</NUM><ETAT>MODIFIE</ETAT>
  <DATE_DEBUT>2007-03-27</DATE_DEBUT><DATE_FIN>2010-03-04</DATE_FIN><TYPE>AUTONOME</TYPE>
 </META_ARTICLE></META_SPEC></META>
<CONTEXTE><TEXTE cid="LEGITEXT…" nature="CODE" …>
  <TITRE_TXT c_titre_court="Code de commerce" debut="2000-09-21" fin="2999-01-01" …/>
  <TM><TITRE_TM debut="…" fin="…" id="LEGISCTA…">Partie réglementaire</TITRE_TM><TM>…</TM></TM>
</TEXTE></CONTEXTE>
<VERSIONS>
  <VERSION etat="MODIFIE"><LIEN_ART debut="2007-03-27" fin="2010-03-04" id="LEGIARTI000006255835" num="R123-1" …/></VERSION>
  …
  <VERSION etat="VIGUEUR"><LIEN_ART debut="2023-01-01" fin="2999-01-01" id="LEGIARTI000043292222" …/></VERSION>
</VERSIONS>
<NOTA><CONTENU>…</CONTENU></NOTA>
<BLOC_TEXTUEL><CONTENU>… texte HTML de l'article …</CONTENU></BLOC_TEXTUEL>
<LIENS>
  <LIEN cidtexte="JORFTEXT…" id="LEGIARTI…" naturetexte="LOI" sens="source" typelien="CITATION">Loi n°94-126 … art. 1</LIEN>
  <LIEN … sens="cible" typelien="CITATION">Arrêté du 17 mars 1995 - art. 1</LIEN>
  <LIEN … sens="source" typelien="CODIFICATION">Décret 2007-431 …</LIEN>
</LIENS></ARTICLE>
```

**Gestion du temps dans LEGI** **[Mesuré, confirmé par la doc AgentPublic]**

- **Chaque version d'article est un fichier `LEGIARTI` distinct.** Il porte `DATE_DEBUT`, `DATE_FIN` et `ETAT`. La date `2999-01-01` signifie « pas de fin connue ».
- Le bloc `<VERSIONS>`, **présent dans chaque version**, donne la chaîne complète des versions de l'article (identifiants, dates, états). On reconstitue l'historique sans jointure coûteuse.
- Le `CONTEXTE` donne le chemin hiérarchique de l'article (`TITRE_TM`), avec les intitulés datés des sections.
- Les **états** possibles (liste de la [fiche AgentPublic/legi](https://huggingface.co/datasets/AgentPublic/legi)) :
  - `VIGUEUR`, `VIGUEUR_DIFF` (entrée en vigueur différée), `MODIFIE`, `ABROGE`, `ABROGE_DIFF` ;
  - `ANNULE` ;
  - `DISJOINT`, « spécifique à la législation fiscale » ;
  - `PERIME` (abrogation implicite ; exemple cité : l'art. 39 octies du CGI) ;
  - `TRANSFERE`, `MODIFIE_MORT_NE`.
- **Liens** (`<LIENS>`) : chaque `LIEN` a un `typelien` (CITATION, CODIFICATION, MODIFIE, ABROGE, CREE, etc.) et un `sens` (`source` = ce texte agit sur l'article ou est cité par lui ; `cible` = l'inverse). On peut en déduire un **graphe de citations et de modifications** entre articles, et vers les lois modificatrices dans JORF.

---

## 3. API Légifrance (PISTE)

- **[Fait sourcé]** Accès **gratuit après inscription** sur [piste.gouv.fr](https://piste.gouv.fr). Version stable depuis le **4 avril 2023** ; la bêta a été fermée le 6 juin 2023. Les données sont celles du site Légifrance. Licence ouverte 2.0, plus les CGU PISTE et les CGU de l'API ([Légifrance, open data et API](https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api)).
- **[Fait sourcé]** Authentification **OAuth 2.0 « client credentials »** ([FAQ API Légifrance](https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api)) :
  - Sandbox : `https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app`, jeton via `https://sandbox-oauth.piste.gouv.fr/api/oauth/token`.
  - Production : `https://api.piste.gouv.fr/dila/legifrance/lf-engine-app`, jeton via `https://oauth.piste.gouv.fr/api/oauth/token`. Un jeton sandbox n'est pas valable en production.
  - Il faut accepter les CGU de l'API dans chaque environnement, sinon on obtient une erreur « 403 Access denied ».
- **[Fait sourcé]** Principaux endpoints (FAQ) : `POST /search` (recherche multi-fonds), `POST /consult/getArticle`, `POST /consult/legiPart` (texte LEGI à une date), `POST /consult/jorfCont`, `POST /consult/lastNJo`, `GET /list/ping`. La documentation Swagger complète est sur PISTE. Fonds interrogeables : LEGI (CODE_ETAT, CODE_DATE, LODA_DATE, LODA_ETAT), JORF, KALI, CETAT/JADE, JURI (Cass.), JUFI, CONSTIT, CNIL, CIRCULAIRES, Questions-Réponses, Débats, etc.
- **Quotas.** **[Fait sourcé]** « Les appels API sont limités par quotas par jetons d'accès ». Les valeurs chiffrées ne sont **pas publiées** : elles se consultent dans PISTE (Applications › API › Actions › « Consulter les quotas »), et la DILA peut les modifier à tout moment ([data.gouv, dataservice Légifrance](https://www.data.gouv.fr/dataservices/legifrance) ; [CGU API](https://www.legifrance.gouv.fr/contenu/Media/files/pied-de-page/cgu-legifrance-api-vf-15-12-2022_0.pdf)). **Je n'ai pas trouvé de chiffre officiel public** ; ceux qui circulent sur des blogs ne sont pas vérifiés.
- **Analyse.** L'API sert à des requêtes ponctuelles : résolution d'un article à une date, vérification en temps réel. Pour **construire un corpus**, les dumps DILA sont plus adaptés : ils sont complets, sans quota et sans authentification.

---

## 4. Décisions de justice en open data

### 4.1 Cadre légal et calendrier

- **[Fait sourcé]** ([Ministère de la Justice](https://www.justice.gouv.fr/documentation/open-data-decisions-justice)) Les textes fondateurs sont :
  - la loi pour une République numérique du 7 octobre 2016 ;
  - la loi du 23 mars 2019 de programmation et de réforme pour la justice ;
  - le décret du 29 juin 2020 ;
  - l'arrêté du 28 avril 2021, qui fixe le calendrier.

  Les noms des personnes physiques sont systématiquement occultés. D'autres éléments peuvent l'être en cas d'atteinte à la sécurité ou à la vie privée. Pour la pseudonymisation, le CE et la Cour de cassation combinent traitement automatisé et vérification manuelle.
- **[Fait sourcé] Calendrier** ([opendata.justice-administrative.fr](https://opendata.justice-administrative.fr/) ; [justice.gouv.fr](https://www.justice.gouv.fr/documentation/open-data-decisions-justice) ; [Capstan](https://www.capstan.fr/articles/1283-open-data-des-decisions-de-justice-le-calendrier-est-fixe/), source secondaire) :
  - **Ordre administratif** : Conseil d'État le **30/09/2021**, CAA le **31/03/2022**, TA le **30/06/2022**.
  - **Ordre judiciaire, matière civile** : Cour de cassation le 30/09/2021, cours d'appel le 30/04/2022, conseils de prud'hommes le 30/06/2023, tribunaux de commerce le 31/12/2024, tribunaux judiciaires au plus tard le **30/09/2025**.
  - **Ordre judiciaire, matière pénale** : Cour de cassation le 30/09/2021. Les étapes suivantes s'étalent jusqu'en 2025-2027 selon la juridiction (le ministère parle de « 31 décembre 2026 et 2027 » pour le pénal de première instance).

### 4.2 Justice administrative : opendata.justice-administrative.fr

- **[Fait sourcé]** Décisions du CE (depuis le 30/09/2021), des CAA (31/03/2022) et des TA (30/06/2022), mises en ligne progressivement, **au format XML**, en ZIP « regroupés par juridiction, par année et par mois ». Réutilisation sous **Licence Ouverte 2.0** complétée par des [CGU](https://opendata.justice-administrative.fr/cgu.html). La pseudonymisation repose sur les articles L. 10 et R. 741-13 à R. 741-15 du CJA.
- **[Mesuré]** Adresses réelles des fichiers : `https://opendata.justice-administrative.fr/DCE/AAAA/MM/CE_AAAAMM.zip`, et de même `DCA/…/CAA_AAAAMM.zip` et `DTA/…/TA_AAAAMM.zip`. Le lien affiché à la racine `/DCE/CE_AAAAMM.zip` renvoie une erreur 404. Il existe aussi un fichier `CE_documents_reverses.csv`.
- **[Mesuré]** Tailles : CE ≈ 1,5 à 3 Mo par mois, CAA ≈ 12,6 Mo (mars 2025), TA ≈ 75 Mo (mars 2025).
- **[Mesuré]** Structure d'un fichier (`DCE_445611_20250321.xml`), à plat, **sans versions** (les mises à jour portent sur les occultations) :
  - `Donnees_Techniques` : `Identification`, `Date_Mise_Jour` ;
  - `Dossier` : `Code_Juridiction`, `Numero_Dossier`, `Date_Lecture`, `Numero_ECLI`, `Type_Decision` (Décision / Ordonnance), `Type_Recours`, `Code_Publication` (A/B/C/D…), `Solution` ;
  - `Audience` : `Formation_Jugement`, par exemple « 3ème et 8ème chambres réunies » ;
  - `Decision/Texte_Integral` : le texte en HTML simple.
- **ArianeWeb** **[Fait sourcé]** ([Conseil d'État](https://conseil-etat.fr/actualites/arianeweb-130-000-decisions-de-jurisprudence-administrative-en-ligne-gratuitement) ; [Jurisguide](https://jurisguide.univ-paris1.fr/fiches-documentaires/arianeweb-1), source secondaire). Base de consultation du CE, ouverte en 2011 avec plus de 130 000 décisions ; environ 300 000 documents selon Jurisguide. Elle contient :
  - des décisions classées **A** (intérêt jurisprudentiel majeur), **B** (mentionnées aux tables) ou **C** ;
  - les **analyses** des décisions A et B ;
  - une **sélection de conclusions de rapporteurs publics depuis 2007**.

  ArianeWeb **n'offre pas de dump** : c'est une interface de recherche. Les conclusions des rapporteurs publics sont pourtant très utiles pour le raisonnement fiscal, et elles ne figurent pas dans le XML open data.

### 4.3 Judilibre (Cour de cassation)

- **[Fait sourcé]** API gratuite via PISTE ([data.gouv](https://www.data.gouv.fr/dataservices/api-judilibre)). Racines : sandbox `https://sandbox-api.piste.gouv.fr/cassation/judilibre/v1.0`, production `https://api.piste.gouv.fr/cassation/judilibre/v1.0`. Les requêtes s'authentifient via PISTE (en-tête `KeyId` selon le [README](https://github.com/Cour-de-cassation/judilibre-search/blob/dev/README.md)). Les quotas sont annoncés « prochainement sur le portail PISTE » et ne sont pas publiés dans la documentation publique. Réutilisation soumise aux [CGU open data](https://piste.gouv.fr/images/cgu/CGU_open_data_V8.pdf).
- **[Mesuré, spécification OpenAPI v1.2.5](https://github.com/Cour-de-cassation/judilibre-search/blob/dev/public/JUDILIBRE-public.json)** :
  - `GET /search` : 50 résultats par page au maximum ; filtres `theme`, `jurisdiction`, `location`, dates…
  - `GET /decision` : texte intégral et métadonnées.
  - `GET /export` et `GET /scan` : export par lots, **`batch_size` de 1 000 au maximum**, filtre `date_type=creation|update` pour la synchronisation incrémentale.
  - `GET /transactionalhistory` : journal des créations, mises à jour et suppressions, pour tenir une copie locale à jour.
  - `GET /taxonomy`, `GET /stats`, `GET /healthcheck`.
  - Juridictions : `cc`, `ca`, `tj`, `tcom`, `cph`.
  - Format JSON, avec un **zonage** du texte (introduction, exposé, moyens, motivations, dispositif, annexes).
- **Volume.** **[Fait sourcé, secondaire]** Environ 480 000 décisions de la Cour de cassation (depuis 1947 pour l'essentiel) étaient accessibles à l'ouverture le 30/09/2021 ([Barreau de Paris](https://www.avocatparis.org/actualites/judilibre-lopen-data-des-decisions-de-justice-cest-maintenant)). Le ministère parle d'environ 100 000 décisions civiles de premier degré en cours de diffusion. Des statistiques à jour sont annoncées sur [stats.judilibre.io](https://stats.judilibre.io/), dont je n'ai pas pu lire le contenu.

---

## 5. BOFiP-Impôts

- **[Fait sourcé]** Le BOFiP contient « les commentaires administratifs des dispositions législatives et réglementaires de portée fiscale, les décisions de rescrit de portée générale, les réponses ministérielles innovantes et les commentaires des décisions de jurisprudence ayant une incidence sur la doctrine » ([data.economie, bofip-impots](https://data.economie.gouv.fr/explore/dataset/bofip-impots/)). Licence : **Licence Ouverte v2.0**, producteur DGFiP.
- **Deux canaux open data** :
  1. **Archives tar.gz** ([jeu `bofip-impots`](https://data.economie.gouv.fr/explore/dataset/bofip-impots/)). **[Fait sourcé, [documentation technique DGFiP](https://data.economie.gouv.fr/api/v2/catalog/datasets/bofip-impots/attachments/bofip_documentation_pdf)]** :
     - un **stock** `bofip_stock_live_AAAAMMJJ.tgz`, extrait **une fois par mois**, qui contient « l'intégralité des données du référentiel BOFiP (dans leur version en cours) » ;
     - un **flux** `bofip_flux_live_AAAAMMJJ_BBBBNNKK.tgz`, extrait **chaque semaine**, avec les documents émis depuis le flux précédent ;
     - un contrôle MD5 pour chaque archive.

     **[Mesuré]** Le stock du 23/09/2026 pèse **116,9 Mo** (`https://bofip.impots.gouv.fr/opendata/stock/9`). Le flux du 17 au 23/09/2026 pèse 177 ko (6 publications). L'API du jeu ne liste que **7 enregistrements** (1 stock et 6 flux) : **l'historique des flux n'est pas conservé** en open data.
  2. **Jeu « publications en vigueur »** ([data.gouv](https://www.data.gouv.fr/datasets/bofip-impots-publications-en-vigueur) / [data.economie `bofip-vigueur`](https://data.economie.gouv.fr/explore/dataset/bofip-vigueur/)), exportable en CSV ou JSON par l'API Opendatasoft, mis à jour **chaque semaine**. Champs : `type`, `titre`, `debut_de_validite`, `serie`, `division`, `identifiant_juridique`, `permalien`, `contenu`, `contenu_html`. **[Mesuré]** **9 148 enregistrements** (6 357 « Contenu » et 2 791 « Actualité ») au 17/09/2026.
- **Structure des archives** **[Fait sourcé + mesuré]** :
  - arborescence `BOFiP/documents/{Contenu|Fichier|Image|PlanClassement}/<type>/<série>/<id>-PGP/<date de publication>/` ;
  - pour chaque document, un `document.xml` (métadonnées **Dublin Core** : `dc:title`, `dc:date`, `dc:subject` = série, `dc:identifier` = permalien avec l'identifiant BOI daté, `dc:relation` typées `references` / `isReferencedBy`) et un bloc `bofip:bodgfip` (`contenu_type` : Commentaire, Barème, Formulaire, Lettre type, Cartographie, Autres annexes ; `contenu_id`, par exemple `BOI-RES-TVA-000272-20260923`) ;
  - le texte dans un `data.html` (en HTML depuis 2020) ;
  - les DTD dans `BOFiP/infos/`.
- **Versions dans le temps.** Chaque publication a un identifiant BOI suffixé par sa date (`BOI-TVA-DED-40-30-20160302`), et le site conserve les **versions antérieures** de chaque BOI ([tutoriel BOFiP](https://bofip.impots.gouv.fr/bofip/12556-PGP.html/ACTU-2020-00272-0)). La doctrine antérieure au 12/09/2012 (anciennes DB, instructions BOI) est sur [bofip-archives.impots.gouv.fr](https://bofip-archives.impots.gouv.fr/). **Analyse** : l'open data ne fournit que la version en cours. Pour un historique (utile en contentieux, puisque la doctrine est opposable à sa date au titre de l'art. L. 80 A du LPF), il faut **archiver les flux hebdomadaires dès maintenant** et récupérer les versions antérieures depuis le site.
- **[Mesuré]** Composition, d'après le jeu HF `louisbrulenaudet/bofip` (instantané de juillet 2025, 8 804 documents, dont 6 212 contenus et 2 592 actualités) : séries BIC 1 178, TVA 851, IS 739, IR 706, IF 670, ENR 459, INT 451, RPPM 386, CF 324, RSA 318, RFPI 267, **REC 245**, BA 244, … , **RES (rescrits) 158**, CVAE 57.

---

## 6. Conventions fiscales, droit de l'UE et jurisprudence CJUE

### 6.1 Conventions fiscales bilatérales

- **[Fait sourcé]** [impots.gouv.fr, « Les conventions internationales »](https://www.impots.gouv.fr/les-conventions-internationales) : textes publiés **par pays**, **uniquement en PDF**. On y trouve la convention d'origine, les avenants, des **versions consolidées modifiées par la convention multilatérale (IML/BEPS)**, et les accords particuliers (frontaliers, télétravail).
- **[Fait sourcé]** La liste officielle ([BOI-ANNX-000306-20260429](https://bofip.impots.gouv.fr/bofip/2509-PGP.html/identifiant=BOI-ANNX-000306-20260429)) recense les conventions **en vigueur au 1er janvier 2026** : **plus de 120 États et territoires**, pour l'impôt sur le revenu, la fortune, les successions et les donations. La [liste des conventions modifiées par l'IML](https://bofip.impots.gouv.fr/bofip/14862-PGP.html/ACTU-2025-00179) est aussi publiée au BOFiP.
- **Autre source** : les décrets de publication des conventions figurent au JORF, et certains textes sont dans LEGI (traités publiés). Leur couverture n'a pas été vérifiée.
- **[Estimation]** Environ 125 conventions de 15 à 40 pages, avec avenants et consolidations : **≈ 2 à 5 M tokens**. L'extraction PDF est à fiabiliser (tableaux, mises en page anciennes numérisées).

### 6.2 Droit de l'UE : EUR-Lex / CELLAR

- **[Fait sourcé]** Pour les gros volumes, on interroge le référentiel **CELLAR** de l'Office des publications :
  - soit par le **point SPARQL** (`https://publications.europa.eu/webapi/rdf/sparql`) ;
  - soit par l'API REST (téléchargement des manifestations XHTML, Formex XML ou PDF à partir des identifiants CELLAR) ;
  - soit par le **webservice SOAP EUR-Lex**, qui demande une inscription ([EUR-Lex, webservice](https://eur-lex.europa.eu/content/help/data-reuse/webservice.html) ; [guide PDF](https://eur-lex.europa.eu/content/tools/webservices/DataExtractionUsingWebServices.pdf)).

  Les documents anciens n'existent souvent qu'en **Formex** (pas en XHTML). Réutilisation autorisée par la décision **2011/833/UE**, en pratique sous **CC BY 4.0** ([décision 2011/833](https://eur-lex.europa.eu/eli/dec/2011/833/oj/eng)).
- **[Mesuré, requêtes SPARQL du 27/09/2026, sans authentification]** Actes portant la matière `subject-matter/FISC` :
  - **209 directives** (CELEX secteur 3, type L), dont **83** marquées en vigueur ;
  - 141 règlements, 565 décisions ;
  - **2 696 documents de la Cour de justice** (secteur 6 « C » : arrêts, conclusions d'avocats généraux, ordonnances) et 16 du Tribunal.

  Exemple : la directive DAC6 (CELEX `32018L0822`) porte le code répertoire `dir-eu-legal-act/0950` et les matières `FISC` et `RAPL`. **Limite** : l'indexation par matière n'est pas garantie exhaustive, et certains arrêts TVA peuvent être indexés autrement.
- **Jurisprudence CJUE.** Même canal (CELLAR, secteur 6 : `CJ` arrêts, `CC` conclusions, `CO` ordonnances), ou [CURIA](https://curia.europa.eu). Le contentieux TVA y est massif.
- **[Estimation]** Environ 2 700 documents fiscaux CJUE × 6 000 à 10 000 tokens (arrêts et conclusions en français) : **≈ 15 à 25 M tokens**. Les directives fiscales en vigueur (TVA 2006/112, DAC, ATAD, mère-fille, intérêts-redevances, Pilier 2…) : **≈ 1 à 2 M tokens**.

---

## 7. Conseil constitutionnel (QPC fiscales)

- **Accès** : base DILA **CONSTIT** (§2, 12 Mo, XML), API Légifrance (fonds CONSTIT), ou [conseil-constitutionnel.fr](https://www.conseil-constitutionnel.fr), qui publie aussi les **commentaires** et les **dossiers documentaires** (absents de CONSTIT).
- **[Mesuré]** L'archive globale du 13/07/2025 contient **1 022 QPC**. Une heuristique sur les titres (mots « impôt, imposition, taxe, contribution, fiscal, droits d'enregistrement, TVA, redevance, prélèvement, plus-value, revenus… ») en isole **162** comme fiscales, soit environ 16 %, pour **≈ 0,43 M tokens** (o200k). Le tri est grossier (faux positifs et faux négatifs possibles) et reste à affiner, par exemple avec les articles du CGI ou du LPF cités dans `LOI_DEF` ou les visas.
- **[Estimation]** En ajoutant les décisions DC sur les lois de finances (environ 2 par an depuis 1959) et les commentaires officiels, le corpus constitutionnel fiscal fait **≈ 1 à 2 M tokens**.

---

## 8. Rescrits, réponses ministérielles, dépenses fiscales, Cour des comptes, CPO

### 8.1 Rescrits publiés

- **[Fait sourcé + mesuré]** Les rescrits « de portée générale » sont publiés au BOFiP dans la série **RES** (`BOI-RES-<série>-<n°>-<date>`, par exemple `BOI-RES-TVA-000272-20260923`, sous forme question / réponse). Ils sont donc inclus dans l'open data BOFiP (158 documents RES dans l'instantané de juillet 2025). Les rescrits individuels ne sont pas publics.

### 8.2 Réponses ministérielles (questions écrites)

- **Assemblée nationale** **[Mesuré]** : [data.assemblee-nationale.fr](https://data.assemblee-nationale.fr/travaux-parlementaires/questions/questions-ecrites) publie « l'ensemble des questions écrites […] et leurs réponses » **par législature**, en ZIP **XML ou JSON**. Pour la 17e législature (`/static/openData/repository/17/questions/questions_ecrites/Questions_ecrites.json.zip`) : **48,1 Mo**, modifié le **27/09/2026** (mise à jour quotidienne). Pour la 16e : 46,6 Mo, figé depuis juin 2024. Licence : conditions propres au site de l'AN, compatibles avec la Licence Ouverte (à vérifier).
- **Sénat** **[Fait sourcé]** : [data.senat.fr, base Questions](https://data.senat.fr/la-base-questions/). Questions écrites et orales **depuis le 2 avril 1978** (références et/ou texte intégral selon la date), en **dump PostgreSQL** (`/data/questions/questions.zip`), plus des extraits CSV (questions de l'année écoulée, questions d'actualité…).
- **DILA** **[Mesuré]** : `OPENDATA/Questions-Reponses/{AN,SENAT}/<année>` depuis 2011, en XML de l'édition « Débats – Questions/Réponses » du JO.
- **Analyse.** Une réponse ministérielle n'est opposable (art. L. 80 A LPF) que si elle est reprise au BOFiP (« réponses ministérielles innovantes »). Le flux parlementaire complet est un gros corpus, très bruité hors fiscal : il faut filtrer par ministère destinataire (Économie, Comptes publics) et par rubrique (« impôts et taxes »…).

### 8.3 Dépenses fiscales : « Évaluation des voies et moyens », tome II

- **[Fait sourcé]** Annexe au PLF qui décrit chaque dépense fiscale : impôt, article du CGI, finalité, coût sur trois exercices, nombre de bénéficiaires, fiabilité du chiffrage ([budget.gouv.fr](https://www.budget.gouv.fr/documentation/documents-annexes-evaluation/evaluations-voies-moyens-tome-2)). Pour le **PLF 2026** : **465 dépenses fiscales**, dont 82 en extinction ; un coût individuel est chiffré pour 408 d'entre elles ; total de **89,4 Md€ en 2024**, 91,8 Md€ en 2025 et 88,3 Md€ en 2026 ([Cour des comptes, NEB 2026 « Dépenses fiscales »](https://www.ccomptes.fr/sites/default/files/2026-04/NEB-2026-Depenses-fiscales.pdf), via un résumé de recherche).
- **[Mesuré]** PDF du PLF 2026 ([budget.gouv.fr/documentation/file-download/30586](https://www.budget.gouv.fr/documentation/file-download/30586)) : **252 pages, 1,56 Mo, ≈ 0,62 M caractères extraits, soit ≈ 0,16 M tokens** (o200k). Le PDF du PLF 2025 ([AN](https://www2.assemblee-nationale.fr/static/17/Annexes-DL/PLF-2025/Voies_et_moyens_Tome_2_2025.pdf)) : 247 pages, ≈ 0,16 M tokens. L'extraction PDF casse les tableaux.
- **[Mesuré] Versions tableur** sur data.economie.gouv.fr :
  - [`plf2023_voies_et_moyens_t2_liste_des_depenses_fiscales`](https://www.data.gouv.fr/datasets/plf2023-voies-et-moyens-t2-liste-des-depenses-fiscales) (xlsx + CSV/JSON, LO 2.0) ;
  - [`plf-2024-vm-tome-2_depenses-fiscales`](https://www.data.gouv.fr/datasets/plf-2024-vm-tome-2-depenses-fiscales) (468 lignes, **colonnes mal nommées** : `empty0`… `empty8`, licence non précisée).

  **Je n'ai trouvé aucun jeu tableur pour les PLF 2025 et 2026** : pour ces années, il faut parser le PDF. Le PLF 2027 (déposé début octobre 2026) n'était pas encore disponible à la date de rédaction.

### 8.4 Cour des comptes et Conseil des prélèvements obligatoires (CPO)

- **[Fait sourcé, partiel]** Les rapports sont publiés en **PDF** sur ccomptes.fr (le CPO dispose d'une rubrique sur le même site). Selon la synthèse de recherche des [mentions légales](https://www.ccomptes.fr/fr/mentions-legales), les documents officiels sont « librement réutilisables » (à confirmer sur la page elle-même). Certains jeux de données annexes sont sur data.gouv.fr sous **ODbL**, par exemple « La gestion des dépenses fiscales en faveur du logement » (2019) et « L'efficience des dépenses fiscales relatives au développement durable » (2016).
- **Analyse.** Il n'existe **aucun dump structuré**. Il faut constituer une liste ciblée de rapports fiscaux (NEB « Dépenses fiscales » annuelle, rapports CPO sur la fiscalité locale, du patrimoine, des entreprises, etc.) et en extraire le texte. **[Estimation]** 30 à 60 rapports pertinents × 50 000 à 150 000 tokens : **≈ 3 à 6 M tokens**.

---

## 9. Outils et jeux de données open source existants

| Projet | Ce qu'il fait | État (27/09/2026) | Licence | Intérêt |
|---|---|---|---|---|
| [**legi.py**](https://github.com/Legilibre/legi.py) (Legilibre) | Convertit les archives LEGI en **SQLite**, gère les mises à jour incrémentales, normalise titres et numéros, « factorise » (relie) les versions d'un texte, détecte des anomalies. **[Fait sourcé]** « La taille du fichier SQLite créé est environ 5 Go (en 2026) » | Actif (dernier push 18/09/2026), 60 étoiles | Non déclarée sur GitHub (à vérifier) | **Meilleur point de départ** pour une base versionnée locale |
| [**Archeo-Lex**](https://github.com/Legilibre/Archeo-Lex) | Historique des codes en **Git + Markdown** (un commit par version) | Inactif (dernier push 2019) | WTFPL | Concept utile (diff entre versions), code daté |
| [**Tricoteuses**](https://git.tricoteuses.fr/logiciels/tricoteuses-legifrance) | Récupère, valide, nettoie et convertit JORF/LEGI/KALI/DOLE (PostgreSQL, JSON). Publie **chaque code sous Git**, y compris [`codes/code_general_des_impots_annexe_iii`](https://git.tricoteuses.fr/codes/code_general_des_impots_annexe_iii), et des jeux HF (`Tricoteuses/LEGI`, `CAPP`, `CNIL`) | Actif (git.tricoteuses.fr) | Voir le dépôt | Codes fiscaux déjà versionnés en Git |
| **HF `louisbrulenaudet/*`** | Un jeu Parquet par code : [`code-impots`](https://huggingface.co/datasets/louisbrulenaudet/code-impots), `code-impots-annexe-i` à `-iv`, `livre-procedures-fiscales`, `code-impositions-biens-services`, [`bofip`](https://huggingface.co/datasets/louisbrulenaudet/bofip)… (44 colonnes, format de l'API Légifrance : `texte`, `texteHtml`, `etat`, `dateDebut`, `dateFin`, `lienCitations`…) | Mis à jour en sept. 2025 (codes) et juillet 2025 (BOFiP) | Voir les fiches | Très pratique pour un prototype ; **version en vigueur seulement**, pas l'historique |
| **HF [`AgentPublic/legi`](https://huggingface.co/datasets/AgentPublic/legi)** (DINUM / Albert, collection « MediaTech ») | LEGI complet, **tous états** (VIGUEUR, MODIFIE, ABROGE…), découpé par code, en chunks vectorisés **BGE-M3** | Mis à jour quotidiennement (26/09/2026) | etalab-2.0 | **Historique complet du CGI prêt à l'emploi** (fichier CGI de 262 Mo avec embeddings). Existent aussi `AgentPublic/constit`, `cnil`, `dole` |
| HF `antoinejeannot/jurisprudence`, `artefactory/Argimi-Legal-French-Jurisprudence` | Jurisprudence judiciaire (Judilibre) | 2025 | Voir les fiches | À évaluer |
| [**Catala**](https://github.com/CatalaLang/catala) | Langage de programmation littéraire du droit. [catala-examples](https://github.com/CatalaLang/catala-examples) contient `impot_revenu/` (`cgi_revenus.catala_fr`, `archives_cgi.catala_fr`, `modèle_convention_fiscale_ocde.catala_fr`…), `allocations_familiales`, `aides_logement`, `droit_successions` | Très actif, 2 396 étoiles | Apache-2.0 | Formalisation exécutable de fragments du CGI : oracle de test pour l'IA |
| [**Mlang**](https://github.com/MLanguage/mlang) | « Compiler for the M language, used to compute the income tax of French taxpayers » (langage M de la calculette IR de la DGFiP) | Push janv. 2026 | Voir le dépôt | Référence de calcul officielle de l'IR |
| [**OpenFisca-France**](https://github.com/openfisca/openfisca-france) | Modèle du système socio-fiscal (IR, prestations…), paramètres datés avec références législatives ; [explorateur de législation](https://legislation.fr.openfisca.org/swagger) | Actif (push 25/09/2026), 312 étoiles | **AGPL-3.0** | Barèmes et paramètres historisés, vérification de calculs |

---

## 10. Volumes en tokens du noyau fiscal

### 10.1 Méthode

- **Textes mesurés** : téléchargement des Parquet HF (`louisbrulenaudet/*` pour la version en vigueur ; `AgentPublic/legi` pour **toutes les versions**, en réassemblant les chunks par `doc_id`), puis comptage.
- **Tokenizers** : o200k_base (GPT-4o) et cl100k_base (GPT-4) via tiktoken, plus trois tokenizers open (Llama 3.1, Qwen 2.5, Mistral v0.3) via `tokenizers`.
- **Ratios mesurés (caractères par token)** :

| Tokenizer | CGI (texte législatif) | BOFiP (échantillon de 600 docs) |
|---|---|---|
| o200k (GPT-4o) | **4,26** | **4,03** |
| cl100k (GPT-4) | 3,60 | 3,46 |
| Llama 3.1 | 3,61 | 3,46 |
| Qwen 2.5 | 3,54 | 3,34 |
| Mistral v0.3 (vocabulaire 32k) | 3,21 | 2,92 |

  L'heuristique « 1 token ≈ 3,5 à 4 caractères » est donc **correcte pour les tokenizers de 100 à 200k tokens**. Les tokenizers à petit vocabulaire produisent 20 à 35 % de tokens en plus.
- **Tokenizer Claude.** Il n'est pas public et n'a pas été mesuré. **Il faut compter via l'endpoint `count_tokens` de l'API Anthropic** avant tout dimensionnement de contexte ou de cache. Les chiffres ci-dessous sont donnés en **o200k (bas de fourchette)** avec un **haut de fourchette ×1,2 à ×1,35**.

### 10.2 Résultats

| Corpus | Documents | Caractères | Tokens o200k | Fourchette tous tokenizers | Statut |
|---|---|---|---|---|---|
| **CGI** (livre, en vigueur) | 2 030 à 2 409 articles | 3,8 à 4,9 M | **0,89 à 1,14 M** | 1,1 à 1,5 M | [Mesuré] (écart entre instantanés 2025 et 2026 et selon qu'on inclut ABROGE_DIFF/VIGUEUR_DIFF) |
| CGI annexe I | 71 | 45 à 48 k | 0,01 M | 0,01 à 0,015 M | [Mesuré] |
| CGI annexe II | 669 à 686 | 0,72 à 0,75 M | 0,16 à 0,18 M | 0,2 à 0,24 M | [Mesuré] |
| CGI annexe III | 1 114 à 1 122 | 1,29 à 1,34 M | 0,30 à 0,32 M | 0,36 à 0,43 M | [Mesuré] |
| CGI annexe IV | 477 | 0,61 à 0,62 M | 0,15 M | 0,17 à 0,2 M | [Mesuré] |
| **CGI + annexes I-IV (en vigueur)** | ≈ 4 400 à 4 800 | ≈ 6,5 à 7,7 M | **≈ 1,5 à 1,8 M** | **1,8 à 2,4 M** | [Mesuré] |
| **LPF** (en vigueur, avec DIFF) | 973 à 1 006 | 0,88 à 0,98 M | **0,20 à 0,22 M** | 0,24 à 0,3 M | [Mesuré] |
| **CIBS** (en vigueur) | 1 482 (VIGUEUR) à 3 135 (avec VIGUEUR_DIFF) | 0,62 à 1,47 M | **0,16 à 0,37 M** | 0,2 à 0,5 M | [Mesuré] (beaucoup d'articles à entrée en vigueur différée à cause de la recodification) |
| CGI + annexes, **toutes versions** depuis 1950 | 34 814 versions d'articles | ≈ 87 M | **≈ 20,4 M** | 24 à 27 M | [Mesuré] (AgentPublic, 09/2026) |
| LPF, toutes versions | 3 417 | 3,6 M | 0,81 M | 1,0 à 1,1 M | [Mesuré] |
| CIBS, toutes versions | 4 747 | 2,4 M | 0,60 M | 0,7 à 0,8 M | [Mesuré] |
| **BOFiP en vigueur** (contenus) | 6 212 | 68,8 M | **17,1 M** | 19,9 à 23,5 M | [Mesuré] (instantané de juillet 2025) |
| BOFiP actualités | 2 592 | 5,3 M | 1,4 M | 1,6 à 1,8 M | [Mesuré] |
| **BOFiP complet en vigueur** | 8 804 (9 148 en sept. 2026) | 74 M | **≈ 18,5 M** (≈ 19,2 M rapporté à 9 148 docs) | **21 à 25 M** | [Mesuré] + extrapolation linéaire |
| BOFiP toutes versions depuis 2012 | ? | ? | **≈ 40 à 70 M** | | [Estimation] (hypothèse : 2 à 4 versions en moyenne par document sur 14 ans ; non vérifié) |
| **Voies et moyens t. II** (PLF 2026) | 252 p. | 0,62 M | **≈ 0,16 M** | 0,19 à 0,22 M | [Mesuré] (extraction PDF avec pypdf) |
| **Jurisprudence fiscale CE, 20 ans** | ≈ 20 000 décisions | | **≈ 30 M** (20 à 45 M) | 35 à 60 M | [Estimation], voir ci-dessous |
| Jurisprudence fiscale CAA, par an | ≈ 3 300 arrêts/an | | ≈ 12 M par an | | [Estimation] |
| QPC fiscales (1 022 QPC, ≈ 162 fiscales) | 162 | | 0,43 M | 0,5 à 0,6 M | [Mesuré] (heuristique) |

**Détail de l'estimation pour la jurisprudence fiscale du CE**

- **[Mesuré]** Six mois échantillonnés dans l'open data CE (06/2022, 11/2023, 03/2024, 03/2025, 10/2025, 02/2026) : **537 à 948 décisions par mois** (moyenne ≈ 690, soit ≈ 8 300 par an, ordonnances comprises).
- **[Mesuré]** Part « fiscale », identifiée par une regex sur « code général des impôts », « livre des procédures fiscales », « impôt sur le revenu / les sociétés », « TVA », « cotisation foncière », « droits de mutation »… : **10 à 19 %** selon le mois (≈ 12 % en régime courant), soit **≈ 60 à 146 décisions par mois** et **≈ 1 000 par an**.
- **[Mesuré]** Taille moyenne d'une décision fiscale CE : **1 330 à 1 960 tokens** (o200k). Beaucoup de décisions de non-admission des pourvois (code D) sont courtes.
- **[Estimation]** 20 ans × ≈ 1 000 décisions × ≈ 1 500 tokens ≈ **30 M tokens** (fourchette 20 à 45 M).
- **Limites** :
  - avant 2021, seule une **sélection** des décisions CE est disponible (JADE, ArianeWeb) ; le volume réellement récupérable pour 2006-2021 est donc probablement plus faible ;
  - les décisions anciennes (style « considérant ») sont un peu plus longues ;
  - les **conclusions des rapporteurs publics** (ArianeWeb, sélection depuis 2007, souvent 5 000 à 15 000 tokens chacune) ne sont pas comptées.
- **[Mesuré]** CAA en mars 2025 : 2 547 arrêts, dont 278 fiscaux (10,9 %), 3 628 tokens en moyenne. **[Estimation]** ≈ 12 M tokens de jurisprudence fiscale CAA par an ; les TA ne sont pas estimés (≈ 75 Mo de ZIP par mois).

### 10.3 Lecture des ordres de grandeur

- **Tient dans 1 M tokens** : CGI (livre) en vigueur **ou** annexes + LPF + CIBS, **mais pas CGI + annexes + LPF + CIBS ensemble** (≈ 1,9 à 2,4 M tokens en o200k).
- **Ne tient pas** : le BOFiP (≈ 20 M), la jurisprudence (dizaines de millions de tokens), l'historique des versions (≈ 20 M rien que pour le CGI et ses annexes).
- **Total plausible d'un corpus fiscal « large »** (textes en vigueur + BOFiP + 20 ans de CE + CAA récentes + QPC + CJUE fiscale + conventions + V&M + rapports) : **≈ 100 à 200 M tokens** **[Estimation]**, avant déduplication et hors historique.

---

## 11. Recommandations pour le pipeline

1. **Textes** : partir de **LEGI (dump DILA)** avec **legi.py** (SQLite versionné) ou du jeu **AgentPublic/legi** pour aller vite. Garder `LEGIARTI` × (`DATE_DEBUT`, `DATE_FIN`, `ETAT`) comme clé temporelle, et les `LIENS` pour le graphe de citations et de modifications. Appliquer quotidiennement les incréments DILA.
2. **BOFiP** : ingérer le **stock mensuel**, puis **archiver chaque flux hebdomadaire** (sinon l'historique est perdu), en exploitant les `dc:relation` pour relier la doctrine aux articles. Pour les versions antérieures déjà publiées, récupérer les pages « versions antérieures » du site, en respectant ses conditions d'accès.
3. **Jurisprudence administrative** : télécharger les **ZIP mensuels CE et CAA** de opendata.justice-administrative.fr (exhaustifs depuis 2021-2022), compléter par **JADE** pour l'antériorité, et filtrer le fiscal par formation (3e, 8e, 9e et 10e chambres pour le CE), par type de recours et par citations CGI/LPF, plutôt que par une simple regex.
4. **Judiciaire** : API **Judilibre** `/export` (1 000 décisions par lot) pour la chambre commerciale et le fiscal judiciaire, avec synchronisation via `/transactionalhistory`.
5. **UE** : sélection par **SPARQL CELLAR** (matière `FISC`, domaines EuroVoc), puis téléchargement XHTML ou Formex.
6. **Dimensionnement** : recompter l'ensemble avec le **tokenizer du modèle cible** (Anthropic `count_tokens`) avant de concevoir le cache ou le chargement en contexte.

---

## 12. Sources

**DILA / Légifrance**
- Serveur open data DILA : https://echanges.dila.gouv.fr/OPENDATA/ (listings consultés le 27/09/2026)
- LEGI : https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides
- JORF : https://www.data.gouv.fr/datasets/jorf-les-donnees-de-l-edition-lois-et-decrets-du-journal-officiel
- JADE : https://www.data.gouv.fr/datasets/jade
- CASS : https://www.data.gouv.fr/datasets/cass
- INCA : https://www.data.gouv.fr/datasets/inca
- CAPP : https://www.data.gouv.fr/datasets/capp
- DTD Légifrance : https://echanges.dila.gouv.fr/OPENDATA/DTD_LEGIFRANCE/
- Avertissement données personnelles : https://echanges.dila.gouv.fr/OPENDATA/AVERTISSEMENT-Donnees_a_caractere_personnel.pdf
- Open data et API Légifrance : https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api
- FAQ API Légifrance : https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api
- CGU API Légifrance : https://www.legifrance.gouv.fr/contenu/Media/files/pied-de-page/cgu-legifrance-api-vf-15-12-2022_0.pdf
- Dataservice Légifrance : https://www.data.gouv.fr/dataservices/legifrance

**Décisions de justice**
- Ministère de la Justice, open data : https://www.justice.gouv.fr/documentation/open-data-decisions-justice
- Calendrier (source secondaire) : https://www.capstan.fr/articles/1283-open-data-des-decisions-de-justice-le-calendrier-est-fixe/
- Justice administrative : https://opendata.justice-administrative.fr/ ; CGU : https://opendata.justice-administrative.fr/cgu.html
- ArianeWeb : https://conseil-etat.fr/actualites/arianeweb-130-000-decisions-de-jurisprudence-administrative-en-ligne-gratuitement ; https://jurisguide.univ-paris1.fr/fiches-documentaires/arianeweb-1
- Judilibre : https://www.data.gouv.fr/dataservices/api-judilibre ; https://github.com/Cour-de-cassation/judilibre-search ; spécification : https://github.com/Cour-de-cassation/judilibre-search/blob/dev/public/JUDILIBRE-public.json ; CGU : https://piste.gouv.fr/images/cgu/CGU_open_data_V8.pdf ; https://www.avocatparis.org/actualites/judilibre-lopen-data-des-decisions-de-justice-cest-maintenant ; https://stats.judilibre.io/

**BOFiP**
- Archives : https://data.economie.gouv.fr/explore/dataset/bofip-impots/
- Documentation technique : https://data.economie.gouv.fr/api/v2/catalog/datasets/bofip-impots/attachments/bofip_documentation_pdf
- Publications en vigueur : https://www.data.gouv.fr/datasets/bofip-impots-publications-en-vigueur
- Versions antérieures : https://bofip.impots.gouv.fr/bofip/12556-PGP.html/ACTU-2020-00272-0
- Archives antérieures à 2012 : https://bofip-archives.impots.gouv.fr/

**International / UE**
- Conventions : https://www.impots.gouv.fr/les-conventions-internationales ; https://bofip.impots.gouv.fr/bofip/2509-PGP.html/identifiant=BOI-ANNX-000306-20260429 ; https://bofip.impots.gouv.fr/bofip/14862-PGP.html/ACTU-2025-00179
- EUR-Lex webservice : https://eur-lex.europa.eu/content/help/data-reuse/webservice.html
- Guide d'extraction EUR-Lex : https://eur-lex.europa.eu/content/tools/webservices/DataExtractionUsingWebServices.pdf
- Décision 2011/833 : https://eur-lex.europa.eu/eli/dec/2011/833/oj/eng
- Point SPARQL CELLAR : https://publications.europa.eu/webapi/rdf/sparql

**Parlement, budget, contrôle**
- AN, questions écrites : https://data.assemblee-nationale.fr/travaux-parlementaires/questions/questions-ecrites
- Sénat, base Questions : https://data.senat.fr/la-base-questions/
- Voies et moyens t. II : https://www.budget.gouv.fr/documentation/documents-annexes-evaluation/evaluations-voies-moyens-tome-2 ; PLF 2026 : https://www.budget.gouv.fr/documentation/file-download/30586 ; PLF 2025 : https://www2.assemblee-nationale.fr/static/17/Annexes-DL/PLF-2025/Voies_et_moyens_Tome_2_2025.pdf
- Jeux tableur V&M : https://www.data.gouv.fr/datasets/plf2023-voies-et-moyens-t2-liste-des-depenses-fiscales ; https://www.data.gouv.fr/datasets/plf-2024-vm-tome-2-depenses-fiscales
- Cour des comptes : https://www.ccomptes.fr/sites/default/files/2026-04/NEB-2026-Depenses-fiscales.pdf ; https://www.ccomptes.fr/fr/mentions-legales

**Outils**
- legi.py : https://github.com/Legilibre/legi.py
- Archeo-Lex : https://github.com/Legilibre/Archeo-Lex
- Tricoteuses : https://git.tricoteuses.fr/logiciels/tricoteuses-legifrance
- Hugging Face : https://huggingface.co/datasets/louisbrulenaudet/code-impots ; https://huggingface.co/datasets/louisbrulenaudet/bofip ; https://huggingface.co/datasets/AgentPublic/legi
- Catala : https://github.com/CatalaLang/catala ; https://github.com/CatalaLang/catala-examples
- Mlang : https://github.com/MLanguage/mlang
- OpenFisca-France : https://github.com/openfisca/openfisca-france
