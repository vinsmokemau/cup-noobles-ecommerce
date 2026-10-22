import { expect, expectNoA11yViolations, test } from './fixtures'

test('p1_v09 index page loads and passes axe', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expectNoA11yViolations(page)
})
