import json

import pytest

from interstice.outils.bofip import (OUTILS_BOFIP, bofip_lire, bofip_plan, bofip_pour_article, bofip_rechercher,
                                     decouper_parties, recherche_bofip, trouver_document, vue_bofip, vue_bofip_noeud)


def test_registre():
    noms = [o.nom for o in OUTILS_BOFIP]
    assert noms == ["bofip_plan", "bofip_lire", "bofip_rechercher", "bofip_pour_article"]
    for o in OUTILS_BOFIP:
        json.dumps(o.schema_openai())


def test_identifiants(base_bofip):
    c = base_bofip
    for ident in ("12038-PGP", "BOI-RPPM-PVBMI-30-10-60-10-20260810", "BOI-RPPM-PVBMI-30-10-60-10",
                  "RPPM-PVBMI-30-10-60-10", " boi-rppm-pvbmi-30-10-60-10 "):
        assert trouver_document(c, ident)[0]["pgp"] == "12038-PGP"
    assert trouver_document(c, "ACTU-2026-00036")[0]["nature"] == "Actualité"
    with pytest.raises(LookupError):
        trouver_document(c, "BOI-XYZ-1")


def test_plan(base_bofip):
    r = bofip_plan(base_bofip)
    assert "`BOI-RPPM` (`7771-PGP`)" in r.texte and "Actualités" in r.texte
    r = bofip_plan(base_bofip, serie="RPPM", profondeur=2)
    assert "BOI-RPPM-PVBMI-30-10-60-10" in r.texte and "Chemin :" in r.texte
    assert r.documents[0].kind == "bofip" and r.documents[0].id == "7771-PGP"
    r = bofip_plan(base_bofip, noeud="BOI-BA-RICI-20")
    assert "BOI-BA-RICI-20-60" in r.texte and "[hors plan publié]" in r.texte
    assert "Actualités 2026" in bofip_plan(base_bofip, serie="ACTU").texte


def test_lire_pagination(base_bofip):
    c = base_bofip
    r = bofip_lire(c, "BOI-RPPM-PVBMI-30-10-60-10")
    assert r.texte.startswith("# BOI-RPPM-PVBMI-30-10-60-10-20260810 (`12038-PGP`)")
    assert "Table des matières" in r.texte and "## Partie 1 /" in r.texte and "`partie=2`" in r.texte
    assert "CGI, art. 150-0 B ter ×" in r.texte
    assert "Plan : RPPM - Revenus et profits du patrimoine mobilier (BOI-RPPM)" in r.texte
    assert r.documents[0].kind == "bofip" and r.documents[0].id == "12038-PGP"
    s = bofip_lire(c, "12038-PGP", section=1)
    assert "## I. Champ d’application" in s.texte and "Table des matières" not in s.texte
    p = bofip_lire(c, "12038-PGP", paragraphe=150)
    assert "(contient le § 150)" in p.texte and "\n§ 150\n" in p.texte
    # courts : lus entièrement
    court = bofip_lire(c, "BOI-BA-RICI-20-60")
    assert "Partie" not in court.texte
    # les « [node:date:NNN-PGP] » sont remplacés par l'identifiant de l'actualité
    assert "[node:date:" not in r.texte and "ACTU-2026-00099 du 2026-08-10" in r.texte


def test_decouper_parties():
    texte = "".join(f"## Titre {i}\n\n§ {i * 10}\n\n" + "x" * 3000 + "\n\n" for i in range(12))
    parts = decouper_parties(texte, 8000)
    assert parts[0][0] == 0 and parts[-1][1] == len(texte)
    assert all(a < b for a, b in parts) and all(parts[i][1] == parts[i + 1][0] for i in range(len(parts) - 1))
    assert all(texte[a:a + 3] == "## " for a, _ in parts)


def test_version_anterieure(base_bofip, archives):
    from interstice.bofip.ingest import ingerer_chaine

    ingerer_chaine(base_bofip, [archives["flux"]], verbeux=False)
    r = bofip_lire(base_bofip, "12038-PGP")
    assert "20261001" in r.texte and "Versions antérieures : BOI-RPPM-PVBMI-30-10-60-10-20260810" in r.texte
    old = bofip_lire(base_bofip, "12038-PGP@2026-08-10")
    assert "VERSION ANTÉRIEURE" in old.texte and "Motif d'archivage : remplacée" in old.texte
    assert old.documents[0].id == "12038-PGP@2026-08-10"
    v = vue_bofip(base_bofip, "12038-PGP")
    assert v["versions"] == [{"id": "12038-PGP@2026-08-10", "boi": "BOI-RPPM-PVBMI-30-10-60-10-20260810",
                              "date": "2026-08-10", "motif": "remplacée"}]


