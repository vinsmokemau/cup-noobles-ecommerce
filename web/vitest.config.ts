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
    // With no provider every icon fails to load, and the warning about it can reach Vitest while
    // the worker closes, which fails the run. The setup file drops that one warning.
    setupFiles: ['tests/setup/setup.ts'],
    // The Nuxt environment starts in a `beforeAll` hook. On a cold cache (a fresh clone, or the
    // first run after this file changes) the first files wait for it longer than Vitest's 10 s.
    hookTimeout: 60_000,
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
