import { useEffect, useRef, useState } from 'react'

export type NavTarget = 'menu' | 'solo' | 'ranked' | 'friend' | 'leaderboard' | 'profile'

export type NavState = {
  current: NavTarget | null // the screen you're on, highlighted in the menu
  inMatch: boolean // a code-off is live: leaving forfeits it
}

const ITEMS: { id: NavTarget; label: string; hint: string }[] = [
  { id: 'menu', label: 'menu', hint: 'back to the start' },
  { id: 'solo', label: 'solo rush', hint: 'you vs the clock' },
  { id: 'ranked', label: 'ranked code-off', hint: 'rating on the line' },
  { id: 'friend', label: 'code-off a friend', hint: 'send a link' },
  { id: 'leaderboard', label: 'leaderboard', hint: "who's cracked" },
  { id: 'profile', label: 'my profile', hint: 'your rating history' },
]

type Props = {
  open: boolean
  onClose: () => void
  hover: { onMouseEnter: () => void; onMouseLeave: () => void }
  state: NavState
  onNavigate: (target: NavTarget) => void
}

// The menu that slides out of the logo. On a computer it flies out beside the
// logo on hover; on a phone it's a drawer from the left edge.
export default function SideMenu({ open, onClose, hover, state, onNavigate }: Props) {
  const [pending, setPending] = useState<NavTarget | null>(null) // waiting for "leave the match?"
  const [wasOpen, setWasOpen] = useState(open)
  const panel = useRef<HTMLElement>(null)

  // Closing forgets any half-answered "leave the match?" question.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (!open) setPending(null)
  }

  useEffect(() => {
    if (!open) return
    const items = () => [...(panel.current?.querySelectorAll<HTMLButtonElement>('button') ?? [])]

    // Opened with a click or the keyboard (not just a hover): put focus inside.
    if (document.activeElement?.classList.contains('logo-button')) items()[0]?.focus()

    function onKey(event: KeyboardEvent) {
      if (event.key === 'Tab') return
      event.stopPropagation() // keep the game's shortcuts from firing behind the menu
      if (event.key === 'Escape') {
        onClose()
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        const list = items()
        const index = list.indexOf(document.activeElement as HTMLButtonElement)
        const step = event.key === 'ArrowDown' ? 1 : -1
        list[(index + step + list.length) % list.length]?.focus()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, onClose])

  function choose(target: NavTarget) {
    if (target === state.current) return onClose()
    if (state.inMatch && pending !== target) return setPending(target)
    onNavigate(target)
    onClose()
  }

  return (
    <>
      <div className={`side-scrim ${open ? 'open' : ''}`} onClick={onClose} aria-hidden="true" />
      <nav
        ref={panel}
        className={`side-menu ${open ? 'open' : ''}`}
        aria-label="main menu"
        aria-hidden={!open}
        {...hover}
      >
        {ITEMS.map((item) => (
          <button
            key={item.id}
            tabIndex={open ? 0 : -1}
            className={`side-item ${item.id === state.current ? 'current' : ''}`}
            aria-current={item.id === state.current ? 'page' : undefined}
            onClick={() => choose(item.id)}
          >
            <span className="side-label">{item.label}</span>
            <span className="side-hint">{item.hint}</span>
          </button>
        ))}

        {pending && (
          <div className="side-confirm" role="alert">
            <p>you're mid-match. leaving forfeits it, and a ranked forfeit counts as a loss.</p>
            <div className="side-confirm-actions">
              <button
                className="btn-primary"
                tabIndex={open ? 0 : -1}
                onClick={() => choose(pending)}
              >
                leave
              </button>
              <button className="link" tabIndex={open ? 0 : -1} onClick={() => setPending(null)}>
                stay
              </button>
            </div>
          </div>
        )}
      </nav>
    </>
  )
}