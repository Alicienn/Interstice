from interstice.graph.citations import extraire
from interstice.legi.numeros import normaliser_num

CGI, LPF, CSS, AIII, LOI = "CGI", "LPF", "CSS", "CGI-AIII", "LOI-2017-1837"
NUMS = {
    CGI: ["150-0 A", "150-0 B", "150-0 B ter", "150-0 D", "150-0 E", "156", "199 undecies A",
          "199 undecies B", "238 bis HE", "39", "39 decies A", "1649 quater-0 B bis", "200 A", "13"],
    LPF: ["L64", "L64 A", "L80 A", "R*196-1"],
    CSS: ["L136-1", "L136-6"],
    AIII: ["46 quater-0 YO"],
    LOI: ["71"],
}
INDEX = {(cid, normaliser_num(n)): n for cid, ns in NUMS.items() for n in ns}


def rnum(cid, cand):
    return INDEX.get((cid, cand))


def rtexte(kind, valeur):
    if kind == "annexe":
        return {"III": AIII}.get(valeur)
    if kind == "loi":
        return {"2017-1837": LOI}.get(valeur)
    v = valeur.lower()
    for titre, cid in [("livre des procédures fiscales", LPF), ("code de la sécurité sociale", CSS),
                       ("code général des impôts", CGI)]:
        if v.startswith(titre):
            return cid
    return None


def ex(texte, source=CGI):
    return [(r.brut, r.num, r.cible_cid, r.plage) for r in extraire(texte, source, rnum, rtexte)]


def test_simple_texte_courant():
    assert ex("dans les conditions prévues à l'article 150-0 B ter.") == [("150-0 B ter", "150-0 B ter", CGI, None)]


def test_plus_long_prefixe():
    # « du » ne fait pas partie du numéro ; « 150-0 B » existe mais « 150-0 B ter » est plus long
    assert ex("l'article 150-0 B ter du présent code")[0][1] == "150-0 B ter"
    assert ex("l'article 156 II")[0][1] == "156"


def test_liste_et_plage():
    r = ex("aux articles 150-0 A à 150-0 E, 199 undecies A et 199 undecies B")
    assert r == [("150-0 A", "150-0 A", CGI, "debut"), ("150-0 E", "150-0 E", CGI, "fin"),
                 ("199 undecies A", "199 undecies A", CGI, None), ("199 undecies B", "199 undecies B", CGI, None)]


def test_autre_code():
    assert ex("mentionné à l'article L. 64 du livre des procédures fiscales") == [("L. 64", "L64", LPF, None)]
    assert ex("prévue à l'article L. 136-6 du code de la sécurité sociale") == [("L. 136-6", "L136-6", CSS, None)]
    assert ex("l'article R* 196-1 du livre des procédures fiscales")[0][1] == "R*196-1"


def test_meme_code():
    r = ex("à l'article L. 136-1 du code de la sécurité sociale et à l'article L. 136-6 du même code")
    assert [x[2] for x in r] == [CSS, CSS] and r[1][1] == "L136-6"


def test_annexe_et_loi():
    assert ex("l'article 46 quater-0 YO de l'annexe III au code général des impôts")[0][1:3] == ("46 quater-0 YO", AIII)
    assert ex("l'article 71 de la loi n° 2017-1837 du 30 décembre 2017")[0][1:3] == ("71", LOI)


def test_suffixes_complexes():
    assert ex("l'article 1649 quater-0 B bis")[0][1] == "1649 quater-0 B bis"
    assert ex("l'article 238 bis HE")[0][1] == "238 bis HE"
    assert ex("l'article 39 decies A")[0][1] == "39 decies A"


def test_non_resolu_conserve():
    r = ex("l'article 9999 ZZ")
    assert r == [("9999 ZZ", None, CGI, None)]


def test_pas_de_faux_positif_sur_mot_capitalise():
    # « Le » ne doit pas être absorbé comme suffixe
    assert ex("l'article 13. Le montant")[0][0] == "13"
