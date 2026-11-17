import { defineConfig, devices } from '@playwright/test'

// End-to-end harness (SPEC.md §4.6). The stack is the compose E2E stack behind Caddy, so the
// specs reach the same origin a customer does.
const BASE_URL = 'http://localhost:8080'
// `make test-all` runs Playwright inside the `e2e` compose service (T15.5), which shares the proxy's
// network, so the address is the same. There is no Docker CLI there: the Makefile starts the stack.
const IN_COMPOSE = !!process.env.E2E_IN_COMPOSE
// The harness's own checks: the offline guard and the axe wrapper (Phase 1), and the internal
// network of the offline run (P15-V13).
const GUARD_SPECS = [/p1_guard\.spec\.ts/, /p15_offline\.spec\.ts/]
// Pre-launch mode is one switch for the whole stack, so the specs that turn it on run after the
// others and one at a time: P12-V28 and the J11 journey on the desktop device (`prelaunch`), then
// J11 on the mobile device (`prelaunch-mobile`).
const J11_SPEC = /j11_prelaunch\.spec\.ts/
const PRELAUNCH_SPECS = [/p12_prelaunch\.spec\.ts/, J11_SPEC]
// P12-V25 starts a second storefront server (compose profile `api-down`). While other specs run,
// that server takes minutes to answer its first page (G72), so the test has a project of its own
// and the Makefile runs it as a second step, after the others. It is not a `dependencies` project:
// a run filtered by file would then execute every spec, and a failure elsewhere would skip it.
const API_DOWN_SPECS = /p12_errors\.spec\.ts/
const API_DOWN_TEST = /p12_v25/

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: true,
  // A test that passes only on retry still fails the run in CI.
  retries: process.env.CI ? 1 : 0,
  failOnFlakyTests: !!process.env.CI,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
  },
  webServer: IN_COMPOSE
    ? undefined
    : {
        // `up --wait` returns once the stack is healthy; the trailing keep-alive is what lets
        // Playwright treat the command as a running server. The stack is left up afterwards.
        command:
          'docker compose -f ../docker-compose.yml -f ../docker-compose.e2e.yml up --wait && node -e "setInterval(() => {}, 1 << 30)"',
        url: `${BASE_URL}/api/health/`,
        // `make e2e` starts the E2E stack first (T13.16), so the stack is always running by now;
        // Playwright only checks it.
        reuseExistingServer: true,
        timeout: 10 * 60 * 1000,
      },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: [...GUARD_SPECS, ...PRELAUNCH_SPECS],
      grepInvert: API_DOWN_TEST,
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'] },
      testIgnore: [...GUARD_SPECS, ...PRELAUNCH_SPECS],
      grepInvert: API_DOWN_TEST,
    },
    {
      name: 'prelaunch',
      use: { ...devices['Desktop Chrome'] },
      testMatch: PRELAUNCH_SPECS,
      dependencies: ['desktop', 'mobile'],
      workers: 1,
    },
    {
      name: 'prelaunch-mobile',
      use: { ...devices['Pixel 7'] },
      testMatch: J11_SPEC,
      dependencies: ['prelaunch'],
    },
    {
      name: 'api-down',
      use: { ...devices['Desktop Chrome'] },
      testMatch: API_DOWN_SPECS,
      grep: API_DOWN_TEST,
    },
    // The harness's own checks: they assert the guard, the axe wrapper and the network, so they
    // run once.
    { name: 'selftest', use: { ...devices['Desktop Chrome'] }, testMatch: GUARD_SPECS },
  ],
})
