import { Boxes, Database, Globe, Layers3, Package, Route } from "lucide-react";
import type { ComponentRole } from "@/api/types";

/** Same role -> token mapping Execution Flow's flow/roleStyle.ts uses, so a
 * component reads as the same color everywhere it appears in the product. */
export const ROLE_VAR: Partial<Record<ComponentRole, string>> = {
  api: "--accent",
  service: "--slate",
  data_access: "--bronze",
  external_integration: "--sage",
};
export const DEFAULT_ROLE_VAR = "--text-faint";

export function roleColorVar(role: ComponentRole | string | null): string {
  return (role && ROLE_VAR[role as ComponentRole]) || DEFAULT_ROLE_VAR;
}

export const ROLE_ICON: Partial<Record<ComponentRole, typeof Route>> = {
  api: Route,
  service: Layers3,
  data_access: Database,
  external_integration: Globe,
  model: Boxes,
};
export function roleIcon(role: ComponentRole | string | null) {
  return (role && ROLE_ICON[role as ComponentRole]) || Package;
}

/** Kept for the four colored roles only (matches the legend Execution Flow's
 * TraceLegend already renders) — model/test/other stay the neutral default. */
export const ROLE_LEGEND: { role: ComponentRole; color: string }[] = [
  { role: "api", color: `var(${ROLE_VAR.api})` },
  { role: "service", color: `var(${ROLE_VAR.service})` },
  { role: "data_access", color: `var(${ROLE_VAR.data_access})` },
  { role: "external_integration", color: `var(${ROLE_VAR.external_integration})` },
];
