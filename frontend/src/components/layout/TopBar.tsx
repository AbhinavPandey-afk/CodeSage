import { Menu, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/evidence/StatusPill";
import type { Repository } from "@/api/types";

export function TopBar({
  repository,
  onReset,
  menuOpen,
  onMenuToggle,
  showMenuButton,
}: {
  repository: Repository | null;
  onReset: () => void;
  menuOpen: boolean;
  onMenuToggle: () => void;
  showMenuButton: boolean;
}) {
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-(--border) bg-(--bg)/92 px-4 backdrop-blur-sm sm:px-6">
      {showMenuButton && (
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen}
          onClick={onMenuToggle}
          className="md:hidden"
        >
          {menuOpen ? <X className="size-4" /> : <Menu className="size-4" />}
        </Button>
      )}

      <div className="flex min-w-0 items-baseline gap-2.5">
        <span className="font-display shrink-0 text-[1.05rem] font-medium tracking-tight text-(--text)">
          CodeBase Archeologist
        </span>
        <span className="hidden truncate font-mono text-[0.72rem] text-(--text-faint) sm:inline">
          Evidence-driven architecture reconstruction
        </span>
      </div>

      {repository && (
        <div className="ml-auto flex min-w-0 items-center gap-2.5">
          <span className="hidden truncate font-mono text-[0.8rem] text-(--text-soft) sm:inline">
            {repository.owner}/{repository.name}
          </span>
          <StatusPill status={repository.status} />
          <Button variant="ghost" size="icon-sm" aria-label="Analyze a different repository" onClick={onReset}>
            <RotateCcw className="size-3.5" />
          </Button>
        </div>
      )}
    </header>
  );
}
