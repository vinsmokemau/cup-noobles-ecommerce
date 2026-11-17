import { describe, expect, it } from 'vitest'

// Part A makes no outbound connection (CR-41), and `make test-all` passes with the network
// internal (P15-V14). The component tests mount Design System parts that show icons. Without a
// server, Nuxt Icon uses its `iconify` provider and asks the public Iconify API for each one, so
// vitest.config.ts gives the test environment no icon provider (T15.5).
describe('unit tests are offline', () => {
  it('p15_v14 the test environment has no icon provider', () => {
    expect(useAppConfig().icon.provider).toBe('none')
  })
})
