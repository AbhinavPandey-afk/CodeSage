import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Recurring "field record" section marker — a mono index number, an
 * uppercase label, and a thin fading rule. Used sparingly to open major
 * sections (see frontend-design skill §24: motifs should support the theme,
 * not decorate every heading).
 */
export function SectionLabel({
  index,
  children,
  className,
}: {
  index: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-center gap-3", className)}>
      <span className="font-mono text-xs font-semibold text-(--accent-text) tabular-nums">{index}</span>
      <span className="text-xs font-semibold tracking-[0.12em] text-(--text-faint) uppercase">
        {children}
      </span>
      <span className="stratum-rule flex-1" />
    </div>
  );
}
