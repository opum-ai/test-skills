/** All amounts are integer cents. */
export function roundHalfUp(cents: number): number {
  return Math.floor(cents + 0.5)
}

export function percentOf(cents: number, basisPoints: number): number {
  return roundHalfUp((cents * basisPoints) / 10000)
}
