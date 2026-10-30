import { useEffect } from 'react'
import { formatRating } from '../lib/rating'

type Props = {
  rating: number
  rd: number
  onSolo: () => void
  onRanked: () => void
  onFriend: () => void
  busy: boolean
}

export default function Menu({ rating, rd, onSolo, onRanked, onFriend, busy }: Props) {
  // Keyboard: 1 solo, 2 ranked, 3 friend.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (busy) return
      if (event.key === '1') onSolo()
      if (event.key === '2') onRanked()
      if (event.key === '3') onFriend()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onSolo, onRanked, onFriend, busy])

  return (
    <div className="menu">
      <button className="mode" onClick={onSolo} disabled={busy}>
        <span className="option-key">1</span>
        <span className="mode-name">solo rush</span>
        <span className="mode-desc">10 questions. just you and the clock.</span>
      </button>
      <button className="mode" onClick={onRanked} disabled={busy}>
        <span className="option-key">2</span>
        <span className="mode-name">
          ranked code-off <span className="mode-rating">{formatRating(rating, rd)}</span>
        </span>
        <span className="mode-desc">get matched with someone your level. rating on the line.</span>
      </button>
      <button className="mode" onClick={onFriend} disabled={busy}>
        <span className="option-key">3</span>
        <span className="mode-name">code-off a friend</span>
        <span className="mode-desc">send a link. 5 rounds. no rating, just bragging rights.</span>
      </button>
    </div>
  )
}