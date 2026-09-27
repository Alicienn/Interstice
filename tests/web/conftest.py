"""Fixtures des tests du backend web."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from interstice.web.app import create_app
from interstice.web.stockage import Stockage
from outillage_web import FAUX_OUTILS, FauxAdaptateur


@pytest.fixture
def corpus(tmp_path):
    chemin = tmp_path / "corpus.sqlite"
    conn = sqlite3.connect(chemin)
    conn.execute("CREATE TABLE articles (id TEXT PRIMARY KEY)")
    conn.executemany("INSERT INTO articles VALUES (?)", [("A1",), ("A2",), ("A3",)])
    conn.execute("CREATE TABLE ingestion (archive TEXT, fin TEXT)")
    conn.execute("INSERT INTO ingestion VALUES ('LEGI_x.tar.gz', '2026-09-27T10:00:00')")
    conn.commit()
    conn.close()
    return chemin


@pytest.fixture
def stockage(tmp_path):
    st = Stockage(tmp_path / "app.sqlite")
    yield st
    st.fermer()


@pytest.fixture
def faux():
    """Adaptateur partagé : les tests y ajoutent leurs tours avant d'appeler l'API."""
    return FauxAdaptateur()


@pytest.fixture
def client(stockage, faux, corpus, tmp_path):
    app = create_app(stockage=stockage, outils=FAUX_OUTILS,
                     fabrique_adaptateur=lambda f: faux, chemin_corpus=corpus,
                     dist=tmp_path / "pas_de_dist")
    with TestClient(app) as c:
        yield c


