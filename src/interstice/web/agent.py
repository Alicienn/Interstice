"""Boucle agent : modèle ↔ outils de navigation du corpus, événements SSE du contrat.

`generer(ctx)` est un générateur asynchrone de couples `(event, data)` :
`user_message`, `message_start`, `thinking_delta`, `text_delta`, `tool_call`, `tool_result`,
`error`, `message_end` (toujours en dernier, même après une erreur ou une interruption).

Les parts du message assistant et la trace LLM (historique neutre rejouable) sont persistées
au fil de l'eau : un message partiel reste consultable après une erreur ou un arrêt.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import date
from typing import Any, AsyncIterator, Callable

from interstice.outils.base import Outil, Resultat
from interstice.web.corpus import CorpusIndisponible
from interstice.web.llm.base import (
    Adaptateur,
    ErreurFournisseur,
    Fin,
    OutilSpec,
    RequeteLLM,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
)
from interstice.web.stockage import Stockage

log = logging.getLogger(__name__)

MAX_TOURS_OUTILS = 40
INTERVALLE_SAUVEGARDE = 1.0  # secondes entre deux sauvegardes des parts pendant le flux

# Prompt système : figé (aucune donnée variable) pour que le cache de prompt fonctionne.
# La date du jour est injectée dans le message utilisateur.
PROMPT_SYSTEME = """\
Tu es Interstice, un assistant d'analyse du droit fiscal français. Tu réponds en français, à \
partir des textes officiels (codes et textes consolidés de la base LEGI) auxquels tu accèdes \
uniquement par les outils de navigation fournis. Tes interlocuteurs sont des juristes et des \
contribuables avertis : sois précis, sourcé et nuancé.

