import { defineConfig, devices } from '@playwright/test'

// End-to-end harness (SPEC.md §4.6). The stack is the compose E2E stack behind Caddy, so the
// specs reach the same origin a customer does.
const BASE_URL = 'http://localhost:8080'
const GUARD_SPECS = /p1_guard\.spec\.ts/

export default defineConfig({
  testDir: './e2e',
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
    reuseExistingServer: !process.env.CI,
    timeout: 10 * 60 * 1000,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] }, testIgnore: GUARD_SPECS },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, testIgnore: GUARD_SPECS },
    // The harness's own checks: they assert the guard and the axe wrapper, so they run once.
    { name: 'selftest', use: { ...devices['Desktop Chrome'] }, testMatch: GUARD_SPECS },
  ],
})
