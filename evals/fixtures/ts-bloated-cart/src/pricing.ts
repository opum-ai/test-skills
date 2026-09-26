import { percentOf } from './money'

export const VOLUME_TIERS: Array<[number, number]> = [
  [100, 1500],
  [50, 1000],
  [10, 500],
]

/** Discount in basis points for a line quantity. */
export function volumeDiscountBps(quantity: number): number {
  for (const [minQty, bps] of VOLUME_TIERS) {
    if (quantity >= minQty) return bps
  }
  return 0
}

export function lineTotal(unitCents: number, quantity: number): number {
  if (!Number.isInteger(quantity) || quantity <= 0) throw new Error('quantity must be a positive integer')
  if (quantity > 999) throw new Error('quantity too large')
  const gross = unitCents * quantity
  return gross - percentOf(gross, volumeDiscountBps(quantity))
}
