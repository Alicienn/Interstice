import sqlite3

import pytest

from interstice.bofip.renvois import Resolveurs, extraire_renvois, normaliser_citations


@pytest.fixture(scope="module")
def res():
    return Resolveurs(None)


def _cites(texte, res):
    return [(r["code"], r["num"]) for r in extraire_renvois(texte, res)]


@pytest.mark.parametrize("phrase, attendu", [
    # formes relevées dans le stock BOFiP de septembre 2026
    ("prévu à l’article 150-0 B ter du code général des impôts (CGI).", [("CGI", "150-0 B ter")]),
    ("codifié à l’article 150-0 B ter du CGI, s’applique", [("CGI", "150-0 B ter")]),
    ("(CGI, art. 238 bis)", [("CGI", "238 bis")]),
    ("(CGI, ann. III, art. 46 quater-0 ZZ bis)", [("CGI-AIII", "46 quater-0 ZZ bis")]),
    ("l'article 39 de l'annexe II au CGI", [("CGI-AII", "39")]),
    ("l’article L. 80 A du livre des procédures fiscales (LPF)", [("LPF", "L. 80 A")]),
    ("en application de l'article L. 64 du LPF", [("LPF", "L. 64")]),
    ("(CIBS, art. L. 162-1 à CIBS, art. L. 162-9)", [("CIBS", "L. 162-1"), ("CIBS", "L. 162-9")]),
    ("(C. com., art. L. 233-3)", [("code de commerce", "L. 233-3")]),
    ("l'article L. 211-1 du CoMoFi", [("code monétaire et financier", "L. 211-1")]),
    ("l’article 18 de la loi n° 2012-1510 du 29 décembre 2012", [("loi n° 2012-1510", "18")]),
    ("les articles 150-0 A et 150-0 D du CGI", [("CGI", "150-0 A"), ("CGI", "150-0 D")]),
    ("l'article 287 et le 3° de l'article 256", [(None, "287"), (None, "256")]),
    ("l’article 1er du CGI", [("CGI", "1")]),
    ("au sens de l'article 39 du même code", [(None, "39")]),
])
def test_formes_de_citation(phrase, attendu, res):
    assert _cites(phrase, res) == attendu


def test_normalisation():
    assert normaliser_citations("(CGI, art. 238 bis)") == "(article 238 bis du code général des impôts)"
    assert "de l'annexe III au code général des impôts" in normaliser_citations("CGI, ann. III, art. 46")


def test_resolution_legi():
    """Avec une base LEGI, le numéro est résolu par plus long préfixe et le LEGITEXT renseigné."""
    legi = sqlite3.connect(":memory:")
    legi.executescript("""
        CREATE TABLE textes (id TEXT, cid TEXT, nature TEXT, titre TEXT);
        CREATE TABLE articles (id TEXT, texte_cid TEXT, texte_nature TEXT, num TEXT, num_norm TEXT);
        INSERT INTO textes VALUES ('LEGITEXT000006069577', 'LEGITEXT000006069577', 'CODE', 'Code général des impôts');
        INSERT INTO articles VALUES ('LEGIARTI1', 'LEGITEXT000006069577', 'CODE', '150-0 B ter', '150-0BTER');
    """)
    res = Resolveurs(legi)
    r = extraire_renvois("l'article 150-0 B ter du CGI", res)[0]
    assert (r["code"], r["texte_cid"], r["num"], r["resolu"]) == ("CGI", "LEGITEXT000006069577", "150-0 B ter", 1)
    r = extraire_renvois("l'article 150-0 Z du CGI", res)[0]
    assert r["resolu"] == 0 and r["num"] == "150-0 Z"


def test_table_renvois(base_bofip):
    c = base_bofip
    rows = c.execute("""SELECT count(*) FROM bofip_renvois WHERE pgp = '12038-PGP'
                        AND code = 'CGI' AND num_norm = '150-0BTER'""").fetchone()[0]
    assert rows >= 20
    # le rescrit RES-RPPM-000114 et l'actualité ACTU-2026-00099 commentent aussi l'article
    pgps = {r[0] for r in c.execute("SELECT DISTINCT pgp FROM bofip_renvois WHERE code = 'CGI' AND num_norm = '150-0BTER'")}
    assert {"12038-PGP", "13644-PGP"} <= pgps
    assert c.execute("SELECT pgp FROM bofip_documents WHERE boi = 'ACTU-2026-00099'").fetchone()[0] in pgps
