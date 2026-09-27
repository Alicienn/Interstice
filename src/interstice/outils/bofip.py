"""Outils de navigation dans la doctrine BOFiP-Impôts (exposés au MCP et à l'agent web).

Principe, comme pour LEGI : l'IA descend le plan de classement (série → division → titre → chapitre →
section) avec `bofip_plan`, lit un document par morceaux avec `bofip_lire` (table des matières par
intertitres, parties de ~12 000 caractères, accès direct à un § numéroté), cherche avec
`bofip_rechercher` et relie la loi à la doctrine avec `bofip_pour_article`.

Identifiants acceptés partout : PGP (« 739-PGP »), identifiant BOI daté (« BOI-RPPM-PVBMI-30-10-60-20260810 »)
ou non daté (« BOI-RPPM-PVBMI-30-10-60 »), code du plan (« BOI-IR-BASE »), actualité (« ACTU-2026-00036 »),
version antérieure « 739-PGP@2021-08-25 ».
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from typing import Any

from interstice.legi.numeros import normaliser_num
from interstice.outils.base import DocRef, Outil, Resultat

TAILLE_PARTIE = 12_000
LECTURE_ENTIERE = 16_000
MAX_LIGNES_PLAN = 300
KIND = "bofip"
_RE_NODE_DATE = re.compile(r"\[node:date:(\d+-PGP)\]")


# ----------------------------------------------------------------- résolution

def _exiger_bofip(conn: sqlite3.Connection) -> None:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'bofip_documents'").fetchone():
        raise LookupError("corpus BOFiP absent de la base : lancez `interstice bofip-download` puis `bofip-ingest`.")


def _versions(conn, pgp: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT boi, date_publication, motif FROM bofip_versions WHERE pgp = ? ORDER BY date_publication DESC",
                        (pgp,)).fetchall()


def trouver_document(conn: sqlite3.Connection, ident: str) -> tuple[sqlite3.Row, bool, list[str]]:
    """(ligne, version courante ?, autres candidats). LookupError si introuvable."""
    _exiger_bofip(conn)
    x = re.sub(r"\s+", "", ident or "")
    if not x:
        raise ValueError("identifiant vide")
    if "@" in x:  # version antérieure : PGP@date
        pgp, date = x.split("@", 1)
        r = conn.execute("SELECT * FROM bofip_documents WHERE pgp = ? AND date_publication = ?", (pgp, date)).fetchone()
        if r:
            return r, True, []
        r = conn.execute("SELECT * FROM bofip_versions WHERE pgp = ? AND date_publication = ? LIMIT 1", (pgp, date)).fetchone()
        if r:
            return r, False, []
        raise LookupError(f"version introuvable : {ident}")
    if re.fullmatch(r"\d+-PGP", x, re.I):
        r = conn.execute("SELECT * FROM bofip_documents WHERE pgp = ?", (x.upper(),)).fetchone()
        if r:
            return r, True, []
    xu = x.upper()
    if not xu.startswith(("BOI-", "ACTU-")) and re.match(r"^[A-Z]{2,6}-", xu):
        xu = "BOI-" + xu  # « RPPM-PVBMI-30 » → « BOI-RPPM-PVBMI-30 »
    for col in ("boi", "boi_base"):
        rows = conn.execute(f"SELECT * FROM bofip_documents WHERE {col} = ? ORDER BY date_publication DESC", (xu,)).fetchall()
        if rows:
            return rows[0], True, [f"{r['boi']} (`{r['pgp']}`)" for r in rows[1:]]
    n = conn.execute("SELECT pgp FROM bofip_plan WHERE code = ? AND pgp IS NOT NULL", (xu,)).fetchone()
    if n:
        return conn.execute("SELECT * FROM bofip_documents WHERE pgp = ?", (n[0],)).fetchone(), True, []
    r = conn.execute("SELECT * FROM bofip_versions WHERE boi = ? ORDER BY date_publication DESC LIMIT 1", (xu,)).fetchone()
    if r:
        return r, False, []
    raise LookupError(f"document BOFiP introuvable : « {ident} ». Utilisez bofip_rechercher ou bofip_plan.")


def _doc_id(row: sqlite3.Row, courant: bool = True) -> str:
    return row["pgp"] if courant else f"{row['pgp']}@{row['date_publication']}"


def libelle_court(titre: str | None) -> str:
    parts = [p.strip() for p in re.split(r"\s+[-–]\s+", titre or "") if p.strip()]
    return parts[-1] if parts else (titre or "")


def _docref(row: sqlite3.Row, courant: bool = True, sous_titre: str | None = None) -> DocRef:
    return DocRef(KIND, _doc_id(row, courant), row["boi"] or row["pgp"],  # type: ignore[arg-type]
                  sous_titre if sous_titre is not None else libelle_court(row["titre"])[:120], row["date_publication"])


def chemin_plan(conn: sqlite3.Connection, pgp: str) -> list[dict[str, Any]]:
    """Miettes du plan, de la série jusqu'au nœud parent du document (inclus le document lui-même)."""
    out = []
    noeud = conn.execute("SELECT * FROM bofip_plan WHERE pgp = ?", (pgp,)).fetchone()
    vus = set()
    while noeud is not None and noeud["noeud"] not in vus:
        vus.add(noeud["noeud"])
        out.append({"id": noeud["pgp"] or noeud["noeud"], "noeud": noeud["noeud"], "code": noeud["code"],
                    "titre": noeud["libelle"]})
        noeud = conn.execute("SELECT * FROM bofip_plan WHERE noeud = ?", (noeud["parent"],)).fetchone() \
            if noeud["parent"] else None
    return out[::-1]


