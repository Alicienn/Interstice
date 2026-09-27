"""Ingestion du BOFiP : archives tar (stock mensuel, flux hebdomadaires) et actualités (jeu bofip-vigueur).

Règles de version (indépendantes de l'ordre d'application) pour un document de clé PGP :
- absent de la base → inséré (« nouveau ») ;
- date de publication plus récente que la version courante → la courante passe dans
  `bofip_versions` (motif « remplacée ») et la nouvelle devient courante (« remplacé ») ;
- même date, même HTML → métadonnées rafraîchies (« identique ») ;
- même date, HTML différent → la courante est archivée (« corrigée ») et remplacée (« corrigé ») ;
- date plus ancienne → rangée dans `bofip_versions` (motif « antérieure ») sans toucher la courante.
Un **stock** (ou un instantané d'actualités) est une photographie complète : les documents courants
qu'il ne contient plus, publiés au plus tard à sa date, sont archivés (motif « retirée »).

Chaque archive n'est ingérée qu'une fois (table `bofip_ingestion`, contrôle du sha256).
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
import sqlite3
import tarfile
import time
from collections import Counter
from importlib.resources import files
from pathlib import Path

from interstice.bofip.parser import (CheminDoc, analyser_chemin, boi_base, corps_html, html_vers_texte_bofip,
                                     lire_document_xml)

COLONNES = ("pgp", "boi", "boi_base", "nature", "type_contenu", "niveau", "serie", "division", "titre",
            "date_publication", "permalien", "createur", "html", "texte", "sha256", "archive", "chemin")
_RE_PGP_URL = re.compile(r"/(\d+-PGP)\.html")
_RE_SERIE_DIV = re.compile(r"S[ée]ries?\s*/\s*Divisions?\s*:\s*\n?\s*([A-Z]+)(?:\s*-\s*([A-Z0-9]+))?")


def init_schema_bofip(conn: sqlite3.Connection) -> None:
    conn.executescript(files("interstice.store").joinpath("schema_bofip.sql").read_text("utf-8"))


def meta_set(conn: sqlite3.Connection, cle: str, valeur: str) -> None:
    conn.execute("INSERT OR REPLACE INTO bofip_meta(cle, valeur) VALUES (?, ?)", (cle, valeur))


def meta_get(conn: sqlite3.Connection, cle: str) -> str | None:
    r = conn.execute("SELECT valeur FROM bofip_meta WHERE cle = ?", (cle,)).fetchone()
    return r[0] if r else None


def _sha256_fichier(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------ versions

def appliquer_version(conn: sqlite3.Connection, doc: dict, relations: list[tuple[str, str, str]] | None,
                      archive: str) -> str:
    cur = conn.execute("SELECT * FROM bofip_documents WHERE pgp = ?", (doc["pgp"],)).fetchone()
    if cur is None:
        _ecrire_courante(conn, doc, relations)
        return "nouveau"
    d_new, d_cur = doc["date_publication"] or "", cur["date_publication"] or ""
    if d_new > d_cur:
        _archiver(conn, cur, "remplacée", archive)
        _ecrire_courante(conn, doc, relations)
        return "remplace"
    if d_new == d_cur:
        if doc["sha256"] == cur["sha256"]:
            _ecrire_courante(conn, doc, relations)  # métadonnées et relations les plus récentes
            return "identique"
        _archiver(conn, cur, "corrigée", archive)
        _ecrire_courante(conn, doc, relations)
        return "corrige"
    conn.execute(f"INSERT OR IGNORE INTO bofip_versions({','.join(COLONNES)}, motif, archive_motif) "
                 f"VALUES ({','.join('?' * len(COLONNES))}, 'antérieure', ?)",
                 [doc[c] for c in COLONNES] + [archive])
    return "anterieur"


def _ecrire_courante(conn, doc: dict, relations) -> None:
    conn.execute(f"INSERT OR REPLACE INTO bofip_documents({','.join(COLONNES)}) VALUES ({','.join('?' * len(COLONNES))})",
                 [doc[c] for c in COLONNES])
    if relations is not None:
        conn.execute("DELETE FROM bofip_relations WHERE pgp = ?", (doc["pgp"],))
        conn.executemany("INSERT INTO bofip_relations VALUES (?,?,?,?,?)",
                         [(doc["pgp"], i, t, ct, c) for i, (t, ct, c) in enumerate(relations)])


def _archiver(conn, cur: sqlite3.Row, motif: str, archive: str) -> None:
    conn.execute(f"INSERT OR IGNORE INTO bofip_versions({','.join(COLONNES)}, motif, archive_motif) "
                 f"VALUES ({','.join('?' * len(COLONNES))}, ?, ?)", [cur[c] for c in COLONNES] + [motif, archive])


def _retirer_absents(conn, nature: str, vus: set[str], date: str, archive: str) -> int:
    rows = conn.execute("SELECT * FROM bofip_documents WHERE nature = ? AND date_publication <= ?",
                        (nature, date)).fetchall()
    n = 0
    for r in rows:
        if r["pgp"] not in vus:
            _archiver(conn, r, "retirée", archive)
            conn.execute("DELETE FROM bofip_documents WHERE pgp = ?", (r["pgp"],))
            conn.execute("DELETE FROM bofip_relations WHERE pgp = ?", (r["pgp"],))
            n += 1
    return n


# ------------------------------------------------------------------------ archives tar

def _doc_contenu(ch: CheminDoc, fichiers: dict[str, bytes], archive: str):
    meta = lire_document_xml(fichiers["document.xml"])
    if meta.pgp != ch.pgp:
        raise ValueError(f"PGP du répertoire {ch.pgp} ≠ dc:identifier {meta.pgp}")
    ref = next((r for t, r in meta.fichiers if r), "data.html")
    if ref not in fichiers:
        raise ValueError(f"fichier de données {ref} absent")
    brut = fichiers[ref]
    html = corps_html(brut.decode("utf-8"))
    if meta.date and meta.date != ch.date:
        raise ValueError(f"dc:date {meta.date} ≠ répertoire {ch.date}")
    if not meta.boi:
        raise ValueError("bofip:contenu_id absent")
    serie = meta.sujets[0] if meta.sujets else ch.serie_dossier
    division = meta.sujets[1] if len(meta.sujets) > 1 else None
    doc = {"pgp": ch.pgp, "boi": meta.boi, "boi_base": boi_base(meta.boi), "nature": "Contenu",
           "type_contenu": meta.type_contenu or ch.type_contenu_dossier, "niveau": meta.niveau,
           "serie": serie, "division": division, "titre": meta.titre, "date_publication": ch.date,
           "permalien": meta.permalien, "createur": meta.createur, "html": html,
           "texte": html_vers_texte_bofip(html), "sha256": hashlib.sha256(brut).hexdigest(),
           "archive": archive, "chemin": ch.repertoire}
    return doc, meta.relations


def ingerer_archive(conn: sqlite3.Connection, path: Path, info: dict | None = None, verbeux: bool = True) -> dict:
    """Ingère une archive tar.gz du BOFiP (stock ou flux). Retourne les statistiques."""
    info = info or {}
    nom = path.name
    sha = info.get("sha256") or _sha256_fichier(path)
    typ = info.get("type") or ("stock" if "_stock_" in nom else "flux")
    date = info.get("fin") or re.findall(r"(\d{8})", nom)[-1]
    if len(date) == 8:
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    debut = dt.datetime.now().isoformat(timespec="seconds")
    t0 = time.time()
    ev: Counter = Counter()
    par_type: Counter = Counter()
    membres = 0
    erreurs: list[tuple[str, str]] = []
    vus_contenu: set[str] = set()
    traites: set[str] = set()

    conn.execute("BEGIN")
    conn.execute("DELETE FROM bofip_erreurs WHERE archive = ?", (nom,))

    def traiter(ch: CheminDoc, fichiers: dict[str, bytes], tailles: dict[str, tuple[int, str]]) -> None:
        if ch.repertoire in traites:
            erreurs.append((ch.repertoire, "répertoire non contigu dans l'archive (lu en deux fois)"))
        traites.add(ch.repertoire)
        par_type[ch.type_document] += 1
        try:
            if ch.type_document == "Contenu":
                vus_contenu.add(ch.pgp)  # même illisible : ne doit pas être « retiré » par le stock
            if "document.xml" not in fichiers:
                raise ValueError("document.xml absent")
            if ch.type_document == "Contenu":
                doc, rel = _doc_contenu(ch, fichiers, nom)
                ev[appliquer_version(conn, doc, rel, nom)] += 1
            elif ch.type_document == "PlanClassement":
                meta = lire_document_xml(fichiers["document.xml"])
                ref = next((r for t, r in meta.fichiers if r), "data.xml")
                xml = fichiers[ref]
                from interstice.bofip.parser import lire_plan
                lire_plan(xml)  # contrôle de validité
                conn.execute("INSERT OR REPLACE INTO bofip_plans_publies VALUES (?,?,?,?)",
                             (ch.date, nom, hashlib.sha256(xml).hexdigest(), xml.decode("utf-8")))
            elif ch.type_document in ("Image", "Attachment"):
                meta = lire_document_xml(fichiers["document.xml"])
                requis = [c for t, ct, c in meta.relations if t.lower().startswith("isrequired")]
                parts = meta.fichiers or [(meta.format or "", n) for n in tailles if n != "document.xml"]
                for mime, ref in parts:
                    if ref not in tailles:
                        raise ValueError(f"fichier {ref} annoncé mais absent")
                    taille, h = tailles[ref]
                    conn.execute("INSERT OR REPLACE INTO bofip_fichiers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 (ch.pgp, ch.date, ch.type_document, meta.titre, mime or meta.format, ref, taille,
                                  h, json.dumps(requis), nom, ch.repertoire))
                autres = set(tailles) - {r for _, r in parts} - {"document.xml"}
                if autres:
                    raise ValueError(f"fichiers non déclarés dans document.xml : {sorted(autres)}")
            else:
                raise ValueError(f"type de document inconnu : {ch.type_document}")
        except Exception as e:  # noqa: BLE001 — toute erreur est tracée, l'ingestion continue
            erreurs.append((ch.repertoire, f"{type(e).__name__}: {e}"))

    courant: CheminDoc | None = None
    fichiers: dict[str, bytes] = {}
    tailles: dict[str, tuple[int, str]] = {}
    try:
        with tarfile.open(path, "r|gz") as tar:
            for m in tar:
                membres += 1
                if not m.isfile():
                    continue
                a = analyser_chemin(m.name)
                if a is None:
                    if not re.match(r"^(?:\./)?BOFiP/infos/[^/]+\.dtd$", m.name):
                        erreurs.append((m.name, "membre inattendu (hors arborescence documents/infos)"))
                    continue
                ch, fichier = a
                if courant is not None and ch.repertoire != courant.repertoire:
                    traiter(courant, fichiers, tailles)
                    fichiers, tailles = {}, {}
                courant = ch
                data = tar.extractfile(m).read()
                tailles[fichier] = (len(data), hashlib.sha256(data).hexdigest())
                if fichier.endswith((".xml", ".html", ".htm")):
                    fichiers[fichier] = data
            if courant is not None:
                traiter(courant, fichiers, tailles)
    except BaseException:  # archive illisible ou interruption : rien n'est écrit
        conn.execute("ROLLBACK")
        raise

    if typ == "stock":
        ev["retire"] += _retirer_absents(conn, "Contenu", vus_contenu, date, nom)
    conn.executemany("INSERT INTO bofip_erreurs VALUES (?,?,?)", [(nom, c, msg) for c, msg in erreurs])
    conn.execute("INSERT OR REPLACE INTO bofip_ingestion VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (nom, typ, date, sha, membres, sum(par_type.values()), json.dumps(dict(par_type)),
                  ev["nouveau"], ev["remplace"], ev["anterieur"], ev["identique"], ev["corrige"], ev["retire"],
                  len(erreurs), debut, dt.datetime.now().isoformat(timespec="seconds")))
    conn.execute("COMMIT")
    stats = {"archive": nom, "type": typ, "documents": dict(par_type), **{k: ev[k] for k in
             ("nouveau", "remplace", "anterieur", "identique", "corrige", "retire")},
             "erreurs": len(erreurs), "secondes": round(time.time() - t0, 1)}
    if verbeux:
        print(f"  {stats}", flush=True)
    return stats


# ------------------------------------------------------------------------ actualités (jeu bofip-vigueur)

def html_actualite(contenu_html: str | None) -> str:
    """Le champ `contenu_html` de l'export double les guillemets (échappement CSV) : on les rétablit."""
    return (contenu_html or "").replace('""', '"')


