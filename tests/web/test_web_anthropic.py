"""Adaptateur Anthropic : SDK officiel branché sur un transport httpx2 simulé (aucun appel réel)."""

from __future__ import annotations

import asyncio
import json

import anthropic
import httpx2
import pytest

from interstice.web.llm.anthropic_natif import (
    AdaptateurAnthropic,
    construire_parametres,
    parametres_reflexion,
    reflexion_heuristique,
)
from interstice.web.llm.base import (
    ErreurFournisseur,
    Fin,
    OutilSpec,
    RequeteLLM,
    TextDelta,
    ThinkingDelta,
    ToolCall,
)


def _sse(*evenements):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in evenements)


FLUX_OUTIL = _sse(
    {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5",
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 1, "cache_read_input_tokens": 900,
                  "cache_creation_input_tokens": 100}}},
    {"type": "content_block_start", "index": 0,
     "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "thinking_delta", "thinking": "Je dois lire "}},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "thinking_delta", "thinking": "le plan du CGI."}},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "signature_delta", "signature": "SIG-abc"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Je "}},
    {"type": "content_block_delta", "index": 1,
     "delta": {"type": "text_delta", "text": "consulte."}},
    {"type": "content_block_stop", "index": 1},
    {"type": "content_block_start", "index": 2, "content_block": {
        "type": "tool_use", "id": "toolu_1", "name": "sommaire", "input": {}}},
    {"type": "content_block_delta", "index": 2,
     "delta": {"type": "input_json_delta", "partial_json": "{\"texte\": "}},
    {"type": "content_block_delta", "index": 2,
     "delta": {"type": "input_json_delta", "partial_json": "\"CGI\"}"}},
    {"type": "content_block_stop", "index": 2},
    {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None},
     "usage": {"output_tokens": 42}},
    {"type": "message_stop"},
)


def _client_simule(reponses, capture):
    def handler(request: httpx2.Request) -> httpx2.Response:
        capture.append(request)
        statut, corps, type_ = reponses.pop(0)
        return httpx2.Response(statut, content=corps.encode("utf-8"),
                               headers={"content-type": type_})

    return anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))


def _requete(model="claude-opus-5", niveau="high", historique=None):
    return RequeteLLM(model=model, system="PROMPT FIGÉ",
                      historique=historique or [{"role": "user", "content": "Q"}],
                      outils=[OutilSpec("sommaire", "Plan.", {"type": "object", "properties": {}}),
                              OutilSpec("lire_article", "Article.",
                                        {"type": "object", "properties": {}})],
                      niveau_reflexion=niveau)


