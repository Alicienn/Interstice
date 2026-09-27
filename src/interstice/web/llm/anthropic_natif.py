"""Adaptateur « anthropic » : API Messages native via le SDK officiel `anthropic` (1.x, httpx2).

- Réflexion adaptative : `thinking={"type": "adaptive", "display": "summarized"}` +
  `output_config={"effort": niveau}` sur les modèles récents ; jamais de `budget_tokens` pour eux.
  Les anciens modèles (Haiku 4.5, Sonnet/Opus 4.5 et antérieurs) utilisent
  `{"type": "enabled", "budget_tokens": N}` sans `effort`.
- Sans niveau demandé, on n'envoie ni `thinking` ni `output_config` : certains modèles refusent
  `thinking: disabled` (Fable 5/5.1, Opus 5.5 ; Opus 5 au-delà de `high`), l'omission est
  toujours acceptée (ces modèles réfléchissent alors par défaut, sans affichage).
- Cache de prompt : `cache_control` sur le dernier outil et sur le bloc système (préfixe stable),
  plus le cache automatique de haut niveau pour la queue de conversation.
- Boucle d'outils : les blocs de réflexion (signés) sont rejoués tels quels au modèle via
  `brut` tant que le modèle ne change pas.
"""

from __future__ import annotations

import re
from typing import Any, AsyncIterator

import anthropic

from interstice.web.llm.base import (
    ErreurFournisseur,
    Evenement,
    Fin,
    RequeteLLM,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
    normaliser_historique,
    thinking_support,
)

URL_DEFAUT = "https://api.anthropic.com"
NIVEAUX_EFFORT = ["low", "medium", "high", "xhigh", "max"]
BUDGETS = {"low": 2048, "medium": 8192, "high": 16384, "xhigh": 24576, "max": 30000}

# Modèles à réflexion « budget_tokens » (antérieurs à la réflexion adaptative).
_MOTIFS_BUDGET = [r"haiku-4-5", r"sonnet-4-5", r"opus-4-5", r"opus-4-1", r"opus-4-0",
                  r"sonnet-4-0", r"opus-4-2025", r"sonnet-4-2025", r"3-7-sonnet"]
_MOTIFS_4_6 = [r"opus-4-6", r"sonnet-4-6"]


def normaliser_base_url(base_url: str | None) -> str:
    url = (base_url or "").strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url or URL_DEFAUT


def mode_reflexion(model_id: str) -> str:
    """'adaptive' | 'budget' | 'aucun' d'après l'identifiant."""
    m = model_id.lower()
    if any(re.search(p, m) for p in _MOTIFS_BUDGET):
        return "budget"
    if re.search(r"claude-3-", m) or not m.startswith("claude"):
        return "aucun"
    return "adaptive"


def reflexion_heuristique(model_id: str) -> dict[str, Any]:
    mode = mode_reflexion(model_id)
    if mode == "aucun":
        return thinking_support(False, [], "heuristique")
    if mode == "budget":
        return thinking_support(True, ["low", "medium", "high"], "heuristique")
    if any(re.search(p, model_id.lower()) for p in _MOTIFS_4_6):
        return thinking_support(True, ["low", "medium", "high", "max"], "heuristique")
    return thinking_support(True, NIVEAUX_EFFORT, "heuristique")


