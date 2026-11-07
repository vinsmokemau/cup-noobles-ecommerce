import type { components } from '~/types/api'

type CheckoutLineError = components['schemas']['CheckoutLineError']
type CheckoutTotals = components['schemas']['CheckoutTotals']

/** What a 409 from `POST /api/checkout/` means (T8.4, T8.12). Nothing was reserved either way. */
export type CheckoutConflict =
  { kind: 'lines'; lineErrors: CheckoutLineError[] } | { kind: 'total'; totals: CheckoutTotals }

/** Reads the payload of a checkout 409; `null` when it is neither of the two known shapes. */
export function parseCheckoutConflict(body: unknown): CheckoutConflict | null {
  if (!body || typeof body !== 'object') return null
  const payload = body as { code?: unknown; line_errors?: unknown; totals?: unknown }
  if (payload.code === 'lines_unavailable' && Array.isArray(payload.line_errors)) {
    return { kind: 'lines', lineErrors: payload.line_errors as CheckoutLineError[] }
  }
  if (payload.code === 'total_changed' && payload.totals && typeof payload.totals === 'object') {
    return { kind: 'total', totals: payload.totals as CheckoutTotals }
  }
  return null
}

/** The message shown beside the affected line ("Solo quedan 2 de …"). */
export function lineErrorMessage(error: CheckoutLineError, productName: string): string {
  if (error.code === 'insufficient_stock') {
    const left = error.available ?? 0
    if (left <= 0) return `Ya no hay existencias de ${productName}.`
    return left === 1 ? `Solo queda 1 de ${productName}.` : `Solo quedan ${left} de ${productName}.`
  }
  if (error.code === 'unavailable') return `${productName} ya no está disponible.`
  return `Revisa la cantidad de ${productName}.`
}
