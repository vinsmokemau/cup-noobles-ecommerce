import { randomUUID } from 'node:crypto'
import { expect, test, waitForHydration, type Page, type SeedManifest } from './fixtures'

// The cart is named by a cookie, so a request made through `page.request` and the page the test
// then opens see the same cart (same helper as p13_checkout.spec.ts).
async function addToCart(page: Page, seed: SeedManifest): Promise<void> {
  const { hoodie } = seed.catalog
  const variantSku = hoodie.variants[3]!
  const detail = await page.request.get(`/api/catalog/products/${hoodie.slug}/`)
  const product = (await detail.json()) as {
    variants: { public_id: string; options: Record<string, string> }[]
  }
  const variant = product.variants.find(
    (v) =>
      v.options.talla === variantSku.options.talla && v.options.color === variantSku.options.color,
  )!
  await page.request.get('/api/cart/')
  const cookies = await page.context().cookies()
  const csrf = cookies.find((c) => c.name === 'csrftoken')!.value
  const response = await page.request.post('/api/cart/lines/', {
    data: { variant_public_id: variant.public_id, quantity: 1 },
    headers: { 'X-CSRFToken': csrf },
  })
  expect(response.ok()).toBe(true)
}

async function openCheckout(page: Page): Promise<void> {
  await page.goto('/checkout')
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Checkout' })).toBeVisible()
}

async function fillCheckout(page: Page, email: string): Promise<void> {
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Teléfono').fill('5555555555')
  await page.getByLabel('Nombre de quien recibe').fill('Cliente de prueba')
  await page.getByLabel('Código postal', { exact: true }).fill('06700')
  await expect(page.getByLabel('Municipio o alcaldía')).not.toHaveValue('')
  await page.getByLabel('Calle').fill('Calle de prueba')
  await page.getByLabel('Número exterior').fill('10')
  await page.getByRole('combobox', { name: 'Colonia' }).click()
  await page.getByRole('option').first().click()
}

// Picks an option by typing its first letters and pressing Enter, the way a keyboard user does: on the
// mobile viewport a pointer click on an option of a long list can land outside the page.
async function choose(page: Page, field: string, typeahead: string): Promise<void> {
  await page.getByRole('combobox', { name: field }).click()
  await page.keyboard.type(typeahead)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('listbox')).toHaveCount(0)
}

async function ordersOf(page: Page, email: string): Promise<{ number: string; state: string }[]> {
  const response = await page.request.get(`/dev/test/orders/?email=${encodeURIComponent(email)}`)
  return ((await response.json()) as { orders: { number: string; state: string }[] }).orders
}

// A fictitious taxpayer: a valid RFC shape, not a real one.
const FISCAL = { rfc: 'XAXX010101000', name: 'Cliente de Prueba SA de CV', postalCode: '06700' }

test('p13_v23 quiero factura fields and errors', async ({ page, browser, seed }) => {
  const email = `cliente-${randomUUID()}@example.com`

  // The client schema only checks that a regime was chosen, so the server's field error needs a code
  // the server does not know: the first checkout request goes out with one, and the real API answers.
  let tampered = false
  await page.route('**/api/checkout/', async (route) => {
    if (tampered) return route.continue()
    tampered = true
    const body = route.request().postDataJSON() as { invoice: Record<string, string> }
    body.invoice.tax_regime = 'ZZZ'
    await route.continue({ postData: JSON.stringify(body) })
  })

  await addToCart(page, seed)
  await openCheckout(page)
  await fillCheckout(page, email)

  // The fields show only when the box is checked.
  const checkbox = page.getByRole('checkbox', { name: 'Quiero factura' })
  await expect(checkbox).not.toBeChecked()
  await expect(page.getByLabel('RFC')).toHaveCount(0)
  await checkbox.check()
  for (const label of ['RFC', 'Nombre o razón social', 'Código postal fiscal']) {
    await expect(page.getByLabel(label)).toBeVisible()
  }
  await expect(page.getByRole('combobox', { name: 'Régimen fiscal' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Uso de CFDI' })).toBeVisible()

  // Client checks: an incomplete section stops "Pagar" before any request.
  let checkoutRequests = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/checkout/')) checkoutRequests++
  })
  await page.getByLabel('RFC').fill('NO-ES-UN-RFC')
  // Leaving the field shows its error, which moves the button down: settle before clicking.
  await page.getByLabel('RFC').blur()
  await expect(page.getByText('El RFC no tiene un formato válido.')).toBeVisible()
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page.getByText('El RFC no tiene un formato válido.')).toBeVisible()
  await expect(page.getByText('Este campo es obligatorio.').first()).toBeVisible()
  expect(checkoutRequests).toBe(0)

  // Server checks: a regime the server does not accept comes back as a field error under Régimen.
  await page.getByLabel('RFC').fill(FISCAL.rfc.toLowerCase())
  await page.getByLabel('Nombre o razón social').fill(FISCAL.name)
  await page.getByLabel('Código postal fiscal').fill(FISCAL.postalCode)
  await choose(page, 'Régimen fiscal', 'Personas')
  await choose(page, 'Uso de CFDI', 'Gastos')
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page.getByText('Elige un régimen fiscal de la lista.')).toBeVisible()
  await expect(page.getByText('Revisa los datos de tu factura.')).toBeVisible()
  expect(checkoutRequests).toBe(1)
  expect(await ordersOf(page, email)).toHaveLength(0)

  // Sent as chosen, the same page pays; the paid order then waits in the admin CFDI queue.
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  await page.getByRole('button', { name: 'Aprobar con tarjeta' }).click()
  await expect(page).toHaveURL(/\/pedido\/[0-9a-f-]{36}\/gracias\?t=.+/)
  await expect.poll(async () => (await ordersOf(page, email)).map((o) => o.state)).toEqual(['paid'])
  const [order] = await ordersOf(page, email)

  const context = await browser.newContext()
  try {
    const staff = await context.newPage()
    await staff.goto('/admin/login/')
    await staff.getByLabel(/correo|email|usuario|username/i).fill(seed.staff.email)
    await staff.getByLabel(/contraseña|password/i).fill(seed.staff.password)
    await staff.locator('input[type=submit]').click()
    await expect(staff).toHaveURL(/\/admin\/$/)
    await staff.goto('/admin/invoicing/invoicerequest/')
    const row = staff.getByRole('row').filter({ hasText: order!.number })
    await expect(row).toBeVisible()
    await expect(row).toContainText(FISCAL.rfc)
  } finally {
    await context.close()
  }
})

test('p13_v23 unchecking sends no invoice data', async ({ page, seed }) => {
  const email = `cliente-${randomUUID()}@example.com`
  await addToCart(page, seed)
  await openCheckout(page)
  await fillCheckout(page, email)

  const checkbox = page.getByRole('checkbox', { name: 'Quiero factura' })
  await checkbox.check()
  await page.getByLabel('RFC').fill(FISCAL.rfc)
  await checkbox.uncheck()
  await expect(page.getByLabel('RFC')).toHaveCount(0)

  const checkout = page.waitForRequest(
    (request) => request.method() === 'POST' && request.url().endsWith('/api/checkout/'),
  )
  await page.getByRole('button', { name: 'Pagar' }).click()
  const body = (await checkout).postDataJSON() as Record<string, unknown>
  expect(body).not.toHaveProperty('invoice')
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
})
