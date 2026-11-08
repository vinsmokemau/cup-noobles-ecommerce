import type { components } from '~/types/api'

export type OrderState = components['schemas']['StateEnum']

// The order has been paid, or has moved on from being paid (T13.7): the `gracias` page confirms it.
const PAID_OR_LATER: ReadonlySet<OrderState> = new Set([
  'paid',
  'awaiting_stock',
  'preparing',
  'ready_for_pickup',
  'shipped',
  'delivered',
  'picked_up',
  'completed',
  'refunded',
  'partially_refunded',
])

// The order will not be paid any more: waiting for it would only run the clock out.
const CLOSED: ReadonlySet<OrderState> = new Set(['cancelled', 'expired'])

export const isPaidOrLater = (state: OrderState) => PAID_OR_LATER.has(state)
export const isClosed = (state: OrderState) => CLOSED.has(state)
