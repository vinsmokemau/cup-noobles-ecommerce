import { expect, test } from './fixtures'

test('p12_v23 sitemap canonical and json-ld', async ({ request, seed }) => {
  const { hoodie, hidden, featured } = seed.catalog

  // The sitemap lists active products and leaves out draft and archived ones.
  const sitemap = await request.get('/sitemap.xml')
  expect(sitemap.status()).toBe(200)
  const xml = await sitemap.text()
  expect(xml).toContain(`/producto/${hoodie.slug}</loc>`)
  expect(xml).toContain(`/producto/${featured[0]!.slug}</loc>`)
  expect(xml).not.toContain(hidden.draft.slug)
  expect(xml).not.toContain(hidden.archived.slug)

  // The product page, as the server renders it (no JavaScript).
  const response = await request.get(`/producto/${hoodie.slug}`)
  expect(response.status()).toBe(200)
  const html = await response.text()
  const canonical = html.match(/<link[^>]*rel="canonical"[^>]*href="([^"]+)"/)
  expect(canonical, 'canonical link').not.toBeNull()
  expect(new URL(canonical![1]!).pathname).toBe(`/producto/${hoodie.slug}`)
  expect(html).toMatch(/<meta[^>]*property="og:image"[^>]*content="https?:\/\/[^"]+"/)

  // G55: a meta description on the product page, and on the home and catalog pages.
  expect(html).toMatch(/<meta[^>]*name="description"[^>]*content="[^"]+"/)
  for (const path of ['/', '/catalogo']) {
    const page = await (await request.get(path)).text()
    expect(page, path).toMatch(/<meta[^>]*name="description"[^>]*content="[^"]+"/)
  }

  const ld = html.match(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/)
  expect(ld, 'JSON-LD').not.toBeNull()
  const data = JSON.parse(ld![1]!)
  expect(data['@type']).toBe('Product')
  expect(data.offers.priceCurrency).toBe('MXN')
  expect(data.offers.availability).toMatch(/^https:\/\/schema\.org\//)
})
