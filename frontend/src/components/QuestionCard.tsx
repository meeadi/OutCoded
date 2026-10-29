import type { Question } from '../lib/api'

type Props = {
  question: Question
  roundKey: string // changes for every new question, which restarts the timer
  running: boolean // the timer drains while this is true
  picked: number | null // position the player chose, if any
  correctChoice: number | null // set once the answer is revealed
  disabled: boolean
  onAnswer: (choice: number | null) => void // null = time ran out
}

// The timer, question and options. Shared by solo rush and Code-Off.
export default function QuestionCard({
  question,
  roundKey,
  running,
  picked,
  correctChoice,
  disabled,
  onAnswer,
}: Props) {
  const playState = running ? 'running' : 'paused'
  const panicAt = Math.max(0, question.time_limit_s - 5)

  function optionClass(index: number) {
    if (correctChoice !== null) {
      if (index === correctChoice) return 'option correct'
      if (index === picked) return 'option wrong'
      return 'option faded'
    }
    if (picked !== null) return index === picked ? 'option locked' : 'option faded'
    return 'option'
  }

  return (
    <>
      {/* The key restarts the animations for every new question.
          In the last 5 seconds the bar turns red and starts to glow. */}
      <div
        key={roundKey}
        className="timer"
        style={{ animationDelay: `${panicAt}s`, animationPlayState: playState }}
      >
        <div
          className="timer-fill"
          style={{
            animationDuration: `${question.time_limit_s}s, 0.3s`,
            animationDelay: `0s, ${panicAt}s`,
            animationPlayState: `${playState}, ${playState}`,
          }}
          onAnimationEnd={(e) => {
            if (e.animationName === 'drain') onAnswer(null)
          }}
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
            onClick={() => onAnswer(index)}
            disabled={disabled}
          >
            <span className="option-key">{index + 1}</span>
            {option}
          </button>
        ))}
      </div>
    </>
  )
}