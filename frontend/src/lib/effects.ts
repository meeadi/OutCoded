import confetti from 'canvas-confetti'

export function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

// Read the current theme's colors so confetti always matches the theme.
function themeColors(): string[] {
  const style = getComputedStyle(document.documentElement)
  return ['--accent', '--correct', '--text'].map((name) => style.getPropertyValue(name).trim())
}

// Restart a CSS animation by removing and re-adding its class.
function replay(selector: string, className: string) {
  const element = document.querySelector<HTMLElement>(selector)
  if (!element) return
  element.classList.remove(className)
  void element.offsetWidth // forces the browser to notice the class was removed
  element.classList.add(className)
}

// Rewards grow with the streak: nothing special at 1-2, confetti at 3, a big burst at 5+.
export function celebrate(streak: number) {
  if (streak < 3) return
  const big = streak >= 5
  confetti({
    particleCount: big ? 160 : 70,
    spread: big ? 100 : 60,
    startVelocity: big ? 45 : 30,
    origin: { y: 0.75 },
    colors: themeColors(),
    disableForReducedMotion: true,
  })
}

// A small pop for any right answer.
export function sparkle() {
  confetti({
    particleCount: 30,
    spread: 50,
    startVelocity: 22,
    origin: { y: 0.75 },
    colors: themeColors(),
    disableForReducedMotion: true,
  })
}

// The big one: cannons from both bottom corners, then a burst in the middle.
export function victory() {
  const colors = themeColors()
  const cannon = {
    particleCount: 90,
    spread: 60,
    startVelocity: 55,
    colors,
    disableForReducedMotion: true,
  }
  confetti({ ...cannon, angle: 60, origin: { x: 0, y: 0.9 } })
  confetti({ ...cannon, angle: 120, origin: { x: 1, y: 0.9 } })
  setTimeout(() => {
    confetti({
      particleCount: 140,
      spread: 120,
      startVelocity: 40,
      origin: { y: 0.6 },
      colors,
      disableForReducedMotion: true,
    })
  }, 250)
}

export function punish() {
  replay('.app', 'shake')
  replay('.flash', 'flash-on')
  navigator.vibrate?.(120) // Android only; iPhones ignore this
}