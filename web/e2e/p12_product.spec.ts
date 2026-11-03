import { expect, test, waitForHydration, type Page } from './fixtures'

// The group updates after the selection reaches the page state, so click and then wait for it.
// A radio is found by its value: its accessible name carries the sold-out suffix.
const option = (page: Page, value: string) =>
  page.getByRole('radio').and(page.locator(`[value="${value}"]`))

async function choose(page: Page, value: string) {
  const radio = option(page, value)
  await radio.click()
  await expect(radio).toHaveAttribute('aria-checked', 'true')
}

const money = (cents: number) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100)

test('p12_v16 variant selection updates price and availability', async ({ page, seed }) => {
  const { hoodie } = seed.catalog
  await page.goto(`/producto/${hoodie.slug}`)
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: hoodie.name })).toBeVisible()

  const status = page.locator('[data-status]').first()
  const first = hoodie.variants[0]! // in stock
  const second = hoodie.variants[3]! // in stock, at a different price
  expect(second.price_cents).not.toBe(first.price_cents)

  for (const variant of [first, second]) {
    await choose(page, variant.options.talla!)
    await choose(page, variant.options.color!)
    await expect(page.getByText(money(variant.price_cents)).first()).toBeVisible()
    await expect(status).toHaveAttribute('data-status', 'in_stock')
  }
  await expect(page.getByText(money(first.price_cents))).toHaveCount(0)

  // The loop ends on L + blanco. M + blanco is sold out, so M is disabled while blanco is chosen.
  await expect(option(page, hoodie.variants[1]!.options.talla!)).toBeDisabled()
})
