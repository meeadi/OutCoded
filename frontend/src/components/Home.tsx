import { useEffect, useState } from 'react'
import { api, type Profile } from '../lib/api'
import { supabase } from '../lib/supabase'
import PuzzleRush from './PuzzleRush'
import UsernamePicker from './UsernamePicker'

type Props = {
  effects: boolean
}

// Loads the player's profile. New players pick a name first, then they can play.
export default function Home({ effects }: Props) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)

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

  if (error) return <p className="auth-message">{error}</p>
  if (!profile) return <p className="tagline">loading...</p>
  if (!profile.username) return <UsernamePicker onDone={setProfile} />

  return (
    <div className="home">
      <PuzzleRush effects={effects} />
      <p className="signed-in">
        playing as <span className="you">{profile.username}</span> ·{' '}
        <button className="link" onClick={() => supabase.auth.signOut()}>
          sign out
        </button>
      </p>
    </div>
  )
}