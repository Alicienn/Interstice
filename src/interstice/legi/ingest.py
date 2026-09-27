"""Ingestion des archives LEGI (global + incréments) dans SQLite.

Garanties :
- chaque membre de chaque archive est compté et classé (répertoire, XML par type,
  liste de suppression, autre) ; un XML non reconnu ou invalide est journalisé, jamais ignoré ;
- les objets sont indexés par identifiant : une archive plus récente remplace la version précédente ;
- les suppressions listées par la DILA sont appliquées et tracées ;
- l'ingestion est idempotente : une archive déjà ingérée (même sha256) est sautée.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tarfile
import time
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

from lxml import etree

from interstice.legi.html import html_vers_texte
from interstice.legi.numeros import normaliser_num
from interstice.legi.parser import (Article, EliVersions, Inconnu, Section, TexteStruct, TexteVersion,
                                    LienStruct, parse)
from interstice.store.db import meta_set

LOT = 500  # fichiers par lot envoyé aux processus de parsing


# ------------------------------------------------------------ côté processus de parsing

def _sommaire_rows(parent_id: str, enfants: list[LienStruct]) -> list[tuple]:
    return [(parent_id, e.position, e.kind, e.id, e.cid, e.titre, e.etat, e.debut, e.fin, e.niv) for e in enfants]


def _contexte_json(ctx) -> str:
    return json.dumps([[asdict(t) for t in niveau] for niveau in ctx.niveaux], ensure_ascii=False)


def _traiter_un(nom: str, data: bytes, mtime: int, archive: str) -> tuple:
    # res[1] = (empreinte du contenu, date de modification dans l'archive)
    digest = (hashlib.blake2b(data, digest_size=8).digest(), mtime)
    try:
        obj = parse(data)
    except etree.XMLSyntaxError as e:
        return (nom, digest, "erreur", str(e))
    if isinstance(obj, Article):
        row = (obj.id, None, obj.ancien_id, obj.num, normaliser_num(obj.num), obj.etat, obj.date_debut,
               obj.date_fin, obj.type, obj.contexte.texte_cid, obj.contexte.texte_nature, obj.contexte.texte_titre,
               _contexte_json(obj.contexte), json.dumps(obj.versions, ensure_ascii=False), obj.nota_html,
               obj.html, html_vers_texte(obj.html), archive, nom)
        liens = [(obj.id, i, l.typelien, l.sens, l.id, l.cidtexte, l.naturetexte, l.num, l.numtexte,
                  l.datesignatexte, l.nortexte, l.libelle) for i, l in enumerate(obj.liens)]
        return (nom, digest, "article", obj.id, row, liens)
    if isinstance(obj, Section):
        row = (obj.id, obj.titre, obj.commentaire, obj.contexte.texte_cid, _contexte_json(obj.contexte), archive, nom)
        return (nom, digest, "section", obj.id, row, _sommaire_rows(obj.id, obj.enfants))
    if isinstance(obj, TexteVersion):
        row = (obj.id, obj.cid, obj.nature, obj.titre, obj.titrefull, obj.etat, obj.date_debut, obj.date_fin,
               obj.num, obj.nor, obj.date_publi, obj.date_texte, obj.derniere_modification,
               json.dumps(obj.versions_a_venir), obj.autorite, obj.ministere, obj.visas_html,
               obj.signataires_html, obj.tp_html, obj.nota_html, obj.abro_html, obj.rect_html, archive, nom)
        return (nom, digest, "texte", obj.id, row)
    if isinstance(obj, TexteStruct):
        row = (obj.id, obj.cid, obj.nature, obj.derniere_modification,
               json.dumps(obj.versions, ensure_ascii=False), archive, nom)
        return (nom, digest, "struct", obj.id, row, _sommaire_rows(obj.id, obj.enfants))
    if isinstance(obj, EliVersions):
        cle = nom.split("/eli/", 1)[-1]
        return (nom, digest, "eli", cle, (cle, json.dumps(obj.versions), archive))
    assert isinstance(obj, Inconnu)
    return (nom, digest, "inconnu", obj.racine)


def _traiter_lot(args: tuple[str, list[tuple[str, bytes, int]]]) -> list[tuple]:
    archive, lot = args
    return [_traiter_un(nom, data, mtime, archive) for nom, data, mtime in lot]


# ------------------------------------------------------------ côté processus principal

def _identifiant_objet(nom: str) -> str:
    return nom.rstrip("/").rsplit("/", 1)[-1].removesuffix(".xml")


class _Lecteur:
    """Parcourt une archive en flux et classe chaque membre."""

    def __init__(self, path: Path):
        self.path = path
        self.stats = Counter()
        self.autres: list[str] = []
        self.vides: list[str] = []
        self.suppressions: list[str] = []

    def lots(self, archive: str) -> Iterator[tuple[str, list[tuple[str, bytes, int]]]]:
        lot: list[tuple[str, bytes, int]] = []
        with tarfile.open(self.path, "r|gz") as tar:
            for m in tar:
                # en mode flux, tarfile conserve chaque en-tête lu : on vide la liste pour borner
                # la mémoire (5 millions d'entrées dans l'archive globale)
                tar.members.clear()
                self.stats["membres"] += 1
                if m.isdir():
                    self.stats["repertoires"] += 1
                    continue
                if not m.isfile():
                    self.stats["autres"] += 1
                    self.autres.append(m.name)
                    continue
                base = m.name.rsplit("/", 1)[-1]
                f = tar.extractfile(m)
                data = f.read() if f else b""
                if base.startswith("liste_suppression"):
                    self.suppressions.extend(l.strip() for l in data.decode("utf-8", "replace").splitlines() if l.strip())
                    continue
                if not base.endswith(".xml"):
                    self.stats["autres"] += 1
                    self.autres.append(m.name)
                    continue
                self.stats["xml"] += 1
                if not data.strip():  # fichier vide à la source (constaté dans eli/) : tracé, pas parsé
                    self.vides.append(m.name)
                    continue
                lot.append((m.name, data, int(m.mtime)))
                if len(lot) >= LOT:
                    yield archive, lot
                    lot = []
        if lot:
            yield archive, lot


_INSERTS = {
    "article": "INSERT OR REPLACE INTO articles VALUES (" + ",".join("?" * 19) + ")",
    "liens": "INSERT OR REPLACE INTO liens VALUES (" + ",".join("?" * 12) + ")",
    "section": "INSERT OR REPLACE INTO sections VALUES (?,?,?,?,?,?,?)",
    "sommaire": "INSERT OR REPLACE INTO sommaire VALUES (?,?,?,?,?,?,?,?,?,?)",
    "texte": "INSERT OR REPLACE INTO textes VALUES (" + ",".join("?" * 24) + ")",
    "struct": "INSERT OR REPLACE INTO textes_struct VALUES (?,?,?,?,?,?,?)",
    "eli": "INSERT OR REPLACE INTO eli VALUES (?,?,?)",
}


_TABLE_CHEMIN = {"article": ("articles", "chemin"), "section": ("sections", "chemin"),
                 "texte": ("textes", "chemin"), "struct": ("textes_struct", "chemin"), "eli": ("eli", "archive")}
_PK = {"article": "id", "section": "id", "texte": "id", "struct": "id", "eli": "chemin_eli"}


def _supprimer(conn: sqlite3.Connection, ligne: str) -> tuple[str, bool]:
    oid = _identifiant_objet(ligne)
    n = 0
    if oid.startswith("LEGIARTI"):
        n += conn.execute("DELETE FROM articles WHERE id = ?", (oid,)).rowcount
        conn.execute("DELETE FROM liens WHERE article_id = ?", (oid,))
    elif oid.startswith("LEGISCTA"):
        n += conn.execute("DELETE FROM sections WHERE id = ?", (oid,)).rowcount
        conn.execute("DELETE FROM sommaire WHERE parent_id = ?", (oid,))
    elif oid.startswith("LEGITEXT") or oid.startswith("JORFTEXT"):
        if "/struct/" in ligne or "/version/" not in ligne:
            n += conn.execute("DELETE FROM textes_struct WHERE id = ?", (oid,)).rowcount
            conn.execute("DELETE FROM sommaire WHERE parent_id = ?", (oid,))
        if "/version/" in ligne or "/struct/" not in ligne:
            n += conn.execute("DELETE FROM textes WHERE id = ?", (oid,)).rowcount
    return oid, n > 0


def ingerer_archive(conn: sqlite3.Connection, path: Path, sha256: str | None = None,
                    processus: int = 4, base_vide: bool = False, pool=None) -> dict:
    """Ingère une archive. `base_vide` évite les DELETE préalables (première ingestion)."""
    if pool is None:
        with Pool(processus) as p:
            return ingerer_archive(conn, path, sha256, processus, base_vide, p)
    archive = path.name
    debut = time.strftime("%Y-%m-%dT%H:%M:%S")
    lecteur = _Lecteur(path)
    par_type: Counter = Counter()
    vus: dict[str, tuple[bytes, int]] = {}  # objet → (empreinte, mtime) du fichier retenu
    ecrits: set[str] = set()
    n_err = n_inc = 0
    t0 = time.time()

    def appliquer(res: tuple) -> None:
        nonlocal n_err, n_inc
        nom, digest, kind = res[0], res[1], res[2]
        par_type[kind] += 1
        if kind == "erreur":
            n_err += 1
            conn.execute("INSERT INTO erreurs VALUES (?,?,?)", (archive, nom, res[3]))
            return
        if kind == "inconnu":
            n_inc += 1
            conn.execute("INSERT INTO inconnus VALUES (?,?,?)", (archive, nom, res[3]))
            return
        oid = f"{kind}:{res[3]}"
        doublon = oid in vus
        if doublon:
            # Même objet sous deux chemins d'une même archive (ex. copie restée dans « en vigueur »
            # après le passage du texte dans « non en vigueur ») : la copie la plus récente
            # (mtime de l'archive) l'emporte ; à égalité, celle de « non_vigueur ».
            (ancien_hash, ancien_mtime), (hash_, mtime) = vus[oid], digest
            table, col = _TABLE_CHEMIN[kind]
            row = conn.execute(f"SELECT {col} FROM {table} WHERE {_PK[kind]} = ?", (res[3],)).fetchone()
            ancien_nom = row[0] if row else None
            garder_ancien = mtime < ancien_mtime or (
                mtime == ancien_mtime and "non_vigueur" in (ancien_nom or "") and "non_vigueur" not in nom)
            retenu, ecarte = (ancien_nom, nom) if garder_ancien else (nom, ancien_nom)
            conn.execute("INSERT INTO doublons VALUES (?,?,?,?,?,?,?)",
                         (archive, res[3], retenu, ecarte, int(ancien_hash == hash_),
                          max(mtime, ancien_mtime) if not garder_ancien else ancien_mtime,
                          ancien_mtime if not garder_ancien else mtime))
            if garder_ancien:
                return
        vus[oid] = digest
        ecrits.add(res[3])
        purger = doublon or not base_vide  # sur base vide, rien à purger sauf doublon
        if kind == "article":
            if purger:
                conn.execute("DELETE FROM liens WHERE article_id = ?", (res[3],))
            conn.execute(_INSERTS["article"], res[4])
            conn.executemany(_INSERTS["liens"], res[5])
        elif kind in ("section", "struct"):
            if purger:
                conn.execute("DELETE FROM sommaire WHERE parent_id = ?", (res[3],))
            conn.execute(_INSERTS[kind], res[4])
            conn.executemany(_INSERTS["sommaire"], res[5])
        else:
            conn.execute(_INSERTS[kind], res[4])

    conn.execute("BEGIN")
    n = 0
    for resultats in pool.imap(_traiter_lot, lecteur.lots(archive), chunksize=1):
        for res in resultats:
            appliquer(res)
        n += len(resultats)
        if n % 50_000 < LOT:
            conn.execute("COMMIT")
            conn.execute("BEGIN")
            print(f"  {archive}: {n} fichiers ({n / max(time.time() - t0, 1e-9):.0f}/s)", flush=True)

    # Suppressions : appliquées en fin d'archive, sauf pour un objet republié dans la même archive.
    for ligne in lecteur.suppressions:
        oid = _identifiant_objet(ligne)
        if oid in ecrits:
            conn.execute("INSERT INTO suppressions VALUES (?,?,?,?)", (archive, ligne, oid, -1))
            continue
        oid, trouve = _supprimer(conn, ligne)
        conn.execute("INSERT INTO suppressions VALUES (?,?,?,?)", (archive, ligne, oid, int(trouve)))
    conn.executemany("INSERT INTO vides VALUES (?,?)", [(archive, v) for v in lecteur.vides])
    par_type["vide"] = len(lecteur.vides)
    if not par_type["vide"]:
        del par_type["vide"]

    stats = {
        "archive": archive, "sha256": sha256, "stamp": _stamp(archive),
        "membres": lecteur.stats["membres"], "repertoires": lecteur.stats["repertoires"],
        "xml": lecteur.stats["xml"], "par_type": dict(par_type), "suppressions": len(lecteur.suppressions),
        "inconnus": n_inc, "erreurs": n_err, "autres_fichiers": lecteur.autres,
        "debut": debut, "fin": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    conn.execute("INSERT OR REPLACE INTO ingestion VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (archive, sha256, stats["stamp"], stats["membres"], stats["repertoires"], stats["xml"],
                  json.dumps(stats["par_type"]), stats["suppressions"], n_inc, n_err,
                  json.dumps(lecteur.autres), debut, stats["fin"]))
    conn.execute("COMMIT")
    return stats


def _stamp(nom: str) -> str:
    import re
    m = re.search(r"(\d{8}-\d{6})", nom)
    return m.group(1) if m else ""


def recalculer_cles(conn: sqlite3.Connection) -> int:
    """Regroupe les versions en articles logiques (union des chaînes <VERSIONS>)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        racine = x
        while parent.get(racine, racine) != racine:
            racine = parent[racine]
        while parent.get(x, x) != racine:  # compression de chemin
            parent[x], x = racine, parent[x]
        return racine

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    ids = []
    for oid, versions in conn.execute("SELECT id, versions FROM articles"):
        ids.append(oid)
        parent.setdefault(oid, oid)
        for v in json.loads(versions or "[]"):
            vid = v.get("id")
            if vid and vid.startswith("LEGIARTI"):
                parent.setdefault(vid, vid)
                union(oid, vid)
    conn.execute("BEGIN")
    conn.executemany("UPDATE articles SET cle = ? WHERE id = ?", ((find(i), i) for i in ids))
    conn.execute("COMMIT")
    return len({find(i) for i in ids})


def ingerer_chaine(conn: sqlite3.Connection, paths: Iterable[Path], manifest: dict[str, dict],
                   processus: int = 4) -> list[dict]:
    deja = {r[0]: r[1] for r in conn.execute("SELECT archive, sha256 FROM ingestion")}
    base_vide = not deja and conn.execute("SELECT count(*) FROM articles").fetchone()[0] == 0
    faits = []
    a_faire = [p for p in paths
               if not (p.name in deja and deja[p.name] == manifest.get(p.name, {}).get("sha256"))]
    if a_faire:
        with Pool(processus) as pool:
            for p in a_faire:
                print(f"Ingestion de {p.name}", flush=True)
                faits.append(ingerer_archive(conn, p, manifest.get(p.name, {}).get("sha256"),
                                             processus=processus, base_vide=base_vide, pool=pool))
                base_vide = False
    if faits:
        print("Regroupement des versions en articles logiques…", flush=True)
        n = recalculer_cles(conn)
        meta_set(conn, "articles_logiques", str(n))
        meta_set(conn, "derniere_ingestion", time.strftime("%Y-%m-%dT%H:%M:%S"))
        meta_set(conn, "derniere_archive", faits[-1]["archive"])
        conn.commit()
    return faits
