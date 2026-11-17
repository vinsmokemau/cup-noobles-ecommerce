import { defineVitestConfig } from '@nuxt/test-utils/config'

// Frontend unit and component tests (SPEC.md §4.6). End-to-end specs live in
// e2e/ and belong to Playwright, so Vitest only looks under tests/.
export default defineVitestConfig({
  test: {
    environment: 'nuxt',
    // The test environment runs without a server, so Nuxt Icon would use its `iconify` provider
    // and ask the public Iconify API for every icon a mounted component shows: an outbound
    // request on every run (CR-41), and on an internal network a failure that arrives while the
    // worker closes (T15.5). No test reads an icon's drawing, so the tests get no provider at all.
    environmentOptions: { nuxt: { overrides: { icon: { provider: 'none' } } } },
    include: ['tests/**/*.test.ts'],
    // No unit test exists until Phase 12; an empty run must not fail `make test`.
    passWithNoTests: true,
    coverage: {
      provider: 'v8',
      include: ['app/composables/**'],
      // Gate for the composables scope (§4.6, Coverage gates); checked at phase close.
      thresholds: {
        lines: 80,
        branches: 80,
        functions: 80,
        statements: 80,
      },
    },
  },
})
