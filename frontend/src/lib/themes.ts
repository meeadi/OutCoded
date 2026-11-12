// Every theme the player can pick. The look itself lives in index.css under
// [data-theme="<id>"]; this list is for the picker (names, vibes, previews).
export const THEMES = [
  {
    id: 'midnight',
    name: 'midnight',
    vibe: 'the original. calm and dark.',
    swatch: { bg: '#14151a', text: '#e6e6e6', accent: '#7c5cff' },
  },
  {
    id: 'paper',
    name: 'paper',
    vibe: 'light, warm, easy on the eyes.',
    swatch: { bg: '#f4f1ea', text: '#2b2a27', accent: '#d9480f' },
  },
  {
    id: 'matcha',
    name: 'matcha',
    vibe: 'earthy greens.',
    swatch: { bg: '#1d2420', text: '#dfe8d8', accent: '#a3c76d' },
  },
  {
    id: 'neon',
    name: 'neon',
    vibe: 'synthwave glow and a grid horizon.',
    swatch: { bg: 'linear-gradient(180deg, #0d0221, #2a0a4a)', text: '#f3e8ff', accent: '#ff2fd0' },
  },
  {
    id: 'terminal',
    name: 'terminal',
    vibe: 'green phosphor CRT, scanlines and all.',
    swatch: { bg: '#030a04', text: '#4dff88', accent: '#c6ff3d' },
  },
  {
    id: 'sunset',
    name: 'sunset',
    vibe: 'golden hour behind the mountains.',
    swatch: { bg: 'linear-gradient(160deg, #2b1a3d, #7a3b4a)', text: '#ffeede', accent: '#ffb36b' },
  },
    {
    id: 'aurora',
    name: 'aurora',
    vibe: 'northern lights over a starry night.',
    swatch: { bg: 'linear-gradient(180deg, #0b1a2e, #070b1a)', text: '#e6f0ff', accent: '#5cf2b0' },
  },
  {
    id: 'lofi',
    name: 'lofi rain',
    vibe: 'rain on the window, lamp on, beats on.',
    swatch: { bg: 'linear-gradient(180deg, #1d2232, #171b25)', text: '#e8e2d6', accent: '#f2b16b' },
  },
  {
    id: 'sakura',
    name: 'sakura',
    vibe: 'cherry blossoms drifting by.',
    swatch: { bg: '#fbf3ee', text: '#3b2a2f', accent: '#e0567f' },
  },
  {
    id: 'deepsea',
    name: 'deep sea',
    vibe: 'bubbles, light beams, total calm.',
    swatch: { bg: 'linear-gradient(180deg, #06324a, #031827)', text: '#dff6ff', accent: '#3ee6d8' },
  },
] as const

export type ThemeId = (typeof THEMES)[number]['id']

export function isThemeId(value: string | null): value is ThemeId {
  return THEMES.some((t) => t.id === value)
}

// Paint the page with a theme (the picker uses this to preview on hover).
export function paintTheme(id: ThemeId): void {
  document.documentElement.dataset.theme = id
}