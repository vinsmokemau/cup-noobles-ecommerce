import { describe, expect, it } from 'vitest'
import { toApiError } from '~/composables/useApi'
import { lineErrorMessage, parseCheckoutConflict } from '~/utils/checkoutConflict'

const line = (over: Record<string, unknown> = {}) => ({
  variant_public_id: '11111111-1111-4111-8111-111111111111',
  sku: 'SKU-1',
  code: 'insufficient_stock' as const,
  requested: 3,
  available: 2,
  ...over,
})

describe('parseCheckoutConflict', () => {
  it('p13_v18 reads the per-line errors of a 409', () => {
    const conflict = parseCheckoutConflict({ code: 'lines_unavailable', line_errors: [line()] })
    expect(conflict).toEqual({ kind: 'lines', lineErrors: [line()] })
  })

  it('p13_v19 reads the fresh totals of a total_changed 409', () => {
    const totals = {
      subtotal_cents: 100,
      shipping_cents: 50,
      discount_cents: 0,
      total_cents: 150,
      tax_included_cents: 20,
    }
    expect(parseCheckoutConflict({ code: 'total_changed', totals })).toEqual({
      kind: 'total',
      totals,
    })
  })

  it('returns null for anything else', () => {
    expect(parseCheckoutConflict(undefined)).toBeNull()
    expect(parseCheckoutConflict('x')).toBeNull()
    expect(parseCheckoutConflict({ code: 'other' })).toBeNull()
    expect(parseCheckoutConflict({ code: 'lines_unavailable' })).toBeNull()
    expect(parseCheckoutConflict({ code: 'total_changed', totals: 5 })).toBeNull()
  })

  it('arrives through ApiError.body from a failed fetch', () => {
    const payload = { code: 'lines_unavailable', line_errors: [line()] }
    const error = toApiError({ response: { status: 409, _data: payload } })
    expect(error.status).toBe(409)
    expect(parseCheckoutConflict(error.body)).toEqual({ kind: 'lines', lineErrors: [line()] })
  })
})

describe('lineErrorMessage', () => {
  it('p13_v18 says how many are left', () => {
    expect(lineErrorMessage(line(), 'Sudadera')).toBe('Solo quedan 2 de Sudadera.')
    expect(lineErrorMessage(line({ available: 1 }), 'Sudadera')).toBe('Solo queda 1 de Sudadera.')
  })

  it('says when none are left or the product is gone', () => {
    expect(lineErrorMessage(line({ available: 0 }), 'Sudadera')).toBe(
      'Ya no hay existencias de Sudadera.',
    )
    expect(lineErrorMessage(line({ available: null }), 'Sudadera')).toBe(
      'Ya no hay existencias de Sudadera.',
    )
    expect(lineErrorMessage(line({ code: 'unavailable' }), 'Sudadera')).toBe(
      'Sudadera ya no está disponible.',
    )
  })

  it('p13_v24 explains a purchase limit and how many are still allowed', () => {
    const limited = (available: number | null) =>
      line({ code: 'purchase_limit_exceeded', available })
    expect(lineErrorMessage(limited(2), 'Sudadera')).toBe(
      'Sudadera tiene un límite de compra por cliente: solo puedes llevar 2 más. Ajusta la cantidad e inténtalo de nuevo.',
    )
    expect(lineErrorMessage(limited(0), 'Sudadera')).toBe(
      'Ya alcanzaste el límite de compra por cliente de Sudadera. Quítalo de tu carrito para continuar.',
    )
    expect(lineErrorMessage(limited(null), 'Sudadera')).toContain('Ya alcanzaste el límite')
  })
})
