/**
 * Horloge partagée : `t` (ms depuis l'envoi) est à la fois un état React (pour le HTML) et une
 * référence mutable lue à chaque image par les scènes WebGL (sans rerendu React).
 */
import { createContext, useContext, useMemo, type MutableRefObject, type ReactNode } from "react";
import { etatA, type Etat, type Prepare } from "./scenario";

interface Horloge {
  t: number;
  tRef: MutableRefObject<number>;
  prep: Prepare;
}

const Ctx = createContext<Horloge | null>(null);

export function FournisseurHorloge({ t, tRef, prep, children }: Horloge & { children: ReactNode }) {
  const valeur = useMemo(() => ({ t, tRef, prep }), [t, tRef, prep]);
  return <Ctx.Provider value={valeur}>{children}</Ctx.Provider>;
}

export function useHorlogeScene(): Horloge & { e: Etat } {
  const h = useContext(Ctx);
  if (!h) throw new Error("horloge absente");
  return { ...h, e: etatA(h.prep, h.t) };
}

/** Lissage exponentiel indépendant de la cadence d'image. */
export function amortir(actuel: number, cible: number, raideur: number, dt: number): number {
  return cible + (actuel - cible) * Math.exp(-raideur * dt);
}

export const facile = (x: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
export const bornes = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lisse = (a: number, b: number, x: number) => {
  const k = bornes((x - a) / (b - a));
  return k * k * (3 - 2 * k);
};
