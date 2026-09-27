import { advance } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { FournisseurHorloge, useHorlogeScene } from "./horloge";
import { Codex } from "./pistes/Codex";
import { Constellation } from "./pistes/Constellation";
import { Marbrure } from "./pistes/Marbrure";
import { Nuee } from "./pistes/Nuee";
import { Rideau } from "./pistes/Rideau";
import { Synapses } from "./pistes/Synapses";
import { preparer, SCENARIOS } from "./scenario";

interface Piste {
  id: string;
  nom: string;
  resume: string;
  intention: string;
  quand: string;
  technique: string;
  retenue?: boolean;
  C: ComponentType;
}

function SceneRideau() {
  const { prep, e } = useHorlogeScene();
  return <div className="stage stage-rideau"><Rideau p={prep} e={e} /></div>;
}

const PISTES: Piste[] = [
  {
    id: "synapses", nom: "Synapses", C: Synapses,
    resume: "Un réseau neuronal en 2D, gris et blanc, qui s'évapore dans le texte.",
    intention: "Des neurones naissent à des positions pseudo-aléatoires et se relient par des courbes fines ; des influx parcourent les connexions et chaque source consultée déclenche une décharge qui se propage dans une grappe. Les neurones anciens montent en s'estompant. À la rédaction, tout s'évapore vers le haut et chaque mot se condense à partir de grains.",
    quand: "Pour montrer un raisonnement vivant sans couleur ni effet criard, dans la sobriété de l'interface.",
    technique: "Canvas 2D : réseau généré de façon déterministe (graine fixe), courbes de Bézier quadratiques avec croissance par De Casteljau, ondes de décharge, grains par mot mesurés sur le texte HTML.",
  },
  {
    id: "constellation", nom: "Constellation", C: Constellation,
    resume: "Le graphe des renvois du CGI, parcouru en 3D.",
    intention: "Les articles forment une galaxie reliée par leurs renvois. Chaque source lue s'allume, un filament trace le chemin de l'IA et la caméra vole jusqu'à elle. À la rédaction, la galaxie s'effondre en spirale dans un noyau d'où jaillit le texte.",
    quand: "Pour rendre visible ce qui distingue Interstice : il ne devine pas, il navigue dans le droit.",
    technique: "Points en shader avec effondrement en spirale dans le vertex shader, filaments additifs, caméra pilotée par l'étape en cours, bloom.",
  },
  {
    id: "codex", nom: "Codex", C: Codex,
    resume: "Un code ouvert dont les pages tournent vers les articles lus.",
    intention: "Pendant la réflexion, les pages défilent en rafale ; pour chaque source, une page tourne lentement jusqu'à l'article, surligné. À la rédaction, la caméra plonge dans la page, qui devient la feuille de réponse.",
    quand: "Pour une première impression forte et un univers juridique immédiatement lisible.",
    technique: "Courbure des pages calculée dans le vertex shader, textures de page peintes en canvas, ombre de contact, travelling de caméra.",
  },
  {
    id: "marbrure", nom: "Marbrure", C: Marbrure,
    resume: "Un champ d'encre liquide qui respire au rythme du modèle.",
    intention: "L'encre tourbillonne comme un papier marbré ; le débit de tokens règle sa turbulence et chaque source lue y lance une onde. À la rédaction, l'encre se retire vers le haut et les mots en émergent, encore liquides, avant de se figer.",
    quand: "Pour une attente contemplative et élégante, sans surcharge d'information.",
    technique: "Shader plein cadre à double déformation du domaine (fbm), ondes de choc, filtre SVG de déplacement sur les mots en cours d'écriture.",
  },
  {
    id: "nuee", nom: "Nuée", C: Nuee,
    resume: "Des milliers de particules qui se posent sur les lettres.",
    intention: "Une nuée tourbillonne pendant le travail et s'agite avec le débit ; chaque source lue provoque une onde de choc. À la rédaction, chaque mot attire exactement les particules qui dessinent ses lettres, puis le texte net les remplace.",
    quand: "Pour faire de chaque réponse un moment, et montrer que le texte se forme à partir du travail effectué.",
    technique: "14 000 particules dans un vertex shader, cibles échantillonnées dans une mise en page canvas identique au HTML, trajectoires en arc, bloom.",
  },
  {
    id: "rideau", nom: "Rideau", C: SceneRideau, retenue: true,
    resume: "Retenue : rien pendant le travail, puis la réponse d'un seul geste.",
    intention: "Chronomètre à chiffres roulants, tokens et sources lues pendant le travail ; à la fin, la réponse se révèle ligne à ligne derrière un masque.",
    quand: "Analyses longues où un brouillon partiel n'a pas d'intérêt.",
    technique: "HTML et CSS : compteurs mécaniques, révélation par masque.",
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
  return { t, tRef, setT, lecture, setLecture };
}

declare global {
  interface Window { __aller?: (ms: number) => void; __avancer?: () => void }
}

// ?piste=nuee&t=9000&scenario=direct : ouvre une piste figée à un instant (captures, liens de revue)
const PARAMS = new URLSearchParams(location.search);

export function App() {
  const [scenarioId, setScenarioId] = useState(PARAMS.get("scenario") ?? SCENARIOS[0].id);
  const [vitesse, setVitesse] = useState(1);
  const [cleRejeu, setCleRejeu] = useState(0);
  const [pisteId, setPisteId] = useState(PARAMS.get("piste") ?? PISTES[0].id);
  const prep = useMemo(() => preparer(SCENARIOS.find((s) => s.id === scenarioId)!), [scenarioId]);
  const { t, tRef, setT, lecture, setLecture } = useHorloge(prep.total, vitesse, cleRejeu);
  useEffect(() => {
    const fige = PARAMS.get("t");
    if (fige !== null) { setLecture(false); setT(Number(fige)); }
  }, []); // eslint-disable-line
  const piste = PISTES.find((x) => x.id === pisteId)!;

  useEffect(() => { // outils de vérification (onglet en arrière-plan : pas de requestAnimationFrame)
    window.__aller = (ms) => { setLecture(false); setT(ms); };
    window.__avancer = () => advance(performance.now());
  });
  useEffect(() => {
    const touche = (ev: KeyboardEvent) => {
      const cible = (ev.target as HTMLElement).tagName;
      if (cible === "INPUT") return;
      if (ev.key === " " && cible !== "BUTTON") {
        ev.preventDefault();
        if (t >= prep.total) setCleRejeu((k) => k + 1); else setLecture((l) => !l);
      }
      if (ev.key.toLowerCase() === "r") setCleRejeu((k) => k + 1);
      const n = Number(ev.key);
      if (n >= 1 && n <= PISTES.length) { setPisteId(PISTES[n - 1].id); setCleRejeu((k) => k + 1); }
    };
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [t, prep.total, setLecture]);

  const { C } = piste;
  return (
    <div className="labo">
      <header className="barre">
        <div className="titre">
          <h1>Chargement des réponses</h1>
          <p>Synapses en tête ; les pistes 3D et Rideau, déjà retenue, restent consultables.</p>
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
        </div>
      </header>

      <nav className="onglets" aria-label="Pistes">
        {PISTES.map((x, k) => (
          <button key={x.id} aria-current={x.id === pisteId ? "page" : undefined}
            onClick={() => { setPisteId(x.id); setCleRejeu((c) => c + 1); }}>
            <span className="onglet-nom">{x.nom}{x.retenue && <span className="retenue">retenue</span>}</span>
            <kbd>{k + 1}</kbd>
          </button>
        ))}
      </nav>

      <div className="plateau">
        <div className="colonne-scene">
          <p className="question">{prep.sc.question}</p>
          <FournisseurHorloge t={t} tRef={tRef} prep={prep}>
            <C key={`${pisteId}-${scenarioId}`} />
          </FournisseurHorloge>
          <div className="transport">
            <button className="principal" onClick={() => (t >= prep.total ? setCleRejeu((k) => k + 1) : setLecture(!lecture))}>
              {t >= prep.total ? "Rejouer" : lecture ? "Pause" : "Lecture"}
            </button>
            <input type="range" min={0} max={prep.total} step={10} value={t} aria-label="Position dans l'animation"
              onChange={(ev) => { setLecture(false); setT(Number(ev.target.value)); }} />
            <span className="temps">{(t / 1000).toFixed(1).replace(".", ",")} s</span>
          </div>
        </div>
        <aside className="notes">
          <h2>{piste.nom}</h2>
          <p className="resume">{piste.resume}</p>
          <h3>Ce qui se passe</h3>
          <p>{piste.intention}</p>
          <h3>Pourquoi cette piste</h3>
          <p>{piste.quand}</p>
          <h3>Technique</h3>
          <p>{piste.technique}</p>
          <ul className="aide">
            <li><kbd>Espace</kbd> lecture ou pause</li>
            <li><kbd>R</kbd> rejouer</li>
            <li><kbd>1</kbd>–<kbd>6</kbd> changer de piste</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}
