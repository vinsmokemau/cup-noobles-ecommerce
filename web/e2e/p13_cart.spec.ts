import {
  expect,
  expectNoA11yViolations,
  test,
  waitForHydration,
  type Page,
  type SeedManifest,
} from './fixtures'

// The cart is named by a cookie, so a request made through `page.request` and the page the test
// then opens see the same cart.
async function addToCart(
  page: Page,
  seed: SeedManifest,
  quantity: number,
  variantIndex = 2, // L + negro, in stock
): Promise<void> {
  const { hoodie } = seed.catalog
  const variantSku = hoodie.variants[variantIndex]!
  const detail = await page.request.get(`/api/catalog/products/${hoodie.slug}/`)
  const product = (await detail.json()) as {
    variants: { public_id: string; options: Record<string, string> }[]
  }
  const variant = product.variants.find(
    (v) =>
      v.options.talla === variantSku.options.talla && v.options.color === variantSku.options.color,
  )!

  // A read hands out the CSRF cookie that unsafe requests must echo back.
  await page.request.get('/api/cart/')
  const cookies = await page.context().cookies()
  const csrf = cookies.find((c) => c.name === 'csrftoken')!.value
  const response = await page.request.post('/api/cart/lines/', {
    data: { variant_public_id: variant.public_id, quantity },
    headers: { 'X-CSRFToken': csrf },
  })
  expect(response.ok()).toBe(true)
}

test('p13_v09 quantity above stock shows reduced', async ({ page, seed }) => {
  await addToCart(page, seed, 1)
  await page.goto('/carrito')
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Tu carrito' })).toBeVisible()
  await expect(page.getByTestId('line-reduced')).toHaveCount(0)

  // The seeded variant has 20 units, so 25 is more than there is.
  const quantity = page.getByRole('spinbutton')
  await quantity.fill('25')
  await quantity.press('Enter')

  const message = page.getByTestId('line-reduced')
  await expect(message).toContainText('Solo quedan 20 disponibles')
  // The stored quantity was not changed silently: the cart still holds what the customer asked for.
  await expect(quantity).toHaveValue(/25/)
  await expect(page.getByRole('link', { name: 'Ir al checkout' })).toHaveAttribute(
    'aria-disabled',
    'true',
  )
  await expectNoA11yViolations(page)
})

test('p13_v10 remove line and empty state', async ({ page, seed }) => {
  await addToCart(page, seed, 1)
  await page.goto('/carrito')
  await waitForHydration(page)
  await expect(page.getByTestId('cart-totals')).toBeVisible()

  await page.getByRole('button', { name: /^Quitar/ }).click()

  const empty = page.getByTestId('empty-cart')
  await expect(empty).toBeVisible()
  await expect(empty.getByRole('link', { name: 'Explorar el catálogo' })).toHaveAttribute(
    'href',
    '/catalogo',
  )
  await expectNoA11yViolations(page)
})

test('p13_v29 lines show product name and options', async ({ page, seed }) => {
  const { hoodie } = seed.catalog
  const [first, second] = [hoodie.variants[2]!, hoodie.variants[3]!]
  expect(first.options).not.toEqual(second.options)
  await addToCart(page, seed, 1, 2)
  await addToCart(page, seed, 1, 3)
  await page.goto('/carrito')
  await waitForHydration(page)

  const rows = page.locator('[data-line-id]')
  await expect(rows).toHaveCount(2)
  for (const [index, variant] of [first, second].entries()) {
    const row = rows.nth(index)
    await expect(row).toContainText(hoodie.name)
    await expect(row).not.toContainText('Producto')
    for (const [key, value] of Object.entries(variant.options)) {
      await expect(row.getByTestId('line-options')).toContainText(`${key}: ${value}`)
    }
  }
  await expectNoA11yViolations(page)
})

test('p13_v08 add to cart updates the badge', async ({ page, seed }) => {
  const { hoodie } = seed.catalog
  await page.goto(`/producto/${hoodie.slug}`)
  await waitForHydration(page)
  const badge = page.getByTestId('cart-badge')
  await expect(badge).toHaveCount(0)

  const add = page.getByTestId('add-to-cart')
  await add.click()
  await expect(page.getByTestId('added-to-cart')).toBeVisible()
  await expect(badge).toHaveText('1')
  await add.click()
  await expect(badge).toHaveText('2')
  await expectNoA11yViolations(page)

  // The server's price, not one computed here.
  const served = (await (await page.request.get('/api/cart/')).json()) as {
    lines: { line_total_cents: number }[]
  }
  expect(served.lines).toHaveLength(1)
  await page.getByRole('link', { name: 'Carrito, 2 productos' }).click()
  await expect(page).toHaveURL(/\/carrito$/)
  const row = page.locator('[data-line-id]')
  await expect(row).toHaveCount(1)
  await expect(row).toContainText(hoodie.name)
  const total = (served.lines[0]!.line_total_cents / 100).toLocaleString('es-MX')
  await expect(row).toContainText(total)
})
