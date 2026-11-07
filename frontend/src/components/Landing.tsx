import { useCallback, useEffect, useState } from 'react'
import TypedLogo from './TypedLogo'

type Props = {
  animate: boolean
  onEnter: () => void
}

// First thing a signed-out visitor sees: the logo types itself out, then "dive in".
export default function Landing({ animate, onEnter }: Props) {
  const [ready, setReady] = useState(!animate)
  const showButton = useCallback(() => setReady(true), [])
  // Invite links get their own line: someone's waiting for you.
  const [invited] = useState(() => new URLSearchParams(window.location.search).has('match'))

  useEffect(() => {
    if (!ready) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Enter') onEnter()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [ready, onEnter])

  return (
    <section className={`landing ${ready ? 'ready' : ''}`}>
      <h2 className="landing-logo">
        <TypedLogo animate={animate} onDone={showButton} />
      </h2>
      <p className="landing-tagline">
        {invited
          ? "you've been challenged to a code-off."
          : 'predict the output. outcode your friends.'}
      </p>
      <button
        className="btn-primary dive-in"
        onClick={onEnter}
        disabled={!ready}
        tabIndex={ready ? 0 : -1}
      >
        dive in
      </button>
      <p className="landing-hint">
        press <kbd>enter</kbd>
      </p>
    </section>
  )
}