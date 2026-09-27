import json

from outillage_bofip import AJOUT, membres_flux, membres_stock, tar_depuis


def test_parser_document_xml():
    from interstice.bofip.parser import boi_base, lire_document_xml
    from outillage_bofip import DOC_12038

    m = lire_document_xml((DOC_12038 / "document.xml").read_bytes())
    assert m.type_document == "Contenu" and m.pgp == "12038-PGP"
    assert m.boi == "BOI-RPPM-PVBMI-30-10-60-10-20260810"
    assert boi_base(m.boi) == "BOI-RPPM-PVBMI-30-10-60-10"
    assert m.sujets[:2] == ["RPPM", "PVBMI"] and m.date == "2026-08-10"
    assert m.type_contenu == "Commentaire"
    assert ("references", "Contenu", "10233-PGP") in m.relations


def test_texte_intertitres_et_paragraphes():
    from interstice.bofip.parser import corps_html, html_vers_texte_bofip
    from outillage_bofip import DOC_12038

    t = html_vers_texte_bofip(corps_html((DOC_12038 / "data.html").read_text("utf-8")))
    assert "## I. Champ d’application" in t
    assert "### A. Opérations concernées" in t
    assert "\n§ 10\n" in t and "\n§ 150\n" in t


def test_stock(base_bofip):
    c = base_bofip
    n = dict(c.execute("SELECT nature, count(*) FROM bofip_documents GROUP BY nature").fetchall())
    assert n == {"Contenu": 8, "Actualité": 2}
    d = c.execute("SELECT * FROM bofip_documents WHERE pgp = '12038-PGP'").fetchone()
    assert d["boi"] == "BOI-RPPM-PVBMI-30-10-60-10-20260810" and d["serie"] == "RPPM" and d["division"] == "PVBMI"
    assert d["date_publication"] == "2026-08-10" and "150-0 B ter" in d["texte"]
    ing = c.execute("SELECT * FROM bofip_ingestion WHERE type = 'stock'").fetchone()
    assert json.loads(ing["par_type"]) == {"Contenu": 8, "Image": 1, "Attachment": 1, "PlanClassement": 1}
    assert ing["erreurs"] == 0
    f = {r["type"]: r for r in c.execute("SELECT * FROM bofip_fichiers")}
    assert f["Attachment"]["mime"] == "application/pdf" and f["Attachment"]["taille"] > 1000
    assert f["Image"]["fichier"] == "data1.PNG"
    a = c.execute("SELECT * FROM bofip_documents WHERE boi = 'ACTU-2026-00036'").fetchone()
    assert a["nature"] == "Actualité" and a["serie"] == "TVA" and a["division"] == "LIQ"
    assert '""' not in a["html"]


def test_plan_et_rattachement(base_bofip):
    c = base_bofip
    plan = {r["noeud"]: r for r in c.execute("SELECT * FROM bofip_plan")}
    assert plan["12038-PGP"]["parent"] == "10195-PGP" and plan["12038-PGP"]["origine"] == "plan"
    # BOI-BA-RICI-20-60 est absent du plan publié : rattaché à BOI-BA-RICI-20
    assert plan["1574-PGP"]["origine"] == "rattache" and plan["1574-PGP"]["parent"] == "4309-PGP"
    assert plan["1574-PGP"]["profondeur"] == 2
    # actualités : nœud virtuel par année
    actu = c.execute("SELECT pgp FROM bofip_documents WHERE boi = 'ACTU-2026-00099'").fetchone()[0]
    assert plan[actu]["parent"] == "@ACTU-2026" and plan["@ACTU-2026"]["parent"] == "@ACTU"
    # tout document courant a un nœud
    assert c.execute("""SELECT count(*) FROM bofip_documents d
                        WHERE NOT EXISTS (SELECT 1 FROM bofip_plan p WHERE p.pgp = d.pgp)""").fetchone()[0] == 0


def test_flux_remplace_une_version(base_bofip, archives):
    from interstice.bofip.ingest import ingerer_chaine

    c = base_bofip
    stats = ingerer_chaine(c, [archives["stock"], archives["actu"], archives["flux"]], verbeux=False)
    assert [s["archive"] for s in stats] == [archives["flux"].name]  # déjà ingérées : sautées
    assert stats[0]["remplace"] == 1 and stats[0]["erreurs"] == 0
    d = c.execute("SELECT * FROM bofip_documents WHERE pgp = '12038-PGP'").fetchone()
    assert d["boi"] == "BOI-RPPM-PVBMI-30-10-60-10-20261001" and AJOUT in d["texte"]
    v = c.execute("SELECT * FROM bofip_versions WHERE pgp = '12038-PGP'").fetchall()
    assert len(v) == 1 and v[0]["motif"] == "remplacée" and v[0]["boi"].endswith("20260810")
    assert v[0]["archive_motif"] == archives["flux"].name and AJOUT not in v[0]["texte"]
    # l'index plein texte suit la nouvelle version
    hits = c.execute("SELECT d.pgp FROM bofip_fts JOIN bofip_documents d ON d.rowid = bofip_fts.rowid "
                     "WHERE bofip_fts MATCH '\"opération par opération\"'").fetchall()
    assert [h[0] for h in hits] == ["12038-PGP"]
    # réappliquer le même flux ne change rien
    assert ingerer_chaine(c, [archives["flux"]], verbeux=False) == []
    s = ingerer_chaine(c, [archives["flux"]], forcer=True, verbeux=False)[0]
    assert s["identique"] == 1 and s["remplace"] == 0
    assert c.execute("SELECT count(*) FROM bofip_versions").fetchone()[0] == 1


