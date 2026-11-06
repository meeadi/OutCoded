import { useCallback, useEffect, useMemo, useRef } from 'react'

// Measures how long the tab is hidden or the window is unfocused.
// reset() when a question appears; read() when the player answers.
// It's sent to the server as a hint for cheat detection, nothing more.
export function useAwayTimer() {
  const awayMs = useRef(0)
  const leftAt = useRef<number | null>(null)

  useEffect(() => {
    function leave() {
      if (leftAt.current === null) leftAt.current = performance.now()
    }
    function comeBack() {
      if (leftAt.current !== null) {
        awayMs.current += performance.now() - leftAt.current
        leftAt.current = null
      }
    }
    function onVisibility() {
      if (document.hidden) leave()
      else comeBack()
    }
    window.addEventListener('blur', leave)
    window.addEventListener('focus', comeBack)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('blur', leave)
      window.removeEventListener('focus', comeBack)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  const reset = useCallback(() => {
    awayMs.current = 0
    leftAt.current = document.hasFocus() ? null : performance.now()
  }, [])

  const read = useCallback(() => {
    const ongoing = leftAt.current === null ? 0 : performance.now() - leftAt.current
    return Math.round(awayMs.current + ongoing)
  }, [])

  // The same object every render, so it's safe to list as a hook dependency.
  return useMemo(() => ({ reset, read }), [reset, read])
}