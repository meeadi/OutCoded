import { useEffect } from 'react'
import type { Variant } from '../lib/practice'
import { bestStreak, rankFor, type Round } from '../lib/session'

type Props = {
  rounds: Round[]
  variant: Variant
  note: string | null // why the session ended ("time's up.")
  best: number | null // previous personal best (blitz, survival), if not beaten
  newBest: boolean
  onRestart: () => void
  onChangeSettings: () => void
}

// The end of a practice session. Rush gets a rank letter; blitz and survival a
// score against your personal best; zen and review a simple tally.
export default function Results({
  rounds,
  variant,
  note,
  best,
  newBest,
  onRestart,
  onChangeSettings,
}: Props) {
  const correct = rounds.filter((r) => r.correct).length
  const total = rounds.length

  // Enter or Space plays again; Esc goes back to the practice settings.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onRestart()
      } else if (event.key === 'Escape') onChangeSettings()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onRestart, onChangeSettings])

  const buttons = (
    <>
      <button className="btn-primary" onClick={onRestart}>
        play again
      </button>
      <p className="hint">
        or press enter ·{' '}
        <button className="link" onClick={onChangeSettings}>
          change topics or mode (esc)
        </button>
      </p>
    </>
  )

  if (total === 0) {
    return (
      <div className="results">
        <p className="rank-line">{note ?? 'nothing answered this time.'}</p>
        {buttons}
      </div>
    )
  }

  const accuracy = Math.round((correct / total) * 100)
  const averageSeconds = rounds.reduce((sum, r) => sum + r.ms, 0) / total / 1000
  const slowest = Math.max(...rounds.map((r) => r.ms))
  const rank = rankFor(correct, total)
  const headline =
    variant === 'blitz'
      ? { value: correct, label: 'correct in 60 seconds' }
      : variant === 'survival'
        ? { value: bestStreak(rounds), label: 'in a row' }
        : variant === 'review'
          ? { value: `${correct}/${total}`, label: 'mistakes fixed' }
          : { value: `${correct}/${total}`, label: 'right' }

  return (
    <div className="results">
      {variant === 'rush' ? (
        <div className="results-head">
          <span className={`rank rank-${rank.letter}`}>{rank.letter}</span>
          <p className="rank-line">{rank.line}</p>
        </div>
      ) : (
        <div className="results-head">
          <span className="score-big">{headline.value}</span>
          <p className="rank-line">
            {headline.label}
            {note && ` · ${note}`}
          </p>
          {newBest && <p className="new-best">new personal best!</p>}
          {best !== null && best > 0 && <p className="practice-note">your best: {best}</p>}
        </div>
      )}

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

      {buttons}
    </div>
  )
}