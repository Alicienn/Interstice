"""Vues détaillées pour le panneau de lecture (routes /api/documents/*).

Formes de retour : voir docs/contrat-api.md §3 (VueArticle, VueNoeud, LigneRecherche).
Chaque fonction lève LookupError si l'objet n'existe pas.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def vue_article(conn: sqlite3.Connection, id: str, date: str | None = None) -> dict[str, Any]:
    raise NotImplementedError


def vue_section(conn: sqlite3.Connection, id: str, date: str | None = None) -> dict[str, Any]:
    raise NotImplementedError


def vue_texte(conn: sqlite3.Connection, cid: str, date: str | None = None) -> dict[str, Any]:
    raise NotImplementedError


def recherche(conn: sqlite3.Connection, q: str, texte: str | None = None,
              date: str | None = None, limite: int = 20) -> list[dict[str, Any]]:
    raise NotImplementedError


def lister_textes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    raise NotImplementedError
