import { useCallback, useEffect, useRef, useState } from 'react'
import { wsUrl, type Question } from '../lib/api'
import { celebrate, punish, sparkle, victory } from '../lib/effects'
import { stampFor } from '../lib/session'
import { supabase } from '../lib/supabase'
import MatchSummary, { type RoundSummary } from './MatchSummary'
import QuestionCard from './QuestionCard'

// ---- Messages the match server sends (see backend/app/match_room.py) ----
type Side = { correct: boolean; timed_out: boolean; response_ms: number; points: number } | null
type Score = { you: number; opponent: number }
type RoundMessage = { type: 'round'; round: number; of: number; question: Question }
type ResultMessage = {
  type: 'round_result'
  round: number
  of: number
  you: Side
  opponent: Side
  correct_choice: number
  explanation: string
  score: Score
  next_in: number
}
type RatingChange = { before: number; after: number; change: number }
type OverMessage = {
  type: 'match_over'
  result: 'win' | 'loss' | 'draw'
  forfeit: boolean
  opponent: string | null
  score: Score
  rated: boolean
  rating: RatingChange | null // only in ranked matches
}
type ServerMessage =
  | { type: 'waiting'; you: string; rated: boolean }
  | { type: 'start'; opponent: string; rounds: number; starts_in: number }
  | RoundMessage
  | { type: 'opponent_answered' }
  | ResultMessage
  | OverMessage
  | { type: 'error'; message: string }

type Status = 'connecting' | 'waiting' | 'starting' | 'playing' | 'result' | 'over' | 'error'

type Props = {
  code: string
  effects: boolean
  onExit: () => void
  onNewMatch: (rated: boolean) => void
}

