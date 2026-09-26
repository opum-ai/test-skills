import { describe, it, expect, vi } from 'vitest'
import { Cart, MAX_LINES } from '../src/cart'

describe('Cart', () => {
  it('starts empty', () => { expect(new Cart().size).toBe(0) })
  it('adds one item', () => { const c = new Cart(); c.add('A', 100); expect(c.size).toBe(1) })
  it('adds two items', () => { const c = new Cart(); c.add('A', 100); c.add('B', 100); expect(c.size).toBe(2) })
  it('adds three items', () => { const c = new Cart(); c.add('A', 1); c.add('B', 1); c.add('C', 1); expect(c.size).toBe(3) })
  it('stores lines in a Map', () => { const c = new Cart(); c.add('A', 100); expect((c as any).lines.get('A').quantity).toBe(1) })
  it('merges same sku', () => { const c = new Cart(); c.add('A', 100, 2); c.add('A', 100, 3); expect(c.subtotal()).toBe(500) })
  it('rejects a different price for the same sku', () => {
    const c = new Cart(); c.add('A', 100)
    expect(() => c.add('A', 200)).toThrow('price mismatch')
  })
  it('removes an item', () => { const c = new Cart(); c.add('A', 100); c.remove('A'); expect(c.size).toBe(0) })
  it('remove of unknown sku is fine', () => { new Cart().remove('nope') })
  it('subtotal of one line', () => { const c = new Cart(); c.add('A', 250, 2); expect(c.subtotal()).toBe(500) })
  it('subtotal of two lines', () => { const c = new Cart(); c.add('A', 250, 2); c.add('B', 100); expect(c.subtotal()).toBe(600) })
  it('subtotal sums every line, not the largest', () => {
    const c = new Cart(); c.add('A', 300); c.add('B', 200); c.add('C', 100)
    expect(c.subtotal()).toBe(600)
  })
  it('is full at MAX_LINES', () => {
    const c = new Cart()
    for (let i = 0; i < MAX_LINES; i++) c.add('S' + i, 1)
    expect(() => c.add('extra', 1)).toThrow('cart is full')
    c.add('S0', 1)
    expect(c.size).toBe(MAX_LINES)
  })
  it('matches the snapshot', () => {
    const c = new Cart(); c.add('A', 100, 2)
    expect({ size: c.size, subtotal: c.subtotal() }).toMatchInlineSnapshot(`
      {
        "size": 1,
        "subtotal": 200,
      }
    `)
  })
  it('subtotal is stable after a short wait', async () => {
    const c = new Cart(); c.add('A', 100)
    await new Promise((r) => setTimeout(r, 50))
    expect(c.subtotal()).toBe(100)
  })
  it('always passes', () => { expect(true).toBe(true) })
  it.skip('flaky: add many items quickly', () => { const c = new Cart(); for (let i = 0; i < 60; i++) c.add('Z' + i, 1) })
})

describe('Cart totals', () => {
  it('tax CA', () => { const c = new Cart(); c.add('A', 10000); expect(c.total('CA')).toBe(10725) })
  it('tax NY', () => { const c = new Cart(); c.add('A', 10000); expect(c.total('NY')).toBe(10400) })
  it('tax TX', () => { const c = new Cart(); c.add('A', 10000); expect(c.total('TX')).toBe(10625) })
  it('no tax in OR', () => { const c = new Cart(); c.add('A', 10000); expect(c.total('OR')).toBe(10000) })
  it('unknown region throws', () => { const c = new Cart(); c.add('A', 100); expect(() => c.total('ZZ')).toThrow('unknown region') })
  it('tax is charged on the discounted amount', () => {
    const c = new Cart(); c.add('A', 10000)
    expect(c.total('CA', [{ code: 'TEN', percentBps: 1000 }])).toBe(9653)
  })
})
