import { execFileSync } from 'node:child_process'
import { expect, test, waitForHydration } from './fixtures'

test('p12_v03 api failure shows retry not blank', async ({ page, seed }) => {
  const { hoodie } = seed.catalog
  await page.goto('/')
  await waitForHydration(page)

  // Client-side navigation: the catalog page asks the API, which fails.
  const fail = (route: { fulfill: (o: { status: number; body: string }) => Promise<void> }) =>
    route.fulfill({ status: 500, body: '{"detail":"boom"}' })
  await page.route('/api/**', fail)
  await page.getByRole('link', { name: 'Ver todo el catálogo' }).click()
  await expect(page).toHaveURL(/\/catalogo$/)
  const retry = page.getByRole('button', { name: 'Reintentar' })
  await expect(retry).toBeVisible()

  await page.unroute('/api/**', fail)
  await retry.click()
  await expect(page.getByRole('link', { name: hoodie.name }).first()).toBeVisible()
  await expect(retry).toHaveCount(0)
})

// A second storefront server whose API target cannot be reached (compose profile `api-down`). It
// is one server for both projects, so the desktop project runs the test and the mobile one skips it.
const COMPOSE = [
  'compose',
  '-f',
  '../docker-compose.yml',
  '-f',
  '../docker-compose.e2e.yml',
  '--profile',
  'api-down',
]
const API_DOWN_URL = 'http://localhost:3001'

test('p12_v25 ssr with api down renders error page', async ({ request, seed }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one shared server')
  // In a full run this server answers its first page only once the other specs wind down, so
  // the test lasts about as long as the suite (G72). Alone it takes under a minute.
  test.setTimeout(480_000)
  const { hoodie } = seed.catalog
  execFileSync('docker', [...COMPOSE, 'up', '-d', '--wait', 'web-api-down'], { stdio: 'inherit' })
  try {
    for (const path of [`/producto/${hoodie.slug}`, '/', '/catalogo']) {
      // A browser asks for HTML, which is what makes Nuxt render `error.vue`.
      const response = await request.get(`${API_DOWN_URL}${path}`, {
        headers: { accept: 'text/html' },
      })
      expect(response.status(), path).toBeGreaterThanOrEqual(500)
      const html = await response.text()
      expect(html.length, path).toBeGreaterThan(0)
      // error.vue: the title and the retry action, and no technical detail.
      expect(html, path).toContain('Algo salió mal de nuestro lado')
      expect(html, path).toContain('Volver a intentar')
      expect(html, path).not.toContain('api-unreachable')
    }
  } finally {
    execFileSync('docker', [...COMPOSE, 'stop', 'web-api-down'], { stdio: 'inherit' })
  }
})
