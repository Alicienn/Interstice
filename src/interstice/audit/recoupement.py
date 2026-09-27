"""Recoupement avec un pipeline indépendant : le jeu AgentPublic/legi (DINUM, Hugging Face).

Compare, code par code, l'ensemble des versions d'articles (identifiants LEGIARTI) de notre base à
celui publié par AgentPublic. Tout identifiant présent chez eux et absent chez nous est un trou
potentiel à expliquer (le reste s'explique d'ordinaire par la différence de date des instantanés).

    uv run --with pyarrow python -m interstice.audit.recoupement
Fichiers attendus : data/recoupement/<nom>.parquet (voir README).
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

from interstice.config import DATA, DB_PATH
from interstice.outils.requetes import cid_par_sigle
from interstice.store.db import connect

FICHIERS = {  # fichier AgentPublic → sigles couverts
    "legi_code_general_des_impots": ("CGI", "CGI-AI", "CGI-AII", "CGI-AIII", "CGI-AIV"),
    "legi_livre_des_procedures_fiscales": ("LPF",),
    "legi_code_des_impositions_sur_les_biens_et_services": ("CIBS",),
    "legi_code_des_douanes": ("CDOUANES",),
}


def _lire(path: Path) -> dict[str, tuple[str, str, str, str]]:
    import pyarrow.parquet as pq

    t = pq.read_table(path, columns=["doc_id", "title", "status", "start_date", "number"])
    out = {}
    for doc, titre, statut, debut, num in zip(*(t.column(c).to_pylist() for c in t.column_names)):
        out[doc] = (titre, statut, debut, num)
    return out


def recouper(dossier: Path = DATA / "recoupement") -> str:
    conn = connect(DB_PATH, lecture_seule=True)
    L = [f"# Recoupement avec AgentPublic/legi — {time.strftime('%Y-%m-%d %H:%M')}", "",
         "| fichier | titres couverts | versions chez eux | chez nous (mêmes codes) | communes | absentes chez nous | absentes chez eux |",
         "|---|---|---|---|---|---|---|"]
    details = []
    sigles = cid_par_sigle(conn)
    for nom, couverts in FICHIERS.items():
        p = dossier / f"{nom}.parquet"
        if not p.exists():
            L.append(f"| {nom} | fichier absent | | | | | |")
            continue
        eux = _lire(p)
        titres = sorted({v[0] for v in eux.values()})
        cids = [sigles[s] for s in couverts if s in sigles]
        nous = {r[0]: (r[1], r[2], r[3]) for r in conn.execute(
            f"SELECT id, etat, date_debut, num FROM articles WHERE texte_cid IN ({','.join('?' * len(cids))})", cids)}
        manquants = sorted(set(eux) - set(nous))
        en_plus = sorted(set(nous) - set(eux))
        L.append(f"| {nom} | {'; '.join(titres)} | {len(eux)} | {len(nous)} | {len(set(eux) & set(nous))} "
                 f"| {len(manquants)} | {len(en_plus)} |")
        if manquants:
            ailleurs = {r[0]: r[1] for r in conn.execute(
                f"SELECT id, texte_cid FROM articles WHERE id IN ({','.join('?' * len(manquants[:900]))})", manquants[:900])}
            details.append(f"\n### {nom} — {len(manquants)} version(s) présente(s) chez AgentPublic, absente(s) chez nous")
            details.append("Par statut : " + ", ".join(f"{k} {v}" for k, v in Counter(eux[m][1] for m in manquants).most_common()))
            if ailleurs:
                details.append(f"Dont {len(ailleurs)} présentes dans notre base mais rattachées à un autre texte.")
            for m in manquants[:15]:
                details.append(f"- `{m}` art. {eux[m][3]} ({eux[m][1]}, début {eux[m][2]}) — {eux[m][0]}")
        if en_plus:
            details.append(f"\n### {nom} — {len(en_plus)} version(s) chez nous, absente(s) chez AgentPublic")
            details.append("Par état : " + ", ".join(f"{k} {v}" for k, v in Counter(nous[m][0] for m in en_plus).most_common()))
            recent = sorted(en_plus, key=lambda m: nous[m][1] or "", reverse=True)[:8]
            for m in recent:
                details.append(f"- `{m}` art. {nous[m][2]} ({nous[m][0]}, début {nous[m][1]})")
    return "\n".join(L + details)


if __name__ == "__main__":
    rapport = recouper()
    dest = DATA / "audit" / f"recoupement-{time.strftime('%Y%m%d-%H%M')}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rapport, "utf-8")
    print(rapport)
    print(f"\nRapport : {dest}", file=sys.stderr)
