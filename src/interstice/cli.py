"""Point d'entrée en ligne de commande : `uv run interstice <commande>`."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="interstice")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("download", help="télécharge une base DILA (global + incréments)")
    s.add_argument("base", nargs="?", default="LEGI")

    s = sub.add_parser("ingest", help="ingère les archives LEGI téléchargées dans la base SQLite")
    s.add_argument("--processus", type=int, default=6, help="processus de parsing en parallèle")
    s.add_argument("--jusqua", type=int, default=None, help="n'ingérer que les N premières archives de la chaîne")

    s = sub.add_parser("index", help="construit le graphe des renvois et l'index plein texte")
    s.add_argument("--processus", type=int, default=6)
    s.add_argument("--sans-renvois", action="store_true")
    s.add_argument("--sans-fts", action="store_true")

    s = sub.add_parser("audit", help="audit d'exhaustivité de la base (rapport dans data/audit/)")
    s.add_argument("--tar", action="store_true", help="recompte les XML de chaque archive avec `tar -t`")
    s.add_argument("--date", default=None)

    sub.add_parser("mcp", help="serveur MCP (stdio) exposant les outils de navigation")

    s = sub.add_parser("export-md", help="export Markdown (un fichier par article, liens wiki entre renvois)")
    s.add_argument("--sigles", nargs="*", default=None, help="ex. CGI LPF (défaut : périmètre fiscal)")
    s.add_argument("--dest", default=None)
    s.add_argument("--date", default=None)

    s = sub.add_parser("serve", help="lance l'application web (API + frontend compilé)")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--reload", action="store_true", help="rechargement auto (développement)")

    args = p.parse_args(argv)
    if args.cmd == "download":
        from interstice.sources.dila import sync

        paths = sync(args.base)
        print(f"{len(paths)} archives à jour")
    elif args.cmd == "serve":
        import uvicorn

        # Écoute locale uniquement : les clés API sont stockées en clair dans data/app.sqlite.
        uvicorn.run("interstice.web.app:create_app", factory=True, host="127.0.0.1",
                    port=args.port, reload=args.reload)
    elif args.cmd == "ingest":
        _ingest(args)
    elif args.cmd == "index":
        _index(args)
    elif args.cmd == "audit":
        _audit(args)
    elif args.cmd == "mcp":
        from interstice.mcp_server import main as mcp_main

        mcp_main()
    elif args.cmd == "export-md":
        from pathlib import Path

        from interstice.config import DATA, DB_PATH
        from interstice.export.markdown import exporter
        from interstice.store.db import connect

        dest = Path(args.dest) if args.dest else DATA / "export-md"
        print(exporter(connect(DB_PATH, lecture_seule=True), dest, args.sigles, args.date))


def _index(args: argparse.Namespace) -> None:
    from interstice.config import DB_PATH
    from interstice.store.db import connect, init_schema, meta_set

    conn = connect(DB_PATH)
    init_schema(conn)
    if not args.sans_renvois:
        from interstice.graph.construire import construire_renvois

        print("Graphe des renvois…", flush=True)
        stats = construire_renvois(conn, processus=args.processus)
        print(f"  {stats}")
        meta_set(conn, "renvois", str(stats))
        conn.commit()
    if not args.sans_fts:
        from interstice.store.fts import reconstruire_fts

        print("Index plein texte…", flush=True)
        print(f"  {reconstruire_fts(conn):.0f} s")


def _audit(args: argparse.Namespace) -> None:
    import sys
    import time

    from interstice.audit.legi import auditer
    from interstice.config import DATA, DB_PATH, RAW
    from interstice.store.db import connect

    rapport, ok = auditer(connect(DB_PATH, lecture_seule=True), RAW / "legi", verifier_tar=args.tar, date=args.date)
    dest = DATA / "audit" / f"legi-{time.strftime('%Y%m%d-%H%M')}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rapport, "utf-8")
    print(rapport)
    print(f"\nRapport : {dest}")
    sys.exit(0 if ok else 1)


def _ingest(args: argparse.Namespace) -> None:
    import json

    from interstice.config import DB_PATH, RAW
    from interstice.legi.ingest import ingerer_chaine
    from interstice.store.db import connect, init_schema

    d = RAW / "legi"
    chaine = json.loads((d / "chain.json").read_text("utf-8")) if (d / "chain.json").exists() else None
    manifest = json.loads((d / "manifest.json").read_text("utf-8"))
    if chaine is None:  # téléchargement en cours : ordre chronologique du manifest
        chaine = [n for n, _ in sorted(manifest.items(), key=lambda kv: (not kv[1]["global"], kv[1]["stamp"]))]
    paths = []
    for nom in chaine[: args.jusqua]:
        if nom not in manifest or not (d / nom).exists():
            print(f"Arrêt avant {nom} (pas encore téléchargé) : l'ordre chronologique doit être respecté.")
            break
        paths.append(d / nom)
    conn = connect(DB_PATH)
    init_schema(conn)
    faits = ingerer_chaine(conn, paths, manifest, processus=args.processus)
    print(f"{len(faits)} archive(s) ingérée(s) ; base : {DB_PATH}")


if __name__ == "__main__":
    main()
