import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { catalogRoutes } from './routes'
import type { SeedManifest } from './fixtures'

// The E2E stack serves the storefront from the Nuxt dev server, which compiles a page the first
// time it is visited. With the desktop and mobile projects running in parallel, that first visit
// to a page could outlast a test's timeout and pass only on retry, which fails a CI run. This
// visits every catalog route once, one after another, before any spec starts, so the specs run
// against compiled pages. It asserts nothing: a broken page is the specs' job to report.
const MANIFEST_PATH = fileURLToPath(new URL('../../var/e2e/manifest.json', import.meta.url))
const BASE_URL = 'http://localhost:8080'

export default async function globalSetup(): Promise<void> {
  const seed = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8')) as SeedManifest
  const routes = [
    ...catalogRoutes(seed),
    `/buscar?q=${encodeURIComponent(seed.catalog.search.query)}`,
  ]
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ baseURL: BASE_URL })
    for (const route of routes) {
      try {
        await page.goto(route, { timeout: 120_000 })
        await page.waitForFunction(
          () => {
            const nuxt = (window as unknown as { useNuxtApp?: () => { isHydrating: boolean } })
              .useNuxtApp
            return nuxt !== undefined && !nuxt().isHydrating
          },
          undefined,
          { timeout: 120_000 },
        )
      } catch {
        // Warming is best effort; the specs report any real failure.
      }
    }
  } finally {
    await browser.close()
  }
}
