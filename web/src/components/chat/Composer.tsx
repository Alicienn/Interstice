import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Brain, Square } from "lucide-react";
import type { ModeleChoix } from "../../api/types";
import { niveauLabel } from "../../lib/format";

type Props = {
  streaming: boolean;
  stopping: boolean;
  models: ModeleChoix[];
  modelKey: string | null;
  onModelChange: (key: string) => void;
  thinking: string | null;
  onThinkingChange: (level: string | null) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  onOpenSettings: () => void;
  /** Texte injecté (suggestions) : { text, n } pour permettre de réinjecter le même texte. */
  preset?: { text: string; n: number } | null;
};

export function Composer(p: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const modele = p.models.find((m) => m.key === p.modelKey) ?? null;

  const groupes = useMemo(() => {
    const map = new Map<string, { name: string; items: ModeleChoix[] }>();
    for (const m of p.models) {
      const g = map.get(m.provider_id) ?? { name: m.provider_name, items: [] };
      g.items.push(m);
      map.set(m.provider_id, g);
    }
    return [...map.values()];
  }, [p.models]);

  useEffect(() => {
    if (p.preset) {
      setText(p.preset.text);
      ref.current?.focus();
    }
  }, [p.preset]);

  // Hauteur automatique
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 260)}px`;
  }, [text]);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  const canSend = !p.streaming && text.trim().length > 0 && modele !== null;

  const submit = () => {
    if (!canSend) return;
    p.onSend(text.trim());
    setText("");
  };

  const niveaux = modele?.thinking.supported ? modele.thinking.levels : [];

  return (
    <div className="composer-wrap">
      <form
        className={`composer ${p.streaming ? "busy" : ""}`}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          ref={ref}
          className="composer-input"
          rows={1}
          value={text}
          placeholder={
            modele ? "Posez une question sur un texte fiscal…" : "Configurez un modèle dans les réglages pour commencer."
          }
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          aria-label="Message"
        />
        <div className="composer-bar">
          {p.models.length === 0 ? (
            <button type="button" className="btn btn-sm" onClick={p.onOpenSettings}>
              Ajouter un modèle…
            </button>
          ) : (
            <select
              className="select select-compact"
              value={p.modelKey ?? ""}
              onChange={(e) => p.onModelChange(e.target.value)}
              aria-label="Modèle"
              title="Modèle"
            >
              {groupes.map((g) => (
                <optgroup key={g.name} label={g.name}>
                  {g.items.map((m) => (
                    <option key={m.key} value={m.key}>
                      {m.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          )}
          {modele?.thinking.supported &&
            (niveaux.length > 0 ? (
              <label className="thinking-select" title="Niveau de réflexion">
                <Brain size={14} aria-hidden />
                <select
                  className="select select-compact"
                  value={p.thinking ?? ""}
                  onChange={(e) => p.onThinkingChange(e.target.value || null)}
                  aria-label="Niveau de réflexion"
                >
                  <option value="">Réflexion désactivée</option>
                  {niveaux.map((l) => (
                    <option key={l} value={l}>
                      Réflexion {niveauLabel(l).toLowerCase()}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="thinking-auto" title="Ce modèle réfléchit sans niveau réglable">
                <Brain size={14} aria-hidden /> Réflexion automatique
              </span>
            ))}
          <span className="composer-hint">
            <span className="kbd">Entrée</span> envoyer · <span className="kbd">Maj</span>+<span className="kbd">Entrée</span>{" "}
            nouvelle ligne
          </span>
          {p.streaming ? (
            <button
              type="button"
              className="send-btn stop"
              onClick={p.onStop}
              disabled={p.stopping}
              title="Arrêter la génération"
              aria-label="Arrêter la génération"
            >
              <Square size={12} fill="currentColor" />
            </button>
          ) : (
            <button type="submit" className="send-btn" disabled={!canSend} title="Envoyer" aria-label="Envoyer">
              <ArrowUp size={17} />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
