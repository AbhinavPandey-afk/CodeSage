import { Code2, Compass, Database, Globe, Layers3, Play, Route } from "lucide-react";
import type { ComponentRole } from "@/api/types";
import type { TraceNode } from "@/lib/flowModel";

/** Same role -> token mapping as architecture/roleStyle's ROLE_VAR, so a
 * component reads as the same color on the Architecture diagram and in a trace. */
const ROLE_VAR: Partial<Record<ComponentRole, string>> = {
  api: "--accent",
  service: "--slate",
  data_access: "--bronze",
  external_integration: "--sage",
};
const DEFAULT_ROLE_VAR = "--text-faint";

export function roleVar(role: ComponentRole | null): string {
  return (role && ROLE_VAR[role]) || DEFAULT_ROLE_VAR;
}

export function nodeIcon(node: TraceNode) {
  if (node.kind === "entry") return Play;
  if (node.kind === "proposed") return Compass;
  if (node.terminalKind === "database") return Database;
  if (node.terminalKind === "external_service") return Globe;
  if (node.componentRole === "api") return Route;
  if (node.componentRole === "service") return Layers3;
  if (node.componentRole === "data_access") return Database;
  if (node.componentRole === "external_integration") return Globe;
  return Code2;
}

export function nodeRoleVar(node: TraceNode): string {
  if (node.kind === "entry") return "--ok";
  if (node.kind === "proposed") return "--accent";
  if (node.terminalKind === "database") return roleVar("data_access");
  if (node.terminalKind === "external_service") return roleVar("external_integration");
  return roleVar(node.componentRole);
}
