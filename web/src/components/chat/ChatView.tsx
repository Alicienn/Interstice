import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from "react";
import { AlertTriangle, Menu } from "lucide-react";
import { api } from "../../api/client";
import type { ModeleChoix, Reglages } from "../../api/types";
import { useStoredState } from "../../hooks/useStoredState";
import type { ReaderTarget } from "../../lib/reader";
import { chatReducer, initialChatState } from "../../state/chatReducer";
import { Composer } from "./Composer";
import { MessageView } from "./MessageView";

type Props = {
  conversationId: string | null;
  title: string;
  models: ModeleChoix[];
  reglages: Reglages;
  activeTarget: ReaderTarget | null;
  onOpenTarget: (t: ReaderTarget) => void;
  onCreated: (id: string) => void;
  onActivity: () => void | Promise<void>;
  onOpenSettings: () => void;
  onToggleSidebar: () => void;
};

const SUGGESTIONS = [
  "Quelles sont les conditions du report d'imposition de l'article 150-0 B ter ?",
  "Différence entre l'abus de droit de l'article L. 64 et celui de l'article L. 64 A du LPF ?",
  "Quels articles du CGI renvoient à l'article 150-0 A ?",
  "Comment l'article 150-0 D a-t-il évolué depuis 2018 ?",
];

const STOP_GRACE_MS = 4000;

export function ChatView(p: Props) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [convId, setConvId] = useState<string | null>(p.conversationId);
  const [loading, setLoading] = useState(p.conversationId !== null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [preset, setPreset] = useState<{ text: string; n: number } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  // ── Choix du modèle et du niveau de réflexion (mémorisés dans le navigateur)
  const [storedModel, setStoredModel] = useStoredState<string | null>("interstice.model", null);
  const [storedThinking, setStoredThinking] = useStoredState<Record<string, string | null>>(
    "interstice.thinking",
    {},
  );
  const has = (k: string | null | undefined) => !!k && p.models.some((m) => m.key === k);
  const modelKey = has(storedModel)
    ? storedModel
    : has(p.reglages.default_model_key)
      ? p.reglages.default_model_key
      : (p.models[0]?.key ?? null);
  const modele = p.models.find((m) => m.key === modelKey) ?? null;
  const levels = modele?.thinking.supported ? modele.thinking.levels : [];
  let thinking: string | null = null;
  if (modelKey && levels.length > 0) {
    const stored = storedThinking[modelKey];
    if (stored === null || (stored !== undefined && levels.includes(stored))) thinking = stored;
    else if (p.reglages.default_thinking && levels.includes(p.reglages.default_thinking))
      thinking = p.reglages.default_thinking;
  }

  // ── Chargement de la conversation (une fois : le composant est remonté à chaque changement de
  // conversation ; une conversation créée par le premier envoi ne doit pas être rechargée).
  const initialId = useRef(p.conversationId).current;
  useEffect(() => {
    if (!initialId) return;
    let alive = true;
    api
      .getConversation(initialId)
      .then((c) => alive && dispatch({ type: "load", messages: c.messages }))
      .catch((e: unknown) => alive && setLoadError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [initialId]);

  // Abandon de la lecture du flux au démontage (la génération continue côté serveur).
  useEffect(() => () => abortRef.current?.abort(), []);

  // ── Défilement : reste collé en bas si l'utilisateur y était
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [state.messages]);

  const send = useCallback(
    async (content: string) => {
      if (!modelKey || state.streaming) return;
      const now = () => new Date().toISOString();
      dispatch({ type: "send", localId: `local-${Date.now()}`, content, now: now() });
      stickRef.current = true;
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setStopping(false);
      try {
        let id = convId;
        if (!id) {
          const c = await api.createConversation();
          id = c.id;
          setConvId(id);
          p.onCreated(id);
        }
        void p.onActivity();
        await api.sendMessage(
          id,
          { content, model_key: modelKey, thinking_level: thinking },
          (event) => {
            dispatch({ type: "event", event, now: now() });
            // Le serveur titre la conversation au premier message : rafraîchit la liste.
            if (event.event === "user_message") void p.onActivity();
          },
          ctrl.signal,
        );
      } catch (e) {
        const aborted = ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError");
        if (!aborted) dispatch({ type: "local_error", message: e instanceof Error ? e.message : String(e), now: now() });
      } finally {
        if (abortRef.current === ctrl) abortRef.current = null;
        dispatch({ type: "finish" });
        setStopping(false);
        void p.onActivity();
      }
    },
    [convId, modelKey, thinking, state.streaming, p],
  );

  const stop = useCallback(() => {
    setStopping(true);
    const ctrl = abortRef.current;
    if (convId) void api.stopConversation(convId).catch(() => ctrl?.abort());
    else ctrl?.abort();
    // Si le serveur ne clôt pas le flux rapidement, on coupe la lecture.
    setTimeout(() => {
      if (abortRef.current === ctrl) ctrl?.abort();
    }, STOP_GRACE_MS);
  }, [convId]);

  const empty = !loading && state.messages.length === 0;

  return (
    <div className="chat">
      <header className="chat-head">
        <button className="icon-btn only-mobile" onClick={p.onToggleSidebar} aria-label="Menu">
          <Menu size={18} />
        </button>
        <h1 className="chat-title">{p.title || (convId ? "Sans titre" : "Nouvelle conversation")}</h1>
      </header>

      <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
        <div className="chat-column">
          {loading && (
            <div className="chat-loading">
              {[92, 64, 78].map((w, i) => (
                <div key={i} className="skeleton" style={{ height: 14, width: `${w}%`, marginBottom: 12 }} />
              ))}
            </div>
          )}
          {loadError && (
            <div className="alert">
              <AlertTriangle size={15} /> Impossible de charger la conversation : {loadError}
            </div>
          )}
          {empty && !loadError && (
            <div className="welcome">
              <div className="welcome-mark" aria-hidden>
                §
              </div>
              <h2>Interroger le droit fiscal, texte à l'appui.</h2>
              <p>
                L'assistant parcourt les codes consolidés (CGI, LPF, CIBS…), lit les articles à la date utile et cite
                ses sources. Chaque document consulté s'ouvre dans le panneau de lecture.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="suggestion" onClick={() => setPreset({ text: s, n: Date.now() })}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {state.messages.map((m) => (
            <MessageView
              key={m.id}
              message={m}
              live={state.streaming && m.id === state.assistantId}
              models={p.models}
              activeTarget={p.activeTarget}
              onOpenTarget={p.onOpenTarget}
            />
          ))}
          {state.streaming && state.messages[state.messages.length - 1]?.role === "user" && (
            <div className="msg msg-assistant live">
              <div className="pending">
                <span className="pending-bar" />
                Envoi…
              </div>
            </div>
          )}
        </div>
      </div>

      <Composer
        streaming={state.streaming}
        stopping={stopping}
        models={p.models}
        modelKey={modelKey}
        onModelChange={(k) => setStoredModel(k)}
        thinking={thinking}
        onThinkingChange={(l) => modelKey && setStoredThinking((s) => ({ ...s, [modelKey]: l }))}
        onSend={(t) => void send(t)}
        onStop={stop}
        onOpenSettings={p.onOpenSettings}
        preset={preset}
      />
    </div>
  );
}
