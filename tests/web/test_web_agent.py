"""Déroulé SSE complet de la boucle agent (faux adaptateur scripté, faux outils)."""

from __future__ import annotations

import asyncio

from outillage_web import FAUX_OUTILS, FauxAdaptateur, lire_sse

from interstice.web import agent
from interstice.web.llm.base import (
    ErreurFournisseur,
    Fin,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
    thinking_support,
)


def _preparer(client, reflexion=True):
    f = client.post("/api/providers", json={"name": "P", "type": "openai",
                                            "base_url": "http://llm.local/v1"}).json()
    ts = thinking_support(reflexion, ["low", "medium", "high"], "api")
    client.put(f"/api/providers/{f['id']}/models", json={"models": [{"id": "m1", "thinking": ts}]})
    c = client.post("/api/conversations", json={}).json()
    return f"{f['id']}::m1", c["id"]


def _envoyer(client, cid, cle, contenu="Quel est le taux du PFU ?", niveau="high"):
    r = client.post(f"/api/conversations/{cid}/messages",
                    json={"content": contenu, "model_key": cle, "thinking_level": niveau})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    return lire_sse(r.text)


def test_deroule_complet_avec_appels_d_outils(client, faux, stockage):
    cle, cid = _preparer(client)
    faux.tours = [
        [ThinkingDelta("Il faut "), ThinkingDelta("consulter le CGI."),
         TextDelta("Je consulte le plan."),
         ToolCall("c1", "sommaire", {"texte": "CGI"}),
         ToolCall("c2", "lire_article", {"id": "LEGIARTI000048"}),
         Fin(Usage(100, 20, 80), "tool_use", brut={"format": "x"})],
        [TextDelta("Le taux est de "), TextDelta("12,8 %."),
         Fin(Usage(300, 30, 250), "end_turn")],
    ]
    evs = _envoyer(client, cid, cle)
    noms = [e for e, _ in evs]
    assert noms == ["user_message", "message_start", "thinking_delta", "thinking_delta",
                    "text_delta", "tool_call", "tool_call", "tool_result", "tool_result",
                    "text_delta", "text_delta", "message_end"]
    d = dict(evs[:2])
    assert d["user_message"]["role"] == "user"
    assert d["user_message"]["parts"] == [{"type": "text", "text": "Quel est le taux du PFU ?"}]
    mid = d["message_start"]["message_id"]
    assert d["message_start"] == {"message_id": mid, "model_key": cle, "thinking_level": "high"}
    assert evs[5][1] == {"call_id": "c1", "name": "sommaire", "arguments": {"texte": "CGI"}}
    r1 = evs[7][1]
    assert r1["call_id"] == "c1" and r1["status"] == "done"
    assert r1["summary"] == "Sommaire de CGI"
    assert r1["documents"] == [{"kind": "texte", "id": "LEGITEXT000006069577",
                                "titre": "Code général des impôts", "sous_titre": "Sommaire",
                                "date": None}]
    assert evs[8][1]["documents"][0]["kind"] == "article"
    fin = evs[-1][1]
    assert isinstance(fin["usage"].pop("duree_ms"), int)  # durée réelle, pour « A travaillé pendant … »
    assert fin == {"message_id": mid, "usage": {"input_tokens": 400, "output_tokens": 50,
                                                "cache_read_tokens": 330}}

    # Deuxième requête : les deux résultats sont renvoyés ensemble, après l'appel.
    h = faux.requetes[1].historique
    assert [x["role"] for x in h] == ["user", "assistant", "tool"]
    assert h[0]["content"].startswith("[Date du jour : ") and "PFU" in h[0]["content"]
    assert h[1]["tool_calls"][1] == {"id": "c2", "name": "lire_article",
                                     "arguments": {"id": "LEGIARTI000048"}}
    assert h[1]["brut"] == {"format": "x"}
    assert [r["call_id"] for r in h[2]["results"]] == ["c1", "c2"]
    assert "Texte de l'article" in h[2]["results"][1]["content"]
    assert faux.requetes[0].niveau_reflexion == "high"
    assert [o.name for o in faux.requetes[0].outils] == ["sommaire", "lire_article"]
    assert "L64" in faux.requetes[0].system and "1741" in faux.requetes[0].system

    # Persistance : parts du contrat, titre automatique
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["title"] == "Quel est le taux du PFU ?"
    user, asst = conv["messages"]
    assert asst["id"] == mid and asst["error"] is None and asst["model_key"] == cle
    assert asst["usage"].pop("duree_ms") >= 0  # persistée avec le message
    assert asst["usage"] == {"input_tokens": 400, "output_tokens": 50, "cache_read_tokens": 330}
    assert [p["type"] for p in asst["parts"]] == ["thinking", "text", "tool", "tool", "text"]
    assert asst["parts"][0]["text"] == "Il faut consulter le CGI."
    assert asst["parts"][4]["text"] == "Le taux est de 12,8 %."
    assert asst["parts"][2]["status"] == "done" and asst["parts"][2]["documents"]
    assert "trace" not in asst

    # Tour suivant : l'historique rejoue la trace complète (rien n'est perdu)
    faux.tours = [[TextDelta("Oui."), Fin(Usage(1, 1, 0), "end_turn")]]
    _envoyer(client, cid, cle, contenu="Et en 2025 ?", niveau=None)
    h = faux.requetes[2].historique
    assert [x["role"] for x in h] == ["user", "assistant", "tool", "assistant", "user"]
    assert h[3]["content"] == "Le taux est de 12,8 %."
    assert faux.requetes[2].niveau_reflexion is None


