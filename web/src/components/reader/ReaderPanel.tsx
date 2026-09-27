import { useCallback, useEffect, useRef, type PointerEvent as RPointerEvent } from "react";
import { ArrowLeft, ArrowRight, BookOpenText, X } from "lucide-react";
import { useStoredState } from "../../hooks/useStoredState";
import type { ReaderHistory, ReaderTarget } from "../../lib/reader";
import { targetKey } from "../../lib/reader";
import { ArticleView } from "./ArticleView";
import { BofipPlanView } from "./BofipPlanView";
import { BofipView } from "./BofipView";
import { NodeView } from "./NodeView";
import { SearchView } from "./SearchView";
import { TextesView } from "./TextesView";

type Props = {
  history: ReaderHistory;
  onNavigate: (t: ReaderTarget) => void;
  onMove: (delta: number) => void;
  onClose: () => void;
};

const MIN_W = 380;
const DEFAULT_W = 580;

const KIND_LABEL: Record<ReaderTarget["kind"], string> = {
  article: "Article",
  section: "Plan",
  texte: "Plan du texte",
  recherche: "Recherche",
  textes: "Corpus",
  bofip: "BOFiP",
  "bofip-plan": "Plan du BOFiP",
};

export function ReaderPanel({ history, onNavigate, onMove, onClose }: Props) {
  const [width, setWidth] = useStoredState("interstice.readerWidth", DEFAULT_W);
  const bodyRef = useRef<HTMLDivElement>(null);
  const target = history.entries[history.index];

  // Remonte en haut à chaque navigation.
  useEffect(() => {
    bodyRef.current?.scrollTo({ top: 0 });
  }, [history.index, history.entries]);

  // Raccourcis : Alt+← / Alt+→ ; Échap ferme.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "ArrowLeft") onMove(-1);
      else if (e.altKey && e.key === "ArrowRight") onMove(1);
      else if (e.key === "Escape" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onMove, onClose]);

  const startResize = useCallback(
    (e: RPointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = width;
      const max = Math.max(MIN_W, window.innerWidth * 0.65);
      document.body.classList.add("resizing");
      const move = (ev: PointerEvent) => setWidth(Math.round(Math.min(max, Math.max(MIN_W, startW + startX - ev.clientX))));
      // Fin du glissement, quelle qu'en soit la cause : la classe « resizing » ne doit jamais rester
      // posée (elle désactive les événements de pointeur, donc le défilement, du panneau).
      const up = () => {
        document.body.classList.remove("resizing");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", up);
        window.removeEventListener("blur", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
      window.addEventListener("pointercancel", up);
      window.addEventListener("blur", up);
    },
    [width, setWidth],
  );

  const openArticle = useCallback((id: string) => onNavigate({ kind: "article", id }), [onNavigate]);

  return (
    <aside className="reader" style={{ ["--reader-w" as string]: `${width}px` }} aria-label="Panneau de lecture">
      <div
        className="reader-resize"
        onPointerDown={startResize}
        onDoubleClick={() => setWidth(DEFAULT_W)}
        role="separator"
        aria-orientation="vertical"
        title="Glisser pour redimensionner (double-clic : largeur par défaut)"
      />
      <header className="reader-head">
        <button className="icon-btn" onClick={() => onMove(-1)} disabled={history.index <= 0} title="Précédent (Alt+←)" aria-label="Précédent">
          <ArrowLeft size={16} />
        </button>
        <button
          className="icon-btn"
          onClick={() => onMove(1)}
          disabled={history.index >= history.entries.length - 1}
          title="Suivant (Alt+→)"
          aria-label="Suivant"
        >
          <ArrowRight size={16} />
        </button>
        <span className="reader-kind">{target ? KIND_LABEL[target.kind] : ""}</span>
        <span className="reader-spacer" />
        <button className="btn btn-ghost btn-sm" onClick={() => onNavigate({ kind: "textes" })} title="Parcourir les codes et le BOFiP">
          <BookOpenText size={14} /> Parcourir
        </button>
        <button className="icon-btn" onClick={onClose} title="Fermer (Échap)" aria-label="Fermer le panneau">
          <X size={17} />
        </button>
      </header>
      <div className="reader-body" ref={bodyRef}>
        {target && <ReaderContent key={targetKey(target)} target={target} onNavigate={onNavigate} onArticle={openArticle} />}
      </div>
    </aside>
  );
}

function ReaderContent({
  target,
  onNavigate,
  onArticle,
}: {
  target: ReaderTarget;
  onNavigate: (t: ReaderTarget) => void;
  onArticle: (id: string) => void;
}) {
  switch (target.kind) {
    case "article":
      return <ArticleView id={target.id} date={target.date ?? null} onNavigate={onNavigate} onArticle={onArticle} />;
    case "section":
    case "texte":
      return <NodeView kind={target.kind} id={target.id} date={target.date ?? null} onNavigate={onNavigate} />;
    case "recherche":
      return (
        <SearchView
          q={target.q}
          corpus={target.corpus ?? "codes"}
          texte={target.texte ?? null}
          serie={target.serie ?? null}
          date={target.date ?? null}
          onNavigate={onNavigate}
        />
      );
    case "textes":
      return <TextesView onNavigate={onNavigate} />;
    case "bofip":
      return <BofipView id={target.id} ancre={target.ancre ?? null} onNavigate={onNavigate} onArticle={onArticle} />;
    case "bofip-plan":
      return <BofipPlanView noeud={target.noeud} trail={target.trail ?? []} onNavigate={onNavigate} />;
  }
}
