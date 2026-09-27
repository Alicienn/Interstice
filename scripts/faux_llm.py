"""Faux fournisseur compatible OpenAI (Chat Completions en flux) pour tester l'application sans clé API.

Scénario déterministe, piloté par le nombre de résultats d'outils déjà présents dans la requête :
1. réflexion + appels `sommaire` (CGI) et `lire_article` (CGI 150-0 B ter) ;
2. appel `bofip_pour_article` (doctrine de l'article) ;
3. réponse rédigée lentement (un mot toutes les ~0,15 s) : laisse le temps de quitter la conversation.

    uv run --no-sync python scripts/faux_llm.py        # écoute sur http://127.0.0.1:8799/v1
Puis, dans l'application : fournisseur « Compatible OpenAI », URL http://127.0.0.1:8799/v1, clé quelconque.
"""

from __future__ import annotations

import asyncio
import json
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
REPONSE = (
    "D'après l'article 150-0 B ter du CGI, la plus-value d'apport de titres à une société contrôlée par "
    "l'apporteur bénéficie d'un report d'imposition. Le report prend fin notamment en cas de cession des "
    "titres reçus en rémunération de l'apport, ou si la société bénéficiaire cède les titres apportés dans "
    "les trois ans sans réinvestir au moins 60 % du produit dans une activité économique. Ce texte de test "
    "est rédigé lentement pour vérifier qu'une génération continue quand on quitte la conversation."
).split(" ")


def _chunk(delta: dict, fin: str | None = None) -> str:
    c = {"id": "faux", "object": "chat.completion.chunk", "created": int(time.time()), "model": "faux-juriste",
         "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
    return f"data: {json.dumps(c, ensure_ascii=False)}\n\n"


def _appel(i: int, nom: str, args: dict) -> dict:
    return {"tool_calls": [{"index": i, "id": f"call_{nom}_{i}", "type": "function",
                            "function": {"name": nom, "arguments": json.dumps(args, ensure_ascii=False)}}]}


@app.get("/v1/models")
def modeles():
    return {"object": "list", "data": [{"id": "faux-juriste", "object": "model", "owned_by": "test"}]}


@app.post("/v1/chat/completions")
async def completions(req: Request):
    corps = await req.json()
    n_outils = sum(1 for m in corps.get("messages", []) if m.get("role") == "tool")

    async def flux():
        if n_outils == 0:
            for mot in "Je dois situer l'apport-cession dans le CGI puis lire l'article.".split(" "):
                yield _chunk({"reasoning_content": mot + " "})
                await asyncio.sleep(0.05)
            yield _chunk(_appel(0, "sommaire", {"texte": "CGI"}))
            yield _chunk(_appel(1, "lire_article", {"texte": "CGI", "num": "150-0 B ter"}))
            yield _chunk({}, "tool_calls")
        elif n_outils == 2:
            yield _chunk({"content": "Je vérifie la doctrine administrative. "})
            yield _chunk(_appel(0, "bofip_pour_article", {"texte": "CGI", "num": "150-0 B ter"}))
            yield _chunk({}, "tool_calls")
        else:
            for mot in REPONSE:
                yield _chunk({"content": mot + " "})
                await asyncio.sleep(0.15)
            yield _chunk({}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(flux(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8799, log_level="warning")
