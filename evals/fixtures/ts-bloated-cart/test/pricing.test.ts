import { describe, it, expect } from 'vitest'
import { lineTotal, volumeDiscountBps } from '../src/pricing'

describe('lineTotal', () => {
  it('one unit', () => { expect(lineTotal(1000, 1)).toBe(1000) })
  it('two units', () => { expect(lineTotal(1000, 2)).toBe(2000) })
  it('three units', () => { expect(lineTotal(1000, 3)).toBe(3000) })
  it('four units', () => { expect(lineTotal(1000, 4)).toBe(4000) })
  it('five units', () => { expect(lineTotal(1000, 5)).toBe(5000) })
  it('six units', () => { expect(lineTotal(1000, 6)).toBe(6000) })
  it('seven units', () => { expect(lineTotal(1000, 7)).toBe(7000) })
  it('returns a number', () => { expect(typeof lineTotal(500, 2)).toBe('number') })
  it('does not crash for a normal line', () => { lineTotal(250, 3) })
  it('rejects zero quantity', () => { expect(() => lineTotal(100, 0)).toThrow() })
  it('rejects negative quantity', () => { expect(() => lineTotal(100, -1)).toThrow() })
  it('rejects fractional quantity', () => { expect(() => lineTotal(100, 1.5)).toThrow() })
  it('accepts 999 units and rejects 1000', () => {
    expect(lineTotal(100, 999)).toBe(84915)
    expect(() => lineTotal(100, 1000)).toThrow('quantity too large')
  })
})

describe('volumeDiscountBps', () => {
  it('no discount for 1', () => { expect(volumeDiscountBps(1)).toBe(0) })
  it('no discount for 5', () => { expect(volumeDiscountBps(5)).toBe(0) })
  it('no discount for 8', () => { expect(volumeDiscountBps(8)).toBe(0) })
  it('5% at 20', () => { expect(volumeDiscountBps(20)).toBe(500) })
  it('5% at 30', () => { expect(volumeDiscountBps(30)).toBe(500) })
  it('10% at 60', () => { expect(volumeDiscountBps(60)).toBe(1000) })
  it('15% at 200', () => { expect(volumeDiscountBps(200)).toBe(1500) })
  it('tier boundaries are inclusive', () => {
    expect(volumeDiscountBps(9)).toBe(0)
    expect(volumeDiscountBps(10)).toBe(500)
    expect(volumeDiscountBps(49)).toBe(500)
    expect(volumeDiscountBps(50)).toBe(1000)
    expect(volumeDiscountBps(99)).toBe(1000)
    expect(volumeDiscountBps(100)).toBe(1500)
  })
})
