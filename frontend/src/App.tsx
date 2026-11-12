import { useCallback, useEffect, useRef, useState } from 'react'
import AuthForm from './components/AuthForm'
import Home from './components/Home'
import Landing from './components/Landing'
import NewPasswordForm from './components/NewPasswordForm'
import SideMenu, { type NavState, type NavTarget } from './components/SideMenu'
import ThemePicker from './components/ThemePicker'
import { canHover, useHoverOpen } from './hooks/useHoverOpen'
import { useSession } from './hooks/useSession'
import { wakeServer } from './lib/api'
import { prefersReducedMotion } from './lib/effects'
import { authLinkFailed } from './lib/supabase'
import { isThemeId, paintTheme, type ThemeId } from './lib/themes'

function loadTheme(): ThemeId {
  const saved = localStorage.getItem('theme')
  return isThemeId(saved) ? saved : 'midnight'
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
  const { session, loading, recovering, finishRecovery } = useSession()
  const sideMenu = useHoverOpen()
  // Home does the navigating (it owns the screens); the menu up here just asks.
  const navigateRef = useRef<((target: NavTarget) => void) | null>(null)
  const [navState, setNavState] = useState<NavState | null>(null)
  const closeSideMenu = useCallback(() => sideMenu.setOpen(false), [sideMenu])

  const enter = useCallback(() => {
    sessionStorage.setItem('entered', 'yes')
    setEntered(true)
  }, [])

  // Start waking the backend while people watch the intro or type their password.
  useEffect(() => wakeServer(), [])

  const page = loading
    ? 'loading'
    : session
      ? recovering
        ? 'reset' // opened a password reset link: choose a new password first
        : 'home'
      : entered || authLinkFailed
        ? 'auth'
        : 'landing'

  // Apply the theme to <html> and remember it for next time.
  useEffect(() => {
    paintTheme(theme)
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
      {/* Theme scenery: behind the page (neon's grid, sunset's glow) and in front of it (terminal's scanlines). */}
      <div className="backdrop" aria-hidden="true" />
      <div className="overlay" aria-hidden="true" />
      <div className="app">
        <header className="header">
          <div className="logo-wrap" {...(navState ? sideMenu.hover : {})}>
            {/* Hidden on the landing page, where the big typed logo takes over. */}
            <h1 className={`logo ${page === 'landing' ? 'logo-hidden' : ''}`}>
              {navState ? (
                // Signed in: the logo opens the side menu.
                <button
                  className="logo-button"
                  aria-expanded={sideMenu.open}
                  aria-label="outcoded: open menu"
                  onClick={() => sideMenu.setOpen(canHover() ? true : !sideMenu.open)}
                >
                  out<span>coded</span>
                </button>
              ) : (
                <>
                  out<span>coded</span>
                </>
              )}
            </h1>
            {navState && (
              <SideMenu
                open={sideMenu.open}
                onClose={closeSideMenu}
                hover={sideMenu.hover}
                state={navState}
                onNavigate={(target) => navigateRef.current?.(target)}
              />
            )}
          </div>
          <div className="header-right">
            <button
              className="fx-toggle"
              onClick={() => setEffects(!effects)}
              title="screen shake, flashes and confetti"
            >
              fx {effects ? 'on' : 'off'}
            </button>
            <ThemePicker theme={theme} onChange={setTheme} />
          </div>
        </header>

        <main className="main">
          {/* A new key per page replays the fade-in: that's the page transition. */}
          <div className="page" key={page}>
            {page === 'home' && session && (
              // The key makes Home start fresh if a different account signs in.
              <Home
                key={session.user.id}
                effects={effects}
                navigateRef={navigateRef}
                onNavState={setNavState}
              />
            )}
            {page === 'auth' && (
              <AuthForm
                notice={
                  authLinkFailed
                    ? 'that email link has expired or was already used. sign in, or ask for a new one.'
                    : null
                }
              />
            )}
            {page === 'reset' && <NewPasswordForm onDone={finishRecovery} />}
            {page === 'landing' && <Landing animate={effects} onEnter={enter} />}
          </div>
        </main>
      </div>
    </>
  )
}