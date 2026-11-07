import { useEffect, useState } from 'react'
import TypedLogo from './TypedLogo'

const SLOW_MS = 5000

// The logo types itself on repeat while we wait. If it takes a while, the
// server is probably waking up (free hosting sleeps when nobody's playing).
export default function LoadingScreen({ animate }: { animate: boolean }) {
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_MS)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="loading-screen" role="status">
      <TypedLogo animate={animate} loop className="loading-logo" />
      <p className={`loading-note ${slow ? 'show' : ''}`}>
        waking the server up… free hosting naps when nobody's playing.
        <br />
        this can take up to a minute.
      </p>
    </div>
  )
}