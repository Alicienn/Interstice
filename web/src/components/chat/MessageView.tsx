import { AlertTriangle, Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Message, ModeleChoix, Usage } from "../../api/types";
import { compact, nombre, totalJetons } from "../../lib/format";
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
      <div className="msg-meta">
        {message.model_key && (
          <span className="meta-item" title={modele ? `${modele.label} · ${modele.provider_name}` : message.model_key}>
            {modele?.label ?? message.model_key.split("::").pop()}
          </span>
        )}
        {u && totalJetons(u) > 0 && <Jetons usage={u} />}
        {final.length > 0 && <Copier markdown={final.map((p) => p.text).join("\n\n")} />}
      </div>
    </div>
  );
}

/** Total des jetons ; le détail (entrée, cache, sortie) s'affiche au survol ou au focus. */
function Jetons({ usage: u }: { usage: Usage }) {
  const entree = u.input_tokens ?? 0;
  const cache = Math.min(u.cache_read_tokens ?? 0, entree);
  const sortie = u.output_tokens ?? 0;
  return (
    <span className="meta-item meta-jetons" tabIndex={0}>
      {compact(totalJetons(u))} jetons
      <span className="infobulle" role="tooltip">
        <span>Entrée</span>
        <b>{nombre(entree - cache)}</b>
        <span>Cache (lecture)</span>
        <b>{nombre(cache)}</b>
        <span>Sortie</span>
        <b>{nombre(sortie)}</b>
        <span className="infobulle-total">Total</span>
        <b className="infobulle-total">{nombre(entree + sortie)}</b>
      </span>
    </span>
  );
}

/** Copie la réponse finale (sans la réflexion ni le journal d'outils) au format Markdown. */
function Copier({ markdown }: { markdown: string }) {
  const [copie, setCopie] = useState(false);
  useEffect(() => {
    if (!copie) return;
    const t = setTimeout(() => setCopie(false), 1600);
    return () => clearTimeout(t);
  }, [copie]);
  const copier = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
    } catch {
      // Contexte non sécurisé ou permission refusée : repli sur une zone de texte temporaire.
      const zone = document.createElement("textarea");
      zone.value = markdown;
      zone.style.position = "fixed";
      zone.style.opacity = "0";
      document.body.appendChild(zone);
      zone.select();
      document.execCommand("copy");
      zone.remove();
    }
    setCopie(true);
  };
  const libelle = copie ? "Copié" : "Copier la réponse (Markdown)";
  return (
    <button
      type="button"
      className={`icon-btn sm meta-copier${copie ? " fait" : ""}`}
      onClick={() => void copier()}
      title={libelle}
      aria-label={libelle}
    >
      {copie ? <Check size={14} /> : <Copy size={14} />}
    </button>
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
