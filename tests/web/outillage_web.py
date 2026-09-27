"""Outillage des tests web : faux adaptateur LLM scripté, faux outils, lecture SSE."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import Any

from interstice.outils.base import DocRef, Outil, Resultat
from interstice.web.llm.base import ErreurFournisseur, RequeteLLM


class FauxAdaptateur:
    """Rejoue des tours scriptés : chaque tour est une liste d'événements (ou une exception)."""

    def __init__(self, tours: list[list[Any]] | None = None,
                 modeles: list[dict[str, Any]] | None = None,
                 erreur_modeles: str | None = None):
        self.tours = list(tours or [])
        self.modeles = modeles or []
        self.erreur_modeles = erreur_modeles
        self.requetes: list[RequeteLLM] = []
        self.delai = 0.0  # pause avant chaque événement (simule un modèle qui rédige lentement)

    async def lister_modeles(self) -> list[dict[str, Any]]:
        if self.erreur_modeles:
            raise ErreurFournisseur(self.erreur_modeles, 401)
        return self.modeles

    async def flux(self, requete: RequeteLLM):
        # copie profonde : l'historique est muté par la boucle agent après l'appel
        self.requetes.append(RequeteLLM(**{**requete.__dict__,
                                           "historique": json.loads(json.dumps(requete.historique))}))
        for ev in self.tours.pop(0):
            if self.delai:
                await asyncio.sleep(self.delai)
            if isinstance(ev, Exception):
                raise ev
            yield ev


def _sommaire(conn: sqlite3.Connection, texte: str, date: str | None = None) -> Resultat:
    if texte == "INCONNU":
        raise LookupError("texte inconnu")
    return Resultat(
        texte=f"# Sommaire de {texte}\n- Livre premier (LEGISCTA000006083735)",
        documents=[DocRef(kind="texte", id="LEGITEXT000006069577", titre="Code général des impôts",
                          sous_titre="Sommaire", date=date)])


def _lire_article(conn: sqlite3.Connection, id: str) -> Resultat:
    return Resultat(texte=f"## CGI, art. 200 A ({id})\nTexte de l'article.",
                    documents=[DocRef(kind="article", id=id, titre="CGI, art. 200 A",
                                      sous_titre="En vigueur", date="2026-09-27")])


FAUX_OUTILS = [
    Outil("sommaire", "Plan d'un texte ou d'une section.",
          {"type": "object", "properties": {"texte": {"type": "string"},
                                            "date": {"type": "string"}},
           "required": ["texte"]}, _sommaire),
    Outil("lire_article", "Texte d'un article.",
          {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
          _lire_article),
]


def lire_sse(texte: str) -> list[tuple[str, dict[str, Any]]]:
    evenements = []
    for bloc in texte.replace("\r\n", "\n").split("\n\n"):
        if not bloc.strip():
            continue
        nom, donnees = None, []
        for ligne in bloc.split("\n"):
            if ligne.startswith("event:"):
                nom = ligne[6:].strip()
            elif ligne.startswith("data:"):
                donnees.append(ligne[5:].strip())
        evenements.append((nom, json.loads("\n".join(donnees))))
    return evenements