Méthode de travail :
- Avant de conclure, situe la question dans l'architecture des textes : parcours le plan du \
code concerné avec l'outil `sommaire` (texte, puis sections pertinentes) pour repérer les \
articles applicables et les dispositions voisines (définitions, exceptions, renvois), plutôt \
que de te fier à ta mémoire ou à une seule recherche plein texte.
- Lis les articles eux-mêmes avant de t'appuyer dessus. Ta mémoire des textes peut être \
périmée ou inexacte ; seul le texte renvoyé par les outils fait foi.
- Vérifie la date de vigueur : la version lue doit être en vigueur à la date pertinente pour \
la situation (date du jour, sauf si la question porte sur une autre période ou un exercice \
passé). Signale les modifications récentes ou à venir et les dispositions transitoires.
- Suis les renvois utiles (articles cités, textes d'application) quand ils conditionnent la \
réponse.

Présentation de la réponse :
- Cite chaque article sur lequel tu t'appuies avec son numéro et le code (ex. « CGI, art. \
150-0 B ter ») et reproduis le passage pertinent entre guillemets, tel que renvoyé par l'outil.
- Distingue nettement ce que dit le texte (citation, paraphrase fidèle) de tes propres \
inférences, interprétations ou hypothèses, que tu présentes comme telles. Si la doctrine \
administrative (BOFiP) ou la jurisprudence pourrait infléchir la lecture et que tu n'y as pas \
accès, dis-le.
- Si les textes consultés ne permettent pas de conclure, dis-le et indique ce qu'il faudrait \
vérifier. N'invente jamais un article, un numéro, un seuil ou une date.

Optimisation fiscale : pour toute piste d'optimisation, qualifie-la explicitement :
- « optimisation sûre » : choix ouvert par la loi, conforme à son objet ;
- « risque d'abus de droit » : montage artificiel ou recherche d'un but exclusivement \
(art. L64 LPF) ou principalement (art. L64 A LPF) fiscal, ou dispositif anti-abus spécifique \
(art. 205 A CGI pour l'impôt sur les sociétés) ; expose le risque et ses conséquences \
(rectification, majorations) ;
- « fraude » : soustraction frauduleuse à l'impôt (art. 1741 CGI).
Tu ne conçois, n'optimises ni ne détailles jamais un montage frauduleux ou destiné à \
dissimuler des faits à l'administration ; tu peux en revanche expliquer pourquoi un schéma \
relève de la fraude ou de l'abus de droit et quels risques il fait courir.

Tes réponses ne remplacent pas le conseil d'un professionnel ; rappelle-le brièvement quand \
l'enjeu le justifie."""


class Interrompu(Exception):
    """Arrêt demandé via /stop."""


@dataclass
class ContexteGeneration:
    stockage: Stockage
    adaptateur: Adaptateur
    conversation_id: str
    contenu: str
    model_id: str
    model_key: str
    niveau_reflexion: str | None
    outils: list[Outil]
    ouvrir_corpus: Callable[[], sqlite3.Connection]
    arret: asyncio.Event = field(default_factory=asyncio.Event)
    date_du_jour: str = field(default_factory=lambda: date.today().isoformat())
    system: str = PROMPT_SYSTEME


def specs_outils(outils: list[Outil]) -> list[OutilSpec]:
    return [OutilSpec(o.nom, o.description, o.parametres) for o in outils]


def resume_resultat(res: Resultat, max_car: int = 160) -> str:
    for ligne in res.texte.splitlines():
        ligne = ligne.strip().lstrip("#>*-• ").strip()
        if ligne:
            return ligne if len(ligne) <= max_car else ligne[: max_car - 1].rstrip() + "…"
    return "Erreur" if res.erreur else "Résultat vide"


class Parts:
    """Parts du message assistant (forme du contrat)."""

    def __init__(self) -> None:
        self.liste: list[dict[str, Any]] = []

    def ajouter_texte(self, type_: str, texte: str) -> None:
        if self.liste and self.liste[-1]["type"] == type_:
            self.liste[-1]["text"] += texte
        else:
            self.liste.append({"type": type_, "text": texte})

    def ajouter_outil(self, appel: ToolCall) -> None:
        self.liste.append({"type": "tool", "call_id": appel.id, "name": appel.name,
                           "arguments": appel.arguments, "status": "running", "documents": []})

    def terminer_outil(self, call_id: str, status: str, summary: str,
                       documents: list[dict[str, Any]]) -> None:
        for p in self.liste:
            if p["type"] == "tool" and p["call_id"] == call_id:
                p.update(status=status, summary=summary, documents=documents)

    def interrompre_outils(self, summary: str) -> list[str]:
        ids = []
        for p in self.liste:
            if p["type"] == "tool" and p["status"] == "running":
                p.update(status="error", summary=summary)
                ids.append(p["call_id"])
        return ids


async def consommer(flux: AsyncIterator[Any], arret: asyncio.Event) -> AsyncIterator[Any]:
    """Relaie `flux` en l'exécutant dans une tâche dédiée, interrompue dès que `arret` est posé.

    Le flux (connexion HTTP du fournisseur) vit entièrement dans sa propre tâche : l'annuler
    ferme proprement la connexion, même si le fournisseur est silencieux (longue réflexion).
    """
    file: asyncio.Queue = asyncio.Queue()
    FIN = object()

    async def producteur() -> None:
        try:
            async for ev in flux:
                file.put_nowait(("ev", ev))
            file.put_nowait(("fin", FIN))
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except BaseException as e:  # noqa: BLE001 — relayé au consommateur
            file.put_nowait(("err", e))

    tache = asyncio.create_task(producteur())
    attente_arret = asyncio.create_task(arret.wait())
    try:
        while True:
            lecture = asyncio.create_task(file.get())
            fait, _ = await asyncio.wait({lecture, attente_arret},
                                         return_when=asyncio.FIRST_COMPLETED)
            if lecture not in fait:
                lecture.cancel()
                raise Interrompu()
            genre, valeur = lecture.result()
            if genre == "fin":
                return
            if genre == "err":
                raise valeur
            yield valeur
    finally:
        attente_arret.cancel()
        if not tache.done():
            tache.cancel()
            try:
                await tache
            except (asyncio.CancelledError, Exception):
                pass


async def generer(ctx: ContexteGeneration) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    st = ctx.stockage
    cid = ctx.conversation_id

    # 1. Message utilisateur (la date du jour n'est visible que du modèle, dans la trace).
    trace_user = [{"role": "user",
                   "content": f"[Date du jour : {ctx.date_du_jour}]\n\n{ctx.contenu}"}]
    msg_user = st.ajouter_message(cid, "user", [{"type": "text", "text": ctx.contenu}],
                                  trace=trace_user)
    st.titrer_si_vide(cid, ctx.contenu)
    yield "user_message", msg_user

    historique_anterieur = st.historique_llm(cid)

    # 2. Message assistant (créé vide, rempli au fil de l'eau).
    msg = st.ajouter_message(cid, "assistant", [], model_key=ctx.model_key,
                             thinking_level=ctx.niveau_reflexion, trace=[])
    mid = msg["id"]
    yield "message_start", {"message_id": mid, "model_key": ctx.model_key,
                            "thinking_level": ctx.niveau_reflexion}

    parts = Parts()
    trace: list[dict[str, Any]] = []
    usage = Usage()
    erreur: str | None = None
    conn: sqlite3.Connection | None = None
    derniere_sauvegarde = time.monotonic()
    outils_par_nom = {o.nom: o for o in ctx.outils}
    specs = specs_outils(ctx.outils)

    def sauver(final: bool = False) -> None:
        st.maj_message(mid, parts=parts.liste, trace=trace, usage=usage.to_dict(),
                       error=erreur if final else None)

    def executer(appel: ToolCall) -> Resultat:
        nonlocal conn
        outil = outils_par_nom.get(appel.name)
        if outil is None:
            return Resultat(texte=f"Erreur : outil inconnu « {appel.name} ».", erreur=True)
        if appel.erreur_arguments:
            return Resultat(texte=f"Erreur : {appel.erreur_arguments}", erreur=True)
        try:
            if conn is None:
                conn = ctx.ouvrir_corpus()
            return outil.appeler(conn, appel.arguments)
        except CorpusIndisponible as e:
            return Resultat(texte=f"Erreur : corpus indisponible ({e}).", erreur=True)
        except NotImplementedError:
            return Resultat(texte="Erreur : outil pas encore implémenté.", erreur=True)
        except Exception as e:  # noqa: BLE001 — renvoyé au modèle comme résultat d'erreur
            log.exception("outil %s", appel.name)
            return Resultat(texte=f"Erreur lors de l'exécution de l'outil : {e}", erreur=True)

    try:
        tours_outils = 0
        while True:
            requete = RequeteLLM(model=ctx.model_id, system=ctx.system,
                                 historique=historique_anterieur + trace, outils=specs,
                                 niveau_reflexion=ctx.niveau_reflexion)
            appels: list[ToolCall] = []
            fin: Fin | None = None
            texte_tour: list[str] = []
            async with aclosing(consommer(ctx.adaptateur.flux(requete), ctx.arret)) as flux:
                async for ev in flux:
                    if isinstance(ev, ThinkingDelta):
                        parts.ajouter_texte("thinking", ev.text)
                        yield "thinking_delta", {"text": ev.text}
                    elif isinstance(ev, TextDelta):
                        parts.ajouter_texte("text", ev.text)
                        texte_tour.append(ev.text)
                        yield "text_delta", {"text": ev.text}
                    elif isinstance(ev, ToolCall):
                        appels.append(ev)
                    elif isinstance(ev, Fin):
                        fin = ev
                    if time.monotonic() - derniere_sauvegarde > INTERVALLE_SAUVEGARDE:
                        sauver()
                        derniere_sauvegarde = time.monotonic()
            fin = fin or Fin()
            usage.ajouter(fin.usage)
            trace.append({"role": "assistant", "content": "".join(texte_tour),
                          "tool_calls": [{"id": a.id, "name": a.name, "arguments": a.arguments}
                                         for a in appels],
                          "brut": fin.brut})

            if not appels:
                if fin.stop_reason == "refusal":
                    erreur = "Le modèle a refusé de répondre (refus de sécurité du fournisseur)."
                elif fin.stop_reason == "max_tokens":
                    erreur = "Réponse tronquée : limite de jetons de sortie atteinte."
                break

            for a in appels:
                parts.ajouter_outil(a)
                yield "tool_call", {"call_id": a.id, "name": a.name, "arguments": a.arguments}

            if fin.stop_reason == "max_tokens" or tours_outils >= MAX_TOURS_OUTILS:
                if fin.stop_reason == "max_tokens":
                    erreur = "Appel d'outil tronqué : limite de jetons de sortie atteinte."
                else:
                    erreur = (f"Limite de {MAX_TOURS_OUTILS} tours d'appels d'outils atteinte ; "
                              "reformulez ou précisez la question.")
                resultats = []
                for a in appels:
                    parts.terminer_outil(a.id, "error", "Non exécuté", [])
                    resultats.append({"call_id": a.id, "name": a.name, "is_error": True,
                                      "content": "Non exécuté : " + erreur})
                    yield "tool_result", {"call_id": a.id, "status": "error",
                                          "summary": "Non exécuté", "documents": []}
                trace.append({"role": "tool", "results": resultats})
                break

            tours_outils += 1
            resultats: list[dict[str, Any]] = []
            trace.append({"role": "tool", "results": resultats})  # rempli au fil de l'eau
            sauver()
            for a in appels:
                if ctx.arret.is_set():
                    raise Interrompu()
                res = await asyncio.to_thread(executer, a)
                documents = [d.to_dict() for d in res.documents]
                statut = "error" if res.erreur else "done"
                resume = resume_resultat(res)
                parts.terminer_outil(a.id, statut, resume, documents)
                resultats.append({"call_id": a.id, "name": a.name, "content": res.texte,
                                  "is_error": res.erreur})
                sauver()
                yield "tool_result", {"call_id": a.id, "status": statut, "summary": resume,
                                      "documents": documents}
            derniere_sauvegarde = time.monotonic()
            if ctx.arret.is_set():
                raise Interrompu()
    except Interrompu:
        erreur = "Génération interrompue par l'utilisateur."
    except ErreurFournisseur as e:
        erreur = e.message
    except (asyncio.CancelledError, GeneratorExit):
        # Client déconnecté : on garde le message partiel.
        erreur = "Génération interrompue (connexion fermée)."
        _cloturer(parts, trace, erreur)
        sauver(final=True)
        st.toucher_conversation(cid)
        if conn is not None:
            conn.close()
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("génération %s", mid)
        erreur = f"Erreur interne : {e}"

    _cloturer(parts, trace, erreur)
    if conn is not None:
        conn.close()
    sauver(final=True)
    st.toucher_conversation(cid)
    if erreur:
        yield "error", {"message": erreur}
    yield "message_end", {"message_id": mid, "usage": usage.to_dict()}


def _cloturer(parts: Parts, trace: list[dict[str, Any]], erreur: str | None) -> None:
    """Passe les outils encore « running » en erreur et complète la trace en conséquence."""
    ids = parts.interrompre_outils("Interrompu")
    if not ids:
        return
    deja = {r["call_id"] for item in trace if item["role"] == "tool" for r in item["results"]}
    manquants = []
    for item in trace:
        if item["role"] == "assistant":
            for c in item["tool_calls"]:
                if c["id"] in ids and c["id"] not in deja:
                    manquants.append({"call_id": c["id"], "name": c["name"], "is_error": True,
                                      "content": "Interrompu : " + (erreur or "")})
    if manquants:
        if trace and trace[-1]["role"] == "tool":
            trace[-1]["results"].extend(manquants)
        else:
            trace.append({"role": "tool", "results": manquants})
