<div align="center">

<img src="assets/logo.svg" alt="Interstice" width="560">

<br>

**Ask a French tax question. Get an answer grounded in the actual text of the law, with the exact article, the version in force on the date that matters, and the doctrine that comments it.**

<br>

[![Python](https://img.shields.io/badge/Python-%E2%89%A5%203.11-3776ab?logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/badge/uv-managed-de5fe9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-TypeScript-61dafb?logo=react&logoColor=black)](https://react.dev)
[![SQLite](https://img.shields.io/badge/SQLite-FTS5-003b57?logo=sqlite&logoColor=white)](https://www.sqlite.org)
[![MCP](https://img.shields.io/badge/MCP-server-c8a96a)](https://modelcontextprotocol.io)
[![Data: LEGI + BOFiP](https://img.shields.io/badge/data-LEGI%20%C2%B7%20BOFiP-1d4ed8)](#the-corpus)
[![Last commit](https://img.shields.io/github/last-commit/Alicienn/Interstice?color=c8a96a)](https://github.com/Alicienn/Interstice/commits)
[![Stars](https://img.shields.io/github/stars/Alicienn/Interstice?style=flat&color=c8a96a)](https://github.com/Alicienn/Interstice/stargazers)

</div>

---

## What is Interstice?

Interstice is an AI assistant specialised in **French tax law**. Instead of guessing from memory, or retrieving "similar-looking" snippets the way a typical RAG does, it works the way a tax lawyer does: it opens the code, walks the table of contents, reads the article, checks what it said **on a given date**, follows the cross-references, then reads the administrative doctrine (BOFiP) that interprets it.

It runs **on your machine** with the AI model of your choice (OpenAI, Anthropic, Mistral, DeepSeek, OpenRouter, a local model through Ollama…). You can use it in two ways:

- as a **web app**: chat, model settings, and a reading pane that shows the documents the AI actually consulted;
- as an **MCP server**, to give Claude Code, Claude Desktop or any MCP client direct access to the French tax corpus.

> **Not legal advice.** Interstice is a research tool. Always check the cited articles yourself before relying on an answer.

## Why Interstice?

| The usual problem | What Interstice does |
|---|---|
| LLMs invent article numbers or quote repealed rules | Every article is read **verbatim** from the official corpus, with its state, validity period and path in the code. |
| "Which version applied in 2021?" is hard to answer | The corpus is **versioned**: every version of every article is stored, and any lookup can be made **as of a date**. |
| Similarity search misses the right article | The AI **navigates** the hierarchy (code → book → title → article) and follows cross-references instead of relying on vector similarity. |
| You can't tell what the AI really read | The reading pane shows **every document consulted**, and answers cite their sources. |
| Cloud tools see your questions | Everything runs locally; only the model provider you configure ever sees your prompts. |

## What you can ask

- *"What does the CGI say about the capital gains regime on the sale of a primary residence, and what changed in the last five years?"*
- *"Compare article 150 U of the CGI between 2018 and today."*
- *"Which articles were modified by the latest finance law?"*
- *"What does the BOFiP say about the deductibility of this expense, and which article does it rely on?"*

## The corpus

An **exhaustive and versioned** official corpus; nothing is filtered at ingestion:

- **LEGI** (DILA): every consolidated code, law and decree, with all versions of each article. The default tax scope covers the *Code général des impôts* (CGI) and its annexes, the *Livre des procédures fiscales* (LPF), the *Code des impositions sur les biens et services* (CIBS) and the *Code des douanes*.
- **BOFiP-Impôts**: the administrative tax doctrine.

Completeness is **audited, not assumed**: every archive member is counted and classified; the audit checks that the number of XML files counted by `tar -t` equals the number ingested, that every table-of-contents link and every announced version exists, and that, for each tax code, the articles in force (from their dates) are exactly the ones you reach by walking down the table of contents.

---

## Installation

**Requirements:** [uv](https://docs.astral.sh/uv/) (it installs the right Python for you) and [pnpm](https://pnpm.io) for the web interface. Around **3 GB** of disk space for the legal corpus.

```bash
git clone https://github.com/Alicienn/Interstice.git
cd Interstice
uv sync

uv run interstice download LEGI      # ~2.9 GB: global archive + daily increments (resumable)
uv run interstice ingest             # builds data/interstice.sqlite (idempotent: only ingests what is new)
uv run interstice index              # cross-reference graph + full-text index
uv run interstice audit --tar        # completeness proof → data/audit/legi-*.md
```

To update the corpus, re-run the same four commands: only new archives are processed.

## Run the web app

```bash
cd web && pnpm install && pnpm build && cd ..
uv run interstice serve              # http://127.0.0.1:8765
```

On Windows you can also double-click **`Interstice.cmd`**: it starts the server and opens your browser.

Then open **Settings**, add a provider (base URL + API key), click **Fetch models**, tick the ones you want, and start chatting. Any OpenAI-compatible API works, as does Anthropic's native API; local servers such as Ollama or LM Studio work too.

## Use it as an MCP server

Give any MCP client access to the corpus. With Claude Code:

```bash
claude mcp add interstice -- uv --directory /path/to/Interstice run interstice mcp
```

### Tools exposed to the AI

| Tool | What it does |
|---|---|
| `lister_textes` | Lists available texts (default tax scope: CGI and annexes, LPF, CIBS, Code des douanes). |
| `sommaire` | Official table of contents of a text or section at a given date, with article counts. |
| `lire_article` | Full text, state, validity period, path, NOTA and cross-references (as of a date). |
| `historique_article` / `comparer_versions` | All versions of an article and their differences. |
| `renvois` | Outgoing and incoming cross-reference graph of an article. |
| `rechercher` | Full-text search (FTS5) among the articles in force at a date. |
| `modifications` | Articles created, modified or repealed over a period. |

---

## Project layout

```
src/interstice/    Python package: CLI, ingestion, SQLite store, MCP server, FastAPI app
  legi/            LEGI parser and ingestion
  bofip/           BOFiP parser, plan and ingestion
  graph/           cross-reference graph
  audit/           exhaustiveness audits
  outils/          the tools exposed to the AI
  web/             HTTP API and LLM clients (OpenAI-compatible and Anthropic)
web/               React + TypeScript + Vite interface
labo-animations/   standalone playground for the answer-loading animations
docs/              research notes, architecture choices, API contract
tests/             pytest suite
```

Background reading (in French): [research synthesis](docs/00-synthese.md), [API contract](docs/contrat-api.md), [implementation plan](docs/superpowers/plans/).

## Tests

```bash
uv run pytest -q                     # backend
cd web && pnpm test && pnpm typecheck
```

`pnpm dev:mock` in `web/` runs the interface against an in-memory fake API, so you can try the UI without the corpus or an API key.

---

<div align="center">

Legal texts come from the open data published by the DILA (LEGI, BOFiP-Impôts).

Found a bug or have an idea? [Open an issue](https://github.com/Alicienn/Interstice/issues).

</div>
