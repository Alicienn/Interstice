"""Point d'entrée en ligne de commande : `uv run interstice <commande>`."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="interstice")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("download", help="télécharge une base DILA (global + incréments)")
    s.add_argument("base", nargs="?", default="LEGI")

    args = p.parse_args(argv)
    if args.cmd == "download":
        from interstice.sources.dila import sync

        paths = sync(args.base)
        print(f"{len(paths)} archives à jour")


if __name__ == "__main__":
    main()
