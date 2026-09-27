"""Accès en lecture seule au corpus juridique (`config.DB_PATH`)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from interstice import config


class CorpusIndisponible(Exception):
    pass


def ouvrir_corpus(chemin: Path | str | None = None) -> sqlite3.Connection:
    """Connexion SQLite en lecture seule (mode=ro). Lève CorpusIndisponible si absent."""
    p = Path(chemin) if chemin is not None else config.DB_PATH
    if not p.exists():
        raise CorpusIndisponible(f"corpus introuvable : {p} (lancez l'ingestion)")
    conn = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def etat_corpus(chemin: Path | str | None = None) -> dict[str, Any]:
    """`{articles, derniere_ingestion}` au mieux de ce que le schéma expose.

    Point d'extension : si le module d'ingestion fournit
    `interstice.outils.vues.etat_corpus(conn) -> dict`, il est utilisé en priorité.
    """
    vide = {"articles": 0, "derniere_ingestion": None}
    try:
        conn = ouvrir_corpus(chemin)
    except (CorpusIndisponible, sqlite3.Error):
        return vide
    try:
        from interstice.outils import vues

        f = getattr(vues, "etat_corpus", None)
        if callable(f):
            try:
                d = f(conn)
                return {"articles": int(d.get("articles") or 0),
                        "derniere_ingestion": d.get("derniere_ingestion")}
            except NotImplementedError:
                pass
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        articles = 0
        for t in ("articles", "article", "article_versions", "articles_versions"):
            if t in tables:
                articles = conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
                break
        derniere = None
        for t in ("ingestions", "ingestion", "journal_ingestion", "archives"):
            if t not in tables:
                continue
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
            for c in ("termine_le", "fin", "date_fin", "ingere_le", "date", "created_at"):
                if c in cols:
                    derniere = conn.execute(f'SELECT max("{c}") FROM "{t}"').fetchone()[0]
                    break
            if derniere:
                break
        return {"articles": int(articles), "derniere_ingestion": derniere}
    except sqlite3.Error:
        return vide
    finally:
        conn.close()
