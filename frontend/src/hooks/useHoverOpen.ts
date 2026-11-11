import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

// Only devices with a real mouse get hover-to-open. Phones use taps instead.
export function canHover(): boolean {
  return window.matchMedia('(hover: hover) and (pointer: fine)').matches
}

// Open/close state for menus that open on hover (with a small delay, so passing
// the mouse over them by accident doesn't pop them open) and on click or tap.
export function useHoverOpen(openDelay = 120, closeDelay = 300) {
  const [open, setOpenState] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const setOpen = useCallback((value: boolean) => {
    window.clearTimeout(timer.current)
    setOpenState(value)
  }, [])

  const onMouseEnter = useCallback(() => {
    if (!canHover()) return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpenState(true), openDelay)
  }, [openDelay])

  const onMouseLeave = useCallback(() => {
    if (!canHover()) return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpenState(false), closeDelay)
  }, [closeDelay])

  return useMemo(
    () => ({ open, setOpen, hover: { onMouseEnter, onMouseLeave } }),
    [open, setOpen, onMouseEnter, onMouseLeave],
  )
}