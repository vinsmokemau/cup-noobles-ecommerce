import { describe, expect, it } from 'vitest'
import { toApiError } from '~/composables/useApi'

// The storefront learns pre-launch mode from the 503 body (G32, ADR-0038).
describe('toApiError prelaunch', () => {
  it('p12_v28 reads {"prelaunch": true} on a 503 as pre-launch mode', () => {
    const error = toApiError({ response: { status: 503, _data: { prelaunch: true } } })
    expect(error.status).toBe(503)
    expect(error.prelaunch).toBe(true)
  })

  it('p12_v28 a plain 503, or the flag on another status, is not pre-launch mode', () => {
    expect(toApiError({ status: 503 }).prelaunch).toBe(false)
    expect(toApiError({ status: 503, data: { prelaunch: false } }).prelaunch).toBe(false)
    expect(toApiError({ status: 500, data: { prelaunch: true } }).prelaunch).toBe(false)
    expect(toApiError(undefined).prelaunch).toBe(false)
  })
})