def test_flux_reflexion_texte_outil_et_requete():
    capture: list = []
    ad = AdaptateurAnthropic("https://api.anthropic.com/v1/", "sk-ant-test",
                             http_client=_client_simule(
                                 [(200, FLUX_OUTIL, "text/event-stream")], capture))

    async def run():
        return [ev async for ev in ad.flux(_requete())]

    evs = asyncio.run(run())
    assert evs[:4] == [ThinkingDelta("Je dois lire "), ThinkingDelta("le plan du CGI."),
                       TextDelta("Je "), TextDelta("consulte.")]
    assert evs[4] == ToolCall("toolu_1", "sommaire", {"texte": "CGI"})
    fin = evs[5]
    assert isinstance(fin, Fin) and fin.stop_reason == "tool_use"
    assert (fin.usage.input_tokens, fin.usage.output_tokens, fin.usage.cache_read_tokens) == (
        1012, 42, 900)
    # Blocs rejouables tels quels (réflexion signée comprise)
    assert fin.brut == {"format": "anthropic", "model": "claude-opus-5", "content": [
        {"type": "thinking", "thinking": "Je dois lire le plan du CGI.", "signature": "SIG-abc"},
        {"type": "text", "text": "Je consulte."},
        {"type": "tool_use", "id": "toolu_1", "name": "sommaire", "input": {"texte": "CGI"}},
    ]}

    req = capture[0]
    assert str(req.url) == "https://api.anthropic.com/v1/messages"
    assert req.headers["x-api-key"] == "sk-ant-test"
    corps = json.loads(req.content)
    assert corps["stream"] is True
    assert corps["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert corps["output_config"] == {"effort": "high"}
    assert "budget_tokens" not in json.dumps(corps)
    assert corps["system"] == [{"type": "text", "text": "PROMPT FIGÉ",
                                "cache_control": {"type": "ephemeral"}}]
    assert "cache_control" not in corps["tools"][0]
    assert corps["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert corps["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert corps["cache_control"] == {"type": "ephemeral"}


def test_rejeu_des_blocs_de_reflexion_dans_la_boucle_d_outils():
    brut = {"format": "anthropic", "model": "claude-opus-5", "content": [
        {"type": "thinking", "thinking": "t", "signature": "SIG"},
        {"type": "tool_use", "id": "toolu_1", "name": "sommaire", "input": {"texte": "CGI"}}]}
    hist = [
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "", "brut": brut,
         "tool_calls": [{"id": "toolu_1", "name": "sommaire", "arguments": {"texte": "CGI"}}]},
        {"role": "tool", "results": [{"call_id": "toolu_1", "name": "sommaire",
                                      "content": "plan", "is_error": False}]},
    ]
    msgs = construire_parametres(_requete(historique=hist))["messages"]
    assert msgs[1] == {"role": "assistant", "content": brut["content"]}
    assert msgs[2] == {"role": "user", "content": [{"type": "tool_result",
                                                    "tool_use_id": "toolu_1",
                                                    "content": "plan", "is_error": False}]}
    # Autre modèle : pas de rejeu des blocs signés, reconstruction neutre
    msgs = construire_parametres(_requete(model="claude-sonnet-5", historique=hist))["messages"]
    assert msgs[1]["content"] == [{"type": "tool_use", "id": "toolu_1", "name": "sommaire",
                                   "input": {"texte": "CGI"}}]


def test_parametres_de_reflexion_par_modele():
    assert parametres_reflexion("claude-opus-5", None) == {}
    assert parametres_reflexion("claude-fable-5-1", "max") == {
        "thinking": {"type": "adaptive", "display": "summarized"},
        "output_config": {"effort": "max"}}
    assert parametres_reflexion("claude-haiku-4-5", "medium") == {
        "thinking": {"type": "enabled", "budget_tokens": 8192}}
    assert reflexion_heuristique("claude-opus-4-6")["levels"] == ["low", "medium", "high", "max"]
    assert reflexion_heuristique("claude-opus-5")["levels"][-2:] == ["xhigh", "max"]
    assert reflexion_heuristique("claude-3-5-haiku-latest")["supported"] is False


def test_liste_des_modeles_via_capacites():
    corps = json.dumps({"data": [
        {"type": "model", "id": "claude-opus-5", "display_name": "Claude Opus 5",
         "created_at": "2026-01-01T00:00:00Z", "max_input_tokens": 1000000, "max_tokens": 128000,
         "capabilities": {
             "thinking": {"supported": True, "types": {"adaptive": {"supported": True},
                                                       "enabled": {"supported": False}}},
             "effort": {"supported": True, "low": {"supported": True},
                        "medium": {"supported": True}, "high": {"supported": True},
                        "xhigh": {"supported": True}, "max": {"supported": True}}}},
        {"type": "model", "id": "claude-sans-capacites", "display_name": "X",
         "created_at": "2025-01-01T00:00:00Z"},
    ], "has_more": False, "first_id": "claude-opus-5", "last_id": "claude-sans-capacites"})
    capture: list = []
    ad = AdaptateurAnthropic(None, "k", http_client=_client_simule(
        [(200, corps, "application/json")], capture))
    modeles = asyncio.run(ad.lister_modeles())
    assert capture[0].url.path == "/v1/models"
    assert modeles[0]["id"] == "claude-opus-5" and modeles[0]["context_length"] == 1000000
    assert modeles[0]["thinking"] == {"supported": True, "source": "api",
                                      "levels": ["low", "medium", "high", "xhigh", "max"]}
    assert modeles[1]["thinking"]["source"] == "heuristique"


def test_erreur_400_sur_la_reflexion():
    corps = json.dumps({"type": "error", "error": {
        "type": "invalid_request_error", "message": "thinking.type.disabled is not supported"}})
    ad = AdaptateurAnthropic(None, "k", http_client=_client_simule(
        [(400, corps, "application/json")], []))

    async def run():
        return [ev async for ev in ad.flux(_requete(niveau="low"))]

    with pytest.raises(ErreurFournisseur) as e:
        asyncio.run(run())
    assert e.value.status == 400 and "réglage de réflexion" in e.value.message
