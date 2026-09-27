"""Routes de l'API : fournisseurs, modèles, réglages, conversations, documents, divers."""

from __future__ import annotations

from interstice.web.llm.base import thinking_support

TS = thinking_support(True, ["low", "medium", "high"], "api")


def _creer(client, **kw):
    corps = {"name": "OpenRouter", "type": "openai", "base_url": "https://openrouter.ai/api/v1/",
             "api_key": "sk-secret-123"}
    corps.update(kw)
    r = client.post("/api/providers", json=corps)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_et_tools(client):
    r = client.get("/api/health")
    assert r.json() == {"ok": True, "db": {"articles": 3,
                                           "derniere_ingestion": "2026-09-27T10:00:00"}}
    noms = [t["name"] for t in client.get("/api/tools").json()]
    assert noms == ["sommaire", "lire_article"]


def test_crud_fournisseurs_sans_jamais_renvoyer_la_cle(client, stockage):
    f = _creer(client)
    assert f["api_key_set"] is True
    assert f["base_url"] == "https://openrouter.ai/api/v1"  # barre finale retirée
    assert f["models"] == []
    assert "api_key" not in f and "sk-secret" not in str(f)

    liste = client.get("/api/providers").json()
    assert [p["id"] for p in liste] == [f["id"]]
    assert "sk-secret" not in client.get("/api/providers").text

    # PATCH sans clé : la clé est conservée
    r = client.patch(f"/api/providers/{f['id']}", json={"name": "OR", "api_key": ""})
    assert r.status_code == 200
    assert r.json()["name"] == "OR" and r.json()["api_key_set"] is True
    assert stockage.fournisseur_prive(f["id"])["api_key"] == "sk-secret-123"

    r = client.patch(f"/api/providers/{f['id']}", json={"api_key": "sk-nouvelle"})
    assert "sk-nouvelle" not in r.text
    assert stockage.fournisseur_prive(f["id"])["api_key"] == "sk-nouvelle"

    # Anthropic sans URL : URL par défaut ; sans clé : api_key_set = False
    a = _creer(client, name="Anthropic", type="anthropic", base_url="", api_key=None)
    assert a["base_url"] == "https://api.anthropic.com" and a["api_key_set"] is False

    assert client.post("/api/providers", json={"name": "x", "type": "autre",
                                               "base_url": "http://a"}).status_code == 422
    assert client.post("/api/providers", json={"name": "x", "type": "openai",
                                               "base_url": ""}).status_code == 422

    assert client.delete(f"/api/providers/{f['id']}").status_code == 204
    assert client.delete(f"/api/providers/{f['id']}").status_code == 404
    assert client.patch(f"/api/providers/{f['id']}", json={"name": "y"}).status_code == 404
    assert [p["id"] for p in client.get("/api/providers").json()] == [a["id"]]


def test_put_modeles_et_liste_models(client):
    f = _creer(client)
    modeles = [
        {"id": "deepseek/deepseek-r1", "label": "R1", "thinking": TS, "context_length": 64000},
        {"id": "openai/gpt-4o", "thinking": {"supported": False, "levels": [],
                                             "source": "heuristique"}},
    ]
    r = client.put(f"/api/providers/{f['id']}/models", json={"models": modeles})
    assert r.status_code == 200
    assert [m["id"] for m in r.json()["models"]] == ["deepseek/deepseek-r1", "openai/gpt-4o"]
    assert r.json()["models"][0]["thinking"] == TS

    choix = client.get("/api/models").json()
    assert choix[0] == {"key": f"{f['id']}::deepseek/deepseek-r1", "provider_id": f["id"],
                        "provider_name": "OpenRouter", "model_id": "deepseek/deepseek-r1",
                        "label": "R1", "thinking": TS}
    assert choix[1]["label"] == "openai/gpt-4o"  # label par défaut = id

    # PUT remplace la liste complète
    client.put(f"/api/providers/{f['id']}/models", json={"models": [modeles[1]]})
    assert [m["model_id"] for m in client.get("/api/models").json()] == ["openai/gpt-4o"]
    assert client.put("/api/providers/nope/models", json={"models": []}).status_code == 404


def test_remote_models_marque_les_modeles_actives(client, faux):
    f = _creer(client)
    faux.modeles = [{"id": "a", "owned_by": None, "context_length": None, "thinking": TS},
                    {"id": "b", "owned_by": "x", "context_length": 8000,
                     "thinking": thinking_support(False)}]
    client.put(f"/api/providers/{f['id']}/models", json={"models": [{"id": "b",
                                                                      "thinking": TS}]})
    r = client.get(f"/api/providers/{f['id']}/remote-models")
    assert r.status_code == 200
    assert [(m["id"], m["enabled"]) for m in r.json()] == [("a", False), ("b", True)]


