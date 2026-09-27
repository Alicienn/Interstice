"""Vues détaillées pour le panneau de lecture (routes /api/documents/*).

Formes de retour : voir docs/contrat-api.md §3 (VueArticle, VueNoeud, LigneRecherche).
Chaque fonction lève LookupError si l'objet n'existe pas.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from interstice.graph.citations import RE_NUM, RE_RENVOI
from interstice.outils.requetes import (FIN_OUVERTE, SIGLES_FISCAUX, catalogue, chemin_article, choisir_version,
                                        compter_articles, en_vigueur_sql, resoudre_texte, texte_racine_id,
                                        valider_date, versions_de)

_DANGEREUX = re.compile(r"<(script|style|iframe|object|embed)\b.*?</\1\s*>", re.I | re.S)
_ATTR_EVT = re.compile(r"\s+on\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)


def _assainir(html: str | None) -> str | None:
    if not html:
        return html
    return _ATTR_EVT.sub("", _DANGEREUX.sub("", html))


def _url_legifrance(art: sqlite3.Row) -> str:
    base = "codes" if art["texte_nature"] == "CODE" else "loda"
    return f"https://www.legifrance.gouv.fr/{base}/article_lc/{art['id']}"


def _version_cible(conn: sqlite3.Connection, cle: str | None, date: str) -> sqlite3.Row | None:
    if not cle:
        return None
    rows = conn.execute("SELECT id, num, etat, date_debut, date_fin, texte_cid FROM articles WHERE cle = ?",
                        (cle,)).fetchall()
    return choisir_version(rows, date) if rows else None


def _lier_renvois(conn: sqlite3.Connection, html: str, art: sqlite3.Row, date: str) -> str:
    """Transforme les numéros d'articles cités en liens <a data-article="…"> (renvois résolus seulement)."""
    cibles: dict[str, str] = {}
    for r in conn.execute("SELECT brut, cible_cle FROM renvois WHERE article_id = ? AND cible_cle IS NOT NULL",
                          (art["id"],)):
        v = _version_cible(conn, r["cible_cle"], date)
        if v:
            cibles.setdefault(r["brut"], v["id"])
    if not cibles:
        return html
    morceaux, pos = [], 0
    for m in RE_RENVOI.finditer(html):
        debut_liste = m.start("liste")
        for n in RE_NUM.finditer(m.group("liste")):
            brut = n.group(0).strip()
            if brut in cibles:
                a, b = debut_liste + n.start(), debut_liste + n.start() + len(brut)
                morceaux += [html[pos:a], f'<a href="#" data-article="{cibles[brut]}">{html[a:b]}</a>']
                pos = b
    morceaux.append(html[pos:])
    return "".join(morceaux)


def _renvoi(conn, cat, row_art: sqlite3.Row | None, typelien: str, origine: str, libelle: str) -> dict[str, Any]:
    if row_art is None:
        return {"id": None, "cle": None, "num": None, "texte_titre": "", "typelien": typelien,
                "origine": origine, "libelle": libelle}
    ref = cat.get(row_art["texte_cid"])
    return {"id": row_art["id"], "cle": row_art["cle"] if "cle" in row_art.keys() else None, "num": row_art["num"],
            "texte_titre": (ref.sigle or ref.titre) if ref else "", "typelien": typelien, "origine": origine,
            "libelle": libelle}


