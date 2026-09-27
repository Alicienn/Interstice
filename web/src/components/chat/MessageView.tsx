import { AlertTriangle } from "lucide-react";
import type { Message, ModeleChoix, Part, ToolPart } from "../../api/types";
import { nombre, niveauLabel } from "../../lib/format";
import type { ReaderTarget } from "../../lib/reader";
import { Markdown } from "./Markdown";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolCall } from "./ToolCall";

type Props = {
  message: Message;
  live: boolean;
  models: ModeleChoix[];
  activeTarget: ReaderTarget | null;
  onOpenTarget: (t: ReaderTarget) => void;
};

type Bloc =
  | { kind: "part"; part: Exclude<Part, ToolPart>; index: number }
  | { kind: "tools"; parts: ToolPart[]; index: number };

/** Regroupe les appels d'outils consécutifs en un seul « journal ». */
function blocs(parts: Part[]): Bloc[] {
  const out: Bloc[] = [];
  parts.forEach((p, index) => {
    if (p.type === "tool") {
      const last = out[out.length - 1];
      if (last && last.kind === "tools") last.parts.push(p);
      else out.push({ kind: "tools", parts: [p], index });
    } else out.push({ kind: "part", part: p, index });
  });
  return out;
}

export function MessageView({ message, live, models, activeTarget, onOpenTarget }: Props) {
  if (message.role === "user") {
    const text = message.parts.map((p) => (p.type === "text" ? p.text : "")).join("\n");
    return (
      <div className="msg msg-user">
        <div className="user-bubble">{text}</div>
      </div>
    );
  }

  const parts = message.parts;
  const lastIndex = parts.length - 1;
  const modele = models.find((m) => m.key === message.model_key);
  const u = message.usage;

  return (
    <div className={`msg msg-assistant ${live ? "live" : ""}`}>
      {parts.length === 0 && live && !message.error && (
        <div className="pending">
          <span className="pending-bar" />
          Préparation de la réponse…
        </div>
      )}
      {blocs(parts).map((b) => {
        if (b.kind === "tools") {
          return (
            <div className="tool-log" key={`t${b.index}`}>
              {b.parts.map((p) => (
                <ToolCall key={p.call_id} part={p} activeTarget={activeTarget} onOpenTarget={onOpenTarget} />
              ))}
            </div>
          );
        }
        const p = b.part;
        if (p.type === "thinking")
          return <ThinkingBlock key={`p${b.index}`} text={p.text} live={live && b.index === lastIndex} />;
        return (
          <div key={`p${b.index}`} className={live && b.index === lastIndex ? "text-live" : undefined}>
            <Markdown text={p.text} />
          </div>
        );
      })}
      {message.error && (
        <div className="alert msg-error" role="alert">
          <AlertTriangle size={15} />
          <span>{message.error}</span>
        </div>
      )}
      {!live && (message.model_key || u) && (
        <div className="msg-meta">
          {message.model_key && (
            <span>{modele ? `${modele.provider_name} · ${modele.label}` : message.model_key}</span>
          )}
          {message.thinking_level && <span>réflexion {niveauLabel(message.thinking_level).toLowerCase()}</span>}
          {u && (u.input_tokens != null || u.output_tokens != null) && (
            <span title="Jetons en entrée → en sortie (dont lus depuis le cache)">
              {nombre(u.input_tokens ?? 0)} → {nombre(u.output_tokens ?? 0)} jetons
              {u.cache_read_tokens ? ` · ${nombre(u.cache_read_tokens)} en cache` : ""}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
