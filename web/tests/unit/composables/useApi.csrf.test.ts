import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { useApi } from '~/composables/useApi'

const requestHeaders = vi.hoisted(() => vi.fn(() => ({}) as Record<string, string>))
mockNuxtImport('useRequestHeaders', () => requestHeaders)

const fetchMock = vi.hoisted(() => vi.fn())
mockNuxtImport('$fetch', () => fetchMock)

beforeEach(() => {
  fetchMock.mockReset().mockResolvedValue({ ok: true })
  requestHeaders.mockReturnValue({})
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'csrftoken=; path=/; max-age=0'
})

function sentHeaders(): Record<string, string> {
  return fetchMock.mock.calls[0]![1].headers
}

// Branch coverage for the CSRF cookie source; p12_v05 covers the browser happy path.
describe('useApi csrf cookie source', () => {
  it('p12_v05 sends no token when the csrftoken cookie is absent', async () => {
    document.cookie = 'other=1; path=/'
    await useApi()('/cart/', { method: 'POST' })
    expect(sentHeaders()).not.toHaveProperty('X-CSRFToken')
    document.cookie = 'other=; path=/; max-age=0'
  })

  it('p12_v05 finds the token among several cookies and decodes it', async () => {
    document.cookie = 'a=1; path=/'
    document.cookie = 'csrftoken=t%3D1; path=/'
    await useApi()('/cart/', { method: 'POST' })
    expect(sentHeaders()['X-CSRFToken']).toBe('t=1')
    document.cookie = 'a=; path=/; max-age=0'
  })

  it('p12_v05 reads the token from the incoming cookie during SSR', async () => {
    requestHeaders.mockReturnValue({ cookie: 'sessionid=abc; csrftoken=ssr456' })
    await useApi()('/cart/', { method: 'POST' })
    expect(sentHeaders()['X-CSRFToken']).toBe('ssr456')
  })

  it('p12_v05 sends no token when there is no cookie source at all', async () => {
    vi.stubGlobal('document', undefined)
    await useApi()('/cart/', { method: 'POST' })
    expect(sentHeaders()).not.toHaveProperty('X-CSRFToken')
  })
})
