import { useCallback, useEffect, useState } from 'react'
import { api, type AnswerResult, type NextQuestion } from '../lib/api'
import { celebrate, punish } from '../lib/effects'
import { currentStreak, SESSION_LENGTH, type Round } from '../lib/session'
import QuestionCard from './QuestionCard'
import Results from './Results'

type Phase = 'loading' | 'question' | 'submitting' | 'result' | 'summary' | 'error'

type Props = {
  effects: boolean
}

export default function PuzzleRush({ effects }: Props) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [current, setCurrent] = useState<NextQuestion | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [result, setResult] = useState<AnswerResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rounds, setRounds] = useState<Round[]>([])

  const showQuestion = useCallback((next: NextQuestion) => {
    setCurrent(next)
    setPicked(null)
    setResult(null)
    setPhase('question')
  }, [])

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
      if (correct >= 8) celebrate(10) // big burst
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
        const res = await api.submitAnswer(current.attempt_id, choice)
        const round = { correct: res.correct, timedOut: res.timed_out, ms: res.response_ms }
        const streak = currentStreak([...rounds, round])
        setResult(res)
        setRounds((previous) => [...previous, round])
        setPhase('result')
        if (effects) {
          if (res.correct) celebrate(streak)
          else punish()
        }
      } catch (e) {
        showError(e)
      }
    },
    [phase, current, rounds, effects, showError],
  )

  // Load the first question when the component appears.
  useEffect(() => {
    let cancelled = false
    api
      .nextQuestion()
      .then((next) => !cancelled && showQuestion(next))
      .catch((e) => !cancelled && showError(e))
    return () => {
      cancelled = true
    }
  }, [showQuestion, showError])

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
    return <p className="tagline">loading...</p>
  }

  const { question } = current
  const answered = phase === 'result' && result

  // Bonus stamps: answered in the last 3 seconds, or right in under 2.5 seconds.
  const remainingMs = question.time_limit_s * 1000 - (result?.response_ms ?? 0)
  let stamp: string | null = null
  if (answered && result.correct) {
    if (remainingMs < 3000) stamp = 'clutch!'
    else if (result.response_ms < 2500) stamp = 'too easy'
  }
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