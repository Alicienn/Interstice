"""Fixtures BOFiP : extrait réel du stock du 23/09/2026 (8 contenus, 1 image, 1 pièce jointe, plan réduit
aux nœuds de ces documents) et deux actualités réelles du jeu bofip-vigueur.

Le flux de test est dérivé d'un document réel (12038-PGP, BOI-RPPM-PVBMI-30-10-60-10) republié à une date
ultérieure avec un paragraphe ajouté : l'open data ne fournit que la version en cours de chaque document,
on ne dispose donc pas de deux versions réelles d'un même BOI.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
STOCK = FIX / "stock"
DOC_12038 = STOCK / "BOFiP/documents/Contenu/Commentaire/RPPM/12038-PGP/2026-08-10"
PLAN = STOCK / "BOFiP/documents/PlanClassement/8-PGP/2026-09-23"
AJOUT = "Précision nouvelle : le plafond de la soulte est apprécié opération par opération."


def tar_depuis(path: Path, membres: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        dossiers = set()
        for nom in membres:
            parts = nom.split("/")
            for i in range(1, len(parts)):
                dossiers.add("/".join(parts[:i]))
        for d in sorted(dossiers):  # comme les archives DGFiP : répertoires listés avant leurs fichiers
            info = tarfile.TarInfo(d)
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        for nom, data in membres.items():
            info = tarfile.TarInfo(nom)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def membres_stock(exclure: tuple[str, ...] = ()) -> dict[str, bytes]:
    out = {}
    for f in sorted(STOCK.rglob("*")):
        if f.is_file():
            nom = f.relative_to(STOCK).as_posix()
            if not any(f"/{p}/" in nom for p in exclure):
                out[nom] = f.read_bytes()
    return out


def version_12038(date: str, ajout: str | None = AJOUT) -> dict[str, bytes]:
    """Nouvelle version (date AAAA-MM-JJ) du document réel 12038-PGP."""
    compact = date.replace("-", "")
    xml = (DOC_12038 / "document.xml").read_text("utf-8")
    xml = xml.replace("2026-08-10", date).replace("20260810", compact)
    html = (DOC_12038 / "data.html").read_text("utf-8")
    if ajout:
        html = html.replace("<body>", f"<body>\n<p>{ajout}</p>", 1)
    rep = f"BOFiP/documents/Contenu/Commentaire/RPPM/12038-PGP/{date}"
    return {f"{rep}/document.xml": xml.encode("utf-8"), f"{rep}/data.html": html.encode("utf-8")}


def membres_flux(date: str, ajout: str | None = AJOUT) -> dict[str, bytes]:
    m = version_12038(date, ajout)
    rep_plan = f"BOFiP/documents/PlanClassement/8-PGP/{date}"
    m[f"{rep_plan}/document.xml"] = (PLAN / "document.xml").read_bytes().replace(b"2026-09-23", date.encode())
    m[f"{rep_plan}/data.xml"] = (PLAN / "data.xml").read_bytes()
    for dtd in ("data", "document", "plan"):
        m[f"BOFiP/infos/{dtd}.dtd"] = (STOCK / f"BOFiP/infos/{dtd}.dtd").read_bytes()
    return m


def actualites_gz(dest: Path) -> Path:
    import gzip
    with gzip.open(dest, "wb") as f:
        f.write((FIX / "actualites.json").read_bytes())
    return dest


