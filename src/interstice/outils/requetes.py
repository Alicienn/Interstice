"""Requêtes communes sur le corpus LEGI (dates de vigueur, résolution des textes et articles)."""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from dataclasses import dataclass

from interstice.legi.numeros import normaliser_num

FIN_OUVERTE = "2999-01-01"
ETATS_EXCLUS = ("MODIFIE_MORT_NE",)  # versions jamais entrées en vigueur

# Périmètre fiscal par défaut : sigle → motif du titre (insensible à la casse)
SIGLES: dict[str, str] = {
    "CGI": r"^code général des impôts$",
    "CGI-AI": r"^code général des impôts,? annexe (?:1|i)\b",
    "CGI-AII": r"^code général des impôts,? annexe (?:2|ii)\b",
    "CGI-AIII": r"^code général des impôts,? annexe (?:3|iii)\b",
    "CGI-AIV": r"^code général des impôts,? annexe (?:4|iv)\b",
    "LPF": r"^livre des procédures fiscales$",
    "CIBS": r"^code des impositions sur les biens et services$",
    "CDOUANES": r"^code des douanes$",
}
SIGLES_FISCAUX = tuple(SIGLES)


def aujourdhui() -> str:
    return dt.date.today().isoformat()


def valider_date(date: str | None) -> str:
    if not date:
        return aujourdhui()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError(f"date invalide « {date} » (format attendu AAAA-MM-JJ)")
    return date


def en_vigueur_sql(alias: str = "", debut: str = "date_debut", fin: str = "date_fin") -> str:
    """Condition SQL « valide à la date :d » (paramètre nommé :d)."""
    a = f"{alias}." if alias else ""
    return (f"({a}{debut} IS NULL OR {a}{debut} <= :d) AND ({a}{fin} IS NULL OR {a}{fin} > :d)")


@dataclass
class TexteRef:
    cid: str
    titre: str
    sigle: str | None
    nature: str


_CATALOGUES: dict[int, tuple[sqlite3.Connection, dict[str, TexteRef]]] = {}


def catalogue(conn: sqlite3.Connection) -> dict[str, TexteRef]:
    """cid → TexteRef pour tous les textes (titre de la version la plus récente). Mis en cache par connexion."""
    entree = _CATALOGUES.get(id(conn))
    if entree and entree[0] is conn:
        return entree[1]
    cache: dict[str, TexteRef] = {}
    _CATALOGUES[id(conn)] = (conn, cache)
    rows = conn.execute(
        "SELECT cid, nature, titre, titrefull, date_debut FROM textes ORDER BY cid, date_debut"
    ).fetchall()
    for r in rows:
        # TITREFULL est l'intitulé propre (« Code général des impôts ») ; TITRE porte des suffixes (« …, CGI. »)
        titre = r["titrefull"] or r["titre"] or r["cid"]
        cache[r["cid"]] = TexteRef(r["cid"], titre, None, r["nature"] or "")
    for sigle, motif in SIGLES.items():
        rx = re.compile(motif, re.I)
        for ref in cache.values():
            if ref.nature == "CODE" and rx.search(ref.titre) and ref.sigle is None:
                ref.sigle = sigle
                break
    return cache


def cid_par_sigle(conn: sqlite3.Connection) -> dict[str, str]:
    return {t.sigle: t.cid for t in catalogue(conn).values() if t.sigle}


def resoudre_texte(conn: sqlite3.Connection, texte: str) -> TexteRef:
    """Accepte un sigle (CGI, LPF…), un identifiant (LEGITEXT…/JORFTEXT…) ou un titre (même partiel)."""
    cat = catalogue(conn)
    t = texte.strip()
    if t in cat:
        return cat[t]
    sig = cid_par_sigle(conn)
    if t.upper() in sig:
        return cat[sig[t.upper()]]
    row = conn.execute("SELECT cid FROM textes WHERE id = ?", (t,)).fetchone()
    if row:
        return cat[row[0]]
    tl = t.lower()
    exacts = [r for r in cat.values() if r.titre.lower() == tl]
    if exacts:
        return exacts[0]
    partiels = sorted((r for r in cat.values() if tl in r.titre.lower()),
                      key=lambda r: (r.nature != "CODE", len(r.titre)))
    if partiels:
        return partiels[0]
    raise LookupError(f"texte introuvable : « {texte} ». Utilisez lister_textes.")


