import { expect, test, waitForHydration } from './fixtures'

// G67: an icon that first appears after the page has loaded, and whose name only the Design System
// layer writes (a button's loading spinner), is asked from Nuxt Icon's own endpoint. That endpoint
// must not sit under `/api`, which Caddy and the Nitro proxy send to Django.
test('g67 a loading button shows its spinner', async ({ page }) => {
  await page.goto('/rastrear')
  await waitForHydration(page)

  // The lookup's answer is held back, so the button stays in its loading state.
  let release: () => void = () => undefined
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/orders/lookup/', async (route) => {
    await held
    await route.fallback()
  })

  const iconAnswered = page.waitForResponse((response) =>
    new URL(response.url()).pathname.startsWith('/_nuxt_icon/'),
  )
  await page.getByLabel('Número de pedido').fill('CN-1999-000000')
  await page.getByLabel('Correo electrónico').fill('nadie@example.com')
  const button = page.getByRole('button', { name: 'Buscar pedido' })
  await button.click()

  await expect(button).toHaveAttribute('aria-busy', 'true')
  expect((await iconAnswered).status()).toBe(200)
  // Nuxt Icon draws the glyph as a mask; without the icon's data the span is an empty box.
  await expect(button.locator('[data-slot="leadingIcon"]')).toHaveCSS(
    'mask-image',
    /^url\("data:image\/svg\+xml/,
  )

  release()
  await expect(page.getByTestId('order-not-found')).toBeVisible()
})
