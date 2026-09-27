"""Catalogue de modèles models.dev : complète ce que renvoie `GET /models` d'un fournisseur.

Même approche que le harnais pi-ai (dont le catalogue est généré depuis models.dev) :
- le catalogue connaît, pour ~220 fournisseurs, tous leurs modèles avec nom, fenêtre de contexte,
  sortie maximale et options de réflexion — ce que les points `GET /models` ne disent pas, et
  certains n'en listent qu'une partie (pagination, modèles non publiés dans la liste) ;
- le fournisseur est reconnu d'après son URL de base (hôte + préfixe de chemin) ;
- la liste renvoyée par l'API et celle du catalogue sont **réunies** : un modèle présent des deux
  côtés prend les métadonnées du catalogue ; un modèle absent de la liste de l'API est signalé
  `origine = "catalogue"`.

Le catalogue est mis en cache 24 h dans `data/cache/models-dev.json` et reste utilisable hors ligne.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from interstice.config import DATA
from interstice.web.llm.base import NIVEAUX_STANDARD, thinking_support

log = logging.getLogger(__name__)

URL_CATALOGUE = "https://models.dev/api.json"
CACHE = DATA / "cache" / "models-dev.json"
DUREE_CACHE = 24 * 3600

# models.dev ne renseigne pas `api` pour les fournisseurs « officiels » : URL de base connues.
BASES_OFFICIELLES = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "mistral": "https://api.mistral.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "xai": "https://api.x.ai/v1",
    "togetherai": "https://api.together.xyz/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "perplexity": "https://api.perplexity.ai",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}


async def charger_catalogue(chemin: Path = CACHE, forcer: bool = False) -> dict[str, Any]:
    """Catalogue models.dev (cache disque 24 h ; en cas d'échec réseau, le cache même périmé)."""
    frais = chemin.exists() and time.time() - chemin.stat().st_mtime < DUREE_CACHE
    if frais and not forcer:
        return json.loads(chemin.read_text("utf-8"))
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
            r = await c.get(URL_CATALOGUE)
            r.raise_for_status()
            donnees = r.json()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(donnees, ensure_ascii=False), "utf-8")
        return donnees
    except (httpx.HTTPError, ValueError) as e:
        if chemin.exists():
            log.warning("models.dev injoignable (%s) : cache périmé utilisé", e)
            return json.loads(chemin.read_text("utf-8"))
        log.warning("models.dev injoignable et pas de cache : %s", e)
        return {}


def _hote_chemin(url: str) -> tuple[str, str]:
    p = urlparse(url.strip() if "://" in url else f"https://{url.strip()}")
    return (p.hostname or "").lower(), p.path.rstrip("/").lower()


def _est_local(hote: str) -> bool:
    import ipaddress
    if hote in ("localhost", "host.docker.internal") or hote.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(hote)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def trouver_fournisseur(catalogue: dict[str, Any], base_url: str,
                        type_fournisseur: str = "openai") -> tuple[str, dict[str, Any]] | None:
    """Fournisseur du catalogue correspondant à une URL de base (hôte identique, plus long préfixe)."""
    if type_fournisseur == "anthropic" and "anthropic" in catalogue:
        hote, _ = _hote_chemin(base_url or "https://api.anthropic.com")
        if hote in ("", "api.anthropic.com"):
            return "anthropic", catalogue["anthropic"]
    hote, chemin = _hote_chemin(base_url)
    if not hote or _est_local(hote):  # serveur local (Ollama, LM Studio…) : seule sa liste fait foi
        return None
    meilleur: tuple[int, str] | None = None
    for pid, p in catalogue.items():
        api = p.get("api") or BASES_OFFICIELLES.get(pid)
        if not api or not isinstance(p.get("models"), dict):
            continue
        h, ch = _hote_chemin(api)
        if h != hote:
            continue
        # préfixe commun de chemin : départage les fournisseurs qui partagent un hôte
        score = len(ch) if chemin.startswith(ch) or ch.startswith(chemin) else 0
        if meilleur is None or score > meilleur[0]:
            meilleur = (score, pid)
    return (meilleur[1], catalogue[meilleur[1]]) if meilleur else None


def reflexion_catalogue(modele: dict[str, Any], type_fournisseur: str = "openai") -> dict[str, Any]:
    """ThinkingSupport déduit des champs `reasoning` / `reasoning_options` de models.dev."""
    if not modele.get("reasoning"):
        return thinking_support(False, [], "catalogue")
    niveaux: list[str] = []
    for o in modele.get("reasoning_options") or []:
        if o.get("type") == "effort":
            niveaux = [v for v in o.get("values") or [] if v != "none"]
            break
        if o.get("type") == "budget_tokens":
            niveaux = list(NIVEAUX_STANDARD)
        # "toggle" : réflexion activable sans niveau → supportée, pas de sélecteur de niveau
    if not modele.get("reasoning_options"):
        niveaux = list(NIVEAUX_STANDARD)
    return thinking_support(True, niveaux, "catalogue")


def _cle(model_id: str) -> str:
    """Identifiant comparable : Google préfixe « models/ » dans sa liste."""
    return model_id.removeprefix("models/")


def fusionner(listes_api: list[dict[str, Any]] | None, fournisseur: tuple[str, dict[str, Any]] | None,
              type_fournisseur: str = "openai") -> list[dict[str, Any]]:
    """Réunit la liste de l'API et celle du catalogue (forme ModeleDistant sans `enabled`)."""
    cat_modeles: dict[str, dict[str, Any]] = {}
    if fournisseur:
        cat_modeles = {_cle(mid): m for mid, m in fournisseur[1]["models"].items()}
    sortie: dict[str, dict[str, Any]] = {}
    for m in listes_api or []:
        c = cat_modeles.get(_cle(m["id"]))
        entree = dict(m)
        entree["origine"] = "api+catalogue" if c else "api"
        if c:
            limite = c.get("limit") or {}
            entree["label"] = m.get("label") or c.get("name")
            entree["context_length"] = m.get("context_length") or limite.get("context")
            entree["max_output"] = m.get("max_output") or limite.get("output")
            entree["thinking"] = reflexion_catalogue(c, type_fournisseur)
        sortie[_cle(m["id"])] = entree
    if fournisseur:
        for cle, c in cat_modeles.items():
            if cle in sortie:
                continue
            limite = c.get("limit") or {}
            sortie[cle] = {"id": cle, "owned_by": fournisseur[0], "label": c.get("name"),
                           "context_length": limite.get("context"), "max_output": limite.get("output"),
                           "thinking": reflexion_catalogue(c, type_fournisseur), "origine": "catalogue"}
    return sorted(sortie.values(), key=lambda m: m["id"].lower())