def vue_article(conn: sqlite3.Connection, id: str, date: str | None = None) -> dict[str, Any]:
    art = conn.execute("SELECT * FROM articles WHERE id = ?", (id,)).fetchone()
    if not art:
        raise LookupError(f"article introuvable : {id}")
    d = valider_date(date) if date else (art["date_debut"] or valider_date(None))
    cat = catalogue(conn)
    ref = cat.get(art["texte_cid"])

    sortants, vus = [], set()
    for r in conn.execute("SELECT * FROM renvois WHERE article_id = ? ORDER BY position", (id,)):
        v = _version_cible(conn, r["cible_cle"], d)
        cle = (r["cible_cid"], r["num"] or r["brut"])
        if cle in vus:
            continue
        vus.add(cle)
        lib = f"{(cat[r['cible_cid']].sigle or cat[r['cible_cid']].titre) if r['cible_cid'] in cat else '?'}, art. {r['num'] or r['brut']}"
        sortants.append(_renvoi(conn, cat, v, "CITATION", "texte", lib) if v else
                        {"id": None, "cle": None, "num": r["brut"], "texte_titre": "", "typelien": "CITATION",
                         "origine": "texte", "libelle": lib + " (non résolu)"})
    for l in conn.execute("SELECT * FROM liens WHERE article_id = ? AND sens = 'source'", (id,)):
        cible = conn.execute("SELECT id, cle, num, texte_cid FROM articles WHERE id = ?", (l["cible_id"],)).fetchone()
        cle = (cible["texte_cid"], cible["num"]) if cible else (l["cidtexte"], l["num"])
        if cle in vus:
            continue
        vus.add(cle)
        sortants.append(_renvoi(conn, cat, cible, l["typelien"], "legi", l["libelle"]))

    entrants = []
    if art["cle"]:
        for r in conn.execute(
                f"""SELECT DISTINCT a.id, a.cle, a.num, a.texte_cid FROM renvois r JOIN articles a ON a.id = r.article_id
                    WHERE r.cible_cle = :c AND a.etat != 'MODIFIE_MORT_NE' AND {en_vigueur_sql('a')}
                    ORDER BY a.texte_cid, a.num LIMIT 300""", {"c": art["cle"], "d": d}):
            ref_s = cat.get(r["texte_cid"])
            entrants.append(_renvoi(conn, cat, r, "CITATION", "texte",
                                    f"{(ref_s.sigle or ref_s.titre) if ref_s else '?'}, art. {r['num']}"))

    return {
        "id": art["id"], "cle": art["cle"], "num": art["num"], "texte_cid": art["texte_cid"],
        "texte_titre": ref.titre if ref else (art["texte_titre"] or ""), "sigle": ref.sigle if ref else None,
        "etat": art["etat"], "date_debut": art["date_debut"], "date_fin": art["date_fin"],
        "chemin": ([{"id": art["texte_cid"], "kind": "texte", "titre": ref.sigle or ref.titre}] if ref else [])
                  + chemin_article(art, d),
        "html": _lier_renvois(conn, _assainir(art["html"]) or "", art, d),
        "nota_html": _assainir(art["nota_html"]),
        "url_legifrance": _url_legifrance(art),
        "versions": [dict(id=v["id"], etat=v["etat"], date_debut=v["date_debut"], date_fin=v["date_fin"])
                     for v in (versions_de(conn, art["cle"]) if art["cle"] else [])],
        "renvois_sortants": sortants,
        "renvois_entrants": entrants,
    }


def _enfants(conn: sqlite3.Connection, parent_id: str, d: str) -> list[dict[str, Any]]:
    out = []
    for e in conn.execute(
            f"SELECT * FROM sommaire WHERE parent_id = :p AND {en_vigueur_sql('', 'debut', 'fin')} ORDER BY position",
            {"p": parent_id, "d": d}):
        if e["kind"] == "section":
            out.append({"kind": "section", "id": e["enfant_id"], "titre": e["titre"], "etat": e["etat"],
                        "nb_articles": compter_articles(conn, e["enfant_id"], d)})
        else:
            out.append({"kind": "article", "id": e["enfant_id"], "titre": f"Article {e['titre']}", "etat": e["etat"]})
    return out


def vue_section(conn: sqlite3.Connection, id: str, date: str | None = None) -> dict[str, Any]:
    d = valider_date(date)
    sec = conn.execute("SELECT * FROM sections WHERE id = ?", (id,)).fetchone()
    if not sec:
        raise LookupError(f"section introuvable : {id}")
    cat = catalogue(conn)
    ref = cat.get(sec["texte_cid"])
    chemin = [{"id": sec["texte_cid"], "kind": "texte", "titre": (ref.sigle or ref.titre) if ref else sec["texte_cid"]}]
    for niveau in json.loads(sec["contexte"] or "[]"):
        if niveau:
            ok = [t for t in niveau if (t.get("debut") or "") <= d < (t.get("fin") or FIN_OUVERTE)]
            t = (ok or niveau)[-1]
            chemin.append({"id": t["id"], "kind": "section", "titre": t["titre"]})
    return {"id": id, "kind": "section", "titre": sec["titre"], "texte_cid": sec["texte_cid"], "chemin": chemin,
            "date": d, "enfants": _enfants(conn, id, d)}


