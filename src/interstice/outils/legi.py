"""Outils de navigation dans le corpus LEGI (exposés au MCP et à l'agent web).

Principe : l'IA descend dans l'arborescence officielle (texte → partie → livre → titre →
chapitre → section → article) avec `sommaire`, lit les articles avec `lire_article`, suit les
renvois avec `renvois`, remonte le temps avec `historique_article` / `comparer_versions`,
et utilise `rechercher` quand elle ne connaît pas l'emplacement.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3

from interstice.outils.base import DocRef, Outil, Resultat
from interstice.outils.requetes import (FIN_OUVERTE, SIGLES_FISCAUX, article_a_date, catalogue, chemin_article,
                                        compter_articles, en_vigueur_sql, libelle_article, perimetre,
                                        resoudre_texte, texte_racine_id, valider_date, versions_de)

MAX_LIGNES_SOMMAIRE = 400
EXTRAIT = 110


def _fin(v: str | None) -> str:
    return "—" if not v or v == FIN_OUVERTE else v


def _extrait(texte: str | None, n: int = EXTRAIT) -> str:
    t = re.sub(r"\s+", " ", texte or "").strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _article_par_id(conn: sqlite3.Connection, id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (id,)).fetchone()
    if not row:
        raise LookupError(f"version d'article introuvable : {id}")
    return row


def _trouver_article(conn, texte: str | None, num: str | None, id: str | None, date: str) -> sqlite3.Row:
    if id:  # une version précise a été demandée : on la renvoie telle quelle
        return _article_par_id(conn, id)
    if not (texte and num):
        raise ValueError("indiquez soit `id`, soit `texte` et `num`.")
    return article_a_date(conn, resoudre_texte(conn, texte).cid, num, date)


def _doc_article(conn, art: sqlite3.Row, date: str | None) -> DocRef:
    ref = catalogue(conn).get(art["texte_cid"])
    ch = chemin_article(art, date)
    return DocRef("article", art["id"], libelle_article(ref, art["num"]),
                  " › ".join(c["titre"].split(":")[0].strip() for c in ch[-3:]), date)


# ----------------------------------------------------------------- lister_textes

def lister_textes(conn: sqlite3.Connection, filtre: str | None = None, tous: bool = False) -> Resultat:
    cat = catalogue(conn)
    refs = [r for r in cat.values() if r.nature == "CODE" or r.sigle]
    if filtre:
        refs = [r for r in cat.values() if filtre.lower() in r.titre.lower()][:60]
    elif not tous:
        refs = [r for r in refs if r.sigle in SIGLES_FISCAUX]
    refs.sort(key=lambda r: (r.sigle is None, SIGLES_FISCAUX.index(r.sigle) if r.sigle in SIGLES_FISCAUX else 0, r.titre))
    lignes = ["| sigle | titre | nature | identifiant |", "|---|---|---|---|"]
    lignes += [f"| {r.sigle or ''} | {r.titre} | {r.nature} | {r.cid} |" for r in refs]
    entete = ("Périmètre fiscal par défaut. `tous=true` pour tous les codes, `filtre` pour chercher un texte (lois, décrets…)."
              if not filtre and not tous else f"{len(refs)} texte(s).")
    return Resultat(entete + "\n\n" + "\n".join(lignes),
                    [DocRef("texte", r.cid, r.sigle or r.titre, r.titre) for r in refs[:12]])


# ----------------------------------------------------------------- sommaire

def sommaire(conn: sqlite3.Connection, texte: str | None = None, section_id: str | None = None,
             date: str | None = None, profondeur: int = 1) -> Resultat:
    d = valider_date(date)
    profondeur = max(1, min(int(profondeur), 4))
    if section_id:
        sec = conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
        if not sec:
            raise LookupError(f"section introuvable : {section_id}")
        cid, racine, titre = sec["texte_cid"], section_id, sec["titre"]
    elif texte:
        ref = resoudre_texte(conn, texte)
        cid, racine, titre = ref.cid, texte_racine_id(conn, ref.cid, d), ref.titre
        if racine is None:
            raise LookupError(f"pas de sommaire pour {ref.titre}")
    else:
        raise ValueError("indiquez `texte` (ex. « CGI ») ou `section_id`.")
    ref = catalogue(conn).get(cid)
    lignes: list[str] = []
    docs: list[DocRef] = []
    tronque = False

    def descendre(parent: str, niveau: int) -> None:
        nonlocal tronque
        enfants = conn.execute(
            f"SELECT * FROM sommaire WHERE parent_id = :p AND {en_vigueur_sql('', 'debut', 'fin')} ORDER BY position",
            {"p": parent, "d": d}).fetchall()
        for e in enfants:
            if len(lignes) >= MAX_LIGNES_SOMMAIRE:
                tronque = True
                return
            ind = "  " * (niveau - 1)
            if e["kind"] == "section":
                n = compter_articles(conn, e["enfant_id"], d)
                lignes.append(f"{ind}- **{e['titre']}** — section `{e['enfant_id']}` ({n} art.)")
                if len(docs) < 15:
                    docs.append(DocRef("section", e["enfant_id"], e["titre"], f"{n} articles", d))
                if niveau < profondeur:
                    descendre(e["enfant_id"], niveau + 1)
            else:
                a = conn.execute("SELECT texte, etat FROM articles WHERE id = ?", (e["enfant_id"],)).fetchone()
                apercu = _extrait(a["texte"]) if a else "(version absente de la base)"
                lignes.append(f"{ind}- art. **{e['titre']}** `{e['enfant_id']}` — {apercu}")

    descendre(racine, 1)
    chemin = ""
    if section_id:
        sec_ctx = conn.execute("SELECT contexte FROM sections WHERE id = ?", (section_id,)).fetchone()
        niveaux = json.loads(sec_ctx["contexte"] or "[]") if sec_ctx else []
        chemin = " › ".join(n[-1]["titre"] for n in niveaux if n)
    entete = f"# {libelle_article(ref, None)} — {titre}\nSommaire au {d}" + (f"\nChemin : {chemin}" if chemin else "")
    if not lignes:
        lignes = ["(aucun élément en vigueur à cette date)"]
    if tronque:
        lignes.append(f"… liste tronquée à {MAX_LIGNES_SOMMAIRE} lignes : descendez dans une section.")
    doc_racine = DocRef("section" if section_id else "texte", section_id or cid, titre, libelle_article(ref, None), d)
    return Resultat(entete + "\n\n" + "\n".join(lignes), [doc_racine] + docs)


# ----------------------------------------------------------------- lire_article

def _renvois_sortants(conn, art: sqlite3.Row) -> list[dict]:
    cat = catalogue(conn)
    out, vus = [], set()
    for r in conn.execute("SELECT * FROM renvois WHERE article_id = ? ORDER BY position", (art["id"],)):
        cle = (r["cible_cid"], r["num"] or r["brut"])
        if cle in vus:
            continue
        vus.add(cle)
        out.append({"libelle": libelle_article(cat.get(r["cible_cid"]), r["num"] or r["brut"]),
                    "cle": r["cible_cle"], "resolu": bool(r["num"]), "origine": "texte"})
    for l in conn.execute("SELECT * FROM liens WHERE article_id = ? AND sens = 'source' AND typelien = 'CITATION'",
                          (art["id"],)):
        cible = conn.execute("SELECT cle, texte_cid, num FROM articles WHERE id = ?", (l["cible_id"],)).fetchone()
        cle = (cible["texte_cid"], cible["num"]) if cible else (l["cidtexte"], l["num"])
        if cle in vus:
            continue
        vus.add(cle)
        out.append({"libelle": libelle_article(cat.get(cible["texte_cid"]), cible["num"]) if cible else l["libelle"],
                    "cle": cible["cle"] if cible else None, "resolu": bool(cible), "origine": "legi"})
    return out


def lire_article(conn: sqlite3.Connection, texte: str | None = None, num: str | None = None,
                 id: str | None = None, date: str | None = None, nums: list[str] | None = None) -> Resultat:
    d = valider_date(date)
    if nums:
        if not texte:
            raise ValueError("`nums` demande `texte`.")
        res = [lire_article(conn, texte=texte, num=n, date=d) for n in nums[:15]]
        return Resultat("\n\n---\n\n".join(r.texte for r in res), [doc for r in res for doc in r.documents])
    art = _trouver_article(conn, texte, num, id, d)
    ref = catalogue(conn).get(art["texte_cid"])
    ch = chemin_article(art, d)
    versions = versions_de(conn, art["cle"]) if art["cle"] else []
    valide = (art["date_debut"] or "") <= d < (art["date_fin"] or FIN_OUVERTE)
    avert = "" if valide or id else f"\n⚠ Aucune version en vigueur au {d} ; version affichée : la plus récente antérieure."
    sortants = _renvois_sortants(conn, art)
    n_entrants = conn.execute("SELECT count(*) FROM renvois WHERE cible_cle = ?", (art["cle"],)).fetchone()[0] \
        if art["cle"] else 0
    lignes = [
        f"# {libelle_article(ref, art['num'])}",
        f"Version `{art['id']}` — état {art['etat']} — en vigueur du {art['date_debut']} au {_fin(art['date_fin'])}{avert}",
        "Chemin : " + " › ".join(f"{c['titre']} (`{c['id']}`)" for c in ch),
        "",
        art["texte"] or "(texte vide)",
    ]
    if art["nota_html"]:
        from interstice.legi.html import html_vers_texte
        lignes += ["", "NOTA : " + html_vers_texte(art["nota_html"])]
    if sortants:
        lignes += ["", "Renvois : " + " ; ".join(s["libelle"] + ("" if s["resolu"] else " (non résolu)") for s in sortants[:40])]
    lignes += [f"Cité par {n_entrants} article(s) (outil `renvois`, sens « entrants »)." if n_entrants else "",
               f"{len(versions)} version(s) connue(s) (outil `historique_article`)."]
    return Resultat("\n".join(l for l in lignes if l is not None).strip(), [_doc_article(conn, art, d)])


# ----------------------------------------------------------------- historique / comparaison

def historique_article(conn: sqlite3.Connection, texte: str | None = None, num: str | None = None,
                       id: str | None = None) -> Resultat:
    art = _trouver_article(conn, texte, num, id, valider_date(None))
    ref = catalogue(conn).get(art["texte_cid"])
    versions = versions_de(conn, art["cle"])
    lignes = [f"# Historique — {libelle_article(ref, art['num'])}", "",
              "| version | état | du | au | modifiée par |", "|---|---|---|---|---|"]
    for v in versions:
        modif = conn.execute(
            "SELECT DISTINCT libelle FROM liens WHERE article_id = ? AND sens = 'cible' AND typelien IN ('MODIFIE','CREE','ABROGE','TRANSFERE','DEPLACE')",
            (v["id"],)).fetchall()
        lignes.append(f"| `{v['id']}` | {v['etat']} | {v['date_debut']} | {_fin(v['date_fin'])} | "
                      f"{'; '.join(m[0] for m in modif)[:300]} |")
    return Resultat("\n".join(lignes), [DocRef("article", v["id"], libelle_article(ref, v["num"]),
                                               f"{v['etat']} {v['date_debut']} → {_fin(v['date_fin'])}", v["date_debut"])
                                        for v in versions[-6:]])


def comparer_versions(conn: sqlite3.Connection, id_avant: str, id_apres: str) -> Resultat:
    a, b = _article_par_id(conn, id_avant), _article_par_id(conn, id_apres)

    def phrases(t: str) -> list[str]:
        return [p.strip() for p in re.split(r"(?<=[.;:])\s+|\n+", t or "") if p.strip()]

    diff = list(difflib.unified_diff(phrases(a["texte"]), phrases(b["texte"]),
                                     f"{a['id']} ({a['date_debut']})", f"{b['id']} ({b['date_debut']})", lineterm="", n=1))
    corps = "\n".join(diff) if diff else "(textes identiques)"
    ref = catalogue(conn).get(b["texte_cid"])
    return Resultat(f"# Comparaison — {libelle_article(ref, b['num'])}\n```diff\n{corps}\n```",
                    [_doc_article(conn, a, a["date_debut"]), _doc_article(conn, b, b["date_debut"])])


# ----------------------------------------------------------------- renvois

def renvois(conn: sqlite3.Connection, texte: str | None = None, num: str | None = None, id: str | None = None,
            sens: str = "les deux", date: str | None = None) -> Resultat:
    d = valider_date(date)
    art = _trouver_article(conn, texte, num, id, d)
    cat = catalogue(conn)
    ref = cat.get(art["texte_cid"])
    lignes = [f"# Renvois — {libelle_article(ref, art['num'])} (version `{art['id']}`)"]
    docs = [_doc_article(conn, art, d)]
    if sens in ("sortants", "les deux"):
        s = _renvois_sortants(conn, art)
        lignes += ["", f"## Sortants ({len(s)}) — articles que celui-ci vise"]
        lignes += [f"- {x['libelle']}" + ("" if x["resolu"] else " (non résolu)") + f" [{x['origine']}]" for x in s]
    if sens in ("entrants", "les deux"):
        rows = conn.execute(
            f"""SELECT DISTINCT a.id, a.num, a.texte_cid, a.texte FROM renvois r JOIN articles a ON a.id = r.article_id
                WHERE r.cible_cle = :c AND a.etat != 'MODIFIE_MORT_NE' AND {en_vigueur_sql('a')}
                ORDER BY a.texte_cid, a.num LIMIT 300""", {"c": art["cle"], "d": d}).fetchall()
        lignes += ["", f"## Entrants ({len(rows)}) — articles en vigueur au {d} qui visent celui-ci"]
        for r in rows:
            lignes.append(f"- {libelle_article(cat.get(r['texte_cid']), r['num'])} `{r['id']}` — {_extrait(r['texte'], 90)}")
            if len(docs) < 12:
                docs.append(DocRef("article", r["id"], libelle_article(cat.get(r["texte_cid"]), r["num"]), "renvoi entrant", d))
    return Resultat("\n".join(lignes), docs)


# ----------------------------------------------------------------- recherche plein texte

def _fts_query(q: str) -> str:
    q = q.strip()
    if re.search(r'["*]|\b(AND|OR|NOT|NEAR)\b', q):
        return q  # syntaxe FTS5 explicite
    mots = re.findall(r"[\w'’-]+", q)
    return " ".join(f'"{m}"' for m in mots if len(m) > 1)


def rechercher(conn: sqlite3.Connection, requete: str, textes: list[str] | str | None = None,
               section_id: str | None = None, date: str | None = None, limite: int = 20) -> Resultat:
    d = valider_date(date)
    limite = max(1, min(int(limite), 50))
    cids = perimetre(conn, textes)
    params: dict = {"q": _fts_query(requete), "d": d, "lim": limite}
    filtre_txt = ""
    if cids:
        filtre_txt = f" AND a.texte_cid IN ({','.join(f':c{i}' for i in range(len(cids)))})"
        params.update({f"c{i}": c for i, c in enumerate(cids)})
    filtre_sec = ""
    if section_id:
        filtre_sec = " AND a.contexte LIKE :sec"
        params["sec"] = f'%"{section_id}"%'
    rows = conn.execute(
        f"""SELECT a.id, a.num, a.texte_cid, a.contexte, a.date_debut,
                   snippet(articles_fts, 1, '«', '»', '…', 24) AS extrait
            FROM articles_fts JOIN articles a ON a.rowid = articles_fts.rowid
            WHERE articles_fts MATCH :q AND a.etat != 'MODIFIE_MORT_NE' AND {en_vigueur_sql('a')}{filtre_txt}{filtre_sec}
            ORDER BY bm25(articles_fts, 5.0, 1.0) LIMIT :lim""", params).fetchall()
    cat = catalogue(conn)
    portee = "tous les textes" if textes is not None and not cids else ", ".join(
        (cat[c].sigle or cat[c].titre) for c in cids if c in cat)
    lignes = [f"# Recherche « {requete} » — {len(rows)} résultat(s) au {d} ({portee})", ""]
    docs = [DocRef("recherche", requete, f"Recherche : {requete}", portee, d)]
    for r in rows:
        ch = chemin_article(r, d)
        lib = libelle_article(cat.get(r["texte_cid"]), r["num"])
        lignes.append(f"- **{lib}** `{r['id']}` — {' › '.join(c['titre'].split(':')[0] for c in ch[-2:])}\n  {r['extrait']}")
        docs.append(DocRef("article", r["id"], lib, " › ".join(c["titre"].split(":")[0] for c in ch[-2:]), d))
    return Resultat("\n".join(lignes), docs[:16])


# ----------------------------------------------------------------- modifications

def modifications(conn: sqlite3.Connection, texte: str = "CGI", depuis: str | None = None,
                  jusqua: str | None = None, limite: int = 200) -> Resultat:
    ref = resoudre_texte(conn, texte)
    fin = valider_date(jusqua)
    if not depuis:
        raise ValueError("`depuis` est requis (AAAA-MM-JJ).")
    debut = valider_date(depuis)
    rows = conn.execute(
        """SELECT id, num, etat, date_debut, date_fin, 'nouvelle version' AS evt FROM articles
           WHERE texte_cid = :c AND date_debut >= :a AND date_debut <= :b AND etat != 'MODIFIE_MORT_NE'
           UNION ALL
           SELECT id, num, etat, date_debut, date_fin, 'fin de vigueur' FROM articles
           WHERE texte_cid = :c AND date_fin >= :a AND date_fin <= :b AND etat IN ('ABROGE','ABROGE_DIFF','PERIME','TRANSFERE','DISJOINT','ANNULE')
           ORDER BY 4 DESC LIMIT :lim""",
        {"c": ref.cid, "a": debut, "b": fin, "lim": max(1, min(int(limite), 500))}).fetchall()
    lignes = [f"# Modifications — {ref.sigle or ref.titre} du {debut} au {fin} ({len(rows)})", "",
              "| date | article | événement | état | version |", "|---|---|---|---|---|"]
    for r in rows:
        date_evt = r["date_debut"] if r["evt"] == "nouvelle version" else r["date_fin"]
        lignes.append(f"| {date_evt} | {r['num']} | {r['evt']} | {r['etat']} | `{r['id']}` |")
    return Resultat("\n".join(lignes), [DocRef("article", r["id"], libelle_article(ref, r["num"]), r["evt"], r["date_debut"])
                                        for r in rows[:10]])


# ----------------------------------------------------------------- registre

_DATE = {"type": "string", "description": "Date de référence AAAA-MM-JJ (défaut : aujourd'hui)."}
_TEXTE = {"type": "string", "description": "Sigle (CGI, CGI-AI…CGI-AIV, LPF, CIBS, CDOUANES), identifiant LEGITEXT/JORFTEXT ou titre."}
_NUM = {"type": "string", "description": "Numéro d'article tel qu'écrit (ex. « 150-0 B ter », « L. 64 A »)."}
_ID = {"type": "string", "description": "Identifiant de version LEGIARTI… (prioritaire sur texte+num)."}


def _schema(props: dict, requis: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": requis or [], "additionalProperties": False}


OUTILS_LEGI = [
    Outil("lister_textes",
          "Liste les textes disponibles (par défaut le périmètre fiscal : CGI et annexes, LPF, CIBS, Code des douanes) "
          "avec leur sigle et identifiant. `filtre` cherche aussi parmi les lois, décrets et autres codes.",
          _schema({"filtre": {"type": "string", "description": "Mot du titre (ex. « loi de finances pour 2024 »)."},
                   "tous": {"type": "boolean", "description": "Tous les codes au lieu du seul périmètre fiscal."}}),
          lister_textes),
    Outil("sommaire",
          "Affiche l'arborescence officielle d'un texte ou d'une section à une date : sous-sections (avec leur nombre "
          "d'articles) et articles (avec un aperçu). Point d'entrée pour naviguer catégorie par catégorie. "
          "Utilisez l'identifiant `section_id` renvoyé pour descendre d'un niveau.",
          _schema({"texte": _TEXTE, "section_id": {"type": "string", "description": "Identifiant LEGISCTA… d'une section."},
                   "date": _DATE,
                   "profondeur": {"type": "integer", "minimum": 1, "maximum": 4,
                                  "description": "Niveaux à déplier (défaut 1)."}}),
          sommaire),
    Outil("lire_article",
          "Lit un article (texte intégral, état, période de vigueur, chemin dans le sommaire, NOTA, renvois). "
          "Par défaut la version en vigueur aujourd'hui ; `date` pour le droit applicable à une autre date. "
          "`nums` permet d'en lire plusieurs du même texte en un appel (15 max).",
          _schema({"texte": _TEXTE, "num": _NUM, "id": _ID, "date": _DATE,
                   "nums": {"type": "array", "items": {"type": "string"}, "maxItems": 15}}),
          lire_article),
    Outil("historique_article",
          "Liste toutes les versions d'un article avec leurs dates et les textes qui les ont modifiées.",
          _schema({"texte": _TEXTE, "num": _NUM, "id": _ID}), historique_article),
    Outil("comparer_versions",
          "Compare deux versions d'un article (diff phrase par phrase). Identifiants issus de `historique_article`.",
          _schema({"id_avant": {"type": "string"}, "id_apres": {"type": "string"}}, ["id_avant", "id_apres"]),
          comparer_versions),
    Outil("renvois",
          "Graphe des renvois d'un article : « sortants » (articles qu'il vise) et « entrants » (articles en vigueur "
          "qui le visent). Indispensable pour mesurer les effets d'un régime sur les autres.",
          _schema({"texte": _TEXTE, "num": _NUM, "id": _ID, "date": _DATE,
                   "sens": {"type": "string", "enum": ["sortants", "entrants", "les deux"]}}),
          renvois),
    Outil("rechercher",
          "Recherche plein texte (mots ou syntaxe FTS5 : \"expression exacte\", OR, NEAR) dans les articles en vigueur "
          "à la date. Par défaut le périmètre fiscal ; `textes` pour restreindre (liste de sigles) ou « tout ».",
          _schema({"requete": {"type": "string"},
                   "textes": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "string"}]},
                   "section_id": {"type": "string", "description": "Restreint à une section (LEGISCTA…)."},
                   "date": _DATE, "limite": {"type": "integer", "minimum": 1, "maximum": 50}}, ["requete"]),
          rechercher),
    Outil("modifications",
          "Articles d'un texte modifiés, créés ou abrogés sur une période (veille législative, repérage des "
          "corrections apportées par le législateur).",
          _schema({"texte": _TEXTE, "depuis": _DATE, "jusqua": _DATE,
                   "limite": {"type": "integer", "minimum": 1, "maximum": 500}}, ["depuis"]),
          modifications),
]
