import { expect, test, waitForHydration, type Page } from './fixtures'

const card = (page: Page, slug: string) => page.locator(`a[href="/producto/${slug}"]`).first()

test('p12_v13 home shows featured products', async ({ page, seed }) => {
  await page.goto('/')
  for (const product of seed.catalog.featured) {
    await expect(card(page, product.slug)).toBeVisible()
  }
  const first = seed.catalog.featured[0]!
  await card(page, first.slug).click()
  await expect(page).toHaveURL(new RegExp(`/producto/${first.slug}$`))
  await expect(page.getByRole('heading', { level: 1, name: first.name })).toBeVisible()
})

test('p12_v14 facet filter updates results and url', async ({ page, seed }) => {
  const { linea } = seed.catalog
  await page.goto('/catalogo')
  await waitForHydration(page)
  const all = [...linea.matching, ...linea.other]
  for (const product of all) {
    await expect(card(page, product.slug)).toBeVisible()
  }

  // The sidebar is open on desktop; below `lg` a button opens it.
  const filter = page.getByRole('checkbox', { name: new RegExp(`^${linea.value}`) })
  if (!(await filter.isVisible())) await page.getByRole('button', { name: 'Filtrar' }).click()
  await filter.click()

  await expect(page).toHaveURL(new RegExp(`attr\\.${linea.key}=${linea.value}`))
  for (const product of linea.other) {
    await expect(page.locator(`a[href="/producto/${product.slug}"]`)).toHaveCount(0)
  }
  for (const product of linea.matching) {
    await expect(card(page, product.slug)).toBeVisible()
  }

  await page.goBack()
  await expect(page).not.toHaveURL(/attr\./)
  for (const product of all) {
    await expect(card(page, product.slug)).toBeVisible()
  }
})

test('p12_v15 category page is scoped', async ({ page, seed }) => {
  const { category } = seed.catalog
  await page.goto(`/catalogo/${category.slug}`)
  for (const product of category.products) {
    await expect(card(page, product.slug)).toBeVisible()
  }
  await expect(page.locator(`a[href="/producto/${category.outside.slug}"]`)).toHaveCount(0)
})
