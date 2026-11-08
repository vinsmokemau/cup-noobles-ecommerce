import { describe, expect, it } from 'vitest'
import { isClosed, isPaidOrLater, type OrderState } from '~/utils/orderLanding'

describe('order landing states', () => {
  it.each<[OrderState, boolean]>([
    ['draft', false],
    ['pending_payment', false],
    ['cancelled', false],
    ['expired', false],
    ['paid', true],
    ['awaiting_stock', true],
    ['preparing', true],
    ['shipped', true],
    ['completed', true],
  ])('p13_v13 %s is paid or later: %s', (state, expected) => {
    expect(isPaidOrLater(state)).toBe(expected)
  })

  it('p13_v13 only a cancelled or expired order is closed', () => {
    expect(isClosed('cancelled')).toBe(true)
    expect(isClosed('expired')).toBe(true)
    expect(isClosed('pending_payment')).toBe(false)
    expect(isClosed('paid')).toBe(false)
  })
})
