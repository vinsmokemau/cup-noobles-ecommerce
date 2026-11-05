import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { usePrelaunch } from '~/composables/usePrelaunch'

const fetchMock = vi.hoisted(() => vi.fn())
mockNuxtImport('$fetch', () => fetchMock)

function failure(status: number, data?: unknown) {
  return Object.assign(new Error(`${status}`), { status, statusCode: status, data })
}

beforeEach(() => {
  clearNuxtData('prelaunch')
  fetchMock.mockReset()
})

describe('usePrelaunch', () => {
  it('p12_v28 is off when the catalog answers', async () => {
    fetchMock.mockResolvedValue([])
    expect((await usePrelaunch()).value).toBe(false)
  })

  it('p12_v28 is on when the API answers 503 {"prelaunch": true}', async () => {
    fetchMock.mockRejectedValue(failure(503, { prelaunch: true }))
    expect((await usePrelaunch()).value).toBe(true)
  })

  it('p12_v28 any other failure counts as off, so the page reports its own error', async () => {
    fetchMock.mockRejectedValue(failure(503))
    expect((await usePrelaunch()).value).toBe(false)
    clearNuxtData('prelaunch')
    fetchMock.mockRejectedValue(failure(500))
    expect((await usePrelaunch()).value).toBe(false)
  })
})
