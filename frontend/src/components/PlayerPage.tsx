import { useEffect, useState } from 'react'
import { api, type PlayerProfile } from '../lib/api'
import { formatRating } from '../lib/rating'
import RatingChart from './RatingChart'

type Props = {
  username: string
  onOpenPlayer: (username: string) => void
}

function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export default function PlayerPage({ username, onOpenPlayer }: Props) {
  const [player, setPlayer] = useState<PlayerProfile | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .player(username)
      .then((p) => !cancelled && setPlayer(p))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [username])

  if (error) return <p className="auth-message">{error}</p>
  if (!player) return <p className="tagline">loading...</p>

  const { record } = player
  const winRate = record.games ? Math.round((record.wins / record.games) * 100) : null

  return (
    <div className="player">
      <div className="player-head">
        <h2 className="player-name">{player.username}</h2>
        <p className="player-rating">{formatRating(player.rating, player.rating_deviation)}</p>
        <p className="picker-hint">
          {player.rank !== null
            ? `#${player.rank} on the leaderboard`
            : `unranked · ${record.games}/${player.placement_matches} placement matches`}
        </p>
      </div>

      <div className="results-stats">
        <div>
          <span className="stat-value">{record.games}</span>
          <span className="stat-label">ranked games</span>
        </div>
        <div>
          <span className="stat-value">
            {record.wins}-{record.losses}-{record.draws}
          </span>
          <span className="stat-label">w-l-d</span>
        </div>
        <div>
          <span className="stat-value">{winRate === null ? '—' : `${winRate}%`}</span>
          <span className="stat-label">win rate</span>
        </div>
      </div>

      {player.history.length >= 2 ? (
        <section className="player-section">
          <h3 className="section-title">rating over time</h3>
          <RatingChart points={player.history} />
        </section>
      ) : (
        <p className="tagline">no ranked matches yet.</p>
      )}

      {player.recent.length > 0 && (
        <section className="player-section">
          <h3 className="section-title">recent ranked matches</h3>
          <div className="recent-list">
            {player.recent.map((m, i) => (
              <div className="recent-row" key={i}>
                <span className={`result-badge ${m.result}`}>{m.result[0].toUpperCase()}</span>
                <span className="recent-vs">
                  vs{' '}
                  {m.opponent ? (
                    <button className="link" onClick={() => onOpenPlayer(m.opponent!)}>
                      {m.opponent}
                    </button>
                  ) : (
                    'deleted player'
                  )}
                  {m.forfeit && <span className="forfeit-tag">forfeit</span>}
                </span>
                <span className="recent-score">
                  {m.score_you}–{m.score_opponent}
                </span>
                <span className={m.change >= 0 ? 'rating-delta up' : 'rating-delta down'}>
                  {m.change >= 0 ? '+' : ''}
                  {m.change}
                </span>
                <span className="recent-when">{timeAgo(m.at)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}