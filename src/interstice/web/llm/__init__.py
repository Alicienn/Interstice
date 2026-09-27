"""Adaptateurs LLM (flux d'événements normalisés) et fabrique par type de fournisseur."""

from __future__ import annotations

from typing import Any

from interstice.web.llm.base import (
    Adaptateur,
    ErreurFournisseur,
    Evenement,
    Fin,
    OutilSpec,
    RequeteLLM,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
)

TYPES_FOURNISSEUR = ("openai", "anthropic")


def creer_adaptateur(fournisseur: dict[str, Any]) -> Adaptateur:
    """Fabrique par défaut. `fournisseur` : ligne du stockage (avec `api_key`)."""
    t = fournisseur["type"]
    if t == "openai":
        from interstice.web.llm.openai_compat import AdaptateurOpenAI

        return AdaptateurOpenAI(fournisseur["base_url"], fournisseur.get("api_key"))
    if t == "anthropic":
        from interstice.web.llm.anthropic_natif import AdaptateurAnthropic

        return AdaptateurAnthropic(fournisseur["base_url"], fournisseur.get("api_key"))
    raise ErreurFournisseur(f"type de fournisseur inconnu : {t}")


__all__ = ["Adaptateur", "ErreurFournisseur", "Evenement", "Fin", "OutilSpec", "RequeteLLM",
           "TextDelta", "ThinkingDelta", "ToolCall", "Usage", "TYPES_FOURNISSEUR",
           "creer_adaptateur"]
