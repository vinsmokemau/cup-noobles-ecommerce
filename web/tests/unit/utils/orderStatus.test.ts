import { describe, expect, it } from 'vitest'
import type { OrderState } from '~/utils/orderLanding'
import { orderStateLabel } from '~/utils/orderStatus'

// Every state of the order state machine (8.A), as the API names them.
const STATES: OrderState[] = [
  'draft',
  'pending_payment',
  'paid',
  'awaiting_stock',
  'preparing',
  'ready_for_pickup',
  'shipped',
  'delivered',
  'picked_up',
  'completed',
  'cancelled',
  'expired',
  'refunded',
  'partially_refunded',
]

describe('order state labels', () => {
  it('p14_v09 every order state has its own Spanish badge label', () => {
    const labels = STATES.map(orderStateLabel)
    for (const label of labels) {
      // DS badge copy: one to three words, sentence case, no final period.
      expect(label).toMatch(/^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+( [a-záéíóúñ]+){0,2}$/)
    }
    expect(new Set(labels).size).toBe(STATES.length)
    // No state name leaks to the customer.
    expect(labels.filter((label) => (STATES as string[]).includes(label))).toEqual([])
  })

  it.each<[OrderState, string]>([
    ['pending_payment', 'Pago pendiente'],
    ['paid', 'Pagado'],
    ['preparing', 'En preparación'],
    ['shipped', 'Enviado'],
    ['delivered', 'Entregado'],
    ['cancelled', 'Cancelado'],
    ['expired', 'Vencido'],
  ])('p14_v09 %s reads "%s"', (state, label) => {
    expect(orderStateLabel(state)).toBe(label)
  })
})
