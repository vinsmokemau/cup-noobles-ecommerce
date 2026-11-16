import { randomUUID } from 'node:crypto'
import {
  expect,
  expectNoA11yViolations,
  waitForHydration,
  type Page,
  type PerProject,
  type SeededProduct,
} from '../fixtures'

// What the Release 1 journeys share (SPEC.md 15.C): a guest who walks from a product page to the
// payment simulator the way a customer does.
//
// The accessibility check runs on every storefront page a journey visits (REQ-051). The pages that
// stand in for a provider's own (the payment simulator, the voucher, the mock tracking page) and
// the Django admin are not checked: the owner's answer in T15.6a (2026-11-16).

/**
 * The journey's own copy of its product for the Playwright project that is running. `desktop` and
 * `mobile` run at the same time and each asserts stock counts, so each buys its own (§4.6).
 */
export function productFor(products: PerProject, project: string): SeededProduct {
  expect(['desktop', 'mobile'], 'a journey runs on the desktop and mobile projects').toContain(
    project,
  )
  return products[project as keyof PerProject]
}

/** Opens the product page and returns the text of its availability badge. */
export async function openProduct(page: Page, product: SeededProduct): Promise<string> {
  await page.goto(`/producto/${product.slug}`)
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: product.name })).toBeVisible()
  const badge = page.locator('main [data-status]').first()
  await expect(badge).toBeVisible()
  await expectNoA11yViolations(page)
  return (await badge.innerText()).trim()
}

/**
 * A guest buys one unit: product page → cart → checkout with CP 06700 → "Pagar". The browser ends
 * on the payment simulator. Returns the email of the order, which is unique to this purchase.
 */
export async function buyAsGuest(page: Page, product: SeededProduct): Promise<string> {
  await openProduct(page, product)
  await page.getByRole('button', { name: 'Agregar al carrito' }).click()
  await page.getByRole('status').getByRole('link', { name: 'Ver carrito' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Tu carrito' })).toBeVisible()
  await expect(page.getByRole('listitem').filter({ hasText: product.name })).toHaveCount(1)
  const checkout = page.getByRole('link', { name: 'Ir al checkout' })
  await expect(checkout).not.toHaveAttribute('aria-disabled', 'true')
  await expectNoA11yViolations(page)
  await checkout.click()

  await expect(page.getByRole('heading', { level: 1, name: 'Checkout' })).toBeVisible()
  const email = `cliente-${randomUUID()}@example.com`
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Teléfono').fill('5555555555')
  await page.getByLabel('Nombre de quien recibe').fill('Cliente de prueba')
  await page.getByLabel('Código postal').fill('06700')
  // The postal code fills in the municipality and offers its neighborhoods.
  await expect(page.getByLabel('Municipio o alcaldía')).not.toHaveValue('')
  await page.getByLabel('Calle').fill('Calle de prueba')
  await page.getByLabel('Número exterior').fill('10')
  await page.getByRole('combobox', { name: 'Colonia' }).click()
  await page.getByRole('option').first().click()
  // The list of neighborhoods closes before the page is checked as the customer leaves it.
  await expect(page.getByRole('listbox')).toHaveCount(0)
  await expectNoA11yViolations(page)
  await page.getByRole('button', { name: 'Pagar' }).click()

  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  await expect(page.getByRole('heading', { level: 1, name: /^Pedido / })).toBeVisible()
  return email
}

/** Presses one of the simulator's buttons and waits for the landing page it sends the browser to. */
export async function chooseOutcome(
  page: Page,
  button: 'Aprobar con tarjeta' | 'Pagar en OXXO',
  landing: 'gracias' | 'pendiente',
): Promise<void> {
  await page.getByRole('button', { name: button }).click()
  await expect(page).toHaveURL(new RegExp(`/pedido/[0-9a-f-]{36}/${landing}\\?t=.+`))
  await waitForHydration(page)
}

/**
 * From `pendiente`: checks the voucher link and its expiry, then opens the voucher, which the
 * storefront shows in a new tab. Returns that tab, on the simulator's voucher page.
 */
export async function openVoucher(page: Page): Promise<Page> {
  const link = page.getByRole('link', { name: 'Ver mi ficha de pago' })
  // The voucher exists once the provider's notification has been processed.
  await expect(link).toBeVisible({ timeout: 20_000 })
  const expiry = page.getByTestId('voucher-expiry').locator('time')
  await expect(expiry).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}T/)
  await expect(expiry).not.toBeEmpty()
  await expectNoA11yViolations(page)

  const opened = page.context().waitForEvent('page')
  await link.click()
  const voucher = await opened
  await expect(voucher).toHaveURL(/\/dev\/payments\/voucher\//)
  await expect(voucher.getByRole('heading', { level: 1, name: 'Ficha de pago OXXO' })).toBeVisible()
  return voucher
}
