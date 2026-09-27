"""Interface commune des outils de navigation.

Un même registre alimente le serveur MCP et l'agent de l'application web.
Chaque outil renvoie un `Resultat` :
- `texte` : ce que lit le LLM (markdown compact, identifiants explicites) ;
- `documents` : références affichées dans le chat sous forme de cartes cliquables.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal

DocKind = Literal["article", "section", "texte", "recherche", "bofip"]


@dataclass
class DocRef:
    kind: DocKind
    id: str  # LEGIARTI (version), LEGISCTA, LEGITEXT (cid) ; pour « recherche » : la requête
    titre: str  # ex. « CGI, art. 150-0 B ter »
    sous_titre: str = ""  # ex. fil d'Ariane abrégé ou état de la version
    date: str | None = None  # date de consultation (AAAA-MM-JJ)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Resultat:
    texte: str
    documents: list[DocRef] = field(default_factory=list)
    erreur: bool = False


@dataclass
class Outil:
    nom: str
    description: str
    parametres: dict[str, Any]  # JSON Schema (type=object)
    fn: Callable[..., Resultat]  # fn(conn, **arguments) -> Resultat

    def schema_openai(self) -> dict[str, Any]:
        return {"type": "function",
                "function": {"name": self.nom, "description": self.description,
                             "parameters": self.parametres}}

    def appeler(self, conn: sqlite3.Connection, arguments: dict[str, Any]) -> Resultat:
        try:
            return self.fn(conn, **arguments)
        except (TypeError, ValueError, LookupError) as e:
            return Resultat(texte=f"Erreur : {e}", erreur=True)
