import { describe, it, expect } from 'vitest'
import { roundHalfUp, percentOf } from '../src/money'

describe('money', () => {
  it('rounds 1.4 down', () => { expect(roundHalfUp(1.4)).toBe(1) })
  it('rounds 2.4 down', () => { expect(roundHalfUp(2.4)).toBe(2) })
  it('rounds 3.4 down', () => { expect(roundHalfUp(3.4)).toBe(3) })
  it('rounds half up, not to even', () => {
    expect(roundHalfUp(2.5)).toBe(3)
    expect(roundHalfUp(0.5)).toBe(1)
  })
  it('percentOf 10%', () => { expect(percentOf(1000, 1000)).toBe(100) })
  it('percentOf 5%', () => { expect(percentOf(1000, 500)).toBe(50) })
  it('percentOf rounds half-cents up', () => { expect(percentOf(25, 1000)).toBe(3) })
  it('is deterministic', () => { expect(percentOf(333, 725)).toBe(percentOf(333, 725)) })
})
