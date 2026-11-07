import { expect, test, waitForHydration } from './fixtures'

test('p13_v20 cart failure stays inside its boundary', async ({ page }) => {
  await page.goto('/')
  await waitForHydration(page)

  // Client-side navigation: the cart page asks the API, which fails.
  const fail = (route: { fulfill: (o: { status: number; body: string }) => Promise<void> }) =>
    route.fulfill({ status: 500, body: '{"detail":"boom"}' })
  await page.route('**/api/cart/**', fail)
  await page.getByTestId('cart-link').click()
  await expect(page).toHaveURL(/\/carrito$/)

  const main = page.getByRole('main')
  const retry = main.getByRole('button', { name: 'Reintentar' })
  await expect(retry).toBeVisible()
  await expect(main.getByRole('heading', { level: 1, name: 'Tu carrito' })).toBeVisible()

  // The header and its navigation are outside the region and keep working.
  const header = page.getByRole('banner')
  await expect(header).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Principal' })).toBeVisible()
  await header.getByRole('link', { name: 'Cup Noobles, inicio' }).click()
  await expect(page).toHaveURL(/\/$/)

  // Once the API answers again, the retry shows the cart.
  await page.goBack()
  await expect(retry).toBeVisible()
  // While the failed read is still running the button is busy and disabled (DS loading pattern).
  await expect(retry).toBeEnabled()
  await page.unroute('**/api/cart/**', fail)
  await retry.click()
  await expect(page.getByTestId('empty-cart')).toBeVisible()
  await expect(retry).toHaveCount(0)
})
