"""Téléchargement des archives open data de la DILA (LEGI, JADE, CONSTIT...).

Principe : une archive globale (`Freemium_<base>_global_*.tar.gz`) plus des
incréments datés (`<BASE>_AAAAMMJJ-HHMMSS.tar.gz`). L'état courant = global +
tous les incréments postérieurs, appliqués dans l'ordre chronologique.

Chaque fichier téléchargé est enregistré dans `manifest.json` (taille, sha256)
pour qu'une ingestion puisse prouver qu'elle a tout traité.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from interstice.config import DILA_OPENDATA, RAW

_GLOBAL_RE = re.compile(r"Freemium_(\w+?)_global_(\d{8}-\d{6})\.tar\.gz$", re.I)
_INCR_RE = re.compile(r"([A-Z]+)_(\d{8}-\d{6})\.tar\.gz$")


@dataclass(frozen=True, order=True)
class Archive:
    stamp: str  # AAAAMMJJ-HHMMSS : clé de tri chronologique
    name: str
    is_global: bool

    @property
    def url_path(self) -> str:
        return self.name


def parse_listing(html: str) -> list[Archive]:
    """Extrait les archives d'un listing Apache de la DILA."""
    archives: set[Archive] = set()
    for href in re.findall(r'href="([^"]+\.tar\.gz)"', html):
        name = href.rsplit("/", 1)[-1]
        if m := _GLOBAL_RE.match(name):
            archives.add(Archive(m.group(2), name, True))
        elif m := _INCR_RE.match(name):
            archives.add(Archive(m.group(2), name, False))
    return sorted(archives)


def select_chain(archives: list[Archive]) -> list[Archive]:
    """Global le plus récent + incréments strictement postérieurs, dans l'ordre."""
    globals_ = [a for a in archives if a.is_global]
    if not globals_:
        raise ValueError("aucune archive globale dans le listing")
    base = max(globals_)
    return [base] + [a for a in archives if not a.is_global and a.stamp > base.stamp]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(client: httpx.Client, url: str, dest: Path) -> None:
    """Téléchargement reprenable (en-tête Range) avec contrôle de taille."""
    part = dest.with_suffix(dest.suffix + ".part")
    head = client.head(url)
    head.raise_for_status()
    total = int(head.headers["content-length"])
    done = part.stat().st_size if part.exists() else 0
    if done < total:
        headers = {"Range": f"bytes={done}-"} if done else {}
        with client.stream("GET", url, headers=headers) as r:
            r.raise_for_status()
            if done and r.status_code != 206:  # serveur sans reprise : on repart de zéro
                done = 0
            with part.open("ab" if done else "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
    if part.stat().st_size != total:
        raise IOError(f"{url}: {part.stat().st_size} octets reçus, {total} attendus")
    part.replace(dest)


def sync(base: str = "LEGI", dest_root: Path = RAW) -> list[Path]:
    """Télécharge la chaîne global + incréments manquants. Retourne les chemins dans l'ordre."""
    dest = dest_root / base.lower()
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / "manifest.json"
    manifest: dict[str, dict] = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}

    url = f"{DILA_OPENDATA}/{base}/"
    with httpx.Client(timeout=httpx.Timeout(60, read=300), follow_redirects=True) as client:
        listing = client.get(url)
        listing.raise_for_status()
        chain = select_chain(parse_listing(listing.text))
        paths = []
        for i, a in enumerate(chain, 1):
            path = dest / a.name
            if a.name not in manifest or not path.exists():
                print(f"[{i}/{len(chain)}] {a.name}", flush=True)
                _download(client, url + a.url_path, path)
                manifest[a.name] = {"stamp": a.stamp, "global": a.is_global,
                                    "size": path.stat().st_size, "sha256": _sha256(path)}
                manifest_path.write_text(json.dumps(manifest, indent=1), "utf-8")
            paths.append(path)
    (dest / "chain.json").write_text(json.dumps([p.name for p in paths], indent=1), "utf-8")
    return paths
