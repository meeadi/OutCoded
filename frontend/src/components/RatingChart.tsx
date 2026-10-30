type Point = { at: string; rating: number }

type Props = {
  points: Point[]
}

const HEIGHT = 160

// Rating over time. The line is SVG (stretched to fit the width); the dots are
// HTML on top, so they stay round and can carry hover labels.
export default function RatingChart({ points }: Props) {
  if (points.length < 2) return null

  const ratings = points.map((p) => p.rating)
  const pad = Math.max(20, (Math.max(...ratings) - Math.min(...ratings)) * 0.15)
  const low = Math.floor((Math.min(...ratings) - pad) / 10) * 10
  const high = Math.ceil((Math.max(...ratings) + pad) / 10) * 10

  const x = (i: number) => (i / (points.length - 1)) * 100 // percent across
  const y = (rating: number) => ((high - rating) / (high - low)) * 100 // percent down
  const line = points.map((p, i) => `${x(i)},${y(p.rating)}`).join(' ')

  return (
    <div className="rating-chart">
      <div className="chart-axis">
        <span>{high}</span>
        <span>{Math.round((high + low) / 2)}</span>
        <span>{low}</span>
      </div>
      <div className="chart-plot" style={{ height: HEIGHT }}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {[0, 50, 100].map((g) => (
            <line key={g} x1="0" x2="100" y1={g} y2={g} className="grid-line" />
          ))}
          <polyline points={line} className="rating-line" />
        </svg>
        {points.map((p, i) => {
          const change = i === 0 ? null : Math.round(p.rating) - Math.round(points[i - 1].rating)
          return (
            <div
              key={i}
              className="chart-dot"
              style={{ left: `${x(i)}%`, top: `${y(p.rating)}%` }}
              tabIndex={0}
            >
              <span className="bar-tip">
                {i === 0 ? 'start' : `match ${i}`} · {Math.round(p.rating)}
                {change !== null && ` (${change >= 0 ? '+' : ''}${change})`}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}