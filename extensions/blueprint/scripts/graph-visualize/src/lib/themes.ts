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
  // Label font size (px at zoom 1)
  labelFontSize: number;
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
      "--background": hexToHsl("#ffffff"),            // page / main canvas background
      "--foreground": hexToHsl("#030712"),            // primary text color
      "--card": hexToHsl("#ffffff"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#030712"),       // text inside cards
      "--popover": hexToHsl("#ffffff"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#030712"),    // text inside popovers
      "--primary": hexToHsl("#0f172a"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#f8fafc"),    // text on primary buttons
      "--secondary": hexToHsl("#f1f5f9"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#0f172a"),  // text on secondary buttons
      "--muted": hexToHsl("#f1f5f9"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#64748b"),      // secondary / placeholder text
      "--accent": hexToHsl("#f1f5f9"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#0f172a"),     // text on accent hover
      "--destructive": hexToHsl("#ef4444"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#f8fafc"),// text on destructive buttons
      "--border": hexToHsl("#e2e8f0"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#e2e8f0"),                 // input field backgrounds
      "--ring": hexToHsl("#0f172a"),                  // focus ring / outline color
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
    labelFontSize: 13,
  },
  {
    key: "dark",
    label: "Dark",
    vars: {
      "--background": hexToHsl("#0a0a0a"),            // page / main canvas background
      "--foreground": hexToHsl("#e0e0e0"),            // primary text color
      "--card": hexToHsl("#0a0a0a"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#e0e0e0"),       // text inside cards
      "--popover": hexToHsl("#1a1a1a"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#e0e0e0"),    // text inside popovers
      "--primary": hexToHsl("#ffffff"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#0a0a0a"),    // text on primary buttons
      "--secondary": hexToHsl("#1a1a1a"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#e0e0e0"),  // text on secondary buttons
      "--muted": hexToHsl("#2a2a2a"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#888888"),      // secondary / placeholder text
      "--accent": hexToHsl("#ffffff"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#0a0a0a"),     // text on accent hover
      "--destructive": hexToHsl("#ff6b6b"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#0a0a0a"),// text on destructive buttons
      "--border": hexToHsl("#333333"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#333333"),                 // input field backgrounds
      "--ring": hexToHsl("#ffffff"),                  // focus ring / outline color
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
    labelFontSize: 13,
  },
  {
    key: "gruvbox",
    label: "Gruvbox Dark",
    vars: {
      "--background": hexToHsl("#1d2021"),            // page / main canvas background
      "--foreground": hexToHsl("#c3b89a"),            // primary text color
      "--card": hexToHsl("#3c3836"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#c3b89a"),       // text inside cards
      "--popover": hexToHsl("#3c3836"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#c3b89a"),    // text inside popovers
      "--primary": hexToHsl("#fabd2f"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#1d2021"),    // text on primary buttons
      "--secondary": hexToHsl("#504945"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#c3b89a"),  // text on secondary buttons
      "--muted": hexToHsl("#504945"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#a89984"),      // secondary / placeholder text
      "--accent": hexToHsl("#fabd2f"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#1d2021"),     // text on accent hover
      "--destructive": hexToHsl("#ff6b6b"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#1d2021"),// text on destructive buttons
      "--border": hexToHsl("#665c54"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#665c54"),                 // input field backgrounds
      "--ring": hexToHsl("#fabd2f"),                  // focus ring / outline color
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
    labelFontSize: 13,
  },
  {
    key: "gruvbox-light",
    label: "Gruvbox Light",
    vars: {
      "--background": hexToHsl("#fbf1c7"),            // page / main canvas background
      "--foreground": hexToHsl("#504945"),            // primary text color
      "--card": hexToHsl("#ebdbb2"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#504945"),       // text inside cards
      "--popover": hexToHsl("#ebdbb2"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#504945"),    // text inside popovers
      "--primary": hexToHsl("#d79921"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#1a1a1a"),    // text on primary buttons
      "--secondary": hexToHsl("#d5c4a1"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#504945"),  // text on secondary buttons
      "--muted": hexToHsl("#d5c4a1"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#7c6f64"),      // secondary / placeholder text
      "--accent": hexToHsl("#d79921"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#1a1a1a"),     // text on accent hover
      "--destructive": hexToHsl("#9d0006"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#fbf1c7"),// text on destructive buttons
      "--border": hexToHsl("#bdae93"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#bdae93"),                 // input field backgrounds
      "--ring": hexToHsl("#d79921"),                  // focus ring / outline color
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
    labelFontSize: 13,
  },
  {
    key: "neon",
    label: "Neon Dark",
    vars: {
      "--background": hexToHsl("#0d0221"),            // page / main canvas background
      "--foreground": hexToHsl("#00ffcc"),            // primary text color
      "--card": hexToHsl("#1a0a2e"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#00ffcc"),       // text inside cards
      "--popover": hexToHsl("#1a0a2e"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#00ffcc"),    // text inside popovers
      "--primary": hexToHsl("#00ffcc"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#0d0221"),    // text on primary buttons
      "--secondary": hexToHsl("#2d1b4e"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#00ffcc"),  // text on secondary buttons
      "--muted": hexToHsl("#2d1b4e"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#a09cff"),      // secondary / placeholder text
      "--accent": hexToHsl("#00ffcc"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#0d0221"),     // text on accent hover
      "--destructive": hexToHsl("#ff4081"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#0d0221"),// text on destructive buttons
      "--border": hexToHsl("#4a2c7a"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#4a2c7a"),                 // input field backgrounds
      "--ring": hexToHsl("#00ffcc"),                  // focus ring / outline color
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
    labelFontSize: 13,
  },
  {
    key: "retro",
    label: "Retro Light",
    vars: {
      "--background": hexToHsl("#fff0f5"),            // page / main canvas background
      "--foreground": hexToHsl("#4b0082"),            // primary text color
      "--card": hexToHsl("#ffffff"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#4b0082"),       // text inside cards
      "--popover": hexToHsl("#ffffff"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#4b0082"),    // text inside popovers
      "--primary": hexToHsl("#dda0dd"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#ffffff"),    // text on primary buttons
      "--secondary": hexToHsl("#f0e0ef"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#4b0082"),  // text on secondary buttons
      "--muted": hexToHsl("#f0e0ef"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#9370db"),      // secondary / placeholder text
      "--accent": hexToHsl("#dda0dd"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#ffffff"),     // text on accent hover
      "--destructive": hexToHsl("#ff69b4"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#ffffff"),// text on destructive buttons
      "--border": hexToHsl("#dda0dd"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#dda0dd"),                 // input field backgrounds
      "--ring": hexToHsl("#4b0082"),                  // focus ring / outline color
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
    labelFontSize: 13,
  },
  {
    key: "netrunner",
    label: "Netrunner",
    vars: {
      "--background": hexToHsl("#0A0F1F"),            // page / main canvas background
      "--foreground": hexToHsl("#F5F7FA"),            // primary text color
      "--card": hexToHsl("#121830"),                  // card / panel backgrounds
      "--card-foreground": hexToHsl("#F5F7FA"),       // text inside cards
      "--popover": hexToHsl("#121830"),               // dropdown / tooltip / popover bg
      "--popover-foreground": hexToHsl("#F5F7FA"),    // text inside popovers
      "--primary": hexToHsl("#00F0FF"),               // main action buttons, selected state
      "--primary-foreground": hexToHsl("#0A0F1F"),    // text on primary buttons
      "--secondary": hexToHsl("#1a2040"),             // secondary buttons, subtle backgrounds
      "--secondary-foreground": hexToHsl("#00F0FF"),  // text on secondary buttons
      "--muted": hexToHsl("#1a2040"),                 // muted / disabled backgrounds
      "--muted-foreground": hexToHsl("#8899aa"),      // secondary / placeholder text
      "--accent": hexToHsl("#FCEE0A"),                // hover / focus backgrounds
      "--accent-foreground": hexToHsl("#0A0F1F"),     // text on accent hover
      "--destructive": hexToHsl("#FF3131"),           // delete / error buttons
      "--destructive-foreground": hexToHsl("#F5F7FA"),// text on destructive buttons
      "--border": hexToHsl("#2a3050"),                // borders on inputs, cards, panels
      "--input": hexToHsl("#2a3050"),                 // input field backgrounds
      "--ring": hexToHsl("#00F0FF"),                  // focus ring / outline color
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
    labelFontSize: 13,
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
