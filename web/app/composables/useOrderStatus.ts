import { ApiError } from '~/composables/useApi'
import type { components } from '~/types/api'
import { isClosed } from '~/utils/orderLanding'

export type OrderStatus = components['schemas']['OrderStatus']
export type PayRetry = components['schemas']['PayRetryResponse']

export const POLL_INTERVAL_MS = 2000
export const POLL_LIMIT_MS = 60_000

/** Where the wait stands: still waiting, got what it waited for, gave up, closed order, or no readable order. */
export type PollPhase = 'waiting' | 'done' | 'timeout' | 'closed' | 'unavailable'

/**
 * The order named by the landing page's URL, read through the order-status token (G21, ADR-0065)
 * and retried through the pay-retry endpoint (G22, ADR-0066). The token is `?t=`; without it the
 * server has nothing to authorise, so the page treats the order as unreadable.
 */
export function useOrderStatus() {
  const api = useApi()
  const route = useRoute()
  const publicId = String(route.params.id)
  const token = typeof route.query.t === 'string' ? route.query.t : ''

  function fetchStatus(): Promise<OrderStatus> {
    return api<OrderStatus>(`/orders/${publicId}/status/`, { query: { t: token } })
  }

  function retryPayment(): Promise<PayRetry> {
    return api<PayRetry>(`/orders/${publicId}/pay/`, { method: 'POST', query: { t: token } })
  }

  return { publicId, token, fetchStatus, retryPayment }
}

/**
 * Polls the order every `POLL_INTERVAL_MS` for up to `POLL_LIMIT_MS` once the page is in the
 * browser (T13.7), until `isReady` accepts it. A failed read other than "not found" is treated as
 * a hiccup and tried again. `gracias` waits for a paid order; `pendiente` waits for its voucher,
 * which exists only once the provider's notification has been processed.
 */
export function useOrderPolling(
  fetchStatus: () => Promise<OrderStatus>,
  hasToken: boolean,
  isReady: (order: OrderStatus) => boolean,
  { intervalMs = POLL_INTERVAL_MS, limitMs = POLL_LIMIT_MS } = {},
) {
  const order = ref<OrderStatus | null>(null)
  const phase = ref<PollPhase>(hasToken ? 'waiting' : 'unavailable')
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined

  const wait = (ms: number) =>
    new Promise<void>((resolve) => {
      timer = setTimeout(resolve, ms)
    })

  async function poll() {
    const startedAt = Date.now()
    while (!stopped) {
      try {
        const current = await fetchStatus()
        if (stopped) return
        order.value = current
        if (isReady(current)) return void (phase.value = 'done')
        if (isClosed(current.state)) return void (phase.value = 'closed')
      } catch (failure) {
        if (stopped) return
        if (failure instanceof ApiError && failure.status === 404) {
          return void (phase.value = 'unavailable')
        }
      }
      if (Date.now() - startedAt + intervalMs > limitMs) return void (phase.value = 'timeout')
      await wait(intervalMs)
    }
  }

  onMounted(() => {
    if (hasToken) void poll()
  })
  onBeforeUnmount(() => {
    stopped = true
    clearTimeout(timer)
  })

  return { order, phase }
}
