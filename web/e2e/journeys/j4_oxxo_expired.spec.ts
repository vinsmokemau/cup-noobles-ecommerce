import { expect, test } from '../fixtures'
import { buyAsGuest, chooseOutcome, openProduct, openVoucher, productFor } from './journey'

// J4 (SPEC.md 15.C): a guest chooses OXXO and never pays. The voucher lapsing changes nothing by
// itself (9.4 maps `cancelled` to no event); the order expires at its payment deadline, which
// releases the unit it held.
test('p15_v04 oxxo expired releases stock', async ({
  page,
  seed,
  run,
  inspect,
  readLatestEmail,
}, testInfo) => {
  // A whole purchase, and the dev server compiles each page on its first visit.
  test.setTimeout(180_000)
  const product = productFor(seed.journeys.j4, testInfo.project.name)
  const { sku } = product.variants[0]!
  const before = await inspect.inventory(sku)
  const availability = await openProduct(page, product)

  const email = await buyAsGuest(page, product)
  await chooseOutcome(page, 'Pagar en OXXO', 'pendiente')
  const voucher = await openVoucher(page)
  const [order] = await inspect.orders(email)
  expect(order!.state).toBe('pending_payment')
  expect(await inspect.inventory(sku)).toEqual({ ...before, reserved: before.reserved + 1 })

  // The voucher lapses at the provider. Its notification is delivered before the order is read
  // again: the order still waits, and still holds its unit.
  await voucher.getByRole('button', { name: 'Simular vencimiento' }).click()
  await expect(voucher.getByRole('button', { name: 'Simular vencimiento' })).toHaveCount(0)
  await run('mock_payments deliver --once', ['--base-url', 'http://proxy:8080'])
  expect((await inspect.orders(email)).map((o) => o.state)).toEqual(['pending_payment'])
  expect(await inspect.inventory(sku)).toEqual({ ...before, reserved: before.reserved + 1 })

  // The payment deadline passes: the order expires and its unit goes back on sale.
  await run('mock_payments expire-order', [order!.number])
  expect((await inspect.orders(email)).map((o) => o.state)).toEqual(['expired'])
  expect(await inspect.inventory(sku)).toEqual(before)

  await run('send_outbox')
  await expect.poll(async () => (await readLatestEmail(email))?.template).toBe('order_expired')
  expect((await readLatestEmail(email))!.text).toContain(order!.number)

  // The product page shows what it showed before the purchase.
  expect(await openProduct(page, product)).toBe(availability)
})
