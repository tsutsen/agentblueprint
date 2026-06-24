/**
 * Theme definitions — single source of truth for all theming.
 * Each theme sets:
 *   - shadcn UI variables (--background, --foreground, etc.)

 *   - 12 node colors that cycle for node fill
 *   - single edge color (rgba)
 */

export interface Theme {
  key: string;
  label: string;
  // shadcn UI variables (HSL format)
  vars: Record<string, string>;

  // 12 node colors that cycle
  nodeColors: string[];
  // Single edge color (rgba)
  edgeColor: string;
  // Node outline thickness (px at zoom 1)
  nodeStrokeWidth: number;
  // Node outline color (default: darker version of node color)
  nodeStrokeColor?: string;
  // Node outline color when selected
  nodeStrokeSelectedColor?: string;
  // Node outline color when hovered
  nodeStrokeHoverColor?: string;
}

function hexToHsl(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b),
    min = Math.min(r, g, b);
  let h = 0,
    s = 0,
    l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
        break;
      case g:
        h = ((b - r) / d + 2) / 6;
        break;
      case b:
        h = ((r - g) / d + 4) / 6;
        break;
    }
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

export const themes: Theme[] = [
  {
    key: "default",
    label: "Default Light",
    vars: {
      "--background": hexToHsl("#ffffff"),
      "--foreground": hexToHsl("#030712"),
      "--card": hexToHsl("#ffffff"),
      "--card-foreground": hexToHsl("#030712"),
      "--popover": hexToHsl("#ffffff"),
      "--popover-foreground": hexToHsl("#030712"),
      "--primary": hexToHsl("#0f172a"),
      "--primary-foreground": hexToHsl("#f8fafc"),
      "--secondary": hexToHsl("#f1f5f9"),
      "--secondary-foreground": hexToHsl("#0f172a"),
      "--muted": hexToHsl("#f1f5f9"),
      "--muted-foreground": hexToHsl("#64748b"),
      "--accent": hexToHsl("#f1f5f9"),
      "--accent-foreground": hexToHsl("#0f172a"),
      "--destructive": hexToHsl("#ef4444"),
      "--destructive-foreground": hexToHsl("#f8fafc"),
      "--border": hexToHsl("#e2e8f0"),
      "--input": hexToHsl("#e2e8f0"),
      "--ring": hexToHsl("#0f172a"),
    },
    nodeColors: [
      "#3b82f6",
      "#ef4444",
      "#10b981",
      "#f59e0b",
      "#8b5cf6",
      "#ec4899",
      "#06b6d4",
      "#f97316",
      "#6366f1",
      "#14b8a6",
      "#e11d48",
      "#84cc16",
    ],
    edgeColor: "rgba(148, 163, 184, 0.4)",
    nodeStrokeWidth: 1.5,
  },
  {
    key: "dark",
    label: "Dark",
    vars: {
      "--background": hexToHsl("#0a0a0a"),
      "--foreground": hexToHsl("#e0e0e0"),
      "--card": hexToHsl("#0a0a0a"),
      "--card-foreground": hexToHsl("#e0e0e0"),
      "--popover": hexToHsl("#1a1a1a"),
      "--popover-foreground": hexToHsl("#e0e0e0"),
      "--primary": hexToHsl("#ffffff"),
      "--primary-foreground": hexToHsl("#0a0a0a"),
      "--secondary": hexToHsl("#1a1a1a"),
      "--secondary-foreground": hexToHsl("#e0e0e0"),
      "--muted": hexToHsl("#2a2a2a"),
      "--muted-foreground": hexToHsl("#888888"),
      "--accent": hexToHsl("#ffffff"),
      "--accent-foreground": hexToHsl("#0a0a0a"),
      "--destructive": hexToHsl("#ff6b6b"),
      "--destructive-foreground": hexToHsl("#0a0a0a"),
      "--border": hexToHsl("#333333"),
      "--input": hexToHsl("#333333"),
      "--ring": hexToHsl("#ffffff"),
    },
    nodeColors: [
      "#60a5fa",
      "#f87171",
      "#34d399",
      "#fbbf24",
      "#a78bfa",
      "#f472b6",
      "#22d3ee",
      "#fb923c",
      "#818cf8",
      "#2dd4bf",
      "#fb7185",
      "#a3e635",
    ],
    edgeColor: "rgba(148, 163, 184, 0.4)",
    nodeStrokeWidth: 1.5,
  },
  {
    key: "gruvbox",
    label: "Gruvbox Dark",
    vars: {
      "--background": hexToHsl("#1d2021"),
      "--foreground": hexToHsl("#c3b89a"),
      "--card": hexToHsl("#3c3836"),
      "--card-foreground": hexToHsl("#c3b89a"),
      "--popover": hexToHsl("#3c3836"),
      "--popover-foreground": hexToHsl("#c3b89a"),
      "--primary": hexToHsl("#fabd2f"),
      "--primary-foreground": hexToHsl("#1d2021"),
      "--secondary": hexToHsl("#504945"),
      "--secondary-foreground": hexToHsl("#c3b89a"),
      "--muted": hexToHsl("#504945"),
      "--muted-foreground": hexToHsl("#a89984"),
      "--accent": hexToHsl("#fabd2f"),
      "--accent-foreground": hexToHsl("#1d2021"),
      "--destructive": hexToHsl("#ff6b6b"),
      "--destructive-foreground": hexToHsl("#1d2021"),
      "--border": hexToHsl("#665c54"),
      "--input": hexToHsl("#665c54"),
      "--ring": hexToHsl("#fabd2f"),
    },
    nodeColors: [
      "#83a598",
      "#fb4934",
      "#b8bb26",
      "#fabd2f",
      "#d3869b",
      "#fe8019",
      "#8ec07c",
      "#ebdbb2",
      "#7cafc2",
      "#d65d0e",
      "#cc241d",
      "#98971a",
    ],
    edgeColor: "rgba(121, 134, 203, 0.3)",
    nodeStrokeWidth: 1.5,
  },
  {
    key: "gruvbox-light",
    label: "Gruvbox Light",
    vars: {
      "--background": hexToHsl("#fbf1c7"),
      "--foreground": hexToHsl("#504945"),
      "--card": hexToHsl("#ebdbb2"),
      "--card-foreground": hexToHsl("#504945"),
      "--popover": hexToHsl("#ebdbb2"),
      "--popover-foreground": hexToHsl("#504945"),
      "--primary": hexToHsl("#d79921"),
      "--primary-foreground": hexToHsl("#1a1a1a"),
      "--secondary": hexToHsl("#d5c4a1"),
      "--secondary-foreground": hexToHsl("#504945"),
      "--muted": hexToHsl("#d5c4a1"),
      "--muted-foreground": hexToHsl("#7c6f64"),
      "--accent": hexToHsl("#d79921"),
      "--accent-foreground": hexToHsl("#1a1a1a"),
      "--destructive": hexToHsl("#9d0006"),
      "--destructive-foreground": hexToHsl("#fbf1c7"),
      "--border": hexToHsl("#bdae93"),
      "--input": hexToHsl("#bdae93"),
      "--ring": hexToHsl("#d79921"),
    },
    nodeColors: [
      "#047587",
      "#b91c1c",
      "#15803d",
      "#a16207",
      "#6d28d9",
      "#be185d",
      "#0e7490",
      "#c2410c",
      "#4f46e5",
      "#0f766e",
      "#9f1239",
      "#4d7c0f",
    ],
    edgeColor: "rgba(121, 134, 203, 0.3)",
    nodeStrokeWidth: 1.5,
  },
  {
    key: "neon",
    label: "Neon Dark",
    vars: {
      "--background": hexToHsl("#0d0221"),
      "--foreground": hexToHsl("#00ffcc"),
      "--card": hexToHsl("#1a0a2e"),
      "--card-foreground": hexToHsl("#00ffcc"),
      "--popover": hexToHsl("#1a0a2e"),
      "--popover-foreground": hexToHsl("#00ffcc"),
      "--primary": hexToHsl("#00ffcc"),
      "--primary-foreground": hexToHsl("#0d0221"),
      "--secondary": hexToHsl("#2d1b4e"),
      "--secondary-foreground": hexToHsl("#00ffcc"),
      "--muted": hexToHsl("#2d1b4e"),
      "--muted-foreground": hexToHsl("#a09cff"),
      "--accent": hexToHsl("#00ffcc"),
      "--accent-foreground": hexToHsl("#0d0221"),
      "--destructive": hexToHsl("#ff4081"),
      "--destructive-foreground": hexToHsl("#0d0221"),
      "--border": hexToHsl("#4a2c7a"),
      "--input": hexToHsl("#4a2c7a"),
      "--ring": hexToHsl("#00ffcc"),
    },
    nodeColors: [
      "#00ffcc",
      "#ff4081",
      "#00e676",
      "#ffea00",
      "#7c4dff",
      "#ff6e40",
      "#00b0ff",
      "#ff9100",
      "#651fff",
      "#1de9b6",
      "#f50057",
      "#76ff03",
    ],
    edgeColor: "rgba(68, 138, 255, 0.3)",
    nodeStrokeWidth: 1.5,
  },
  {
    key: "retro",
    label: "Retro Light",
    vars: {
      "--background": hexToHsl("#fff0f5"),
      "--foreground": hexToHsl("#4b0082"),
      "--card": hexToHsl("#ffffff"),
      "--card-foreground": hexToHsl("#4b0082"),
      "--popover": hexToHsl("#ffffff"),
      "--popover-foreground": hexToHsl("#4b0082"),
      "--primary": hexToHsl("#dda0dd"),
      "--primary-foreground": hexToHsl("#ffffff"),
      "--secondary": hexToHsl("#f0e0ef"),
      "--secondary-foreground": hexToHsl("#4b0082"),
      "--muted": hexToHsl("#f0e0ef"),
      "--muted-foreground": hexToHsl("#9370db"),
      "--accent": hexToHsl("#dda0dd"),
      "--accent-foreground": hexToHsl("#ffffff"),
      "--destructive": hexToHsl("#ff69b4"),
      "--destructive-foreground": hexToHsl("#ffffff"),
      "--border": hexToHsl("#dda0dd"),
      "--input": hexToHsl("#dda0dd"),
      "--ring": hexToHsl("#4b0082"),
    },
    nodeColors: [
      "#6a0dad",
      "#c62828",
      "#2e7d32",
      "#f57f17",
      "#4a148c",
      "#ad1457",
      "#006064",
      "#e65100",
      "#1a237e",
      "#004d40",
      "#880e4f",
      "#33691e",
    ],
    edgeColor: "rgba(155, 89, 182, 0.3)",
    nodeStrokeWidth: 1.5,
  },
  {
    key: "netrunner",
    label: "Netrunner",
    vars: {
      "--background": hexToHsl("#0A0F1F"),
      "--foreground": hexToHsl("#F5F7FA"),
      "--card": hexToHsl("#121830"),
      "--card-foreground": hexToHsl("#F5F7FA"),
      "--popover": hexToHsl("#121830"),
      "--popover-foreground": hexToHsl("#F5F7FA"),
      "--primary": hexToHsl("#00F0FF"),
      "--primary-foreground": hexToHsl("#0A0F1F"),
      "--secondary": hexToHsl("#1a2040"),
      "--secondary-foreground": hexToHsl("#00F0FF"),
      "--muted": hexToHsl("#1a2040"),
      "--muted-foreground": hexToHsl("#8899aa"),
      "--accent": hexToHsl("#FCEE0A"),
      "--accent-foreground": hexToHsl("#0A0F1F"),
      "--destructive": hexToHsl("#FF3131"),
      "--destructive-foreground": hexToHsl("#F5F7FA"),
      "--border": hexToHsl("#2a3050"),
      "--input": hexToHsl("#2a3050"),
      "--ring": hexToHsl("#00F0FF"),
    },
    nodeColors: [
      "#FF2A6D",  // magenta
      "#FF3131",  // red
      "#FCEE0A",  // signature yellow
      "#00F0FF",  // cyan
      "#9D4EDD",  // purple
      "#00FF9D",  // neon green
      "#FF6B6B",  // coral
      "#FFAA00",  // orange
      "#00CCDD",  // teal
      "#FF4444",  // bright red
      "#4DB8FF",  // sky blue
      "#E040FB",  // pink-purple
    ],
    edgeColor: "rgba(0, 240, 255, 0.35)",
    nodeStrokeWidth: 2,
  },
];

