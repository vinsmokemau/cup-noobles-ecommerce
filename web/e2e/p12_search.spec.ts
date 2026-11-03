import { expect, test } from './fixtures'

test('p12_v17 search tolerates a typo', async ({ page, seed }) => {
  const { search } = seed.catalog
  for (const query of [search.query, search.typo]) {
    await page.goto('/buscar')
    await page.getByRole('searchbox', { name: 'Buscar productos' }).fill(query)
    await page.getByRole('button', { name: 'Buscar', exact: true }).click()
    await expect(page).toHaveURL(/\/buscar\?q=/)
    await expect(page.locator(`a[href="/producto/${search.slug}"]`).first()).toBeVisible()
  }
})
