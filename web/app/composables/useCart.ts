import type { components } from '~/types/api'

export type Cart = components['schemas']['Cart']

/**
 * The visitor's cart, as the server last described it (CR-24: server state, no Pinia).
 *
 * Every action calls the API and then replaces the state with the response. Nothing is changed
 * locally first and no total is computed here: the server is the only place totals exist (CR-02,
 * REQ-002). A failed request throws an `ApiError` and leaves the state as it was.
 */
export function useCart() {
  const api = useApi()
  const cart = useState<Cart | null>('cart', () => null)
  const pending = useState<boolean>('cart-pending', () => false)

  async function send(path: string, options: Parameters<typeof api>[1] = {}): Promise<Cart> {
    pending.value = true
    try {
      const next = await api<Cart>(path, options)
      cart.value = next
      return next
    } finally {
      pending.value = false
    }
  }

  /** Reads the cart. With a delivery cart, `postalCode` asks the server to quote shipping to it. */
  function refresh(postalCode?: string) {
    return send('/cart/', postalCode ? { query: { postal_code: postalCode } } : {})
  }

  /** Adds a variant, or sets its quantity if it is already in the cart (the API upserts). */
  function add(variantPublicId: string, quantity: number) {
    return send('/cart/lines/', {
      method: 'POST',
      body: { variant_public_id: variantPublicId, quantity },
    })
  }

  function update(lineId: number, quantity: number) {
    return send(`/cart/lines/${lineId}/`, { method: 'PATCH', body: { quantity } })
  }

  function remove(lineId: number) {
    return send(`/cart/lines/${lineId}/`, { method: 'DELETE' })
  }

  /** Release 1 is delivery only (OA-08); the server rejects any other method. */
  function setFulfillment(postalCode: string, method = 'delivery') {
    return send('/cart/fulfillment/', {
      method: 'POST',
      body: { method, postal_code: postalCode },
    })
  }

  return { cart, pending, refresh, add, update, remove, setFulfillment }
}
