import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Brain,
  Check,
  CloudDownload,
  KeyRound,
  Loader2,
  PanelLeftOpen,
  PenLine,
  Plus,
  Trash2,
} from "lucide-react";
import { api } from "../../api/client";
import type { Fournisseur, ModeleChoix, Reglages } from "../../api/types";
import { modelDropdownOptions, thinkingDropdownOptions } from "../../lib/options";
import { Dropdown } from "../ui/Dropdown";
import { ModelPicker } from "./ModelPicker";
import { ProviderForm, TYPE_LABEL } from "./ProviderForm";

type Props = {
  onBack: () => void;
  onChanged: () => void | Promise<void>;
  onToggleSidebar: () => void;
};

export function SettingsView({ onBack, onChanged, onToggleSidebar }: Props) {
  const [providers, setProviders] = useState<Fournisseur[] | null>(null);
  const [models, setModels] = useState<ModeleChoix[]>([]);
  const [reglages, setReglages] = useState<Reglages | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<{ provider: Fournisseur | null } | null>(null);
  const [picker, setPicker] = useState<Fournisseur | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, m, s] = await Promise.all([api.listProviders(), api.listModels(), api.getSettings()]);
      setProviders(p);
      setModels(m);
      setReglages(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setProviders((x) => x ?? []);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const changed = async () => {
    await load();
    await onChanged();
  };

  return (
    <div className="settings">
      <header className="chat-head">
        <button
          className="icon-btn sidebar-toggle"
          onClick={onToggleSidebar}
          title="Afficher la barre latérale (Ctrl+B)"
          aria-label="Afficher la barre latérale"
        >
          <PanelLeftOpen size={17} />
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onBack}>
          <ArrowLeft size={15} /> Retour au chat
        </button>
      </header>

      <div className="settings-scroll">
        <div className="settings-column">
          <h1 className="settings-title">Réglages</h1>
          <p className="settings-lead">
            Fournisseurs de modèles, modèles activés et choix par défaut. Les clés API restent sur le serveur.
          </p>

          {error && (
            <div className="alert" style={{ marginBottom: 20 }}>
              <AlertTriangle size={15} />
              <span>{error}</span>
            </div>
          )}

          <section className="settings-section">
            <div className="section-head">
              <div>
                <h2>Fournisseurs</h2>
                <p>Une URL de base et une clé par fournisseur ; puis choisissez les modèles à proposer.</p>
              </div>
              <button className="btn btn-primary" onClick={() => setForm({ provider: null })}>
                <Plus size={15} /> Ajouter
              </button>
            </div>

            {providers === null ? (
              <div className="provider-card skeleton" style={{ height: 96 }} />
            ) : providers.length === 0 ? (
              <div className="empty-card">
                <p>Aucun fournisseur configuré.</p>
                <button className="btn" onClick={() => setForm({ provider: null })}>
                  <Plus size={15} /> Ajouter un premier fournisseur
                </button>
              </div>
            ) : (
              <div className="providers">
                {providers.map((p) => (
                  <ProviderCard
                    key={p.id}
                    p={p}
                    onEdit={() => setForm({ provider: p })}
                    onModels={() => setPicker(p)}
                    onDelete={async () => {
                      await api.deleteProvider(p.id);
                      await changed();
                    }}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="settings-section">
            <div className="section-head">
              <div>
                <h2>Par défaut</h2>
                <p>Modèle et niveau de réflexion proposés au démarrage d'une conversation.</p>
              </div>
            </div>
            {reglages && <Defaults models={models} reglages={reglages} onSaved={setReglages} onChanged={onChanged} />}
          </section>
        </div>
      </div>

      {form && (
        <ProviderForm
          provider={form.provider}
          onClose={() => setForm(null)}
          onSaved={(p, created) => {
            setForm(null);
            void changed();
            if (created) setPicker(p);
          }}
        />
      )}
      {picker && (
        <ModelPicker
          provider={picker}
          onClose={() => setPicker(null)}
          onSaved={() => {
            setPicker(null);
            void changed();
          }}
        />
      )}
    </div>
  );
}

function ProviderCard({
  p,
  onEdit,
  onModels,
  onDelete,
}: {
  p: Fournisseur;
  onEdit: () => void;
  onModels: () => void;
  onDelete: () => Promise<void>;
}) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="provider-card">
      <div className="provider-top">
        <div className="provider-id">
          <h3>{p.name}</h3>
          <span className="badge plain">{TYPE_LABEL[p.type]}</span>
        </div>
        <div className="provider-actions">
          <button className="btn btn-sm" onClick={onModels}>
            <CloudDownload size={14} /> Récupérer les modèles
          </button>
          <button className="icon-btn" onClick={onEdit} title="Modifier" aria-label="Modifier">
            <PenLine size={15} />
          </button>
          {confirm ? (
            <>
              <button
                className="btn btn-sm btn-danger"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onDelete();
                  } catch (e) {
                    setErr(e instanceof Error ? e.message : String(e));
                    setBusy(false);
                    setConfirm(false);
                  }
                }}
              >
                {busy ? <Loader2 size={13} className="spin" /> : <Check size={13} />} Supprimer
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => setConfirm(false)}>
                Annuler
              </button>
            </>
          ) : (
            <button className="icon-btn" onClick={() => setConfirm(true)} title="Supprimer" aria-label="Supprimer">
              <Trash2 size={15} />
            </button>
          )}
        </div>
      </div>
      <div className="provider-meta">
        <span className="mono">{p.base_url}</span>
        <span className={`key-state ${p.api_key_set ? "set" : ""}`}>
          <KeyRound size={12} /> {p.api_key_set ? "clé enregistrée" : "sans clé"}
        </span>
      </div>
      {err && <div className="alert" style={{ marginTop: 10 }}>{err}</div>}
      <div className="provider-models">
        {p.models.length === 0 ? (
          <span className="muted">Aucun modèle activé — cliquez sur « Récupérer les modèles ».</span>
        ) : (
          p.models.map((m) => (
            <span key={m.id} className="model-chip" title={m.id}>
              {m.label ?? m.id}
              {m.thinking.supported && <Brain size={11} className="model-chip-th" aria-label="réflexion" />}
            </span>
          ))
        )}
      </div>
    </div>
  );
}

