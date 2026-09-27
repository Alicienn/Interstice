import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ComponentType } from "react";
import type { ProprietesPiste } from "./commun";
import { Caviardage } from "./pistes/Caviardage";
import { Encre } from "./pistes/Encre";
import { Rideau } from "./pistes/Rideau";
import { Signal } from "./pistes/Signal";
import { etatA, preparer, SCENARIOS } from "./scenario";

interface Piste {
  id: string;
  nom: string;
  resume: string;
  intention: string;
  quand: string;
  attente: string;
  C: ComponentType<ProprietesPiste>;
}

const PISTES: Piste[] = [
  {
    id: "encre", nom: "Encre", C: Encre,
    resume: "Mot à mot, chaque mot sèche comme de l'encre fraîche.",
    intention: "Le texte naît flou et teinté de bleu, puis se fixe ; une plume lumineuse suit le front d'écriture. Le travail préalable reste un journal compact qui se replie en bilan.",
    quand: "Réponses de longueur moyenne, lues pendant qu'elles s'écrivent. C'est la piste la plus proche du comportement actuel, avec plus de matière.",
    attente: "Très courte : le premier mot arrive dès que le modèle rédige.",
  },
  {
    id: "rideau", nom: "Rideau", C: Rideau,
    resume: "Rien pendant le travail, puis la réponse entière d'un seul geste.",
    intention: "Pendant que l'IA travaille, la scène montre ce qui se passe réellement : temps, tokens, sources lues. À la fin, les compteurs se retirent en pied de page et la réponse se révèle ligne à ligne derrière un masque.",
    quand: "Analyses longues où lire un brouillon partiel n'a pas d'intérêt : recherche de zones grises, consultations de plusieurs minutes.",
    attente: "Assumée : l'attente devient un tableau de bord plutôt qu'un vide.",
  },
  {
    id: "signal", nom: "Signal", C: Signal,
    resume: "Le rythme du modèle rendu visible en direct.",
    intention: "Une onde trace le débit de tokens : petites impulsions pendant la réflexion, pics à chaque lecture de source, masse dense pendant la rédaction. Le texte se développe comme une photo sous une tête de lecture.",
    quand: "Utilisateurs avancés qui veulent sentir si l'IA réfléchit, lit ou écrit, et comparer des modèles entre eux.",
    attente: "Rendue lisible : on voit l'IA travailler même quand aucun mot n'apparaît.",
  },
  {
    id: "caviardage", nom: "Caviardage", C: Caviardage,
    resume: "La réponse est là dès le départ, caviardée, puis déchiffrée.",
    intention: "La structure est posée d'emblée sous des bandeaux de caviardage. Chaque mot se déchiffre en faisant défiler des glyphes juridiques avant de se fixer. Aucun saut de mise en page pendant l'écriture.",
    quand: "Démonstrations et premières impressions : la piste la plus signée, qui ancre Interstice dans l'univers du document juridique.",
    attente: "Mise en scène : la forme de la réponse est connue avant son contenu.",
  },
];

const VITESSES = [0.5, 1, 2];

function useHorloge(total: number, vitesse: number, cleRejeu: number) {
  const [t, setTEtat] = useState(0);
  const [lecture, setLecture] = useState(true);
  const tRef = useRef(0);
  const setT = (v: number) => { tRef.current = v; setTEtat(v); };
  useEffect(() => { setT(0); setLecture(true); }, [cleRejeu, total]);
  useEffect(() => {
    if (!lecture) return;
    let id = 0;
    let derniere: number | null = null;
    const boucle = (maintenant: number) => {
      const dt = derniere === null ? 0 : maintenant - derniere;
      derniere = maintenant;
      const suivant = Math.min(total, tRef.current + dt * vitesse);
      setT(suivant);
      if (suivant >= total) { setLecture(false); return; }
      id = requestAnimationFrame(boucle);
    };
    id = requestAnimationFrame(boucle);
    return () => cancelAnimationFrame(id);
  }, [lecture, vitesse, total]);
  return { t, setT, lecture, setLecture };
}

