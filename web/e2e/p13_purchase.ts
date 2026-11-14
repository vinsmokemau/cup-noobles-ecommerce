import { randomUUID } from 'node:crypto'
import { expect, waitForHydration, type Page, type SeedManifest } from './fixtures'

// Helpers for the Phase 13 specs that need an order waiting at the payment simulator.

async function addToCart(page: Page, seed: SeedManifest): Promise<void> {
  const { hoodie } = seed.catalog
  // L + blanco: the variant the seed keeps well stocked for purchases.
  const variantSku = hoodie.variants[3]!
  const detail = await page.request.get(`/api/catalog/products/${hoodie.slug}/`)
  const product = (await detail.json()) as {
    variants: { public_id: string; options: Record<string, string> }[]
  }
  const variant = product.variants.find(
    (v) =>
      v.options.talla === variantSku.options.talla && v.options.color === variantSku.options.color,
  )!
  await page.request.get('/api/cart/') // hands out the CSRF cookie
  const cookies = await page.context().cookies()
  const csrf = cookies.find((c) => c.name === 'csrftoken')!.value
  const response = await page.request.post('/api/cart/lines/', {
    data: { variant_public_id: variant.public_id, quantity: 1 },
    headers: { 'X-CSRFToken': csrf },
  })
  expect(response.ok()).toBe(true)
}

/**
 * Fills the checkout for a fresh cart and presses "Pagar": the browser ends on the simulator.
 * Returns the email the order was placed with, which is unique to this purchase.
 */
export async function startPurchase(page: Page, seed: SeedManifest): Promise<string> {
  await page.context().clearCookies()
  await addToCart(page, seed)
  await page.goto('/checkout')
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Checkout' })).toBeVisible()
  const email = `cliente-${randomUUID()}@example.com`
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Teléfono').fill('5555555555')
  await page.getByLabel('Nombre de quien recibe').fill('Cliente de prueba')
  await page.getByLabel('Código postal').fill('06700')
  await expect(page.getByLabel('Municipio o alcaldía')).not.toHaveValue('')
  await page.getByLabel('Calle').fill('Calle de prueba')
  await page.getByLabel('Número exterior').fill('10')
  await page.getByRole('combobox', { name: 'Colonia' }).click()
  await page.getByRole('option').first().click()
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  return email
}

/** Presses one of the simulator's buttons and waits for the landing page it sends the browser to. */
export async function chooseOutcome(
  page: Page,
  button: string,
  landing: 'gracias' | 'pendiente' | 'error',
): Promise<void> {
  await page.getByRole('button', { name: button }).click()
  await expect(page).toHaveURL(new RegExp(`/pedido/[0-9a-f-]{36}/${landing}\\?t=.+`))
  await waitForHydration(page)
}