def ingerer_actualites(conn: sqlite3.Connection, path: Path, info: dict | None = None, verbeux: bool = True) -> dict:
    """Ingère un instantané JSON(.gz) des actualités du jeu « publications en vigueur »."""
    info = info or {}
    nom = path.name
    sha = info.get("sha256") or _sha256_fichier(path)
    date = info.get("fin") or re.findall(r"(\d{8})", nom)[-1]
    if len(date) == 8:
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    debut = dt.datetime.now().isoformat(timespec="seconds")
    t0 = time.time()
    ouvrir = gzip.open if nom.endswith(".gz") else open
    with ouvrir(path, "rb") as f:
        recs = json.loads(f.read().decode("utf-8"))
    ev: Counter = Counter()
    erreurs: list[tuple[str, str]] = []
    vus: set[str] = set()
    conn.execute("BEGIN")
    conn.execute("DELETE FROM bofip_erreurs WHERE archive = ?", (nom,))
    for i, r in enumerate(recs):
        cle = r.get("identifiant_juridique") or f"enregistrement {i}"
        try:
            if r.get("type") != "Actualité":
                continue
            m = _RE_PGP_URL.search(r.get("permalien") or "")
            if not m:
                raise ValueError(f"permalien sans PGP : {r.get('permalien')}")
            vus.add(m.group(1))
            html = html_actualite(r.get("contenu_html"))
            sd = _RE_SERIE_DIV.search(r.get("contenu") or "")
            doc = {"pgp": m.group(1), "boi": r.get("identifiant_juridique"), "boi_base": r.get("identifiant_juridique"),
                   "nature": "Actualité", "type_contenu": "Actualité", "niveau": None,
                   "serie": r.get("serie") or (sd.group(1) if sd else None),
                   "division": r.get("division") or (sd.group(2) if sd else None),
                   "titre": r.get("titre"), "date_publication": r.get("debut_de_validite"),
                   "permalien": r.get("permalien"), "createur": None, "html": html,
                   "texte": html_vers_texte_bofip(html), "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                   "archive": nom, "chemin": f"{nom}#{r.get('identifiant_juridique')}"}
            if not doc["date_publication"]:
                raise ValueError("debut_de_validite absent")
            ev[appliquer_version(conn, doc, None, nom)] += 1
        except Exception as e:  # noqa: BLE001
            erreurs.append((cle, f"{type(e).__name__}: {e}"))
    ev["retire"] += _retirer_absents(conn, "Actualité", vus, date, nom)
    conn.executemany("INSERT INTO bofip_erreurs VALUES (?,?,?)", [(nom, c, msg) for c, msg in erreurs])
    conn.execute("INSERT OR REPLACE INTO bofip_ingestion VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (nom, "vigueur-actualites", date, sha, len(recs), len(vus), json.dumps({"Actualité": len(vus)}),
                  ev["nouveau"], ev["remplace"], ev["anterieur"], ev["identique"], ev["corrige"], ev["retire"],
                  len(erreurs), debut, dt.datetime.now().isoformat(timespec="seconds")))
    conn.execute("COMMIT")
    stats = {"archive": nom, "type": "vigueur-actualites", "documents": {"Actualité": len(vus)},
             **{k: ev[k] for k in ("nouveau", "remplace", "anterieur", "identique", "corrige", "retire")},
             "erreurs": len(erreurs), "secondes": round(time.time() - t0, 1)}
    if verbeux:
        print(f"  {stats}", flush=True)
    return stats