export default function CodeOff({ code, effects, onExit, onNewMatch }: Props) {
  const [status, setStatus] = useState<Status>('connecting')
  const [rated, setRated] = useState(false)
  const [opponent, setOpponent] = useState('')
  const [round, setRound] = useState<RoundMessage | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [locked, setLocked] = useState(false)
  const [opponentLocked, setOpponentLocked] = useState(false)
  const [result, setResult] = useState<ResultMessage | null>(null)
  const [score, setScore] = useState<Score>({ you: 0, opponent: 0 })
  const [over, setOver] = useState<OverMessage | null>(null)
  const [error, setError] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [history, setHistory] = useState<RoundSummary[]>([])
  const [streakShown, setStreakShown] = useState(0)

  const socket = useRef<WebSocket | null>(null)
  const streak = useRef(0)
  // Read the latest fx setting inside socket handlers without reconnecting when it changes.
  const effectsRef = useRef(effects)
  useEffect(() => {
    effectsRef.current = effects
  }, [effects])

  // Connect to the match and react to everything the server says.
  useEffect(() => {
    let done = false
    const ws = new WebSocket(wsUrl(`/ws/matches/${code}`))
    socket.current = ws

    ws.onopen = async () => {
      const { data } = await supabase.auth.getSession()
      ws.send(JSON.stringify({ type: 'auth', token: data.session?.access_token ?? '' }))
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data) as ServerMessage
      switch (message.type) {
        case 'waiting':
          setRated(message.rated)
          setStatus('waiting')
          break
        case 'start':
          setOpponent(message.opponent)
          setCountdown(message.starts_in)
          setStatus('starting')
          break
        case 'round':
          setRound(message)
          setPicked(null)
          setLocked(false)
          setOpponentLocked(false)
          setResult(null)
          setStatus('playing')
          break
        case 'opponent_answered':
          setOpponentLocked(true)
          break
        case 'round_result':
          setResult(message)
          setScore(message.score)
          setHistory((h) => [
            ...h,
            { round: message.round, you: message.you, opponent: message.opponent },
          ])
          setCountdown(message.next_in)
          setStatus('result')
          streak.current = message.you?.correct ? streak.current + 1 : 0
          setStreakShown(streak.current)
          if (effectsRef.current) {
            if (!message.you?.correct) punish()
            else if (streak.current >= 3) celebrate(streak.current)
            else sparkle()
          }
          break
        case 'match_over':
          done = true
          setOver(message)
          setScore(message.score)
          setStatus('over')
          if (effectsRef.current) {
            if (message.result === 'win') victory()
            else if (message.result === 'loss') punish()
          }
          break
        case 'error':
          done = true
          setError(message.message)
          setStatus('error')
          break
      }
    }

    ws.onclose = () => {
      if (!done) {
        setError('Lost connection to the match.')
        setStatus('error')
      }
    }

    // Leaving the screen closes the connection (mid-match, that's a forfeit).
    return () => {
      done = true
      ws.close()
    }
  }, [code])

  // Tick countdowns down once per second.
  useEffect(() => {
    if (countdown <= 0) return
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(id)
  }, [countdown])

  // choice is null when the timer ran out without an answer.
  const answer = useCallback(
    (choice: number | null) => {
      if (status !== 'playing' || locked) return
      setPicked(choice)
      setLocked(true)
      socket.current?.send(JSON.stringify({ type: 'answer', choice }))
    },
    [status, locked],
  )

  // Keyboard: 1-4 to answer.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (status !== 'playing' || locked || !round) return
      const n = Number(event.key)
      if (n >= 1 && n <= round.question.options.length) answer(n - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [status, locked, round, answer])

  if (status === 'connecting') return <p className="tagline">connecting...</p>

  if (status === 'error') {
    return (
      <div className="codeoff-center">
        <p className="auth-message">{error}</p>
        <button className="link" onClick={onExit}>
          ← back to menu
        </button>
      </div>
    )
  }

  if (status === 'waiting') {
    if (rated) return <p className="tagline">waiting for your opponent to connect...</p>
    return <Lobby code={code} onExit={onExit} />
  }

  if (status === 'starting') {
    return (
      <div className="codeoff-center">
        <p className="vs">
          you <span className="vs-x">vs</span> <span className="you">{opponent}</span>
        </p>
        {/* The key replays the pop animation for every number. */}
        <p key={countdown} className="countdown">
          {countdown > 0 ? countdown : 'go!'}
        </p>
      </div>
    )
  }

  if (status === 'over' && over) {
    return (
      <MatchOver
        over={over}
        history={history}
        effects={effects}
        onExit={onExit}
        onNewMatch={onNewMatch}
      />
    )
  }

  if (!round) return null
  const revealed = status === 'result' && result
  const stamp =
    revealed && result.you
      ? stampFor(result.you.correct, result.you.response_ms, round.question.time_limit_s)
      : null

  return (
    <div className="rush">
      <div className="scoreboard">
        <div className="side">
          <span className="side-name">
            you
            {streakShown >= 3 && <span className="hot-streak">🔥 {streakShown} in a row</span>}
          </span>
          <span className="side-score">{score.you}</span>
        </div>
        <span className="round-label">
          {rated && 'ranked · '}round {round.round}/{round.of}
        </span>
        <div className="side right">
          <span className="side-score">{score.opponent}</span>
          <span className="side-name">
            {opponent}
            {status === 'playing' && (
              <span className={opponentLocked ? 'opp-status locked' : 'opp-status'}>
                {opponentLocked ? 'locked in ✓' : 'thinking...'}
              </span>
            )}
          </span>
        </div>
      </div>

      <QuestionCard
        question={round.question}
        roundKey={`${code}-${round.round}`}
        running={status === 'playing' && !locked}
        picked={picked}
        correctChoice={revealed ? result.correct_choice : null}
        disabled={status !== 'playing' || locked}
        onAnswer={answer}
      />

      {status === 'playing' && locked && (
        <p className="waiting-note">locked in. waiting for {opponent}...</p>
      )}

      {revealed && (
        <div className="result">
          <p className={result.you?.correct ? 'verdict good' : 'verdict bad'}>
            {result.you?.correct ? 'correct!' : result.you?.timed_out ? "time's up" : 'nope'}
            <span className="points"> +{result.you?.points ?? 0}</span>
            {stamp && <span className="stamp">{stamp}</span>}
          </p>
          <p className="opp-line">
            {opponent}: {describe(result.opponent)}
          </p>
          <p className="explanation">{result.explanation}</p>
          <p className="next-note">
            {result.round < result.of
              ? `next round in ${countdown}...`
              : `final results in ${countdown}...`}
          </p>
        </div>
      )}
    </div>
  )
}

