import { NAV_GROUPS, type Tab } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function SidebarNav({
  activeTab,
  onSelect,
  onNavigate,
}: {
  activeTab: Tab;
  onSelect: (tab: Tab) => void;
  /** Called after a selection is made — used by the mobile drawer to close itself. */
  onNavigate?: () => void;
}) {
  return (
    <nav aria-label="Investigation stages" className="flex flex-col gap-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.stage}>
          <p className="mb-1.5 px-3 font-mono text-[0.65rem] font-semibold tracking-[0.14em] text-(--text-faint) uppercase">
            {group.stage}
          </p>
          <ul className="flex flex-col gap-0.5">
            {group.items.map((item) => {
              const isActive = item.tab === activeTab;
              const Icon = item.icon;
              return (
                <li key={item.tab}>
                  <button
                    type="button"
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => {
                      onSelect(item.tab);
                      onNavigate?.();
                    }}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
                      isActive
                        ? "bg-(--accent-soft) text-(--accent-text)"
                        : "text-(--text-soft) hover:bg-(--bg-sunken) hover:text-(--text)",
                    )}
                  >
                    <Icon className="size-4 shrink-0" strokeWidth={2} />
                    <span className="truncate">{item.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