def test_erreur_fournisseur_donne_502(client, faux):
    f = _creer(client)
    faux.erreur_modeles = "GET /models a répondu 401 : clé invalide"
    r = client.get(f"/api/providers/{f['id']}/remote-models")
    assert r.status_code == 502
    assert r.json() == {"detail": "GET /models a répondu 401 : clé invalide"}


def test_reglages(client):
    assert client.get("/api/settings").json() == {"default_model_key": None,
                                                  "default_thinking": None}
    corps = {"default_model_key": "p::m", "default_thinking": "high"}
    assert client.put("/api/settings", json=corps).json() == corps
    assert client.get("/api/settings").json() == corps


def test_crud_conversations(client):
    c = client.post("/api/conversations", json={}).json()
    assert c["messages"] == [] and c["title"] == "Nouvelle conversation"
    c2 = client.post("/api/conversations", json={"title": "Plus-values"}).json()
    assert client.post("/api/conversations").status_code == 200  # corps absent
    r = client.patch(f"/api/conversations/{c['id']}", json={"title": "Renommée"})
    assert r.json()["title"] == "Renommée" and set(r.json()) == {"id", "title", "updated_at"}
    liste = client.get("/api/conversations").json()
    assert liste[0]["id"] == c["id"]  # la plus récemment modifiée d'abord
    assert {x["id"] for x in liste} >= {c["id"], c2["id"]}
    assert client.get(f"/api/conversations/{c2['id']}").json()["title"] == "Plus-values"
    assert client.delete(f"/api/conversations/{c['id']}").status_code == 204
    assert client.get(f"/api/conversations/{c['id']}").status_code == 404
    assert client.post(f"/api/conversations/{c['id']}/stop").status_code == 204


def test_documents_delegues_aux_vues(client, monkeypatch):
    from interstice.outils import vues

    # Vues non implémentées → 501 propre
    def pas_fait(conn, *a, **k):
        raise NotImplementedError

    monkeypatch.setattr(vues, "vue_article", pas_fait)
    r = client.get("/api/documents/article/LEGIARTI1?date=2026-01-01")
    assert r.status_code == 501 and "detail" in r.json()

    # LookupError → 404
    def introuvable(conn, id, date=None):
        raise LookupError(f"section inconnue : {id}")

    monkeypatch.setattr(vues, "vue_section", introuvable)
    r = client.get("/api/documents/section/LEGISCTA9")
    assert r.status_code == 404 and r.json()["detail"] == "section inconnue : LEGISCTA9"

    # Délégation effective (connexion au corpus, paramètres transmis)
    appels = {}

    def recherche(conn, q, texte=None, date=None, limite=20):
        appels["recherche"] = (q, texte, date, conn.execute("select count(*) from articles")
                               .fetchone()[0])
        return [{"id": "A1", "num": "1", "texte_titre": "CGI", "chemin": "", "extrait_html": ""}]

    monkeypatch.setattr(vues, "recherche", recherche)
    monkeypatch.setattr(vues, "vue_texte", lambda conn, cid, date=None: {"id": cid, "date": date})
    monkeypatch.setattr(vues, "lister_textes", lambda conn: [{"cid": "X", "fiscal": True}])
    r = client.get("/api/documents/recherche", params={"q": "plus-value", "texte": "CGI"})
    assert r.json()["resultats"][0]["id"] == "A1"
    assert appels["recherche"] == ("plus-value", "CGI", None, 3)
    assert client.get("/api/documents/texte/LEGITEXT1?date=2020-01-01").json() == {
        "id": "LEGITEXT1", "date": "2020-01-01"}
    assert client.get("/api/textes").json() == [{"cid": "X", "fiscal": True}]


def test_frontend_statique_et_repli_spa(stockage, corpus, tmp_path):
    from fastapi.testclient import TestClient

    from interstice.web.app import create_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app(stockage=stockage, outils=[], chemin_corpus=corpus, dist=dist)
    with TestClient(app) as c:
        assert c.get("/").text == "<html>SPA</html>"
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/conversations/abc").text == "<html>SPA</html>"  # repli SPA
        assert c.get("/api/inexistante").status_code == 404
        r = c.options("/api/health", headers={"Origin": "http://localhost:5173",
                                              "Access-Control-Request-Method": "GET"})
        assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
