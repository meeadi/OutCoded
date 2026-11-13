import { useCallback, useEffect, useRef, useState } from 'react'
import { useAwayTimer } from '../hooks/useAwayTimer'
import { api, ApiError, type AnswerResult, type NextQuestion } from '../lib/api'
import { celebrate, punish, sparkle, victory } from '../lib/effects'
import {
  BLITZ_SECONDS,
  loadBest,
  MODES,
  RUSH_LENGTH,
  saveBest,
  savedSession,
  SESSION_KEY,
  type PracticeSettings,
} from '../lib/practice'
import { bestStreak, currentStreak, stampFor, type Round } from '../lib/session'
import Loader from './Loader'
import QuestionCard from './QuestionCard'
import Results from './Results'

type Phase = 'loading' | 'question' | 'submitting' | 'result' | 'summary' | 'error'

type Props = {
  settings: PracticeSettings
  effects: boolean
  onChangeSettings: () => void // back to the practice hub
}

export default function Practice({ settings, effects, onChangeSettings }: Props) {
  const { variant } = settings
  const [resumed] = useState<Round[]>(() => {
    const saved = savedSession()
    const same = saved && JSON.stringify(saved.settings) === JSON.stringify(settings)
    return same && variant !== 'blitz' ? saved.rounds : []
  })
  const finishedAlready = variant === 'rush' && resumed.length >= RUSH_LENGTH
  const [phase, setPhase] = useState<Phase>(finishedAlready ? 'summary' : 'loading')
  const [current, setCurrent] = useState<NextQuestion | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [result, setResult] = useState<AnswerResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rounds, setRounds] = useState<Round[]>(resumed)
  const [endNote, setEndNote] = useState<string | null>(null) // why the session ended
  const [best] = useState(() => loadBest(settings)) // personal best before this session
  const [blitzLeft, setBlitzLeft] = useState(BLITZ_SECONDS)
  const blitzStarted = useRef(false)
  const blitzClock = useRef(BLITZ_SECONDS)
  const away = useAwayTimer()

  const showQuestion = useCallback(
    (next: NextQuestion) => {
      away.reset()
      setCurrent(next)
      setPicked(null)
      setResult(null)
      setPhase('question')
      blitzStarted.current = true
    },
    [away],
  )

  const finish = useCallback((note: string | null = null) => {
    setEndNote(note)
    setPhase('summary')
  }, [])

  const showError = useCallback(
    (e: unknown) => {
      // Review runs until nothing's left: that's a happy ending, not an error.
      if (variant === 'review' && e instanceof ApiError && e.status === 404) {
        finish('every mistake fixed. clean slate.')
        return
      }
      setError(e instanceof Error ? e.message : String(e))
      setPhase('error')
    },
    [variant, finish],
  )

  const loadNext = useCallback(() => {
    setPhase('loading')
    api.nextQuestion(settings).then(showQuestion).catch(showError)
  }, [settings, showQuestion, showError])

  // After an answer: next question, or the end of the session.
  const advance = useCallback(() => {
    const last = rounds[rounds.length - 1]
    if (variant === 'rush' && rounds.length >= RUSH_LENGTH) return finish()
    if (variant === 'survival' && last && !last.correct) return finish('one mistake and it ends.')
    loadNext()
  }, [rounds, variant, finish, loadNext])

  const restart = useCallback(() => {
    setRounds([])
    setEndNote(null)
    setBlitzLeft(BLITZ_SECONDS)
    blitzClock.current = BLITZ_SECONDS
    blitzStarted.current = false
    loadNext()
  }, [loadNext])

  // choice is null when the timer ran out without an answer.
  const answer = useCallback(
    async (choice: number | null) => {
      if (phase !== 'question' || !current) return
      setPicked(choice)
      setPhase('submitting')
      try {
        const res = await api.submitAnswer(current.attempt_id, choice, away.read())
        const round = { correct: res.correct, timedOut: res.timed_out, ms: res.response_ms }
        const streak = currentStreak([...rounds, round])
        setResult(res)
        setRounds((previous) => [...previous, round])
        setPhase('result')
        if (effects) {
          if (!res.correct) punish()
          else if (streak >= 3) celebrate(streak)
          else sparkle()
        }
      } catch (e) {
        showError(e)
      }
    },
    [phase, current, rounds, effects, showError, away],
  )

  // Blitz: no explanations, just a quick verdict and straight on to the next one.
  useEffect(() => {
    if (variant !== 'blitz' || phase !== 'result') return
    const id = setTimeout(advance, 700)
    return () => clearTimeout(id)
  }, [variant, phase, advance])

  // Blitz: one clock for the whole session, starting with the first question.
  const blitzRunning = variant === 'blitz' && phase !== 'summary' && phase !== 'error'
  useEffect(() => {
    if (!blitzRunning) return
    const id = setInterval(() => {
      if (!blitzStarted.current) return
      blitzClock.current = Math.max(0, blitzClock.current - 1)
      setBlitzLeft(blitzClock.current)
      if (blitzClock.current === 0) finish("time's up.")
    }, 1000)
    return () => clearInterval(id)
  }, [blitzRunning, finish])

  // Celebrate the end of a session, and remember personal bests.
  const score =
    variant === 'blitz'
      ? rounds.filter((r) => r.correct).length
      : variant === 'survival'
        ? bestStreak(rounds)
        : 0
  const newBest = (variant === 'blitz' || variant === 'survival') && score > best
  const celebrated = useRef(false) // once per session
  useEffect(() => {
    if (phase !== 'summary') {
      celebrated.current = false
      return
    }
    if (celebrated.current || rounds.length === 0) return
    celebrated.current = true
    if (newBest) saveBest(settings, score)
    if (!effects) return
    const correct = rounds.filter((r) => r.correct).length
    if (newBest || (variant === 'rush' && correct >= 8)) victory()
    else if (variant === 'rush' && correct <= 3) punish()
  }, [phase, rounds, newBest, settings, score, effects, variant])

  // Remember progress in this tab; forget it when the player leaves the session.
  useEffect(() => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ settings, rounds }))
  }, [settings, rounds])
  useEffect(() => () => sessionStorage.removeItem(SESSION_KEY), [])

  // Load the first question when the component appears (unless the rush is already over).
  useEffect(() => {
    if (finishedAlready) return
    let cancelled = false
    api
      .nextQuestion(settings)
      .then((next) => !cancelled && showQuestion(next))
      .catch((e) => !cancelled && showError(e))
    return () => {
      cancelled = true
    }
  }, [finishedAlready, settings, showQuestion, showError])

  // Keyboard: 1-4 to answer, Enter or Space for the next question.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (phase === 'question' && current) {
        const n = Number(event.key)
        if (n >= 1 && n <= current.question.options.length) answer(n - 1)
      } else if (phase === 'result' && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault()
        advance()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase, current, answer, advance])

  const modeName = MODES.find((m) => m.id === variant)?.name ?? variant

  if (phase === 'summary') {
    return (
      <Results
        rounds={rounds}
        variant={variant}
        note={endNote}
        best={newBest ? null : best}
        newBest={newBest}
        onRestart={restart}
        onChangeSettings={onChangeSettings}
      />
    )
  }

  if (phase === 'error') {
    return (
      <div className="rush">
        <p className="auth-message">{error}</p>
        <button className="link" onClick={loadNext}>
          try again
        </button>
        <button className="link" onClick={onChangeSettings}>
          ← change settings
        </button>
      </div>
    )
  }

  if (!current || phase === 'loading') {
    return <Loader />
  }

  const { question } = current
  const answered = phase === 'result' && result
  const untimed = variant === 'zen' || variant === 'blitz' // blitz uses one clock for the session
  const stamp = answered
    ? stampFor(result.correct, result.response_ms, question.time_limit_s)
    : null
  const streak = currentStreak(rounds)
  const correct = rounds.filter((r) => r.correct).length
  const isLast = variant === 'rush' && rounds.length >= RUSH_LENGTH
  const ending = isLast || (variant === 'survival' && answered && !result.correct)

  return (
    <div className="rush">
      <div className="rush-stats">
        <span>
          {variant === 'rush' &&
            `${Math.min(rounds.length + (answered ? 0 : 1), RUSH_LENGTH)}/${RUSH_LENGTH}`}
          {variant === 'blitz' && (
            <span className={blitzLeft <= 10 ? 'blitz-clock low' : 'blitz-clock'}>
              {blitzLeft}s · {correct} correct
            </span>
          )}
          {variant === 'survival' && `survived ${streak}${best ? ` · best ${best}` : ''}`}
          {variant === 'zen' && `zen · ${rounds.length} answered`}
          {variant === 'review' && `review · ${correct} fixed`}
        </span>
        <span className={streak >= 3 ? 'streak hot' : 'streak'}>
          streak {streak}
          {streak >= 5 && ' 🔥'}
        </span>
      </div>

      {variant === 'blitz' && (
        <div className="blitz-bar" aria-hidden="true">
          <div style={{ width: `${(blitzLeft / BLITZ_SECONDS) * 100}%` }} />
        </div>
      )}
      {current.widened && (
        <p className="widened-note">
          nothing left at this difficulty here, so this one's from another level.
        </p>
      )}

      <QuestionCard
        question={question}
        roundKey={current.attempt_id}
        running={phase === 'question'}
        timed={!untimed}
        picked={picked}
        correctChoice={answered ? result.correct_choice : null}
        disabled={phase !== 'question'}
        onAnswer={answer}
      />

      {answered && variant === 'blitz' && (
        <p className={result.correct ? 'verdict good' : 'verdict bad'}>
          {result.correct ? 'correct!' : 'nope'}
        </p>
      )}

      {answered && variant !== 'blitz' && (
        <div className="result">
          <p className={result.correct ? 'verdict good' : 'verdict bad'}>
            {result.correct ? 'correct!' : result.timed_out ? "time's up" : 'nope'}
            <span className="time"> {(result.response_ms / 1000).toFixed(1)}s</span>
            {stamp && variant !== 'zen' && <span className="stamp">{stamp}</span>}
          </p>
          <p className="explanation">{result.explanation}</p>
          <button className="link" onClick={advance}>
            {ending ? 'press enter for results →' : 'press enter for next →'}
          </button>
        </div>
      )}

      {(variant === 'zen' || variant === 'review') && rounds.length > 0 && (
        <button className="link end-session" onClick={() => finish()}>
          end {modeName} session
        </button>
      )}
    </div>
  )
}