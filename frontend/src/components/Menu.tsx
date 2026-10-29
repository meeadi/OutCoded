import { useEffect } from 'react'

type Props = {
  onSolo: () => void
  onCodeOff: () => void
  busy: boolean
}

export default function Menu({ onSolo, onCodeOff, busy }: Props) {
  // Keyboard: 1 for solo, 2 for code-off.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (busy) return
      if (event.key === '1') onSolo()
      if (event.key === '2') onCodeOff()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onSolo, onCodeOff, busy])

  return (
    <div className="menu">
      <button className="mode" onClick={onSolo} disabled={busy}>
        <span className="option-key">1</span>
        <span className="mode-name">solo rush</span>
        <span className="mode-desc">10 questions. just you and the clock.</span>
      </button>
      <button className="mode" onClick={onCodeOff} disabled={busy}>
        <span className="option-key">2</span>
        <span className="mode-name">code-off</span>
        <span className="mode-desc">1v1 a friend. 5 rounds. loser gets outcoded.</span>
      </button>
    </div>
  )
}