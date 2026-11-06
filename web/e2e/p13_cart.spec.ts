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
async function addToCart(page: Page, seed: SeedManifest, quantity: number): Promise<void> {
  const { hoodie } = seed.catalog
  const variantSku = hoodie.variants[2]! // L + negro, in stock
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
