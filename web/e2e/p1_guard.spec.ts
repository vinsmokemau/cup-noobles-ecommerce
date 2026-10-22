import AxeBuilder from '@axe-core/playwright'
import { A11Y_TAGS, expect, expectNoA11yViolations, test } from './fixtures'

// Self-tests of the harness. They run in the `selftest` project, once.

test('p1_v08 offline guard aborts external request', async ({ page }) => {
  // The guard marks the test failed when it aborts an external request; `test.fail()` asserts that.
  test.fail()
  await page.goto('https://example.com/').catch(() => {})
})

test('p1_v08 offline guard lets localhost through', async ({ page }) => {
  const response = await page.goto('/')
  expect(response?.ok()).toBe(true)
})

test('p1_v20 axe runs the wcag 2.2 aa tags', async ({ page }) => {
  expect(A11Y_TAGS).toEqual(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])

  const original = AxeBuilder.prototype.withTags
  let seen: unknown
  AxeBuilder.prototype.withTags = function (tags) {
    seen = tags
    return original.call(this, tags)
  }
  // Two 10 px targets 2 px apart break WCAG 2.2 SC 2.5.8 (target size, 24 × 24 px).
  await page.setContent(`<!doctype html><html lang="es-MX"><head><title>Fixture</title></head>
    <body><main><h1>Fixture</h1>
      <button style="position:absolute;top:80px;left:0;width:10px;height:10px;padding:0">a</button>
      <button style="position:absolute;top:80px;left:12px;width:10px;height:10px;padding:0">b</button>
    </main></body></html>`)
  try {
    await expect(expectNoA11yViolations(page)).rejects.toThrow(/target-size/)
  } finally {
    AxeBuilder.prototype.withTags = original
  }
  expect(seen).toEqual(A11Y_TAGS)
})
