import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { ApiError } from '~/composables/useApi'
import { useCart, type Cart } from '~/composables/useCart'

const requestHeaders = vi.hoisted(() => vi.fn(() => ({}) as Record<string, string>))
mockNuxtImport('useRequestHeaders', () => requestHeaders)

const fetchMock = vi.hoisted(() => vi.fn())
mockNuxtImport('$fetch', () => fetchMock)

const VARIANT = '5f0f6a1e-6f6f-4f0e-9d57-0b3a2f6c1a11'

function cartFixture(overrides: Partial<Cart> = {}): Cart {
  return {
    fulfillment_method: null,
    shipping_quote: null,
    lines: [
      {
        id: 7,
        variant_public_id: VARIANT,
        quantity: 2,
        unit_price_cents: 15000,
        line_total_cents: 30000,
        availability: 'ok',
        max_available: null,
      },
    ],
    // Deliberately not the sum of the lines: the server's numbers are the ones shown.
    totals: {
      subtotal_cents: 31234,
      shipping_cents: 5600,
      discount_cents: 0,
      total_cents: 36834,
      tax_included_cents: 5080,
    },
    ...overrides,
  }
}

function failure(status: number, data?: unknown) {
  return Object.assign(new Error(`${status}`), { status, statusCode: status, data })
}

beforeEach(() => {
  fetchMock.mockReset()
  requestHeaders.mockReturnValue({})
  useCart().cart.value = null
})

describe('useCart', () => {
  it('p13_v03 state replaced from server response', async () => {
    const { cart, add, update, remove, setFulfillment } = useCart()
    const actions: Array<[string, () => Promise<unknown>]> = [
      ['add', () => add(VARIANT, 5)],
      ['update', () => update(7, 5)],
      ['remove', () => remove(7)],
      ['setFulfillment', () => setFulfillment('06700')],
    ]
    for (const [name, act] of actions) {
      // The server answers differently from what was asked: a reduced quantity, another price.
      const served = cartFixture({
        lines: [
          {
            id: 7,
            variant_public_id: VARIANT,
            quantity: 2,
            unit_price_cents: 16500,
            line_total_cents: 33000,
            availability: 'reduced',
            max_available: 2,
          },
        ],
      })
      fetchMock.mockResolvedValueOnce(structuredClone(served))
      await act()
      expect(cart.value, name).toEqual(served)
      // Server totals, not the sum of the lines (31234 ≠ 33000 + 5600 - 0).
      expect(cart.value?.totals.total_cents, name).toBe(36834)
    }
  })

  it('p13_v03 calls the cart endpoints', async () => {
    fetchMock.mockResolvedValue(cartFixture())
    const { add, update, remove, setFulfillment } = useCart()
    await add(VARIANT, 3)
    await update(7, 4)
    await remove(7)
    await setFulfillment('06700')
    const calls = fetchMock.mock.calls.map(([path, options]) => [
      path,
      options.method,
      options.body,
    ])
    expect(calls).toEqual([
      ['/cart/lines/', 'POST', { variant_public_id: VARIANT, quantity: 3 }],
      ['/cart/lines/7/', 'PATCH', { quantity: 4 }],
      ['/cart/lines/7/', 'DELETE', undefined],
      ['/cart/fulfillment/', 'POST', { method: 'delivery', postal_code: '06700' }],
    ])
  })

  it('p13_v04 error leaves state untouched', async () => {
    const { cart, add, update, remove, setFulfillment } = useCart()
    const actions: Array<() => Promise<unknown>> = [
      () => add(VARIANT, 5),
      () => update(7, 5),
      () => remove(7),
      () => setFulfillment('06700'),
    ]
    for (const status of [409, 500]) {
      for (const act of actions) {
        const prior = cartFixture()
        cart.value = structuredClone(prior)

        let reject!: (reason: unknown) => void
        fetchMock.mockReturnValueOnce(new Promise((_, r) => (reject = r)))
        const settled = act().catch((e: unknown) => e)
        // While the request is pending nothing has changed: no optimistic update.
        expect(cart.value).toEqual(prior)

        reject(failure(status, { detail: 'No se pudo.' }))
        const error = await settled
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(status)
        expect(cart.value).toEqual(prior)
      }
    }
  })

  it('p13_v03 refresh reads the cart, quoting to a postal code when given one', async () => {
    const served = cartFixture()
    fetchMock.mockResolvedValue(served)
    const { cart, refresh } = useCart()
    await refresh()
    expect(fetchMock.mock.calls[0]![0]).toBe('/cart/')
    expect(fetchMock.mock.calls[0]![1].query).toBeUndefined()
    await refresh('06700')
    expect(fetchMock.mock.calls[1]![1].query).toEqual({ postal_code: '06700' })
    expect(cart.value).toEqual(served)
  })

  it('p13_v04 pending is cleared after a failure', async () => {
    const { pending, add } = useCart()
    fetchMock.mockRejectedValueOnce(failure(500))
    await add(VARIANT, 1).catch(() => undefined)
    expect(pending.value).toBe(false)
  })
})
