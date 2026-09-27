import { AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Message, ModeleChoix } from "../../api/types";
import { nombre, niveauLabel } from "../../lib/format";
import { decouperMessage } from "../../lib/journal";
import type { ReaderTarget } from "../../lib/reader";
import { INTERRUPTED_SUMMARY } from "../../state/chatReducer";
import { Travail } from "./Journal";
import { Markdown } from "./Markdown";
import { RideauLive } from "./Rideau";

type Props = {
  message: Message;
  live: boolean;
  /** Début de la génération (ms) pour le compteur en direct. */
  startedAt: number | null;
  models: ModeleChoix[];
  activeTarget: ReaderTarget | null;
  onOpenTarget: (t: ReaderTarget) => void;
};

export function MessageView({ message, live, startedAt, models, activeTarget, onOpenTarget }: Props) {
  // Rideau : la réponse ne se révèle (animation) que si on l'a vue se terminer ; un message
  // rouvert depuis l'historique s'affiche directement.
  const etaitLive = useRef(live);
  const [revele, setRevele] = useState(false);
  useEffect(() => {
    if (etaitLive.current && !live) setRevele(true);
    etaitLive.current = live;
  }, [live]);

  if (message.role === "user") {
    const text = message.parts.map((p) => (p.type === "text" ? p.text : "")).join("\n");
    return (
      <div className="msg msg-user">
        <div className="user-bubble">{text}</div>
      </div>
    );
  }

  const nav = { activeTarget, onOpenTarget };
  const parts = message.parts;
  const u = message.usage;

  // En cours : le rideau est baissé — temps, jetons, sources lues ; rien de la réponse.
  if (live) {
    return (
      <div className="msg msg-assistant live">
        <RideauLive message={message} depuis={startedAt ?? Date.now()} {...nav} />
      </div>
    );
  }

  // Terminé : tout le travail est replié dans une ligne, seul le texte final reste affiché.
  const { journal, final } = decouperMessage(parts);
  const interrompu =
    !!message.error || parts.some((p) => p.type === "tool" && p.status === "error" && p.summary === INTERRUPTED_SUMMARY);
  const modele = models.find((m) => m.key === message.model_key);

  return (
    <div className={`msg msg-assistant${revele ? " revele" : ""}`}>
      {(journal.length > 0 || interrompu) && (
        <Travail journal={journal} dureeMs={u?.duree_ms ?? null} interrompu={interrompu} {...nav} />
      )}
      {final.map((p, i) => (
        <div key={i} className="text-block">
          <Markdown text={p.text} />
        </div>
      ))}
      {message.error && <Erreur message={message.error} />}
      {(message.model_key || u) && (
        <div className="msg-meta">
          {message.model_key && <span>{modele ? `${modele.provider_name} · ${modele.label}` : message.model_key}</span>}
          {message.thinking_level && <span>réflexion {niveauLabel(message.thinking_level).toLowerCase()}</span>}
          {u && ((u.input_tokens ?? 0) > 0 || (u.output_tokens ?? 0) > 0) && (
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

function Erreur({ message }: { message: string }) {
  return (
    <div className="alert msg-error" role="alert">
      <AlertTriangle size={15} />
      <span>{message}</span>
    </div>
  );
}
