"""Archiveur des publications open data du BOFiP-Impôts.

La DGFiP publie sur data.economie.gouv.fr (jeu `bofip-impots`) :
- un **stock** mensuel `bofip_stock_live_AAAAMMJJ.tgz` (tout le référentiel en vigueur) ;
- un **flux** hebdomadaire `bofip_flux_live_AAAAMMJJ_AAAAMMJJ.tgz` (publications de la semaine) ;
- pour chacun une **empreinte** MD5 (`md5  nom_du_fichier`).

Seuls le dernier stock et les flux des ~6 dernières semaines sont listés : l'historique n'est
pas conservé par la DGFiP. `synchroniser()` est donc destiné à tourner chaque semaine ; il ne
retélécharge rien de ce qui figure déjà (vérifié) dans `data/raw/bofip/manifest.json`.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from interstice.config import RAW

API_JEU = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/bofip-impots/records"
DOSSIER = RAW / "bofip"

_STOCK_RE = re.compile(r"^bofip_stock_live_(\d{8})\.tgz$")
_FLUX_RE = re.compile(r"^bofip_flux_live_(\d{8})_(\d{8})\.tgz$")


@dataclass(frozen=True)
class ArchiveBofip:
    nom: str
    type: str  # "stock" | "flux"
    debut: str | None  # AAAA-MM-JJ (flux)
    fin: str  # AAAA-MM-JJ : date d'extraction (stock) ou fin de période (flux)
    url: str
    url_empreinte: str
    contenu: str = ""

    @property
    def cle_tri(self) -> tuple:
        """Ordre d'application : par date de fin, le stock avant un flux de même date de fin."""
        return (self.fin, self.type != "stock", self.nom)


def _iso(aaaammjj: str) -> str:
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:]}"


def infos_nom(nom: str) -> tuple[str, str | None, str]:
    """(type, début, fin) déduits du nom de fichier ; ValueError si le nom est inattendu."""
    if m := _STOCK_RE.match(nom):
        return "stock", None, _iso(m.group(1))
    if m := _FLUX_RE.match(nom):
        return "flux", _iso(m.group(1)), _iso(m.group(2))
    raise ValueError(f"nom d'archive BOFiP inattendu : {nom}")


def lister(client: httpx.Client) -> list[ArchiveBofip]:
    """Archives actuellement proposées par l'API du jeu `bofip-impots`, dans l'ordre d'application."""
    r = client.get(API_JEU, params={"limit": 100})
    r.raise_for_status()
    data = r.json()
    out = []
    for rec in data["results"]:
        nom = rec["nom_du_fichier"]
        typ, debut, fin = infos_nom(nom)
        out.append(ArchiveBofip(nom, typ, debut, fin, rec["telechargement"], rec["empreinte"], rec.get("contenu") or ""))
    if data.get("total_count", len(out)) > len(out):
        raise RuntimeError("listing BOFiP incomplet (plus de 100 enregistrements) : paginer")
    return sorted(out, key=lambda a: a.cle_tri)


def _hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_attendu(client: httpx.Client, a: ArchiveBofip) -> str:
    r = client.get(a.url_empreinte)
    r.raise_for_status()
    m = re.match(r"\s*([0-9a-fA-F]{32})\s+(\S+)", r.text)
    if not m:
        raise ValueError(f"empreinte illisible pour {a.nom} : {r.text[:80]!r}")
    if m.group(2) != a.nom:
        raise ValueError(f"empreinte pour {m.group(2)}, attendu {a.nom}")
    return m.group(1).lower()


def _telecharger(client: httpx.Client, url: str, dest: Path) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    with client.stream("GET", url) as r:
        r.raise_for_status()
        attendu = int(r.headers["content-length"]) if "content-length" in r.headers else None
        with part.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    if attendu is not None and part.stat().st_size != attendu:
        raise IOError(f"{url} : {part.stat().st_size} octets reçus, {attendu} attendus")
    part.replace(dest)


def lire_manifest(dossier: Path = DOSSIER) -> dict[str, dict]:
    p = dossier / "manifest.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else {}


def _ecrire_manifest(dossier: Path, manifest: dict[str, dict]) -> None:
    tmp = dossier / "manifest.json.tmp"
    tmp.write_text(json.dumps(dict(sorted(manifest.items())), indent=1, ensure_ascii=False), "utf-8")
    tmp.replace(dossier / "manifest.json")


API_VIGUEUR = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/bofip-vigueur"
CHAMPS_INDEX = "type,titre,debut_de_validite,serie,division,identifiant_juridique,permalien"


def _ecrire_gz(dest: Path, data: bytes) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    with gzip.open(part, "wb", compresslevel=9) as f:
        f.write(data)
    part.replace(dest)


