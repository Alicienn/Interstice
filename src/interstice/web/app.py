"""API FastAPI d'Interstice (contrat : docs/contrat-api.md).

`create_app()` accepte des dépendances injectables (tests, variantes) :
- `stockage` : instance de `Stockage` (défaut : `INTERSTICE_APP_DB` ou `data/app.sqlite`) ;
- `outils` : liste d'`Outil` ou fonction qui la renvoie (défaut : `interstice.outils.OUTILS`,
  relu à chaque requête car rempli par un autre module) ;
- `fabrique_adaptateur` : `fournisseur (dict avec api_key) -> Adaptateur` ;
- `chemin_corpus` : base du corpus (défaut : `config.DB_PATH`) ;
- `dist` : dossier du frontend compilé (défaut : `web/dist`).
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from interstice import config
from interstice.outils import vues
from interstice.outils.base import Outil
from interstice.web import agent
from interstice.web.corpus import CorpusIndisponible, etat_corpus, ouvrir_corpus
from interstice.web.llm import ErreurFournisseur, creer_adaptateur
from interstice.web.llm.anthropic_natif import URL_DEFAUT as URL_ANTHROPIC
from interstice.web.stockage import Stockage, separer_cle

log = logging.getLogger(__name__)

ORIGINES_DEV = ["http://localhost:5173", "http://127.0.0.1:5173"]


# ---- schémas d'entrée ---------------------------------------------------------------------

class ThinkingSupportIn(BaseModel):
    supported: bool = False
    levels: list[str] = Field(default_factory=list)
    source: Literal["api", "heuristique", "manuel"] = "manuel"


class ModeleActiveIn(BaseModel):
    id: str = Field(min_length=1)
    label: str | None = None
    thinking: ThinkingSupportIn = Field(default_factory=ThinkingSupportIn)
    context_length: int | None = None


class ModelesIn(BaseModel):
    models: list[ModeleActiveIn]


class FournisseurIn(BaseModel):
    name: str = Field(min_length=1)
    type: Literal["openai", "anthropic"]
    base_url: str = ""
    api_key: str | None = None


class FournisseurPatch(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # null ou "" : clé inchangée


class ReglagesIn(BaseModel):
    default_model_key: str | None = None
    default_thinking: str | None = None


class ConversationIn(BaseModel):
    title: str | None = None


class ConversationPatch(BaseModel):
    title: str


class MessageIn(BaseModel):
    content: str
    model_key: str
    thinking_level: str | None = None


# ---- utilitaires --------------------------------------------------------------------------

def _outils_par_defaut() -> list[Outil]:
    from interstice.outils import OUTILS

    if not OUTILS:
        try:  # le registre est rempli à l'import du module d'outils LEGI, s'il existe
            importlib.import_module("interstice.outils.legi")
        except ModuleNotFoundError:
            pass
    return list(OUTILS)


def _sse(evenement: str, donnees: dict[str, Any]) -> str:
    return f"event: {evenement}\ndata: {json.dumps(donnees, ensure_ascii=False)}\n\n"


def _normaliser_url(type_: str, base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if type_ == "anthropic" and not url:
        return URL_ANTHROPIC
    if not url:
        raise HTTPException(422, "base_url requis pour un fournisseur de type openai")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "base_url doit commencer par http:// ou https://")
    return url


def create_app(*, stockage: Stockage | None = None,
               outils: list[Outil] | Callable[[], list[Outil]] | None = None,
               fabrique_adaptateur: Callable[[dict[str, Any]], Any] | None = None,
               chemin_corpus: Path | str | None = None,
               dist: Path | str | None = None) -> FastAPI:
    st = stockage or Stockage()
    if outils is None:
        fournir_outils: Callable[[], list[Outil]] = _outils_par_defaut
    elif callable(outils):
        fournir_outils = outils
    else:
        liste = list(outils)
        fournir_outils = lambda: liste  # noqa: E731
    fabrique = fabrique_adaptateur or creer_adaptateur
    corpus = Path(chemin_corpus) if chemin_corpus is not None else config.DB_PATH
    dossier_dist = Path(dist) if dist is not None else config.ROOT / "web" / "dist"
    generations: dict[str, asyncio.Event] = {}

    app = FastAPI(title="Interstice", version="0.1.0")
    app.state.stockage = st
    app.state.generations = generations
    app.add_middleware(CORSMiddleware, allow_origins=ORIGINES_DEV, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    # ---- divers ---------------------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "db": etat_corpus(corpus)}

    @app.get("/api/tools")
    def tools() -> list[dict[str, Any]]:
        return [{"name": o.nom, "description": o.description, "parameters": o.parametres}
                for o in fournir_outils()]

    # ---- fournisseurs ---------------------------------------------------------------------

    def _fournisseur_ou_404(pid: str) -> dict[str, Any]:
        f = st.fournisseur_prive(pid)
        if not f:
            raise HTTPException(404, "fournisseur introuvable")
        return f

    @app.get("/api/providers")
    def lister_fournisseurs() -> list[dict[str, Any]]:
        return st.lister_fournisseurs()

    @app.post("/api/providers")
    def creer_fournisseur(corps: FournisseurIn) -> dict[str, Any]:
        url = _normaliser_url(corps.type, corps.base_url)
        return st.creer_fournisseur(corps.name.strip(), corps.type, url, corps.api_key)

    @app.patch("/api/providers/{pid}")
    def modifier_fournisseur(pid: str, corps: FournisseurPatch) -> dict[str, Any]:
        f = _fournisseur_ou_404(pid)
        champs: dict[str, Any] = {}
        if corps.name is not None and corps.name.strip():
            champs["name"] = corps.name.strip()
        if corps.base_url is not None:
            champs["base_url"] = _normaliser_url(f["type"], corps.base_url)
        if corps.api_key:
            champs["api_key"] = corps.api_key
        return st.modifier_fournisseur(pid, **champs)  # type: ignore[return-value]

    @app.delete("/api/providers/{pid}", status_code=204)
    def supprimer_fournisseur(pid: str) -> Response:
        if not st.supprimer_fournisseur(pid):
            raise HTTPException(404, "fournisseur introuvable")
        return Response(status_code=204)

    @app.get("/api/providers/{pid}/remote-models")
    async def modeles_distants(pid: str) -> list[dict[str, Any]]:
        f = _fournisseur_ou_404(pid)
        actifs = {m["id"] for m in f["models"]}
        try:
            modeles = await fabrique(f).lister_modeles()
        except ErreurFournisseur as e:
            raise HTTPException(502, e.message) from e
        except Exception as e:  # noqa: BLE001
            log.exception("remote-models %s", pid)
            raise HTTPException(502, f"Erreur du fournisseur : {e}") from e
        return [{**m, "enabled": m["id"] in actifs} for m in modeles]

    @app.put("/api/providers/{pid}/models")
    def definir_modeles(pid: str, corps: ModelesIn) -> dict[str, Any]:
        _fournisseur_ou_404(pid)
        st.definir_modeles(pid, [m.model_dump() for m in corps.models])
        return st.fournisseur(pid)  # type: ignore[return-value]

    @app.get("/api/models")
    def modeles() -> list[dict[str, Any]]:
        return st.modeles_choix()

    # ---- réglages -------------------------------------------------------------------------

    @app.get("/api/settings")
    def lire_reglages() -> dict[str, Any]:
        return st.lire_reglages()

    @app.put("/api/settings")
    def ecrire_reglages(corps: ReglagesIn) -> dict[str, Any]:
        return st.ecrire_reglages(corps.model_dump())

    # ---- conversations --------------------------------------------------------------------

    @app.get("/api/conversations")
    def lister_conversations() -> list[dict[str, Any]]:
        return st.lister_conversations()

    @app.post("/api/conversations")
    def creer_conversation(corps: ConversationIn | None = None) -> dict[str, Any]:
        return st.creer_conversation(corps.title if corps else None)

    @app.get("/api/conversations/{cid}")
    def lire_conversation(cid: str) -> dict[str, Any]:
        c = st.conversation(cid)
        if not c:
            raise HTTPException(404, "conversation introuvable")
        return c

    @app.patch("/api/conversations/{cid}")
    def renommer_conversation(cid: str, corps: ConversationPatch) -> dict[str, Any]:
        c = st.renommer_conversation(cid, corps.title)
        if not c:
            raise HTTPException(404, "conversation introuvable")
        return c

    @app.delete("/api/conversations/{cid}", status_code=204)
    def supprimer_conversation(cid: str) -> Response:
        ev = generations.get(cid)
        if ev:
            ev.set()
        if not st.supprimer_conversation(cid):
            raise HTTPException(404, "conversation introuvable")
        return Response(status_code=204)

    @app.post("/api/conversations/{cid}/stop", status_code=204)
    def arreter(cid: str) -> Response:
        ev = generations.get(cid)
        if ev:
            ev.set()
        return Response(status_code=204)

    @app.post("/api/conversations/{cid}/messages")
    async def envoyer_message(cid: str, corps: MessageIn) -> StreamingResponse:
        if not st.conversation_brute(cid):
            raise HTTPException(404, "conversation introuvable")
        contenu = corps.content.strip()
        if not contenu:
            raise HTTPException(422, "message vide")
        try:
            pid, model_id = separer_cle(corps.model_key)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        f = st.fournisseur_prive(pid)
        if not f:
            raise HTTPException(404, "fournisseur du modèle introuvable")
        modele = st.modele_active(pid, model_id)
        niveau = corps.thinking_level or None
        if modele is not None and not modele["thinking"].get("supported"):
            niveau = None  # le modèle ne propose pas de réglage de réflexion
        if cid in generations:
            raise HTTPException(409, "une génération est déjà en cours pour cette conversation")
        try:
            adaptateur = fabrique(f)
        except ErreurFournisseur as e:
            raise HTTPException(502, e.message) from e

        arret = asyncio.Event()
        ctx = agent.ContexteGeneration(
            stockage=st, adaptateur=adaptateur, conversation_id=cid, contenu=contenu,
            model_id=model_id, model_key=corps.model_key, niveau_reflexion=niveau,
            outils=fournir_outils(), ouvrir_corpus=lambda: ouvrir_corpus(corpus), arret=arret)

        async def flux() -> AsyncIterator[str]:
            # Enregistrée ici (et non avant) : si le flux ne démarre jamais, rien ne reste bloqué.
            if cid in generations:
                yield _sse("error", {"message": "une génération est déjà en cours"})
                return
            generations[cid] = arret
            try:
                async for evenement, donnees in agent.generer(ctx):
                    yield _sse(evenement, donnees)
            finally:
                if generations.get(cid) is arret:
                    del generations[cid]

        return StreamingResponse(flux(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    # ---- documents (panneau de lecture) ---------------------------------------------------

    def _vue(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            conn = ouvrir_corpus(corpus)
        except CorpusIndisponible as e:
            raise HTTPException(503, str(e)) from e
        try:
            return fn(conn, *args, **kwargs)
        except NotImplementedError as e:
            raise HTTPException(501, "vue pas encore implémentée") from e
        except LookupError as e:
            raise HTTPException(404, str(e) or "document introuvable") from e
        except sqlite3.Error as e:
            raise HTTPException(503, f"corpus illisible : {e}") from e
        finally:
            conn.close()

    @app.get("/api/documents/recherche")
    def recherche(q: str = Query(..., min_length=1), texte: str | None = None,
                  date: str | None = None) -> dict[str, Any]:
        return {"resultats": _vue(vues.recherche, q, texte=texte or None, date=date or None)}

    @app.get("/api/documents/article/{id}")
    def document_article(id: str, date: str | None = None) -> Any:
        return _vue(vues.vue_article, id, date=date or None)

    @app.get("/api/documents/section/{id}")
    def document_section(id: str, date: str | None = None) -> Any:
        return _vue(vues.vue_section, id, date=date or None)

    @app.get("/api/documents/texte/{cid}")
    def document_texte(cid: str, date: str | None = None) -> Any:
        return _vue(vues.vue_texte, cid, date=date or None)

    @app.get("/api/textes")
    def textes() -> Any:
        return _vue(vues.lister_textes)

    # ---- BOFiP ----------------------------------------------------------------------------

    @app.get("/api/bofip/documents/{id}")
    def bofip_document(id: str) -> Any:
        from interstice.outils.bofip import vue_bofip
        return _vue(vue_bofip, id)

    @app.get("/api/bofip/plan")
    def bofip_plan(noeud: str | None = None) -> Any:
        from interstice.outils.bofip import vue_bofip_noeud
        return _vue(vue_bofip_noeud, noeud or None)

    @app.get("/api/bofip/recherche")
    def bofip_recherche(q: str = Query(..., min_length=1), serie: str | None = None) -> dict[str, Any]:
        from interstice.outils.bofip import recherche_bofip
        return {"resultats": _vue(recherche_bofip, q, serie=serie or None)}

    # ---- frontend compilé -----------------------------------------------------------------

    @app.api_route("/api/{reste:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   include_in_schema=False)
    def api_inconnue(reste: str) -> JSONResponse:
        return JSONResponse({"detail": "route inconnue"}, status_code=404)

    @app.get("/{chemin:path}", include_in_schema=False)
    def statique(chemin: str, request: Request) -> Response:
        index = dossier_dist / "index.html"
        if not index.is_file():
            return JSONResponse({"detail": "frontend non compilé (web/dist absent)"},
                                status_code=404)
        racine = dossier_dist.resolve()
        cible = (racine / chemin).resolve()
        if chemin and cible.is_file() and cible.is_relative_to(racine):
            return FileResponse(cible)
        return FileResponse(index)  # repli SPA

    return app
