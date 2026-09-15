import {
  Compass,
  Hammer,
  History,
  Layers3,
  Network,
  Radar,
  Route,
  ScrollText,
  SearchCheck,
  type LucideIcon,
} from "lucide-react";

export type Tab =
  | "overview"
  | "architecture"
  | "flow"
  | "graph"
  | "smells"
  | "optimization"
  | "impact"
  | "history"
  | "ask";

export interface NavItem {
  tab: Tab;
  label: string;
  icon: LucideIcon;
  question: string;
}

export interface NavGroup {
  stage: string;
  items: NavItem[];
}

/** Mirrors CLAUDE.md §4's six capability areas, collapsed to the five stages
 * that apply once a repository is loaded (Excavate happens before this). */
export const NAV_GROUPS: NavGroup[] = [
  {
    stage: "Site",
    items: [
      {
        tab: "overview",
        label: "Overview",
        icon: Compass,
        question: "What did CodeBase Archeologist discover?",
      },
    ],
  },
  {
    stage: "Reconstruct",
    items: [
      {
        tab: "architecture",
        label: "Architecture",
        icon: Layers3,
        question: "What architecture does this repository implement?",
      },
      {
        tab: "flow",
        label: "Execution Flow",
        icon: Route,
        question: "How does an operation move through the system?",
      },
    ],
  },
  {
    stage: "Analyze",
    items: [
      {
        tab: "graph",
        label: "Evidence Explorer",
        icon: Network,
        question: "What evidence connects these parts?",
      },
      {
        tab: "smells",
        label: "Architecture Analysis",
        icon: SearchCheck,
        question: "What structural problems exist?",
      },
      {
        tab: "impact",
        label: "Impact & Risk",
        icon: Radar,
        question: "What could break if I change this?",
      },
    ],
  },
  {
    stage: "Improve",
    items: [
      {
        tab: "optimization",
        label: "Optimization",
        icon: Hammer,
        question: "How could these problems be improved?",
      },
    ],
  },
  {
    stage: "History",
    items: [
      {
        tab: "history",
        label: "Historical Record",
        icon: History,
        question: "How did this system evolve?",
      },
    ],
  },
  {
    stage: "Explain",
    items: [
      {
        tab: "ask",
        label: "Ask the Archeologist",
        icon: ScrollText,
        question: "What does the evidence tell me?",
      },
    ],
  },
];
