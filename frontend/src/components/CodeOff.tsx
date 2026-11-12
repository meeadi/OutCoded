import { useCallback, useEffect, useRef, useState } from 'react'
import { useAwayTimer } from '../hooks/useAwayTimer'
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
  forfeit_reason: 'left' | 'disconnected' | null
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
  | { type: 'opponent_disconnected'; reconnect_s: number; round_voided: boolean }
  | { type: 'opponent_reconnected' }
  | { type: 'round_voided'; round: number; score: Score }
  | {
      type: 'resume'
      opponent: string
      rated: boolean
      completed: number
      score: Score
      history: RoundSummary[]
      opponent_connected: boolean
    }
  | { type: 'resuming'; in: number }
  | { type: 'ping' }

type Status =
  | 'connecting'
  | 'waiting'
  | 'starting'
  | 'playing'
  | 'result'
  | 'paused' // someone's reconnecting, or a round was thrown away
  | 'reconnecting' // our own connection dropped
  | 'over'
  | 'error'

const RECONNECT_MS = 30_000 // matches RECONNECT_S on the server
const SILENCE_MS = 25_000 // the server pings every 10 s; this long without a word means the line is dead

// The current time, ticking while `active`, for "back in 23s" style countdowns.
function useNow(active: boolean): number {
  const [now, setNow] = useState(0)
  useEffect(() => {
    if (!active) return
    const tick = () => setNow(Date.now())
    const id = setInterval(tick, 250)
    const first = setTimeout(tick, 0)
    return () => {
      clearInterval(id)
      clearTimeout(first)
    }
  }, [active])
  return now
}

function secondsLeft(deadline: number, now: number, max: number): number {
  return Math.max(0, Math.min(max, Math.ceil((deadline - now) / 1000)))
}

type Props = {
  code: string
  effects: boolean
  onExit: () => void
  onNewMatch: (rated: boolean) => void
  onLiveChange?: (live: boolean) => void // true while the match is being played
}

