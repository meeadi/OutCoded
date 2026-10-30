import { useEffect, useState } from 'react'
import { wsUrl } from '../lib/api'
import { supabase } from '../lib/supabase'

type QueueMessage =
  | { type: 'queued'; rating: number; in_queue: number }
  | { type: 'searching'; waited_s: number; range: number | null; in_queue: number }
  | { type: 'matched'; code: string; opponent: string; opponent_rating: number }
  | { type: 'error'; message: string }

type Props = {
  onMatched: (code: string) => void
  onCancel: () => void
}

// Ranked matchmaking: wait here until the server pairs us with someone.
export default function Queue({ onMatched, onCancel }: Props) {
  const [waited, setWaited] = useState(0)
  const [range, setRange] = useState<number | null>(100)
  const [inQueue, setInQueue] = useState(1)
  const [found, setFound] = useState<{ opponent: string; rating: number } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let done = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const ws = new WebSocket(wsUrl('/ws/queue'))

    ws.onopen = async () => {
      const { data } = await supabase.auth.getSession()
      ws.send(JSON.stringify({ type: 'auth', token: data.session?.access_token ?? '' }))
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data) as QueueMessage
      switch (message.type) {
        case 'queued':
          setInQueue(message.in_queue)
          break
        case 'searching':
          setWaited(message.waited_s)
          setRange(message.range)
          setInQueue(message.in_queue)
          break
        case 'matched':
          done = true
          setFound({ opponent: message.opponent, rating: message.opponent_rating })
          ws.close()
          // A short beat to read who you got, then into the match.
          timer = setTimeout(() => onMatched(message.code), 1200)
          break
        case 'error':
          done = true
          setError(message.message)
          break
      }
    }

    ws.onclose = () => {
      if (!done) setError('Lost connection to matchmaking.')
    }

    // Leaving this screen takes you out of the queue.
    return () => {
      done = true
      clearTimeout(timer)
      ws.close()
    }
  }, [onMatched])

  // Esc cancels.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  if (error) {
    return (
      <div className="codeoff-center">
        <p className="auth-message">{error}</p>
        <button className="link" onClick={onCancel}>
          ← back to menu
        </button>
      </div>
    )
  }

  if (found) {
    return (
      <div className="codeoff-center">
        <p className="auth-title">opponent found</p>
        <p className="found-name">{found.opponent}</p>
        <p className="picker-hint">rated {found.rating}</p>
      </div>
    )
  }

  const minutes = Math.floor(waited / 60)
  const seconds = String(waited % 60).padStart(2, '0')

  return (
    <div className="codeoff-center">
      <h2 className="auth-title">ranked</h2>
      <div className="radar" aria-hidden="true" />
      <p className="waiting-dots">
        finding an opponent<span>.</span>
        <span>.</span>
        <span>.</span>
      </p>
      <p className="queue-stats">
        {minutes}:{seconds} · {range === null ? 'any rating' : `±${range}`} · {inQueue}{' '}
        searching
      </p>
      <button className="link" onClick={onCancel}>
        cancel (esc)
      </button>
    </div>
  )
}