# Labo : chargement des réponses

Site autonome qui compare quatre pistes d'animation pour l'arrivée des réponses d'Interstice,
jouées sur une même horloge déterministe (pause, rejeu, curseur, vitesse, thème clair/sombre).

| piste | modèle | idée |
|---|---|---|
| Encre | progressif, mot à mot | chaque mot naît flou et teinté d'encre, puis sèche ; une plume suit le front d'écriture |
| Rideau | tout d'un coup | compteurs (temps, tokens, sources) pendant le travail, puis révélation ligne à ligne |
| Signal | progressif + débit | onde du débit de tokens en direct, texte « développé » sous une tête de lecture |
| Caviardage | structure d'abord | réponse caviardée d'emblée, chaque mot se déchiffre parmi des glyphes juridiques |

```bash
pnpm install
pnpm dev        # http://localhost:5190
```

Raccourcis : Espace (lecture/pause), R (rejouer), Échap (revenir aux quatre pistes).
Le moteur (`src/scenario.ts`) calcule l'état à l'instant `t` ; chaque piste (`src/pistes/`) n'est
qu'une vue de cet état, ce qui rend son intégration dans l'application directe.
