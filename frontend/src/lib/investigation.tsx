import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Tab } from "@/lib/navigation";

/**
 * What the user was looking at when they asked to jump to another page —
 * e.g. Overview's "Investigate {component}" sets `componentId` and switches
 * to the Architecture tab. Consumers read this once on mount to focus
 * themselves, then it's up to them whether to clear it.
 */
export interface FocusTarget {
  componentId?: string;
  symbolUid?: string;
  qualifiedName?: string;
  /** A question to seed Ask the Archeologist with (e.g. from Execution Flow's "Explain" action). */
  presetQuestion?: string;
}

interface InvestigationContextValue {
  tab: Tab;
  focus: FocusTarget | null;
  navigate: (tab: Tab, focus?: FocusTarget) => void;
}

const InvestigationContext = createContext<InvestigationContextValue | null>(null);

export function InvestigationProvider({
  tab,
  onTabChange,
  children,
}: {
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  children: ReactNode;
}) {
  const [focus, setFocus] = useState<FocusTarget | null>(null);

  const value = useMemo<InvestigationContextValue>(
    () => ({
      tab,
      focus,
      navigate: (nextTab, nextFocus) => {
        setFocus(nextFocus ?? null);
        onTabChange(nextTab);
      },
    }),
    [tab, focus, onTabChange],
  );

  return <InvestigationContext.Provider value={value}>{children}</InvestigationContext.Provider>;
}

export function useInvestigation() {
  const ctx = useContext(InvestigationContext);
  if (!ctx) throw new Error("useInvestigation must be used within an InvestigationProvider");
  return ctx;
}
