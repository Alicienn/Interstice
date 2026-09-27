-- Corpus BOFiP-Impôts (doctrine administrative). Tables préfixées `bofip_`.
-- Clé stable d'un document : l'identifiant technique PGP (ex. « 739-PGP »), identique d'une version
-- à l'autre. L'identifiant juridique daté (BOI-…-AAAAMMJJ) désigne une version ; il n'est pas unique
-- dans le référentiel (quelques doublons publiés par la DGFiP), d'où la clé PGP.

PRAGMA journal_mode = WAL;

-- Version courante de chaque document : contenus (archives tar) et actualités (jeu bofip-vigueur).
CREATE TABLE IF NOT EXISTS bofip_documents (
    pgp TEXT PRIMARY KEY,
    boi TEXT,                  -- identifiant juridique daté : BOI-IR-BASE-10-20230118, ACTU-2025-00123
    boi_base TEXT,             -- sans la date : BOI-IR-BASE-10 (= boi pour une actualité)
    nature TEXT NOT NULL,      -- 'Contenu' | 'Actualité'
    type_contenu TEXT,         -- Commentaire, Barème, Formulaire, Lettre type / Modèle, Cartographie, Autres annexes, Actualité
    niveau TEXT,               -- Parent / Enfant (bofip:contenu_niveau)
    serie TEXT, division TEXT,
    titre TEXT,
    date_publication TEXT,     -- AAAA-MM-JJ (dc:date, date du BOI) = début de validité de la version
    permalien TEXT,
    createur TEXT,             -- bureau rédacteur (dc:creator)
    html TEXT,                 -- corps HTML tel que publié (liens internes « Contenu:NNN-PGP »)
    texte TEXT,                -- texte brut : intertitres en « ## », numéros de paragraphe en « § 10 »
    sha256 TEXT,               -- empreinte du HTML (identité de version)
    archive TEXT NOT NULL,     -- archive qui a fourni cette version
    chemin TEXT NOT NULL       -- répertoire dans l'archive (ou enregistrement du jeu bofip-vigueur)
);
CREATE INDEX IF NOT EXISTS bofip_documents_boi ON bofip_documents(boi);
CREATE INDEX IF NOT EXISTS bofip_documents_base ON bofip_documents(boi_base);
CREATE INDEX IF NOT EXISTS bofip_documents_serie ON bofip_documents(serie);

