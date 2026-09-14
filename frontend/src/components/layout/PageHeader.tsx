import type { ReactNode } from "react";

export function PageHeader({
  title,
  question,
  actions,
}: {
  title: string;
  /** The one dominant question this page answers (frontend-design skill §35). */
  question: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-(--border) pb-5">
      <div>
        <h1 className="font-display text-2xl font-medium tracking-tight text-(--text)">{title}</h1>
        <p className="mt-1 text-sm text-(--text-faint)">{question}</p>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
