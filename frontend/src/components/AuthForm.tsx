import { useState, type FormEvent } from 'react'
import { supabase } from '../lib/supabase'

type Mode = 'signin' | 'signup'

export default function AuthForm() {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)

    if (mode === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) setMessage(error.message)
    } else {
      const { data, error } = await supabase.auth.signUp({ email, password })
      if (error) setMessage(error.message)
      else if (!data.session) setMessage('Check your inbox to confirm your email.')
    }

    setBusy(false)
  }

  return (
    <form className="auth" onSubmit={handleSubmit}>
      <h2 className="auth-title">{mode === 'signin' ? 'welcome back' : 'join the arena'}</h2>

      <input
        type="email"
        placeholder="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
        required
      />
      <input
        type="password"
        placeholder="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
        minLength={6}
        required
      />

      <button className="btn-primary" type="submit" disabled={busy}>
        {busy ? '...' : mode === 'signin' ? 'sign in' : 'sign up'}
      </button>

      {message && <p className="auth-message">{message}</p>}

      <button
        type="button"
        className="auth-switch"
        onClick={() => {
          setMode(mode === 'signin' ? 'signup' : 'signin')
          setMessage(null)
        }}
      >
        {mode === 'signin' ? 'new here? create an account' : 'have an account? sign in'}
      </button>
    </form>
  )
}