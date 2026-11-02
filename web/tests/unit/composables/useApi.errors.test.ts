import { describe, expect, it } from 'vitest'
import { ApiError, toApiError } from '~/composables/useApi'

// Branch coverage for `toApiError`; the T12.2 tests (p12_v07) cover the main DRF shapes.
describe('toApiError', () => {
  it('p12_v07 returns an ApiError unchanged', () => {
    const original = new ApiError(418, 'Soy una tetera.')
    expect(toApiError(original)).toBe(original)
  })

  it('p12_v07 treats a missing failure as a network error', () => {
    expect(toApiError(undefined).status).toBe(0)
    expect(toApiError(null).status).toBe(0)
  })

  it('p12_v07 reads the status and payload from the response', () => {
    const error = toApiError({ response: { status: 400, _data: { detail: 'Mal.' } } })
    expect(error.status).toBe(400)
    expect(error.detail).toBe('Mal.')
  })

  it('p12_v07 falls back to statusCode and status', () => {
    expect(toApiError({ statusCode: 502 }).status).toBe(502)
    expect(toApiError({ status: 503 }).status).toBe(503)
  })

  it('p12_v07 reads a string or list payload as the detail', () => {
    expect(toApiError({ status: 400, data: 'Texto.' }).detail).toBe('Texto.')
    expect(toApiError({ status: 400, data: ['Uno.', 'Dos.', 3] }).detail).toBe('Uno. Dos.')
  })

  it('p12_v07 joins several messages and skips empty or non-text fields', () => {
    const error = toApiError({
      status: 400,
      data: { detail: ['A.', 'B.'], name: [], age: 5, email: 'Requerido.' },
    })
    expect(error.detail).toBe('A. B.')
    expect(error.fieldErrors).toEqual({ email: ['Requerido.'] })
  })

  it('p12_v07 uses the generic message when the payload has no text', () => {
    expect(toApiError({ status: 500, data: {} }).detail).toMatch(/Algo salió mal/)
    expect(toApiError({ status: 500, data: 42 }).detail).toMatch(/Algo salió mal/)
  })
})
