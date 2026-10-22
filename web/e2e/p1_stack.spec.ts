import { expect, test } from './fixtures'

test('p1_v01 same origin serves web and api', async ({ request, baseURL }) => {
  const home = await request.get('/')
  expect(home.status()).toBe(200)
  expect(home.headers()['content-type']).toContain('text/html')
  expect(await home.text()).toContain('<html')

  const schema = await request.get('/api/schema/?format=json')
  expect(schema.status()).toBe(200)
  expect(schema.headers()['content-type']).toContain('json')
  expect((await schema.json()).openapi).toMatch(/^3\.1/)

  const origin = new URL(baseURL!).origin
  expect([home.url(), schema.url()].map((u) => new URL(u).origin)).toEqual([origin, origin])
})

test('p1_v02 admin login reachable', async ({ request }) => {
  const login = await request.get('/admin/login/')
  expect(login.status()).toBe(200)
  const html = await login.text()
  expect(html).toContain('name="username"')
  expect(html).toContain('name="password"')
})
