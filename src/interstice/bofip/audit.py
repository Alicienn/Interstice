"""Audit d'exhaustivité du corpus BOFiP (rapport markdown).

Questions posées :
1. **Tout a-t-il été lu ?** Pour chaque archive, les répertoires de document comptés par un outil
   indépendant (`tar -tzf`, à défaut le module tarfile) = documents ingérés, par type ; 0 erreur.
2. **L'état courant est-il exact ?** Contenus courants = contenus du dernier stock ∪ flux postérieurs
   (comparaison des ensembles de PGP) ; actualités courantes = dernier instantané.
3. **Tout est-il navigable ?** Chaque nœud du plan publié pointe vers un document courant ; chaque
   document courant a un nœud dans `bofip_plan` ; les documents absents du plan publié sont listés.
4. **Concordance externe** : comparaison au jeu « publications en vigueur » (bofip-vigueur).
"""

from __future__ import annotations

import gzip
import json
import re
import sqlite3
import subprocess
import tarfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

from interstice.bofip.parser import analyser_chemin

_RE_PGP_URL = re.compile(r"/(\d+-PGP)\.html(?:/identifiant=([^/?#]+))?")


def lister_tar(path: Path) -> tuple[list[str], str]:
    """Noms des membres d'une archive, par `tar -tzf` (outil indépendant) ou, à défaut, tarfile."""
    try:
        out = subprocess.run(["tar", "-tzf", str(path)], capture_output=True, check=True, timeout=3600).stdout
        return out.decode("utf-8", "replace").splitlines(), "tar -tzf"
    except (OSError, subprocess.SubprocessError):
        with tarfile.open(path, "r:gz") as t:
            return t.getnames(), "tarfile"


def documents_tar(noms: list[str]) -> dict[str, set[str]]:
    """Type de document → ensemble des PGP (un répertoire de version contenant document.xml)."""
    out: dict[str, set[str]] = defaultdict(set)
    for n in noms:
        a = analyser_chemin(n.rstrip("/"))
        if a and a[1] == "document.xml":
            out[a[0].type_document].add(a[0].pgp)
    return out


