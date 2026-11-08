import { describe, expect, it } from 'vitest'
import { formatDateTime, formatMXN } from '~/utils/money'

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

describe('formatDateTime', () => {
  it('p13_v14 formats a timestamp in the store timezone, with its time', () => {
    // 18:30 UTC is 12:30 in Mexico City (UTC-6 in November).
    expect(formatDateTime('2026-11-15T18:30:00Z')).toMatch(
      /^15 de noviembre de 2026(,| a las) 12:30/,
    )
    // Late evening UTC falls on the next calendar day in UTC but the same day in the store.
    expect(formatDateTime('2026-11-16T03:15:00Z')).toMatch(
      /^15 de noviembre de 2026(,| a las) 9:15/,
    )
  })
})