def instantane_vigueur(dossier: Path, client: httpx.Client, manifest: dict[str, dict], verbeux: bool = True) -> None:
    """Archive le jeu « publications en vigueur » (bofip-vigueur), seule source open data des actualités.

    Deux fichiers datés de la dernière mise à jour du jeu (`data_processed`) :
    - `bofip_vigueur_index_AAAAMMJJ.json.gz` : tous les enregistrements sans le texte (sert à l'audit) ;
    - `bofip_vigueur_actualites_AAAAMMJJ.json.gz` : les actualités avec `contenu` et `contenu_html`.
    Pas d'empreinte publiée : on vérifie le nombre d'enregistrements contre l'API.
    """
    metas = client.get(API_VIGUEUR).raise_for_status().json()["metas"]["default"]
    stamp = (metas.get("data_processed") or metas["modified"])[:10]
    compact = stamp.replace("-", "")
    total = int(metas["records_count"])
    n_actu = int(client.get(f"{API_VIGUEUR}/records", params={"where": 'type="Actualité"', "limit": 0})
                 .raise_for_status().json()["total_count"])
    for nom, params, attendu, typ in (
            (f"bofip_vigueur_index_{compact}.json.gz", {"select": CHAMPS_INDEX}, total, "vigueur-index"),
            (f"bofip_vigueur_actualites_{compact}.json.gz", {"where": 'type="Actualité"'}, n_actu, "vigueur-actualites")):
        path = dossier / nom
        if nom in manifest and path.exists():
            continue
        if verbeux:
            print(f"instantané {nom}", flush=True)
        r = client.get(f"{API_VIGUEUR}/exports/json", params=params)
        r.raise_for_status()
        n = len(r.json())
        if n != attendu:
            raise IOError(f"{nom} : {n} enregistrements reçus, {attendu} annoncés par l'API")
        _ecrire_gz(path, r.content)
        manifest[nom] = {"type": typ, "debut": None, "fin": stamp, "url": str(r.url), "taille": path.stat().st_size,
                         "md5": _hash(path, "md5"), "md5_verifie": False, "sha256": _hash(path, "sha256"),
                         "enregistrements": n, "verification": "nombre d'enregistrements = API",
                         "telecharge_le": dt.datetime.now().isoformat(timespec="seconds")}
        _ecrire_manifest(dossier, manifest)


def synchroniser(dossier: Path = DOSSIER, client: httpx.Client | None = None, verbeux: bool = True,
                 vigueur: bool = True) -> list[Path]:
    """Télécharge les archives listées absentes du manifest, vérifie leur MD5, les enregistre.

    Retourne la chaîne à ingérer (dernier stock + flux de fin ≥ date du stock), dans l'ordre.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    manifest = lire_manifest(dossier)
    propre = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60, read=600), follow_redirects=True)
    try:
        for a in lister(client):
            path = dossier / a.nom
            entree = manifest.get(a.nom)
            if entree and path.exists() and path.stat().st_size == entree["taille"]:
                continue
            md5 = md5_attendu(client, a)
            if not (path.exists() and _hash(path, "md5") == md5):
                if verbeux:
                    print(f"téléchargement {a.nom}", flush=True)
                _telecharger(client, a.url, path)
            recu = _hash(path, "md5")
            if recu != md5:
                path.unlink()
                raise IOError(f"{a.nom} : MD5 {recu} ≠ empreinte publiée {md5} (fichier supprimé)")
            manifest[a.nom] = {"type": a.type, "debut": a.debut, "fin": a.fin, "url": a.url,
                               "taille": path.stat().st_size, "md5": md5, "md5_verifie": True,
                               "sha256": _hash(path, "sha256"), "contenu": a.contenu,
                               "telecharge_le": dt.datetime.now().isoformat(timespec="seconds")}
            _ecrire_manifest(dossier, manifest)
        if vigueur:
            instantane_vigueur(dossier, client, manifest, verbeux)
    finally:
        if propre:
            client.close()
    return chaine(dossier, manifest)


def chaine(dossier: Path = DOSSIER, manifest: dict[str, dict] | None = None) -> list[Path]:
    """Toutes les archives du manifest dans l'ordre d'application.

    Stocks et flux par date de fin (le stock avant un flux de même date), puis les instantanés
    d'actualités. Les flux antérieurs au dernier stock ne changent pas l'état courant (leurs versions
    sont déjà dans le stock ou ont été remplacées) mais alimentent l'historique des versions.
    L'ingestion est idempotente et saute les archives déjà traitées.
    """
    manifest = lire_manifest(dossier) if manifest is None else manifest
    tar = sorted(((m["fin"], m["type"] != "stock", n) for n, m in manifest.items() if m["type"] in ("stock", "flux")))
    actu = sorted((m["fin"], n) for n, m in manifest.items() if m["type"] == "vigueur-actualites")
    return [dossier / n for *_, n in tar] + [dossier / n for _, n in actu]


def dernier_index_vigueur(dossier: Path = DOSSIER) -> Path | None:
    m = lire_manifest(dossier)
    idx = sorted((v["fin"], n) for n, v in m.items() if v["type"] == "vigueur-index")
    return dossier / idx[-1][1] if idx else None