def _remplacer_node_date(conn, texte: str) -> str:
    def rep(m: re.Match) -> str:
        r = conn.execute("SELECT boi, date_publication FROM bofip_documents WHERE pgp = ?", (m.group(1),)).fetchone()
        return f"{r['boi']} du {r['date_publication']}" if r else m.group(1)
    return _RE_NODE_DATE.sub(rep, texte or "")


# ----------------------------------------------------------------- plan

def _compter(conn, noeud: str) -> int:
    return conn.execute("""WITH RECURSIVE sous(n) AS (SELECT noeud FROM bofip_plan WHERE parent = :p
                                UNION ALL SELECT p.noeud FROM bofip_plan p JOIN sous ON p.parent = sous.n)
                           SELECT count(*) FROM bofip_plan WHERE noeud IN (SELECT n FROM sous) AND pgp IS NOT NULL""",
                        {"p": noeud}).fetchone()[0]


def _trouver_noeud(conn, noeud: str | None, serie: str | None) -> sqlite3.Row | None:
    if serie:
        s = serie.strip().upper()
        if s in ("ACTU", "ACTUALITES", "ACTUALITÉS"):
            return conn.execute("SELECT * FROM bofip_plan WHERE noeud = '@ACTU'").fetchone()
        r = conn.execute("SELECT * FROM bofip_plan WHERE code = ? AND parent IS NULL", (f"BOI-{s}",)).fetchone()
        if not r:
            raise LookupError(f"série inconnue : {serie}. Appelez bofip_plan sans argument pour la liste.")
        return r
    if not noeud:
        return None
    x = noeud.strip()
    r = conn.execute("SELECT * FROM bofip_plan WHERE noeud = ? OR code = ? ORDER BY origine = 'plan' DESC",
                     (x, x.upper())).fetchone()
    if r:
        return r
    row, _, _ = trouver_document(conn, x)
    r = conn.execute("SELECT * FROM bofip_plan WHERE pgp = ?", (row["pgp"],)).fetchone()
    if not r:
        raise LookupError(f"{x} n'a pas de nœud dans le plan")
    return r


def bofip_plan(conn: sqlite3.Connection, noeud: str | None = None, serie: str | None = None,
               profondeur: int = 1) -> Resultat:
    _exiger_bofip(conn)
    profondeur = max(1, min(int(profondeur), 4))
    racine = _trouver_noeud(conn, noeud, serie)
    lignes: list[str] = []
    docs: list[DocRef] = []
    tronque = False

    def descendre(parent: str | None, niveau: int) -> None:
        nonlocal tronque
        q = "SELECT * FROM bofip_plan WHERE parent IS NULL ORDER BY position" if parent is None else \
            "SELECT * FROM bofip_plan WHERE parent = ? ORDER BY position"
        for e in conn.execute(q, () if parent is None else (parent,)).fetchall():
            if len(lignes) >= MAX_LIGNES_PLAN:
                tronque = True
                return
            n = _compter(conn, e["noeud"])
            ind = "  " * (niveau - 1)
            ident = f"`{e['code']}`" + (f" (`{e['pgp']}`)" if e["pgp"] else "")
            marque = " [hors plan publié]" if e["origine"] == "rattache" else ""
            lignes.append(f"{ind}- **{e['libelle']}** — {ident}" + (f" — {n} doc. dessous" if n else "") + marque)
            if e["pgp"] and len(docs) < 15:
                d = conn.execute("SELECT * FROM bofip_documents WHERE pgp = ?", (e["pgp"],)).fetchone()
                if d:
                    docs.append(_docref(d, sous_titre=e["libelle"][:120]))
            if niveau < profondeur and n:
                descendre(e["noeud"], niveau + 1)

    if racine is None:
        entete = ("# BOFiP-Impôts — plan de classement\nSéries (racines). Descendez avec `noeud` = code "
                  "(ex. « BOI-IR-BASE ») ou identifiant PGP ; `serie` = sigle (IR, TVA, RES…) ; « ACTU » pour les actualités.")
        descendre(None, 1)
    else:
        ch = chemin_plan(conn, racine["pgp"]) if racine["pgp"] else [{"titre": racine["libelle"], "code": racine["code"]}]
        entete = (f"# {racine['libelle']} — `{racine['code']}`" + (f" (`{racine['pgp']}`)" if racine["pgp"] else "")
                  + "\nChemin : " + " › ".join(f"{c['titre']} ({c['code']})" for c in ch))
        if racine["pgp"]:
            entete += "\nLe nœud est lui-même un document (souvent un sommaire) : `bofip_lire` avec son identifiant."
            d = conn.execute("SELECT * FROM bofip_documents WHERE pgp = ?", (racine["pgp"],)).fetchone()
            if d:
                docs.insert(0, _docref(d, sous_titre=racine["libelle"][:120]))
        descendre(racine["noeud"], 1)
    if not lignes:
        lignes = ["(aucun sous-élément : document terminal, lisez-le avec `bofip_lire`)"]
    if tronque:
        lignes.append(f"… liste tronquée à {MAX_LIGNES_PLAN} lignes : descendez dans un nœud.")
    return Resultat(entete + "\n\n" + "\n".join(lignes), docs)


