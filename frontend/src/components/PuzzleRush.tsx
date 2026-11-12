import { useCallback, useEffect, useState } from 'react'
import { useAwayTimer } from '../hooks/useAwayTimer'
import { api, type AnswerResult, type NextQuestion } from '../lib/api'
import { celebrate, punish, sparkle, victory } from '../lib/effects'
import { currentStreak, SESSION_LENGTH, stampFor, type Round } from '../lib/session'
import QuestionCard from './QuestionCard'
import Results from './Results'
import Loader from './Loader'

type Phase = 'loading' | 'question' | 'submitting' | 'result' | 'summary' | 'error'


// Progress survives a refresh or a dropped connection: the rush picks up where
// it left off (with a fresh question; the one on screen is skipped, not counted).
export const RUSH_KEY = 'rush-progress'

function savedRounds(): Round[] {
  try {
    const saved = JSON.parse(sessionStorage.getItem(RUSH_KEY) ?? '[]')
    return Array.isArray(saved) ? saved : []
  } catch {
    return []
  }
}

type Props = {
  effects: boolean
}

export default function PuzzleRush({ effects }: Props) {
  const [resumed] = useState(savedRounds)
  const [phase, setPhase] = useState<Phase>(
    resumed.length >= SESSION_LENGTH ? 'summary' : 'loading',
  )
  const [current, setCurrent] = useState<NextQuestion | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [result, setResult] = useState<AnswerResult | null>(null)
  const [error, setError] = useState<string | null>(null)
    const [rounds, setRounds] = useState<Round[]>(resumed)
  const away = useAwayTimer()

  const showQuestion = useCallback(
     (next: NextQuestion) => {
       away.reset()
       setCurrent(next)
       setPicked(null)
       setResult(null)
       setPhase('question')
     }, [away],)

  const showError = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : String(e))
    setPhase('error')
  }, [])

  const loadNext = useCallback(() => {
    setPhase('loading')
    api.nextQuestion().then(showQuestion).catch(showError)
  }, [showQuestion, showError])

  // After the last question, show the summary instead of another question.
  const advance = useCallback(() => {
    if (rounds.length < SESSION_LENGTH) {
      loadNext()
      return
    }
    setPhase('summary')
    const correct = rounds.filter((r) => r.correct).length
    if (effects) {
      if (correct >= 8) victory() // big burst
      else if (correct <= 3) punish()
    }
  }, [rounds, effects, loadNext])

  const restart = useCallback(() => {
    setRounds([])
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

  // Remember progress in this tab; forget it when the player leaves the rush.
  useEffect(() => {
    sessionStorage.setItem(RUSH_KEY, JSON.stringify(rounds))
  }, [rounds])
  useEffect(() => () => sessionStorage.removeItem(RUSH_KEY), [])

  // Load the first question when the component appears (unless the rush is already over).
  useEffect(() => {
    if (resumed.length >= SESSION_LENGTH) return
    let cancelled = false
    api
      .nextQuestion()
      .then((next) => !cancelled && showQuestion(next))
      .catch((e) => !cancelled && showError(e))
    return () => {
      cancelled = true
    }
  }, [resumed, showQuestion, showError])

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

  if (phase === 'summary') {
    return <Results rounds={rounds} onRestart={restart} />
  }

  if (phase === 'error') {
    return (
      <div className="rush">
        <p className="auth-message">{error}</p>
        <button className="link" onClick={loadNext}>
          try again
        </button>
      </div>
    )
  }

  if (!current || phase === 'loading') {
    return <Loader />
  }

  const { question } = current
  const answered = phase === 'result' && result

  // Bonus stamps: answered in the last 3 seconds, or right in under 2.5 seconds.
  const stamp = answered
    ? stampFor(result.correct, result.response_ms, question.time_limit_s)
    : null
  const streak = currentStreak(rounds)
  const isLast = rounds.length >= SESSION_LENGTH

  return (
    <div className="rush">
      <div className="rush-stats">
        <span>
          {Math.min(rounds.length + (answered ? 0 : 1), SESSION_LENGTH)}/{SESSION_LENGTH}
        </span>
        <span className={streak >= 3 ? 'streak hot' : 'streak'}>
          streak {streak}
          {streak >= 5 && ' 🔥'}
        </span>
      </div>

      <QuestionCard
        question={question}
        roundKey={current.attempt_id}
        running={phase === 'question'}
        picked={picked}
        correctChoice={answered ? result.correct_choice : null}
        disabled={phase !== 'question'}
        onAnswer={answer}
      />

      {answered && (
        <div className="result">
          <p className={result.correct ? 'verdict good' : 'verdict bad'}>
            {result.correct ? 'correct!' : result.timed_out ? "time's up" : 'nope'}
            <span className="time"> {(result.response_ms / 1000).toFixed(1)}s</span>
            {stamp && <span className="stamp">{stamp}</span>}
          </p>
          <p className="explanation">{result.explanation}</p>
          <button className="link" onClick={advance}>
            {isLast ? 'press enter for results →' : 'press enter for next →'}
          </button>
        </div>
      )}
    </div>
  )
}