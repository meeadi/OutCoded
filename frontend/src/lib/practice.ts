// Practice: modes, difficulty presets, and what we remember between visits.

import type { Round } from './session'

export type Preset = 'chill' | 'level' | 'pain'
export type Variant = 'rush' | 'blitz' | 'survival' | 'zen' | 'review'

export type PracticeSettings = {
  topics: string[] // empty = all topics
  preset: Preset
  variant: Variant
}

export const PRESETS: { id: Preset; name: string; hint: string }[] = [
  { id: 'chill', name: 'chill', hint: 'below your level' },
  { id: 'level', name: 'my level', hint: 'best for improving' },
  { id: 'pain', name: 'pain', hint: 'above your level' },
]

export const MODES: { id: Variant; name: string; desc: string }[] = [
  { id: 'rush', name: 'rush', desc: '10 questions against the clock.' },
  { id: 'blitz', name: 'blitz', desc: '60 seconds. as many as you can.' },
  { id: 'survival', name: 'survival', desc: 'keep going until your first mistake.' },
  { id: 'zen', name: 'zen', desc: 'no timer. read, think, learn.' },
  { id: 'review', name: 'review', desc: 'the questions you got wrong, until they stick.' },
]

export const RUSH_LENGTH = 10
export const BLITZ_SECONDS = 60

const DEFAULTS: PracticeSettings = { topics: [], preset: 'level', variant: 'rush' }

export function loadSettings(): PracticeSettings {
  try {
    const saved = JSON.parse(localStorage.getItem('practice-settings') ?? 'null')
    if (saved && MODES.some((m) => m.id === saved.variant)) return { ...DEFAULTS, ...saved }
  } catch {
    // ignore unreadable settings
  }
  return DEFAULTS
}

export function saveSettings(settings: PracticeSettings): void {
  try {
    localStorage.setItem('practice-settings', JSON.stringify(settings))
  } catch {
    // storage blocked: settings just won't be remembered
  }
}

// Personal bests for blitz (most correct) and survival (longest run), kept in this browser.
function bestKey(settings: PracticeSettings): string {
  const topics = settings.topics.length ? [...settings.topics].sort().join('+') : 'all'
  return `best:${settings.variant}:${topics}:${settings.preset}`
}

export function loadBest(settings: PracticeSettings): number {
  try {
    return Number(localStorage.getItem(bestKey(settings)) ?? 0)
  } catch {
    return 0
  }
}

export function saveBest(settings: PracticeSettings, score: number): void {
  try {
    localStorage.setItem(bestKey(settings), String(score))
  } catch {
    // storage blocked
  }
}

// Progress survives a refresh or a dropped connection: the session picks up where
// it left off (with a fresh question; the one on screen is skipped, not counted).
// Blitz is the exception: its clock can't be paused, so a refresh ends it.
export const SESSION_KEY = 'practice-session'

export type SavedSession = { settings: PracticeSettings; rounds: Round[] }

export function savedSession(): SavedSession | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? 'null')
    return saved && Array.isArray(saved.rounds) && saved.settings ? saved : null
  } catch {
    return null
  }
}