/**
 * Apply a theme by setting CSS variables on :root (document.documentElement).
 * Sets shadcn, legacy graph, and canvas variables from a single source of truth.
 */
export function applyTheme(themeKey: string): void {
  const theme = themes.find((t) => t.key === themeKey);
  if (!theme) return;

  const root = document.documentElement;
  // Apply shadcn UI variables
  for (const [key, value] of Object.entries(theme.vars)) {
    root.style.setProperty(key, value);
  }
  // Apply edge color
  root.style.setProperty("--edge-color", theme.edgeColor);
  // Apply 12 node colors
  for (let i = 0; i < 12; i++) {
    root.style.setProperty(`--node-color-${i}`, theme.nodeColors[i]);
  }
  // Apply node stroke width
  root.style.setProperty("--node-stroke-width", theme.nodeStrokeWidth.toString());
  // Apply node stroke colors
  root.style.setProperty("--node-stroke", theme.nodeStrokeColor || "");
  root.style.setProperty("--node-stroke-selected", theme.nodeStrokeSelectedColor || "#fff");
  root.style.setProperty("--node-stroke-hover", theme.nodeStrokeHoverColor || "#fff");
  // Toggle dark class for compatibility
  const darkKeys = ["dark", "gruvbox", "neon", "netrunner"];
  if (darkKeys.includes(themeKey)) {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}
