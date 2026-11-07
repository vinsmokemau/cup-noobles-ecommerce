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
  test.setTimeout(60_000) // two full purchases; close to the 30 s default when both projects run
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
  test.setTimeout(60_000) // two full purchases; close to the 30 s default when both projects run
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

// ---- T13.6: checkout errors ------------------------------------------------------------------

// Puts the single variant of a seeded checkout-error product in the page's cart.
async function addProductToCart(page: Page, slug: string, quantity: number): Promise<void> {
  const detail = await page.request.get(`/api/catalog/products/${slug}/`)
  const product = (await detail.json()) as { variants: { public_id: string }[] }
  await page.request.get('/api/cart/')
  const cookies = await page.context().cookies()
  const csrf = cookies.find((c) => c.name === 'csrftoken')!.value
  const response = await page.request.post('/api/cart/lines/', {
    data: { variant_public_id: product.variants[0]!.public_id, quantity },
    headers: { 'X-CSRFToken': csrf },
  })
  expect(response.ok()).toBe(true)
}

test('p13_v17 server validation errors inline', async ({ page, seed }) => {
  const email = uniqueEmail()
  await addToCart(page, seed, 1)
  await openCheckout(page)
  await fillCheckout(page, email)

  // The form is valid, so the page sends it. The request is changed on its way out so the real
  // server answers with its own field errors: first an invalid email, then no address fields.
  const serverErrors: Record<string, unknown>[] = []
  let attempt = 0
  await page.route('**/api/checkout/', async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    const changed =
      attempt++ === 0 ? { ...body, email: 'no-es-un-correo' } : { ...body, address_payload: {} }
    const response = await route.fetch({ postData: JSON.stringify(changed) })
    serverErrors.push((await response.json()) as Record<string, unknown>)
    await route.fulfill({ response })
  })

  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect.poll(() => serverErrors.length).toBe(1)
  const emailMessage = (serverErrors[0]!.email as string[])[0]!
  await expect(page.getByText(emailMessage)).toBeVisible()
  await expect(page.getByLabel('Correo electrónico')).toHaveAttribute('aria-invalid', 'true')

  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect.poll(() => serverErrors.length).toBe(2)
  const address = serverErrors[1]!.address_payload as Record<string, string[]>
  await expect(page.getByText(address.street![0]!).first()).toBeVisible()
  await expect(page.getByLabel('Calle')).toHaveAttribute('aria-invalid', 'true')

  await expect(page).toHaveURL(/\/checkout/)
  expect(await ordersOf(page, email)).toHaveLength(0)
})

test('p13_v18 stock lost between cart and pay', async ({ page, seed, playwright }, testInfo) => {
  // `seed_e2e` leaves two units: one run of this spec uses them. Both projects share the stack.
  test.skip(testInfo.project.name !== 'desktop', 'P13-V18 runs on the desktop project')
  const { scarce } = seed.catalog.checkoutErrors
  const email = uniqueEmail()
  await addProductToCart(page, scarce.slug, 2)
  await openCheckout(page)
  await fillCheckout(page, email)
  const inventory = async () =>
    (await (await page.request.get(`/dev/test/inventory/${scarce.sku}/`)).json()) as {
      on_hand: number
      reserved: number
    }
  const before = await inventory()

  // A second client buys one of the two units while the first one is still on the page.
  const baseURL = testInfo.project.use.baseURL ?? 'http://localhost:8080'
  const other = await playwright.request.newContext({ baseURL })
  try {
    const detail = (await (await other.get(`/api/catalog/products/${scarce.slug}/`)).json()) as {
      variants: { public_id: string }[]
    }
    await other.get('/api/cart/')
    const csrf = (await other.storageState()).cookies.find((c) => c.name === 'csrftoken')!.value
    const headers = { 'X-CSRFToken': csrf }
    await other.post('/api/cart/lines/', {
      data: { variant_public_id: detail.variants[0]!.public_id, quantity: 1 },
      headers,
    })
    const cp = (await (await other.get('/api/postal-codes/06700/')).json()) as {
      state_code: string
      municipality: string
      neighborhoods: string[]
    }
    const purchase = await other.post('/api/checkout/', {
      headers,
      data: {
        email: uniqueEmail(),
        phone: '5555555555',
        fulfillment_method: 'delivery',
        address_payload: {
          recipient_name: 'Otro cliente',
          street: 'Calle de prueba',
          ext_number: '1',
          neighborhood: cp.neighborhoods[0],
          municipality: cp.municipality,
          state_code: cp.state_code,
          postal_code: '06700',
        },
      },
    })
    expect(purchase.status()).toBe(201)
  } finally {
    await other.dispose()
  }
  const during = await inventory()

  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page.getByTestId('line-error')).toContainText(`Solo queda 1 de ${scarce.name}.`)
  await expect(page).toHaveURL(/\/checkout/)
  expect(await ordersOf(page, email)).toHaveLength(0)
  expect(during.reserved).toBe(before.reserved + 1)
  expect(await inventory()).toEqual(during)
})

test('p13_v19 price changed before pay', async ({ page, seed }) => {
  // The page's last view of the cart is older than the server's prices: every cart answer shows a
  // total that is 50 pesos too low, as if the price had risen since the customer last looked. The
  // server stays real. The admin cannot change a price here (G58), so the staleness is on the page.
  const STALE_BY = 5000
  let stale = true
  await page.route(/\/api\/cart\//, async (route) => {
    const response = await route.fetch()
    const cart = (await response.json()) as { totals?: { total_cents: number } }
    if (stale && cart.totals) cart.totals.total_cents -= STALE_BY
    await route.fulfill({ response, json: cart })
  })

  const email = uniqueEmail()
  await addToCart(page, seed, 1)
  await openCheckout(page)
  await fillCheckout(page, email)
  const totals = page.getByTestId('checkout-totals')
  await expect(totals).toBeVisible()
  const staleTotal = await totals.innerText()

  const requests: Record<string, unknown>[] = []
  const answers: { status: number; totals?: { total_cents: number } }[] = []
  page.on('response', async (response) => {
    if (response.request().method() === 'POST' && response.url().endsWith('/api/checkout/')) {
      requests.push(response.request().postDataJSON() as Record<string, unknown>)
      const body = (await response.json().catch(() => ({}))) as { totals?: { total_cents: number } }
      answers.push({ status: response.status(), totals: body.totals })
      stale = false // the next cart read is the server's own
    }
  })

  // First press: the server refuses the total the customer saw and creates nothing.
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page.getByTestId('total-notice')).toBeVisible()
  await expect(page).toHaveURL(/\/checkout/)
  expect(answers[0]?.status).toBe(409)
  const fresh = answers[0]!.totals!.total_cents
  expect(fresh).toBe((requests[0]!.expected_total_cents as number) + STALE_BY)
  expect(await ordersOf(page, email)).toHaveLength(0)

  // The review section now shows what the customer will pay.
  await expect(totals).not.toHaveText(staleTotal)
  await expect(totals).toContainText(
    (fresh / 100).toLocaleString('es-MX', { minimumFractionDigits: 2 }),
  )

  // Second press pays that total.
  await page.getByRole('button', { name: 'Pagar' }).click()
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  expect(requests[1]!.expected_total_cents).toBe(fresh)
  expect(await ordersOf(page, email)).toHaveLength(1)
})
