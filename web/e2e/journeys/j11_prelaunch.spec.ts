import { expect, expectNoA11yViolations, test, waitForHydration } from '../fixtures'
import { buyAsGuest, chooseOutcome, openProduct } from './journey'

// The dev-only toggle of T12.15. The journey uses it to start with the mode on; going live is done
// by staff, in the admin.
const TOGGLE = '/dev/test/prelaunch/'

// Whatever happens, the stack is left with the mode off, so a run that fails or times out does not
// leave the next specs behind "próximamente". The test's own `request` is closed by then.
test.afterEach(async ({ playwright, baseURL }) => {
  const api = await playwright.request.newContext({ baseURL })
  await api.post(TOGGLE, { data: { on: false } })
  await api.dispose()
})

// J11 (SPEC.md 15.C): before launch the public sees only "próximamente" while staff buy for real
// and refund the test order; then staff publish the catalog and turn the mode off.
//
// The mode is one switch for the whole stack, so this spec runs in the `prelaunch` and
// `prelaunch-mobile` projects, after the other specs and one at a time (playwright.config.ts).
test('p15_v16 prelaunch hides catalog until go-live', async ({
  page,
  request,
  seed,
  inspect,
  adminLogin,
  isMobile,
}) => {
  // A purchase and the admin, and the dev server compiles each page on its first visit.
  test.setTimeout(240_000)
  const product = seed.journeys.j11
  // Not on sale yet: staff publish it when the store goes live.
  const unpublished = seed.journeys.j11Launch[isMobile ? 'mobile' : 'desktop']
  expect((await request.post(TOGGLE, { data: { on: true } })).status()).toBe(200)

  await test.step('an anonymous visitor sees "próximamente" everywhere', async () => {
    for (const route of ['/', '/catalogo', `/producto/${product.slug}`]) {
      await page.goto(route)
      await expect(
        page.getByRole('heading', { level: 1, name: 'Próximamente' }),
        route,
      ).toBeVisible()
      await expect(page.getByRole('heading', { name: product.name }), route).toHaveCount(0)
      await expectNoA11yViolations(page)
    }
  })

  // A staff session sees the catalog and buys like any customer, through the simulator.
  await adminLogin(page)
  const email = await buyAsGuest(page, product)
  const stateOf = async () => (await inspect.orders(email)).map((o) => o.state)
  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect(page.getByRole('heading', { level: 1, name: 'Pago confirmado' })).toBeVisible({
    timeout: 20_000,
  })
  await expectNoA11yViolations(page)
  const [order] = await inspect.orders(email)
  const { number } = order!
  expect(order!.state).toBe('paid')

  await test.step('staff refund the test order', async () => {
    await page.goto(`/admin/orders/order/?q=${encodeURIComponent(number)}`)
    await page.getByRole('link', { name: number, exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/orders\/order\/\d+\/change\//)
    await page.getByRole('button', { name: 'Registrar reembolso total' }).click()
    await expect(
      page.getByText('«Registrar reembolso total» aplicado: el pedido está en refunded.'),
    ).toBeVisible()
    expect(await stateOf()).toEqual(['refunded'])
  })

  await test.step('staff publish the catalog and turn the mode off', async () => {
    // Staff see the catalog as it will be: a product that is not published is not in it.
    const hidden = await page.request.get(`/api/catalog/products/${unpublished.slug}/`)
    expect(hidden.status()).toBe(404)

    await page.goto('/admin/catalog/product/?q=J11')
    for (const name of [product.name, unpublished.name]) {
      await page.getByRole('row').filter({ hasText: name }).getByRole('checkbox').check()
    }
    await page.getByRole('combobox', { name: /^Acción/ }).selectOption({ label: 'Publicar' })
    await page.getByRole('button', { name: 'Ejecutar', exact: true }).click()
    await expect(page.getByText('Publicados: 2.')).toBeVisible()

    // Going live is one switch (REQ-062).
    await page.goto('/admin/core/sitesetting/1/change/')
    await page.getByRole('checkbox', { name: 'Prelaunch mode' }).uncheck()
    await page.getByRole('button', { name: 'Guardar', exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/core\/sitesetting\/$/)
    // The staff session ends here: the next visitor is anonymous again.
    await page.context().clearCookies()
  })

  await test.step('the anonymous visitor now sees the catalog', async () => {
    await page.goto('/catalogo')
    await waitForHydration(page)
    await expect(page.getByRole('heading', { name: 'Próximamente' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: seed.catalog.hoodie.name }).first()).toBeVisible()
    await expectNoA11yViolations(page)
    // The product staff published a moment ago is on sale too.
    await openProduct(page, unpublished)
    await openProduct(page, product)
  })
})
