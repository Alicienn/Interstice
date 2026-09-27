# Interstice — frontend web

React + TypeScript + Vite. Contrat d'API : `../docs/contrat-api.md` (types dans `src/api/types.ts`).

```sh
pnpm install
pnpm dev          # http://localhost:5173, proxy /api → http://127.0.0.1:8765 (backend FastAPI)
pnpm dev:mock     # même chose sans backend : API simulée en mémoire (VITE_MOCK=1, src/api/mock.ts)
pnpm typecheck    # TypeScript strict
pnpm test         # vitest : parseur SSE, réducteur du flux (dont rejeu /stream), historique du panneau
pnpm build        # → dist/ (chemins relatifs, servi par FastAPI sur « / »)
```

Maquette (`pnpm dev:mock`) :

- un message contenant « erreur » simule une erreur du fournisseur ; une URL de base contenant
  « erreur » fait échouer « Récupérer les modèles » (502) ;
- OpenRouter renvoie ~400 modèles (API ∪ catalogue models.dev) pour tester la liste ;
- les générations continuent « côté serveur » quand on quitte la conversation ; pour tester le
  rattachement, dans la console : `__intersticeMock.pauseApres(20)`, envoyer, changer de conversation,
  revenir, puis `__intersticeMock.reprendre()` ;
- BOFiP : petit plan (RPPM, CF, Actualités) et 5 documents fictifs abrégés.

Structure :

- `src/api/` — `types.ts` (contrat), `client.ts` (client unique), `sse.ts` (parseur SSE), `mock.ts` (maquette)
- `src/state/chatReducer.ts` — construction des messages à partir des événements SSE (envoi et rejeu)
- `src/components/` — `Sidebar`, `chat/`, `reader/` (panneau de lecture : codes et BOFiP), `settings/`,
  `ui/` (`Dropdown` : liste déroulante accessible, `Modal`)
- `src/styles/` — jetons clair/sombre (`base.css`) et feuilles par zone
