"""Serveur MCP (stdio) exposant les outils de navigation du corpus.

Utilisation avec Claude Code / Claude Desktop :
    claude mcp add interstice -- uv --directory <chemin du projet> run interstice mcp
"""

from __future__ import annotations

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from interstice.config import DB_PATH
from interstice.outils import OUTILS, get_outil
from interstice.store.db import connect

INSTRUCTIONS = (
    "Corpus du droit fiscal français (base LEGI officielle, toutes versions). Naviguez comme dans un code : "
    "`lister_textes` → `sommaire` (descendre section par section) → `lire_article`. Suivez `renvois` pour les "
    "interactions entre régimes, `historique_article` / `comparer_versions` pour l'évolution dans le temps, "
    "`rechercher` quand l'emplacement est inconnu. Citez toujours le numéro d'article et la version lue."
)


def _formater(res) -> str:
    if not res.documents:
        return res.texte
    refs = "\n".join(f"- [{d.kind}] {d.titre} — `{d.id}`" for d in res.documents)
    return f"{res.texte}\n\n<documents>\n{refs}\n</documents>"


def creer_serveur() -> Server:
    conn = connect(DB_PATH, lecture_seule=True)

    async def lister(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[
            types.Tool(name=o.nom, description=o.description, input_schema=o.parametres) for o in OUTILS])

    async def appeler(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        try:
            outil = get_outil(params.name)
        except LookupError as e:
            return types.CallToolResult(content=[types.TextContent(type="text", text=str(e))], is_error=True)
        res = await anyio.to_thread.run_sync(outil.appeler, conn, dict(params.arguments or {}))
        return types.CallToolResult(content=[types.TextContent(type="text", text=_formater(res))],
                                    is_error=res.erreur)

    return Server("interstice", version="0.1.0", instructions=INSTRUCTIONS,
                  on_list_tools=lister, on_call_tool=appeler)


def main() -> None:
    serveur = creer_serveur()

    async def run() -> None:
        async with stdio_server() as (lecture, ecriture):
            await serveur.run(lecture, ecriture, serveur.create_initialization_options())

    anyio.run(run)


if __name__ == "__main__":
    main()
