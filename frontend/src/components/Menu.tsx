import { useEffect } from 'react'
import { formatRating } from '../lib/rating'

type Props = {
  rating: number
  rd: number
  onPractice: () => void
  onRanked: () => void
  onFriend: () => void
  onLeaderboard: () => void
  busy: boolean
}

export default function Menu({
  rating,
  rd,
  onPractice,
  onRanked,
  onFriend,
  onLeaderboard,
  busy,
}: Props) {
  // Keyboard: 1 practice, 2 ranked, 3 friend, 4 leaderboard.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (busy) return
      if (event.key === '1') onPractice()
      if (event.key === '2') onRanked()
      if (event.key === '3') onFriend()
      if (event.key === '4') onLeaderboard()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onPractice, onRanked, onFriend, onLeaderboard, busy])

  return (
    <div className="menu">
      <button className="mode" onClick={onPractice} disabled={busy}>
        <span className="option-key">1</span>
        <span className="mode-name">practice</span>
        <span className="mode-desc">pick topics and a mode. rush, blitz, survival, zen, review.</span>
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
      <button className="mode small" onClick={onLeaderboard} disabled={busy}>
        <span className="option-key">4</span>
        <span className="mode-name">leaderboard</span>
        <span className="mode-desc">who's actually cracked.</span>
      </button>
    </div>
  )
}