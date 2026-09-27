"""Export Markdown : un fichier par article en vigueur, rangé selon le sommaire officiel.

Les renvois résolus deviennent des liens wiki `[[CGI art. 150-0 A]]` : ouvert dans Obsidian,
le dossier donne une vue graphe du réseau de renvois entre articles.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from interstice.outils.requetes import (catalogue, cid_par_sigle, en_vigueur_sql, resoudre_texte,
                                        texte_racine_id, valider_date)

_INTERDIT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _nom_fichier(s: str, n: int = 80) -> str:
    s = _INTERDIT.sub(" ", s).strip().rstrip(".")
    s = re.sub(r"\s+", " ", s)
    return s[:n].rstrip() or "sans titre"


def _nom_article(sigle: str, num: str) -> str:
    return _nom_fichier(f"{sigle} art. {num}", 120)


def exporter(conn: sqlite3.Connection, dest: Path, sigles: list[str] | None = None, date: str | None = None) -> dict:
    d = valider_date(date)
    cat = catalogue(conn)
    textes = sigles or list(cid_par_sigle(conn))
    noms_par_cle: dict[str, str] = {}
    a_ecrire: list[tuple[Path, sqlite3.Row, str, list[str]]] = []

    for t in textes:
        ref = resoudre_texte(conn, t)
        cid, sigle = ref.cid, ref.sigle or ref.titre
        racine = texte_racine_id(conn, cid, d)
        if racine is None:
            continue

        def descendre(parent: str, dossier: Path, chemin: list[str]) -> None:
            for i, e in enumerate(conn.execute(
                    f"SELECT * FROM sommaire WHERE parent_id = :p AND {en_vigueur_sql('', 'debut', 'fin')} ORDER BY position",
                    {"p": parent, "d": d}).fetchall()):
                if e["kind"] == "section":
                    sous = dossier / f"{i:03d} {_nom_fichier(e['titre'])}"
                    descendre(e["enfant_id"], sous, chemin + [e["titre"]])
                else:
                    art = conn.execute("SELECT * FROM articles WHERE id = ?", (e["enfant_id"],)).fetchone()
                    if art:
                        nom = _nom_article(sigle, art["num"] or e["titre"])
                        noms_par_cle[art["cle"]] = nom
                        a_ecrire.append((dossier / f"{nom}.md", art, sigle, chemin))

        descendre(racine, dest / _nom_fichier(sigle if sigle == cat[cid].titre else f"{sigle} - {cat[cid].titre}"),
                  [cat[cid].titre])

    for path, art, sigle, chemin in a_ecrire:
        liens = []
        for r in conn.execute("SELECT DISTINCT cible_cle, num, brut FROM renvois WHERE article_id = ?", (art["id"],)):
            if r["cible_cle"] in noms_par_cle:
                liens.append(f"[[{noms_par_cle[r['cible_cle']]}]]")
        path.parent.mkdir(parents=True, exist_ok=True)
        front = "\n".join([
            "---", f"id: {art['id']}", f"article: \"{art['num']}\"", f"code: {sigle}", f"etat: {art['etat']}",
            f"en_vigueur_depuis: {art['date_debut']}", f"en_vigueur_jusqua: {art['date_fin']}",
            f"legifrance: https://www.legifrance.gouv.fr/codes/article_lc/{art['id']}", "---", ""])
        corps = [f"# {sigle}, art. {art['num']}", "", "> " + " › ".join(chemin), "", art["texte"] or ""]
        if liens:
            corps += ["", "## Renvois", "", " · ".join(dict.fromkeys(liens))]
        path.write_text(front + "\n".join(corps) + "\n", "utf-8")
    return {"articles": len(a_ecrire), "dossier": str(dest), "date": d}
