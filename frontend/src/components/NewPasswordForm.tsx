import { useState, type FormEvent } from 'react'
import { supabase } from '../lib/supabase'

// Shown after opening a password reset link: the email proved who you are,
// so you're signed in. Pick a new password before carrying on.
export default function NewPasswordForm({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (password !== again) {
      setMessage("those passwords don't match.")
      return
    }
    setBusy(true)
    setMessage(null)
    const { error } = await supabase.auth.updateUser({ password })
    setBusy(false)
    if (error) setMessage(error.message)
    else setSaved(true)
  }

  if (saved) {
    return (
      <div className="auth">
        <h2 className="auth-title">password updated</h2>
        <p className="auth-note">you're signed in. try not to forget this one ;)</p>
        <button className="btn-primary" onClick={onDone} autoFocus>
          continue
        </button>
      </div>
    )
  }

  return (
    <form className="auth" onSubmit={handleSubmit}>
      <h2 className="auth-title">choose a new password</h2>
      <input
        type="password"
        placeholder="new password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="new-password"
        minLength={6}
        required
        autoFocus
      />
      <input
        type="password"
        placeholder="new password, again"
        value={again}
        onChange={(e) => setAgain(e.target.value)}
        autoComplete="new-password"
        minLength={6}
        required
      />
      <button className="btn-primary" type="submit" disabled={busy}>
        {busy ? '...' : 'save password'}
      </button>
      {message && <p className="auth-message">{message}</p>}
    </form>
  )
}