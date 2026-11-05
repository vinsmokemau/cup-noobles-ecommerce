import { expect, test, waitForHydration, type Locator, type Page } from './fixtures'
import { catalogRoutes } from './routes'

// CR-33 and CR-36: 360 px wide, no horizontal scroll, and tap targets of at least 44 px.
test.use({ viewport: { width: 360, height: 740 } })

const TAP_TARGET = 44

// A radio or checkbox is a 20 px box inside an item row; the row, whose label fills it, is what a thumb
// reaches (DS size `2xl`).
// Buttons, links styled as buttons and text fields are their own target.
const CONTROLS = 'button, input:not([type="hidden"]), select, textarea, a[role="button"]'

async function tapTargets(page: Page, scope?: Locator) {
  const root = scope ?? page.locator('body')
  return root.evaluate((el, selector) => {
    const rows = new Set<Element>()
    for (const control of el.querySelectorAll(selector)) {
      const box = control.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) continue
      const isChoice = ['radio', 'checkbox'].includes(control.getAttribute('role') ?? '')
      rows.add(isChoice ? (control.closest('[data-slot="item"]') ?? control) : control)
    }
    return [...rows].map((row) => ({
      name: (row.textContent ?? row.getAttribute('aria-label') ?? row.tagName).trim().slice(0, 40),
      height: row.getBoundingClientRect().height,
    }))
  }, CONTROLS)
}

async function expectTapTargets(page: Page, label: string, scope?: Locator) {
  const targets = await tapTargets(page, scope)
  const small = targets.filter((t) => t.height < TAP_TARGET)
  expect(small, `${label}: controls under ${TAP_TARGET}px`).toEqual([])
}

test('p12_v21 no horizontal scroll at 360px', async ({ page, seed }) => {
  // Many routes in one test, and the dev server compiles each page on first visit.
  test.setTimeout(120_000)
  for (const route of catalogRoutes(seed)) {
    await test.step(route, async () => {
      await page.goto(route)
      await waitForHydration(page)
      const width = await page.evaluate(() => document.documentElement.scrollWidth)
      expect(width, `${route} scrollWidth`).toBeLessThanOrEqual(360)
      await expectTapTargets(page, route)
    })
  }

  await test.step('product page: variant radios', async () => {
    await page.goto(`/producto/${seed.catalog.hoodie.slug}`)
    await waitForHydration(page)
    const radios = page.getByRole('radio')
    expect(await radios.count()).toBeGreaterThan(0)
    for (const radio of await radios.all()) {
      const row = await radio.evaluate(
        (el) => (el.closest('[data-slot="item"]') ?? el).getBoundingClientRect().height,
      )
      expect(row).toBeGreaterThanOrEqual(TAP_TARGET)
    }
  })

  await test.step('catalog: filter panel', async () => {
    await page.goto('/catalogo')
    await waitForHydration(page)
    await page.getByRole('button', { name: 'Filtrar' }).click()
    const panel = page.getByRole('dialog')
    await expect(panel).toBeVisible()
    const checkboxes = panel.getByRole('checkbox')
    expect(await checkboxes.count()).toBeGreaterThan(0)
    for (const box of await checkboxes.all()) {
      const row = await box.evaluate(
        (el) => (el.closest('[data-slot="item"]') ?? el).getBoundingClientRect().height,
      )
      expect(row).toBeGreaterThanOrEqual(TAP_TARGET)
    }
    // The slideover's close button (size `xl`) is among the controls checked here.
    await expectTapTargets(page, 'filter panel', panel)
    // Nuxt UI's built-in text is es-MX through CnApp (DSR-13), not English "Close".
    await expect(panel.getByRole('button', { name: 'Cerrar' })).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
      'filter panel scrollWidth',
    ).toBeLessThanOrEqual(360)
  })
})
