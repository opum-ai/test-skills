import { describe, it, expect, vi } from 'vitest'
import * as money from '../src/money'
import { lineTotal } from '../src/pricing'

describe('lineTotal (extra)', () => {
  it('ten units get 5% off', () => { expect(lineTotal(1000, 10)).toBe(9500) })
  it('twenty units get 5% off', () => { expect(lineTotal(1000, 20)).toBe(19000) })
  it('fifty units get 10% off', () => { expect(lineTotal(1000, 50)).toBe(45000) })
  it('hundred units get 15% off', () => { expect(lineTotal(1000, 100)).toBe(85000) })
  it('calls percentOf exactly once', () => {
    const spy = vi.spyOn(money, 'percentOf')
    lineTotal(1000, 10)
    expect(spy).toHaveBeenCalledTimes(1)
    spy.mockRestore()
  })
  it('result is not null', () => { expect(lineTotal(1000, 1)).not.toBeNull() })
})
