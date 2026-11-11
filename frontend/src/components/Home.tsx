import { useCallback, useEffect, useState, type RefObject } from 'react'
import { api, type Profile } from '../lib/api'
import { supabase } from '../lib/supabase'
import CodeOff from './CodeOff'
import Leaderboard from './Leaderboard'
import LoadingScreen from './LoadingScreen'
import Menu from './Menu'
import PlayerPage from './PlayerPage'
import PuzzleRush from './PuzzleRush'
import Queue from './Queue'
import type { NavState, NavTarget } from './SideMenu'
import UsernamePicker from './UsernamePicker'

type Props = {
  effects: boolean
  navigateRef: RefObject<((target: NavTarget) => void) | null> // filled in here, used by the side menu
  onNavState: (state: NavState | null) => void
}

type Mode =
  | { kind: 'menu' }
  | { kind: 'solo' }
  | { kind: 'queue' }
  | { kind: 'codeoff'; code: string }
  | { kind: 'leaderboard' }
  | { kind: 'player'; username: string }

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
export default function Home({ effects, navigateRef, onNavState }: Props) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>(initialMode)
  const [creating, setCreating] = useState(false)
  const [attempt, setAttempt] = useState(0) // bump to retry loading the profile
  const [matchLive, setMatchLive] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((p) => !cancelled && setProfile(p))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [attempt])

  const goToMenu = useCallback(() => {
    setMatchInUrl(null)
    setMode({ kind: 'menu' })
    api
      .me()
      .then(setProfile)
      .catch(() => {}) // pick up a new rating after a ranked match
  }, [])

  // Stable on purpose: the queue reconnects if this function changes.
  const joinMatch = useCallback((code: string) => {
    setMatchInUrl(code)
    setMode({ kind: 'codeoff', code })
  }, [])

  const findRanked = useCallback(() => {
    setMatchInUrl(null)
    setMode({ kind: 'queue' })
  }, [])

  const openPlayer = useCallback((username: string) => {
    setMatchInUrl(null)
    setMode({ kind: 'player', username })
  }, [])

  async function startFriendMatch() {
    setCreating(true)
    setError(null)
    try {
      const { code } = await api.createMatch()
      joinMatch(code)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  // Let the side menu drive the screens.
  useEffect(() => {
    navigateRef.current = (target: NavTarget) => {
      if (target === 'menu') goToMenu()
      else if (target === 'solo') {
        setMatchInUrl(null)
        setMode({ kind: 'solo' })
      } else if (target === 'ranked') findRanked()
      else if (target === 'friend') startFriendMatch()
      else if (target === 'leaderboard') {
        setMatchInUrl(null)
        setMode({ kind: 'leaderboard' })
      } else if (profile?.username) openPlayer(profile.username)
    }
  })

  // Tell the side menu where we are (or that there's no menu yet: no username).
  const current: NavTarget | null =
    mode.kind === 'queue'
      ? 'ranked'
      : mode.kind === 'player'
        ? mode.username === profile?.username
          ? 'profile'
          : null
        : mode.kind === 'codeoff'
          ? null
          : mode.kind
  const ready = Boolean(profile?.username)
  useEffect(() => {
    onNavState(ready ? { current, inMatch: matchLive } : null)
  }, [ready, current, matchLive, onNavState])
  useEffect(() => () => onNavState(null), [onNavState])

  if (!profile && error) {
    return (
      <div className="load-failed">
        <p className="auth-message">couldn't reach the server: {error}</p>
        <button
          className="btn-primary"
          onClick={() => {
            setError(null)
            setAttempt((a) => a + 1)
          }}
        >
          try again
        </button>
      </div>
    )
  }
  if (!profile) return <LoadingScreen animate={effects} />
  if (!profile.username) return <UsernamePicker onDone={setProfile} />

  return (
    <div className="home">
      {/* Keyed by screen, so switching screens replays the fade-in. */}
      <div className="page" key={mode.kind}>
        {mode.kind === 'menu' && (
          <>
            <Menu
              rating={profile.rating}
              rd={profile.rating_deviation}
              onSolo={() => setMode({ kind: 'solo' })}
              onRanked={findRanked}
              onFriend={startFriendMatch}
              onLeaderboard={() => setMode({ kind: 'leaderboard' })}
              busy={creating}
            />
            {error && <p className="auth-message">{error}</p>}
          </>
        )}
        {mode.kind === 'solo' && <PuzzleRush effects={effects} />}
        {mode.kind === 'queue' && <Queue onMatched={joinMatch} onCancel={goToMenu} />}
        {mode.kind === 'leaderboard' && (
          <Leaderboard me={profile.username} onOpenPlayer={openPlayer} />
        )}
        {mode.kind === 'player' && (
          // The key reloads the page when you jump from one player to another.
          <PlayerPage key={mode.username} username={mode.username} onOpenPlayer={openPlayer} />
        )}
        {mode.kind === 'codeoff' && (
          <CodeOff
            // A new key for every match means a fresh connection and fresh state.
            key={mode.code}
            code={mode.code}
            effects={effects}
            onExit={goToMenu}
            onNewMatch={(rated) => (rated ? findRanked() : startFriendMatch())}
            onLiveChange={setMatchLive}
          />
        )}
      </div>

      <p className="signed-in">
        {mode.kind !== 'menu' && !matchLive && (
          <>
            <button className="link" onClick={goToMenu}>
              menu
            </button>{' '}
            ·{' '}
          </>
        )}
        playing as{' '}
        <button className="link you" onClick={() => openPlayer(profile.username!)}>
          {profile.username}
        </button>{' '}
        ·{' '}
        <button className="link" onClick={() => supabase.auth.signOut()}>
          sign out
        </button>
      </p>
    </div>
  )
}