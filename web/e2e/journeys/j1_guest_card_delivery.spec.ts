import { expect, expectNoA11yViolations, test, waitForHydration } from '../fixtures'
import { buyAsGuest, chooseOutcome, productFor } from './journey'

// J1 (SPEC.md 15.C): a guest pays by card, the job moves the order to `preparing`, staff ship it
// with the mock carrier, the carrier delivers it, and the customer finds it on `/rastrear`.
test('p15_v01 guest card purchase with delivery', async ({
  page,
  seed,
  run,
  inspect,
  adminLogin,
  readLatestEmail,
}, testInfo) => {
  // The longest journey: a purchase, the admin and the tracking pages, and the dev server compiles
  // each page on its first visit.
  test.setTimeout(240_000)
  const product = productFor(seed.journeys.j1, testInfo.project.name)
  const { sku } = product.variants[0]!
  const before = await inspect.inventory(sku)

  const email = await buyAsGuest(page, product)
  const stateOf = async () => (await inspect.orders(email)).map((o) => o.state)
  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect(page.getByRole('heading', { level: 1, name: 'Pago confirmado' })).toBeVisible({
    timeout: 20_000,
  })
  await expectNoA11yViolations(page)

  // Paid: the unit left the stock and its hold is gone.
  const [order] = await inspect.orders(email)
  const { number } = order!
  expect(order!.state).toBe('paid')
  expect(await inspect.inventory(sku)).toEqual({ ...before, on_hand: before.on_hand - 1 })

  // The job moves the order to `preparing`; nobody in the admin has to (G75). It is run for this
  // order alone, because other specs are reading their own `paid` orders meanwhile (G79).
  await run('advance_orders', ['--order', number])
  expect(await stateOf()).toEqual(['preparing'])

  // The confirmation waits in the outbox until `send_outbox` runs: the E2E stack has no scheduler.
  await run('send_outbox')
  await expect.poll(async () => (await readLatestEmail(email))?.template).toBe('order_confirmation')
  expect((await readLatestEmail(email))!.text).toContain(number)

  const trackingNumber = `MOCK-${number}-1`
  await test.step('staff ship the order with a blank tracking number', async () => {
    await adminLogin(page)
    await page.goto(`/admin/orders/order/?q=${encodeURIComponent(number)}`)
    await page.getByRole('link', { name: number, exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/orders\/order\/\d+\/change\//)

    // The blank row of "Envío": ticked with no tracking number, the mock carrier makes one up.
    const shipment = page.getByRole('group', { name: 'Envío', exact: true })
    await shipment.getByRole('checkbox').check()
    await expect(shipment.getByRole('textbox').first()).toHaveValue('')
    await page.getByRole('button', { name: 'Guardar', exact: true }).click()
    await expect(page.getByText('Envío creado: el pedido está en shipped.')).toBeVisible()
    expect(await stateOf()).toEqual(['shipped'])
    // The customer is a guest: the staff session ends here.
    await page.context().clearCookies()
  })

  // The tracking email names the shipment and links to the carrier's page.
  await run('send_outbox')
  await expect.poll(async () => (await readLatestEmail(email))?.template).toBe('order_shipped')
  const shipped = (await readLatestEmail(email))!
  expect(shipped.text).toContain(trackingNumber)
  const trackingUrl = /https?:\/\/\S+\/dev\/carrier\/track\/[^\s"<>]+/.exec(shipped.text)?.[0]
  expect(trackingUrl, 'the tracking email links to the tracking page').toContain(trackingNumber)

  await test.step('the carrier delivers the package', async () => {
    await page.goto(trackingUrl!)
    await expect(
      page.getByRole('heading', { level: 1, name: `Guía ${trackingNumber}` }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Entregado' }).click()
    await expect(page.getByRole('cell', { name: 'delivered' })).toBeVisible()
    expect(await stateOf()).toEqual(['delivered'])
  })

  await test.step('the customer finds the delivered order on /rastrear', async () => {
    await page.goto('/rastrear')
    await waitForHydration(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Rastrea tu pedido' })).toBeVisible()
    await page.getByLabel('Número de pedido').fill(number)
    await page.getByLabel('Correo electrónico').fill(email)
    await page.getByRole('button', { name: 'Buscar pedido' }).click()

    const result = page.getByTestId('order-result')
    await expect(result.getByRole('heading', { level: 2 })).toHaveText(`Pedido ${number}`)
    await expect(result.getByTestId('order-state')).toHaveText('Entregado')
    await expect(result.getByTestId('order-shipment')).toContainText(trackingNumber)
    await expectNoA11yViolations(page)
  })
})