def test_erreurs_d_outil_renvoyees_au_modele(client, faux):
    cle, cid = _preparer(client)
    faux.tours = [
        [ToolCall("c1", "sommaire", {"texte": "INCONNU"}),
         ToolCall("c2", "outil_fantome", {}),
         ToolCall("c3", "lire_article", {}, erreur_arguments="arguments JSON invalides"),
         Fin(Usage(), "tool_use")],
        [TextDelta("Désolé."), Fin(Usage(), "end_turn")],
    ]
    evs = _envoyer(client, cid, cle)
    res = [d for e, d in evs if e == "tool_result"]
    assert [r["status"] for r in res] == ["error", "error", "error"]
    h = faux.requetes[1].historique[-1]
    assert all(r["is_error"] for r in h["results"])
    assert "texte inconnu" in h["results"][0]["content"]
    assert "outil inconnu" in h["results"][1]["content"]


def test_niveau_ignore_si_modele_sans_reflexion(client, faux):
    cle, cid = _preparer(client, reflexion=False)
    faux.tours = [[TextDelta("ok"), Fin(Usage(), "end_turn")]]
    evs = _envoyer(client, cid, cle, niveau="high")
    assert evs[1][1]["thinking_level"] is None
    assert faux.requetes[0].niveau_reflexion is None


def test_erreur_fournisseur_en_cours_de_flux_garde_le_message_partiel(client, faux):
    cle, cid = _preparer(client)
    faux.tours = [[TextDelta("Début de réponse"),
                   ErreurFournisseur("Le fournisseur a répondu 429 : quota dépassé", 429)]]
    evs = _envoyer(client, cid, cle)
    assert [e for e, _ in evs][-3:] == ["text_delta", "error", "message_end"]
    assert evs[-2][1] == {"message": "Le fournisseur a répondu 429 : quota dépassé"}
    asst = client.get(f"/api/conversations/{cid}").json()["messages"][1]
    assert asst["error"] == "Le fournisseur a répondu 429 : quota dépassé"
    assert asst["parts"] == [{"type": "text", "text": "Début de réponse"}]


def test_validation_avant_flux(client):
    cle, cid = _preparer(client)
    corps = {"content": "x", "model_key": cle, "thinking_level": None}
    assert client.post("/api/conversations/nope/messages", json=corps).status_code == 404
    assert client.post(f"/api/conversations/{cid}/messages",
                       json={**corps, "model_key": "sans-separateur"}).status_code == 422
    assert client.post(f"/api/conversations/{cid}/messages",
                       json={**corps, "model_key": "inconnu::m"}).status_code == 404
    assert client.post(f"/api/conversations/{cid}/messages",
                       json={**corps, "content": "  "}).status_code == 422


def test_refus_et_troncature(client, faux):
    cle, cid = _preparer(client)
    faux.tours = [[Fin(Usage(), "refusal")]]
    evs = _envoyer(client, cid, cle)
    assert evs[-2][0] == "error" and "refusé" in evs[-2][1]["message"]


def test_limite_de_tours_d_outils(client, faux, monkeypatch):
    monkeypatch.setattr(agent, "MAX_TOURS_OUTILS", 2)
    cle, cid = _preparer(client)
    faux.tours = [[ToolCall(f"c{i}", "sommaire", {"texte": "CGI"}), Fin(Usage(), "tool_use")]
                  for i in range(3)]
    evs = _envoyer(client, cid, cle)
    assert len(faux.requetes) == 3
    res = [d for e, d in evs if e == "tool_result"]
    assert [r["status"] for r in res] == ["done", "done", "error"]
    assert evs[-2][0] == "error" and "Limite de 2 tours" in evs[-2][1]["message"]


def test_arret_pendant_le_flux(stockage):
    """/stop pendant que le fournisseur est silencieux : message partiel persisté."""

    class Lent(FauxAdaptateur):
        async def flux(self, requete):
            yield TextDelta("Analyse en cours")
            await asyncio.sleep(3600)
            yield Fin()

    cid = stockage.creer_conversation()["id"]

    async def scenario():
        ctx = agent.ContexteGeneration(
            stockage=stockage, adaptateur=Lent(), conversation_id=cid, contenu="Question",
            model_id="m", model_key="p::m", niveau_reflexion=None, outils=FAUX_OUTILS,
            ouvrir_corpus=lambda: None)
        evs = []
        async for e, d in agent.generer(ctx):
            evs.append((e, d))
            if e == "text_delta":
                ctx.arret.set()
        return evs

    evs = asyncio.run(asyncio.wait_for(scenario(), timeout=10))
    assert [e for e, _ in evs] == ["user_message", "message_start", "text_delta", "error",
                                   "message_end"]
    assert "interrompue" in evs[3][1]["message"]
    asst = stockage.conversation(cid)["messages"][1]
    assert asst["parts"] == [{"type": "text", "text": "Analyse en cours"}]
    assert asst["error"] == "Génération interrompue par l'utilisateur."


def test_normalisation_d_un_historique_interrompu():
    from interstice.web.llm.base import normaliser_historique

    h = normaliser_historique([
        {"role": "assistant", "content": "orphelin", "tool_calls": []},
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "a", "name": "sommaire", "arguments": {}},
            {"id": "b", "name": "sommaire", "arguments": {}}]},
        {"role": "tool", "results": [{"call_id": "a", "name": "sommaire", "content": "ok",
                                      "is_error": False}]},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "user", "content": "Q2"},
    ])
    assert [x["role"] for x in h] == ["user", "assistant", "tool", "user"]
    assert [(r["call_id"], r["is_error"]) for r in h[2]["results"]] == [("a", False),
                                                                         ("b", True)]
