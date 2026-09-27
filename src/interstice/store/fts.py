"""Index plein texte (SQLite FTS5) sur les articles.

Index à contenu externe (`content='articles'`) : il ne duplique pas le texte. Comme
l'ingestion remplace des lignes (INSERT OR REPLACE change le rowid), l'index est
reconstruit entièrement après chaque ingestion.
"""

from __future__ import annotations

import sqlite3
import time


def reconstruire_fts(conn: sqlite3.Connection) -> float:
    t0 = time.time()
    conn.execute("DROP TABLE IF EXISTS articles_fts")
    conn.execute(
        """CREATE VIRTUAL TABLE articles_fts USING fts5(
               num, texte, content='articles', content_rowid='rowid',
               tokenize="unicode61 remove_diacritics 2")""")
    conn.execute("INSERT INTO articles_fts(articles_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO articles_fts(articles_fts) VALUES ('optimize')")
    conn.commit()
    return time.time() - t0
