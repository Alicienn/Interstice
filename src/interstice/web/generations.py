"""Générations en arrière-plan, indépendantes des connexions HTTP.

Chaque génération tourne dans sa propre tâche asyncio et publie ses événements dans un tampon.
Les flux SSE ne font que s'y abonner : quitter la conversation (connexion fermée) désabonne le
client sans interrompre la rédaction ; revenir sur la conversation rejoue le tampon depuis le
début du message puis suit le direct. Seul `arreter()` (bouton stop, suppression) interrompt.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

log = logging.getLogger(__name__)

Evenement = tuple[str, dict[str, Any]]


class Generation:
    def __init__(self, conversation_id: str, arret: asyncio.Event):
        self.conversation_id = conversation_id
        self.arret = arret
        self.evenements: list[Evenement] = []
        self.message_id: str | None = None
        self.terminee = False
        self._cond = asyncio.Condition()

    async def publier(self, evenement: str, donnees: dict[str, Any]) -> None:
        async with self._cond:
            if evenement == "message_start":
                self.message_id = donnees.get("message_id")
            self.evenements.append((evenement, donnees))
            self._cond.notify_all()

    async def terminer(self) -> None:
        async with self._cond:
            self.terminee = True
            self._cond.notify_all()

    async def suivre(self, depuis: int = 0) -> AsyncIterator[Evenement]:
        """Rejoue les événements depuis `depuis`, puis suit le direct jusqu'à la fin."""
        i = depuis
        while True:
            async with self._cond:
                await self._cond.wait_for(lambda: len(self.evenements) > i or self.terminee)
                lot = self.evenements[i:]
                i = len(self.evenements)
                fini = self.terminee and i == len(self.evenements)
            for ev in lot:
                yield ev
            if fini:
                return


class Gestionnaire:
    """Registre des générations en cours (une par conversation au plus)."""

    def __init__(self) -> None:
        self._en_cours: dict[str, Generation] = {}
        self._taches: set[asyncio.Task] = set()  # références fortes : sinon la tâche peut être collectée

    def get(self, conversation_id: str) -> Generation | None:
        return self._en_cours.get(conversation_id)

    def __contains__(self, conversation_id: str) -> bool:
        return conversation_id in self._en_cours

    def demarrer(self, conversation_id: str, arret: asyncio.Event,
                 source: Callable[[], AsyncIterator[Evenement]]) -> Generation:
        if conversation_id in self._en_cours:
            raise RuntimeError("une génération est déjà en cours pour cette conversation")
        gen = Generation(conversation_id, arret)
        self._en_cours[conversation_id] = gen

        async def executer() -> None:
            try:
                async for evenement, donnees in source():
                    await gen.publier(evenement, donnees)
            except Exception:  # noqa: BLE001 — agent.generer gère déjà ses erreurs ; filet de sécurité
                log.exception("génération %s", conversation_id)
                await gen.publier("error", {"message": "Erreur interne pendant la génération."})
            finally:
                if self._en_cours.get(conversation_id) is gen:
                    del self._en_cours[conversation_id]
                await gen.terminer()

        tache = asyncio.create_task(executer(), name=f"generation-{conversation_id}")
        self._taches.add(tache)
        tache.add_done_callback(self._taches.discard)
        return gen

    def arreter(self, conversation_id: str) -> bool:
        gen = self._en_cours.get(conversation_id)
        if gen:
            gen.arret.set()
        return gen is not None

    async def fermer(self) -> None:
        """Arrêt du serveur : interrompt proprement les générations en cours."""
        for gen in list(self._en_cours.values()):
            gen.arret.set()
        if self._taches:
            await asyncio.wait(self._taches, timeout=10)
