import { useCallback, useEffect, useState } from 'react'
import AuthForm from './components/AuthForm'
import Home from './components/Home'
import Landing from './components/Landing'
import { useSession } from './hooks/useSession'
import { wakeServer } from './lib/api'
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

// Seen the landing page already in this tab? Then a refresh skips it.
function loadEntered(): boolean {
  return sessionStorage.getItem('entered') === 'yes'
}

export default function App() {
  const [theme, setTheme] = useState<ThemeId>(loadTheme)
  const [effects, setEffects] = useState(loadEffects)
  const [entered, setEntered] = useState(loadEntered)
  const { session, loading } = useSession()

  const enter = useCallback(() => {
    sessionStorage.setItem('entered', 'yes')
    setEntered(true)
  }, [])

  // Start waking the backend while people watch the intro or type their password.
  useEffect(() => wakeServer(), [])

  const page = loading ? 'loading' : session ? 'home' : entered ? 'auth' : 'landing'

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
          {/* Hidden on the landing page, where the big typed logo takes over. */}
          <h1 className={`logo ${page === 'landing' ? 'logo-hidden' : ''}`}>
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
          {/* A new key per page replays the fade-in: that's the page transition. */}
          <div className="page" key={page}>
            {page === 'home' && session && (
              // The key makes Home start fresh if a different account signs in.
              <Home key={session.user.id} effects={effects} />
            )}
            {page === 'auth' && <AuthForm />}
            {page === 'landing' && <Landing animate={effects} onEnter={enter} />}
          </div>
        </main>
      </div>
    </>
  )
}