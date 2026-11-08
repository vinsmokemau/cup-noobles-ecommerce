import { expectNoA11yViolations, expect, test, waitForHydration } from './fixtures'
import { chooseOutcome, startPurchase } from './p13_purchase'

// Every 13.A route: the cart, the checkout, and the three landing pages (REQ-051).
test('p13_v16 axe on cart checkout and landing pages', async ({ page, seed }) => {
  // Four purchases in one test, and the dev server compiles each page on first visit.
  test.setTimeout(180_000)

  await test.step('/carrito and /checkout with a line in the cart', async () => {
    await startPurchase(page, seed)
    for (const route of ['/carrito', '/checkout']) {
      const response = await page.goto(route)
      expect(response?.status(), route).toBe(200)
      await waitForHydration(page)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expectNoA11yViolations(page)
    }
  })

  await test.step('/pedido/{id}/gracias', async () => {
    await startPurchase(page, seed)
    await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
    await expect(page.getByRole('heading', { level: 1, name: 'Pago confirmado' })).toBeVisible()
    await expectNoA11yViolations(page)
  })

  await test.step('/pedido/{id}/pendiente', async () => {
    await startPurchase(page, seed)
    await chooseOutcome(page, 'Pagar en OXXO', 'pendiente')
    await expect(page.getByTestId('voucher-link')).toBeVisible()
    await expectNoA11yViolations(page)
  })

  await test.step('/pedido/{id}/error', async () => {
    await startPurchase(page, seed)
    await chooseOutcome(page, 'Rechazar', 'error')
    await expect(page.getByRole('button', { name: 'Intentar el pago de nuevo' })).toBeVisible()
    await expectNoA11yViolations(page)
  })

  await test.step('a link that cannot be read', async () => {
    await page.goto('/pedido/00000000-0000-4000-8000-000000000000/gracias?t=bad')
    await waitForHydration(page)
    await expect(page.getByTestId('order-unavailable')).toBeVisible()
    await expectNoA11yViolations(page)
  })
})
