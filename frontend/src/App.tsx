import { useEffect, useState } from 'react'
import AuthForm from './components/AuthForm'
import PuzzleRush from './components/PuzzleRush'
import { useSession } from './hooks/useSession'
import { prefersReducedMotion } from './lib/effects'
import { supabase } from './lib/supabase'

const THEMES = [
  { id: 'midnight', swatch: '#7c5cff' },
  { id: 'paper', swatch: '#d9480f' },
  { id: 'matcha', swatch: '#a3c76d' },
] as const

type ThemeId = (typeof THEMES)[number]['id']

function loadTheme(): ThemeId {
  const saved = localStorage.getItem('theme')
  return THEMES.some((t) => t.id === saved) ? (saved as ThemeId) : 'midnight'
}

function loadEffects(): boolean {
  const saved = localStorage.getItem('effects')
  return saved === null ? !prefersReducedMotion() : saved === 'on'
}

export default function App() {
  const [theme, setTheme] = useState<ThemeId>(loadTheme)
  const [effects, setEffects] = useState(loadEffects)
  const { session, loading } = useSession()

  // Apply the theme to <html> and remember it for next time.
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.dataset.fx = effects ? 'on' : 'off'
    localStorage.setItem('effects', effects ? 'on' : 'off')
  }, [effects])

  return (
    <>
      {/* Outside .app on purpose: .app shakes, and a shaking parent would trap the flash. */}
      <div className="flash" aria-hidden="true" />
      <div className="app">
        <header className="header">
          <h1 className="logo">
            out<span>coded</span>
          </h1>
          <div className="themes">
            <button
              className="fx-toggle"
              onClick={() => setEffects(!effects)}
              title="screen shake, flashes and confetti"
            >
              fx {effects ? 'on' : 'off'}
            </button>
            {THEMES.map((t) => (
              <button
                key={t.id}
                className={`theme-dot ${t.id === theme ? 'active' : ''}`}
                style={{ background: t.swatch }}
                onClick={() => setTheme(t.id)}
                aria-label={`${t.id} theme`}
                title={t.id}
              />
            ))}
          </div>
        </header>

        <main className="main">
          {loading ? null : session ? (
            <div className="home">
              <PuzzleRush effects={effects} />
              <p className="signed-in">
                signed in as {session.user.email} ·{' '}
                <button className="link" onClick={() => supabase.auth.signOut()}>
                  sign out
                </button>
              </p>
            </div>
          ) : (
            <AuthForm />
          )}
        </main>
      </div>
    </>
  )
}