def perimetre(conn: sqlite3.Connection, textes: list[str] | str | None) -> list[str]:
    """Liste de cid. None → périmètre fiscal ; « tout » → aucun filtre (liste vide)."""
    if textes is None:
        return list(cid_par_sigle(conn).values())
    if isinstance(textes, str):
        if textes.strip().lower() in ("tout", "tous", "*"):
            return []
        textes = [textes]
    return [resoudre_texte(conn, t).cid for t in textes]


def texte_racine_id(conn: sqlite3.Connection, cid: str, date: str) -> str | None:
    """Identifiant LEGITEXT de la structure du texte valable à la date (sinon la plus récente)."""
    rows = conn.execute("SELECT id, versions FROM textes_struct WHERE cid = ?", (cid,)).fetchall()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]["id"]
    best = None
    for r in rows:
        for v in json.loads(r["versions"] or "[]"):
            if v.get("id") == r["id"] and (v.get("debut") or "") <= date < (v.get("fin") or FIN_OUVERTE):
                return r["id"]
        best = r["id"]
    return best


def article_a_date(conn: sqlite3.Connection, cid: str, num: str, date: str) -> sqlite3.Row:
    """Version d'un article (texte + numéro) applicable à la date ; à défaut la plus récente."""
    nn = normaliser_num(num)
    rows = conn.execute(
        "SELECT * FROM articles WHERE texte_cid = ? AND num_norm = ? ORDER BY date_debut",
        (cid, nn)).fetchall()
    if not rows:
        raise LookupError(f"article « {num} » introuvable dans ce texte.")
    return choisir_version(rows, date)


def choisir_version(rows: list[sqlite3.Row], date: str) -> sqlite3.Row:
    valides = [r for r in rows if r["etat"] not in ETATS_EXCLUS
               and (r["date_debut"] or "") <= date < (r["date_fin"] or FIN_OUVERTE)]
    if valides:
        return max(valides, key=lambda r: r["date_debut"] or "")
    candidats = [r for r in rows if r["etat"] not in ETATS_EXCLUS] or rows
    anterieurs = [r for r in candidats if (r["date_debut"] or "") <= date]
    return max(anterieurs or candidats, key=lambda r: r["date_debut"] or "")


def versions_de(conn: sqlite3.Connection, cle: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, num, etat, date_debut, date_fin FROM articles WHERE cle = ? ORDER BY date_debut",
                        (cle,)).fetchall()


def chemin_article(art: sqlite3.Row, date: str | None = None) -> list[dict]:
    """Fil d'Ariane : un intitulé par niveau, celui valable à la date (sinon le dernier)."""
    d = date or art["date_debut"] or aujourdhui()
    out = []
    for niveau in json.loads(art["contexte"] or "[]"):
        if not niveau:
            continue
        ok = [t for t in niveau if (t.get("debut") or "") <= d < (t.get("fin") or FIN_OUVERTE)]
        t = (ok or niveau)[-1]
        out.append({"id": t["id"], "kind": "section", "titre": t["titre"]})
    return out


def libelle_article(ref: TexteRef | None, num: str | None) -> str:
    nom = (ref.sigle or ref.titre) if ref else "?"
    return f"{nom}, art. {num}" if num else nom


def compter_articles(conn: sqlite3.Connection, parent_id: str, date: str) -> int:
    """Nombre d'articles valables à la date sous un nœud du sommaire (récursif)."""
    return conn.execute(
        f"""WITH RECURSIVE sous(id) AS (
                SELECT enfant_id FROM sommaire WHERE parent_id = :p AND kind = 'section' AND {en_vigueur_sql('', 'debut', 'fin')}
                UNION
                SELECT s.enfant_id FROM sommaire s JOIN sous ON s.parent_id = sous.id
                WHERE s.kind = 'section' AND {en_vigueur_sql('s', 'debut', 'fin')})
            SELECT count(*) FROM sommaire WHERE kind = 'article' AND {en_vigueur_sql('', 'debut', 'fin')}
              AND (parent_id = :p OR parent_id IN (SELECT id FROM sous))""",
        {"p": parent_id, "d": date}).fetchone()[0]
