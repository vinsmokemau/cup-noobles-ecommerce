import { expect, test } from '../fixtures'
import { expectSimulator, fillCheckoutAsGuest, productFor } from './journey'

// A slow connection, so the first press of "Pagar" is still on its way when the second lands:
// 400 ms each way and about 400 kbit/s.
const SLOW_NETWORK = {
  offline: false,
  latency: 400,
  downloadThroughput: 50_000,
  uploadThroughput: 50_000,
}
const NO_THROTTLING = { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }

// J8 (SPEC.md 15.C): a guest double-clicks "Pagar" on a slow connection. One order is made, its
// unit is held once, and the browser goes to the payment page once.
test('p15_v08 double-click Pagar creates one order', async ({ page, seed, inspect }, testInfo) => {
  // A whole checkout, and the dev server compiles each page on its first visit.
  test.setTimeout(180_000)
  const product = productFor(seed.journeys.j8, testInfo.project.name)
  const { sku } = product.variants[0]!
  const before = await inspect.inventory(sku)

  const email = await fillCheckoutAsGuest(page, product)

  let simulatorVisits = 0
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame() && /\/dev\/payments\/checkout\//.test(frame.url())) {
      simulatorVisits++
    }
  })

  // Both projects run Chromium, so the connection is slowed through its DevTools protocol.
  const devtools = await page.context().newCDPSession(page)
  await devtools.send('Network.enable')
  await devtools.send('Network.emulateNetworkConditions', SLOW_NETWORK)
  await page.getByRole('button', { name: 'Pagar' }).dblclick()
  await expectSimulator(page)
  await devtools.send('Network.emulateNetworkConditions', NO_THROTTLING)

  // One order, holding the cart's one unit once; nothing has left the stock.
  const orders = await inspect.orders(email)
  expect(orders.map((order) => order.state)).toEqual(['pending_payment'])
  expect(await inspect.inventory(sku)).toEqual({ ...before, reserved: before.reserved + 1 })

  // A second order would have sent the browser to the payment page a second time.
  await page.waitForLoadState('load')
  await expect(
    page.getByRole('heading', { level: 1, name: `Pedido ${orders[0]!.number}` }),
  ).toBeVisible()
  expect(simulatorVisits).toBe(1)
})
