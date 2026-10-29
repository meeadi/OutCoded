import { useEffect } from 'react'
import { bestStreak, rankFor, type Round } from '../lib/session'

type Props = {
  rounds: Round[]
  onRestart: () => void
}

export default function Results({ rounds, onRestart }: Props) {
  const correct = rounds.filter((r) => r.correct).length
  const accuracy = Math.round((correct / rounds.length) * 100)
  const averageSeconds = rounds.reduce((sum, r) => sum + r.ms, 0) / rounds.length / 1000
  const slowest = Math.max(...rounds.map((r) => r.ms))
  const rank = rankFor(correct, rounds.length)

  // Enter or Space starts a new session.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onRestart()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onRestart])

  return (
    <div className="results">
      <div className="results-head">
        <span className={`rank rank-${rank.letter}`}>{rank.letter}</span>
        <p className="rank-line">{rank.line}</p>
      </div>

      <div className="results-stats">
        <div>
          <span className="stat-value">{accuracy}%</span>
          <span className="stat-label">accuracy</span>
        </div>
        <div>
          <span className="stat-value">{averageSeconds.toFixed(1)}s</span>
          <span className="stat-label">avg time</span>
        </div>
        <div>
          <span className="stat-value">{bestStreak(rounds)}</span>
          <span className="stat-label">best streak</span>
        </div>
      </div>

      {/* One bar per question: taller = slower. Bars grow in one after another. */}
      <div className="chart" aria-label="time per question">
        {rounds.map((round, i) => (
          <div
            key={i}
            className={`bar ${round.correct ? 'bar-good' : 'bar-bad'}`}
            style={{
              height: `${Math.max(6, (round.ms / slowest) * 100)}%`,
              animationDelay: `${i * 60}ms`,
            }}
          >
            <span className="bar-tip">
              Q{i + 1} · {(round.ms / 1000).toFixed(1)}s{round.timedOut && ' ⏰'}
            </span>
          </div>
        ))}
      </div>
      <p className="chart-caption">time per question · green = right, red = wrong</p>

      <button className="btn-primary" onClick={onRestart}>
        play again
      </button>
      <p className="hint">or press enter</p>
    </div>
  )
}