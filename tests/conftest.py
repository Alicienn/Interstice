import io
import tarfile
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "legi"
CODE = "legi/global/code_et_TNC_en_vigueur/code_en_vigueur/LEGI/TEXT/00/00/05/63/43/LEGITEXT000005634379"


def fabriquer_tar(path: Path, membres: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for nom, data in membres.items():
            info = tarfile.TarInfo(nom)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


@pytest.fixture(scope="session")
def base_mini(tmp_path_factory):
    """Mini-base : Code de commerce (texte, sommaire racine, une section, un article), indexée."""
    from interstice.graph.construire import construire_renvois
    from interstice.legi.ingest import ingerer_chaine
    from interstice.store.db import connect, init_schema
    from interstice.store.fts import reconstruire_fts

    d = tmp_path_factory.mktemp("base")
    art = (FIX / "article_modifie.xml").read_bytes()
    # la section racine référence un sous-livre ; on y rattache l'article pour tester la descente
    section = (FIX / "section_racine.xml").read_bytes().replace(
        b"</STRUCTURE_TA>",
        b'<LIEN_ART debut="2017-01-01" etat="MODIFIE" fin="2020-01-01" id="LEGIARTI000032944414" num="R123-1" origine="LEGI"/></STRUCTURE_TA>')
    glob = fabriquer_tar(d / "Freemium_legi_global_20250713-140000.tar.gz", {
        f"20250713-140000/{CODE}/texte/version/LEGITEXT000005634379.xml": (FIX / "texte_version_code.xml").read_bytes(),
        f"20250713-140000/{CODE}/texte/struct/LEGITEXT000005634379.xml": (FIX / "texte_struct_code.xml").read_bytes(),
        f"20250713-140000/{CODE}/section_ta/LEGISCTA000006083281.xml": section,
        f"20250713-140000/{CODE}/article/LEGIARTI000032944414.xml": art,
    })
    conn = connect(d / "corpus.sqlite")
    init_schema(conn)
    ingerer_chaine(conn, [glob], {}, processus=1)
    construire_renvois(conn, processus=1)
    reconstruire_fts(conn)
    return conn
