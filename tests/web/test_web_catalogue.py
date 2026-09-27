"""Catalogue models.dev : reconnaissance du fournisseur, réflexion, fusion avec la liste de l'API."""

import asyncio

from fastapi.testclient import TestClient

from interstice.web.app import create_app
from interstice.web.llm.base import ErreurFournisseur
from interstice.web.llm.catalogue import fusionner, reflexion_catalogue, trouver_fournisseur

CAT = {
    "openai": {"id": "openai", "models": {
        "gpt-5": {"id": "gpt-5", "name": "GPT-5", "reasoning": True,
                  "reasoning_options": [{"type": "effort", "values": ["minimal", "low", "medium", "high"]}],
                  "limit": {"context": 400000, "output": 128000}},
        "gpt-4o": {"id": "gpt-4o", "name": "GPT-4o", "reasoning": False, "limit": {"context": 128000, "output": 16384}},
        "o3-pro": {"id": "o3-pro", "name": "o3 Pro", "reasoning": True,
                   "reasoning_options": [{"type": "effort", "values": ["none", "low", "high"]}],
                   "limit": {"context": 200000, "output": 100000}},
    }},
    "deepseek": {"id": "deepseek", "api": "https://api.deepseek.com", "models": {
        "deepseek-chat": {"id": "deepseek-chat", "name": "DeepSeek Chat", "reasoning": True,
                          "reasoning_options": [{"type": "toggle"}], "limit": {"context": 128000}}}},
    "passerelle-a": {"api": "https://gw.test/a/v1", "models": {"x": {"id": "x"}}},
    "passerelle-b": {"api": "https://gw.test/b/v1", "models": {"y": {"id": "y"}}},
}


def test_trouver_fournisseur():
    assert trouver_fournisseur(CAT, "https://api.openai.com/v1")[0] == "openai"
    assert trouver_fournisseur(CAT, "https://api.deepseek.com/v1")[0] == "deepseek"
    assert trouver_fournisseur(CAT, "https://gw.test/b/v1")[0] == "passerelle-b"  # hôte partagé : préfixe
    assert trouver_fournisseur(CAT, "http://localhost:11434/v1") is None
    local = {**CAT, "local-x": {"api": "http://localhost:8080/v1", "models": {"z": {"id": "z"}}}}
    assert trouver_fournisseur(local, "http://localhost:8080/v1") is None   # jamais pour un serveur local
    assert trouver_fournisseur(local, "http://192.168.1.20:1234/v1") is None


def test_reflexion_catalogue():
    assert reflexion_catalogue(CAT["openai"]["models"]["gpt-5"])["levels"] == ["minimal", "low", "medium", "high"]
    assert reflexion_catalogue(CAT["openai"]["models"]["o3-pro"])["levels"] == ["low", "high"]  # « none » retiré
    toggle = reflexion_catalogue(CAT["deepseek"]["models"]["deepseek-chat"])
    assert toggle == {"supported": True, "levels": [], "source": "catalogue"}
    assert reflexion_catalogue(CAT["openai"]["models"]["gpt-4o"])["supported"] is False


def test_fusion_reunit_api_et_catalogue():
    api = [{"id": "gpt-5", "owned_by": "openai", "label": None, "context_length": None, "max_output": None,
            "thinking": {"supported": True, "levels": ["low", "medium", "high"], "source": "heuristique"}},
           {"id": "ft:gpt-4o:perso", "owned_by": "moi", "label": None, "context_length": None, "max_output": None,
            "thinking": {"supported": False, "levels": [], "source": "heuristique"}}]
    res = {m["id"]: m for m in fusionner(api, trouver_fournisseur(CAT, "https://api.openai.com/v1"))}
    assert set(res) == {"gpt-5", "ft:gpt-4o:perso", "gpt-4o", "o3-pro"}
    assert res["gpt-5"]["origine"] == "api+catalogue" and res["gpt-5"]["label"] == "GPT-5"
    assert res["gpt-5"]["context_length"] == 400000 and res["gpt-5"]["max_output"] == 128000
    assert res["gpt-5"]["thinking"]["source"] == "catalogue"
    assert res["ft:gpt-4o:perso"]["origine"] == "api"          # modèle privé : conservé tel quel
    assert res["o3-pro"]["origine"] == "catalogue"             # absent de la liste de l'API


class _Adaptateur:
    def __init__(self, erreur=None):
        self.erreur = erreur

    async def lister_modeles(self):
        if self.erreur:
            raise self.erreur
        return [{"id": "gpt-5", "owned_by": "openai", "label": None, "context_length": None, "max_output": None,
                 "thinking": {"supported": False, "levels": [], "source": "heuristique"}}]


def _client(stockage, corpus, tmp_path, adaptateur):
    async def cat():
        return CAT
    return TestClient(create_app(stockage=stockage, outils=[], fabrique_adaptateur=lambda f: adaptateur,
                                 chemin_corpus=corpus, dist=tmp_path / "x", catalogue=cat))


def _fournisseur(c):
    return c.post("/api/providers", json={"name": "OpenAI", "type": "openai",
                                          "base_url": "https://api.openai.com/v1", "api_key": "k"}).json()["id"]


def test_route_fusion(stockage, corpus, tmp_path):
    with _client(stockage, corpus, tmp_path, _Adaptateur()) as c:
        r = c.get(f"/api/providers/{_fournisseur(c)}/remote-models").json()
        assert [m["id"] for m in r] == ["gpt-4o", "gpt-5", "o3-pro"]
        assert all("enabled" in m for m in r)


def test_route_repli_catalogue_si_pas_de_liste(stockage, corpus, tmp_path):
    with _client(stockage, corpus, tmp_path, _Adaptateur(ErreurFournisseur("404", 404))) as c:
        r = c.get(f"/api/providers/{_fournisseur(c)}/remote-models")
        assert r.status_code == 200 and {m["origine"] for m in r.json()} == {"catalogue"}


def test_route_cle_invalide_non_masquee(stockage, corpus, tmp_path):
    with _client(stockage, corpus, tmp_path, _Adaptateur(ErreurFournisseur("clé", 401))) as c:
        assert c.get(f"/api/providers/{_fournisseur(c)}/remote-models").status_code == 502


def test_cache_hors_ligne(tmp_path, monkeypatch):
    import httpx

    from interstice.web.llm import catalogue as mod
    cache = tmp_path / "c.json"
    cache.write_text('{"openai": {"models": {}}}', "utf-8")
    import os
    os.utime(cache, (0, 0))  # périmé

    class Echec:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url): raise httpx.ConnectError("hors ligne")

    monkeypatch.setattr(mod.httpx, "AsyncClient", Echec)
    assert asyncio.run(mod.charger_catalogue(cache)) == {"openai": {"models": {}}}
