"""Interface commune des adaptateurs LLM.

Chaque adaptateur transforme un `RequeteLLM` (historique neutre + outils + niveau de réflexion)
en un flux d'événements normalisés :

- `ThinkingDelta(text)` : fragment de réflexion affichable ;
- `TextDelta(text)` : fragment de réponse ;
- `ToolCall(id, name, arguments)` : appel d'outil COMPLET (arguments JSON déjà parsés) ;
- `Fin(usage, stop_reason, brut)` : fin du tour, toujours émis en dernier.

Historique neutre (liste de dicts, sérialisable en JSON, persisté dans `messages.trace`) :

- `{"role": "user", "content": str}`
- `{"role": "assistant", "content": str, "tool_calls": [{"id", "name", "arguments"}],
   "brut": dict | None}`  ; `brut` = contenu propre au fournisseur (ex. blocs de réflexion
   Anthropic signés) que l'adaptateur peut rejouer tel quel s'il en reconnaît le format ;
- `{"role": "tool", "results": [{"call_id", "name", "content", "is_error"}]}`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, Union

NIVEAUX_STANDARD = ["low", "medium", "high"]


class ErreurFournisseur(Exception):
    """Erreur renvoyée (ou provoquée) par le fournisseur de modèles."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class ThinkingDelta:
    text: str


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Renseigné si les arguments reçus n'étaient pas un objet JSON valide.
    erreur_arguments: str | None = None


@dataclass
class Usage:
    input_tokens: int = 0  # total des jetons d'entrée (y compris lus / écrits en cache)
    output_tokens: int = 0
    cache_read_tokens: int = 0

    def ajouter(self, autre: "Usage") -> None:
        self.input_tokens += autre.input_tokens
        self.output_tokens += autre.output_tokens
        self.cache_read_tokens += autre.cache_read_tokens

    def to_dict(self) -> dict[str, int]:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cache_read_tokens": self.cache_read_tokens}


@dataclass
class Fin:
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None  # "end_turn" | "tool_use" | "max_tokens" | "refusal" | …
    brut: dict[str, Any] | None = None


Evenement = Union[ThinkingDelta, TextDelta, ToolCall, Fin]


@dataclass
class OutilSpec:
    """Description d'un outil telle qu'envoyée au modèle."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class RequeteLLM:
    model: str
    system: str
    historique: list[dict[str, Any]]
    outils: list[OutilSpec] = field(default_factory=list)
    niveau_reflexion: str | None = None


class Adaptateur(Protocol):
    async def lister_modeles(self) -> list[dict[str, Any]]:
        """Modèles distants : `[{id, owned_by, context_length, thinking}]` (forme ModeleDistant
        sans `enabled`). Lève ErreurFournisseur."""
        ...

    def flux(self, requete: RequeteLLM) -> AsyncIterator[Evenement]:
        """Générateur asynchrone d'événements ; lève ErreurFournisseur."""
        ...


def thinking_support(supported: bool, levels: list[str] | None = None,
                     source: str = "heuristique") -> dict[str, Any]:
    return {"supported": supported, "levels": list(levels or []) if supported else [],
            "source": source}


def normaliser_historique(historique: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rend un historique acceptable par tous les fournisseurs.

    - chaque appel d'outil d'un message assistant reçoit un résultat (synthétique si absent,
      ex. génération interrompue) ;
    - les messages assistant vides (ni texte ni appel d'outil) sont retirés ;
    - les résultats orphelins sont retirés ;
    - l'historique commence par un message utilisateur.
    """
    sortie: list[dict[str, Any]] = []
    en_attente: list[dict[str, Any]] = []  # appels sans résultat

    def solder() -> None:
        if en_attente:
            sortie.append({"role": "tool", "results": [
                {"call_id": c["id"], "name": c["name"],
                 "content": "Appel interrompu : aucun résultat.", "is_error": True}
                for c in en_attente]})
            en_attente.clear()

    for item in historique:
        role = item.get("role")
        if role == "assistant":
            solder()
            calls = item.get("tool_calls") or []
            if not (item.get("content") or calls):
                continue
            sortie.append(item)
            en_attente.extend(calls)
        elif role == "tool":
            ids = {c["id"] for c in en_attente}
            res = [r for r in item.get("results") or [] if r.get("call_id") in ids]
            if not res:
                continue
            recus = {r["call_id"] for r in res}
            manquants = [c for c in en_attente if c["id"] not in recus]
            res = res + [{"call_id": c["id"], "name": c["name"],
                          "content": "Appel interrompu : aucun résultat.", "is_error": True}
                         for c in manquants]
            en_attente.clear()
            sortie.append({"role": "tool", "results": res})
        elif role == "user":
            solder()
            sortie.append(item)
    solder()
    while sortie and sortie[0].get("role") != "user":
        sortie.pop(0)
    return sortie
