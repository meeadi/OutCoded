// What we remember about each answer in a session.
export type Round = {
  correct: boolean
  timedOut: boolean
  ms: number
}

export const SESSION_LENGTH = 10

// Correct answers in a row at the end of the list.
export function currentStreak(rounds: Round[]): number {
  let streak = 0
  for (let i = rounds.length - 1; i >= 0 && rounds[i].correct; i--) streak++
  return streak
}

export function bestStreak(rounds: Round[]): number {
  let best = 0
  let run = 0
  for (const round of rounds) {
    run = round.correct ? run + 1 : 0
    best = Math.max(best, run)
  }
  return best
}

// Rank letter plus a line of trash talk, based on how many you got right.
export function rankFor(correct: number, total: number): { letter: string; line: string } {
  const score = total === 0 ? 0 : correct / total
  if (score === 1) return { letter: 'S', line: 'flawless. go touch grass.' }
  if (score >= 0.8) return { letter: 'A', line: 'cracked. genuinely.' }
  if (score >= 0.6) return { letter: 'B', line: 'solid. the compiler respects you.' }
  if (score >= 0.4) return { letter: 'C', line: 'mid. but honest mid.' }
  if (score >= 0.2) return { letter: 'D', line: 'you got outcoded.' }
  return { letter: 'F', line: 'did you read the questions or just vibe?' }
}

// Bonus stamp for a right answer: in the last 3 seconds, or in under 2.5 seconds.
export function stampFor(correct: boolean, responseMs: number, timeLimitS: number): string | null {
  if (!correct) return null
  if (timeLimitS * 1000 - responseMs < 3000) return 'clutch!'
  if (responseMs < 2500) return 'too easy'
  return null
}