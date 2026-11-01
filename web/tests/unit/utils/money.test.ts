import { describe, expect, it } from 'vitest'
import { formatMXN } from '~/utils/money'

describe('formatMXN', () => {
  it.each([
    [123400, '$1,234.00'],
    [0, '$0.00'],
    [5, '$0.05'],
    [100000000, '$1,000,000.00'],
  ])('p12_v09 formatMXN %i → %s', (cents, expected) => {
    expect(formatMXN(cents)).toBe(expected)
  })

  it.each([12.5, Number.NaN, Number.POSITIVE_INFINITY])(
    'p12_v09 formatMXN throws on non-integer input %s',
    (cents) => {
      expect(() => formatMXN(cents)).toThrow(TypeError)
    },
  )
})