-- Versions antérieures (jamais écrasées) : remplacées par un flux, corrigées, ou absentes d'un stock ultérieur.
CREATE TABLE IF NOT EXISTS bofip_versions (
    pgp TEXT NOT NULL, boi TEXT, boi_base TEXT, nature TEXT, type_contenu TEXT, niveau TEXT,
    serie TEXT, division TEXT, titre TEXT, date_publication TEXT, permalien TEXT, createur TEXT,
    html TEXT, texte TEXT, sha256 TEXT NOT NULL, archive TEXT NOT NULL, chemin TEXT NOT NULL,
    motif TEXT NOT NULL,       -- 'remplacée' | 'corrigée' | 'antérieure' | 'retirée'
    archive_motif TEXT,        -- archive qui a provoqué l'archivage de la version
    PRIMARY KEY (pgp, date_publication, sha256)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS bofip_versions_boi ON bofip_versions(boi);

-- dc:relation de la version courante : references / isReferencedBy / requires / isRequiredBy
CREATE TABLE IF NOT EXISTS bofip_relations (
    pgp TEXT NOT NULL, position INTEGER NOT NULL, type TEXT NOT NULL,
    cible_type TEXT,           -- Contenu, Actualite, Image, Fichier
    cible_pgp TEXT NOT NULL,
    PRIMARY KEY (pgp, position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS bofip_relations_cible ON bofip_relations(cible_pgp);

-- Pièces jointes non textuelles (images, PDF…) : inventaire seulement, contenu non indexé.
CREATE TABLE IF NOT EXISTS bofip_fichiers (
    pgp TEXT NOT NULL, date_publication TEXT NOT NULL,
    type TEXT,                 -- Image | Attachment
    titre TEXT, mime TEXT,
    fichier TEXT,              -- nom du fichier de données (data1.pdf…)
    taille INTEGER, sha256 TEXT,
    requis_par TEXT,           -- JSON : PGP des contenus qui l'utilisent
    archive TEXT NOT NULL, chemin TEXT NOT NULL,
    PRIMARY KEY (pgp, date_publication, fichier)
) WITHOUT ROWID;

-- Plans de classement publiés (un par archive ; le plus récent sert à construire bofip_plan)
CREATE TABLE IF NOT EXISTS bofip_plans_publies (
    date TEXT NOT NULL, archive TEXT NOT NULL, sha256 TEXT, xml TEXT NOT NULL,
    PRIMARY KEY (date, archive)
) WITHOUT ROWID;

-- Arborescence de navigation : série → division → titre → chapitre → section → sous-section.
-- Chaque nœud réel est un document (noeud = PGP). origine :
--   'plan'    : nœud du plan de classement publié ;
--   'rattache': document absent du plan publié, rattaché au nœud dont le code est le plus long préfixe ;
--   'virtuel' : regroupement créé ici (actualités par année, racine des documents non classables).
CREATE TABLE IF NOT EXISTS bofip_plan (
    noeud TEXT PRIMARY KEY,
    parent TEXT,               -- NULL pour une racine (série)
    position INTEGER NOT NULL,
    libelle TEXT,
    code TEXT,                 -- code de classement (nodeId) : BOI-IR-CHAMP-20
    pgp TEXT,                  -- document du nœud (NULL pour un nœud virtuel)
    profondeur INTEGER NOT NULL,
    origine TEXT NOT NULL
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS bofip_plan_parent ON bofip_plan(parent, position);
CREATE INDEX IF NOT EXISTS bofip_plan_pgp ON bofip_plan(pgp);
CREATE INDEX IF NOT EXISTS bofip_plan_code ON bofip_plan(code);

-- Articles de loi cités dans le texte (voir interstice.bofip.renvois)
CREATE TABLE IF NOT EXISTS bofip_renvois (
    pgp TEXT NOT NULL, position INTEGER NOT NULL,
    brut TEXT,                 -- numéro tel qu'écrit
    code TEXT,                 -- sigle (CGI, CGI-AIII, LPF, CIBS…), intitulé du code ou « loi n° … » ; NULL = non déterminé
    texte_cid TEXT,            -- LEGITEXT… si le texte est connu de la base LEGI
    num TEXT,                  -- numéro (forme LEGI si résolu, sinon tel qu'écrit)
    num_norm TEXT,             -- normaliser_num(num)
    resolu INTEGER NOT NULL,   -- 1 si le numéro existe dans la base LEGI
    plage TEXT, formule TEXT,
    PRIMARY KEY (pgp, position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS bofip_renvois_article ON bofip_renvois(code, num_norm);
CREATE INDEX IF NOT EXISTS bofip_renvois_cid ON bofip_renvois(texte_cid, num_norm);

-- Traçabilité (preuve d'exhaustivité)
CREATE TABLE IF NOT EXISTS bofip_ingestion (
    archive TEXT PRIMARY KEY, type TEXT, date TEXT, sha256 TEXT,
    membres INTEGER,           -- entrées du tar (fichiers + répertoires) ou enregistrements JSON
    documents INTEGER,         -- répertoires de document lus (tous types)
    par_type TEXT,             -- JSON {Contenu: n, Image: n, Attachment: n, PlanClassement: n, Actualité: n}
    nouveaux INTEGER, remplaces INTEGER, anterieurs INTEGER, identiques INTEGER, corriges INTEGER,
    retires INTEGER, erreurs INTEGER, debut TEXT, fin TEXT
);
CREATE TABLE IF NOT EXISTS bofip_erreurs (archive TEXT, chemin TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS bofip_meta (cle TEXT PRIMARY KEY, valeur TEXT);
