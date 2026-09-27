import json

from interstice.bofip.audit import auditer_bofip, documents_tar, lister_tar


def test_listing_independant(archives):
    noms, outil = lister_tar(archives["stock"])
    docs = documents_tar(noms)
    assert {k: len(v) for k, v in docs.items()} == {"Contenu": 8, "Image": 1, "Attachment": 1, "PlanClassement": 1}


def test_audit_ok(base_bofip, archives):
    from interstice.bofip.ingest import ingerer_chaine
    from outillage_bofip import FIX

    ingerer_chaine(base_bofip, [archives["flux"]], verbeux=False)
    actus = json.loads((FIX / "actualites.json").read_text("utf-8"))
    index = [{k: v for k, v in r.items() if not k.startswith("contenu")} for r in actus] + [
        {"type": "Contenu", "titre": "…", "debut_de_validite": "2026-08-10", "serie": "RPPM",
         "identifiant_juridique": "BOI-RPPM-PVBMI-30-10-60-10",
         "permalien": "https://bofip.impots.gouv.fr/bofip/12038-PGP.html/identifiant=BOI-RPPM-PVBMI-30-10-60-10-20260810"}]
    rapport, ok = auditer_bofip(base_bofip, archives["stock"].parent, index)
    assert ok, rapport
    assert "| 8 / 8 |" in rapport and "Erreurs de lecture : **0**" in rapport
    assert "en base : **8** ; manquants : 0 ; en trop : 0 ✅" in rapport
    assert "rattachés par préfixe de code : **1**" in rapport and "BOI-BA-RICI-20-60" in rapport
    assert "remplacée 1" in rapport
    assert "1 où la base a une version plus récente" in rapport  # 12038 republié par le flux


def test_audit_detecte_un_ecart(base_bofip, archives):
    base_bofip.execute("DELETE FROM bofip_documents WHERE pgp = '4310-PGP'")
    rapport, ok = auditer_bofip(base_bofip, archives["stock"].parent, None)
    assert not ok
    assert "manquant `4310-PGP`" in rapport and "nœuds sans document courant : **1** ❌" in rapport
