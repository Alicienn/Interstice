import { useState } from "react";
import { ChevronRight, Lightbulb } from "lucide-react";

export function ThinkingBlock({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false);
  const mots = text.trim() ? text.trim().split(/\s+/).length : 0;
  return (
    <div className={`thinking ${open ? "open" : ""} ${live ? "live" : ""}`}>
      <button className="thinking-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <ChevronRight size={14} className="chev" />
        <Lightbulb size={14} />
        {live ? (
          <span className="thinking-live">
            Réfléchit<span className="dots" aria-hidden><i>.</i><i>.</i><i>.</i></span>
          </span>
        ) : (
          <span>Réflexion</span>
        )}
        <span className="thinking-meta">{mots > 0 ? `${mots} mots` : ""}</span>
      </button>
      {open && <div className="thinking-body">{text}</div>}
    </div>
  );
}
