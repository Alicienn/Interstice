"""La génération continue en arrière-plan quand le client quitte la conversation.

Test d'intégration avec un vrai serveur uvicorn et un vrai client HTTP : le client de test de
Starlette ne simule pas la fermeture de connexion côté navigateur.
"""

from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest
import uvicorn
from outillage_web import FAUX_OUTILS, lire_sse

from interstice.web.app import create_app
from interstice.web.llm.base import Fin, TextDelta, ToolCall, Usage

MORCEAUX = [f"mot{i} " for i in range(20)]


@pytest.fixture
def serveur(stockage, faux, corpus, tmp_path):
    async def catalogue_vide():
        return {}

    app = create_app(stockage=stockage, outils=FAUX_OUTILS, fabrique_adaptateur=lambda f: faux,
                     chemin_corpus=corpus, dist=tmp_path / "x", catalogue=catalogue_vide)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(5)


def _preparer(base: str) -> tuple[str, str]:
    with httpx.Client(base_url=base) as c:
        f = c.post("/api/providers", json={"name": "P", "type": "openai", "base_url": "http://llm.local/v1"}).json()
        c.put(f"/api/providers/{f['id']}/models", json={"models": [
            {"id": "m1", "thinking": {"supported": False, "levels": [], "source": "api"}}]})
        cid = c.post("/api/conversations", json={}).json()["id"]
    return f"{f['id']}::m1", cid


def _scenario(faux):
    faux.delai = 0.05
    faux.tours = [
        [TextDelta("Je consulte. "), ToolCall("c1", "sommaire", {"texte": "CGI"}), Fin(Usage(10, 5), "tool_use")],
        [*(TextDelta(m) for m in MORCEAUX), Fin(Usage(20, 20), "end_turn")],
    ]


def _attendre_fin(base: str, cid: str, delai: float = 15.0) -> dict:
    fin = time.time() + delai
    with httpx.Client(base_url=base) as c:
        while time.time() < fin:
            conv = c.get(f"/api/conversations/{cid}").json()
            if not conv.get("generation_en_cours"):
                return conv
            time.sleep(0.1)
    raise AssertionError("la génération ne s'est pas terminée")


def test_quitter_la_conversation_n_arrete_pas_la_generation(serveur, faux):
    cle, cid = _preparer(serveur)
    _scenario(faux)
    with httpx.Client(base_url=serveur, timeout=10) as c:
        with c.stream("POST", f"/api/conversations/{cid}/messages",
                      json={"content": "Question ?", "model_key": cle, "thinking_level": None}) as r:
            for ligne in r.iter_lines():
                if ligne.startswith("event: text_delta"):
                    break  # l'utilisateur quitte la conversation en pleine rédaction
    conv = _attendre_fin(serveur, cid)
    msg = conv["messages"][-1]
    assert msg["role"] == "assistant" and not msg.get("error"), msg
    texte = "".join(p["text"] for p in msg["parts"] if p["type"] == "text")
    assert texte == "Je consulte. " + "".join(MORCEAUX)
    assert any(p["type"] == "tool" and p["status"] == "done" for p in msg["parts"])


def test_revenir_sur_la_conversation_reprend_le_flux(serveur, faux):
    cle, cid = _preparer(serveur)
    _scenario(faux)
    with httpx.Client(base_url=serveur, timeout=10) as c:
        with c.stream("POST", f"/api/conversations/{cid}/messages",
                      json={"content": "Question ?", "model_key": cle, "thinking_level": None}) as r:
            for ligne in r.iter_lines():
                if ligne.startswith("event: tool_call"):
                    break
        conv = c.get(f"/api/conversations/{cid}").json()
        assert conv["generation_en_cours"] is True
        # rattachement : rejoue depuis le début du message, puis le direct, jusqu'à message_end
        r = c.get(f"/api/conversations/{cid}/stream", timeout=20)
        evs = lire_sse(r.text)
    noms = [e for e, _ in evs]
    assert noms[0] == "user_message" and noms[1] == "message_start" and noms[-1] == "message_end"
    assert "".join(d["text"] for e, d in evs if e == "text_delta") == "Je consulte. " + "".join(MORCEAUX)
    with httpx.Client(base_url=serveur) as c:
        assert c.get(f"/api/conversations/{cid}/stream").status_code == 204  # plus rien en cours


def test_stop_arrete_toujours(serveur, faux):
    cle, cid = _preparer(serveur)
    _scenario(faux)
    with httpx.Client(base_url=serveur, timeout=10) as c:
        with c.stream("POST", f"/api/conversations/{cid}/messages",
                      json={"content": "Question ?", "model_key": cle, "thinking_level": None}) as r:
            for ligne in r.iter_lines():
                if ligne.startswith("event: text_delta"):
                    break
        assert c.post(f"/api/conversations/{cid}/stop").status_code == 204
    conv = _attendre_fin(serveur, cid)
    assert "interrompue" in (conv["messages"][-1].get("error") or "").lower()
