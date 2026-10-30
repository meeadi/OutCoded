// Head-to-head breakdown of a finished Code-Off: stats plus a round-by-round chart.

export type SideResult = {
  correct: boolean
  timed_out: boolean
  response_ms: number
  points: number
} | null

export type RoundSummary = {
  round: number
  you: SideResult
  opponent: SideResult
}

type Stats = { correct: number; average: number | null; fastest: number | null }

function statsFor(results: SideResult[]): Stats {
  const answered = results.filter((r) => r && !r.timed_out).map((r) => r!.response_ms)
  const correctTimes = results.filter((r) => r?.correct).map((r) => r!.response_ms)
  return {
    correct: correctTimes.length,
    average: answered.length ? answered.reduce((a, b) => a + b, 0) / answered.length : null,
    fastest: correctTimes.length ? Math.min(...correctTimes) : null,
  }
}

const seconds = (ms: number | null) => (ms === null ? '—' : `${(ms / 1000).toFixed(1)}s`)

// Compare times as they're shown (tenths of a second), so a visible tie counts as a tie.
const tenths = (ms: number | null) => (ms === null ? null : Math.round(ms / 100))

// Which side "wins" a stat row, so it can be highlighted. Lower is better for times.
function better(a: number | null, b: number | null, lowerWins: boolean): 'you' | 'them' | null {
  if (a === null && b === null) return null
  if (a === null) return 'them'
  if (b === null) return 'you'
  if (a === b) return null
  return (a < b) === lowerWins ? 'you' : 'them'
}

type Props = {
  rounds: RoundSummary[]
  opponent: string
}

export default function MatchSummary({ rounds, opponent }: Props) {
  if (rounds.length === 0) return null

  const you = statsFor(rounds.map((r) => r.you))
  const them = statsFor(rounds.map((r) => r.opponent))
  const rows: { label: string; you: string; them: string; winner: 'you' | 'them' | null }[] = [
    {
      label: 'correct',
      you: `${you.correct}/${rounds.length}`,
      them: `${them.correct}/${rounds.length}`,
      winner: better(you.correct, them.correct, false),
    },
    {
      label: 'avg time',
      you: seconds(you.average),
      them: seconds(them.average),
      winner: better(tenths(you.average), tenths(them.average), true),
    },
    {
      label: 'fastest right',
      you: seconds(you.fastest),
      them: seconds(them.fastest),
      winner: better(tenths(you.fastest), tenths(them.fastest), true),
    },
  ]

  return (
    <div className="summary">
      <div className="h2h">
        <span className="h2h-head">you</span>
        <span />
        <span className="h2h-head">{opponent}</span>
        {rows.map((row) => (
          <div className="h2h-row" key={row.label}>
            <span className={row.winner === 'you' ? 'h2h-value best' : 'h2h-value'}>{row.you}</span>
            <span className="h2h-label">{row.label}</span>
            <span className={row.winner === 'them' ? 'h2h-value best' : 'h2h-value'}>
              {row.them}
            </span>
          </div>
        ))}
      </div>

      {/* Points per round: your bar on the left, theirs on the right. Max is 200. */}
      <div className="duel-chart" aria-label="points per round">
        {rounds.map((r, i) => (
          <div className="duel-round" key={r.round}>
            <div className="duel-bars">
              <Bar side={r.you} who="you" round={r.round} delay={i * 120} />
              <Bar side={r.opponent} who={opponent} round={r.round} delay={i * 120 + 60} faded />
            </div>
            <span className="duel-label">R{r.round}</span>
          </div>
        ))}
      </div>
      <p className="chart-caption">
        points per round · solid = you, faded = {opponent} · red = missed
      </p>
    </div>
  )
}

function Bar({
  side,
  who,
  round,
  delay,
  faded = false,
}: {
  side: SideResult
  who: string
  round: number
  delay: number
  faded?: boolean
}) {
  const points = side?.points ?? 0
  const label = !side
    ? 'no answer'
    : side.correct
      ? `+${points} in ${seconds(side.response_ms)}`
      : side.timed_out
        ? 'ran out of time'
        : 'missed'

  return (
    <div
      className={`bar ${side?.correct ? 'bar-good' : 'bar-bad'}${faded ? ' faded' : ''}`}
      style={{ height: `${Math.max(6, (points / 200) * 100)}%`, animationDelay: `${delay}ms` }}
    >
      <span className="bar-tip">
        R{round} · {who}: {label}
      </span>
    </div>
  )
}