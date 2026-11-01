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
