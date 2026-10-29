import { useEffect, useState } from 'react'
import AuthForm from './components/AuthForm'
import Home from './components/Home'
import { useSession } from './hooks/useSession'
import { prefersReducedMotion } from './lib/effects'

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
            // The key makes Home start fresh if a different account signs in.
            <Home key={session.user.id} effects={effects} />
          ) : (
            <AuthForm />
          )}
        </main>
      </div>
    </>
  )
}