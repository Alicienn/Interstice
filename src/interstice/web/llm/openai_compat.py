"""Adaptateur « openai » : toute API compatible Chat Completions (httpx, flux SSE).

Réflexion :
- en sortie : `delta.reasoning_content` (DeepSeek, vLLM) ou `delta.reasoning` (OpenRouter) ;
- en entrée : `reasoning_effort` (OpenAI et compatibles), `reasoning: {effort}` pour OpenRouter.
Un refus (400) lié au paramètre de réflexion remonte en erreur claire, sans nouvel essai.
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

import httpx

from interstice.web.llm.base import (
    NIVEAUX_STANDARD,
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

# Identifiants de modèles « à raisonnement » connus (heuristique, faute d'information de l'API).
_MOTIFS_REFLEXION = [
    r"^o[134](?:$|[-_.])",       # o1, o3, o4-mini…
    r"^gpt-5",                   # gpt-5, gpt-5-mini…
    r"reasoner",                 # deepseek-reasoner
    r"thinking",                 # *-thinking
    r"qwq",
    r"(?:^|[-_/.])r1(?:$|[-_.:])",  # deepseek-r1, r1-distill…
    r"magistral",
    r"^grok-(?:3-mini|4)",
    r"^qwen3",
    r"^gemini-(?:2\.5|3)",
]

_CLES_CONTEXTE = ("context_length", "context_window", "max_model_len", "max_context_length")


def est_openrouter(base_url: str) -> bool:
    return "openrouter.ai" in base_url.lower()


def detecter_reflexion(modele: dict[str, Any]) -> dict[str, Any]:
    """ThinkingSupport d'un modèle renvoyé par `GET /models`."""
    params = modele.get("supported_parameters")
    if isinstance(params, list):
        ok = "reasoning" in params or "include_reasoning" in params
        return thinking_support(ok, NIVEAUX_STANDARD, "api")
    ident = str(modele.get("id", "")).lower()
    court = ident.rsplit("/", 1)[-1]
    for motif in _MOTIFS_REFLEXION:
        if re.search(motif, court):
            return thinking_support(True, NIVEAUX_STANDARD, "heuristique")
    return thinking_support(False, [], "heuristique")


def _contexte(modele: dict[str, Any]) -> int | None:
    for cle in _CLES_CONTEXTE:
        v = modele.get(cle)
        if isinstance(v, int) and v > 0:
            return v
    top = modele.get("top_provider")
    if isinstance(top, dict) and isinstance(top.get("context_length"), int):
        return top["context_length"]
    return None


class AccumulateurToolCalls:
    """Reconstitue les appels d'outils fragmentés de `delta.tool_calls`."""

    def __init__(self) -> None:
        self._appels: dict[int, dict[str, str]] = {}
        self._dernier: int | None = None

    def ajouter(self, fragments: list[dict[str, Any]]) -> None:
        for frag in fragments:
            idx = frag.get("index")
            fid = frag.get("id") or ""
            if not isinstance(idx, int):
                # Certains fournisseurs omettent `index` : nouvel appel si nouvel id.
                connus = {a["id"] for a in self._appels.values()}
                if fid and fid not in connus:
                    idx = len(self._appels)
                elif self._dernier is not None:
                    idx = self._dernier
                else:
                    idx = 0
            a = self._appels.setdefault(idx, {"id": "", "name": "", "arguments": ""})
            self._dernier = idx
            if fid and not a["id"]:
                a["id"] = fid
            fn = frag.get("function") or {}
            nom = fn.get("name")
            if nom:
                if not a["name"]:
                    a["name"] = nom
                elif nom != a["name"]:
                    a["name"] += nom
            args = fn.get("arguments")
            if args:
                if isinstance(args, dict):  # certains serveurs envoient déjà un objet
                    args = json.dumps(args, ensure_ascii=False)
                a["arguments"] += args

    def terminer(self) -> list[ToolCall]:
        sortie = []
        for i, idx in enumerate(sorted(self._appels)):
            a = self._appels[idx]
            brut = a["arguments"].strip()
            erreur = None
            try:
                args = json.loads(brut) if brut else {}
                if not isinstance(args, dict):
                    erreur, args = f"arguments non objet : {brut[:200]}", {}
            except json.JSONDecodeError as e:
                erreur, args = f"arguments JSON invalides ({e.msg}) : {brut[:200]}", {}
            sortie.append(ToolCall(id=a["id"] or f"call_{i}", name=a["name"], arguments=args,
                                   erreur_arguments=erreur))
        return sortie


