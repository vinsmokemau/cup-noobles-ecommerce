import { randomUUID } from 'node:crypto'
import { expect, test, waitForHydration, type Page, type SeedManifest } from './fixtures'

// The cart is named by a cookie, so a request made through `page.request` and the page the test
// then opens see the same cart.
async function addToCart(page: Page, seed: SeedManifest, quantity: number): Promise<void> {
  const { hoodie } = seed.catalog
  // L + blanco: the variant the seed keeps well stocked for purchases (the cart specs use L + negro).
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
    data: { variant_public_id: variant.public_id, quantity },
    headers: { 'X-CSRFToken': csrf },
  })
  expect(response.ok()).toBe(true)
}

const uniqueEmail = () => `cliente-${randomUUID()}@example.com`

async function openCheckout(page: Page): Promise<void> {
  await page.goto('/checkout')
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Checkout' })).toBeVisible()
}

async function fillPostalCode(page: Page, postalCode: string): Promise<void> {
  await page.getByLabel('Código postal').fill(postalCode)
}

// Fills the contact and delivery sections with a postal code of the sample dataset.
async function fillCheckout(page: Page, email: string, postalCode = '06700'): Promise<void> {
  await page.getByLabel('Correo electrónico').fill(email)
  await page.getByLabel('Teléfono').fill('5555555555')
  await page.getByLabel('Nombre de quien recibe').fill('Cliente de prueba')
  await fillPostalCode(page, postalCode)
  await expect(page.getByLabel('Municipio o alcaldía')).not.toHaveValue('')
  await page.getByLabel('Calle').fill('Calle de prueba')
  await page.getByLabel('Número exterior').fill('10')
  await page.getByRole('combobox', { name: 'Colonia' }).click()
  await page.getByRole('option').first().click()
}

async function ordersOf(page: Page, email: string): Promise<{ number: string; state: string }[]> {
  const response = await page.request.get(`/dev/test/orders/?email=${encodeURIComponent(email)}`)
  return ((await response.json()) as { orders: { number: string; state: string }[] }).orders
}

test('p13_v01 mobile viewport purchase delivery', async ({ page, seed }, testInfo) => {
  // The ID names the mobile project; the desktop project has no purchase to check (P13-V01).
  test.skip(testInfo.project.name !== 'mobile', 'P13-V01 runs on the mobile project')
  const email = uniqueEmail()
  await addToCart(page, seed, 1)
  await openCheckout(page)
  await fillCheckout(page, email)

  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  await page.getByRole('button', { name: 'Aprobar con tarjeta' }).click()
  await expect(page).toHaveURL(/\/pedido\/[0-9a-f-]{36}\/gracias\?t=.+/)

  await expect.poll(async () => (await ordersOf(page, email)).map((o) => o.state)).toEqual(['paid'])
})

test('p13_v02 double-click Pagar creates one order', async ({ page, seed }) => {
  async function attempt(fire: () => Promise<void>) {
    const email = uniqueEmail()
    await page.context().clearCookies()
    await addToCart(page, seed, 1)
    await openCheckout(page)
    await fillCheckout(page, email)

    let checkoutRequests = 0
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith('/api/checkout/')) {
        checkoutRequests++
      }
    })
    const simulator = new Promise<number>((resolve) => {
      let navigations = 0
      page.on('framenavigated', (frame) => {
        if (frame === page.mainFrame() && /\/dev\/payments\/checkout\//.test(frame.url())) {
          resolve(++navigations)
        }
      })
    })
    await fire()
    expect(await simulator).toBe(1)
    await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
    expect(checkoutRequests).toBe(1)
    expect(await ordersOf(page, email)).toHaveLength(1)
    page.removeAllListeners('request')
    page.removeAllListeners('framenavigated')
  }

  const pagar = () => page.getByRole('button', { name: 'Pagar' })
  await attempt(() => pagar().dblclick())
  // Two clicks fired in the same tick, before the page can re-render the disabled button.
  await attempt(() => pagar().evaluate((button: HTMLElement) => (button.click(), button.click())))
})

test('p13_v11 delivery quote follows the cp', async ({ page, seed }) => {
  await addToCart(page, seed, 1)
  await openCheckout(page)
  const shipping = page.getByTestId('checkout-shipping')

  // §2.5 dev defaults: MXN 99 local, MXN 179 nacional.
  await fillPostalCode(page, '06700')
  await expect(shipping).toContainText('$99.00')
  await fillPostalCode(page, '97000')
  await expect(shipping).toContainText('$179.00')

  // At or above the free-shipping threshold the quote is free.
  await page.context().clearCookies()
  await addToCart(page, seed, 2)
  await openCheckout(page)
  await fillPostalCode(page, '97000')
  await expect(page.getByTestId('checkout-shipping')).toContainText('Gratis')
})

test('p13_v21 idempotency key lifecycle', async ({ page, seed }) => {
  const keys: string[] = []
  await page.route('**/api/checkout/', async (route) => {
    keys.push(route.request().headers()['idempotency-key'] ?? '')
    if (keys.length === 1) {
      // The server gets the request and answers, but the answer never reaches the page.
      await route.fetch()
      await route.abort('failed')
      return
    }
    await route.continue()
  })

  const email = uniqueEmail()
  await addToCart(page, seed, 1)
  await openCheckout(page)
  await fillCheckout(page, email)
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  expect(keys).toHaveLength(2)
  expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/)
  expect(keys[1]).toBe(keys[0])
  expect(await ordersOf(page, email)).toHaveLength(1)

  // A new page load is a new purchase attempt: a new key.
  await page.unroute('**/api/checkout/')
  const reloadKeys: string[] = []
  await page.route('**/api/checkout/', async (route) => {
    reloadKeys.push(route.request().headers()['idempotency-key'] ?? '')
    await route.abort('failed')
  })
  await page.context().clearCookies()
  await addToCart(page, seed, 1)
  await openCheckout(page)
  await fillCheckout(page, uniqueEmail())
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect.poll(() => reloadKeys.length).toBe(1)
  await page.reload()
  await waitForHydration(page)
  await fillCheckout(page, uniqueEmail())
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect.poll(() => reloadKeys.length).toBe(2)
  expect(reloadKeys[1]).not.toBe(reloadKeys[0])
})
