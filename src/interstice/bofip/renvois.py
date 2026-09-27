"""Articles de loi cités par la doctrine BOFiP → table `bofip_renvois`.

Réutilise `interstice.graph.citations.extraire` (repérage de « article(s) … » et du texte visé),
après une normalisation propre au style du BOFiP :
- « CGI, art. 238 bis » / « CGI, ann. III, art. 46 quater-0 ZZ » / « C. com., art. L. 225-102 »
  → « article 238 bis du code général des impôts », « article … de l'annexe III au code général des impôts »…
- sigles et abréviations après « du » / « au » : « du CGI », « du LPF », « du CoMoFi », « du C. com. »…
  → intitulé complet du code.
Le texte visé est désigné par une clé : le sigle pour le périmètre fiscal (CGI, CGI-AI…CGI-AIV, LPF,
CIBS, CDOUANES), sinon l'intitulé du code en minuscules (« code de commerce »), ou « loi n° 2017-1837 ».
Si une base LEGI est disponible (`conn_legi`), le numéro est résolu par plus long préfixe existant
(« 150-0 B ter du » → « 150-0 B ter ») et le LEGITEXT est renseigné ; sinon le numéro est gardé tel qu'écrit.
Une citation sans code identifiable (« l'article 287 » seul) est conservée avec `code` NULL.
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections import defaultdict

from interstice.graph.citations import _LISTE_SEP, _NUM, extraire
from interstice.legi.numeros import normaliser_num

# clé → intitulé complet (minuscules) ; les clés en majuscules sont les sigles fiscaux
TITRES_FISCAUX = {
    "CGI": "code général des impôts",
    "LPF": "livre des procédures fiscales",
    "CIBS": "code des impositions sur les biens et services",
    "CDOUANES": "code des douanes",
}
# abréviation telle qu'écrite au BOFiP → intitulé complet
ABREVIATIONS = {
    "CGI": "code général des impôts", "CGl": "code général des impôts",
    "LPF": "livre des procédures fiscales", "CIBS": "code des impositions sur les biens et services",
    "C. douanes": "code des douanes", "CoMoFi": "code monétaire et financier", "Comofi": "code monétaire et financier",
    "CMF": "code monétaire et financier", "C. mon. fin.": "code monétaire et financier",
    "CCH": "code de la construction et de l'habitation", "C. com.": "code de commerce", "C. com": "code de commerce",
    "CPC exéc.": "code des procédures civiles d'exécution", "C. trav.": "code du travail",
    "C. civ.": "code civil", "CSS": "code de la sécurité sociale", "C. rur.": "code rural et de la pêche maritime",
    "CGCT": "code général des collectivités territoriales", "CASF": "code de l'action sociale et des familles",
    "C. envir.": "code de l'environnement", "CJA": "code de justice administrative", "C. urb.": "code de l'urbanisme",
    "C. assur.": "code des assurances", "CSP": "code de la santé publique", "C. proc. civ.": "code de procédure civile",
    "C. proc. Civ.": "code de procédure civile", "C. proc. Civ": "code de procédure civile",
    "CPC": "code de procédure civile", "C. for.": "code forestier", "CPI": "code de la propriété intellectuelle",
    "CPCE": "code des postes et des communications électroniques", "C. consom.": "code de la consommation",
    "C. éduc.": "code de l'éducation", "C. transp.": "code des transports", "COJ": "code de l'organisation judiciaire",
    "C. pén.": "code pénal", "C. patr.": "code du patrimoine", "C. tourisme": "code du tourisme",
    "C. serv. nat.": "code du service national", "CGPPP": "code général de la propriété des personnes publiques",
    "C. mut.": "code de la mutualité", "C. énergie": "code de l'énergie", "C. sport": "code du sport",
}
_ANNEXES = {"I": "CGI-AI", "II": "CGI-AII", "III": "CGI-AIII", "IV": "CGI-AIV"}
_ROMAIN = {"1": "I", "2": "II", "3": "III", "4": "IV"}

_ABR = "|".join(re.escape(a) for a in sorted(ABREVIATIONS, key=len, reverse=True))
_FIN_ABR = r"(?![A-Za-zÀ-ÿ])"
_LISTE = rf"{_NUM}(?:{_LISTE_SEP}{_NUM})*"
# « CGI, ann. III, art. 46 » / « CGI, art. 238 bis » / « C. com., art. L. 225-102 »
RE_SIGLE_ART = re.compile(
    rf"(?<![\w.])(?P<abr>{_ABR}){_FIN_ABR}\s*,?\s*(?:ann(?:exe|x)?\.?\s*(?P<ann>IV|III|II|I|[1-4])\s*,\s*)?"
    rf"art(?:icles?|\.)\s*(?P<liste>{_LISTE})")
RE_PREMIER = re.compile(r"(\b[Aa]rt(?:icles?|\.)\s+)(\d+)(?:er|ᵉʳ)\b")
# « du CGI », « au CGI », « du C. com. »
RE_DU_SIGLE = re.compile(rf"\b(?P<prep>du|au)\s+(?P<abr>{_ABR}){_FIN_ABR}")


def norm_titre(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower().replace("’", "'")).strip()


def normaliser_citations(texte: str) -> str:
    def sigle_art(m: re.Match) -> str:
        titre = ABREVIATIONS[m["abr"]]
        if m["ann"] and titre == "code général des impôts":
            ann = _ROMAIN.get(m["ann"], m["ann"])
            return f"article {m['liste']} de l'annexe {ann} au code général des impôts"
        return f"article {m['liste']} du {titre}"

    t = RE_PREMIER.sub(lambda m: m.group(1) + m.group(2), texte)  # « article 1er du CGI » → « article 1 du CGI »
    t = RE_SIGLE_ART.sub(sigle_art, t)
    return RE_DU_SIGLE.sub(lambda m: f"{m['prep']} {ABREVIATIONS[m['abr']]}", t)


class Resolveurs:
    """Résolution des textes (clé) et des numéros (base LEGI facultative)."""

    def __init__(self, conn_legi: sqlite3.Connection | None = None):
        self.cid: dict[str, str] = {}  # clé → LEGITEXT (cid)
        self.titres: list[tuple[str, str]] = [(v, k) for k, v in TITRES_FISCAUX.items()]
        self.titres += [(v, v) for v in set(ABREVIATIONS.values()) if v not in TITRES_FISCAUX.values()]
        self.nums: dict[tuple[str, str], str] = {}  # (cid, num_norm) → num LEGI
        if conn_legi is not None and _a_legi(conn_legi):
            self._charger(conn_legi)
        self.titres.sort(key=lambda t: -len(t[0]))

    def _charger(self, conn: sqlite3.Connection) -> None:
        from interstice.config import CODES_FISCAUX
        from interstice.outils.requetes import SIGLES
        vus = {t for t, _ in self.titres}
        for cid, titre in conn.execute(
                "SELECT cid, max(titre) FROM textes WHERE nature = 'CODE' AND titre IS NOT NULL GROUP BY cid"):
            # « Code de la sécurité sociale. », « Code général des impôts, CGI. » → intitulé nu
            t = norm_titre(re.sub(r"(?:,\s*[A-Z][A-Z0-9]{1,12})?[\s.]*$", "", titre))
            # identifiants de référence d'abord (le titre LEGI du CGI est « Code général des impôts, CGI. »)
            cle = CODES_FISCAUX.get(cid) or next((s for s, motif in SIGLES.items() if re.search(motif, titre, re.I)), None)
            if cle:
                self.cid.setdefault(cle, cid)
            else:
                self.cid.setdefault(t, cid)
                if t not in vus:
                    self.titres.append((t, t))
                    vus.add(t)
        for cid in set(self.cid.values()):  # une requête par code : index articles_texte_num
            for nn, num in conn.execute("SELECT num_norm, max(num) FROM articles WHERE texte_cid = ? "
                                        "AND num_norm IS NOT NULL GROUP BY num_norm", (cid,)):
                self.nums[(cid, nn)] = num

    def texte(self, kind: str, valeur: str) -> str | None:
        if kind == "annexe":
            return _ANNEXES.get(valeur)
        if kind == "titre":
            v = norm_titre(valeur)
            for titre, cle in self.titres:
                if v.startswith(titre):
                    return cle
            return None
        return f"{kind} n° {valeur}"  # loi, ordonnance, décret, arrêté

    def num(self, cle: str, cand: str) -> str | None:
        cid = self.cid.get(cle)
        return self.nums.get((cid, cand)) if cid else None


def _a_legi(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('articles','textes')").fetchone()[0] == 2


def extraire_renvois(texte: str, res: Resolveurs) -> list[dict]:
    out = []
    for r in extraire(normaliser_citations(texte or ""), None, res.num, res.texte):  # type: ignore[arg-type]
        num = r.num or re.sub(r"\s+", " ", r.brut).strip()
        out.append({"brut": r.brut, "code": r.cible_cid, "texte_cid": res.cid.get(r.cible_cid) if r.cible_cid else None,
                    "num": num, "num_norm": normaliser_num(num), "resolu": int(r.num is not None),
                    "plage": r.plage, "formule": r.contexte_cible})
    return out


def construire_renvois_bofip(conn: sqlite3.Connection, conn_legi: sqlite3.Connection | None = None) -> dict:
    """Reconstruit `bofip_renvois` pour toutes les versions courantes. `conn_legi` : base LEGI (défaut : conn)."""
    t0 = time.time()
    res = Resolveurs(conn_legi if conn_legi is not None else conn)
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM bofip_renvois")
        for pgp, texte in conn.execute("SELECT pgp, texte FROM bofip_documents").fetchall():
            rows = [(pgp, i, r["brut"], r["code"], r["texte_cid"], r["num"], r["num_norm"], r["resolu"], r["plage"],
                     r["formule"]) for i, r in enumerate(extraire_renvois(texte, res))]
            conn.executemany("INSERT INTO bofip_renvois VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    stats = dict(conn.execute("""SELECT count(*) AS total, sum(code IS NOT NULL) AS code_identifie,
                                        sum(resolu) AS resolus, count(DISTINCT pgp) AS documents FROM bofip_renvois""").fetchone())
    par_code = defaultdict(int)
    for code, c in conn.execute("SELECT code, count(*) FROM bofip_renvois WHERE code IS NOT NULL GROUP BY code "
                                "ORDER BY 2 DESC LIMIT 8"):
        par_code[code] = c
    stats["par_code"] = dict(par_code)
    stats["legi"] = bool(res.nums)
    stats["secondes"] = round(time.time() - t0, 1)
    return stats
