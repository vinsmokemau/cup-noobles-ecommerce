import AxeBuilder from '@axe-core/playwright'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test as base, expect, type Page } from '@playwright/test'
import { a11yExceptions } from './a11y-exceptions'

// WCAG 2.2 A and AA (CR-35).
export const A11Y_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

type Ref = { slug: string; name: string }
// A product with its variants, in the order the product page lists them.
export type SeededProduct = Ref & { variants: { sku: string; options: Record<string, string> }[] }
// One copy of a product per Playwright project, for a journey that asserts stock counts: the
// `desktop` and `mobile` projects run at the same time, so each buys its own.
export type PerProject = { desktop: SeededProduct; mobile: SeededProduct }

// What `manage.py seed_e2e` wrote to `var/e2e/manifest.json`, so specs never hard-code slugs,
// SKUs, emails or order numbers. Each phase adds its own part.
export interface SeedManifest {
  // The demo dataset of SPEC.md 15.A, which `seed_e2e` includes (T15.2). A spec that changes
  // stock buys from `journeys`, never from here.
  demo: {
    staff: { email: string; password: string }
    // The email of the seeded guest order history.
    guest: { email: string }
    products: Record<
      'tcg' | 'fundas' | 'sudadera' | 'playera' | 'figura' | 'artbook',
      SeededProduct
    >
    hidden: { draft: SeededProduct; archived: SeededProduct }
    // Order numbers: a completed delivery, an OXXO order that is pending when first seeded and
    // expires with its voucher, and a paid order with a CFDI request.
    orders: { completed: string; oxxo: string; cfdi: string }
  }
  // Each Release 1 journey's own copy of the 15.A product it buys (SKU prefix `E2E-J<n>`).
  // `seed_e2e` puts the stock back to the 15.A count on every run.
  journeys: {
    j1: PerProject
    j3: PerProject
    j4: PerProject
    j8: PerProject
    j10: SeededProduct
    j11: SeededProduct
  }
  catalog: {
    hidden: { draft: Ref; archived: Ref }
    featured: Ref[]
    linea: { key: string; value: string; matching: Ref[]; other: Ref[] }
    category: { slug: string; products: Ref[]; outside: Ref }
    hoodie: Ref & {
      variants: { options: Record<string, string>; price_cents: number; in_stock: boolean }[]
    }
    search: Ref & { query: string; typo: string }
    // A product with two units, which the stock-loss spec (P13-V18) uses up; `seed_e2e` refills it.
    // A product with a per-customer limit that the purchase-limit spec (P13-V24) asks to exceed.
    checkoutErrors: { scarce: Ref & { sku: string }; limited: Ref & { limit: number } }
  }
  // A fictional staff account (T12.15), apart from the demo staff user.
  staff: { email: string; password: string }
}

const MANIFEST_PATH = fileURLToPath(new URL('../../var/e2e/manifest.json', import.meta.url))
// Where `FileEmailSender` writes (SPEC.md §4.3): the api's `var/` is this folder, bind-mounted.
const EMAIL_DIR = fileURLToPath(new URL('../../var/emails/', import.meta.url))
// `<YYYYmmdd-HHMMSS>-<template>-<outbox id>.html`; an attachment's name has one more part.
const EMAIL_FILE = /^(\d{8}-\d{6})-([a-z0-9_]+)-(\w+)\.html$/

// What `POST /dev/test/run/` may run (SPEC.md 15.3). The request's `args` follow the command.
export type RunnableCommand =
  | 'expire_reservations'
  | 'advance_orders'
  | 'reconcile_payments'
  | 'sync_shipments'
  | 'send_outbox'
  | 'mock_payments expire-order'
  | 'mock_payments deliver --once'

// Physical units over every location, plus pre-order units (`GET /dev/test/inventory/<sku>/`).
export type StockCounts = { on_hand: number; reserved: number; preorder_committed: number }
export type InspectedOrder = { number: string; state: string }

// One email as `FileEmailSender` wrote it: both bodies, and the files sent with it by file name
// (the CFDI PDF and XML).
export type SentEmail = {
  template: string
  html: string
  text: string
  attachments: Record<string, Buffer>
}

export type Helpers = {
  // Runs one job or mock-payment action now and returns what it printed. The E2E stack has no
  // scheduler (§4.8, G77), so a spec moves the clock-driven jobs itself. A job acts on every
  // order in the stack, not only the spec's own.
  run: (command: RunnableCommand, args?: string[]) => Promise<string>
  // Signs the page's browser context in to the admin as the seeded staff user (15.A).
  adminLogin: (page: Page) => Promise<void>
  inspect: {
    inventory: (sku: string) => Promise<StockCounts>
    // The orders placed with one email, newest first.
    orders: (email: string) => Promise<InspectedOrder[]>
  }
  // The newest email sent to that address, or null while there is none. An email is written only
  // when `send_outbox` runs, and another worker's run may be the one that sends it: after
  // `run('send_outbox')`, read it with `expect.poll`.
  readLatestEmail: (to: string) => Promise<SentEmail | null>
}

type EmailFile = { prefix: string; stamp: string; template: string; tail: string }

// The emails among the folder's file names, newest first: by the send time in the name, then by
// outbox id.
function emailFiles(names: string[]): EmailFile[] {
  return names
    .flatMap((name) => {
      const match = EMAIL_FILE.exec(name)
      if (!match) return []
      return [{ prefix: name.slice(0, -5), stamp: match[1]!, template: match[2]!, tail: match[3]! }]
    })
    .sort((a, b) => b.stamp.localeCompare(a.stamp) || (Number(b.tail) || 0) - (Number(a.tail) || 0))
}