function Defaults({
  models,
  reglages,
  onSaved,
  onChanged,
}: {
  models: ModeleChoix[];
  reglages: Reglages;
  onSaved: (r: Reglages) => void;
  onChanged: () => void | Promise<void>;
}) {
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);
  const modele = models.find((m) => m.key === reglages.default_model_key) ?? null;
  const levels = modele?.thinking.supported ? modele.thinking.levels : [];

  const save = async (r: Reglages) => {
    setState("saving");
    try {
      onSaved(await api.putSettings(r));
      setState("saved");
      void onChanged();
      setTimeout(() => setState((s) => (s === "saved" ? "idle" : s)), 1800);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setState("error");
    }
  };

  return (
    <div className="defaults">
      <div className="field">
        <span className="field-label">Modèle par défaut</span>
        <Dropdown
          variant="field"
          ariaLabel="Modèle par défaut"
          value={reglages.default_model_key ?? ""}
          options={[{ value: "", label: "Aucun (premier modèle disponible)" }, ...modelDropdownOptions(models)]}
          searchPlaceholder="Rechercher un modèle…"
          onChange={(v) => {
            const key = v || null;
            const m = models.find((x) => x.key === key);
            const lv = m?.thinking.supported ? m.thinking.levels : [];
            const th = reglages.default_thinking && lv.includes(reglages.default_thinking) ? reglages.default_thinking : null;
            void save({ default_model_key: key, default_thinking: th });
          }}
        />
      </div>
      <div className="field">
        <span className="field-label">Réflexion par défaut</span>
        <Dropdown
          variant="field"
          ariaLabel="Réflexion par défaut"
          icon={<Brain size={14} />}
          value={reglages.default_thinking ?? ""}
          options={thinkingDropdownOptions(levels)}
          searchable={false}
          disabled={levels.length === 0}
          onChange={(v) => void save({ ...reglages, default_thinking: v || null })}
        />
        <span className="hint">
          {modele && !modele.thinking.supported
            ? "Ce modèle ne propose pas de réflexion réglable."
            : modele && levels.length === 0
              ? "Ce modèle réfléchit sans niveau réglable."
              : " "}
        </span>
      </div>
      <div className="defaults-state" aria-live="polite">
        {state === "saving" && (
          <>
            <Loader2 size={13} className="spin" /> Enregistrement…
          </>
        )}
        {state === "saved" && (
          <>
            <Check size={13} /> Enregistré
          </>
        )}
        {state === "error" && <span className="bad">{err}</span>}
      </div>
    </div>
  );
}