# ------------------------------------------------------------------------ chaîne complète

def ingerer_chaine(conn: sqlite3.Connection, paths: list[Path], manifest: dict[str, dict] | None = None,
                   conn_legi: sqlite3.Connection | None = None, forcer: bool = False, verbeux: bool = True) -> list[dict]:
    """Ingère les archives non encore traitées (dans l'ordre donné), puis reconstruit plan, renvois et FTS."""
    from interstice.bofip.plan import construire_plan
    from interstice.bofip.renvois import construire_renvois_bofip

    init_schema_bofip(conn)
    manifest = manifest or {}
    faites = {r[0]: r[1] for r in conn.execute("SELECT archive, sha256 FROM bofip_ingestion")}
    stats = []
    for p in paths:
        info = manifest.get(p.name, {})
        sha = info.get("sha256") or _sha256_fichier(p)
        if not forcer and faites.get(p.name) == sha:
            continue
        if verbeux:
            print(f"Ingestion {p.name}", flush=True)
        info = {**info, "sha256": sha}
        if p.name.endswith((".json", ".json.gz")):
            stats.append(ingerer_actualites(conn, p, info, verbeux))
        else:
            stats.append(ingerer_archive(conn, p, info, verbeux))
    if verbeux:
        print("Plan de classement…", flush=True)
    s_plan = construire_plan(conn)
    if verbeux:
        print(f"  {s_plan}", flush=True)
    if verbeux:
        print("Renvois vers les articles de loi…", flush=True)
    r = construire_renvois_bofip(conn, conn_legi)
    if verbeux:
        print(f"  {r}", flush=True)
        print("Index plein texte…", flush=True)
    reconstruire_fts_bofip(conn)
    return stats


def reconstruire_fts_bofip(conn: sqlite3.Connection) -> float:
    t0 = time.time()
    conn.execute("DROP TABLE IF EXISTS bofip_fts")
    conn.execute(
        """CREATE VIRTUAL TABLE bofip_fts USING fts5(
               titre, texte, content='bofip_documents', content_rowid='rowid',
               tokenize="unicode61 remove_diacritics 2")""")
    conn.execute("INSERT INTO bofip_fts(bofip_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO bofip_fts(bofip_fts) VALUES ('optimize')")
    return time.time() - t0
