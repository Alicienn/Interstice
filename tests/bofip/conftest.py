"""Fixtures pytest du corpus BOFiP (voir outillage_bofip pour la description des données)."""

from __future__ import annotations

from pathlib import Path

import pytest
from outillage_bofip import actualites_gz, membres_flux, membres_stock, tar_depuis


@pytest.fixture()
def base_vide(tmp_path):
    from interstice.bofip.ingest import init_schema_bofip
    from interstice.store.db import connect

    conn = connect(tmp_path / "bofip.sqlite")
    init_schema_bofip(conn)
    return conn


@pytest.fixture()
def archives(tmp_path) -> dict[str, Path]:
    d = tmp_path / "raw"
    d.mkdir()
    return {
        "stock": tar_depuis(d / "bofip_stock_live_20260923.tgz", membres_stock()),
        "flux": tar_depuis(d / "bofip_flux_live_20261001_20261007.tgz", membres_flux("2026-10-01")),
        "actu": actualites_gz(d / "bofip_vigueur_actualites_20260917.json.gz"),
    }


@pytest.fixture()
def base_bofip(base_vide, archives):
    """Stock + actualités ingérés (sans flux), plan, renvois et FTS construits."""
    from interstice.bofip.ingest import ingerer_chaine

    ingerer_chaine(base_vide, [archives["stock"], archives["actu"]], verbeux=False)
    return base_vide