def test_flux_anterieur_et_correction(base_bofip, tmp_path):
    from interstice.bofip.ingest import ingerer_chaine

    c = base_bofip
    ancien = tar_depuis(tmp_path / "bofip_flux_live_20250101_20250107.tgz", membres_flux("2025-01-01", "Ancienne rédaction."))
    s = ingerer_chaine(c, [ancien], verbeux=False)[0]
    assert s["anterieur"] == 1
    assert c.execute("SELECT boi FROM bofip_documents WHERE pgp = '12038-PGP'").fetchone()[0].endswith("20260810")
    assert c.execute("SELECT motif FROM bofip_versions WHERE pgp = '12038-PGP'").fetchone()[0] == "antérieure"
    # même date, HTML différent : correction
    corr = tar_depuis(tmp_path / "bofip_flux_live_20260810_20260812.tgz", membres_flux("2026-08-10", "Erratum."))
    s = ingerer_chaine(c, [corr], verbeux=False)[0]
    assert s["corrige"] == 1
    assert "Erratum." in c.execute("SELECT texte FROM bofip_documents WHERE pgp = '12038-PGP'").fetchone()[0]
    assert {r[0] for r in c.execute("SELECT motif FROM bofip_versions")} == {"antérieure", "corrigée"}


def test_stock_suivant_retire_les_absents(base_bofip, tmp_path):
    from interstice.bofip.ingest import ingerer_chaine

    c = base_bofip
    nouveau = tar_depuis(tmp_path / "bofip_stock_live_20261021.tgz", membres_stock(exclure=("1574-PGP",)))
    s = ingerer_chaine(c, [nouveau], verbeux=False)[0]
    assert s["retire"] == 1 and s["identique"] == 7
    assert c.execute("SELECT count(*) FROM bofip_documents WHERE pgp = '1574-PGP'").fetchone()[0] == 0
    assert c.execute("SELECT motif FROM bofip_versions WHERE pgp = '1574-PGP'").fetchone()[0] == "retirée"
    assert c.execute("SELECT count(*) FROM bofip_plan WHERE pgp = '1574-PGP'").fetchone()[0] == 0


def test_erreur_de_lecture_tracee(base_vide, tmp_path):
    from interstice.bofip.ingest import ingerer_chaine

    m = membres_stock()
    cle = next(k for k in m if k.endswith("1574-PGP/2026-05-06/data.html"))
    del m[cle]
    arch = tar_depuis(tmp_path / "bofip_stock_live_20260923.tgz", m)
    s = ingerer_chaine(base_vide, [arch], verbeux=False)[0]
    assert s["erreurs"] == 1
    e = base_vide.execute("SELECT * FROM bofip_erreurs").fetchone()
    assert "1574-PGP" in e["chemin"] and "absent" in e["message"]


def test_document_illisible_non_retire(base_bofip, tmp_path):
    """Un contenu illisible dans un stock ultérieur garde sa version courante (il n'est pas « retiré »)."""
    from interstice.bofip.ingest import ingerer_chaine

    m = membres_stock()
    cle = next(k for k in m if k.endswith("1574-PGP/2026-05-06/document.xml"))
    m[cle] = b"<document"  # XML tronqué
    s = ingerer_chaine(base_bofip, [tar_depuis(tmp_path / "bofip_stock_live_20261021.tgz", m)], verbeux=False)[0]
    assert s["erreurs"] == 1 and s["retire"] == 0
    assert base_bofip.execute("SELECT count(*) FROM bofip_documents WHERE pgp = '1574-PGP'").fetchone()[0] == 1


def test_archive_corrompue_annulee(base_vide, tmp_path):
    import pytest

    from interstice.bofip.ingest import ingerer_chaine

    arch = tmp_path / "bofip_stock_live_20260923.tgz"
    arch.write_bytes(b"\x1f\x8b pas une archive")
    with pytest.raises(Exception):
        ingerer_chaine(base_vide, [arch], verbeux=False)
    assert not base_vide.in_transaction
    assert base_vide.execute("SELECT count(*) FROM bofip_ingestion").fetchone()[0] == 0