# ----------------------------------------------------------------- lecture

def table_des_matieres(texte: str) -> list[dict[str, Any]]:
    """Intertitres (« ## … ») avec position, niveau et premier § qui suit."""
    out = []
    pos = 0
    for ligne in texte.splitlines(keepends=True):
        m = re.match(r"^(#{2,7}) (.+)", ligne)
        if m:
            out.append({"n": len(out) + 1, "niveau": len(m.group(1)) - 1, "titre": m.group(2).strip(), "debut": pos})
        pos += len(ligne)
    for i, t in enumerate(out):
        fin = len(texte)
        for u in out[i + 1:]:
            if u["niveau"] <= t["niveau"]:
                fin = u["debut"]
                break
        t["fin"] = fin
        paras = re.findall(r"^§ (\d+)$", texte[t["debut"]:fin], re.M)
        t["paragraphes"] = (paras[0], paras[-1]) if paras else None
    return out


def decouper_parties(texte: str, taille: int = TAILLE_PARTIE) -> list[tuple[int, int]]:
    """Découpe en parties d'environ `taille` caractères, coupées de préférence avant un intertitre ou un §."""
    bornes: list[tuple[int, int]] = []
    debut = 0
    n = len(texte)
    while debut < n:
        if n - debut <= taille * 1.25:
            bornes.append((debut, n))
            break
        fenetre = texte[debut + taille // 2: debut + taille]
        coupe = None
        for motif in (r"\n(?=#{2,7} )", r"\n(?=§ \d+\n)", r"\n\n", r"\n"):
            ms = list(re.finditer(motif, fenetre))
            if ms:
                coupe = debut + taille // 2 + ms[-1].end()
                break
        coupe = coupe or debut + taille
        bornes.append((debut, coupe))
        debut = coupe
    return bornes or [(0, 0)]


def _articles_cites(conn, pgp: str, limite: int = 25) -> list[tuple[str, str, int]]:
    return [(r[0], r[1], r[2]) for r in conn.execute(
        """SELECT code, min(num), count(*) FROM bofip_renvois WHERE pgp = ? AND code IS NOT NULL
           GROUP BY code, num_norm ORDER BY count(*) DESC, min(position) LIMIT ?""", (pgp, limite))]


def _libelle_article(code: str, num: str) -> str:
    return f"{code}, art. {num}"


def bofip_lire(conn: sqlite3.Connection, id: str, section: int | None = None, partie: int | None = None,
               paragraphe: int | None = None) -> Resultat:
    row, courant, autres = trouver_document(conn, id)
    texte = _remplacer_node_date(conn, row["texte"] or "")
    toc = table_des_matieres(texte)
    parties = decouper_parties(texte)

    def partie_de(pos: int) -> int:
        return next((i + 1 for i, (a, b) in enumerate(parties) if a <= pos < b), len(parties))

    ch = chemin_plan(conn, row["pgp"]) if courant else []
    versions = _versions(conn, row["pgp"])
    entete = [f"# {row['boi']} (`{row['pgp']}`)" + ("" if courant else " — VERSION ANTÉRIEURE"),
              row["titre"] or "",
              f"{row['nature']} · {row['type_contenu'] or ''} · série {row['serie'] or '—'}"
              + (f" / {row['division']}" if row["division"] else "")
              + f" · publié le {row['date_publication']} · {row['permalien'] or ''}"]
    if ch:
        entete.append("Plan : " + " › ".join(f"{c['titre']} ({c['code']})" for c in ch[:-1]))
    if autres:
        entete.append("Autres documents de même identifiant : " + ", ".join(autres))
    if not courant:
        cur = conn.execute("SELECT boi, date_publication FROM bofip_documents WHERE pgp = ?", (row["pgp"],)).fetchone()
        entete.append(f"Motif d'archivage : {row['motif']} ; version courante : "
                      + (f"{cur['boi']} du {cur['date_publication']}" if cur else "aucune (retiré)"))
    if versions and courant:
        entete.append("Versions antérieures : " + ", ".join(f"{v['boi']} ({v['motif']}, id `{row['pgp']}@{v['date_publication']}`)"
                                                          for v in versions[:6]))
    docs = [_docref(row, courant)]

    corps: list[str] = []
    if section is not None:
        t = next((t for t in toc if t["n"] == int(section)), None)
        if t is None:
            raise LookupError(f"section {section} inexistante ({len(toc)} intertitres)")
        extrait = texte[t["debut"]:t["fin"]]
        if len(extrait) > LECTURE_ENTIERE:
            p = partie_de(t["debut"])
            extrait = extrait[:TAILLE_PARTIE] + f"\n\n… section tronquée : suite avec `partie={p + 1}` (ou sous-sections)."
        corps = [f"## Section {t['n']} / {len(toc)}", extrait]
    elif paragraphe is not None:
        m = re.search(rf"^§ {int(paragraphe)}$", texte, re.M)
        if not m:
            raise LookupError(f"§ {paragraphe} absent de ce document")
        p = partie_de(m.start())
        a, b = parties[p - 1]
        corps = [f"## Partie {p} / {len(parties)} (contient le § {paragraphe})", texte[a:b]]
    elif len(texte) <= LECTURE_ENTIERE and partie is None:
        corps = [texte or "(document sans texte)"]
    else:
        p = max(1, min(int(partie or 1), len(parties)))
        a, b = parties[p - 1]
        corps = [f"## Partie {p} / {len(parties)} (caractères {a}–{b} sur {len(texte)})", texte[a:b]]
        if p < len(parties):
            corps.append(f"\n… suite : `partie={p + 1}`.")

    premiere_lecture = section is None and paragraphe is None and (partie or 1) == 1
    if len(texte) > LECTURE_ENTIERE and premiere_lecture:
        lignes_toc = ["", "## Table des matières (`section=n` pour lire un intertitre, `partie=p` pour une tranche)"]
        for t in toc[:120]:
            a_, b_ = t["paragraphes"] or (None, None)
            paras = "" if a_ is None else (f" § {a_}" if a_ == b_ else f" § {a_}–{b_}")
            lignes_toc.append(f"{'  ' * (t['niveau'] - 1)}{t['n']}. {t['titre']}{paras} (partie {partie_de(t['debut'])})")
        if len(toc) > 120:
            lignes_toc.append(f"… {len(toc) - 120} intertitres de plus")
        if not toc:
            lignes_toc.append(f"(pas d'intertitres ; {len(parties)} partie(s))")
        entete += lignes_toc

    pied = []
    if courant and premiere_lecture:
        cites = _articles_cites(conn, row["pgp"])
        if cites:
            pied.append("Articles cités : " + " ; ".join(f"{_libelle_article(c, n)} ×{k}" for c, n, k in cites))
        n_in = conn.execute("SELECT count(DISTINCT pgp) FROM bofip_relations WHERE cible_pgp = ? AND type = 'references'",
                            (row["pgp"],)).fetchone()[0]
        n_out = conn.execute("SELECT count(*) FROM bofip_relations WHERE pgp = ? AND type = 'references'",
                             (row["pgp"],)).fetchone()[0]
        pied.append(f"Renvoie à {n_out} document(s) BOFiP ; cité par {n_in} document(s).")
    return Resultat("\n".join(entete) + "\n\n" + "\n".join(corps) + ("\n\n" + "\n".join(pied) if pied else ""), docs)


# ----------------------------------------------------------------- recherche

def bofip_rechercher(conn: sqlite3.Connection, requete: str, serie: str | None = None, nature: str | None = None,
                     limite: int = 20) -> Resultat:
    from interstice.outils.legi import _fts_query

    _exiger_bofip(conn)
    limite = max(1, min(int(limite), 50))
    params: dict[str, Any] = {"q": _fts_query(requete), "lim": limite}
    filtres = ""
    if serie:
        filtres += " AND (d.serie = :s OR (d.serie = 'RES' AND d.division = :s))"
        params["s"] = serie.strip().upper()
    if nature:
        n = nature.strip().lower()
        if n.startswith("actu"):
            filtres += " AND d.nature = 'Actualité'"
        elif n.startswith("rescrit"):
            filtres += " AND d.serie = 'RES'"
        elif n.startswith(("contenu", "commentaire", "doctrine")):
            filtres += " AND d.nature = 'Contenu'"
    try:
        rows = conn.execute(
            f"""SELECT d.pgp, d.boi, d.titre, d.serie, d.nature, d.date_publication,
                       snippet(bofip_fts, 1, '«', '»', '…', 24) AS extrait
                FROM bofip_fts JOIN bofip_documents d ON d.rowid = bofip_fts.rowid
                WHERE bofip_fts MATCH :q{filtres}
                ORDER BY bm25(bofip_fts, 5.0, 1.0) LIMIT :lim""", params).fetchall()
    except sqlite3.OperationalError as e:
        raise ValueError(f"requête plein texte invalide ({e}) : mots simples ou \"expression exacte\"") from e
    portee = ", ".join(x for x in (f"série {serie}" if serie else "", nature or "") if x) or "tout le BOFiP"
    lignes = [f"# Recherche BOFiP « {requete} » — {len(rows)} résultat(s) ({portee})", ""]
    docs = [DocRef("recherche", requete, f"BOFiP : {requete}", portee, None)]
    for r in rows:
        extrait = re.sub(r"\s+", " ", r["extrait"] or "")
        lignes.append(f"- **{r['boi']}** (`{r['pgp']}`, {r['date_publication']}) — {libelle_court(r['titre'])[:140]}\n"
                      f"  {extrait}")
        docs.append(_docref(r))
    return Resultat("\n".join(lignes), docs[:16])


# ----------------------------------------------------------------- doctrine d'un article

_LATINS = r"bis|ter|quater|quinquies|sexies|septies|octies|nonies|novies|decies|undecies|duodecies|terdecies|quaterdecies|quindecies|sexdecies|septdecies|octodecies|novodecies|vicies"


def cle_code(conn: sqlite3.Connection, texte: str) -> tuple[str, str | None]:
    """Clé de `bofip_renvois.code` (sigle fiscal ou intitulé) et cid LEGI éventuel."""
    from interstice.bofip.renvois import ABREVIATIONS, TITRES_FISCAUX, norm_titre
    t = texte.strip()
    u = t.upper().replace(" ", "")
    fiscaux = {"CGI", "LPF", "CIBS", "CDOUANES", "CGI-AI", "CGI-AII", "CGI-AIII", "CGI-AIV"}
    if u in fiscaux:
        cle = u
    elif t in ABREVIATIONS:
        titre = ABREVIATIONS[t]
        cle = next((k for k, v in TITRES_FISCAUX.items() if v == titre), titre)
    else:
        cle = None
        try:
            from interstice.outils.requetes import resoudre_texte
            ref = resoudre_texte(conn, t)
            cle = ref.sigle or norm_titre(ref.titre)
        except Exception:  # noqa: BLE001 — base LEGI absente ou texte inconnu
            cle = norm_titre(t)
    cid = conn.execute("SELECT texte_cid FROM bofip_renvois WHERE code = ? AND texte_cid IS NOT NULL LIMIT 1",
                       (cle,)).fetchone()
    return cle, cid[0] if cid else None


def _motif_num(num: str) -> re.Pattern:
    jetons = [re.escape(j) for j in re.split(r"[\s  .]+", num.strip()) if j]
    corps = r"[\s  .]*".join(jetons)
    return re.compile(rf"(?<![\w-]){corps}(?![\w-]|[\s  ]+(?:{_LATINS}|[A-Z]{{1,3}})\b)")


def paragraphes_citant(texte: str, num: str) -> list[str]:
    """Numéros de § dont le texte mentionne ce numéro d'article (repérage approché)."""
    motif = _motif_num(num)
    out: list[str] = []
    courant = None
    for ligne in texte.splitlines():
        m = re.match(r"^§ (\d+)$", ligne)
        if m:
            courant = m.group(1)
        elif courant and courant not in out and motif.search(ligne):
            out.append(courant)
    return out


def bofip_pour_article(conn: sqlite3.Connection, texte: str, num: str, limite: int = 40,
                       nature: str | None = None) -> Resultat:
    _exiger_bofip(conn)
    cle, cid = cle_code(conn, texte)
    nn = normaliser_num(num)
    if not nn:
        raise ValueError("numéro d'article vide")
    filtre = ""
    if nature and nature.lower().startswith("actu"):
        filtre = " AND d.nature = 'Actualité'"
    elif nature and nature.lower().startswith(("contenu", "commentaire", "doctrine")):
        filtre = " AND d.nature = 'Contenu'"
    rows = conn.execute(
        f"""SELECT d.pgp, d.boi, d.titre, d.nature, d.serie, d.date_publication, count(*) AS n
            FROM bofip_renvois r JOIN bofip_documents d ON d.pgp = r.pgp
            WHERE (r.code = :c OR (:cid IS NOT NULL AND r.texte_cid = :cid)) AND r.num_norm = :n{filtre}
            GROUP BY d.pgp
            ORDER BY d.nature = 'Actualité', d.serie = 'RES', n DESC, d.date_publication DESC""",
        {"c": cle, "cid": cid, "n": nn}).fetchall()
    total = len(rows)
    rows = rows[:max(1, min(int(limite), 200))]
    lib = _libelle_article(cle, num)
    lignes = [f"# Doctrine BOFiP citant {lib} — {total} document(s)"
              + (f" (affichés : {len(rows)})" if total > len(rows) else ""),
              "Tri : commentaires (les plus citants d'abord), puis rescrits, puis actualités. "
              "§ = paragraphes où l'article est mentionné (lire avec `bofip_lire` + `paragraphe`).", ""]
    docs: list[DocRef] = []
    for r in rows:
        texte_doc = conn.execute("SELECT texte FROM bofip_documents WHERE pgp = ?", (r["pgp"],)).fetchone()[0]
        paras = paragraphes_citant(texte_doc or "", num)
        p = f" — § {', '.join(paras[:12])}" + ("…" if len(paras) > 12 else "") if paras else ""
        lignes.append(f"- **{r['boi']}** (`{r['pgp']}`, {r['date_publication']}) — {libelle_court(r['titre'])[:120]} "
                      f"— {r['n']} mention(s){p}")
        if len(docs) < 15:
            docs.append(_docref(r))
    if not rows:
        lignes.append("(aucun document ne cite cet article sous cette forme ; essayez `bofip_rechercher` "
                      "avec le numéro entre guillemets)")
    return Resultat("\n".join(lignes), docs)


# ----------------------------------------------------------------- vues pour le panneau

_DANGEREUX = re.compile(r"<(script|style|iframe|object|embed|form)\b.*?</\1\s*>", re.I | re.S)
_ATTR_EVT = re.compile(r"\s+(?:on\w+|contenteditable)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_HREF_JS = re.compile(r"""href\s*=\s*(["'])\s*javascript:[^"']*\1""", re.I)
_LIEN_INTERNE = re.compile(r"""href\s*=\s*"(?:Contenu|Actualit(?:%C3%A9|é|e))(?:\.[^:"]*)?:(\d+-PGP)(?:#([^"]*))?\"""", re.I)
_LIEN_FICHIER = re.compile(r"""href\s*=\s*"Fichier:(\d+-PGP)[^"]*\"""", re.I)
_IMAGE = re.compile(r"""src\s*=\s*"Image:(\d+-PGP)[^"]*\"""", re.I)
_SPAN = re.compile(r"<span>([^<]{3,200})</span>")


def assainir(html: str | None) -> str:
    if not html:
        return ""
    return _HREF_JS.sub('href="#"', _ATTR_EVT.sub("", _DANGEREUX.sub("", html)))


def _articles_legi(conn, pgp: str) -> list[dict[str, Any]]:
    """Articles cités, avec l'identifiant de la version LEGI en vigueur quand la base LEGI est présente."""
    try:  # base LEGI dans la même base ou attachée
        conn.execute("SELECT 1 FROM articles LIMIT 1")
        a_legi = True
    except sqlite3.OperationalError:
        a_legi = False
    aujourdhui = dt.date.today().isoformat()
    out = []
    for r in conn.execute("""SELECT code, texte_cid, num_norm, min(num) AS num, count(*) AS n FROM bofip_renvois
                             WHERE pgp = ? AND code IS NOT NULL GROUP BY code, num_norm
                             ORDER BY min(position)""", (pgp,)):
        art_id = None
        if a_legi and r["texte_cid"]:
            try:
                from interstice.outils.requetes import article_a_date
                art_id = article_a_date(conn, r["texte_cid"], r["num"], aujourdhui)["id"]
            except LookupError:
                pass
        out.append({"code": r["code"], "num": r["num"], "texte_cid": r["texte_cid"], "article_id": art_id,
                    "libelle": _libelle_article(r["code"], r["num"]), "occurrences": r["n"]})
    return out


def _lier_articles(html: str, articles: list[dict[str, Any]]) -> str:
    """<span>article 150-0 B ter du CGI</span> → lien data-article vers la version LEGI en vigueur."""
    from interstice.bofip.renvois import Resolveurs, extraire_renvois
    cibles = {(a["code"], normaliser_num(a["num"])): a["article_id"] for a in articles if a["article_id"]}
    if not cibles:
        return html
    res = Resolveurs(None)

    def rep(m: re.Match) -> str:
        for r in extraire_renvois(m.group(1), res):
            art = cibles.get((r["code"], r["num_norm"]))
            if art:
                return f'<a href="#" data-article="{art}">{m.group(1)}</a>'
        return m.group(0)
    return _SPAN.sub(rep, html)


def vue_bofip(conn: sqlite3.Connection, id: str) -> dict[str, Any]:
    """Document pour le panneau de lecture. LookupError si introuvable.

    Liens internes réécrits : `<a data-bofip="NNN-PGP" data-ancre="…">` (document BOFiP),
    `<a data-bofip-fichier="NNN-PGP">` (pièce jointe), `<img data-bofip-image="NNN-PGP">` (image non servie),
    `<a data-article="LEGIARTI…">` (article de loi en vigueur, si la base LEGI est présente).
    """
    row, courant, autres = trouver_document(conn, id)
    html = assainir(row["html"])
    ids_img = sorted(set(_IMAGE.findall(html)))
    titres_img = dict(conn.execute(f"SELECT pgp, titre FROM bofip_fichiers WHERE pgp IN ({','.join('?' * len(ids_img))})",
                                   ids_img).fetchall()) if ids_img else {}
    html = _LIEN_INTERNE.sub(lambda m: f'href="#" data-bofip="{m.group(1)}"' + (f' data-ancre="{m.group(2)}"' if m.group(2) else ""), html)
    html = _LIEN_FICHIER.sub(lambda m: f'href="#" data-bofip-fichier="{m.group(1)}"', html)
    html = _IMAGE.sub(lambda m: f'data-bofip-image="{m.group(1)}" alt="{(titres_img.get(m.group(1)) or "image").replace(chr(34), "")}"', html)
    html = _remplacer_node_date(conn, html)
    articles = _articles_legi(conn, row["pgp"]) if courant else []
    html = _lier_articles(html, articles)

    def ref(p: str) -> dict[str, Any]:
        d = conn.execute("SELECT pgp, boi, titre, nature, date_publication FROM bofip_documents WHERE pgp = ?", (p,)).fetchone()
        return ({"id": d["pgp"], "boi": d["boi"], "titre": d["titre"], "nature": d["nature"], "date": d["date_publication"],
                 "disponible": True} if d else {"id": p, "boi": None, "titre": None, "nature": None, "date": None,
                                                  "disponible": False})

    sortantes = [dict(ref(r["cible_pgp"]), type=r["type"], cible_type=r["cible_type"])
                 for r in conn.execute("SELECT * FROM bofip_relations WHERE pgp = ? AND type = 'references' ORDER BY position",
                                       (row["pgp"],))]
    entrantes = [dict(ref(r[0]), type="isReferencedBy", cible_type="Contenu")
                 for r in conn.execute("SELECT DISTINCT pgp FROM bofip_relations WHERE cible_pgp = ? AND type = 'references'",
                                       (row["pgp"],))]
    fichiers = [dict(pgp=f["pgp"], type=f["type"], titre=f["titre"], mime=f["mime"], taille=f["taille"], chemin=f["chemin"])
                for f in conn.execute("""SELECT f.* FROM bofip_relations r JOIN bofip_fichiers f ON f.pgp = r.cible_pgp
                                         WHERE r.pgp = ? AND r.type = 'requires'""", (row["pgp"],))]
    return {
        "id": _doc_id(row, courant), "pgp": row["pgp"], "boi": row["boi"], "boi_base": row["boi_base"],
        "titre": row["titre"], "serie": row["serie"], "division": row["division"], "nature": row["nature"],
        "type_contenu": row["type_contenu"], "date": row["date_publication"], "permalien": row["permalien"],
        "courant": courant, "homonymes": autres,
        "chemin": chemin_plan(conn, row["pgp"]) if courant else [],
        "html": html,
        "relations": {"sortantes": sortantes, "entrantes": entrantes, "fichiers": fichiers},
        "articles_cites": articles,
        "versions": [{"id": f"{row['pgp']}@{v['date_publication']}", "boi": v["boi"], "date": v["date_publication"],
                      "motif": v["motif"]} for v in _versions(conn, row["pgp"])],
    }


def vue_bofip_noeud(conn: sqlite3.Connection, noeud: str | None = None) -> dict[str, Any]:
    """Nœud du plan pour le panneau : enfants avec nombre de documents (racines si `noeud` est None)."""
    racine = _trouver_noeud(conn, noeud, None) if noeud else None
    q = ("SELECT * FROM bofip_plan WHERE parent = ? ORDER BY position", (racine["noeud"],)) if racine else \
        ("SELECT * FROM bofip_plan WHERE parent IS NULL ORDER BY position", ())
    enfants = [{"noeud": e["noeud"], "id": e["pgp"], "code": e["code"], "titre": e["libelle"], "origine": e["origine"],
                "nb_documents": _compter(conn, e["noeud"])} for e in conn.execute(*q)]
    return {"noeud": racine["noeud"] if racine else None, "id": racine["pgp"] if racine else None,
            "code": racine["code"] if racine else None, "titre": racine["libelle"] if racine else "BOFiP-Impôts",
            "chemin": chemin_plan(conn, racine["pgp"]) if racine and racine["pgp"] else [], "enfants": enfants}


def recherche_bofip(conn: sqlite3.Connection, q: str, serie: str | None = None, limite: int = 20) -> list[dict[str, Any]]:
    from interstice.outils.legi import _fts_query
    params: dict[str, Any] = {"q": _fts_query(q), "lim": max(1, min(limite, 100))}
    filtre = ""
    if serie:
        filtre = " AND (d.serie = :s OR (d.serie = 'RES' AND d.division = :s))"
        params["s"] = serie.upper()
    rows = conn.execute(
        f"""SELECT d.pgp, d.boi, d.titre, d.serie, d.nature, d.date_publication,
                   snippet(bofip_fts, 1, '<mark>', '</mark>', '…', 30) AS extrait
            FROM bofip_fts JOIN bofip_documents d ON d.rowid = bofip_fts.rowid
            WHERE bofip_fts MATCH :q{filtre} ORDER BY bm25(bofip_fts, 5.0, 1.0) LIMIT :lim""", params).fetchall()
    return [{"id": r["pgp"], "boi": r["boi"], "titre": r["titre"], "serie": r["serie"], "nature": r["nature"],
             "date": r["date_publication"], "extrait_html": assainir(r["extrait"])} for r in rows]


# ----------------------------------------------------------------- registre

_ID = {"type": "string", "description": "Identifiant : BOI daté ou non (« BOI-RPPM-PVBMI-30-10-60 »), PGP (« 739-PGP »), "
                                         "ACTU-AAAA-NNNNN, ou « NNN-PGP@AAAA-MM-JJ » pour une version antérieure."}


def _schema(props: dict, requis: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": requis or [], "additionalProperties": False}


OUTILS_BOFIP = [
    Outil("bofip_plan",
          "Plan de classement du BOFiP-Impôts (doctrine administrative) : séries → divisions → titres → chapitres → "
          "sections, avec le nombre de documents sous chaque nœud. Sans argument : liste des séries (IR, BIC, TVA, "
          "RES = rescrits, Annexes, Actualités…). Descendez avec le code (« BOI-IR-BASE ») ou l'identifiant renvoyé.",
          _schema({"noeud": {"type": "string", "description": "Code du plan (BOI-IR-BASE-10), PGP ou identifiant BOI."},
                   "serie": {"type": "string", "description": "Sigle de série (IR, RPPM, TVA, RES…) ou « ACTU »."},
                   "profondeur": {"type": "integer", "minimum": 1, "maximum": 4,
                                  "description": "Niveaux à déplier (défaut 1)."}}),
          bofip_plan),
    Outil("bofip_lire",
          "Lit un document BOFiP (commentaire, rescrit, barème, annexe, actualité) : métadonnées, chemin dans le plan, "
          "texte avec intertitres (##) et numéros de paragraphe (§ 10). Un document long est servi par parties "
          "(~12 000 caractères) avec sa table des matières : `section` = n° d'intertitre, `partie` = n° de tranche, "
          "`paragraphe` = n° de § (ex. 150 pour « § 150 »).",
          _schema({"id": _ID, "section": {"type": "integer", "minimum": 1},
                   "partie": {"type": "integer", "minimum": 1}, "paragraphe": {"type": "integer", "minimum": 0}}, ["id"]),
          bofip_lire),
    Outil("bofip_rechercher",
          "Recherche plein texte dans le BOFiP en vigueur (titres et textes ; mots ou syntaxe FTS5 : \"expression exacte\", "
          "OR, NEAR). `serie` restreint à une série (IR, TVA…, inclut les rescrits de cette matière) ; `nature` : "
          "« contenu », « rescrit » ou « actualite ».",
          _schema({"requete": {"type": "string"}, "serie": {"type": "string"},
                   "nature": {"type": "string", "enum": ["contenu", "rescrit", "actualite"]},
                   "limite": {"type": "integer", "minimum": 1, "maximum": 50}}, ["requete"]),
          bofip_rechercher),
    Outil("bofip_pour_article",
          "Doctrine administrative qui commente un article de loi : documents BOFiP (commentaires, rescrits, actualités) "
          "citant l'article, avec le nombre de mentions et les § concernés. Pont entre la loi (outils LEGI) et la doctrine.",
          _schema({"texte": {"type": "string", "description": "Sigle (CGI, CGI-AII, CGI-AIII, LPF, CIBS…) ou intitulé du code."},
                   "num": {"type": "string", "description": "Numéro d'article (« 150-0 B ter », « L. 80 A »)."},
                   "nature": {"type": "string", "enum": ["contenu", "actualite"]},
                   "limite": {"type": "integer", "minimum": 1, "maximum": 200}}, ["texte", "num"]),
          bofip_pour_article),
]