export default function CodeOff({ code, effects, onExit, onNewMatch, onLiveChange }: Props) {
  const [status, setStatus] = useState<Status>('connecting')
  const live =
    status === 'starting' ||
    status === 'playing' ||
    status === 'result' ||
    status === 'paused' ||
    status === 'reconnecting'
  const liveRef = useRef(live)
  useEffect(() => {
    liveRef.current = live
  }, [live])

  useEffect(() => {
    onLiveChange?.(live)
  }, [live, onLiveChange])
  useEffect(() => () => onLiveChange?.(false), [onLiveChange])
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
  const [pauseNote, setPauseNote] = useState('')
  const [reconnectBy, setReconnectBy] = useState(0) // when our own reconnect window closes
  const [opponentAway, setOpponentAway] = useState<{ until: number; voided: boolean } | null>(null)
  const now = useNow(status === 'reconnecting' || opponentAway !== null)

  const socket = useRef<WebSocket | null>(null)
  const away = useAwayTimer()
  const streak = useRef(0)
  // Read the latest fx setting inside socket handlers without reconnecting when it changes.
  const effectsRef = useRef(effects)
  useEffect(() => {
    effectsRef.current = effects
  }, [effects])

  // Connect to the match and react to everything the server says. If the
  // connection drops mid-match, keep trying to get back in for up to 30 s.
  useEffect(() => {
    let done = false // match over, an error, or we left the screen: stop reconnecting
    let ws: WebSocket | null = null
    let lostAt: number | null = null
    let tries = 0
    let retry: ReturnType<typeof setTimeout> | undefined
    let watchdog: ReturnType<typeof setTimeout> | undefined

    function handle(message: ServerMessage) {
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
          away.reset()
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
        case 'opponent_disconnected':
          setOpponentAway({
            until: Date.now() + message.reconnect_s * 1000,
            voided: message.round_voided,
          })
          if (message.round_voided) {
            setPauseNote("this round won't count. it'll be replayed with a new question.")
            setStatus('paused')
          }
          break
        case 'opponent_reconnected':
          setOpponentAway(null)
          break
        case 'round_voided':
          setScore(message.score)
          setStatus('paused')
          break
        case 'resume':
          // We're back (after a drop or a page refresh): catch up on the match so far.
          setOpponent(message.opponent)
          setRated(message.rated)
          setScore(message.score)
          setHistory(message.history)
          setRound(null)
          setPauseNote(
            message.opponent_connected
              ? "you're back in. next round coming up..."
              : `you're back in. waiting for ${message.opponent}...`,
          )
          setStatus('paused')
          break
        case 'resuming':
          setOpponentAway(null)
          setCountdown(message.in)
          setPauseNote("everyone's here. resuming...")
          setStatus('paused')
          break
        case 'match_over':
          done = true
          setOver(message)
          setScore(message.score)
          setOpponentAway(null)
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
        case 'ping':
          break
      }
    }

    function connect() {
      const current = new WebSocket(wsUrl(`/ws/matches/${code}`))
      ws = current
      socket.current = current

      // No message for a while (not even a ping) means a dead line: drop it and reconnect.
      const listen = () => {
        clearTimeout(watchdog)
        watchdog = setTimeout(() => current.close(), SILENCE_MS)
      }

      current.onopen = async () => {
        listen()
        const { data } = await supabase.auth.getSession()
        current.send(JSON.stringify({ type: 'auth', token: data.session?.access_token ?? '' }))
      }

      current.onmessage = (event) => {
        listen()
        lostAt = null
        tries = 0
        handle(JSON.parse(event.data) as ServerMessage)
      }

      current.onclose = (event) => {
        clearTimeout(watchdog)
        if (done || current !== ws) return
        if (event.code === 4000) {
          done = true
          setError('this match is open in another tab now.')
          setStatus('error')
          return
        }
        lostAt ??= Date.now()
        const left = RECONNECT_MS - (Date.now() - lostAt)
        if (left <= 0) {
          done = true
          setError(
            "couldn't get back in time. if the match was still going, it counted as a forfeit.",
          )
          setStatus('error')
          return
        }
        setReconnectBy(lostAt + RECONNECT_MS)
        setStatus('reconnecting')
        retry = setTimeout(connect, Math.min(3000, 500 * 2 ** tries++))
      }
    }

    connect()

    // Leaving the screen on purpose: tell the server right away (mid-match, that's a forfeit).
    return () => {
      done = true
      clearTimeout(retry)
      clearTimeout(watchdog)
      if (liveRef.current && ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'forfeit' }))
      }
      ws?.close()
    }
  }, [code, away])

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
      socket.current?.send(JSON.stringify({ type: 'answer', choice, away_ms: away.read() }))
    },
    [status, locked, away],
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

  if (status === 'reconnecting') {
    return (
      <div className="codeoff-center">
        <h2 className="over-title">connection lost</h2>
        <p className="waiting-dots">
          reconnecting<span>.</span>
          <span>.</span>
          <span>.</span>
        </p>
        <p className="picker-hint">
          the match is paused for both of you. {secondsLeft(reconnectBy, now, 30)}s to get back.
        </p>
        <button className="link" onClick={onExit}>
          leave match
        </button>
      </div>
    )
  }

  if (status === 'paused') {
    return (
      <div className="codeoff-center">
        <p className="vs">
          you <span className="vs-x">vs</span> <span className="you">{opponent}</span>
        </p>
        <p className="final-score">
          {score.you} <span className="dash">—</span> {score.opponent}
        </p>
        {opponentAway ? (
          <OpponentAway name={opponent} seconds={secondsLeft(opponentAway.until, now, 30)} />
        ) : (
          countdown > 0 && (
            <p key={countdown} className="countdown">
              {countdown}
            </p>
          )
        )}
        {pauseNote && <p className="picker-hint">{pauseNote}</p>}
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

      {opponentAway && (
        <OpponentAway name={opponent} seconds={secondsLeft(opponentAway.until, now, 30)} />
      )}

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

// "<name> lost connection · 23s to get back". Their round counts as a miss if
// they've used their replay; otherwise it's thrown away.
function OpponentAway({ name, seconds }: { name: string; seconds: number }) {
  return (
    <p className="opp-away" role="status">
      {name} lost connection · {seconds}s to get back
    </p>
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
    ? over.forfeit_reason === 'disconnected'
      ? `${name} lost connection and didn't make it back. a win's a win.`
      : `${name} rage-quit. a win's a win.`
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