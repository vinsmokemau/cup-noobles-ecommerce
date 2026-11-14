import { defineConfig, devices } from '@playwright/test'

// End-to-end harness (SPEC.md §4.6). The stack is the compose E2E stack behind Caddy, so the
// specs reach the same origin a customer does.
const BASE_URL = 'http://localhost:8080'
const GUARD_SPECS = /p1_guard\.spec\.ts/
// Pre-launch mode is one switch for the whole stack, so its spec runs alone, after the others.
const PRELAUNCH_SPECS = /p12_prelaunch\.spec\.ts/
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
  webServer: {
    // `up --wait` returns once the stack is healthy; the trailing keep-alive is what lets
    // Playwright treat the command as a running server. The stack is left up afterwards.
    command:
      'docker compose -f ../docker-compose.yml -f ../docker-compose.e2e.yml up --wait && node -e "setInterval(() => {}, 1 << 30)"',
    url: `${BASE_URL}/api/health/`,
    // `make e2e` and `make e2e-all` start the E2E stack first (T13.16), so the stack is always
    // running by now; Playwright only checks it, in CI as well.
    reuseExistingServer: true,
    timeout: 10 * 60 * 1000,
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: [GUARD_SPECS, PRELAUNCH_SPECS],
      grepInvert: API_DOWN_TEST,
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'] },
      testIgnore: [GUARD_SPECS, PRELAUNCH_SPECS],
      grepInvert: API_DOWN_TEST,
    },
    {
      name: 'prelaunch',
      use: { ...devices['Desktop Chrome'] },
      testMatch: PRELAUNCH_SPECS,
      dependencies: ['desktop', 'mobile'],
    },
    {
      name: 'api-down',
      use: { ...devices['Desktop Chrome'] },
      testMatch: API_DOWN_SPECS,
      grep: API_DOWN_TEST,
    },
    // The harness's own checks: they assert the guard and the axe wrapper, so they run once.
    { name: 'selftest', use: { ...devices['Desktop Chrome'] }, testMatch: GUARD_SPECS },
  ],
})