function Scene({ piste, t, prep, onAgrandir, grande }: {
  piste: Piste; t: number; prep: ReturnType<typeof preparer>; onAgrandir?: () => void; grande?: boolean;
}) {
  const e = etatA(prep, t);
  const zone = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { // garde le front d'écriture en vue, comme un vrai fil de discussion
    const z = zone.current;
    if (!z) return;
    if (t === 0) { z.scrollTop = 0; return; }
    const front = z.querySelector<HTMLElement>("[data-front]");
    if (!front) return;
    const ecart = front.getBoundingClientRect().bottom - z.getBoundingClientRect().bottom + 72;
    if (ecart > 0) z.scrollTop += ecart;
  });
  const { C } = piste;
  return (
    <section className={`scene${grande ? " grande" : ""}`} aria-label={`Piste ${piste.nom}`}>
      <header className="scene-tete">
        <div>
          <h2>{piste.nom}</h2>
          <p>{piste.resume}</p>
        </div>
        {onAgrandir && <button className="discret" onClick={onAgrandir}>Agrandir</button>}
      </header>
      <div className="scene-fil" ref={zone}>
        <p className="question">{prep.sc.question}</p>
        <C p={prep} e={e} />
      </div>
    </section>
  );
}

export function App() {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id);
  const [vitesse, setVitesse] = useState(1);
  const [theme, setTheme] = useState<"sombre" | "clair">("sombre");
  const [cleRejeu, setCleRejeu] = useState(0);
  const [focus, setFocus] = useState<string | null>(null);
  const prep = useMemo(() => preparer(SCENARIOS.find((s) => s.id === scenarioId)!), [scenarioId]);
  const { t, setT, lecture, setLecture } = useHorloge(prep.total, vitesse, cleRejeu);

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => {
    const touche = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setFocus(null);
      if (ev.key === " " && (ev.target as HTMLElement).tagName !== "BUTTON" && (ev.target as HTMLElement).tagName !== "INPUT") {
        ev.preventDefault();
        if (t >= prep.total) setCleRejeu((k) => k + 1); else setLecture((l) => !l);
      }
      if (ev.key.toLowerCase() === "r") setCleRejeu((k) => k + 1);
    };
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [t, prep.total, setLecture]);

  const pisteFocus = PISTES.find((x) => x.id === focus);
  return (
    <div className="labo">
      <header className="barre">
        <div className="titre">
          <h1>Chargement des réponses</h1>
          <p>Quatre pistes pour Interstice, jouées sur la même horloge.</p>
        </div>
        <div className="commandes">
          <div className="segment" role="radiogroup" aria-label="Scénario">
            {SCENARIOS.map((s) => (
              <button key={s.id} role="radio" aria-checked={s.id === scenarioId}
                onClick={() => { setScenarioId(s.id); setCleRejeu((k) => k + 1); }}>{s.nom}</button>
            ))}
          </div>
          <div className="segment" role="radiogroup" aria-label="Vitesse">
            {VITESSES.map((v) => (
              <button key={v} role="radio" aria-checked={v === vitesse} onClick={() => setVitesse(v)}>
                {String(v).replace(".", ",")}×
              </button>
            ))}
          </div>
          <button className="discret" onClick={() => setTheme(theme === "sombre" ? "clair" : "sombre")}>
            {theme === "sombre" ? "Thème clair" : "Thème sombre"}
          </button>
        </div>
      </header>

      <div className="transport">
        <button className="principal" onClick={() => (t >= prep.total ? setCleRejeu((k) => k + 1) : setLecture(!lecture))}>
          {t >= prep.total ? "Rejouer" : lecture ? "Pause" : "Lecture"}
        </button>
        <input type="range" min={0} max={prep.total} step={10} value={t} aria-label="Position dans l'animation"
          onChange={(ev) => { setLecture(false); setT(Number(ev.target.value)); }} />
        <span className="temps">{(t / 1000).toFixed(1).replace(".", ",")} s</span>
      </div>

      {pisteFocus ? (
        <div className="focus">
          <Scene piste={pisteFocus} t={t} prep={prep} grande />
          <aside className="notes">
            <button className="discret retour" onClick={() => setFocus(null)}>Revenir aux quatre pistes</button>
            <h3>Intention</h3>
            <p>{pisteFocus.intention}</p>
            <h3>Quand l'utiliser</h3>
            <p>{pisteFocus.quand}</p>
            <h3>Rapport à l'attente</h3>
            <p>{pisteFocus.attente}</p>
            <nav className="autres" aria-label="Autres pistes">
              {PISTES.filter((x) => x.id !== focus).map((x) => (
                <button key={x.id} className="discret" onClick={() => setFocus(x.id)}>{x.nom}</button>
              ))}
            </nav>
          </aside>
        </div>
      ) : (
        <main className="grille">
          {PISTES.map((x) => <Scene key={x.id} piste={x} t={t} prep={prep} onAgrandir={() => setFocus(x.id)} />)}
        </main>
      )}
      <ul className="aide">
        <li><kbd>Espace</kbd> lecture ou pause</li>
        <li><kbd>R</kbd> rejouer</li>
        <li><kbd>Échap</kbd> revenir aux quatre pistes</li>
      </ul>
    </div>
  );
}
