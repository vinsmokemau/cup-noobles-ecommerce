import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { ApiError, useApi } from '~/composables/useApi'

const requestHeaders = vi.hoisted(() => vi.fn(() => ({}) as Record<string, string>))
mockNuxtImport('useRequestHeaders', () => requestHeaders)

const fetchMock = vi.hoisted(() => vi.fn())
mockNuxtImport('$fetch', () => fetchMock)

function failure(status: number, data?: unknown) {
  return Object.assign(new Error(`${status}`), { status, statusCode: status, data })
}

beforeEach(() => {
  fetchMock.mockReset().mockResolvedValue({ ok: true })
  requestHeaders.mockReturnValue({})
  document.cookie = 'csrftoken=tok123; path=/'
})

afterEach(() => {
  document.cookie = 'csrftoken=; path=/; max-age=0'
})

function sentHeaders(): Record<string, string> {
  return fetchMock.mock.calls[0]![1].headers
}

describe('useApi', () => {
  it('p12_v05 csrf header on unsafe methods only', async () => {
    const api = useApi()
    for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
      fetchMock.mockClear()
      await api('/cart/', { method })
      expect(sentHeaders()['X-CSRFToken']).toBe('tok123')
    }
    for (const method of ['GET', 'HEAD', undefined]) {
      fetchMock.mockClear()
      await api('/cart/', { method })
      expect(sentHeaders()).not.toHaveProperty('X-CSRFToken')
    }
  })

  it('p12_v06 forwards cookies during SSR', async () => {
    requestHeaders.mockReturnValue({ cookie: 'sessionid=abc' })
    await useApi()('/me/')
    expect(requestHeaders).toHaveBeenCalledWith(['cookie'])
    expect(sentHeaders().cookie).toBe('sessionid=abc')

    // In the browser the composable returns no cookie, so none is set by hand.
    fetchMock.mockClear()
    requestHeaders.mockReturnValue({})
    await useApi()('/me/')
    expect(sentHeaders()).not.toHaveProperty('cookie')
  })

  it('p12_v06 prefixes the API base', async () => {
    await useApi()('/catalog/facets/')
    expect(fetchMock.mock.calls[0]![0]).toBe('/catalog/facets/')
    expect(fetchMock.mock.calls[0]![1].baseURL).toBe('/api')
  })

  it('p12_v07 maps DRF errors', async () => {
    const api = useApi()
    const cases: Array<[unknown, number, string | RegExp, Record<string, string[]>]> = [
      [failure(400, { email: ['Correo inválido.'] }), 400, /\S/, { email: ['Correo inválido.'] }],
      [failure(400, { non_field_errors: ['Datos incorrectos.'] }), 400, 'Datos incorrectos.', {}],
      [failure(403, { detail: 'Sin permiso.' }), 403, 'Sin permiso.', {}],
      [failure(404, { detail: 'No encontrado.' }), 404, 'No encontrado.', {}],
      [failure(429, { detail: 'Request was throttled.' }), 429, /demasiados intentos/, {}],
      [failure(500), 500, /\S/, {}],
      [new TypeError('Failed to fetch'), 0, /conectarnos/, {}],
    ]
    for (const [thrown, status, detail, fieldErrors] of cases) {
      fetchMock.mockRejectedValueOnce(thrown)
      const error = await api('/x/').catch((e: unknown) => e)
      expect(error).toBeInstanceOf(ApiError)
      const apiError = error as ApiError
      expect(apiError.status).toBe(status)
      expect(apiError.detail).toMatch(detail instanceof RegExp ? detail : new RegExp(`^${detail}$`))
      expect(apiError.fieldErrors).toEqual(fieldErrors)
    }
  })
})
