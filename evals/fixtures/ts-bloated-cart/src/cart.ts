import { lineTotal } from './pricing'
import { percentOf } from './money'

export interface Coupon { code: string; percentBps?: number; fixedCents?: number; minSpendCents?: number }

export const TAX_BPS: Record<string, number> = { CA: 725, NY: 400, TX: 625, OR: 0 }
export const MAX_LINES = 50

export class Cart {
  private lines = new Map<string, { unitCents: number; quantity: number }>()

  add(sku: string, unitCents: number, quantity = 1): void {
    const line = this.lines.get(sku)
    if (line) {
      if (line.unitCents !== unitCents) throw new Error('price mismatch for ' + sku)
      line.quantity += quantity
      return
    }
    if (this.lines.size >= MAX_LINES) throw new Error('cart is full')
    this.lines.set(sku, { unitCents, quantity })
  }

  remove(sku: string): void {
    this.lines.delete(sku)
  }

  subtotal(): number {
    let sum = 0
    for (const { unitCents, quantity } of this.lines.values()) sum += lineTotal(unitCents, quantity)
    return sum
  }

  discount(coupons: Coupon[]): number {
    const sub = this.subtotal()
    let remaining = sub
    const eligible = coupons.filter((c) => sub >= (c.minSpendCents ?? 0))
    for (const c of eligible.filter((c) => c.percentBps)) remaining -= percentOf(remaining, c.percentBps!)
    for (const c of eligible.filter((c) => c.fixedCents)) remaining -= c.fixedCents!
    return Math.min(sub, sub - Math.max(0, remaining))
  }

  total(region: string, coupons: Coupon[] = []): number {
    const rate = TAX_BPS[region]
    if (rate === undefined) throw new Error('unknown region ' + region)
    const net = this.subtotal() - this.discount(coupons)
    return net + percentOf(net, rate)
  }

  get size(): number {
    return this.lines.size
  }
}
