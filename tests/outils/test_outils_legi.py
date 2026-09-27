import pytest

from interstice.outils import OUTILS, get_outil
from interstice.outils import vues

ART = "LEGIARTI000032944414"
CODE = "LEGITEXT000005634379"


def appel(conn, nom, **args):
    res = get_outil(nom).appeler(conn, args)
    assert not res.erreur, res.texte
    return res


def test_registre_schemas_valides():
    noms = {o.nom for o in OUTILS}
    assert {"lister_textes", "sommaire", "lire_article", "historique_article", "comparer_versions",
            "renvois", "rechercher", "modifications"} <= noms
    for o in OUTILS:
        s = o.schema_openai()
        assert s["function"]["parameters"]["type"] == "object"
        assert set(s["function"]["parameters"]["required"]) <= set(s["function"]["parameters"]["properties"])


def test_lister_textes_filtre(base_mini):
    res = appel(base_mini, "lister_textes", filtre="commerce")
    assert CODE in res.texte and res.documents[0].kind == "texte"


def test_sommaire_texte_puis_section(base_mini):
    res = appel(base_mini, "sommaire", texte="Code de commerce", date="2018-06-01")
    assert "Partie législative" in res.texte and "LEGISCTA000006083281" in res.texte
    assert "(1 art.)" in res.texte  # l'article rattaché est compté récursivement
    res2 = appel(base_mini, "sommaire", section_id="LEGISCTA000006083281", date="2018-06-01")
    assert "art. **R123-1**" in res2.texte and ART in res2.texte


def test_sommaire_filtre_par_date(base_mini):
    res = appel(base_mini, "sommaire", section_id="LEGISCTA000006083281", date="2021-01-01")
    assert ART not in res.texte  # la version 2017-2020 n'est plus en vigueur


def test_lire_article_par_numero_et_date(base_mini):
    res = appel(base_mini, "lire_article", texte="Code de commerce", num="R. 123-1", date="2018-01-01")
    assert "I.-Les centres de formalités" in res.texte
    assert "2017-01-01" in res.texte and "Partie réglementaire" in res.texte
    assert res.documents[0].id == ART and res.documents[0].kind == "article"


def test_lire_article_hors_vigueur_averti(base_mini):
    res = appel(base_mini, "lire_article", texte="Code de commerce", num="R123-1", date="2024-01-01")
    assert "Aucune version en vigueur" in res.texte


def test_article_introuvable_est_une_erreur_propre(base_mini):
    res = get_outil("lire_article").appeler(base_mini, {"texte": "Code de commerce", "num": "Z999"})
    assert res.erreur and "introuvable" in res.texte


def test_rechercher(base_mini):
    res = appel(base_mini, "rechercher", requete="formalités entreprises", textes="tout", date="2018-01-01")
    assert ART in res.texte and "«" in res.texte


def test_renvois_sortants(base_mini):
    res = appel(base_mini, "renvois", id=ART, sens="sortants")
    # renvois textuels (R. 123-30, R. 123-83, L. 711-3) — non résolus dans la mini-base — et lien LEGI vers la loi
    assert "R. 123-30" in res.texte or "R123-30" in res.texte
    assert "94-126" in res.texte


def test_historique(base_mini):
    res = appel(base_mini, "historique_article", id=ART)
    assert ART in res.texte and "MODIFIE" in res.texte


def test_vues(base_mini):
    v = vues.vue_article(base_mini, ART, "2018-01-01")
    assert v["num"] == "R123-1" and v["chemin"][0]["kind"] == "texte"
    assert v["url_legifrance"].endswith(ART)
    assert v["html"].startswith("<p>I.-Les centres")
    n = vues.vue_texte(base_mini, CODE, "2018-01-01")
    assert n["enfants"][0]["titre"] == "Partie législative" and n["enfants"][0]["nb_articles"] == 1
    s = vues.vue_section(base_mini, "LEGISCTA000006083281", "2018-01-01")
    assert any(e["kind"] == "article" and e["id"] == ART for e in s["enfants"])
    assert vues.recherche(base_mini, "formalités", texte="tout", date="2018-01-01")[0]["id"] == ART
    with pytest.raises(LookupError):
        vues.vue_article(base_mini, "LEGIARTI000000000000")
