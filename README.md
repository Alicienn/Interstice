# Interstice

IA spécialisée en droit fiscal français. Elle s'appuie sur un corpus officiel **exhaustif et versionné**
(base LEGI de la DILA : tous les codes, lois et décrets consolidés, toutes les versions de chaque
article ; BOFiP-Impôts) et navigue dedans comme un juriste, catégorie par catégorie, au lieu d'un RAG
par similarité.

- Recherche préalable et choix d'architecture : [`docs/00-synthese.md`](docs/00-synthese.md) et [`docs/recherche/`](docs/recherche/)
- Plan d'implémentation : [`docs/superpowers/plans/`](docs/superpowers/plans/)
- Contrat de l'API web : [`docs/contrat-api.md`](docs/contrat-api.md)

## Mise en route

```bash
uv sync
uv run interstice download LEGI      # ~2,9 Go : archive globale + incréments quotidiens (reprenable)
uv run interstice ingest             # SQLite data/interstice.sqlite (idempotent : n'ingère que le nouveau)
uv run interstice index              # graphe des renvois + index plein texte
uv run interstice audit --tar        # preuve d'exhaustivité → data/audit/legi-*.md
```

Mise à jour quotidienne : relancer les quatre commandes, seules les nouvelles archives sont traitées.

## Utilisation

**Application web** (réglages des fournisseurs de modèles, chat, lecture des documents consultés) :

```bash
cd web && pnpm install && pnpm build && cd ..
uv run interstice serve              # http://127.0.0.1:8765
```

**Serveur MCP** (Claude Code, Claude Desktop, tout client MCP) :

```bash
claude mcp add interstice -- uv --directory C:/Users/alici/Documents/Interstice run interstice mcp
```

## Outils exposés à l'IA

| outil | rôle |
|---|---|
| `lister_textes` | textes disponibles (périmètre fiscal par défaut : CGI et annexes, LPF, CIBS, Code des douanes) |
| `sommaire` | arborescence officielle d'un texte ou d'une section à une date, avec nombre d'articles |
| `lire_article` | texte intégral, état, période de vigueur, chemin, NOTA, renvois (à une date donnée) |
| `historique_article` / `comparer_versions` | toutes les versions d'un article et leurs différences |
| `renvois` | graphe des renvois sortants et entrants d'un article |
| `rechercher` | plein texte (FTS5) sur les articles en vigueur à une date |
| `modifications` | articles créés, modifiés ou abrogés sur une période |

## Exhaustivité

Rien n'est filtré à l'ingestion. Chaque membre de chaque archive est compté et classé ; l'audit vérifie
que le nombre de XML comptés par `tar -t` égale le nombre ingéré, que chaque lien du sommaire et chaque
version annoncée existent, et que pour chaque code fiscal les articles en vigueur (d'après leurs dates)
sont exactement ceux qu'on atteint en descendant le sommaire.

## Tests

```bash
uv run pytest -q
```
