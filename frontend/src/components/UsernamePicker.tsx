import { useState, type FormEvent } from 'react'
import { api, type Profile } from '../lib/api'

const VALID_NAME = /^[A-Za-z0-9_]{3,20}$/

const ADJECTIVES = ['sleepy', 'feral', 'based', 'cursed', 'turbo', 'sneaky', 'chaotic', 'spicy', 'lazy', 'atomic']
const NOUNS = ['bug', 'pointer', 'lambda', 'goblin', 'compiler', 'semicolon', 'null', 'regex', 'gremlin', 'byte']

function pick<T>(items: T[]): T {
  return items[Math.floor(Math.random() * items.length)]
}

// e.g. "feral_semicolon42". Always fits the 20-character limit.
function randomName(): string {
  return `${pick(ADJECTIVES)}_${pick(NOUNS)}${Math.floor(Math.random() * 90) + 10}`
}

type Props = {
  onDone: (profile: Profile) => void
}

export default function UsernamePicker({ onDone }: Props) {
  const [name, setName] = useState(randomName)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rolls, setRolls] = useState(0)
  const valid = VALID_NAME.test(name)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!valid) return
    setBusy(true)
    setError(null)
    try {
      onDone(await api.setUsername(name))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <form className="auth" onSubmit={handleSubmit}>
      <h2 className="auth-title">pick your name</h2>
      <p className="picker-hint">this is what people see when you outcode them</p>

      <div className="name-row">
        <input
          value={name}
          onChange={(e) => {
            setName(e.target.value.replace(/\s/g, '_'))
            setError(null)
          }}
          maxLength={20}
          spellCheck={false}
          autoComplete="off"
          autoFocus
          aria-label="username"
        />
        <button
          type="button"
          className="dice"
          // The key restarts the spin animation on every roll.
          key={rolls}
          onClick={() => {
            setName(randomName())
            setRolls(rolls + 1)
            setError(null)
          }}
          title="random name"
          aria-label="random name"
        >
          🎲
        </button>
      </div>
      <p className={valid || !name ? 'picker-rule' : 'picker-rule bad'}>
        3–20 letters, numbers or _
      </p>

      <button className="btn-primary" type="submit" disabled={!valid || busy}>
        {busy ? '...' : "that's me"}
      </button>

      {error && <p className="auth-message">{error}</p>}
    </form>
  )
}