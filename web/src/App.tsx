import { useCallback, useEffect, useState } from "react";
import { api, IS_MOCK } from "./api/client";
import type { ConversationResume, ModeleChoix, Reglages } from "./api/types";
import { Sidebar } from "./components/Sidebar";
import { ChatView } from "./components/chat/ChatView";
import { ReaderPanel } from "./components/reader/ReaderPanel";
import { SettingsView } from "./components/settings/SettingsView";
import { useStoredState } from "./hooks/useStoredState";
import { useTheme } from "./hooks/useTheme";
import { emptyHistory, pushTarget, type ReaderHistory, type ReaderTarget } from "./lib/reader";

type Vue = "chat" | "settings";

export default function App() {
  const [theme, cycleTheme] = useTheme();
  const [vue, setVue] = useState<Vue>("chat");
  const [conversations, setConversations] = useState<ConversationResume[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [models, setModels] = useState<ModeleChoix[]>([]);
  const [reglages, setReglages] = useState<Reglages>({ default_model_key: null, default_thinking: null });
  const [reader, setReader] = useState<ReaderHistory>(emptyHistory);
  const [readerOpen, setReaderOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Grand écran : barre latérale repliable (mémorisée). Petit écran : tiroir (sidebarOpen).
  const [sidebarReduite, setSidebarReduite] = useStoredState("interstice.sidebar-reduite", false);
  const basculerSidebar = useCallback(() => {
    if (window.matchMedia("(max-width: 820px)").matches) setSidebarOpen((o) => !o);
    else setSidebarReduite((r) => !r);
  }, [setSidebarReduite]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        basculerSidebar();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [basculerSidebar]);
  // Clé de montage du chat : change quand l'utilisateur choisit une conversation, mais pas
  // quand une conversation est créée à la volée par le premier envoi (le flux continue).
  const [chatSession, setChatSession] = useState(0);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
      setListError(null);
    } catch (e) {
      setListError(e instanceof Error ? e.message : String(e));
      setConversations((c) => c ?? []);
    }
  }, []);

  const refreshModels = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([api.listModels(), api.getSettings()]);
      setModels(m);
      setReglages(s);
    } catch {
      /* affiché dans le compositeur (aucun modèle) */
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
    void refreshModels();
  }, [refreshConversations, refreshModels]);

  // Tant qu'une génération tourne en arrière-plan, la liste est rafraîchie régulièrement
  // (indicateur « rédige… », titre, ordre) ; elle l'est aussi à la fin de chaque flux suivi.
  const enCours = conversations?.some((c) => c.generation_en_cours) ?? false;
  useEffect(() => {
    if (!enCours) return;
    const t = setInterval(() => void refreshConversations(), 5000);
    return () => clearInterval(t);
  }, [enCours, refreshConversations]);

  const openTarget = useCallback((t: ReaderTarget) => {
    setReader((h) => pushTarget(h, t));
    setReaderOpen(true);
  }, []);

  const activeTarget = readerOpen ? (reader.entries[reader.index] ?? null) : null;

  const selectConversation = (id: string | null) => {
    setCurrentId(id);
    setChatSession((n) => n + 1);
    setVue("chat");
    setSidebarOpen(false);
  };

  const deleteConversation = async (id: string) => {
    await api.deleteConversation(id);
    if (id === currentId) selectConversation(null);
    await refreshConversations();
  };

  const renameConversation = async (id: string, title: string) => {
    await api.renameConversation(id, title);
    await refreshConversations();
  };

  return (
    <div
      className={`app ${readerOpen ? "has-reader" : ""} ${sidebarOpen ? "sidebar-open" : ""} ${sidebarReduite ? "sidebar-reduite" : ""}`}
    >
      <Sidebar
        onCollapse={() => setSidebarReduite(true)}
        conversations={conversations}
        error={listError}
        currentId={vue === "chat" ? currentId : null}
        vue={vue}
        theme={theme}
        onCycleTheme={cycleTheme}
        onNew={() => selectConversation(null)}
        onSelect={(id) => selectConversation(id)}
        onRename={renameConversation}
        onDelete={deleteConversation}
        onBrowse={() => {
          openTarget({ kind: "textes" });
          setSidebarOpen(false);
        }}
        onBrowseBofip={() => {
          openTarget({ kind: "bofip-plan", noeud: null });
          setSidebarOpen(false);
        }}
        onSettings={() => {
          setVue("settings");
          setSidebarOpen(false);
        }}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      <main className="main">
        {IS_MOCK && <div className="mock-ribbon" title="Données fictives en mémoire (VITE_MOCK=1)">Maquette</div>}
        {vue === "settings" ? (
          <SettingsView
            onBack={() => {
              setVue("chat");
              void refreshModels();
            }}
            onChanged={refreshModels}
            onToggleSidebar={basculerSidebar}
          />
        ) : (
          <ChatView
            key={chatSession}
            conversationId={currentId}
            title={conversations?.find((c) => c.id === currentId)?.title ?? ""}
            models={models}
            reglages={reglages}
            activeTarget={activeTarget}
            onOpenTarget={openTarget}
            onCreated={(id) => setCurrentId(id)}
            onActivity={refreshConversations}
            onOpenSettings={() => setVue("settings")}
            onToggleSidebar={basculerSidebar}
          />
        )}
      </main>

      {readerOpen && (
        <ReaderPanel
          history={reader}
          onNavigate={openTarget}
          onMove={(delta) =>
            setReader((h) => ({ ...h, index: Math.min(h.entries.length - 1, Math.max(0, h.index + delta)) }))
          }
          onClose={() => setReaderOpen(false)}
        />
      )}
      <div className="scrim" onClick={() => setSidebarOpen(false)} aria-hidden />
    </div>
  );
}
