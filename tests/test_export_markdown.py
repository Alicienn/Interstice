from interstice.export.markdown import exporter


def test_export_un_fichier_par_article(base_mini, tmp_path):
    stats = exporter(base_mini, tmp_path, ["Code de commerce"], date="2018-01-01")
    assert stats["articles"] == 1
    (fichier,) = list(tmp_path.rglob("*.md"))
    assert fichier.name == "Code de commerce art. R123-1.md"
    assert "Partie législative" in str(fichier.parent)
    contenu = fichier.read_text("utf-8")
    assert contenu.startswith("---\nid: LEGIARTI000032944414")
    assert "I.-Les centres de formalités" in contenu