def _message_erreur(corps: str) -> str:
    try:
        d = json.loads(corps)
    except (json.JSONDecodeError, ValueError):
        return corps.strip()[:500] or "réponse vide"
    err = d.get("error", d) if isinstance(d, dict) else d
    if isinstance(err, dict):
        return str(err.get("message") or err.get("detail") or err)[:500]
    return str(err)[:500]


class AdaptateurOpenAI:
    def __init__(self, base_url: str, api_key: str | None,
                 transport: httpx.AsyncBaseTransport | None = None,
                 timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self._transport = transport
        self._timeout = timeout

    # Mémorise (par processus) les bases qui refusent `stream_options`.
    _sans_stream_options: set[str] = set()

    def _client(self) -> httpx.AsyncClient:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.AsyncClient(headers=headers, transport=self._transport,
                                 timeout=httpx.Timeout(self._timeout, connect=15.0))

    async def lister_modeles(self) -> list[dict[str, Any]]:
        try:
            async with self._client() as c:
                r = await c.get(f"{self.base_url}/models")
        except httpx.HTTPError as e:
            raise ErreurFournisseur(f"Fournisseur injoignable ({self.base_url}) : {e}") from e
        if r.status_code >= 400:
            raise ErreurFournisseur(
                f"GET /models a répondu {r.status_code} : {_message_erreur(r.text)}", r.status_code)
        try:
            d = r.json()
        except ValueError as e:
            raise ErreurFournisseur("Réponse de /models illisible (JSON attendu).") from e
        items = d.get("data", d.get("models", [])) if isinstance(d, dict) else d
        if not isinstance(items, list):
            raise ErreurFournisseur("Réponse de /models inattendue (liste attendue).")
        sortie = []
        for m in items:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            sortie.append({"id": str(m["id"]), "owned_by": m.get("owned_by"),
                           "context_length": _contexte(m), "thinking": detecter_reflexion(m)})
        sortie.sort(key=lambda m: m["id"])
        return sortie

    # ---- conversion de l'historique -------------------------------------------------------

    def messages(self, requete: RequeteLLM) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = [{"role": "system", "content": requete.system}]
        for item in normaliser_historique(requete.historique):
            if item["role"] == "user":
                msgs.append({"role": "user", "content": item["content"]})
            elif item["role"] == "assistant":
                m: dict[str, Any] = {"role": "assistant", "content": item.get("content") or None}
                if item.get("tool_calls"):
                    m["tool_calls"] = [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"],
                                      "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                        for c in item["tool_calls"]]
                msgs.append(m)
            elif item["role"] == "tool":
                for r in item["results"]:
                    msgs.append({"role": "tool", "tool_call_id": r["call_id"],
                                 "content": r["content"]})
        return msgs

    def corps(self, requete: RequeteLLM, stream_options: bool = True) -> dict[str, Any]:
        corps: dict[str, Any] = {"model": requete.model, "messages": self.messages(requete),
                                 "stream": True}
        if stream_options:
            corps["stream_options"] = {"include_usage": True}
        if requete.outils:
            corps["tools"] = [{"type": "function",
                               "function": {"name": o.name, "description": o.description,
                                            "parameters": o.parameters}}
                              for o in requete.outils]
        if requete.niveau_reflexion:
            if est_openrouter(self.base_url):
                corps["reasoning"] = {"effort": requete.niveau_reflexion}
            else:
                corps["reasoning_effort"] = requete.niveau_reflexion
        return corps

    # ---- flux -----------------------------------------------------------------------------

    async def flux(self, requete: RequeteLLM) -> AsyncIterator[Evenement]:
        avec_options = self.base_url not in self._sans_stream_options
        async with self._client() as c:
            for tentative in (1, 2):
                corps = self.corps(requete, stream_options=avec_options)
                try:
                    async with c.stream("POST", f"{self.base_url}/chat/completions",
                                        json=corps) as r:
                        if r.status_code >= 400:
                            texte = (await r.aread()).decode("utf-8", "replace")
                            msg = _message_erreur(texte)
                            if (r.status_code in (400, 422) and avec_options and tentative == 1
                                    and "stream_options" in texte):
                                # Le fournisseur n'accepte pas stream_options : on s'en passe.
                                self._sans_stream_options.add(self.base_url)
                                avec_options = False
                                continue
                            if r.status_code in (400, 422) and requete.niveau_reflexion:
                                param = ("reasoning.effort" if est_openrouter(self.base_url)
                                         else "reasoning_effort")
                                raise ErreurFournisseur(
                                    f"Le fournisseur a refusé la requête ({r.status_code}) alors "
                                    f"que la réflexion était demandée ({param}="
                                    f"{requete.niveau_reflexion!r}) ; ce modèle ne prend "
                                    f"probablement pas en charge ce réglage. Choisissez « sans "
                                    f"réflexion » ou un autre niveau. Détail : {msg}",
                                    r.status_code)
                            raise ErreurFournisseur(
                                f"Le fournisseur a répondu {r.status_code} : {msg}", r.status_code)
                        async for ev in self._lire_flux(r.aiter_lines()):
                            yield ev
                        return
                except httpx.HTTPError as e:
                    raise ErreurFournisseur(f"Erreur réseau avec le fournisseur : {e}") from e

    async def _lire_flux(self, lignes: AsyncIterator[str]) -> AsyncIterator[Evenement]:
        async for ev in lire_flux_sse(lignes):
            yield ev


async def lire_flux_sse(lignes: AsyncIterator[str]) -> AsyncIterator[Evenement]:
    """Transforme les lignes SSE brutes de /chat/completions en événements normalisés."""
    acc = AccumulateurToolCalls()
    usage = Usage()
    stop_reason: str | None = None
    tampon: list[str] = []

    def traiter(donnees: str) -> list[Evenement]:
        nonlocal stop_reason, usage
        try:
            chunk = json.loads(donnees)
        except json.JSONDecodeError:
            return []
        if not isinstance(chunk, dict):
            return []
        if chunk.get("error"):
            raise ErreurFournisseur(
                f"Erreur du fournisseur en cours de flux : {_message_erreur(json.dumps(chunk))}")
        evs: list[Evenement] = []
        u = chunk.get("usage")
        if isinstance(u, dict):
            details = u.get("prompt_tokens_details") or {}
            usage = Usage(input_tokens=int(u.get("prompt_tokens") or 0),
                          output_tokens=int(u.get("completion_tokens") or 0),
                          cache_read_tokens=int(details.get("cached_tokens") or 0)
                          if isinstance(details, dict) else 0)
        for choix in chunk.get("choices") or []:
            delta = choix.get("delta") or {}
            reflexion = delta.get("reasoning_content")
            if not isinstance(reflexion, str) or not reflexion:
                reflexion = delta.get("reasoning")
            if isinstance(reflexion, str) and reflexion:
                evs.append(ThinkingDelta(reflexion))
            texte = delta.get("content")
            if isinstance(texte, str) and texte:
                evs.append(TextDelta(texte))
            if delta.get("tool_calls"):
                acc.ajouter(delta["tool_calls"])
            if choix.get("finish_reason"):
                stop_reason = choix["finish_reason"]
        return evs

    termine = False
    async for ligne in lignes:
        ligne = ligne.rstrip("\r")
        if not ligne:
            if tampon:
                donnees = "\n".join(tampon)
                tampon = []
                if donnees.strip() == "[DONE]":
                    termine = True
                    break
                for ev in traiter(donnees):
                    yield ev
            continue
        if ligne.startswith(":"):
            continue  # commentaire / keep-alive (ex. « : OPENROUTER PROCESSING »)
        if ligne.startswith("data:"):
            tampon.append(ligne[5:].lstrip(" "))
    if not termine and tampon:
        donnees = "\n".join(tampon)
        if donnees.strip() != "[DONE]":
            for ev in traiter(donnees):
                yield ev

    appels = acc.terminer()
    for appel in appels:
        yield appel
    correspondance = {"stop": "end_turn", "tool_calls": "tool_use", "function_call": "tool_use",
                      "length": "max_tokens", "content_filter": "refusal"}
    raison = correspondance.get(stop_reason or "", stop_reason)
    if appels and raison in (None, "end_turn"):
        raison = "tool_use"
    yield Fin(usage=usage, stop_reason=raison or "end_turn", brut=None)
