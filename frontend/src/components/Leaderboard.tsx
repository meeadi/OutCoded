import { useEffect, useState } from 'react'
import { api, type Leaderboard as Board, type LeaderboardRow } from '../lib/api'
import { formatRating } from '../lib/rating'

type Props = {
  me: string
  onOpenPlayer: (username: string) => void
}

const MEDALS = ['🥇', '🥈', '🥉']

export default function Leaderboard({ me, onOpenPlayer }: Props) {
  const [board, setBoard] = useState<Board | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .leaderboard()
      .then((b) => !cancelled && setBoard(b))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <p className="auth-message">{error}</p>
  if (!board) return <p className="tagline">loading...</p>

  const youInList = board.players.some((p) => p.username === me)
  const toGo = board.placement_matches - board.your_games

  const row = (p: LeaderboardRow) => (
    <button
      key={p.username}
      className={p.username === me ? 'lb-row me' : 'lb-row'}
      onClick={() => onOpenPlayer(p.username)}
    >
      <span className="lb-rank">{MEDALS[p.rank - 1] ?? `#${p.rank}`}</span>
      <span className="lb-name">{p.username}</span>
      <span className="lb-record">
        {p.record.wins}w {p.record.losses}l {p.record.draws}d
      </span>
      <span className="lb-rating">{formatRating(p.rating, p.rating_deviation)}</span>
    </button>
  )

  return (
    <div className="board">
      <h2 className="auth-title">leaderboard</h2>

      {board.you === null && (
        <p className="placement-note">
          {toGo === board.placement_matches
            ? `play ${toGo} ranked matches to get on the board`
            : `${toGo} more ranked ${toGo === 1 ? 'match' : 'matches'} to get placed`}
        </p>
      )}

      {board.players.length === 0 ? (
        <p className="tagline">nobody's placed yet. be the first.</p>
      ) : (
        <div className="lb-list">
          {board.players.map(row)}
          {board.you && !youInList && (
            <>
              <div className="lb-gap">···</div>
              {row(board.you)}
            </>
          )}
        </div>
      )}
    </div>
  )
}