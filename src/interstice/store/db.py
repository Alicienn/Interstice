"""Connexion à la base du corpus."""

from __future__ import annotations

import sqlite3
from importlib.resources import files
from pathlib import Path

from interstice.config import DB_PATH


def connect(path: Path | str = DB_PATH, *, lecture_seule: bool = False) -> sqlite3.Connection:
    path = Path(path)
    if lecture_seule:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.isolation_level = None  # transactions explicites (BEGIN/COMMIT) uniquement
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA cache_size = -200000")  # ~200 Mo
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(files("interstice.store").joinpath("schema.sql").read_text("utf-8"))


def meta_get(conn: sqlite3.Connection, cle: str) -> str | None:
    row = conn.execute("SELECT valeur FROM meta WHERE cle = ?", (cle,)).fetchone()
    return row[0] if row else None


def meta_set(conn: sqlite3.Connection, cle: str, valeur: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(cle, valeur) VALUES (?, ?)", (cle, valeur))
