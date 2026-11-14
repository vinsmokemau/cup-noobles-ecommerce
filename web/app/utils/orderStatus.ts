import type { OrderState } from '~/utils/orderLanding'

// The name of each order state as a customer reads it on a badge: one to three words, sentence
// case, no final period (DS: badge). Typed over every state, so a new state without a label fails
// the type check. The pickup and pre-order states are Release 2; an R1 order never reaches them.
const ORDER_STATE_LABELS: Record<OrderState, string> = {
  draft: 'En proceso',
  pending_payment: 'Pago pendiente',
  paid: 'Pagado',
  awaiting_stock: 'En preventa',
  preparing: 'En preparación',
  ready_for_pickup: 'Listo para recoger',
  shipped: 'Enviado',
  delivered: 'Entregado',
  picked_up: 'Recogido',
  completed: 'Completado',
  cancelled: 'Cancelado',
  expired: 'Vencido',
  refunded: 'Reembolsado',
  partially_refunded: 'Reembolso parcial',
}

export const orderStateLabel = (state: OrderState): string => ORDER_STATE_LABELS[state]
