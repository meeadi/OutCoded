import { useCallback, useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { arrivedFromRecoveryLink, supabase } from '../lib/supabase'

// Tracks who is signed in, and updates whenever they sign in or out.
// `recovering` is true after opening a password reset link: the player is
// signed in, but should choose a new password before anything else.
export function useSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [recovering, setRecovering] = useState(arrivedFromRecoveryLink)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    const { data } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession)
      if (event === 'PASSWORD_RECOVERY') setRecovering(true)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  const finishRecovery = useCallback(() => setRecovering(false), [])

  return { session, loading, recovering, finishRecovery }
}