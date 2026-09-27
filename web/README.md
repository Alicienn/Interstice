# Interstice — frontend web

React + TypeScript + Vite. Contrat d'API : `../docs/contrat-api.md` (types dans `src/api/types.ts`).

```sh
pnpm install
pnpm dev          # http://localhost:5173, proxy /api → http://127.0.0.1:8765 (backend FastAPI)
pnpm dev:mock     # même chose sans backend : API simulée en mémoire (VITE_MOCK=1, src/api/mock.ts)
pnpm typecheck    # TypeScript strict
pnpm test         # vitest : parseur SSE, réducteur du flux
pnpm build        # → dist/ (chemins relatifs, servi par FastAPI sur « / »)
```

En mode maquette, un message contenant le mot « erreur » simule une erreur du fournisseur,
et une URL de base contenant « erreur » fait échouer « Récupérer les modèles » (502).

Structure :

- `src/api/` — `types.ts` (contrat), `client.ts` (client unique), `sse.ts` (parseur SSE), `mock.ts` (maquette)
- `src/state/chatReducer.ts` — construction du message assistant à partir des événements SSE
- `src/components/` — `Sidebar`, `chat/`, `reader/` (panneau de lecture), `settings/`, `ui/`
- `src/styles/` — jetons de thème clair/sombre (`base.css`) et feuilles par zone
