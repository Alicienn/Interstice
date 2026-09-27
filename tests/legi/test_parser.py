from pathlib import Path

from interstice.legi.html import html_vers_texte
from interstice.legi.parser import Article, Inconnu, Section, TexteStruct, TexteVersion, parse

FIX = Path(__file__).parents[1] / "fixtures" / "legi"


def load(name: str):
    return parse((FIX / name).read_bytes())


def test_texte_version_code():
    t = load("texte_version_code.xml")
    assert isinstance(t, TexteVersion)
    assert t.id == t.cid == "LEGITEXT000005634379"
    assert t.nature == "CODE"
    assert t.titrefull == "Code de commerce"
    assert t.etat == "VIGUEUR"
    assert t.versions_a_venir[:2] == ["2026-10-01", "2027-01-01"]
    assert t.nota_html is None


def test_texte_version_tnc_cid_jorf():
    t = load("texte_version_tnc.xml")
    assert t.id == "LEGITEXT000005757180"
    assert t.cid == "JORFTEXT000000244542"
    assert t.titre.startswith("Loi n° 2003-1365")
    assert "Jacques Chirac" in t.signataires_html


def test_texte_struct():
    s = load("texte_struct_code.xml")
    assert isinstance(s, TexteStruct)
    assert [e.titre for e in s.enfants][:2] == ["Partie législative", "Partie réglementaire"]
    assert all(e.kind == "section" for e in s.enfants)
    assert s.enfants[0].debut == "2000-09-21" and s.enfants[0].niv == 1
    assert s.versions == [{"id": "LEGITEXT000005634379", "etat": "VIGUEUR", "debut": "2000-09-21",
                           "fin": "2999-01-01", "num": None}]


def test_section_enfants_versionnes():
    s = load("section_profonde.xml")
    assert isinstance(s, Section)
    assert s.contexte.texte_cid == "LEGITEXT000005634379"
    assert [n[0].titre for n in s.contexte.niveaux] == ["Partie législative"]
    titre3 = [e for e in s.enfants if e.cid == "LEGISCTA000006133173"]
    # même section logique (cid), deux versions (id) avec des périodes distinctes
    assert {e.id for e in titre3} == {"LEGISCTA000006133173", "LEGISCTA000019292498"}
    assert sorted((e.debut, e.fin) for e in titre3) == [("2000-09-21", "2008-08-06"), ("2008-08-06", "2999-01-01")]


def test_section_avec_articles():
    s = load("section_articles.xml")
    arts = [e for e in s.enfants if e.kind == "article"]
    assert arts and all(a.id.startswith("LEGIARTI") and a.titre for a in arts)
    assert [e.position for e in s.enfants] == list(range(len(s.enfants)))


def test_article():
    a = load("article_modifie.xml")
    assert isinstance(a, Article)
    assert (a.id, a.num, a.etat) == ("LEGIARTI000032944414", "R123-1", "MODIFIE")
    assert (a.date_debut, a.date_fin) == ("2017-01-01", "2020-01-01")
    assert a.contexte.texte_cid == "LEGITEXT000005634379"
    assert a.contexte.texte_titre == "Code de commerce"
    # niveau « Section préliminaire » : deux intitulés datés
    assert len(a.contexte.niveaux) == 6
    assert len(a.contexte.niveaux[4]) == 2
    assert [v["id"] for v in a.versions][-1] == "LEGIARTI000043292222"
    assert len(a.versions) == 6
    assert a.html.startswith("<p>I.-Les centres de formalités")
    cit = [l for l in a.liens if l.sens == "source" and l.typelien == "CITATION"]
    assert any(l.num == "L711-3" for l in cit)


def test_racine_inconnue():
    assert isinstance(parse(b"<AUTRE/>"), Inconnu)


def test_html_vers_texte():
    html = "<p>I.-Premier   alinéa.</p><p>1° Point ;<br/>suite</p><table><tr><td>a</td><td>b</td></tr></table>"
    assert html_vers_texte(html) == "I.-Premier alinéa.\n\n1° Point ;\nsuite\n\na | b"
    assert html_vers_texte(None) == ""
