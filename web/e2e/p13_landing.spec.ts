import { expect, test } from './fixtures'
import { chooseOutcome, startPurchase } from './p13_purchase'

test('p13_v13 gracias polls until paid', async ({ page, seed }) => {
  test.setTimeout(60_000)
  await startPurchase(page, seed)

  // The mock webhook fires at once in the E2E stack, which would hide the waiting state. The first
  // two reads see the order as the API had it before the webhook: still waiting for payment.
  let reads = 0
  await page.route('**/api/orders/*/status/**', async (route) => {
    reads++
    if (reads > 2) return route.fallback()
    const response = await route.fetch()
    const order = (await response.json()) as Record<string, unknown>
    await route.fulfill({ response, json: { ...order, state: 'pending_payment' } })
  })

  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect(page.getByRole('heading', { level: 1, name: 'Confirmando tu pago…' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 1, name: 'Pago confirmado' })).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByTestId('order-confirming')).toHaveCount(0)
  expect(reads).toBeGreaterThan(2)
})

test('p13_v13 gracias says the email will confirm when the wait runs out', async ({
  page,
  seed,
}) => {
  await startPurchase(page, seed)
  // The page waits 60 s for the payment. The page's clock jumps past that instead of the spec
  // waiting it out, so the spec does not hold a worker for over a minute.
  await page.clock.install()
  await page.route('**/api/orders/*/status/**', async (route) => {
    const response = await route.fetch()
    const order = (await response.json()) as Record<string, unknown>
    await route.fulfill({ response, json: { ...order, state: 'pending_payment' } })
  })

  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect(page.getByRole('heading', { level: 1, name: 'Confirmando tu pago…' })).toBeVisible()
  await page.clock.fastForward(61_000)
  await expect(page.getByTestId('order-timeout')).toBeVisible()
  await expect(page.getByText('Te avisaremos por correo')).toBeVisible()
})

test('p13_v14 pendiente shows voucher and expiry', async ({ page, seed }) => {
  await startPurchase(page, seed)
  await chooseOutcome(page, 'Pagar en OXXO', 'pendiente')

  const link = page.getByRole('link', { name: 'Ver mi ficha de pago' })
  await expect(link).toHaveAttribute('href', /\/dev\/payments\/voucher\//)
  // es-MX long date and time in the store timezone, e.g. "15 de noviembre de 2026 a las 12:30 p.m.".
  const expiry = page.getByTestId('voucher-expiry').locator('time')
  await expect(expiry).toHaveText(/^\d{1,2} de [a-záéíóú]+ de \d{4}(,| a las) \d{1,2}:\d{2}/)
  await expect(expiry).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}T/)
})

test('p13_v15 error page offers retry', async ({ page, seed }) => {
  await startPurchase(page, seed)
  const firstSession = page.url()
  await chooseOutcome(page, 'Rechazar', 'error')

  await expect(page.getByRole('link', { name: 'Volver al carrito' })).toHaveAttribute(
    'href',
    '/carrito',
  )
  await page.getByRole('button', { name: 'Intentar el pago de nuevo' }).click()
  await expect(page).toHaveURL(/\/dev\/payments\/checkout\//)
  expect(page.url()).not.toBe(firstSession)
  // Same order: the simulator shows the number of the order that was rejected.
  await expect(page.getByRole('heading', { level: 1, name: /^Pedido / })).toBeVisible()
})
