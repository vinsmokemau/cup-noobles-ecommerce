import { expectNoA11yViolations, expect, test, waitForHydration, type Page } from './fixtures'
import { chooseOutcome, startPurchase } from './p13_purchase'

// `/rastrear`, the guest order lookup (T14.6). The lookups are real: the E2E stack turns the
// API's 5-per-hour limit off (G66), because every spec reaches it from one address.

// The Spanish badge label of the states a card purchase can be in when it is looked up.
const PAID_LABELS: Record<string, string> = { paid: 'Pagado', preparing: 'En preparación' }

/** The number the store gave the one order placed with this email (`/dev/test/orders/`, T13.8). */
async function orderNumberOf(page: Page, email: string): Promise<string> {
  const response = await page.request.get(`/dev/test/orders/?email=${encodeURIComponent(email)}`)
  const { orders } = (await response.json()) as { orders: { number: string }[] }
  expect(orders).toHaveLength(1)
  return orders[0]!.number
}

async function openLookup(page: Page): Promise<void> {
  await page.goto('/rastrear')
  await waitForHydration(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Rastrea tu pedido' })).toBeVisible()
}

/** Sends the form and waits for the API's answer, so nothing is read from the previous lookup. */
async function lookUp(page: Page, number: string, email: string): Promise<number> {
  await page.getByLabel('Número de pedido').fill(number)
  await page.getByLabel('Correo electrónico').fill(email)
  const answered = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/orders/lookup/',
  )
  await page.getByRole('button', { name: 'Buscar pedido' }).click()
  return (await answered).status()
}

test('p14_v09 guest tracking lookup', async ({ page, seed }) => {
  // A purchase first, and the dev server compiles each page on its first visit.
  test.setTimeout(120_000)
  const email = await startPurchase(page, seed)
  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect(page.getByRole('heading', { level: 1, name: 'Pago confirmado' })).toBeVisible({
    timeout: 20_000,
  })
  const number = await orderNumberOf(page, email)

  await openLookup(page)

  // The right number and email: the order's status, as a badge with its Spanish label.
  expect(await lookUp(page, number, email)).toBe(200)
  const result = page.getByTestId('order-result')
  await expect(result.getByRole('heading', { level: 2 })).toHaveText(`Pedido ${number}`)
  const badge = result.getByTestId('order-state')
  await expect(badge).toBeVisible()
  const state = (await badge.getAttribute('data-state')) ?? ''
  expect(Object.keys(PAID_LABELS)).toContain(state)
  await expect(badge).toHaveText(PAID_LABELS[state]!)
  await expect(page.getByTestId('order-not-found')).toHaveCount(0)

  // A wrong email with the right number.
  expect(await lookUp(page, number, `otro-${email}`)).toBe(404)
  const notFound = page.getByTestId('order-not-found')
  await expect(notFound).toContainText(/no encontramos ese pedido/i)
  await expect(result).toHaveCount(0)
  const wrongEmailMessage = await notFound.innerText()

  // A number no order has, with the right email: the same message, word for word.
  expect(await lookUp(page, 'CN-1999-000000', email)).toBe(404)
  await expect(notFound).toContainText(/no encontramos ese pedido/i)
  await expect(result).toHaveCount(0)
  expect(await notFound.innerText()).toBe(wrongEmailMessage)
})

test('p14_v09 a lookup sent right after fixing a field reaches the API', async ({ page }) => {
  await openLookup(page)

  // An empty submit: one alert counts the fields, each field says what to write, and the first
  // one takes the focus.
  await page.getByRole('button', { name: 'Buscar pedido' }).click()
  await expect(page.getByTestId('lookup-invalid')).toContainText('Revisa 2 campos')
  await expect(page.getByText('Escribe el número de tu pedido.')).toBeVisible()
  await expect(page.getByLabel('Número de pedido')).toBeFocused()

  // The button is pressed with the last field still focused. Leaving the field would clear its
  // message and move the button before the click lands; the click must still send the form.
  expect(await lookUp(page, 'CN-1999-000000', 'nadie@example.com')).toBe(404)
  await expect(page.getByTestId('order-not-found')).toBeVisible()
  await expect(page.getByTestId('lookup-invalid')).toHaveCount(0)
})

test('p14_v17 axe on rastrear', async ({ page, seed }) => {
  test.setTimeout(120_000)
  // An OXXO order waiting for its payment: the found view at its fullest, with the voucher link.
  const email = await startPurchase(page, seed)
  await chooseOutcome(page, 'Pagar en OXXO', 'pendiente')
  await expect(page.getByTestId('voucher-link')).toBeVisible({ timeout: 20_000 })
  const number = await orderNumberOf(page, email)

  await test.step('empty', async () => {
    await openLookup(page)
    await expectNoA11yViolations(page)
  })

  await test.step('showing a found order', async () => {
    expect(await lookUp(page, number, email)).toBe(200)
    const result = page.getByTestId('order-result')
    await expect(result.getByTestId('order-state')).toHaveText('Pago pendiente')
    await expect(result.getByRole('link', { name: 'Ver mi ficha de pago' })).toHaveAttribute(
      'href',
      /\/dev\/payments\/voucher\//,
    )
    await expectNoA11yViolations(page)
  })

  await test.step('showing the not-found message', async () => {
    expect(await lookUp(page, number, `otro-${email}`)).toBe(404)
    await expect(page.getByTestId('order-not-found')).toBeVisible()
    await expectNoA11yViolations(page)
  })
})
