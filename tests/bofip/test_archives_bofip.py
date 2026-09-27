import hashlib
import json

import httpx
import pytest

from interstice.bofip import archives as A

STOCK = b"contenu du stock"
FLUX = b"contenu du flux"


def _serveur(md5_stock: str | None = None):
    appels: list[str] = []
    recs = [
        {"nom_du_fichier": "bofip_flux_live_20260917_20260923.tgz", "type": "flux",
         "telechargement": "https://bofip.test/opendata/flux/39", "empreinte": "https://bofip.test/opendata/empreinte/flux/39",
         "contenu": "6 nouvelles publications"},
        {"nom_du_fichier": "bofip_stock_live_20260923.tgz", "type": "stock",
         "telechargement": "https://bofip.test/opendata/stock/9", "empreinte": "https://bofip.test/opendata/empreinte/stock/9",
         "contenu": "Contenu doctrinal en vigueur au 23/09/2026."},
        {"nom_du_fichier": "bofip_flux_live_20260910_20260916.tgz", "type": "flux",
         "telechargement": "https://bofip.test/opendata/flux/38", "empreinte": "https://bofip.test/opendata/empreinte/flux/38"},
    ]
    fichiers = {"/opendata/flux/39": FLUX, "/opendata/stock/9": STOCK, "/opendata/flux/38": FLUX + b"38"}
    noms = {"/opendata/empreinte/flux/39": ("bofip_flux_live_20260917_20260923.tgz", FLUX),
            "/opendata/empreinte/stock/9": ("bofip_stock_live_20260923.tgz", STOCK),
            "/opendata/empreinte/flux/38": ("bofip_flux_live_20260910_20260916.tgz", FLUX + b"38")}

    def handler(req: httpx.Request) -> httpx.Response:
        appels.append(req.url.path)
        if req.url.path.endswith("/bofip-impots/records"):
            return httpx.Response(200, json={"total_count": len(recs), "results": recs})
        if req.url.path in fichiers:
            data = fichiers[req.url.path]
            return httpx.Response(200, content=data, headers={"content-length": str(len(data))})
        if req.url.path in noms:
            nom, data = noms[req.url.path]
            md5 = md5_stock if (md5_stock and "stock" in nom) else hashlib.md5(data).hexdigest()
            return httpx.Response(200, text=f"{md5}  {nom}\n")
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler)), appels


def test_infos_nom():
    assert A.infos_nom("bofip_stock_live_20260923.tgz") == ("stock", None, "2026-09-23")
    assert A.infos_nom("bofip_flux_live_20260917_20260923.tgz") == ("flux", "2026-09-17", "2026-09-23")
    with pytest.raises(ValueError):
        A.infos_nom("autre.tgz")


def test_synchroniser_idempotent(tmp_path):
    client, appels = _serveur()
    chaine = A.synchroniser(tmp_path, client, verbeux=False, vigueur=False)
    # ordre d'application : flux antérieur, stock, puis flux de même date de fin que le stock
    assert [p.name for p in chaine] == ["bofip_flux_live_20260910_20260916.tgz", "bofip_stock_live_20260923.tgz",
                                        "bofip_flux_live_20260917_20260923.tgz"]
    m = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    s = m["bofip_stock_live_20260923.tgz"]
    assert s["md5_verifie"] and s["md5"] == hashlib.md5(STOCK).hexdigest()
    assert s["sha256"] == hashlib.sha256(STOCK).hexdigest() and s["taille"] == len(STOCK)
    assert (tmp_path / "bofip_stock_live_20260923.tgz").read_bytes() == STOCK
    telechargements = [a for a in appels if "/empreinte/" not in a and "records" not in a]
    assert len(telechargements) == 3
    appels.clear()
    A.synchroniser(tmp_path, client, verbeux=False, vigueur=False)
    assert all("records" in a for a in appels)  # seul le listing est relu : rien n'est retéléchargé


def test_md5_invalide(tmp_path):
    client, _ = _serveur(md5_stock="0" * 32)
    with pytest.raises(IOError, match="MD5"):
        A.synchroniser(tmp_path, client, verbeux=False, vigueur=False)
    assert not (tmp_path / "bofip_stock_live_20260923.tgz").exists()
    m = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    assert "bofip_stock_live_20260923.tgz" not in m and "bofip_flux_live_20260910_20260916.tgz" in m