def test_rechercher(base_bofip):
    r = bofip_rechercher(base_bofip, "report d'imposition apport", serie="RPPM")
    assert "12038-PGP" in r.texte and r.documents[0].kind == "recherche"
    assert all(d.kind == "bofip" for d in r.documents[1:])
    r = bofip_rechercher(base_bofip, "moins-values", nature="rescrit")
    assert "BOI-RES-RPPM-000114" in r.texte and "12038-PGP" not in r.texte
    r = bofip_rechercher(base_bofip, "rénovation", nature="actualite")
    assert "ACTU-2026-00036" in r.texte
    assert recherche_bofip(base_bofip, "soulte")[0]["id"] == "12038-PGP"


def test_pour_article(base_bofip):
    r = bofip_pour_article(base_bofip, "CGI", "150-0 B ter")
    lignes = [l for l in r.texte.splitlines() if l.startswith("- **")]
    assert lignes[0].startswith("- **BOI-RPPM-PVBMI-30-10-60-10-20260810**")  # commentaires d'abord
    assert any("BOI-RES-RPPM-000114" in l for l in lignes) and any("ACTU-2026-00099" in l for l in lignes)
    assert "§ 10" in lignes[0]
    assert "150-0 B ter" in r.texte.splitlines()[0]
    assert "aucun document" in bofip_pour_article(base_bofip, "CGI", "1").texte
    # « 150-0 B » n'englobe pas « 150-0 B ter »
    assert "BOI-RES-RPPM-000114" not in bofip_pour_article(base_bofip, "CGI", "150-0 B").texte


def test_vues(base_bofip):
    v = vue_bofip(base_bofip, "BOI-RPPM-PVBMI-30-10-60-10")
    assert v["id"] == "12038-PGP" and v["serie"] == "RPPM" and v["date"] == "2026-08-10"
    assert [c["code"] for c in v["chemin"]] == ["BOI-RPPM", "BOI-RPPM-PVBMI-30-10-60", "BOI-RPPM-PVBMI-30-10-60-10"]
    assert 'data-bofip="15099-PGP"' in v["html"] and "Contenu:" not in v["html"]
    assert "contenteditable" not in v["html"] and "<script" not in v["html"]
    assert any(a["libelle"] == "CGI, art. 150-0 B ter" and a["occurrences"] >= 20 for a in v["articles_cites"])
    assert {r["id"] for r in v["relations"]["sortantes"]} >= {"10233-PGP"}
    n = vue_bofip_noeud(base_bofip)
    assert [e["code"] for e in n["enfants"]][:2] == ["BOI-RPPM", "BOI-BA"]
    n = vue_bofip_noeud(base_bofip, "BOI-RPPM")
    assert n["enfants"][0]["id"] == "10195-PGP" and n["enfants"][0]["nb_documents"] == 1
    with pytest.raises(LookupError):
        vue_bofip(base_bofip, "999999-PGP")


def test_appel_via_outil(base_bofip):
    o = next(o for o in OUTILS_BOFIP if o.nom == "bofip_lire")
    assert o.appeler(base_bofip, {"id": "inexistant"}).erreur
    assert not o.appeler(base_bofip, {"id": "12038-PGP", "partie": 2}).erreur


def test_base_sans_bofip(tmp_path):
    from interstice.store.db import connect

    conn = connect(tmp_path / "vide.sqlite")
    for o in OUTILS_BOFIP:
        args = {"id": "x", "requete": "x", "texte": "CGI", "num": "1"}
        props = o.parametres["properties"]
        r = o.appeler(conn, {k: v for k, v in args.items() if k in props})
        assert r.erreur and "bofip-ingest" in r.texte


def test_requete_fts_invalide(base_bofip):
    o = next(o for o in OUTILS_BOFIP if o.nom == "bofip_rechercher")
    assert o.appeler(base_bofip, {"requete": 'soulte AND ("'}).erreur
