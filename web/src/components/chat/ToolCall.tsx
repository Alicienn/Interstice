import { useState } from "react";
import { AlertTriangle, Check, ChevronDown, Loader2 } from "lucide-react";
import type { ToolPart } from "../../api/types";
import { nomOutil, resumeArguments } from "../../lib/format";
import { sameDoc, targetFromDoc, type ReaderTarget } from "../../lib/reader";
import { DocCard } from "./DocCard";

type Props = {
  part: ToolPart;
  activeTarget: ReaderTarget | null;
  onOpenTarget: (t: ReaderTarget) => void;
};

export function ToolCall({ part, activeTarget, onOpenTarget }: Props) {
  const [raw, setRaw] = useState(false);
  const args = resumeArguments(part.arguments);
  return (
    <div className={`tool tool-${part.status}`}>
      <div className="tool-line">
        <span className="tool-status" aria-label={part.status === "running" ? "en cours" : part.status === "done" ? "terminé" : "erreur"}>
          {part.status === "running" ? (
            <Loader2 size={13} className="spin" />
          ) : part.status === "done" ? (
            <Check size={13} />
          ) : (
            <AlertTriangle size={13} />
          )}
        </span>
        <span className="tool-name">{nomOutil(part.name)}</span>
        <span className="tool-args mono">
          {args.map(([k, v]) => (
            <span key={k} className="tool-arg">
              <span className="k">{k}</span>
              <span className="v">{v}</span>
            </span>
          ))}
        </span>
        {part.summary && <span className="tool-summary">{part.summary}</span>}
        <button
          className={`icon-btn sm tool-raw-toggle ${raw ? "on" : ""}`}
          onClick={() => setRaw((r) => !r)}
          title="Voir l'appel brut"
          aria-label="Voir l'appel brut"
          aria-expanded={raw}
        >
          <ChevronDown size={13} />
        </button>
      </div>
      {raw && (
        <pre className="tool-raw mono">
          {part.name}({JSON.stringify(part.arguments, null, 2)})
        </pre>
      )}
      {part.documents.length > 0 && (
        <div className="doc-cards">
          {part.documents.map((d, i) => (
            <DocCard
              key={`${d.kind}:${d.id}:${i}`}
              doc={d}
              active={sameDoc(activeTarget, d)}
              onOpen={() => onOpenTarget(targetFromDoc(d))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
