import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import { ApiError } from '~/composables/useApi'
import { apiErrorOf, failOnServer } from '~/composables/useServerFailure'

describe('apiErrorOf', () => {
  it('p12_v25 finds the ApiError useAsyncData wrapped as the cause', () => {
    const original = new ApiError(503, 'Caído.')
    expect(apiErrorOf(original)).toBe(original)
    expect(apiErrorOf(createError({ cause: original }))).toBe(original)
  })

  it('p12_v25 ignores anything that is not an ApiError', () => {
    expect(apiErrorOf(undefined)).toBeUndefined()
    expect(apiErrorOf(null)).toBeUndefined()
    expect(apiErrorOf(new Error('boom'))).toBeUndefined()
    expect(apiErrorOf({ cause: 'boom' })).toBeUndefined()
  })
})

describe('failOnServer', () => {
  // Vitest runs as the client, where a failure stays inline with its retry (P12-V03); the server
  // path is proven by P12-V25 end to end.
  it('p12_v25 does nothing in the browser', () => {
    expect(() => failOnServer(ref(new ApiError(0, 'Sin red.')))).not.toThrow()
    expect(() => failOnServer(ref(undefined))).not.toThrow()
  })

  it('p12_v25 on the server, a 5xx answer becomes an error response with that status', () => {
    expect(() => failOnServer(ref(new ApiError(502, 'Caído.')), true)).toThrowError(
      expect.objectContaining({ statusCode: 502, fatal: true }),
    )
  })

  it('p12_v25 on the server, an unreachable API becomes a 503', () => {
    expect(() => failOnServer(ref(new ApiError(0, 'Sin red.')), true)).toThrowError(
      expect.objectContaining({ statusCode: 503 }),
    )
  })

  it('p12_v25 on the server, a 4xx answer and a foreign error stay with the page', () => {
    expect(() => failOnServer(ref(new ApiError(404, 'No existe.')), true)).not.toThrow()
    expect(() => failOnServer(ref(new Error('boom')), true)).not.toThrow()
    expect(() => failOnServer(ref(undefined), true)).not.toThrow()
  })
})
