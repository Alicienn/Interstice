"""Adaptateur OpenAI-compatible sur des flux SSE bruts enregistrés (httpx.MockTransport)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from interstice.web.llm.base import (
    ErreurFournisseur,
    Fin,
    OutilSpec,
    RequeteLLM,
    TextDelta,
    ThinkingDelta,
    ToolCall,
)
from interstice.web.llm.openai_compat import AdaptateurOpenAI, detecter_reflexion

# Flux réel (forme OpenAI) : deux appels d'outils parallèles, arguments fragmentés,
# chunk d'usage final sans choices (stream_options.include_usage).
FLUX_TOOL_CALLS = """\
data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{"role":"assistant","content":null,"tool_calls":[{"index":0,"id":"call_AAA","type":"function","function":{"name":"sommaire","arguments":""}}]},"finish_reason":null}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"te"}}]},"finish_reason":null}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"xte\\": \\"CGI\\"}"}}]},"finish_reason":null}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"id":"call_BBB","type":"function","function":{"name":"lire_article","arguments":""}}]},"finish_reason":null}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"function":{"arguments":"{\\"id\\":"}}]},"finish_reason":null}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"function":{"arguments":" \\"LEGIARTI000048\\", \\"note\\": \\"é\\"}"}}]},"finish_reason":null}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}],"usage":null}

data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1,"model":"gpt-4.1","choices":[],"usage":{"prompt_tokens":812,"completion_tokens":57,"total_tokens":869,"prompt_tokens_details":{"cached_tokens":768}}}

data: [DONE]

"""

# DeepSeek : réflexion dans delta.reasoning_content ; CRLF et commentaire keep-alive.
FLUX_DEEPSEEK = (
    ': keep-alive\r\n\r\n'
    'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":null,'
    '"reasoning_content":"Le PFU "}}]}\r\n\r\n'
    'data: {"choices":[{"index":0,"delta":{"content":null,"reasoning_content":"vaut 30 %."}}]}'
    '\r\n\r\n'
    'data: {"choices":[{"index":0,"delta":{"content":"Réponse : 12,8 % d\'IR.",'
    '"reasoning_content":null}}]}\r\n\r\n'
    'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],'
    '"usage":{"prompt_tokens":10,"completion_tokens":5}}\r\n\r\n'
    'data: [DONE]\r\n\r\n'
)

# OpenRouter : réflexion dans delta.reasoning, commentaire de traitement.
FLUX_OPENROUTER = """\
: OPENROUTER PROCESSING

data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"","reasoning":"Je vérifie","reasoning_details":[{"type":"reasoning.text","text":"Je vérifie"}]}}]}

data: {"choices":[{"index":0,"delta":{"content":"OK","reasoning":null}}]}

data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

