import { useCallback, useEffect, useState } from 'react'
import { api, type AnswerResult, type NextQuestion } from '../lib/api'

type Phase = 'loading' | 'question' | 'submitting' | 'result' | 'error'

export default function PuzzleRush() {
  const [phase, setPhase] = useState<Phase>('loading')
  const [current, setCurrent] = useState<NextQuestion | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [result, setResult] = useState<AnswerResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState({ correct: 0, total: 0, streak: 0 })

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

  // choice is null when the timer ran out without an answer.
  const answer = useCallback(
    async (choice: number | null) => {
      if (phase !== 'question' || !current) return
      setPicked(choice)
      setPhase('submitting')
      try {
        const res = await api.submitAnswer(current.attempt_id, choice)
        setResult(res)
        setStats((s) => ({
          correct: s.correct + (res.correct ? 1 : 0),
          total: s.total + 1,
          streak: res.correct ? s.streak + 1 : 0,
        }))
        setPhase('result')
      } catch (e) {
        showError(e)
      }
    },
    [phase, current, showError],
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
        loadNext()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase, current, answer, loadNext])

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

  function optionClass(index: number) {
    if (!answered) return 'option'
    if (index === result!.correct_choice) return 'option correct'
    if (index === picked) return 'option wrong'
    return 'option faded'
  }

  return (
    <div className="rush">
      <div className="rush-stats">
        <span>
          {stats.correct}/{stats.total}
        </span>
        <span className={stats.streak >= 3 ? 'streak hot' : 'streak'}>streak {stats.streak}</span>
      </div>

      {/* The key restarts the animation for every new question. */}
      <div className="timer">
        <div
          key={current.attempt_id}
          className="timer-fill"
          style={{
            animationDuration: `${question.time_limit_s}s`,
            animationPlayState: phase === 'question' ? 'running' : 'paused',
          }}
          onAnimationEnd={() => answer(null)}
        />
      </div>

      <p className="meta">
        {question.category} · {question.difficulty}
      </p>
      <h2 className="prompt">{question.prompt}</h2>
      {question.code && (
        <pre className="code">
          <code>{question.code}</code>
        </pre>
      )}

      <div className="options">
        {question.options.map((option, index) => (
          <button
            key={index}
            className={optionClass(index)}
            onClick={() => answer(index)}
            disabled={phase !== 'question'}
          >
            <span className="option-key">{index + 1}</span>
            {option}
          </button>
        ))}
      </div>

      {answered && (
        <div className="result">
          <p className={result.correct ? 'verdict good' : 'verdict bad'}>
            {result.correct ? 'correct!' : result.timed_out ? "time's up" : 'nope'}
            <span className="time"> {(result.response_ms / 1000).toFixed(1)}s</span>
          </p>
          <p className="explanation">{result.explanation}</p>
          <button className="link" onClick={loadNext}>
            press enter for next →
          </button>
        </div>
      )}
    </div>
  )
}