function describe(side: Side): string {
  if (!side) return 'no answer'
  if (side.correct) return `+${side.points} in ${(side.response_ms / 1000).toFixed(1)}s`
  return side.timed_out ? 'ran out of time' : 'missed it'
}

function Lobby({ code, onExit }: { code: string; onExit: () => void }) {
  const [copied, setCopied] = useState(false)
  const link = `${window.location.origin}${window.location.pathname}?match=${code}`

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard blocked: the link is still selectable in the box
    }
  }

  return (
    <div className="codeoff-center lobby">
      <h2 className="auth-title">code-off</h2>
      <p className="match-code">{code}</p>
      <p className="picker-hint">send this link to your opponent</p>
      <div className="name-row">
        <input className="link-box" value={link} readOnly onFocus={(e) => e.target.select()} />
        <button className="btn-primary copy" onClick={copy}>
          {copied ? 'copied!' : 'copy'}
        </button>
      </div>
      <p className="waiting-dots">
        waiting for opponent<span>.</span>
        <span>.</span>
        <span>.</span>
      </p>
      <button className="link" onClick={onExit}>
        cancel
      </button>
    </div>
  )
}

function MatchOver({
  over,
  history,
  effects,
  onExit,
  onNewMatch,
}: {
  over: OverMessage
  history: RoundSummary[]
  effects: boolean
  onExit: () => void
  onNewMatch: (rated: boolean) => void
}) {
  const name = over.opponent ?? 'your opponent'
  const title =
    over.result === 'win'
      ? 'you outcoded'
      : over.result === 'loss'
        ? 'you got outcoded'
        : 'dead even'
  const subtitle = over.forfeit
    ? `${name} rage-quit. a win's a win.`
    : over.result === 'win'
      ? name
      : over.result === 'loss'
        ? `by ${name}`
        : `you and ${name} are equally cracked`

  return (
    <div className={`codeoff-center match-over ${over.result}`}>
      <h2 className="over-title">{title}</h2>
      <p className="over-subtitle">{subtitle}</p>
      <p className="final-score">
        {over.score.you} <span className="dash">—</span> {over.score.opponent}
      </p>
      {over.rating && <RatingTicker change={over.rating} animate={effects} />}
      <MatchSummary rounds={history} opponent={name} />
      <button className="btn-primary" onClick={() => onNewMatch(over.rated)}>
        {over.rated ? 'find another match' : 'new code-off'}
      </button>
      <button className="link" onClick={onExit}>
        ← menu
      </button>
    </div>
  )
}

// The new rating counts up (or down) from the old one, like a slot machine.
function RatingTicker({ change, animate }: { change: RatingChange; animate: boolean }) {
  const [shown, setShown] = useState(animate ? change.before : change.after)

  useEffect(() => {
    if (!animate) return
    let frame = 0
    const delay = setTimeout(() => {
      const start = performance.now()
      const duration = 1200
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / duration)
        const eased = 1 - (1 - t) ** 3 // fast at first, settling at the end
        setShown(Math.round(change.before + (change.after - change.before) * eased))
        if (t < 1) frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
    }, 600) // let the title land first
    return () => {
      clearTimeout(delay)
      cancelAnimationFrame(frame)
    }
  }, [change, animate])

  const up = change.change >= 0
  return (
    <p className="rating-ticker">
      <span className="rating-label">rating</span>
      <span className="rating-now">{shown}</span>
      <span className={up ? 'rating-delta up' : 'rating-delta down'}>
        {up ? '+' : ''}
        {change.change}
      </span>
    </p>
  )
}