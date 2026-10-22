import AxeBuilder from '@axe-core/playwright'
import { test as base, expect, type Page } from '@playwright/test'
import { a11yExceptions } from './a11y-exceptions'

// WCAG 2.2 A and AA (CR-35).
export const A11Y_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

// Offline guard (CR-41): `localhost` passes, any other http(s) request is aborted and fails the
// test that made it.
export const test = base.extend<{ offlineGuard: undefined }>({
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