def vue_texte(conn: sqlite3.Connection, cid: str, date: str | None = None) -> dict[str, Any]:
    d = valider_date(date)
    ref = resoudre_texte(conn, cid)
    racine = texte_racine_id(conn, ref.cid, d)
    if racine is None:
        raise LookupError(f"pas de sommaire pour {ref.titre}")
    return {"id": ref.cid, "kind": "texte", "titre": ref.titre, "texte_cid": ref.cid, "chemin": [], "date": d,
            "enfants": _enfants(conn, racine, d)}


def recherche(conn: sqlite3.Connection, q: str, texte: str | None = None,
              date: str | None = None, limite: int = 20) -> list[dict[str, Any]]:
    from interstice.outils.legi import _fts_query
    from interstice.outils.requetes import perimetre
    d = valider_date(date)
    cids = perimetre(conn, texte)
    params: dict[str, Any] = {"q": _fts_query(q), "d": d, "lim": max(1, min(limite, 100))}
    filtre = ""
    if cids:
        filtre = f" AND a.texte_cid IN ({','.join(f':c{i}' for i in range(len(cids)))})"
        params.update({f"c{i}": c for i, c in enumerate(cids)})
    rows = conn.execute(
        f"""SELECT a.id, a.num, a.texte_cid, a.contexte, a.date_debut,
                   snippet(articles_fts, 1, '<mark>', '</mark>', '…', 30) AS extrait
            FROM articles_fts JOIN articles a ON a.rowid = articles_fts.rowid
            WHERE articles_fts MATCH :q AND a.etat != 'MODIFIE_MORT_NE' AND {en_vigueur_sql('a')}{filtre}
            ORDER BY bm25(articles_fts, 5.0, 1.0) LIMIT :lim""", params).fetchall()
    cat = catalogue(conn)
    out = []
    for r in rows:
        ref = cat.get(r["texte_cid"])
        out.append({"id": r["id"], "num": r["num"], "texte_titre": (ref.sigle or ref.titre) if ref else "",
                    "chemin": " › ".join(c["titre"] for c in chemin_article(r, d)),
                    "extrait_html": _assainir(r["extrait"]) or ""})
    return out


_CACHE_TEXTES: dict[int, tuple[sqlite3.Connection, list]] = {}


def lister_textes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Codes (fiscaux en tête) avec leur nombre d'articles en vigueur aujourd'hui."""
    entree = _CACHE_TEXTES.get(id(conn))
    if entree and entree[0] is conn:
        return entree[1]
    d = valider_date(None)
    cat = catalogue(conn)
    codes = [r for r in cat.values() if r.nature == "CODE" or r.sigle]
    comptes = dict(conn.execute(
        f"""SELECT texte_cid, count(*) FROM articles WHERE etat != 'MODIFIE_MORT_NE' AND {en_vigueur_sql()}
            AND texte_cid IN ({','.join('?' * len(codes))}) GROUP BY texte_cid""".replace(":d", "?"),
        [d, d] + [r.cid for r in codes]).fetchall()) if codes else {}
    out = [{"cid": r.cid, "sigle": r.sigle, "titre": r.titre, "nature": r.nature,
            "fiscal": r.sigle in SIGLES_FISCAUX, "nb_articles_vigueur": comptes.get(r.cid, 0)} for r in codes]
    out.sort(key=lambda x: (not x["fiscal"], SIGLES_FISCAUX.index(x["sigle"]) if x["fiscal"] else 0, x["titre"]))
    _CACHE_TEXTES[id(conn)] = (conn, out)
    return out
