import { useState } from "react";
import { AlertTriangle, KeyRound } from "lucide-react";
import { api } from "../../api/client";
import type { Fournisseur, TypeFournisseur } from "../../api/types";
import { Modal } from "../ui/Modal";

type Preset = { label: string; name: string; type: TypeFournisseur; url: string; sansCle?: boolean };

export const PRESETS: Preset[] = [
  { label: "OpenAI", name: "OpenAI", type: "openai", url: "https://api.openai.com/v1" },
  { label: "OpenRouter", name: "OpenRouter", type: "openai", url: "https://openrouter.ai/api/v1" },
  { label: "Mistral", name: "Mistral", type: "openai", url: "https://api.mistral.ai/v1" },
  { label: "DeepSeek", name: "DeepSeek", type: "openai", url: "https://api.deepseek.com/v1" },
  { label: "Ollama (local)", name: "Ollama", type: "openai", url: "http://localhost:11434/v1", sansCle: true },
  { label: "Anthropic", name: "Anthropic", type: "anthropic", url: "https://api.anthropic.com" },
];

export const TYPE_LABEL: Record<TypeFournisseur, string> = {
  openai: "Compatible OpenAI",
  anthropic: "Anthropic natif",
};

type Props = {
  provider: Fournisseur | null; // null = création
  onClose: () => void;
  onSaved: (p: Fournisseur, created: boolean) => void;
};

export function ProviderForm({ provider, onClose, onSaved }: Props) {
  const edit = provider !== null;
  const [name, setName] = useState(provider?.name ?? "");
  const [type, setType] = useState<TypeFournisseur>(provider?.type ?? "openai");
  const [baseUrl, setBaseUrl] = useState(provider?.base_url ?? "");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const presets = edit ? PRESETS.filter((p) => p.type === type) : PRESETS;
  const preset = PRESETS.find((p) => p.url === baseUrl.trim());

  const applyPreset = (p: Preset) => {
    setBaseUrl(p.url);
    if (!edit) setType(p.type);
    if (!name.trim() || PRESETS.some((x) => x.name === name.trim())) setName(p.name);
  };

  const valid = name.trim() !== "" && /^https?:\/\/\S+$/.test(baseUrl.trim());

  const save = async () => {
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      if (provider) {
        const patch: { name?: string; base_url?: string; api_key?: string } = {};
        if (name.trim() !== provider.name) patch.name = name.trim();
        if (baseUrl.trim() !== provider.base_url) patch.base_url = baseUrl.trim();
        if (key !== "") patch.api_key = key;
        const p = Object.keys(patch).length > 0 ? await api.updateProvider(provider.id, patch) : provider;
        onSaved(p, false);
      } else {
        const p = await api.createProvider({ name: name.trim(), type, base_url: baseUrl.trim(), api_key: key });
        onSaved(p, true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <Modal
      title={edit ? `Modifier « ${provider.name} »` : "Ajouter un fournisseur"}
      subtitle="Une URL de base et une clé : tout service compatible OpenAI, ou l'API Anthropic."
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button className="btn btn-primary" onClick={() => void save()} disabled={!valid || busy}>
            {edit ? "Enregistrer" : "Ajouter"}
          </button>
        </>
      }
    >
      <form
        className="form-grid"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <label className="field">
          <span>Nom</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. OpenRouter" />
        </label>

        <div className="field">
          <span className="field-label">Type d'API</span>
          <div className="segmented" role="radiogroup" aria-label="Type d'API">
            {(["openai", "anthropic"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={type === t}
                className={type === t ? "on" : ""}
                onClick={() => setType(t)}
                disabled={edit && type !== t}
                title={edit ? "Le type ne peut pas être modifié après création" : undefined}
              >
                {TYPE_LABEL[t]}
              </button>
            ))}
          </div>
          <span className="hint">
            {type === "openai"
              ? "API Chat Completions : OpenAI, OpenRouter, Mistral, DeepSeek, Groq, vLLM, Ollama, LM Studio…"
              : "API Messages native : cache de prompt, réflexion adaptative, paramètre effort."}
          </span>
        </div>

        <label className="field">
          <span>URL de base</span>
          <input
            className="input mono"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://…/v1"
            spellCheck={false}
          />
          <div className="presets">
            <span className="hint">Exemples :</span>
            {presets.map((p) => (
              <button
                key={p.label}
                type="button"
                className={`chip ${preset?.url === p.url ? "on" : ""}`}
                onClick={() => applyPreset(p)}
                title={p.url}
              >
                {p.label}
              </button>
            ))}
          </div>
        </label>

        <label className="field">
          <span>
            <KeyRound size={12} style={{ verticalAlign: -1 }} /> Clé API
          </span>
          <input
            className="input mono"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={edit ? (provider.api_key_set ? "•••••••• (inchangée)" : "aucune clé enregistrée") : "sk-…"}
            autoComplete="new-password"
            spellCheck={false}
          />
          <span className="hint">
            {edit
              ? "Laisser vide pour conserver la clé actuelle. La clé n'est jamais renvoyée par le serveur."
              : preset?.sansCle
                ? "Facultative pour un serveur local."
                : "Stockée côté serveur ; elle n'est jamais renvoyée à l'interface."}
          </span>
        </label>
        <button type="submit" hidden />
      </form>
      {error && (
        <div className="alert" style={{ marginTop: 14 }}>
          <AlertTriangle size={15} />
          <span>{error}</span>
        </div>
      )}
    </Modal>
  );
}