"""


def _requete(niveau=None, **kw):
    return RequeteLLM(
        model="m", system="SYS",
        historique=[
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "", "brut": None,
             "tool_calls": [{"id": "call_0", "name": "sommaire", "arguments": {"texte": "CGI"}}]},
            {"role": "tool", "results": [{"call_id": "call_0", "name": "sommaire",
                                          "content": "plan", "is_error": False}]},
            {"role": "assistant", "content": "R1", "tool_calls": [], "brut": None},
            {"role": "user", "content": "Q2"},
        ],
        outils=[OutilSpec("sommaire", "Plan.", {"type": "object", "properties": {}})],
        niveau_reflexion=niveau, **kw)


def _adaptateur(base_url, corps_reponse, statut=200, capture=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture.append(request)
        return httpx.Response(statut, content=corps_reponse.encode("utf-8"),
                              headers={"content-type": "text/event-stream"})

    return AdaptateurOpenAI(base_url, "sk-test", transport=httpx.MockTransport(handler))


def _collecter(adaptateur, requete):
    async def run():
        return [ev async for ev in adaptateur.flux(requete)]

    return asyncio.run(run())


def test_accumulation_tool_calls_fragmentes_et_requete():
    capture: list[httpx.Request] = []
    evs = _collecter(_adaptateur("https://api.openai.com/v1/", FLUX_TOOL_CALLS, capture=capture),
                     _requete(niveau="medium"))
    appels = [e for e in evs if isinstance(e, ToolCall)]
    assert appels == [
        ToolCall("call_AAA", "sommaire", {"texte": "CGI"}),
        ToolCall("call_BBB", "lire_article", {"id": "LEGIARTI000048", "note": "é"}),
    ]
    fin = evs[-1]
    assert isinstance(fin, Fin) and fin.stop_reason == "tool_use"
    assert (fin.usage.input_tokens, fin.usage.output_tokens, fin.usage.cache_read_tokens) == (
        812, 57, 768)

    req = capture[0]
    assert str(req.url) == "https://api.openai.com/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-test"
    corps = json.loads(req.content)
    assert corps["stream"] is True and corps["stream_options"] == {"include_usage": True}
    assert corps["reasoning_effort"] == "medium" and "reasoning" not in corps
    assert corps["tools"][0] == {"type": "function", "function": {
        "name": "sommaire", "description": "Plan.", "parameters": {"type": "object",
                                                                   "properties": {}}}}
    msgs = corps["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool", "assistant",
                                         "user"]
    assert msgs[2]["tool_calls"][0]["function"] == {"name": "sommaire",
                                                    "arguments": '{"texte": "CGI"}'}
    assert msgs[3] == {"role": "tool", "tool_call_id": "call_0", "content": "plan"}


def test_reasoning_content_deepseek():
    evs = _collecter(_adaptateur("https://api.deepseek.com", FLUX_DEEPSEEK), _requete())
    assert evs[:3] == [ThinkingDelta("Le PFU "), ThinkingDelta("vaut 30 %."),
                       TextDelta("Réponse : 12,8 % d'IR.")]
    assert evs[3].stop_reason == "end_turn" and evs[3].usage.input_tokens == 10


def test_reasoning_openrouter_et_parametre_reasoning():
    capture: list[httpx.Request] = []
    evs = _collecter(_adaptateur("https://openrouter.ai/api/v1", FLUX_OPENROUTER,
                                 capture=capture), _requete(niveau="high"))
    assert evs[:2] == [ThinkingDelta("Je vérifie"), TextDelta("OK")]
    corps = json.loads(capture[0].content)
    assert corps["reasoning"] == {"effort": "high"} and "reasoning_effort" not in corps


def test_400_sur_parametre_de_reflexion_donne_erreur_claire_sans_nouvel_essai():
    capture: list[httpx.Request] = []
    corps = json.dumps({"error": {"message": "Unrecognized request argument supplied: "
                                             "reasoning_effort", "type": "invalid_request_error"}})
    ad = _adaptateur("https://api.mistral.ai/v1", corps, statut=400, capture=capture)
    with pytest.raises(ErreurFournisseur) as e:
        _collecter(ad, _requete(niveau="low"))
    assert len(capture) == 1
    assert e.value.status == 400
    assert "reasoning_effort='low'" in e.value.message
    assert "Unrecognized request argument" in e.value.message


def test_erreur_http_generique():
    ad = _adaptateur("https://x.test/v1", '{"error":{"message":"Invalid API key"}}', statut=401)
    with pytest.raises(ErreurFournisseur) as e:
        _collecter(ad, _requete())
    assert e.value.message == "Le fournisseur a répondu 401 : Invalid API key"


def test_liste_des_modeles_et_detection_de_la_reflexion():
    corps = json.dumps({"data": [
        {"id": "deepseek/deepseek-r1", "context_length": 163840,
         "supported_parameters": ["tools", "reasoning", "include_reasoning"]},
        {"id": "openai/gpt-4o", "context_length": 128000,
         "supported_parameters": ["tools", "temperature"]},
    ]})
    capture: list[httpx.Request] = []

    def handler(request):
        capture.append(request)
        return httpx.Response(200, content=corps.encode())

    ad = AdaptateurOpenAI("https://openrouter.ai/api/v1", "k",
                          transport=httpx.MockTransport(handler))
    modeles = asyncio.run(ad.lister_modeles())
    assert str(capture[0].url) == "https://openrouter.ai/api/v1/models"
    assert capture[0].headers["authorization"] == "Bearer k"
    assert modeles[0] == {"id": "deepseek/deepseek-r1", "owned_by": None, "label": None,
                          "context_length": 163840, "max_output": None,
                          "thinking": {"supported": True, "levels": ["low", "medium", "high"],
                                       "source": "api"}}
    assert modeles[1]["thinking"] == {"supported": False, "levels": [], "source": "api"}


@pytest.mark.parametrize("ident,attendu", [
    ("o3-mini", True), ("o1", True), ("o4-mini-2025-04-16", True), ("gpt-5", True),
    ("deepseek-reasoner", True), ("claude-3-7-sonnet-thinking", True), ("qwq-32b", True),
    ("deepseek-r1:14b", True), ("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", True),
    ("gpt-4o", False), ("mistral-large-latest", False), ("llama-3.3-70b", False),
    ("gpt-4o-2024-08-06", False),
])
def test_heuristique_reflexion(ident, attendu):
    ts = detecter_reflexion({"id": ident})
    assert ts["supported"] is attendu
    assert ts["source"] == "heuristique"
    assert ts["levels"] == (["low", "medium", "high"] if attendu else [])


def test_models_erreur_donne_erreur_fournisseur():
    ad = AdaptateurOpenAI("https://x.test/v1", "k", transport=httpx.MockTransport(
        lambda r: httpx.Response(403, json={"error": {"message": "forbidden"}})))
    with pytest.raises(ErreurFournisseur, match=r"403 \(vérifiez la clé API\) : forbidden"):
        asyncio.run(ad.lister_modeles())


def test_models_pagination_has_more_et_jeton():
    """Anthropic-compatible (has_more/last_id) puis Google (next_page_token) : toutes les pages lues."""
    appels: list[httpx.Request] = []

    def handler(request):
        appels.append(request)
        p = dict(request.url.params)
        if "after_id" in p:
            return httpx.Response(200, json={"data": [{"id": "m3"}], "has_more": False})
        if "pageToken" in p:
            return httpx.Response(200, json={"models": [{"id": "m4", "display_name": "Modèle 4",
                                                         "inputTokenLimit": 1000}]})
        if request.url.host == "a.test":
            return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}], "has_more": True,
                                             "last_id": "m2"})
        return httpx.Response(200, json={"models": [{"id": "m0"}], "next_page_token": "t1"})

    a = asyncio.run(AdaptateurOpenAI("https://a.test/v1", "k", transport=httpx.MockTransport(handler))
                    .lister_modeles())
    assert [m["id"] for m in a] == ["m1", "m2", "m3"]
    assert dict(appels[1].url.params)["after_id"] == "m2"
    g = asyncio.run(AdaptateurOpenAI("https://g.test/v1beta/openai", "k",
                                     transport=httpx.MockTransport(handler)).lister_modeles())
    assert [m["id"] for m in g] == ["m0", "m4"]
    assert g[1]["label"] == "Modèle 4" and g[1]["context_length"] == 1000
    assert str(appels[2].url) == "https://g.test/v1beta/openai/models"  # préfixe conservé


def test_models_entree_sans_id_ignoree():
    ad = AdaptateurOpenAI("https://x.test/v1", "k", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"data": [{"object": "model"}, {"id": "ok"}]})))
    assert [m["id"] for m in asyncio.run(ad.lister_modeles())] == ["ok"]