def _charger_json(path: Path) -> list[dict]:
    ouvrir = gzip.open if path.name.endswith(".gz") else open
    with ouvrir(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def auditer_bofip(conn: sqlite3.Connection, dossier: Path, index_vigueur: Path | list[dict] | None = None) -> tuple[str, bool]:
    L: list[str] = [f"# Audit d'exhaustivité BOFiP — {time.strftime('%Y-%m-%d %H:%M')}", ""]
    ok = True
    ingestions = conn.execute("SELECT * FROM bofip_ingestion ORDER BY date, type != 'stock', archive").fetchall()

    # 1. lecture des archives --------------------------------------------------------------
    L += ["## 1. Lecture des archives", "",
          "| archive | type | membres | Contenu (archive / lus) | Image | Attachment | Plan | nouveaux | remplacés | antérieurs | identiques | corrigés | retirés | erreurs |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    listings: dict[str, dict[str, set[str]]] = {}
    outil = ""
    for r in ingestions:
        lus = json.loads(r["par_type"])
        p = dossier / r["archive"]
        if r["type"] in ("stock", "flux"):
            if p.exists():
                noms, outil = lister_tar(p)
                docs = documents_tar(noms)
                listings[r["archive"]] = docs
                cellules = []
                for t in ("Contenu", "Image", "Attachment", "PlanClassement"):
                    n_ar, n_lu = len(docs.get(t, ())), lus.get(t, 0)
                    cellules.append(f"{n_ar} / {n_lu}" + ("" if n_ar == n_lu else " ❌"))
                    ok &= n_ar == n_lu
                inconnus = set(docs) - {"Contenu", "Image", "Attachment", "PlanClassement"}
                if inconnus:
                    ok = False
                    cellules[-1] += f" (types inconnus : {sorted(inconnus)})"
            else:
                cellules = ["archive absente ❌"] + [str(lus.get(t, 0)) for t in ("Image", "Attachment", "PlanClassement")]
                ok = False
        else:
            if p.exists():
                recs = _charger_json(p)
                n_ar = sum(1 for x in recs if x.get("type") == "Actualité")
                n_lu = lus.get("Actualité", 0)
                cellules = [f"{n_ar} / {n_lu} (actualités)" + ("" if n_ar == n_lu else " ❌"), "", "", ""]
                ok &= n_ar == n_lu
            else:
                cellules = ["archive absente ❌", "", "", ""]
                ok = False
        ok &= r["erreurs"] == 0
        L.append(f"| {r['archive']} | {r['type']} | {r['membres']} | {' | '.join(cellules)} | {r['nouveaux']} | "
                 f"{r['remplaces']} | {r['anterieurs']} | {r['identiques']} | {r['corriges']} | {r['retires']} | {r['erreurs']} |")
    L += ["", f"Comptage indépendant : `{outil or 'n/a'}` (répertoires de version contenant un document.xml)."]
    erreurs = conn.execute("SELECT * FROM bofip_erreurs").fetchall()
    L += [f"Erreurs de lecture : **{len(erreurs)}**."]
    for e in erreurs[:50]:
        L.append(f"- `{e['archive']}` `{e['chemin']}` : {e['message']}")

    # 2. état courant ------------------------------------------------------------------------
    L += ["", "## 2. État courant", ""]
    courant = {r[0]: r for r in conn.execute("SELECT pgp, boi, nature, date_publication, serie, type_contenu, titre "
                                             "FROM bofip_documents")}
    contenus_db = {p for p, r in courant.items() if r["nature"] == "Contenu"}
    actus_db = {p for p, r in courant.items() if r["nature"] == "Actualité"}
    stocks = [r for r in ingestions if r["type"] == "stock"]
    if stocks and stocks[-1]["archive"] in listings:
        s = stocks[-1]
        attendu = set(listings[s["archive"]].get("Contenu", set()))
        for r in ingestions:
            if r["type"] == "flux" and r["date"] >= s["date"] and r["archive"] in listings:
                attendu |= listings[r["archive"]].get("Contenu", set())
        manquants, en_trop = attendu - contenus_db, contenus_db - attendu
        ok &= not manquants and not en_trop
        L += [f"- Contenus attendus (stock `{s['archive']}` ∪ flux postérieurs, listing indépendant) : **{len(attendu)}** ; "
              f"en base : **{len(contenus_db)}** ; manquants : {len(manquants)} ; en trop : {len(en_trop)}"
              + (" ✅" if not manquants and not en_trop else " ❌")]
        for p in sorted(manquants)[:30]:
            L.append(f"  - manquant `{p}`")
        for p in sorted(en_trop)[:30]:
            L.append(f"  - en trop `{p}` {courant[p]['boi']} ({courant[p]['date_publication']})")
    actu_ing = [r for r in ingestions if r["type"] == "vigueur-actualites"]
    if actu_ing and (dossier / actu_ing[-1]["archive"]).exists():
        recs = _charger_json(dossier / actu_ing[-1]["archive"])
        attendu_a = {m.group(1) for x in recs if x.get("type") == "Actualité"
                     for m in [_RE_PGP_URL.search(x.get("permalien") or "")] if m}
        ecart = attendu_a ^ actus_db
        ok &= not ecart
        L.append(f"- Actualités attendues (instantané `{actu_ing[-1]['archive']}`) : **{len(attendu_a)}** ; en base : "
                 f"**{len(actus_db)}**" + (" ✅" if not ecart else f" ❌ écart {sorted(ecart)[:20]}"))
    par_type = Counter((r["nature"], r["type_contenu"]) for r in courant.values())
    L += ["", "| nature | type | documents |", "|---|---|---|"]
    L += [f"| {n} | {t} | {c} |" for (n, t), c in sorted(par_type.items())]
    series = Counter(r["serie"] for r in courant.values() if r["nature"] == "Contenu")
    L += ["", "Contenus par série : " + ", ".join(f"{s or '—'} {c}" for s, c in series.most_common()),
          f"Rescrits (série RES) : **{series.get('RES', 0)}** ; actualités : **{len(actus_db)}**."]
    versions = conn.execute("SELECT motif, count(*) FROM bofip_versions GROUP BY motif").fetchall()
    L.append("Versions antérieures conservées : " + (", ".join(f"{m} {c}" for m, c in versions) or "0")
             + " (l'open data ne publie que la version en cours : l'historique s'accumule flux après flux).")

    # 3. plan de classement -------------------------------------------------------------------
    L += ["", "## 3. Plan de classement et navigation", ""]
    plan_date = conn.execute("SELECT valeur FROM bofip_meta WHERE cle = 'plan_date'").fetchone()
    noeuds_plan = conn.execute("SELECT noeud, pgp, code, libelle FROM bofip_plan WHERE origine = 'plan'").fetchall()
    casses = [n for n in noeuds_plan if n["pgp"] not in courant]
    ok &= not casses
    L.append(f"- Plan publié du {plan_date[0] if plan_date else '?'} : **{len(noeuds_plan)}** nœuds ; "
             f"nœuds sans document courant : **{len(casses)}**" + (" ✅" if not casses else " ❌"))
    for n in casses[:30]:
        L.append(f"  - `{n['noeud']}` {n['code']} « {n['libelle']} »")
    avec_noeud = {r[0] for r in conn.execute("SELECT pgp FROM bofip_plan WHERE pgp IS NOT NULL")}
    sans_noeud = set(courant) - avec_noeud
    ok &= not sans_noeud
    L.append(f"- Documents courants sans nœud de navigation : **{len(sans_noeud)}**" + (" ✅" if not sans_noeud else " ❌"))
    orph = conn.execute("""SELECT count(*) FROM bofip_plan p WHERE p.parent IS NOT NULL
                           AND NOT EXISTS (SELECT 1 FROM bofip_plan q WHERE q.noeud = p.parent)""").fetchone()[0]
    ok &= orph == 0
    L.append(f"- Nœuds dont le parent n'existe pas : **{orph}**" + (" ✅" if not orph else " ❌"))
    hors = conn.execute("""SELECT d.type_contenu, count(*) FROM bofip_plan p JOIN bofip_documents d ON d.pgp = p.pgp
                           WHERE p.origine = 'rattache' GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    n_hors = sum(c for _, c in hors)
    L.append(f"- Contenus absents du plan publié, rattachés par préfixe de code : **{n_hors}** ("
             + ", ".join(f"{t} {c}" for t, c in hors) + ")")
    vrais_orph = conn.execute("SELECT count(*) FROM bofip_plan WHERE parent = '@HORS-PLAN'").fetchone()[0]
    L.append(f"- Contenus non rattachables (placés sous « Documents hors plan de classement ») : **{vrais_orph}**")
    liste = conn.execute("""SELECT d.boi, d.titre, q.code AS parent_code FROM bofip_plan p
                            JOIN bofip_documents d ON d.pgp = p.pgp LEFT JOIN bofip_plan q ON q.noeud = p.parent
                            WHERE p.origine = 'rattache' ORDER BY d.boi_base""").fetchall()
    L += ["", "<details><summary>Liste des contenus hors plan publié (identifiant → nœud de rattachement)</summary>", ""]
    L += [f"- {r['boi']} → {r['parent_code'] or '(hors plan)'}" for r in liste]
    L += ["", "</details>"]

    # pièces jointes -----------------------------------------------------------------------
    fich = conn.execute("SELECT type, count(*), sum(taille) FROM bofip_fichiers GROUP BY type").fetchall()
    L += ["", "## 4. Pièces jointes (inventaire, contenu non indexé)", ""]
    L += [f"- {t} : {c} fichier(s), {round((s or 0) / 1e6, 1)} Mo" for t, c, s in fich]
    requis = conn.execute("""SELECT count(*) FROM bofip_relations r WHERE r.type = 'requires'
                             AND NOT EXISTS (SELECT 1 FROM bofip_fichiers f WHERE f.pgp = r.cible_pgp)""").fetchone()[0]
    L.append(f"- Relations « requires » d'un contenu vers une pièce absente de l'archive : **{requis}** "
             "(pièces annoncées dans document.xml mais non livrées par la DGFiP ; rien à ingérer)")
    for r in conn.execute("""SELECT r.pgp, d.boi, r.cible_type, r.cible_pgp FROM bofip_relations r
                             LEFT JOIN bofip_documents d ON d.pgp = r.pgp WHERE r.type = 'requires'
                             AND NOT EXISTS (SELECT 1 FROM bofip_fichiers f WHERE f.pgp = r.cible_pgp) LIMIT 30"""):
        L.append(f"  - {r['boi']} (`{r['pgp']}`) → {r['cible_type']} `{r['cible_pgp']}`")
    refs = conn.execute("""SELECT r.cible_type, count(*), count(DISTINCT r.cible_pgp) FROM bofip_relations r
                           WHERE r.type = 'references'
                           AND NOT EXISTS (SELECT 1 FROM bofip_documents d WHERE d.pgp = r.cible_pgp) GROUP BY 1""").fetchall()
    L.append("- Relations « references » vers un document absent de la base : "
             + (", ".join(f"{t} {c} liens vers {n} documents" for t, c, n in refs) or "0")
             + " (documents cités qui ne sont plus en vigueur : ni le stock ni le jeu vigueur ne les contiennent)")

    # renvois ------------------------------------------------------------------------------
    rv = conn.execute("""SELECT count(*) t, sum(code IS NOT NULL) c, sum(resolu) r, count(DISTINCT pgp) d,
                                sum(code IS NOT NULL AND code NOT LIKE '% n° %') k
                         FROM bofip_renvois""").fetchone()
    if rv["t"]:
        L += ["", "## 5. Renvois vers les articles de loi", "",
              f"- {rv['t']} citations dans {rv['d']} documents ; texte visé identifié : {rv['c']} "
              f"({100 * rv['c'] / rv['t']:.1f} %) ; numéro vérifié dans LEGI : {rv['r'] or 0} "
              f"({100 * (rv['r'] or 0) / rv['t']:.1f} % du total, "
              f"{100 * (rv['r'] or 0) / max(rv['k'] or 0, 1):.1f} % des {rv['k'] or 0} citations d'un code ; "
              f"les articles de lois et décrets ne sont pas vérifiés)."]
        top = conn.execute("SELECT code, count(*) FROM bofip_renvois WHERE code IS NOT NULL GROUP BY code ORDER BY 2 DESC LIMIT 10")
        L.append("- Par texte : " + ", ".join(f"{c} {n}" for c, n in top))

    # 6. concordance avec bofip-vigueur -------------------------------------------------------
    if index_vigueur is not None:
        recs = index_vigueur if isinstance(index_vigueur, list) else _charger_json(index_vigueur)
        L += ["", "## 6. Concordance avec le jeu « publications en vigueur » (bofip-vigueur)", ""]
        L += _comparer_vigueur(recs, courant, conn)
    return "\n".join(L) + "\n", bool(ok)


def _comparer_vigueur(recs: list[dict], courant: dict, conn) -> list[str]:
    L = []
    par_type = Counter(r.get("type") for r in recs)
    dates = sorted(r.get("debut_de_validite") or "" for r in recs)
    date_v = dates[-1] if dates else "?"
    L.append(f"- Enregistrements : **{len(recs)}** ({', '.join(f'{t} {c}' for t, c in par_type.items())}), "
             f"publication la plus récente : {date_v}.")
    v: dict[str, dict] = {}
    sans_pgp = 0
    for r in recs:
        m = _RE_PGP_URL.search(r.get("permalien") or "")
        if not m:
            sans_pgp += 1
            continue
        v[m.group(1)] = {**r, "boi_date": re.sub(r"\s+", "", unquote(m.group(2) or "")) or None}
    base = {p: r for p, r in courant.items()}
    for nature, libelle in (("Contenu", "Contenu"), ("Actualité", "Actualité")):
        vp = {p for p, r in v.items() if r.get("type") == libelle}
        bp = {p for p, r in base.items() if r["nature"] == nature}
        seulement_base, seulement_v = bp - vp, vp - bp
        commun = vp & bp
        dates_diff = [p for p in commun if nature == "Contenu" and v[p]["boi_date"] and v[p]["boi_date"] != base[p]["boi"]]
        L.append(f"- **{nature}** : vigueur {len(vp)}, base {len(bp)}, communs {len(commun)} ; "
                 f"seulement en base {len(seulement_base)}, seulement dans vigueur {len(seulement_v)}, "
                 f"version différente {len(dates_diff)}.")
        apres = [p for p in seulement_base if (base[p]["date_publication"] or "") > date_v]
        if seulement_base:
            L.append(f"  - seulement en base dont publiés après le {date_v} (instantané vigueur plus ancien que le stock) : "
                     f"{len(apres)}")
            for p in sorted(seulement_base - set(apres))[:15]:
                L.append(f"    - `{p}` {base[p]['boi']} ({base[p]['date_publication']}) {(base[p]['titre'] or '')[:90]}")
        for p in sorted(seulement_v)[:15]:
            r = v[p]
            dans_versions = conn.execute("SELECT motif FROM bofip_versions WHERE pgp = ? ORDER BY date_publication DESC",
                                         (p,)).fetchone()
            L.append(f"  - seulement dans vigueur : `{p}` {r.get('boi_date') or r.get('identifiant_juridique')} "
                     f"({r.get('debut_de_validite')}) {(r.get('titre') or '')[:80]}"
                     + (f" — en base : version {dans_versions[0]}" if dans_versions else ""))
        if dates_diff:
            plus_recent = sum(1 for p in dates_diff if base[p]["boi"][-8:] > v[p]["boi_date"][-8:])
            meme_date = sum(1 for p in dates_diff if base[p]["boi"][-8:] == v[p]["boi_date"][-8:])
            L.append(f"  - identifiants différents : {plus_recent} où la base a une version plus récente (republiée après "
                     f"l'instantané vigueur) ; {meme_date} de même date mais de numéro différent (annexes, formulaires "
                     f"et lettres types renumérotés : l'archive et le jeu vigueur divergent pour une même version) ; "
                     f"{len(dates_diff) - plus_recent - meme_date} autres")
            for p in sorted(dates_diff)[:10]:
                L.append(f"    - `{p}` base {base[p]['boi']} / vigueur {v[p]['boi_date']}")
    if sans_pgp:
        L.append(f"- Enregistrements vigueur sans PGP dans le permalien : {sans_pgp}")
    return L
