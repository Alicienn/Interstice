-- Corpus LEGI. Une ligne par objet XML ; rien n'est filtré à l'ingestion.
-- Dates au format AAAA-MM-JJ ; '2999-01-01' = pas de fin connue (convention DILA).
-- `archive` / `chemin` : provenance exacte du fichier retenu (dernière archive qui l'a fourni).

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS textes (            -- texte/version/LEGITEXT… (version d'un texte)
    id TEXT PRIMARY KEY, cid TEXT NOT NULL, nature TEXT, titre TEXT, titrefull TEXT, etat TEXT,
    date_debut TEXT, date_fin TEXT, num TEXT, nor TEXT, date_publi TEXT, date_texte TEXT,
    derniere_modification TEXT, versions_a_venir TEXT, autorite TEXT, ministere TEXT,
    visas_html TEXT, signataires_html TEXT, tp_html TEXT, nota_html TEXT, abro_html TEXT, rect_html TEXT,
    archive TEXT NOT NULL, chemin TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS textes_cid ON textes(cid);

CREATE TABLE IF NOT EXISTS textes_struct (      -- texte/struct/LEGITEXT… (racine du sommaire)
    id TEXT PRIMARY KEY, cid TEXT NOT NULL, nature TEXT, derniere_modification TEXT, versions TEXT,
    archive TEXT NOT NULL, chemin TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS textes_struct_cid ON textes_struct(cid);

CREATE TABLE IF NOT EXISTS sections (           -- LEGISCTA… (une version de section)
    id TEXT PRIMARY KEY, titre TEXT, commentaire TEXT, texte_cid TEXT, contexte TEXT,
    archive TEXT NOT NULL, chemin TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sections_texte ON sections(texte_cid);

-- Arêtes du sommaire : parent (LEGITEXT de textes_struct ou LEGISCTA) → enfant (section ou article),
-- chacune avec sa propre période de validité. C'est l'arborescence versionnée.
CREATE TABLE IF NOT EXISTS sommaire (
    parent_id TEXT NOT NULL, position INTEGER NOT NULL, kind TEXT NOT NULL,
    enfant_id TEXT NOT NULL, enfant_cid TEXT, titre TEXT, etat TEXT, debut TEXT, fin TEXT, niv INTEGER,
    PRIMARY KEY (parent_id, position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS sommaire_enfant ON sommaire(enfant_id);

CREATE TABLE IF NOT EXISTS articles (           -- LEGIARTI… (une version d'article)
    id TEXT PRIMARY KEY,
    cle TEXT,                                   -- article logique : plus petit id de sa chaîne de versions
    ancien_id TEXT, num TEXT, num_norm TEXT, etat TEXT, date_debut TEXT, date_fin TEXT, type TEXT,
    texte_cid TEXT, texte_nature TEXT, texte_titre TEXT,
    contexte TEXT,                              -- JSON : niveaux du sommaire avec intitulés datés
    versions TEXT,                              -- JSON : chaîne des versions telle que publiée
    nota_html TEXT, html TEXT, texte TEXT,      -- texte = html converti en texte brut
    archive TEXT NOT NULL, chemin TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS articles_texte_num ON articles(texte_cid, num_norm);
CREATE INDEX IF NOT EXISTS articles_cle ON articles(cle);

CREATE TABLE IF NOT EXISTS liens (              -- <LIENS> de chaque version d'article
    article_id TEXT NOT NULL, position INTEGER NOT NULL, typelien TEXT, sens TEXT,
    cible_id TEXT, cidtexte TEXT, naturetexte TEXT, num TEXT, numtexte TEXT,
    datesignatexte TEXT, nortexte TEXT, libelle TEXT,
    PRIMARY KEY (article_id, position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS liens_cible ON liens(cible_id);

-- Renvois extraits du texte des articles (voir interstice.graph.citations)
CREATE TABLE IF NOT EXISTS renvois (
    article_id TEXT NOT NULL, position INTEGER NOT NULL, brut TEXT, num TEXT,
    cible_cid TEXT, cible_cle TEXT, plage TEXT, formule TEXT,
    PRIMARY KEY (article_id, position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS renvois_cible ON renvois(cible_cle);

CREATE TABLE IF NOT EXISTS eli (                -- eli/…/versions.xml
    chemin_eli TEXT PRIMARY KEY, versions TEXT, archive TEXT NOT NULL
);

-- Traçabilité de l'ingestion (preuve d'exhaustivité)
CREATE TABLE IF NOT EXISTS ingestion (
    archive TEXT PRIMARY KEY, sha256 TEXT, stamp TEXT, membres INTEGER, repertoires INTEGER,
    xml INTEGER, par_type TEXT, suppressions INTEGER, inconnus INTEGER, erreurs INTEGER,
    autres_fichiers TEXT, debut TEXT, fin TEXT
);
CREATE TABLE IF NOT EXISTS erreurs (archive TEXT, chemin TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS inconnus (archive TEXT, chemin TEXT, racine TEXT);
CREATE TABLE IF NOT EXISTS suppressions (archive TEXT, ligne TEXT, id TEXT, trouve INTEGER);
-- Même identifiant rencontré plusieurs fois dans une même archive (chemins différents)
CREATE TABLE IF NOT EXISTS doublons (archive TEXT, id TEXT, chemin_retenu TEXT, chemin_ecarte TEXT, identiques INTEGER);

CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
