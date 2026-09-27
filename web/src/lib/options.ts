import type { ModeleChoix } from "../api/types";
import type { DropdownOption } from "../components/ui/Dropdown";
import { niveauLabel } from "./format";

/** Modèles groupés par fournisseur (ordre d'apparition des fournisseurs conservé). */
export function modelDropdownOptions(models: ModeleChoix[]): DropdownOption[] {
  const order: string[] = [];
  const byProvider = new Map<string, ModeleChoix[]>();
  for (const m of models) {
    if (!byProvider.has(m.provider_id)) {
      byProvider.set(m.provider_id, []);
      order.push(m.provider_id);
    }
    byProvider.get(m.provider_id)!.push(m);
  }
  return order.flatMap((pid) =>
    byProvider.get(pid)!.map((m) => ({
      value: m.key,
      label: m.label,
      group: m.provider_name,
      hint: m.label !== m.model_id ? m.model_id : undefined,
    })),
  );
}

export function thinkingDropdownOptions(levels: string[]): DropdownOption[] {
  return [
    { value: "", label: "Réflexion désactivée" },
    ...levels.map((l) => ({ value: l, label: `Réflexion ${niveauLabel(l).toLowerCase()}`, hint: l })),
  ];
}
