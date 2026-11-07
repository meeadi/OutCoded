import { useEffect, useState } from 'react'

const WORD = 'outcoded'
const SPLIT = 3 // "out" in the text color, "coded" in the accent

type Props = {
  animate: boolean // false: show the whole word at once (fx off)
  loop?: boolean // type, pause, delete, type again (for loading screens)
  onDone?: () => void // called once the word is fully typed (not when looping)
  className?: string
}

// "outcoded" typed out letter by letter, with a blinking cursor.
export default function TypedLogo({ animate, loop = false, onDone, className = '' }: Props) {
  const [count, setCount] = useState(animate ? 0 : WORD.length)
  const [deleting, setDeleting] = useState(false)
  const typing = animate && (deleting || count < WORD.length)

  useEffect(() => {
    if (!animate) return
    let delay: number
    let step: () => void
    if (!deleting && count < WORD.length) {
      // A little randomness makes it feel like a person typing.
      delay = count === 0 ? 350 : 70 + Math.random() * 90
      step = () => setCount((c) => c + 1)
    } else if (!deleting) {
      if (!loop) {
        onDone?.()
        return
      }
      delay = 1200
      step = () => setDeleting(true)
    } else if (count > 0) {
      delay = 40
      step = () => setCount((c) => c - 1)
    } else {
      delay = 350
      step = () => setDeleting(false)
    }
    const timer = setTimeout(step, delay)
    return () => clearTimeout(timer)
  }, [animate, loop, count, deleting, onDone])

  return (
    <span className={`typed-logo ${className}`} role="img" aria-label={WORD}>
      <span aria-hidden="true">
        {WORD.slice(0, Math.min(count, SPLIT))}
        <span className="coded">{WORD.slice(SPLIT, count)}</span>
        <span className={`caret ${typing ? 'solid' : ''}`} />
      </span>
    </span>
  )
}