"""Construit la table `renvois` pour tous les articles de la base (toutes versions)."""

from __future__ import annotations

import re
import sqlite3
import time
from collections import defaultdict
from multiprocessing import Pool

from interstice.graph.citations import extraire
from interstice.outils.requetes import FIN_OUVERTE, SIGLES

_NATURES = {"loi": ("LOI", "LOI_ORGANIQUE"), "ordonnance": ("ORDONNANCE",), "décret": ("DECRET", "DECRET_LOI"),
            "arrêté": ("ARRETE",)}

# État partagé des processus (initialisé une fois par processus)
_NUMS: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
_TITRES: list[tuple[str, str]] = []
_ANNEXES: dict[str, str] = {}
_ACTES: dict[tuple[str, str], str] = {}


def _init(nums, titres, annexes, actes) -> None:
    global _NUMS, _TITRES, _ANNEXES, _ACTES
    _NUMS, _TITRES, _ANNEXES, _ACTES = nums, titres, annexes, actes


def _resoudre_texte(kind: str, valeur: str) -> str | None:
    if kind == "annexe":
        return _ANNEXES.get(valeur)
    if kind == "titre":
        v = re.sub(r"\s+", " ", valeur.lower()).strip()
        for titre, cid in _TITRES:  # du plus long au plus court
            if v.startswith(titre):
                return cid
        return None
    for nature in _NATURES.get(kind, ()):
        cid = _ACTES.get((nature, valeur))
        if cid:
            return cid
    return None


def _choisir_cle(candidats: list[tuple[str, str, str, str]], date: str | None) -> tuple[str, str]:
    """candidats : (num, cle, debut, fin). Retient la clé valable à la date de l'article source."""
    if len(candidats) == 1 or not date:
        c = candidats[-1]
        return c[0], c[1]
    for c in candidats:
        if (c[2] or "") <= date < (c[3] or FIN_OUVERTE):
            return c[0], c[1]
    c = max(candidats, key=lambda c: c[2] or "")
    return c[0], c[1]


def _traiter(lot: list[tuple[str, str, str, str]]) -> list[tuple]:
    rows = []
    for art_id, cid, texte, date in lot:
        choix: dict[tuple[str, str], str] = {}

        def resoudre_num(cible: str, cand: str) -> str | None:
            c = _NUMS.get((cible, cand))
            if not c:
                return None
            num, cle = _choisir_cle(c, date)
            choix[(cible, num)] = cle
            return num

        for i, r in enumerate(extraire(texte or "", cid, resoudre_num, _resoudre_texte)):
            cle = choix.get((r.cible_cid, r.num)) if r.num else None
            rows.append((art_id, i, r.brut, r.num, r.cible_cid, cle, r.plage, r.contexte_cible))
    return rows


def _index(conn: sqlite3.Connection):
    nums: dict[tuple[str, str], list] = defaultdict(list)
    for cid, nn, num, cle, debut, fin in conn.execute(
            """SELECT texte_cid, num_norm, max(num), cle, min(date_debut), max(date_fin) FROM articles
               WHERE num_norm IS NOT NULL AND cle IS NOT NULL GROUP BY texte_cid, num_norm, cle"""):
        nums[(cid, nn)].append((num, cle, debut, fin))
    for v in nums.values():
        v.sort(key=lambda c: c[2] or "")
    titres, annexes, actes = [], {}, {}
    for cid, nature, titre, num in conn.execute("SELECT cid, nature, titre, num FROM textes"):
        if nature == "CODE" and titre:
            titres.append((re.sub(r"\s+", " ", titre.lower()).strip(), cid))
        elif num and nature:
            actes.setdefault((nature, num), cid)
        for n, motif in (("I", "CGI-AI"), ("II", "CGI-AII"), ("III", "CGI-AIII"), ("IV", "CGI-AIV")):
            if nature == "CODE" and titre and re.search(SIGLES[motif], titre, re.I):
                annexes[n] = cid
    titres.sort(key=lambda t: -len(t[0]))
    return dict(nums), titres, annexes, actes


def construire_renvois(conn: sqlite3.Connection, processus: int = 6, lot: int = 2000) -> dict:
    t0 = time.time()
    index = _index(conn)
    conn.execute("DELETE FROM renvois")
    ins = "INSERT INTO renvois VALUES (?,?,?,?,?,?,?,?)"
    # connexion séparée pour lire pendant que `conn` écrit ; le pool la lit depuis son propre thread
    lecteur = sqlite3.connect(conn.execute("PRAGMA database_list").fetchone()[2], check_same_thread=False)
    n_art = n_ren = 0
    with Pool(processus, initializer=_init, initargs=index) as pool:
        conn.execute("BEGIN")
        for rows in pool.imap(_traiter, _lots_depuis(lecteur, lot), chunksize=1):
            conn.executemany(ins, rows)
            n_ren += len(rows)
            n_art += lot
            if n_art % 200_000 < lot:
                conn.execute("COMMIT")
                conn.execute("BEGIN")
                print(f"  renvois : ~{n_art} articles, {n_ren} renvois ({time.time() - t0:.0f}s)", flush=True)
        conn.execute("COMMIT")
    lecteur.close()
    stats = dict(conn.execute("""SELECT count(*) AS total, sum(num IS NOT NULL) AS resolus,
                                        sum(cible_cid IS NULL) AS texte_inconnu FROM renvois""").fetchone())
    stats["secondes"] = round(time.time() - t0)
    return stats


def _lots_depuis(conn: sqlite3.Connection, taille: int):
    buf = []
    for row in conn.execute("SELECT id, texte_cid, texte, date_debut FROM articles"):
        buf.append(tuple(row))
        if len(buf) >= taille:
            yield buf
            buf = []
    if buf:
        yield buf
