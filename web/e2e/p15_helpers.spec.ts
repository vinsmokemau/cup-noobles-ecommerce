import { expect, test } from './fixtures'
import { chooseOutcome, startPurchase } from './p13_purchase'

// Self-tests of the helpers the Phase 15 journeys use (T15.4, G73). They run on both projects, as
// the journeys do. No test here runs a job that moves other specs' orders (`advance_orders`,
// `expire_reservations`): the specs of earlier phases run at the same time and read order states.

test('g73 inspect.inventory reads the stock of a seeded sku', async ({ seed, inspect }) => {
  // `[DEMO] Artbook` is seeded with 2 units (15.A) and no spec buys it.
  const { sku } = seed.demo.products.artbook.variants[0]!
  expect(await inspect.inventory(sku)).toEqual({ on_hand: 2, reserved: 0, preorder_committed: 0 })
  await expect(inspect.inventory('NO-SUCH-SKU')).rejects.toThrow(/answered 404/)
})

test('g73 adminLogin signs in the seeded staff user', async ({ page, adminLogin }) => {
  await adminLogin(page)
  // A page only staff can open: an anonymous visitor is sent back to the login form.
  await page.goto('/admin/orders/order/')
  await expect(page).toHaveURL(/\/admin\/orders\/order\/$/)
})

test('g73 run reports a command that fails', async ({ run }) => {
  await expect(run('mock_payments expire-order', ['CN-0000-000000'])).rejects.toThrow(
    /There is no order CN-0000-000000/,
  )
})

test('g73 a purchase is read back with inspect.orders, run and readLatestEmail', async ({
  page,
  seed,
  run,
  inspect,
  readLatestEmail,
}) => {
  const email = await startPurchase(page, seed)
  expect((await inspect.orders(email)).map((order) => order.state)).toEqual(['pending_payment'])
  // An unpaid card order has no email yet.
  expect(await readLatestEmail(email)).toBeNull()

  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect
    .poll(async () => (await inspect.orders(email)).map((order) => order.state))
    .toEqual(['paid'])
  const [order] = await inspect.orders(email)

  // The confirmation waits in the outbox until `send_outbox` runs: the E2E stack has no scheduler.
  await run('send_outbox')
  await expect.poll(async () => (await readLatestEmail(email))?.template).toBe('order_confirmation')
  const sent = (await readLatestEmail(email))!
  expect(sent.text).toContain(`Pedido ${order!.number}`)
  expect(sent.html).toContain(order!.number)
  expect(sent.attachments).toEqual({})

  // An address with no order has no email.
  expect(await readLatestEmail(`nadie-${email}`)).toBeNull()
})
