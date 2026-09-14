import { AnimatePresence, motion } from "motion/react";
import { type ReactNode, useState } from "react";
import { SidebarNav } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import type { Repository } from "@/api/types";
import type { Tab } from "@/lib/navigation";

export function AppShell({
  repository,
  tab,
  onTabChange,
  onReset,
  children,
}: {
  repository: Repository | null;
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  onReset: () => void;
  children: ReactNode;
}) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const showSidebar = repository?.status === "ready";

  return (
    <div className="flex min-h-screen flex-col bg-(--bg) text-(--text)">
      <TopBar
        repository={repository}
        onReset={onReset}
        menuOpen={mobileNavOpen}
        onMenuToggle={() => setMobileNavOpen((v) => !v)}
        showMenuButton={showSidebar}
      />

      <div className="flex flex-1">
        {showSidebar && (
          <aside className="hidden w-60 shrink-0 border-r border-(--border) px-3 py-5 md:block">
            <SidebarNav activeTab={tab} onSelect={onTabChange} />
          </aside>
        )}

        <AnimatePresence>
          {showSidebar && mobileNavOpen && (
            <>
              <motion.div
                key="backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="fixed inset-0 z-40 bg-black/40 md:hidden"
                onClick={() => setMobileNavOpen(false)}
              />
              <motion.aside
                key="drawer"
                initial={{ x: "-100%" }}
                animate={{ x: 0 }}
                exit={{ x: "-100%" }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className="fixed inset-y-0 left-0 z-50 w-64 overflow-y-auto border-r border-(--border) bg-(--bg) px-3 py-5 md:hidden"
              >
                <SidebarNav activeTab={tab} onSelect={onTabChange} onNavigate={() => setMobileNavOpen(false)} />
              </motion.aside>
            </>
          )}
        </AnimatePresence>

        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
