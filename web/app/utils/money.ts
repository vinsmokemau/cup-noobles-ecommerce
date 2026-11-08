// The only place the storefront formats money (CR-30, ADR-0024). The locale and
// the currency code live here and nowhere else (SPEC.md §4.5).

const LOCALE = 'es-MX'
const CURRENCY = 'MXN'

const currencyFormat = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: CURRENCY })

/** Formats integer centavos of MXN, e.g. `123400` → `$1,234.00`. No suffix. */
export function formatMXN(cents: number): string {
  if (!Number.isSafeInteger(cents)) {
    throw new TypeError(`formatMXN expects integer centavos, got ${cents}`)
  }
  return currencyFormat.format(cents / 100)
}

// Dates share the locale above. The store timezone is a constant, not a setting (G5, ADR-0030).
const STORE_TIME_ZONE = 'America/Mexico_City'
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

/**
 * Formats a date or an ISO timestamp, e.g. `2026-11-15` → `15 de noviembre de 2026` (CR-31).
 * `long` goes in sentences, `medium` in cards and lists (DS:formatting.md). A date with no time is a
 * calendar day, so it is read in UTC to stay on the same day; a timestamp is read in the store timezone.
 */
export function formatDate(value: string, dateStyle: 'long' | 'medium' = 'long'): string {
  const timeZone = DATE_ONLY.test(value) ? 'UTC' : STORE_TIME_ZONE
  return new Intl.DateTimeFormat(LOCALE, { dateStyle, timeZone }).format(new Date(value))
}

/**
 * Formats a timestamp with its time, e.g. `2026-11-15T18:30:00Z` → `15 de noviembre de 2026, 12:30 p.m.`
 * in the store timezone (CR-31). For a deadline the customer must act on, such as a voucher expiry.
 */
export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: STORE_TIME_ZONE,
  }).format(new Date(value))
}
