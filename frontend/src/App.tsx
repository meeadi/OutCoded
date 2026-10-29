import { useEffect, useState } from 'react'
import AuthForm from './components/AuthForm'
import { useSession } from './hooks/useSession'
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

export default function App() {
  const [theme, setTheme] = useState<ThemeId>(loadTheme)
  const { session, loading } = useSession()

  // Apply the theme to <html> and remember it for next time.
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">
          out<span>coded</span>
        </h1>
        <div className="themes">
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
            <p className="tagline">// outthink. outplay. outcode.</p>
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
  )
}