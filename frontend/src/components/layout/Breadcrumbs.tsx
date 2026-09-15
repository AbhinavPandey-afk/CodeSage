import { ChevronRight } from "lucide-react";
import { Fragment } from "react";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  onClick?: () => void;
}

/** Reusable abstraction trail — e.g. Architecture > Payments > payment_service.py. */
export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn("flex flex-wrap items-center gap-1 text-sm", className)}>
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <Fragment key={i}>
            {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-(--text-faint)" />}
            {item.onClick && !isLast ? (
              <button
                onClick={item.onClick}
                className="rounded px-1 -mx-1 text-(--text-faint) hover:text-(--accent-text) hover:underline"
              >
                {item.label}
              </button>
            ) : (
              <span className={cn(isLast ? "font-medium text-(--text)" : "text-(--text-faint)")}>
                {item.label}
              </span>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
