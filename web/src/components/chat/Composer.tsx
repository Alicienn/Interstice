import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Brain, Square } from "lucide-react";
import type { ModeleChoix } from "../../api/types";
import { modelDropdownOptions, thinkingDropdownOptions } from "../../lib/options";
import { Dropdown } from "../ui/Dropdown";

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

  const modelOptions = useMemo(() => modelDropdownOptions(p.models), [p.models]);
  const niveaux = modele?.thinking.supported ? modele.thinking.levels : [];
  const thinkingOptions = useMemo(() => thinkingDropdownOptions(niveaux), [niveaux]);

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
            <Dropdown
              ariaLabel="Modèle"
              title="Modèle"
              value={p.modelKey ?? ""}
              options={modelOptions}
              onChange={p.onModelChange}
              searchPlaceholder="Rechercher un modèle…"
              minPopoverWidth={300}
            />
          )}
          {modele?.thinking.supported &&
            (niveaux.length > 0 ? (
              <Dropdown
                ariaLabel="Niveau de réflexion"
                title="Niveau de réflexion"
                icon={<Brain size={14} />}
                value={p.thinking ?? ""}
                options={thinkingOptions}
                onChange={(v) => p.onThinkingChange(v || null)}
                searchable={false}
                minPopoverWidth={220}
              />
            ) : (
              <span className="thinking-auto" title="Ce modèle réfléchit sans niveau réglable">
                <Brain size={14} aria-hidden /> Réflexion automatique
              </span>
            ))}
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
