import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Brain, Loader2, RotateCw, Search, SlidersHorizontal, Undo2 } from "lucide-react";
import { api } from "../../api/client";
import type { Fournisseur, ModeleActive, ModeleDistant, ThinkingSupport } from "../../api/types";
import { contexte, niveauLabel, nombre, SOURCE_LABEL } from "../../lib/format";
import { Modal } from "../ui/Modal";

type Props = {
  provider: Fournisseur;
  onClose: () => void;
  onSaved: (p: Fournisseur) => void;
};

type Ligne = {
  id: string;
  label: string | null;
  owned_by: string | null;
  context_length: number | null;
  max_output: number | null;
  detected: ThinkingSupport;
  origine: ModeleDistant["origine"] | "absent";
  /** Texte de recherche normalisé (précalculé : listes de plusieurs centaines de modèles). */
  hay: string;
};

type Filtre = "tous" | "api" | "reflexion";

const NIVEAUX_CONNUS = ["minimal", "low", "medium", "high", "xhigh", "max"];

/** Libellé court de la source de l'information « réflexion ». */
const SOURCE_COURTE: Record<string, string> = {
  api: "API",
  catalogue: "models.dev",
  heuristique: "déduit",
  manuel: "manuel",
};

const TIP_CATALOGUE =
  "Connu du catalogue models.dev mais non listé par l'API du fournisseur : peut nécessiter un accès particulier";

const norm = (s: string) =>
  s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

