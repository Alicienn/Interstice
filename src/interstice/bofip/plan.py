"""Construction de l'arborescence de navigation `bofip_plan`.

1. Nœuds du dernier plan de classement publié (origine « plan ») : chaque nœud est un document
   (série → division → titre → chapitre → section → sous-section).
2. Documents courants absents du plan publié (≈ 600 dans le stock de septembre 2026 : annexes,
   formulaires, lettres types, rescrits récents, quelques commentaires) : rattachés au nœud dont le
   code de classement est le plus long préfixe de leur identifiant (BOI-BA-RICI-20-60 → BOI-BA-RICI-20 ;
   BOI-RES-TVA-000272 → BOI-RES-TVA ; BOI-ANNX-000099 → BOI-ANNX-000000), origine « rattache ».
3. Actualités : nœud virtuel « Actualités » → une année → actualités (plus récentes d'abord).
Ainsi tout document courant est atteignable en descendant l'arborescence.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from interstice.bofip.parser import lire_plan

RACINE_ACTU = "@ACTU"
RACINE_HORS_PLAN = "@HORS-PLAN"
_FAMILLES = re.compile(r"-(ANNX|BAREME|FORM|LETTRE|CARTE)-\d+$")


def cle_naturelle(code: str | None) -> tuple:
    return tuple((0, int(s), "") if s.isdigit() else (1, 0, s) for s in re.split(r"[-\s]+", code or ""))


def libelle_court(titre: str | None) -> str:
    """Dernier segment d'un titre BOFiP « IR - Base d'imposition - … - Section 2 : … »."""
    parts = [p.strip() for p in re.split(r"\s+[-–]\s+", titre or "") if p.strip()]
    return parts[-1] if parts else (titre or "")


def construire_plan(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT date, archive, xml FROM bofip_plans_publies ORDER BY date DESC, archive DESC LIMIT 1").fetchone()
    lignes: list[tuple] = []  # (noeud, parent, position, libelle, code, pgp, profondeur, origine)
    prof: dict[str, int] = {}
    par_code: dict[str, str] = {}
    n_enfants: dict[str | None, int] = defaultdict(int)
    if row:
        for n in lire_plan(row["xml"].encode("utf-8")):
            lignes.append((n.pgp, n.parent, n.position, n.libelle, n.code, n.pgp, n.profondeur, "plan"))
            prof[n.pgp] = n.profondeur
            par_code.setdefault(n.code, n.pgp)
            n_enfants[n.parent] += 1
    dans_plan = set(prof)

    # 2. documents courants hors plan
    hors = conn.execute(
        "SELECT pgp, boi_base, titre, serie FROM bofip_documents WHERE nature = 'Contenu'").fetchall()
    hors = sorted((r for r in hors if r["pgp"] not in dans_plan), key=lambda r: cle_naturelle(r["boi_base"]))
    n_rattaches = n_orphelins = 0
    for r in hors:
        parent = _parent_deduit(r["boi_base"] or "", par_code)
        if parent is None:
            if RACINE_HORS_PLAN not in prof:
                lignes.append((RACINE_HORS_PLAN, None, 10_000, "Documents hors plan de classement", None, None, 0, "virtuel"))
                prof[RACINE_HORS_PLAN] = 0
            parent = RACINE_HORS_PLAN
            n_orphelins += 1
        else:
            n_rattaches += 1
        p = prof[parent] + 1
        lignes.append((r["pgp"], parent, n_enfants[parent], f"{libelle_court(r['titre'])}", r["boi_base"], r["pgp"], p,
                       "rattache"))
        n_enfants[parent] += 1
        prof[r["pgp"]] = p
        if r["boi_base"]:
            par_code.setdefault(r["boi_base"], r["pgp"])  # un document hors plan peut en accueillir un autre

    # 3. actualités par année
    actus = conn.execute("""SELECT pgp, boi, titre, date_publication FROM bofip_documents WHERE nature = 'Actualité'
                            ORDER BY date_publication DESC, boi DESC""").fetchall()
    if actus:
        lignes.append((RACINE_ACTU, None, 9_000, "Actualités", "ACTU", None, 0, "virtuel"))
        annees: dict[str, int] = {}
        for a in actus:
            an = (a["date_publication"] or "????")[:4]
            noeud_an = f"{RACINE_ACTU}-{an}"
            if an not in annees:
                annees[an] = 0
                lignes.append((noeud_an, RACINE_ACTU, len(annees) - 1, f"Actualités {an}", f"ACTU-{an}", None, 1, "virtuel"))
            lignes.append((a["pgp"], noeud_an, annees[an], a["titre"], a["boi"], a["pgp"], 2, "virtuel"))
            annees[an] += 1

    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM bofip_plan")
        conn.executemany("INSERT OR REPLACE INTO bofip_plan VALUES (?,?,?,?,?,?,?,?)", lignes)
        conn.execute("INSERT OR REPLACE INTO bofip_meta VALUES ('plan_date', ?)", (row["date"] if row else "",))
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    return {"plan_publie": row["date"] if row else None, "noeuds_plan": len(dans_plan), "rattaches": n_rattaches,
            "hors_plan": n_orphelins, "actualites": len(actus), "total_noeuds": len(lignes)}


def _parent_deduit(base: str, par_code: dict[str, str]) -> str | None:
    segs = base.split("-")
    for k in range(len(segs) - 1, 1, -1):
        cand = "-".join(segs[:k])
        if cand in par_code:
            return par_code[cand]
    if m := _FAMILLES.search(base):
        return par_code.get(f"BOI-{m.group(1)}-000000")
    return None
