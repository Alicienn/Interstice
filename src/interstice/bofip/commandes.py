"""Commandes BOFiP appelées par `interstice.cli` (bofip-download, bofip-ingest, bofip-audit)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def ajouter_sous_commandes(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("bofip-download", help="archive le stock et les flux BOFiP (MD5 vérifié) + instantané bofip-vigueur")
    s.add_argument("--sans-vigueur", action="store_true", help="n'archive pas le jeu « publications en vigueur »")
    s = sub.add_parser("bofip-ingest", help="ingère les archives BOFiP téléchargées (stock, flux, actualités)")
    s.add_argument("--forcer", action="store_true", help="réingère aussi les archives déjà traitées")
    s.add_argument("--legi", default=None,
                   help="base LEGI pour résoudre les articles cités (défaut : la base cible elle-même)")
    s.add_argument("--audit", action="store_true", help="enchaîne l'audit d'exhaustivité")
    s = sub.add_parser("bofip-audit", help="audit d'exhaustivité BOFiP (rapport dans data/audit/)")
    s.add_argument("--hors-ligne", action="store_true", help="compare au dernier instantané bofip-vigueur archivé")


def executer(args: argparse.Namespace) -> None:
    if args.cmd == "bofip-download":
        telecharger(vigueur=not args.sans_vigueur)
    elif args.cmd == "bofip-ingest":
        ingerer(forcer=args.forcer, legi=args.legi)
        if args.audit:
            auditer()
    elif args.cmd == "bofip-audit":
        auditer(en_ligne=not args.hors_ligne)


def telecharger(vigueur: bool = True) -> list[Path]:
    from interstice.bofip.archives import synchroniser

    chemins = synchroniser(vigueur=vigueur)
    print(f"{len(chemins)} archive(s) BOFiP dans la chaîne d'ingestion")
    return chemins


def ingerer(forcer: bool = False, legi: str | None = None) -> None:
    from interstice.bofip.archives import DOSSIER, chaine, lire_manifest
    from interstice.bofip.ingest import ingerer_chaine
    from interstice.config import DB_PATH
    from interstice.store.db import connect

    conn = connect(DB_PATH)
    conn_legi = connect(legi, lecture_seule=True) if legi else None
    chemins = chaine(DOSSIER)
    if not chemins:
        print("Aucune archive : lancez d'abord `interstice bofip-download`.")
        return
    stats = ingerer_chaine(conn, chemins, lire_manifest(DOSSIER), conn_legi=conn_legi, forcer=forcer)
    print(f"{len(stats)} archive(s) ingérée(s) ; base : {DB_PATH}")


def auditer(en_ligne: bool = True) -> None:
    from interstice.bofip.archives import DOSSIER, dernier_index_vigueur
    from interstice.bofip.audit import auditer_bofip
    from interstice.config import DATA, DB_PATH
    from interstice.store.db import connect

    index = None
    if en_ligne:
        try:
            import httpx

            from interstice.bofip.archives import API_VIGUEUR, CHAMPS_INDEX
            r = httpx.get(f"{API_VIGUEUR}/exports/json", params={"select": CHAMPS_INDEX}, timeout=300)
            r.raise_for_status()
            index = r.json()
        except Exception as e:  # noqa: BLE001 — repli sur l'instantané archivé
            print(f"(API bofip-vigueur indisponible : {e} ; instantané archivé utilisé)")
    if index is None:
        index = dernier_index_vigueur(DOSSIER)
    rapport, ok = auditer_bofip(connect(DB_PATH, lecture_seule=True), DOSSIER, index)
    dest = DATA / "audit" / f"bofip-{time.strftime('%Y%m%d-%H%M')}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rapport, "utf-8")
    print(rapport)
    print(f"\nRapport : {dest}")
    sys.exit(0 if ok else 1)
