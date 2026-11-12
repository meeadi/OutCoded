import { useState, type FormEvent } from 'react'
import { supabase } from '../lib/supabase'

type Mode = 'signin' | 'signup' | 'forgot'

type Message = { text: string; ok: boolean } // ok: good news (grey), not an error (red)

const TITLES: Record<Mode, string> = {
  signin: 'welcome back',
  signup: 'join the arena',
  forgot: 'reset your password',
}

export default function AuthForm({ notice = null }: { notice?: string | null }) {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<Message | null>(
    notice ? { text: notice, ok: false } : null,
  )
  const [busy, setBusy] = useState(false)

  function switchTo(next: Mode) {
    setMode(next)
    setMessage(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)

    if (mode === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) setMessage({ text: error.message, ok: false })
    } else if (mode === 'signup') {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: window.location.origin },
      })
      if (error) setMessage({ text: error.message, ok: false })
      else if (!data.session)
        setMessage({ text: 'check your inbox to confirm your email.', ok: true })
    } else {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.origin,
      })
      // Same answer whether or not the account exists, so nobody can fish for emails.
      if (error) setMessage({ text: error.message, ok: false })
      else
        setMessage({
          text: "if there's an account for that email, a reset link is on its way. check spam too.",
          ok: true,
        })
    }

    setBusy(false)
  }

  const submitLabel =
    mode === 'signin' ? 'sign in' : mode === 'signup' ? 'sign up' : 'send reset link'

  return (
    <form className="auth" onSubmit={handleSubmit}>
      <h2 className="auth-title">{TITLES[mode]}</h2>

      <input
        type="email"
        placeholder="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
        required
      />
      {mode !== 'forgot' && (
        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
          minLength={6}
          required
        />
      )}
      {mode === 'signin' && (
        <button
          type="button"
          className="auth-switch auth-forgot"
          onClick={() => switchTo('forgot')}
        >
          forgot password?
        </button>
      )}

      <button className="btn-primary" type="submit" disabled={busy}>
        {busy ? '...' : submitLabel}
      </button>

      {message && <p className={message.ok ? 'auth-note' : 'auth-message'}>{message.text}</p>}

      <button
        type="button"
        className="auth-switch"
        onClick={() => switchTo(mode === 'signin' ? 'signup' : 'signin')}
      >
        {mode === 'signin' ? 'new here? create an account' : 'have an account? sign in'}
      </button>
    </form>
  )
}