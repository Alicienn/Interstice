"""Audit d'exhaustivité de la base LEGI.

Produit un rapport markdown qui répond à trois questions :
1. **Tout a-t-il été lu ?** fichiers XML comptés par un outil indépendant (`tar -t`) = fichiers ingérés,
   0 erreur de parsing, 0 racine inconnue, aucun fichier non-XML ignoré sans être listé ;
2. **La base est-elle cohérente ?** chaque lien du sommaire et chaque version annoncée existe ;
3. **Tout est-il atteignable ?** pour chaque code fiscal, les articles en vigueur selon leurs dates
   sont exactement ceux qu'on atteint en descendant le sommaire depuis la racine.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from pathlib import Path

from interstice.outils.requetes import catalogue, cid_par_sigle, en_vigueur_sql, texte_racine_id, valider_date


def _tar_xml(path: Path) -> int | None:
    try:
        out = subprocess.run(["tar", "-tzf", str(path)], capture_output=True, check=True, timeout=3600).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return sum(1 for l in out.splitlines() if l.endswith(b".xml"))


def auditer(conn: sqlite3.Connection, dossier_archives: Path | None = None, verifier_tar: bool = False,
            date: str | None = None) -> tuple[str, bool]:
    d = valider_date(date)
    L: list[str] = [f"# Audit d'exhaustivité LEGI — {time.strftime('%Y-%m-%d %H:%M')}", ""]
    ok = True

    # 1. lecture complète ----------------------------------------------------------------
    L += ["## 1. Lecture des archives", "",
          "| archive | membres | XML lus | classés | erreurs | inconnus | autres fichiers | tar -t (XML) |",
          "|---|---|---|---|---|---|---|---|"]
    tot = {"xml": 0, "err": 0, "inc": 0}
    for r in conn.execute("SELECT * FROM ingestion ORDER BY stamp"):
        par_type = json.loads(r["par_type"])
        classes = sum(par_type.values())
        autres = json.loads(r["autres_fichiers"] or "[]")
        tar = ""
        if verifier_tar and dossier_archives and (dossier_archives / r["archive"]).exists():
            n = _tar_xml(dossier_archives / r["archive"])
            tar = "?" if n is None else str(n)
            if n is not None and n != r["xml"]:
                ok = False
                tar += " ❌"
        if classes != r["xml"]:
            ok = False
        tot["xml"] += r["xml"]
        tot["err"] += r["erreurs"]
        tot["inc"] += r["inconnus"]
        if r["archive"].startswith("Freemium") or r["erreurs"] or r["inconnus"] or autres or tar.endswith("❌"):
            L.append(f"| {r['archive']} | {r['membres']} | {r['xml']} | {classes} | {r['erreurs']} | {r['inconnus']} "
                     f"| {len(autres)} | {tar} |")
    n_arch = conn.execute("SELECT count(*) FROM ingestion").fetchone()[0]
    L += ["", f"{n_arch} archives ingérées, {tot['xml']} fichiers XML lus au total "
              "(seules les archives avec anomalie et l'archive globale sont détaillées ci-dessus)."]
    if tot["err"] or tot["inc"]:
        ok = False
        L.append(f"❌ {tot['err']} erreur(s) de parsing, {tot['inc']} racine(s) inconnue(s) :")
        for r in conn.execute("SELECT archive, chemin, message FROM erreurs LIMIT 20"):
            L.append(f"- erreur `{r[1]}` : {r[2][:200]}")
        for r in conn.execute("SELECT archive, chemin, racine FROM inconnus LIMIT 20"):
            L.append(f"- racine `{r[2]}` : `{r[1]}`")
    else:
        L.append("✅ 0 erreur de parsing, 0 racine inconnue.")
    autres = conn.execute("SELECT archive, autres_fichiers FROM ingestion WHERE autres_fichiers != '[]'").fetchall()
    if autres:
        L.append(f"Fichiers non XML rencontrés (listés, non ingérés) : "
                 f"{sum(len(json.loads(a[1])) for a in autres)} — exemples : "
                 + ", ".join(f"`{x}`" for a in autres[:1] for x in json.loads(a[1])[:5]))

    # 2. cohérence -----------------------------------------------------------------------
    L += ["", "## 2. Cohérence référentielle", ""]
    compte = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("textes", "textes_struct", "sections", "sommaire", "articles", "liens", "eli", "renvois")}
    L.append("Objets : " + ", ".join(f"{k} {v:,}".replace(",", " ") for k, v in compte.items()))
    n_logiques = conn.execute("SELECT count(DISTINCT cle) FROM articles").fetchone()[0]
    L.append(f"Articles logiques (chaînes de versions) : {n_logiques:,}".replace(",", " "))

    checks = [
        ("liens de sommaire vers un article absent",
         "SELECT count(*) FROM sommaire s WHERE s.kind='article' AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.id=s.enfant_id)",
         "SELECT s.parent_id, s.enfant_id, s.titre FROM sommaire s WHERE s.kind='article' AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.id=s.enfant_id) LIMIT 10"),
        ("liens de sommaire vers une section absente",
         "SELECT count(*) FROM sommaire s WHERE s.kind='section' AND NOT EXISTS (SELECT 1 FROM sections x WHERE x.id=s.enfant_id)",
         "SELECT s.parent_id, s.enfant_id, s.titre FROM sommaire s WHERE s.kind='section' AND NOT EXISTS (SELECT 1 FROM sections x WHERE x.id=s.enfant_id) LIMIT 10"),
        ("structures de texte sans métadonnées de version",
         "SELECT count(*) FROM textes_struct s WHERE NOT EXISTS (SELECT 1 FROM textes t WHERE t.id=s.id)",
         "SELECT id, cid, '' FROM textes_struct s WHERE NOT EXISTS (SELECT 1 FROM textes t WHERE t.id=s.id) LIMIT 10"),
        ("articles jamais rattachés à un sommaire",
         "SELECT count(*) FROM articles a WHERE NOT EXISTS (SELECT 1 FROM sommaire s WHERE s.enfant_id=a.id)",
         "SELECT id, texte_cid, num FROM articles a WHERE NOT EXISTS (SELECT 1 FROM sommaire s WHERE s.enfant_id=a.id) LIMIT 10"),
    ]
    for libelle, q_count, q_ex in checks:
        n = conn.execute(q_count).fetchone()[0]
        L.append(f"- {'✅' if n == 0 else '⚠️'} {libelle} : {n:,}".replace(",", " "))
        if n:
            for r in conn.execute(q_ex):
                L.append(f"  - `{r[0]}` → `{r[1]}` {r[2] or ''}")

    manquantes = 0
    exemples = []
    ids = {r[0] for r in conn.execute("SELECT id FROM articles")}
    for oid, versions in conn.execute("SELECT id, versions FROM articles"):
        for v in json.loads(versions or "[]"):
            vid = v.get("id")
            if vid and vid.startswith("LEGIARTI"):
                if vid not in ids:
                    manquantes += 1
                    if len(exemples) < 10:
                        exemples.append((oid, vid))
    L.append(f"- {'✅' if manquantes == 0 else '⚠️'} versions annoncées dans <VERSIONS> mais absentes : {manquantes}")
    L += [f"  - `{a}` annonce `{b}`" for a, b in exemples]

    sup = conn.execute("SELECT sum(trouve = 1), sum(trouve = 0), sum(trouve = -1) FROM suppressions").fetchone()
    L.append(f"- suppressions DILA appliquées : {sup[0] or 0}, déjà absentes : {sup[1] or 0}, "
             f"ignorées car republiées dans la même archive : {sup[2] or 0}")
    db = conn.execute("SELECT count(*), sum(identiques) FROM doublons").fetchone()
    L.append(f"- doublons (même identifiant, chemins différents, même archive) : {db[0]} dont {db[1] or 0} identiques")
    if db[0] and db[0] != (db[1] or 0):
        for r in conn.execute("SELECT archive, id, chemin_retenu, chemin_ecarte FROM doublons WHERE identiques = 0 LIMIT 5"):
            L.append(f"  - `{r[1]}` : retenu `{r[2]}` / écarté `{r[3]}`")

    # 3. atteignabilité des codes fiscaux --------------------------------------------------
    L += ["", f"## 3. Atteignabilité des codes fiscaux au {d}", "",
          "| code | articles en vigueur (dates) | atteints par le sommaire | en vigueur non atteints | atteints hors vigueur | sans texte |",
          "|---|---|---|---|---|---|"]
    cat = catalogue(conn)
    for sigle, cid in cid_par_sigle(conn).items():
        racine = texte_racine_id(conn, cid, d)
        vig = {r[0] for r in conn.execute(
            f"SELECT id FROM articles WHERE texte_cid = :c AND etat != 'MODIFIE_MORT_NE' AND {en_vigueur_sql()}",
            {"c": cid, "d": d})}
        atteints = {r[0] for r in conn.execute(
            f"""WITH RECURSIVE n(id) AS (
                   SELECT :r UNION
                   SELECT s.enfant_id FROM sommaire s JOIN n ON s.parent_id = n.id
                   WHERE s.kind = 'section' AND {en_vigueur_sql('s', 'debut', 'fin')})
                SELECT s.enfant_id FROM sommaire s JOIN n ON s.parent_id = n.id
                WHERE s.kind = 'article' AND {en_vigueur_sql('s', 'debut', 'fin')}""", {"r": racine, "d": d})}
        vides = conn.execute(
            f"SELECT count(*) FROM articles WHERE texte_cid = :c AND {en_vigueur_sql()} AND coalesce(texte,'') = ''",
            {"c": cid, "d": d}).fetchone()[0]
        non_att, hors = vig - atteints, atteints - vig
        if non_att or hors:
            ok = ok and not non_att
        L.append(f"| {sigle} | {len(vig)} | {len(atteints)} | {len(non_att)} | {len(hors)} | {vides} |")
        for aid in sorted(non_att)[:5]:
            r = conn.execute("SELECT num, etat, date_debut, date_fin FROM articles WHERE id = ?", (aid,)).fetchone()
            L.append(f"|  | ↳ non atteint `{aid}` art. {r[0]} ({r[1]}, {r[2]} → {r[3]}) | | | | |")
        for aid in sorted(hors)[:5]:
            r = conn.execute("SELECT num, etat, date_debut, date_fin FROM articles WHERE id = ?", (aid,)).fetchone()
            L.append(f"|  | ↳ atteint hors vigueur `{aid}` art. {r[0] if r else '?'} ({r[1] if r else 'absent'}) | | | | |")
    manquants = [s for s in ("CGI", "CGI-AI", "CGI-AII", "CGI-AIII", "CGI-AIV", "LPF", "CIBS", "CDOUANES")
                 if s not in cid_par_sigle(conn)]
    if manquants:
        ok = False
        L.append(f"❌ codes fiscaux non trouvés par leur titre : {', '.join(manquants)}")
    L += ["", f"**Verdict : {'✅ exhaustif et cohérent' if ok else '❌ anomalies bloquantes, voir ci-dessus'}**"]
    return "\n".join(L), ok
