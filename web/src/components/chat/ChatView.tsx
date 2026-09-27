import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from "react";
import { AlertTriangle, PanelLeftOpen } from "lucide-react";
import { api } from "../../api/client";
import type { ModeleChoix, Reglages } from "../../api/types";
import { useStoredState } from "../../hooks/useStoredState";
import type { ReaderTarget } from "../../lib/reader";
import { chatReducer, initialChatState, stripGeneration } from "../../state/chatReducer";
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

/**
 * Début d'une génération pour le compteur : horodatage de la question (serveur) s'il est antérieur à
 * celui de la bulle assistant (qui, lors d'un rejeu /stream, vaut l'heure du rattachement).
 */
function debutGeneration(assistant: string, question: string | undefined): number {
  const a = Date.parse(assistant);
  const q = question ? Date.parse(question) : NaN;
  const t = Number.isNaN(q) ? a : Number.isNaN(a) ? q : Math.min(a, q);
  return Number.isNaN(t) ? Date.now() : Math.min(t, Date.now());
}

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
      .then((c) => {
        if (!alive) return;
        setLoading(false);
        if (c.generation_en_cours) {
          // Génération en arrière-plan : on retire le message partiel et sa question, puis on se
          // rattache au flux (rejeu depuis le début, puis direct).
          dispatch({ type: "load", messages: stripGeneration(c.messages, c.generation_message_id) });
          void attach(c.id);
        } else dispatch({ type: "load", messages: c.messages });
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setLoading(false);
        setLoadError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialId]);

  /** Rattachement à une génération en cours côté serveur (GET /stream). */
  async function attach(id: string) {
    const now = () => new Date().toISOString();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    stickRef.current = true;
    dispatch({ type: "attach" });
    try {
      const enCours = await api.resumeStream(id, (event) => dispatch({ type: "event", event, now: now() }), ctrl.signal);
      if (!enCours) {
        // Terminée entre-temps (204) : on recharge la version définitive.
        const c = await api.getConversation(id);
        if (!ctrl.signal.aborted) dispatch({ type: "load", messages: c.messages });
      }
    } catch (e) {
      const aborted = ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError");
      if (!aborted) dispatch({ type: "local_error", message: e instanceof Error ? e.message : String(e), now: now() });
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null;
      if (!ctrl.signal.aborted) {
        dispatch({ type: "finish" });
        void p.onActivity();
      }
    }
  }

  // Au démontage (changement de conversation) : on abandonne seulement la LECTURE du flux.
  // Ne jamais appeler /stop ici : la génération continue côté serveur et pourra être rejointe.
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
        <button
          className="icon-btn sidebar-toggle"
          onClick={p.onToggleSidebar}
          title="Afficher la barre latérale (Ctrl+B)"
          aria-label="Afficher la barre latérale"
        >
          <PanelLeftOpen size={17} />
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
          {state.messages.map((m, i) => {
            const live = state.streaming && m.id === state.assistantId;
            return (
              <MessageView
                key={m.id}
                message={m}
                live={live}
                startedAt={live ? debutGeneration(m.created_at, state.messages[i - 1]?.created_at) : null}
                models={p.models}
                activeTarget={p.activeTarget}
                onOpenTarget={p.onOpenTarget}
              />
            );
          })}
          {state.streaming && state.messages[state.messages.length - 1]?.role === "user" && (
            <div className="msg msg-assistant live">
              <div className="work-live">
                <span className="work-dot" aria-hidden />
                <span className="shimmer">Envoi…</span>
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
