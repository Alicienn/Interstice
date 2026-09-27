import { useMemo } from "react";
import * as THREE from "three";

/**
 * Matériau shader créé une seule fois, qui conserve la référence à `uniforms`.
 *
 * Passer `uniforms` en propriété JSX à <shaderMaterial> fait copier l'objet par React Three Fiber :
 * les mises à jour par image écrivent alors dans une copie que le GPU ne voit jamais. Construire le
 * matériau impérativement (le constructeur garde la référence) évite ce piège.
 */
export function useShader(params: THREE.ShaderMaterialParameters): THREE.ShaderMaterial {
  // les paramètres sont figés au premier rendu : les valeurs dynamiques passent par `uniforms`
  const m = useMemo(() => new THREE.ShaderMaterial(params), []);
  return m;
}