def _en_dict(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    for meth in ("to_dict", "model_dump"):
        f = getattr(obj, meth, None)
        if callable(f):
            try:
                return f()
            except TypeError:
                continue
    return None


def _supporte(noeud: Any) -> bool:
    return isinstance(noeud, dict) and bool(noeud.get("supported"))


def reflexion_depuis_capacites(model_id: str, capacites: Any) -> dict[str, Any]:
    caps = _en_dict(capacites)
    if not caps or "thinking" not in caps:
        return reflexion_heuristique(model_id)
    thinking = caps.get("thinking") or {}
    if not _supporte(thinking):
        return thinking_support(False, [], "api")
    types = thinking.get("types") or {}
    effort = caps.get("effort") or {}
    if _supporte(types.get("adaptive")) and _supporte(effort):
        niveaux = [n for n in NIVEAUX_EFFORT if _supporte(effort.get(n))]
        return thinking_support(True, niveaux or ["low", "medium", "high"], "api")
    return thinking_support(True, ["low", "medium", "high"], "api")


def max_tokens_pour(model_id: str) -> int:
    mode = mode_reflexion(model_id)
    if mode == "adaptive":
        return 64000
    if mode == "budget":
        return 32000
    return 8192


def parametres_reflexion(model_id: str, niveau: str | None) -> dict[str, Any]:
    """Paramètres `thinking` / `output_config` à envoyer (dict vide si aucun)."""
    if not niveau:
        return {}
    mode = mode_reflexion(model_id)
    if mode == "adaptive":
        return {"thinking": {"type": "adaptive", "display": "summarized"},
                "output_config": {"effort": niveau}}
    if mode == "budget":
        return {"thinking": {"type": "enabled", "budget_tokens": BUDGETS.get(niveau, 8192)}}
    return {}


def _bloc_param(bloc: Any) -> dict[str, Any] | None:
    """Bloc de réponse → bloc de requête équivalent (rejoué tel quel)."""
    t = getattr(bloc, "type", None)
    if t == "thinking":
        return {"type": "thinking", "thinking": bloc.thinking, "signature": bloc.signature}
    if t == "redacted_thinking":
        return {"type": "redacted_thinking", "data": bloc.data}
    if t == "text":
        return {"type": "text", "text": bloc.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": bloc.id, "name": bloc.name, "input": bloc.input}
    return None


def construire_messages(requete: RequeteLLM) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    def ajouter(role: str, blocs: list[dict[str, Any]]) -> None:
        if not blocs:
            return
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocs)
        else:
            messages.append({"role": role, "content": blocs})

    for item in normaliser_historique(requete.historique):
        if item["role"] == "user":
            ajouter("user", [{"type": "text", "text": item["content"] or "…"}])
        elif item["role"] == "assistant":
            brut = item.get("brut") or {}
            if brut.get("format") == "anthropic" and brut.get("model") == requete.model \
                    and brut.get("content"):
                blocs = [dict(b) for b in brut["content"]]
            else:
                blocs = []
                if item.get("content"):
                    blocs.append({"type": "text", "text": item["content"]})
                for c in item.get("tool_calls") or []:
                    blocs.append({"type": "tool_use", "id": c["id"], "name": c["name"],
                                  "input": c["arguments"]})
            ajouter("assistant", blocs)
        elif item["role"] == "tool":
            ajouter("user", [{"type": "tool_result", "tool_use_id": r["call_id"],
                              "content": r["content"], "is_error": bool(r.get("is_error"))}
                             for r in item["results"]])
    # Les tool_result doivent précéder le texte dans un message utilisateur fusionné.
    for m in messages:
        if m["role"] == "user":
            m["content"].sort(key=lambda b: 0 if b["type"] == "tool_result" else 1)
    return messages


def construire_parametres(requete: RequeteLLM) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model": requete.model,
        "max_tokens": max_tokens_pour(requete.model),
        "system": [{"type": "text", "text": requete.system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": construire_messages(requete),
        "cache_control": {"type": "ephemeral"},
    }
    if requete.outils:
        outils = [{"name": o.name, "description": o.description, "input_schema": o.parameters}
                  for o in requete.outils]
        outils[-1]["cache_control"] = {"type": "ephemeral"}
        params["tools"] = outils
    params.update(parametres_reflexion(requete.model, requete.niveau_reflexion))
    return params


def _erreur(e: Exception, requete: RequeteLLM | None = None) -> ErreurFournisseur:
    if isinstance(e, anthropic.APIStatusError):
        msg = getattr(e, "message", None) or str(e)
        if (requete is not None and requete.niveau_reflexion and e.status_code == 400
                and re.search(r"thinking|effort|budget", msg, re.I)):
            return ErreurFournisseur(
                f"Anthropic a refusé le réglage de réflexion ({requete.niveau_reflexion!r}) "
                f"pour {requete.model} : {msg}", 400)
        return ErreurFournisseur(f"Anthropic a répondu {e.status_code} : {msg}", e.status_code)
    if isinstance(e, anthropic.APIConnectionError):
        return ErreurFournisseur(f"Anthropic injoignable : {e}")
    return ErreurFournisseur(f"Erreur Anthropic : {e}")


class AdaptateurAnthropic:
    def __init__(self, base_url: str | None, api_key: str | None,
                 http_client: Any | None = None):
        self.base_url = normaliser_base_url(base_url)
        kwargs: dict[str, Any] = {"api_key": api_key or None, "base_url": self.base_url}
        if http_client is not None:
            kwargs["http_client"] = http_client  # doit venir de httpx2 (DefaultAsyncHttpxClient)
        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def lister_modeles(self) -> list[dict[str, Any]]:
        sortie = []
        try:
            async for m in self.client.models.list():
                sortie.append({
                    "id": m.id,
                    "owned_by": "anthropic",
                    "label": getattr(m, "display_name", None),
                    "context_length": getattr(m, "max_input_tokens", None),
                    "thinking": reflexion_depuis_capacites(m.id, getattr(m, "capabilities", None)),
                })
        except anthropic.AnthropicError as e:
            raise _erreur(e) from e
        return sortie

    async def flux(self, requete: RequeteLLM) -> AsyncIterator[Evenement]:
        params = construire_parametres(requete)
        try:
            async with self.client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        d = event.delta
                        if d.type == "thinking_delta" and d.thinking:
                            yield ThinkingDelta(d.thinking)
                        elif d.type == "text_delta" and d.text:
                            yield TextDelta(d.text)
                final = await stream.get_final_message()
        except anthropic.AnthropicError as e:
            raise _erreur(e, requete) from e

        for bloc in final.content:
            if bloc.type == "tool_use":
                args = bloc.input if isinstance(bloc.input, dict) else {}
                erreur = None if isinstance(bloc.input, dict) else "arguments non objet"
                yield ToolCall(id=bloc.id, name=bloc.name, arguments=args,
                               erreur_arguments=erreur)
        u = final.usage
        usage = Usage(
            input_tokens=(u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
            + (getattr(u, "cache_read_input_tokens", 0) or 0),
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        )
        contenu = [b for b in (_bloc_param(x) for x in final.content) if b is not None]
        yield Fin(usage=usage, stop_reason=final.stop_reason,
                  brut={"format": "anthropic", "model": requete.model, "content": contenu})
