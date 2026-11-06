import { expect, test, waitForHydration } from './fixtures'

// The dev-only toggle goes through the proxy to the API (T12.15). The mode is one switch for the
// whole stack, so this spec has its own project (playwright.config.ts) that runs after the others.
const TOGGLE = '/dev/test/prelaunch/'

test('p12_v28 prelaunch page for anonymous visitors', async ({ page, request, seed, browser }) => {
  const { hoodie } = seed.catalog
  const routes = ['/', '/catalogo', `/producto/${hoodie.slug}`]
  const set = async (on: boolean) => {
    const response = await request.post(TOGGLE, { data: { on } })
    expect(response.status()).toBe(200)
  }

  await set(true)
  try {
    // Anonymous: the page, status 200 and noindex, in the raw HTML and in the browser.
    for (const route of routes) {
      const raw = await request.get(route, { headers: { accept: 'text/html' } })
      expect(raw.status(), route).toBe(200)
      expect(await raw.text(), route).toMatch(/<meta[^>]+name="robots"[^>]+content="noindex/)

      const response = await page.goto(route)
      expect(response?.status(), route).toBe(200)
      await expect(page.getByRole('heading', { level: 1, name: 'Próximamente' })).toBeVisible()
      await expect(page.getByRole('heading', { name: hoodie.name })).toHaveCount(0)
    }

    // Staff: a signed-in session sees the catalog.
    const context = await browser.newContext()
    const staff = await context.newPage()
    await staff.goto('/admin/login/')
    await staff.getByLabel(/correo|email|usuario|username/i).fill(seed.staff.email)
    await staff.getByLabel(/contraseña|password/i).fill(seed.staff.password)
    await staff.locator('input[type=submit]').click()
    await expect(staff).toHaveURL(/\/admin\/$/)
    await staff.goto(`/producto/${hoodie.slug}`)
    await waitForHydration(staff)
    await expect(staff.getByRole('heading', { level: 1, name: hoodie.name })).toBeVisible()
    await expect(staff.getByRole('heading', { name: 'Próximamente' })).toHaveCount(0)
    await context.close()
  } finally {
    await set(false)
  }

  // Off again: the public sees the catalog.
  await page.goto('/catalogo')
  await expect(page.getByRole('heading', { name: 'Próximamente' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: hoodie.name }).first()).toBeVisible()
})
