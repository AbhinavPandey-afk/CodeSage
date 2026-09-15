/** Best-effort parse of a raw route-decorator source string (Flask/FastAPI
 * `.route()`/`.get()`, bare `@Get()`, Spring `@GetMapping`, ...) into an HTTP
 * method + path for display. Never invents a method/path it can't find in
 * the string — falls back to nulls, and callers show the raw decorator text
 * instead. */
export interface ParsedRoute {
  method: string | null;
  path: string | null;
}

const VERB_FROM_CALL = /\.(get|post|put|delete|patch|websocket)\s*\(/i;
const BARE_VERB = /@(get|post|put|delete|patch|all)\s*\(/i;
const MAPPING_VERB = /@(get|post|put|delete|patch)mapping/i;
const METHODS_LIST_RE = /methods\s*=\s*\[\s*['"](\w+)['"]/i;
const PATH_RE = /\(\s*['"]([^'"]+)['"]/;

export function parseRouteHint(hint: string | null): ParsedRoute {
  if (!hint) return { method: null, path: null };

  let method: string | null = null;
  const verbMatch = hint.match(VERB_FROM_CALL) ?? hint.match(BARE_VERB) ?? hint.match(MAPPING_VERB);
  if (verbMatch) method = verbMatch[1].toUpperCase();

  const methodsListMatch = hint.match(METHODS_LIST_RE);
  if (methodsListMatch) method = methodsListMatch[1].toUpperCase();

  if (!method && /\.route\s*\(|RequestMapping/i.test(hint)) method = "ANY";

  const pathMatch = hint.match(PATH_RE);
  const path = pathMatch ? pathMatch[1] : null;

  return { method, path };
}