function readEmail(file: EmailFile, names: string[]): SentEmail {
  const attachments: Record<string, Buffer> = {}
  for (const name of names) {
    if (name.startsWith(`${file.prefix}-`)) {
      attachments[name.slice(file.prefix.length + 1)] = readFileSync(join(EMAIL_DIR, name))
    }
  }
  return {
    template: file.template,
    html: readFileSync(join(EMAIL_DIR, `${file.prefix}.html`), 'utf8'),
    text: readFileSync(join(EMAIL_DIR, `${file.prefix}.txt`), 'utf8'),
    attachments,
  }
}

// Offline guard (CR-41): `localhost` passes, any other http(s) request is aborted and fails the
// test that made it.
export const test = base.extend<{ offlineGuard: undefined; seed: SeedManifest } & Helpers>({
  seed: async ({ page: _page }, use) => {
    await use(JSON.parse(readFileSync(MANIFEST_PATH, 'utf8')) as SeedManifest)
  },
  run: async ({ request }, use) => {
    await use(async (command, args = []) => {
      const response = await request.post('/dev/test/run/', { data: { command, args } })
      const body = (await response.json()) as { detail?: string; output?: string }
      expect(
        response.ok(),
        `run("${command}") failed: ${body.detail ?? response.status()}\n${body.output ?? ''}`,
      ).toBe(true)
      return body.output ?? ''
    })
  },
  adminLogin: async ({ seed }, use) => {
    await use(async (page) => {
      const { email, password } = seed.demo.staff
      await page.goto('/admin/login/')
      await page.getByLabel('Email').fill(email)
      await page.getByLabel('Contraseña').fill(password)
      await page.getByRole('button', { name: 'Identificarse' }).click()
      await expect(page).toHaveURL(/\/admin\/$/)
    })
  },
  inspect: async ({ request }, use) => {
    await use({
      inventory: async (sku) => {
        const response = await request.get(`/dev/test/inventory/${encodeURIComponent(sku)}/`)
        expect(response.ok(), `inspect.inventory("${sku}") answered ${response.status()}`).toBe(
          true,
        )
        return (await response.json()) as StockCounts
      },
      orders: async (email) => {
        const response = await request.get(`/dev/test/orders/?email=${encodeURIComponent(email)}`)
        expect(response.ok(), `inspect.orders("${email}") answered ${response.status()}`).toBe(true)
        return ((await response.json()) as { orders: InspectedOrder[] }).orders
      },
    })
  },
  readLatestEmail: async ({ inspect }, use) => {
    await use(async (to) => {
      // The files hold the two bodies and nothing says who an email was sent to (G78), so the
      // recipient is found through their orders: every R1 email names its order ("Pedido CN-…").
      const numbers = (await inspect.orders(to)).map((order) => order.number)
      if (numbers.length === 0) return null
      const naming = new RegExp(`(?:${numbers.join('|')})(?!\\d)`)
      // Only emails written since the E2E data was last seeded: `make e2e-reset` starts the order
      // numbers again, and an older file can name the same number for another customer.
      const seededAt = statSync(MANIFEST_PATH).mtimeMs
      const names = existsSync(EMAIL_DIR) ? readdirSync(EMAIL_DIR) : []
      for (const file of emailFiles(names)) {
        const text = join(EMAIL_DIR, `${file.prefix}.txt`)
        if (statSync(join(EMAIL_DIR, `${file.prefix}.html`)).mtimeMs < seededAt) break
        // The `.txt` is written right after the `.html`; skip an email that is still being written.
        if (!existsSync(text)) continue
        if (naming.test(readFileSync(text, 'utf8'))) return readEmail(file, names)
      }
      return null
    })
  },
  offlineGuard: [
    async ({ context }, use) => {
      const blocked: string[] = []
      await context.route(/^https?:/, (route) => {
        const { hostname, href } = new URL(route.request().url())
        if (LOCAL_HOSTS.has(hostname)) return route.fallback()
        blocked.push(href)
        return route.abort('blockedbyclient')
      })
      await use(undefined)
      expect(blocked, 'external requests are not allowed (Part A is offline)').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

// Fails on any `serious` or `critical` violation under the WCAG 2.2 AA tags, minus the entries
// in a11y-exceptions.ts.
export async function expectNoA11yViolations(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).withTags(A11Y_TAGS).analyze()
  const blocking = violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({
      ...v,
      nodes: v.nodes.filter(
        (node) =>
          !a11yExceptions.some(
            (e) => e.rule === v.id && node.target.some((t) => String(t) === e.selector),
          ),
      ),
    }))
    .filter((v) => v.nodes.length > 0)
  expect(
    blocking.map((v) => ({
      rule: v.id,
      impact: v.impact,
      targets: v.nodes.map((n) => n.target.join(' ')),
    })),
    'axe found serious or critical violations',
  ).toEqual([])
}

// Pages are rendered on the server, so a click before Vue hydrates does nothing. Waits for Nuxt to
// finish hydrating (never for `networkidle`, DS T5.7).
export async function waitForHydration(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const nuxt = (window as unknown as { useNuxtApp?: () => { isHydrating: boolean } }).useNuxtApp
    return nuxt !== undefined && !nuxt().isHydrating
  })
}
