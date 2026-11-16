import { expect, test } from '../fixtures'
import { buyAsGuest, chooseOutcome, openVoucher, productFor } from './journey'

// J3 (SPEC.md 15.C): a guest chooses OXXO, gets the voucher, and pays it later. The unit is held
// while the order waits and leaves the stock when the payment arrives.
test('p15_v03 oxxo pending then paid', async ({
  page,
  seed,
  run,
  inspect,
  readLatestEmail,
}, testInfo) => {
  // A whole purchase, and the dev server compiles each page on its first visit.
  test.setTimeout(180_000)
  const product = productFor(seed.journeys.j3, testInfo.project.name)
  const { sku } = product.variants[0]!
  const before = await inspect.inventory(sku)

  const email = await buyAsGuest(page, product)
  await chooseOutcome(page, 'Pagar en OXXO', 'pendiente')
  const voucher = await openVoucher(page)

  // The order waits for its payment and holds its unit; nothing has left the stock.
  const [order] = await inspect.orders(email)
  expect(order!.state).toBe('pending_payment')
  expect(await inspect.inventory(sku)).toEqual({ ...before, reserved: before.reserved + 1 })

  // The voucher email waits in the outbox until `send_outbox` runs: the E2E stack has no scheduler.
  await run('send_outbox')
  await expect.poll(async () => (await readLatestEmail(email))?.template).toBe('oxxo_voucher')
  expect((await readLatestEmail(email))!.text).toContain(order!.number)

  // The customer pays at the store: the provider notifies the shop a moment later.
  await voucher.getByRole('button', { name: 'Simular pago recibido' }).click()
  await expect(voucher.getByRole('button', { name: 'Simular pago recibido' })).toHaveCount(0)
  await expect
    .poll(async () => (await inspect.orders(email)).map((o) => o.state), { timeout: 30_000 })
    .toEqual(['paid'])

  // The held unit is sold: the hold is gone and the stock is one unit lower.
  expect(await inspect.inventory(sku)).toEqual({ ...before, on_hand: before.on_hand - 1 })
})
