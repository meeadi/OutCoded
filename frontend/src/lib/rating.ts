// Ratings stay "provisional" until the system is fairly sure about them
// (a rating deviation above 110, the same cut-off Lichess uses).
export const PROVISIONAL_RD = 110

export function formatRating(rating: number, rd: number): string {
  return `${Math.round(rating)}${rd > PROVISIONAL_RD ? '?' : ''}`
}