export function ModelPicker({ provider, onClose, onSaved }: Props) {
  const [lignes, setLignes] = useState<Ligne[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [overrides, setOverrides] = useState<Record<string, ThinkingSupport>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filtre, setFiltre] = useState<Filtre>("tous");
  const [seulementCoches, setSeulementCoches] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const dq = useDeferredValue(q);

  const charger = useCallback(
    async (signal?: AbortSignal) => {
      setLignes(null);
      setError(null);
      try {
        const distants: ModeleDistant[] = await api.remoteModels(provider.id, signal);
        const vus = new Set(distants.map((d) => d.id));
        const rows: Ligne[] = distants.map((d) => ({
          id: d.id,
          label: d.label ?? null,
          owned_by: d.owned_by ?? null,
          context_length: d.context_length ?? null,
          max_output: d.max_output ?? null,
          detected: d.thinking,
          origine: d.origine ?? "api",
          hay: norm(`${d.id} ${d.label ?? ""} ${d.owned_by ?? ""}`),
        }));
        // Modèles activés que le fournisseur ne liste plus : affichés pour décision explicite.
        for (const m of provider.models)
          if (!vus.has(m.id))
            rows.unshift({
              id: m.id,
              label: m.label ?? null,
              owned_by: null,
              context_length: m.context_length ?? null,
              max_output: null,
              detected: m.thinking,
              origine: "absent",
              hay: norm(`${m.id} ${m.label ?? ""}`),
            });
        setLignes(rows);
        setChecked(new Set([...distants.filter((d) => d.enabled).map((d) => d.id), ...provider.models.map((m) => m.id)]));
        const ov: Record<string, ThinkingSupport> = {};
        for (const m of provider.models) if (m.thinking.source === "manuel") ov[m.id] = m.thinking;
        setOverrides(ov);
      } catch (e) {
        if (signal?.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [provider],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    void charger(ctrl.signal);
    return () => ctrl.abort();
  }, [charger]);

  const compte = useMemo(() => {
    const l = lignes ?? [];
    return {
      tous: l.length,
      api: l.filter((x) => x.origine === "api" || x.origine === "api+catalogue").length,
      reflexion: l.filter((x) => (overrides[x.id] ?? x.detected).supported).length,
    };
  }, [lignes, overrides]);

  const filtrees = useMemo(() => {
    if (!lignes) return [];
    const mots = norm(dq).split(/\s+/).filter(Boolean);
    return lignes.filter(
      (l) =>
        (!seulementCoches || checked.has(l.id)) &&
        (filtre === "tous" ||
          (filtre === "api" && (l.origine === "api" || l.origine === "api+catalogue")) ||
          (filtre === "reflexion" && (overrides[l.id] ?? l.detected).supported)) &&
        mots.every((m) => l.hay.includes(m)),
    );
  }, [lignes, dq, filtre, seulementCoches, checked, overrides]);

  const toggle = (id: string) =>
    setChecked((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const filtreActif = dq.trim() !== "" || filtre !== "tous" || seulementCoches;
  const nbFiltresNonCoches = filtrees.filter((l) => !checked.has(l.id)).length;
  const cocherFiltres = () => setChecked((s) => new Set([...s, ...filtrees.map((l) => l.id)]));
  const toutDecocher = () => setChecked(new Set());

  const valider = async () => {
    if (!lignes) return;
    setSaving(true);
    setSaveError(null);
    const actifs = new Map(provider.models.map((m) => [m.id, m]));
    const models: ModeleActive[] = lignes
      .filter((l) => checked.has(l.id))
      .map((l) => {
        const m: ModeleActive = {
          id: l.id,
          thinking: overrides[l.id] ?? l.detected,
          context_length: l.context_length,
        };
        const label = actifs.get(l.id)?.label ?? l.label;
        if (label) m.label = label;
        return m;
      });
    try {
      onSaved(await api.setProviderModels(provider.id, models));
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  };

  return (
    <Modal
      wide
      title={`Modèles — ${provider.name}`}
      subtitle={<span className="mono">GET {provider.base_url.replace(/\/$/, "")}/models ∪ catalogue models.dev</span>}
      onClose={onClose}
      footer={
        <>
          {saveError && (
            <span className="foot-error">
              <AlertTriangle size={14} /> {saveError}
            </span>
          )}
          <span className="foot-count">
            <strong>{checked.size}</strong> modèle{checked.size > 1 ? "s" : ""} sélectionné{checked.size > 1 ? "s" : ""}
            {lignes && <span className="muted"> sur {nombre(lignes.length)}</span>}
          </span>
          <button className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button className="btn btn-primary" onClick={() => void valider()} disabled={!lignes || saving}>
            {saving && <Loader2 size={14} className="spin" />}
            Valider
          </button>
        </>
      }
    >
      {error ? (
        <div className="picker-error">
          <div className="alert">
            <AlertTriangle size={15} />
            <span>Impossible de récupérer la liste des modèles : {error}</span>
          </div>
          <button className="btn btn-sm" onClick={() => void charger()}>
            <RotateCw size={13} /> Réessayer
          </button>
        </div>
      ) : !lignes ? (
        <div className="picker-loading">
          <Loader2 size={18} className="spin" /> Interrogation du fournisseur…
        </div>
      ) : (
        <>
          <div className="picker-tools">
            <label className="filter grow">
              <Search size={14} aria-hidden />
              <input
                className="input"
                placeholder={`Rechercher parmi ${nombre(lignes.length)} modèles…`}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                aria-label="Rechercher un modèle"
                autoFocus
              />
            </label>
            <div className="segmented" role="radiogroup" aria-label="Filtrer les modèles">
              {(
                [
                  ["tous", "Tous", compte.tous],
                  ["api", "Listés par l'API", compte.api],
                  ["reflexion", "Avec réflexion", compte.reflexion],
                ] as const
              ).map(([v, label, n]) => (
                <button key={v} role="radio" aria-checked={filtre === v} className={filtre === v ? "on" : ""} onClick={() => setFiltre(v)}>
                  {label} <span className="seg-count">{nombre(n)}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="picker-tools picker-tools-2">
            <button className="btn btn-sm" onClick={cocherFiltres} disabled={nbFiltresNonCoches === 0}>
              {filtreActif ? `Tout cocher (${nombre(filtrees.length)} filtrés)` : "Tout cocher"}
            </button>
            <button className="btn btn-sm" onClick={toutDecocher} disabled={checked.size === 0}>
              Tout décocher
            </button>
            <label className="check-inline">
              <input type="checkbox" className="checkbox" checked={seulementCoches} onChange={(e) => setSeulementCoches(e.target.checked)} />
              Cochés seulement
            </label>
            <span className="picker-shown">
              {nombre(filtrees.length)} affiché{filtrees.length > 1 ? "s" : ""}
            </span>
          </div>

          <div className="picker-list" role="list">
            {filtrees.length === 0 && <p className="empty">Aucun modèle ne correspond.</p>}
            {filtrees.map((l) => {
              const on = checked.has(l.id);
              const th = overrides[l.id] ?? l.detected;
              const forced = l.id in overrides;
              const tailles = [
                l.context_length ? `${contexte(l.context_length)} ctx` : null,
                l.max_output ? `${contexte(l.max_output)} out` : null,
              ]
                .filter(Boolean)
                .join(" · ");
              return (
                <div key={l.id} className={`picker-row ${on ? "on" : ""} ${editing === l.id ? "editing" : ""}`} role="listitem">
                  <label className="picker-main">
                    <input type="checkbox" className="checkbox" checked={on} onChange={() => toggle(l.id)} />
                    <span className="picker-names">
                      <span className="picker-label">
                        {l.label || l.id}
                        {l.origine === "catalogue" && (
                          <span className="tag tag-catalogue" title={TIP_CATALOGUE}>
                            catalogue
                          </span>
                        )}
                        {l.origine === "absent" && (
                          <span className="tag tag-warn" title="Activé chez nous mais absent de la liste du fournisseur">
                            non listé
                          </span>
                        )}
                      </span>
                      {l.label && l.label !== l.id && <span className="picker-id mono">{l.id}</span>}
                    </span>
                  </label>
                  <span className="picker-ctx" title="Fenêtre de contexte · sortie maximale (jetons)">
                    {tailles}
                  </span>
                  <ThinkingInfo th={th} />
                  <button
                    className={`icon-btn sm ${editing === l.id ? "on" : ""}`}
                    onClick={() => setEditing(editing === l.id ? null : l.id)}
                    disabled={!on}
                    title={on ? "Forcer la prise en charge de la réflexion" : "Cochez le modèle pour régler la réflexion"}
                    aria-label="Régler la réflexion"
                  >
                    <SlidersHorizontal size={13} />
                  </button>
                  {editing === l.id && on && (
                    <ThinkingEditor
                      value={th}
                      forced={forced}
                      onChange={(t) => setOverrides((o) => ({ ...o, [l.id]: { ...t, source: "manuel" } }))}
                      onReset={() =>
                        setOverrides((o) => {
                          const n = { ...o };
                          delete n[l.id];
                          return n;
                        })
                      }
                    />
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </Modal>
  );
}

function ThinkingInfo({ th }: { th: ThinkingSupport }) {
  const src = SOURCE_LABEL[th.source] ?? th.source;
  if (!th.supported)
    return (
      <span className="th-info off" title={`Pas de réflexion (${src})`}>
        <Brain size={13} aria-hidden /> <span>—</span>
        <span className={`th-src src-${th.source}`}>{SOURCE_COURTE[th.source] ?? th.source}</span>
      </span>
    );
  return (
    <span className="th-info" title={`Réflexion : ${th.levels.map(niveauLabel).join(", ") || "sans niveaux"} (${src})`}>
      <Brain size={13} aria-hidden />
      <span className="th-levels">{th.levels.length ? th.levels.join(" · ") : "auto"}</span>
      <span className={`th-src src-${th.source}`}>{SOURCE_COURTE[th.source] ?? th.source}</span>
    </span>
  );
}

function ThinkingEditor({
  value,
  forced,
  onChange,
  onReset,
}: {
  value: ThinkingSupport;
  forced: boolean;
  onChange: (t: ThinkingSupport) => void;
  onReset: () => void;
}) {
  const [custom, setCustom] = useState("");
  const tous = [...NIVEAUX_CONNUS, ...value.levels.filter((l) => !NIVEAUX_CONNUS.includes(l))];
  const toggleLevel = (l: string) => {
    const levels = value.levels.includes(l) ? value.levels.filter((x) => x !== l) : [...value.levels, l];
    // Conserve l'ordre canonique pour les niveaux connus.
    levels.sort((a, b) => {
      const ia = tous.indexOf(a);
      const ib = tous.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    onChange({ ...value, supported: true, levels });
  };
  return (
    <div className="th-editor">
      <label className="check-inline">
        <input
          type="checkbox"
          className="checkbox"
          checked={value.supported}
          onChange={(e) => onChange({ ...value, supported: e.target.checked })}
        />
        Réflexion prise en charge
      </label>
      <div className={`th-chips ${value.supported ? "" : "disabled"}`}>
        <span className="hint">Niveaux proposés :</span>
        {tous.map((l) => (
          <button
            key={l}
            type="button"
            className={`chip ${value.levels.includes(l) ? "on" : ""}`}
            onClick={() => toggleLevel(l)}
            disabled={!value.supported}
            title={niveauLabel(l)}
          >
            {l}
          </button>
        ))}
        <form
          className="chip-add"
          onSubmit={(e) => {
            e.preventDefault();
            const v = custom.trim();
            if (v && !value.levels.includes(v)) toggleLevel(v);
            setCustom("");
          }}
        >
          <input
            className="input"
            placeholder="autre…"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            disabled={!value.supported}
            aria-label="Ajouter un niveau"
          />
        </form>
      </div>
      <div className="th-editor-foot">
        <span className="hint">
          {forced ? "Réglage manuel (source « manuel »)." : `Valeur détectée : ${SOURCE_LABEL[value.source] ?? value.source}.`}
        </span>
        {forced && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onReset}>
            <Undo2 size={13} /> Revenir à la détection
          </button>
        )}
      </div>
    </div>
  );
}
