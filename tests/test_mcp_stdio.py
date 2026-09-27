"""Test de bout en bout : lance `interstice mcp` en sous-processus et dialogue en MCP via stdio."""

import os
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_mcp_liste_et_appelle(base_mini):
    chemin = base_mini.execute("PRAGMA database_list").fetchone()[2]
    params = StdioServerParameters(command=sys.executable, args=["-m", "interstice.cli", "mcp"],
                                   env={**os.environ, "INTERSTICE_DB": chemin})

    async def scenario():
        async with stdio_client(params) as (lecture, ecriture):
            async with ClientSession(lecture, ecriture) as session:
                await session.initialize()
                outils = await session.list_tools()
                noms = {t.name for t in outils.tools}
                assert {"sommaire", "lire_article", "rechercher", "renvois"} <= noms
                res = await session.call_tool("lire_article", {"id": "LEGIARTI000032944414"})
                assert not res.is_error
                assert "I.-Les centres de formalités" in res.content[0].text
                err = await session.call_tool("lire_article", {"texte": "Code de commerce", "num": "Z999"})
                assert err.is_error

    anyio.run(scenario)
