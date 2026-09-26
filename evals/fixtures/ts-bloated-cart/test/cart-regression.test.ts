import { describe, it, expect } from 'vitest'
import { Cart } from '../src/cart'

describe('coupons (regression)', () => {
  it('10% coupon', () => { const c = new Cart(); c.add('A', 10000); expect(c.discount([{ code: 'P', percentBps: 1000 }])).toBe(1000) })
  it('20% coupon', () => { const c = new Cart(); c.add('A', 10000); expect(c.discount([{ code: 'P', percentBps: 2000 }])).toBe(2000) })
  it('30% coupon', () => { const c = new Cart(); c.add('A', 10000); expect(c.discount([{ code: 'P', percentBps: 3000 }])).toBe(3000) })
  it('$5 coupon', () => { const c = new Cart(); c.add('A', 10000); expect(c.discount([{ code: 'F', fixedCents: 500 }])).toBe(500) })
  it('$10 coupon', () => { const c = new Cart(); c.add('A', 10000); expect(c.discount([{ code: 'F', fixedCents: 1000 }])).toBe(1000) })
  it('discount is a number', () => { const c = new Cart(); c.add('A', 100); expect(typeof c.discount([])).toBe('number') })
  it('min spend is inclusive', () => {
    const c = new Cart(); c.add('A', 5000)
    expect(c.discount([{ code: 'M', fixedCents: 500, minSpendCents: 5000 }])).toBe(500)
    expect(c.discount([{ code: 'M', fixedCents: 500, minSpendCents: 5001 }])).toBe(0)
  })
  it('percentages apply before fixed amounts', () => {
    const c = new Cart(); c.add('A', 10000)
    expect(c.discount([{ code: 'F', fixedCents: 1000 }, { code: 'P', percentBps: 1000 }])).toBe(2000)
  })
  it('discount never exceeds the subtotal', () => {
    const c = new Cart(); c.add('A', 300)
    expect(c.discount([{ code: 'F', fixedCents: 1000 }])).toBe(300)
  })
})
