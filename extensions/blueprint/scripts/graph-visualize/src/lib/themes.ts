/**
 * Theme definitions — single source of truth for all theming.
 * Each theme sets:
 *   - shadcn UI variables (--background, --foreground, etc.)
 *   - graph CSS variables (--bg, --surface, --text, etc.) for sidebar/UI
 *   - 12 node colors that cycle for node fill
 *   - single edge color (rgba)
 */

export interface Theme {
  key: string;
  label: string;
  // shadcn UI variables (HSL format)
  vars: Record<string, string>;
  // Graph CSS variables (hex/rgba) — used by graph.css for sidebar/UI styling
  legacyVars: Record<string, string>;
  // 12 node colors that cycle
  nodeColors: string[];
  // Single edge color (rgba)
  edgeColor: string;
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
      "--background": "0 0% 100%",
      "--foreground": "222.2 84% 4.9%",
      "--card": "0 0% 100%",
      "--card-foreground": "222.2 84% 4.9%",
      "--popover": "0 0% 100%",
      "--popover-foreground": "222.2 84% 4.9%",
      "--primary": "222.2 47.4% 11.2%",
      "--primary-foreground": "210 40% 98%",
      "--secondary": "210 40% 96.1%",
      "--secondary-foreground": "222.2 47.4% 11.2%",
      "--muted": "210 40% 96.1%",
      "--muted-foreground": "215.4 16.3% 46.9%",
      "--accent": "210 40% 96.1%",
      "--accent-foreground": "222.2 47.4% 11.2%",
      "--destructive": "0 84.2% 60.2%",
      "--destructive-foreground": "210 40% 98%",
      "--border": "214.3 31.8% 91.4%",
      "--input": "214.3 31.8% 91.4%",
      "--ring": "222.2 84% 4.9%",
    },
    legacyVars: {
      "--bg": "#ffffff",
      "--surface": "#f5f5f5",
      "--surface2": "#e8e8e8",
      "--btn-text": "#1a1a1a",
      "--text": "#1a1a1a",
      "--text-dim": "#666666",
      "--text-bright": "#000000",
      "--text-secondary": "#666666",
      "--accent": "#000000",
      "--accent-text": "#ffffff",
      "--accent-glow": "rgba(0, 0, 0, 0.1)",
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
    legacyVars: {
      "--bg": "#0a0a0a",
      "--surface": "#1a1a1a",
      "--surface2": "#2a2a2a",
      "--btn-text": "#e0e0e0",
      "--text": "#e0e0e0",
      "--text-dim": "#888888",
      "--text-bright": "#ffffff",
      "--text-secondary": "#888888",
      "--accent": "#ffffff",
      "--accent-text": "#0a0a0a",
      "--accent-glow": "rgba(255, 255, 255, 0.1)",
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
    legacyVars: {
      "--bg": "#1d2021",
      "--surface": "#3c3836",
      "--surface2": "#504945",
      "--btn-text": "#e0e0e0",
      "--text": "#c3b89a",
      "--text-dim": "#a89984",
      "--text-bright": "#d5c4a1",
      "--text-secondary": "#a89984",
      "--accent": "#fabd2f",
      "--accent-text": "#1a1a1a",
      "--accent-glow": "rgba(250, 189, 47, 0.15)",
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
    legacyVars: {
      "--bg": "#fbf1c7",
      "--surface": "#ebdbb2",
      "--surface2": "#d5c4a1",
      "--btn-text": "#504945",
      "--text": "#504945",
      "--text-dim": "#7c6f64",
      "--text-bright": "#282828",
      "--text-secondary": "#7c6f64",
      "--accent": "#d79921",
      "--accent-text": "#1a1a1a",
      "--accent-glow": "rgba(215, 153, 33, 0.15)",
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
    legacyVars: {
      "--bg": "#0d0221",
      "--surface": "#1a0a2e",
      "--surface2": "#2d1b4e",
      "--btn-text": "#00ffcc",
      "--text": "#00ffcc",
      "--text-dim": "#a09cff",
      "--text-bright": "#ff80ff",
      "--text-secondary": "#a09cff",
      "--accent": "#00ffcc",
      "--accent-text": "#0d0221",
      "--accent-glow": "rgba(0, 255, 204, 0.2)",
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
    legacyVars: {
      "--bg": "#fff0f5",
      "--surface": "#ffe4e1",
      "--surface2": "#ffdab9",
      "--btn-text": "#4b0082",
      "--text": "#4b0082",
      "--text-dim": "#9b1b9b",
      "--text-bright": "#1a0030",
      "--text-secondary": "#9b1b9b",
      "--accent": "#d6357f",
      "--accent-text": "#1a1a1a",
      "--accent-glow": "rgba(255, 105, 180, 0.2)",
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
  },
  {
    key: "netrunner",
    label: "⌘ Netrunner",
    vars: {
      "--background": hexToHsl("#080810"),
      "--foreground": hexToHsl("#e0e0ff"),
      "--card": hexToHsl("#12121f"),
      "--card-foreground": hexToHsl("#e0e0ff"),
      "--popover": hexToHsl("#12121f"),
      "--popover-foreground": hexToHsl("#e0e0ff"),
      "--primary": hexToHsl("#00dcff"),
      "--primary-foreground": hexToHsl("#080810"),
      "--secondary": hexToHsl("#1a1a2e"),
      "--secondary-foreground": hexToHsl("#00dcff"),
      "--muted": hexToHsl("#1a1a2e"),
      "--muted-foreground": hexToHsl("#8888aa"),
      "--accent": hexToHsl("#00dcff"),
      "--accent-foreground": hexToHsl("#080810"),
      "--destructive": hexToHsl("#ff2d6b"),
      "--destructive-foreground": hexToHsl("#080810"),
      "--border": hexToHsl("#2a2a4a"),
      "--input": hexToHsl("#2a2a4a"),
      "--ring": hexToHsl("#00dcff"),
    },
    legacyVars: {
      "--bg": "#080810",
      "--surface": "#12121f",
      "--surface2": "#1a1a2e",
      "--btn-text": "#00dcff",
      "--text": "#e0e0ff",
      "--text-dim": "#8888aa",
      "--text-bright": "#ffffff",
      "--text-secondary": "#8888aa",
      "--accent": "#00dcff",
      "--accent-text": "#080810",
      "--accent-glow": "rgba(0, 220, 255, 0.2)",
    },
    nodeColors: [
      "#00dcff",
      "#ff2d6b",
      "#c8ff00",
      "#ff6b00",
      "#a020f0",
      "#00ff9d",
      "#ff9fff",
      "#ffcc00",
      "#0af0a0",
      "#ff4444",
      "#4db8ff",
      "#e040fb",
    ],
    edgeColor: "rgba(0, 220, 255, 0.35)",
  },
  {
    key: "netrunner-light",
    label: "⌘ Netrunner Light",

    vars: {
      "--background": hexToHsl("#f4f6fc"),
      "--foreground": hexToHsl("#0a0e1a"),

      "--card": hexToHsl("#ffffff"),
      "--card-foreground": hexToHsl("#0a0e1a"),

      "--popover": hexToHsl("#ffffff"),
      "--popover-foreground": hexToHsl("#0a0e1a"),

      "--primary": hexToHsl("#0088cc"),
      "--primary-foreground": hexToHsl("#f4f6fc"),

      "--secondary": hexToHsl("#e2eaf5"),
      "--secondary-foreground": hexToHsl("#0a0e1a"),

      "--muted": hexToHsl("#e2eaf5"),
      "--muted-foreground": hexToHsl("#4a5568"),

      "--accent": hexToHsl("#0088cc"),
      "--accent-foreground": hexToHsl("#f4f6fc"),

      "--destructive": hexToHsl("#e01535"),
      "--destructive-foreground": hexToHsl("#ffffff"),

      "--border": hexToHsl("#c8d4e8"),
      "--input": hexToHsl("#c8d4e8"),

      "--ring": hexToHsl("#0088cc"),
    },

    legacyVars: {
      "--bg": "#f4f6fc",
      "--surface": "#ffffff",
      "--surface2": "#e2eaf5",

      "--btn-text": "#0a0e1a",

      "--text": "#0a0e1a",
      "--text-dim": "#4a5568",
      "--text-bright": "#000000",
      "--text-secondary": "#4a5568",

      "--accent": "#0088cc",
      "--accent-text": "#f4f6fc",

      "--accent-glow": "rgba(0,136,204,0.25)",
    },

    nodeColors: [
      "#0088cc",  // electric blue
      "#e01535",  // vivid red
      "#22c55e",  // bright green
      "#f59e0b",  // amber
      "#8b5cf6",  // violet
      "#10b981",  // emerald
      "#ec4899",  // pink
      "#f97316",  // orange
      "#06b6d4",  // cyan
      "#ef4444",  // red
      "#3b82f6",  // blue
      "#a855f7",  // purple
    ],

    edgeColor: "rgba(0, 136, 204, 0.4)",
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
  // Apply legacy graph CSS variables
  for (const [key, value] of Object.entries(theme.legacyVars)) {
    root.style.setProperty(key, value);
  }
  // Apply edge color
  root.style.setProperty("--edge-color", theme.edgeColor);
  // Apply 12 node colors
  for (let i = 0; i < 12; i++) {
    root.style.setProperty(`--node-color-${i}`, theme.nodeColors[i]);
  }
  // Toggle dark class for compatibility
  const darkKeys = ["dark", "gruvbox", "neon", "netrunner"];
  if (darkKeys.includes(themeKey)) {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}
