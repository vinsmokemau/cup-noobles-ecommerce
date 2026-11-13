import { expectNoA11yViolations, expect, test, waitForHydration } from './fixtures'
import { catalogRoutes } from './routes'

test('p12_v19 axe on every catalog page', async ({ page, seed }) => {
  // Many routes in one test, and the dev server compiles each page on first visit.
  test.setTimeout(300_000)
  for (const route of catalogRoutes(seed)) {
    await test.step(route, async () => {
      const response = await page.goto(route)
      expect(response?.status(), route).toBe(200)
      await waitForHydration(page)
      await expectNoA11yViolations(page)
    })
  }

  // The search results and the open filter panel are states of those routes.
  await test.step('/buscar with results', async () => {
    await page.goto(`/buscar?q=${encodeURIComponent(seed.catalog.search.query)}`)
    await waitForHydration(page)
    await expect(
      page.locator(`a[href="/producto/${seed.catalog.search.slug}"]`).first(),
    ).toBeVisible()
    await expectNoA11yViolations(page)
  })

  await test.step('/catalogo with the filters open', async () => {
    await page.goto('/catalogo')
    await waitForHydration(page)
    const open = page.getByRole('button', { name: 'Filtrar' })
    if (await open.isVisible()) await open.click()
    await expect(page.getByRole('checkbox').first()).toBeVisible()
    await expectNoA11yViolations(page)
  })
})
