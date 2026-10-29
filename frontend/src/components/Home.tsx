import { useEffect, useState } from 'react'
import { api, type Profile } from '../lib/api'
import { supabase } from '../lib/supabase'
import CodeOff from './CodeOff'
import Menu from './Menu'
import PuzzleRush from './PuzzleRush'
import UsernamePicker from './UsernamePicker'

type Props = {
  effects: boolean
}

type Mode = { kind: 'menu' } | { kind: 'solo' } | { kind: 'codeoff'; code: string }

// An invite link looks like ...?match=abc123
function initialMode(): Mode {
  const code = new URLSearchParams(window.location.search).get('match')
  return code ? { kind: 'codeoff', code } : { kind: 'menu' }
}

function setMatchInUrl(code: string | null) {
  const url = new URL(window.location.href)
  if (code) url.searchParams.set('match', code)
  else url.searchParams.delete('match')
  window.history.replaceState(null, '', url)
}

// Loads the player's profile. New players pick a name first, then they can play.
export default function Home({ effects }: Props) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>(initialMode)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((p) => !cancelled && setProfile(p))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [])

  function goToMenu() {
    setMatchInUrl(null)
    setMode({ kind: 'menu' })
  }

  async function startCodeOff() {
    setCreating(true)
    setError(null)
    try {
      const { code } = await api.createMatch()
      setMatchInUrl(code)
      setMode({ kind: 'codeoff', code })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  if (!profile) {
    return error ? <p className="auth-message">{error}</p> : <p className="tagline">loading...</p>
  }
  if (!profile.username) return <UsernamePicker onDone={setProfile} />

  return (
    <div className="home">
      {mode.kind === 'menu' && (
        <>
          <Menu onSolo={() => setMode({ kind: 'solo' })} onCodeOff={startCodeOff} busy={creating} />
          {error && <p className="auth-message">{error}</p>}
        </>
      )}
      {mode.kind === 'solo' && <PuzzleRush effects={effects} />}
      {mode.kind === 'codeoff' && (
        <CodeOff
          // A new key for every match means a fresh connection and fresh state.
          key={mode.code}
          code={mode.code}
          effects={effects}
          onExit={goToMenu}
          onNewMatch={startCodeOff}
        />
      )}

      <p className="signed-in">
        {mode.kind !== 'menu' && (
          <>
            <button className="link" onClick={goToMenu}>
              menu
            </button>{' '}
            ·{' '}
          </>
        )}
        playing as <span className="you">{profile.username}</span> ·{' '}
        <button className="link" onClick={() => supabase.auth.signOut()}>
          sign out
        </button>
      </p>
    </div>
  )
}