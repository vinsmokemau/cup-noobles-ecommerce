import { expect, test } from './fixtures'

// G18: server rendering reaches Django through the Nitro proxy (the proposed resolution, built in T12.1).
test('p12_v01 product HTML contains name and price', async ({ request, seed }) => {
  const { hoodie } = seed.catalog
  const response = await request.get(`/producto/${hoodie.slug}`)
  expect(response.status()).toBe(200)
  // Raw HTML: no JavaScript ran, so this is what the server rendered.
  const html = await response.text()
  expect(html).toContain(hoodie.name)

  const first = hoodie.variants.find((v) => v.in_stock)!
  const price = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(
    first.price_cents / 100,
  )
  expect(html).toContain(price)

  const ld = html.match(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/)
  expect(ld, 'JSON-LD is in the server HTML').not.toBeNull()
  const data = JSON.parse(ld![1]!)
  expect(data.offers.price).toBe((first.price_cents / 100).toFixed(2))
  expect(data.offers.priceCurrency).toBe('MXN')
})
