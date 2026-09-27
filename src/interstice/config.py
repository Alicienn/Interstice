"""Chemins et constantes du projet."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("INTERSTICE_DATA", ROOT / "data"))
RAW = DATA / "raw"
DB_PATH = Path(os.environ.get("INTERSTICE_DB", DATA / "interstice.sqlite"))

DILA_OPENDATA = "https://echanges.dila.gouv.fr/OPENDATA"
BOFIP_OPENDATA = "https://bofip.impots.gouv.fr/opendata"

# Textes du périmètre fiscal. L'ingestion LEGI couvre tout le fonds ; ce
# dictionnaire sert seulement à marquer le périmètre par défaut des outils.
# Les identifiants sont vérifiés par l'audit (titre attendu dans LEGITEXT).
CODES_FISCAUX: dict[str, str] = {
    "LEGITEXT000006069577": "CGI",
    "LEGITEXT000006069568": "CGI-AI",
    "LEGITEXT000006069569": "CGI-AII",
    "LEGITEXT000006069574": "CGI-AIII",
    "LEGITEXT000006069576": "CGI-AIV",
    "LEGITEXT000006069583": "LPF",
    "LEGITEXT000044595989": "CIBS",
    "LEGITEXT000006071570": "CDOUANES",
}
