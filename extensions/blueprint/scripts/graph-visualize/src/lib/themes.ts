/**
 * Theme definitions — maps legacy theme palettes to shadcn CSS variables.
 * Each theme sets :root variables that shadcn components + D3 canvas both consume.
 */

export interface Theme {
  key: string
  label: string
  // shadcn UI variables (HSL format)
  vars: Record<string, string>
  // Canvas-specific CSS variables (hex/rgba)
  canvasVars: Record<string, string>
}

function hexToHsl(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h = 0, s = 0, l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break
      case g: h = ((b - r) / d + 2) / 6; break
      case b: h = ((r - g) / d + 4) / 6; break
    }
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`
}

export const themes: Theme[] = [
  {
    key: 'default',
    label: 'Default Light',
    vars: {
      '--background': '0 0% 100%',
      '--foreground': '222.2 84% 4.9%',
      '--card': '0 0% 100%',
      '--card-foreground': '222.2 84% 4.9%',
      '--popover': '0 0% 100%',
      '--popover-foreground': '222.2 84% 4.9%',
      '--primary': '222.2 47.4% 11.2%',
      '--primary-foreground': '210 40% 98%',
      '--secondary': '210 40% 96.1%',
      '--secondary-foreground': '222.2 47.4% 11.2%',
      '--muted': '210 40% 96.1%',
      '--muted-foreground': '215.4 16.3% 46.9%',
      '--accent': '210 40% 96.1%',
      '--accent-foreground': '222.2 47.4% 11.2%',
      '--destructive': '0 84.2% 60.2%',
      '--destructive-foreground': '210 40% 98%',
      '--border': '214.3 31.8% 91.4%',
      '--input': '214.3 31.8% 91.4%',
      '--ring': '222.2 84% 4.9%',
    },
    canvasVars: {
      '--edge-color': 'rgba(148, 163, 184, 0.4)',
      '--edge-related': 'rgba(148, 163, 184, 0.4)',
      '--edge-spec': 'rgba(52, 211, 153, 0.4)',
      '--edge-cross': 'rgba(255, 170, 0, 0.3)',
    },
  },
  {
    key: 'dark',
    label: 'Dark',
    vars: {
      '--background': '222.2 84% 4.9%',
      '--foreground': '210 40% 98%',
      '--card': '222.2 84% 4.9%',
      '--card-foreground': '210 40% 98%',
      '--popover': '222.2 84% 4.9%',
      '--popover-foreground': '210 40% 98%',
      '--primary': '210 40% 98%',
      '--primary-foreground': '222.2 47.4% 11.2%',
      '--secondary': '217.2 32.6% 17.5%',
      '--secondary-foreground': '210 40% 98%',
      '--muted': '217.2 32.6% 17.5%',
      '--muted-foreground': '215 20.2% 65.1%',
      '--accent': '217.2 32.6% 17.5%',
      '--accent-foreground': '210 40% 98%',
      '--destructive': '0 62.8% 30.6%',
      '--destructive-foreground': '210 40% 98%',
      '--border': '217.2 32.6% 17.5%',
      '--input': '217.2 32.6% 17.5%',
      '--ring': '212.7 26.8% 83.9%',
    },
    canvasVars: {
      '--edge-color': 'rgba(148, 163, 184, 0.3)',
      '--edge-related': 'rgba(148, 163, 184, 0.3)',
      '--edge-spec': 'rgba(52, 211, 153, 0.3)',
      '--edge-cross': 'rgba(255, 170, 0, 0.25)',
    },
  },
  {
    key: 'gruvbox',
    label: 'Gruvbox Dark',
    vars: {
      '--background': hexToHsl('#1d2021'),
      '--foreground': hexToHsl('#c3b89a'),
      '--card': hexToHsl('#3c3836'),
      '--card-foreground': hexToHsl('#c3b89a'),
      '--popover': hexToHsl('#3c3836'),
      '--popover-foreground': hexToHsl('#c3b89a'),
      '--primary': hexToHsl('#fabd2f'),
      '--primary-foreground': hexToHsl('#1d2021'),
      '--secondary': hexToHsl('#504945'),
      '--secondary-foreground': hexToHsl('#c3b89a'),
      '--muted': hexToHsl('#504945'),
      '--muted-foreground': hexToHsl('#a89984'),
      '--accent': hexToHsl('#fabd2f'),
      '--accent-foreground': hexToHsl('#1d2021'),
      '--destructive': hexToHsl('#ff6b6b'),
      '--destructive-foreground': hexToHsl('#1d2021'),
      '--border': hexToHsl('#665c54'),
      '--input': hexToHsl('#665c54'),
      '--ring': hexToHsl('#fabd2f'),
    },
    canvasVars: {
      '--edge-color': 'rgba(121, 134, 203, 0.3)',
      '--edge-related': 'rgba(121, 134, 203, 0.3)',
      '--edge-spec': 'rgba(77, 182, 172, 0.3)',
      '--edge-cross': 'rgba(255, 183, 77, 0.3)',
    },
  },
  {
    key: 'neon',
    label: 'Neon Dark',
    vars: {
      '--background': hexToHsl('#0d0221'),
      '--foreground': hexToHsl('#00ffcc'),
      '--card': hexToHsl('#1a0a2e'),
      '--card-foreground': hexToHsl('#00ffcc'),
      '--popover': hexToHsl('#1a0a2e'),
      '--popover-foreground': hexToHsl('#00ffcc'),
      '--primary': hexToHsl('#00ffcc'),
      '--primary-foreground': hexToHsl('#0d0221'),
      '--secondary': hexToHsl('#2d1b4e'),
      '--secondary-foreground': hexToHsl('#00ffcc'),
      '--muted': hexToHsl('#2d1b4e'),
      '--muted-foreground': hexToHsl('#a09cff'),
      '--accent': hexToHsl('#00ffcc'),
      '--accent-foreground': hexToHsl('#0d0221'),
      '--destructive': hexToHsl('#ff4081'),
      '--destructive-foreground': hexToHsl('#0d0221'),
      '--border': hexToHsl('#4a2c7a'),
      '--input': hexToHsl('#4a2c7a'),
      '--ring': hexToHsl('#00ffcc'),
    },
    canvasVars: {
      '--edge-color': 'rgba(68, 138, 255, 0.3)',
      '--edge-related': 'rgba(68, 138, 255, 0.3)',
      '--edge-spec': 'rgba(0, 229, 255, 0.3)',
      '--edge-cross': 'rgba(255, 193, 7, 0.3)',
    },
  },
  {
    key: 'retro',
    label: 'Retro Light',
    vars: {
      '--background': hexToHsl('#fff0f5'),
      '--foreground': hexToHsl('#4b0082'),
      '--card': hexToHsl('#ffffff'),
      '--card-foreground': hexToHsl('#4b0082'),
      '--popover': hexToHsl('#ffffff'),
      '--popover-foreground': hexToHsl('#4b0082'),
      '--primary': hexToHsl('#dda0dd'),
      '--primary-foreground': hexToHsl('#ffffff'),
      '--secondary': hexToHsl('#f0e0ef'),
      '--secondary-foreground': hexToHsl('#4b0082'),
      '--muted': hexToHsl('#f0e0ef'),
      '--muted-foreground': hexToHsl('#9370db'),
      '--accent': hexToHsl('#dda0dd'),
      '--accent-foreground': hexToHsl('#ffffff'),
      '--destructive': hexToHsl('#ff69b4'),
      '--destructive-foreground': hexToHsl('#ffffff'),
      '--border': hexToHsl('#dda0dd'),
      '--input': hexToHsl('#dda0dd'),
      '--ring': hexToHsl('#4b0082'),
    },
    canvasVars: {
      '--edge-color': 'rgba(155, 89, 182, 0.3)',
      '--edge-related': 'rgba(155, 89, 182, 0.3)',
      '--edge-spec': 'rgba(52, 211, 153, 0.3)',
      '--edge-cross': 'rgba(255, 105, 180, 0.3)',
    },
  },
]

/**
 * Apply a theme by setting CSS variables on :root (document.documentElement).
 */
export function applyTheme(themeKey: string): void {
  const theme = themes.find((t) => t.key === themeKey)
  if (!theme) return

  const root = document.documentElement
  // Apply shadcn UI variables
  for (const [key, value] of Object.entries(theme.vars)) {
    root.style.setProperty(key, value)
  }
  // Apply canvas-specific variables
  for (const [key, value] of Object.entries(theme.canvasVars)) {
    root.style.setProperty(key, value)
  }
  // Toggle dark class for compatibility
  const darkKeys = ['dark', 'gruvbox', 'neon']
  if (darkKeys.includes(themeKey)) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}
