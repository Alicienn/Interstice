import io
import json
import tarfile
from pathlib import Path

from interstice.legi.ingest import ingerer_chaine
from interstice.store.db import connect, init_schema

FIX = Path(__file__).parents[1] / "fixtures" / "legi"
CODE = "20250713-140000/legi/global/code_et_TNC_en_vigueur/code_en_vigueur/LEGI/TEXT/00/00/05/63/43/LEGITEXT000005634379"


def _tar(path: Path, membres: dict[str, bytes | tuple[bytes, int]]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for nom, data in membres.items():
            data, mtime = data if isinstance(data, tuple) else (data, 0)
            info = tarfile.TarInfo(nom)
            info.size = len(data)
            info.mtime = mtime
            tar.addfile(info, io.BytesIO(data))
        d = tarfile.TarInfo("20250713-140000/legi")
        d.type = tarfile.DIRTYPE
        tar.addfile(d)
    return path


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def test_chaine_global_puis_increment(tmp_path):
    art = _fx("article_modifie.xml")
    glob = _tar(tmp_path / "Freemium_legi_global_20250713-140000.tar.gz", {
        f"{CODE}/texte/version/LEGITEXT000005634379.xml": _fx("texte_version_code.xml"),
        f"{CODE}/texte/struct/LEGITEXT000005634379.xml": _fx("texte_struct_code.xml"),
        f"{CODE}/section_ta/LEGI/SCTA/LEGISCTA000006083281.xml": _fx("section_racine.xml"),
        f"{CODE}/article/LEGI/ARTI/LEGIARTI000032944414.xml": art,
        # doublon : même article sous un autre chemin
        "20250713-140000/legi/global/code_et_TNC_non_vigueur/x/LEGIARTI000032944414.xml": art,
        "20250713-140000/legi/global/eli/loi/2003/12/31/X/jo/article_1/versions.xml":
            b'<VERSIONS><VERSION debut="2999-01-01" etat="" fin="2999-01-01" id="JORFARTI000001146598"/></VERSIONS>',
        "20250713-140000/legi/global/bizarre.xml": b"<AUTRE/>",
        "20250713-140000/legi/global/casse.xml": b"<ARTICLE><oups>",
        "20250713-140000/LISEZMOI.txt": b"hello",
    })
    # incrément : l'article change d'état, la section racine est supprimée
    art2 = art.replace(b"<ETAT>MODIFIE</ETAT>", b"<ETAT>VIGUEUR</ETAT>")
    inc = _tar(tmp_path / "LEGI_20250714-210000.tar.gz", {
        f"20250714-210000/{CODE.split('/', 1)[1]}/article/LEGI/ARTI/LEGIARTI000032944414.xml": art2,
        "20250714-210000/liste_suppression_legi.dat":
            f"legi/global/{CODE.split('/legi/global/', 1)[1]}/section_ta/LEGI/SCTA/LEGISCTA000006083281\n".encode(),
    })

    conn = connect(tmp_path / "t.sqlite")
    init_schema(conn)
    faits = ingerer_chaine(conn, [glob, inc], {}, processus=2)
    assert len(faits) == 2
    g = faits[0]
    assert g["xml"] == 8 and g["erreurs"] == 1 and g["inconnus"] == 1
    assert g["autres_fichiers"] == ["20250713-140000/LISEZMOI.txt"]
    assert g["par_type"] == {"texte": 1, "struct": 1, "section": 1, "article": 2, "eli": 1,
                             "inconnu": 1, "erreur": 1}
    assert conn.execute("SELECT count(*) FROM doublons WHERE identiques = 1").fetchone()[0] == 1

    etat, archive = conn.execute("SELECT etat, archive FROM articles").fetchone()
    assert (etat, archive) == ("VIGUEUR", "LEGI_20250714-210000.tar.gz")
    assert conn.execute("SELECT count(*) FROM sections").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM sommaire WHERE parent_id='LEGISCTA000006083281'").fetchone()[0] == 0
    assert conn.execute("SELECT trouve FROM suppressions").fetchone()[0] == 1
    # liens remplacés, pas dupliqués
    n_liens = conn.execute("SELECT count(*) FROM liens").fetchone()[0]
    assert n_liens == art.count(b"<LIEN ")
    # clé d'article logique = plus petit id de la chaîne des versions
    assert conn.execute("SELECT cle FROM articles").fetchone()[0] == "LEGIARTI000006255835"
    # idempotence
    assert ingerer_chaine(conn, [glob, inc], {}, processus=2) == []
    row = conn.execute("SELECT num, num_norm, texte FROM articles").fetchone()
    assert row["num_norm"] == "R123-1" and row["texte"].startswith("I.-Les centres")
    assert json.loads(conn.execute("SELECT versions FROM eli").fetchone()[0])[0]["id"] == "JORFARTI000001146598"


def test_doublon_la_copie_la_plus_recente_gagne(tmp_path):
    art = _fx("article_modifie.xml")
    perimee = art.replace(b"<ETAT>MODIFIE</ETAT>", b"<ETAT>ABROGE_DIFF</ETAT>")
    fraiche = art.replace(b"<ETAT>MODIFIE</ETAT>", b"<ETAT>ABROGE</ETAT>")
    base = "20250713-140000/legi/global"
    glob = _tar(tmp_path / "Freemium_legi_global_20250713-140000.tar.gz", {
        # la copie récente arrive d'abord, la périmée ensuite : l'ordre ne doit pas compter
        f"{base}/code_et_TNC_non_vigueur/a/LEGIARTI000032944414.xml": (fraiche, 2000),
        f"{base}/code_et_TNC_en_vigueur/a/LEGIARTI000032944414.xml": (perimee, 1000),
        f"{base}/eli/jo/2013/10/17/versions.xml": (b'<?xml version="1.0"?>\n<ID>JORFCONT000028076811</ID>', 5),
        f"{base}/eli/decision/2024/x/versions.xml": (b"", 5),
    })
    conn = connect(tmp_path / "t.sqlite")
    init_schema(conn)
    (s,) = ingerer_chaine(conn, [glob], {}, processus=1)
    assert conn.execute("SELECT etat FROM articles").fetchone()[0] == "ABROGE"
    d = conn.execute("SELECT chemin_retenu, mtime_retenu, mtime_ecarte FROM doublons").fetchone()
    assert "non_vigueur" in d[0] and (d[1], d[2]) == (2000, 1000)
    assert s["par_type"] == {"article": 2, "eli": 1, "vide": 1} and s["erreurs"] == 0 and s["inconnus"] == 0
    assert json.loads(conn.execute("SELECT versions FROM eli").fetchone()[0])[0]["id"] == "JORFCONT000028076811"
