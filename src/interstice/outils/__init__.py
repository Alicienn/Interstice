"""Registre des outils de navigation (partagé MCP / application web)."""

from __future__ import annotations

from interstice.outils.base import DocRef, Outil, Resultat

# Rempli par interstice.outils.legi (import en bas de fichier pour éviter les cycles).
OUTILS: list[Outil] = []


def get_outil(nom: str) -> Outil:
    for o in OUTILS:
        if o.nom == nom:
            return o
    raise LookupError(f"outil inconnu : {nom}")


__all__ = ["DocRef", "Outil", "Resultat", "OUTILS", "get_outil"]

from interstice.outils.bofip import OUTILS_BOFIP  # noqa: E402
from interstice.outils.legi import OUTILS_LEGI  # noqa: E402

OUTILS.extend(OUTILS_LEGI)
OUTILS.extend(OUTILS_BOFIP)
