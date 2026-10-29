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

export function punish() {
  replay('.app', 'shake')
  replay('.flash', 'flash-on')
  navigator.vibrate?.(120) // Android only; iPhones ignore this
}