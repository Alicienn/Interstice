import { useEffect, useRef, useState } from "react";
import {
  BookOpenText,
  Check,
  Monitor,
  Moon,
  PenLine,
  Plus,
  ScrollText,
  Settings2,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import type { ConversationResume } from "../api/types";
import type { ThemeChoice } from "../hooks/useTheme";
import { ilYA } from "../lib/format";

type Props = {
  conversations: ConversationResume[] | null;
  error: string | null;
  currentId: string | null;
  vue: "chat" | "settings";
  theme: ThemeChoice;
  onCycleTheme: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onBrowse: () => void;
  onBrowseBofip: () => void;
  onSettings: () => void;
  onCloseMobile: () => void;
};

const THEME_LABEL: Record<ThemeChoice, string> = {
  system: "Thème : système",
  light: "Thème : clair",
  dark: "Thème : sombre",
};

export function Sidebar(p: Props) {
  const ThemeIcon = p.theme === "light" ? Sun : p.theme === "dark" ? Moon : Monitor;
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          §
        </span>
        <span className="brand-name">Interstice</span>
        <button className="icon-btn sm only-mobile" onClick={p.onCloseMobile} aria-label="Fermer le menu">
          <X size={16} />
        </button>
      </div>
      <p className="brand-tag">Droit fiscal · codes consolidés</p>

      <nav className="side-actions">
        <button className="side-action primary" onClick={p.onNew}>
          <Plus size={16} />
          Nouvelle conversation
        </button>
        <button className="side-action" onClick={p.onBrowse}>
          <BookOpenText size={16} />
          Parcourir les codes
        </button>
        <button className="side-action" onClick={p.onBrowseBofip}>
          <ScrollText size={16} />
          Doctrine BOFiP
        </button>
      </nav>

      <div className="side-section-title">Conversations</div>
      <div className="conv-list">
        {p.conversations === null ? (
          <div className="conv-skeletons">
            {[70, 55, 80].map((w, i) => (
              <div key={i} className="skeleton" style={{ height: 12, width: `${w}%`, margin: "12px 12px" }} />
            ))}
          </div>
        ) : p.conversations.length === 0 ? (
          <p className="conv-empty">{p.error ? `Erreur : ${p.error}` : "Aucune conversation pour l'instant."}</p>
        ) : (
          p.conversations.map((c) => (
            <ConvItem
              key={c.id}
              conv={c}
              active={c.id === p.currentId}
              onSelect={() => p.onSelect(c.id)}
              onRename={(t) => p.onRename(c.id, t)}
              onDelete={() => p.onDelete(c.id)}
            />
          ))
        )}
      </div>

      <div className="side-footer">
        <button className={`side-action ${p.vue === "settings" ? "active" : ""}`} onClick={p.onSettings}>
          <Settings2 size={16} />
          Réglages
        </button>
        <button className="icon-btn" onClick={p.onCycleTheme} title={THEME_LABEL[p.theme]} aria-label={THEME_LABEL[p.theme]}>
          <ThemeIcon size={16} />
        </button>
      </div>
    </aside>
  );
}

function ConvItem({
  conv,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  conv: ConversationResume;
  active: boolean;
  onSelect: () => void;
  onRename: (title: string) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [draft, setDraft] = useState(conv.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  useEffect(() => {
    if (!confirming) return;
    const t = setTimeout(() => setConfirming(false), 4000);
    return () => clearTimeout(t);
  }, [confirming]);

  const commit = async () => {
    const t = draft.trim();
    setEditing(false);
    if (t && t !== conv.title) await onRename(t);
    else setDraft(conv.title);
  };

  if (editing) {
    return (
      <div className="conv-item editing">
        <input
          ref={inputRef}
          className="conv-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void commit();
            if (e.key === "Escape") {
              setDraft(conv.title);
              setEditing(false);
            }
          }}
          onBlur={() => void commit()}
          aria-label="Nouveau titre"
        />
      </div>
    );
  }

  return (
    <div className={`conv-item ${active ? "active" : ""}`}>
      <button className="conv-main" onClick={onSelect} title={conv.title || "Sans titre"}>
        <span className="conv-title">{conv.title || <em className="muted">Sans titre</em>}</span>
        <span className="conv-date">
          {conv.generation_en_cours ? (
            <span className="conv-live" title="Réponse en cours de rédaction">
              <span className="live-dot" aria-hidden /> rédige…
            </span>
          ) : (
            ilYA(conv.updated_at)
          )}
        </span>
      </button>
      <div className="conv-tools">
        {confirming ? (
          <>
            <button className="icon-btn sm danger" onClick={() => void onDelete()} title="Confirmer la suppression" aria-label="Confirmer la suppression">
              <Check size={14} />
            </button>
            <button className="icon-btn sm" onClick={() => setConfirming(false)} title="Annuler" aria-label="Annuler">
              <X size={14} />
            </button>
          </>
        ) : (
          <>
            <button
              className="icon-btn sm"
              onClick={() => {
                setDraft(conv.title);
                setEditing(true);
              }}
              title="Renommer"
              aria-label="Renommer"
            >
              <PenLine size={13} />
            </button>
            <button className="icon-btn sm" onClick={() => setConfirming(true)} title="Supprimer" aria-label="Supprimer">
              <Trash2 size={13} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
