import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { isPaidOrLater } from '~/utils/orderLanding'
import { ApiError } from '~/composables/useApi'
import {
  POLL_INTERVAL_MS,
  POLL_LIMIT_MS,
  useOrderPolling,
  useOrderStatus,
  type OrderStatus,
} from '~/composables/useOrderStatus'

const route = vi.hoisted(() => ({
  params: { id: 'abc-123' } as Record<string, unknown>,
  query: {} as Record<string, unknown>,
}))
mockNuxtImport('useRoute', () => () => route)

const fetchMock = vi.hoisted(() => vi.fn())
mockNuxtImport('$fetch', () => fetchMock)
mockNuxtImport('useRequestHeaders', () => () => ({}))

const order = (state: OrderStatus['state']) => ({ number: 'CN-2026-000001', state }) as OrderStatus

// A component that runs the composable the way a page does and exposes what it returns.
function mountPolling(fetchStatus: () => Promise<OrderStatus>, hasToken = true) {
  let result!: ReturnType<typeof useOrderPolling>
  const Probe = defineComponent({
    setup() {
      result = useOrderPolling(fetchStatus, hasToken, (o) => isPaidOrLater(o.state))
      return () => h('div')
    },
  })
  return mountSuspended(Probe).then((wrapper) => ({ wrapper, ...result }))
}

describe('useOrderPolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('p13_v13 waits every 2 s and confirms once the order is paid', async () => {
    const fetchStatus = vi
      .fn()
      .mockResolvedValueOnce(order('pending_payment'))
      .mockResolvedValueOnce(order('pending_payment'))
      .mockResolvedValue(order('paid'))
    const { phase, order: current } = await mountPolling(fetchStatus)

    await vi.advanceTimersByTimeAsync(0)
    expect(phase.value).toBe('waiting')
    expect(fetchStatus).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(fetchStatus).toHaveBeenCalledTimes(2)
    expect(phase.value).toBe('waiting')
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(phase.value).toBe('done')
    expect(current.value?.state).toBe('paid')

    // Done: no more reads.
    await vi.advanceTimersByTimeAsync(POLL_LIMIT_MS)
    expect(fetchStatus).toHaveBeenCalledTimes(3)
  })

  it('p13_v13 counts every state after paid as confirmed', async () => {
    const { phase } = await mountPolling(() => Promise.resolve(order('preparing')))
    await vi.advanceTimersByTimeAsync(0)
    expect(phase.value).toBe('done')
  })

  it('p13_v13 gives up after 60 s', async () => {
    const fetchStatus = vi.fn().mockResolvedValue(order('pending_payment'))
    const { phase } = await mountPolling(fetchStatus)

    await vi.advanceTimersByTimeAsync(POLL_LIMIT_MS - POLL_INTERVAL_MS)
    expect(phase.value).toBe('waiting')
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(phase.value).toBe('timeout')
    const reads = fetchStatus.mock.calls.length
    // One read at the start, then one every 2 s up to and including the 60th second.
    expect(reads).toBe(POLL_LIMIT_MS / POLL_INTERVAL_MS + 1)
    await vi.advanceTimersByTimeAsync(POLL_LIMIT_MS)
    expect(fetchStatus).toHaveBeenCalledTimes(reads)
  })

  it('p13_v13 keeps trying after a failed read, and stops on a 404', async () => {
    const fetchStatus = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, 'boom'))
      .mockResolvedValueOnce(order('paid'))
    const { phase } = await mountPolling(fetchStatus)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(phase.value).toBe('done')

    const missing = await mountPolling(() => Promise.reject(new ApiError(404, 'no')))
    await vi.advanceTimersByTimeAsync(0)
    expect(missing.phase.value).toBe('unavailable')
  })

  it('p13_v13 stops on a closed order and never reads without a token', async () => {
    const closed = await mountPolling(() => Promise.resolve(order('expired')))
    await vi.advanceTimersByTimeAsync(0)
    expect(closed.phase.value).toBe('closed')

    const fetchStatus = vi.fn()
    const noToken = await mountPolling(fetchStatus, false)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(noToken.phase.value).toBe('unavailable')
    expect(fetchStatus).not.toHaveBeenCalled()
  })

  it('p13_v13 stops reading when the page goes away', async () => {
    const fetchStatus = vi.fn().mockResolvedValue(order('pending_payment'))
    const { wrapper } = await mountPolling(fetchStatus)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    const reads = fetchStatus.mock.calls.length
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(POLL_LIMIT_MS)
    expect(fetchStatus).toHaveBeenCalledTimes(reads)
  })
})

describe('useOrderPolling when the page goes away mid-read', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it.each([
    ['answers', (r: { resolve: (o: OrderStatus) => void }) => r.resolve(order('paid'))],
    ['fails', (r: { reject: (e: unknown) => void }) => r.reject(new ApiError(500, 'boom'))],
  ])('p13_v13 ignores a read that %s after the page is gone', async (_name, settle) => {
    let handlers!: { resolve: (o: OrderStatus) => void; reject: (e: unknown) => void }
    const fetchStatus = vi.fn(
      () =>
        new Promise<OrderStatus>((resolve, reject) => {
          handlers = { resolve, reject }
        }),
    )
    const { wrapper, phase } = await mountPolling(fetchStatus)
    await vi.advanceTimersByTimeAsync(0)
    wrapper.unmount()

    settle(handlers as never)
    await vi.advanceTimersByTimeAsync(POLL_LIMIT_MS)
    expect(phase.value).toBe('waiting')
    expect(fetchStatus).toHaveBeenCalledTimes(1)
  })
})

describe('useOrderStatus', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    route.params = { id: 'abc-123' }
    route.query = { t: 'signed-token' }
  })

  it('p13_v13 reads the status of the order named in the URL with its token', async () => {
    fetchMock.mockResolvedValue(order('paid'))
    const { fetchStatus, publicId, token } = useOrderStatus()

    expect(publicId).toBe('abc-123')
    expect(token).toBe('signed-token')
    await expect(fetchStatus()).resolves.toMatchObject({ state: 'paid' })
    expect(fetchMock.mock.calls[0]![0]).toBe('/orders/abc-123/status/')
    expect(fetchMock.mock.calls[0]![1].query).toEqual({ t: 'signed-token' })
  })

  it('p13_v15 retries the payment of the order with its token', async () => {
    fetchMock.mockResolvedValue({ checkout_url: 'https://pay.example/next' })
    const { retryPayment } = useOrderStatus()

    await expect(retryPayment()).resolves.toEqual({ checkout_url: 'https://pay.example/next' })
    expect(fetchMock.mock.calls[0]![0]).toBe('/orders/abc-123/pay/')
    expect(fetchMock.mock.calls[0]![1].method).toBe('POST')
    expect(fetchMock.mock.calls[0]![1].query).toEqual({ t: 'signed-token' })
  })

  it('p13_v13 treats a link without a token as unreadable', () => {
    route.query = {}
    expect(useOrderStatus().token).toBe('')
    route.query = { t: ['a', 'b'] }
    expect(useOrderStatus().token).toBe('')
  })
})
